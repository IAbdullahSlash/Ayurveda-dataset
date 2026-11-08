#!/usr/bin/env python3
"""Refresh identifier-bound source evidence for name and taxonomy gaps.

Only public Wikidata/GBIF metadata is collected. Proposed identities and source
labels remain distinguishable from qualified botanical or language approval.
"""
import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I omits the script folder
from lib.review import write_review_csv

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/source_gap_research'
UA = {'User-Agent': 'AyurKB-source-gap-audit/1.0 (research; public metadata)'}


def taxon_key(value):
    text = str(value).strip()
    return text[:-2] if re.fullmatch(r'\d+\.0', text) else text


def selected_entity(entity, retrieved, response_hash):
    def claims(prop):
        return [str(c['mainsnak']['datavalue']['value']) for c in entity.get('claims', {}).get(prop, [])
                if c.get('rank') != 'deprecated' and 'datavalue' in c.get('mainsnak', {})]
    return dict(qid=entity['id'], labels={k:v['value'] for k,v in entity.get('labels', {}).items()},
        aliases_hi=[v['value'] for v in entity.get('aliases', {}).get('hi', [])],
        gbif_ids=claims('P846'), scientific_names=claims('P225'),
        revision_id=entity.get('lastrevid'), modified=entity.get('modified'), retrieved_utc=retrieved,
        source_url='https://www.wikidata.org/wiki/' + entity['id'], response_sha256=response_hash)


def hindi_candidate(herb, entity):
    if entity.get('qid') != herb['wikidata_qid']:
        return '', 'identifier_mismatch'
    if taxon_key(herb['gbif_key']) not in entity.get('gbif_ids', []):
        return '', 'gbif_claim_requires_alignment_review'
    label = entity.get('labels', {}).get('hi', '').strip()
    if not label:
        return '', 'source_has_no_hindi_label'
    if not re.search('[ऀ-ॿ]', label):
        return '', 'source_hindi_label_requires_script_review'
    return label, 'identifier_bound_source_label_unreviewed'


def fetch_json(url, params=None):
    response = requests.get(url, params=params, headers=UA, timeout=45)
    response.raise_for_status()
    data = response.json()
    if 'error' in data:
        raise ValueError('Source API error: ' + str(data['error'].get('code', 'unknown')))
    return data, hashlib.sha256(response.content).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true', help='Fetch missing public source snapshots; default uses existing snapshots')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    herbs = pd.read_csv(ROOT / 'data/processed/herbs.csv', keep_default_na=False)
    missing = herbs[herbs.name_hi_common.eq('')]
    wd_path = OUT / 'wikidata_entities.json'
    entities = json.loads(wd_path.read_text(encoding="utf-8")) if wd_path.exists() else {}
    qids = sorted({q for q in missing.wikidata_qid if re.fullmatch('Q[0-9]+', q)})
    todo = [q for q in qids if q not in entities]
    if args.fetch:
        for start in range(0, len(todo), 40):
            batch = todo[start:start+40]
            data, sha = fetch_json('https://www.wikidata.org/w/api.php',
                {'action':'wbgetentities', 'ids':'|'.join(batch), 'props':'labels|aliases|claims',
                 'languages':'hi|sa|en', 'format':'json'})
            if set(data.get('entities', {})) != set(batch):
                raise ValueError('Wikidata response omitted requested entity IDs')
            retrieved = datetime.now(timezone.utc).isoformat()
            for key, entity in data['entities'].items():
                if 'missing' in entity or 'id' not in entity:
                    entities[key] = {'qid':key, 'missing':True, 'retrieved_utc':retrieved, 'response_sha256':sha}
                else:
                    entities[key] = selected_entity(entity, retrieved, sha)
            wd_path.write_text(json.dumps(entities, ensure_ascii=False, indent=2) + '\n', encoding="utf-8")
            print(f'Wikidata snapshots {min(start+40, len(todo))}/{len(todo)}', flush=True)
            time.sleep(1)
    proposals = []
    for herb in missing.to_dict('records'):
        entity = entities.get(herb['wikidata_qid'])
        if not herb['wikidata_qid']:
            label, state = '', 'no_existing_wikidata_identifier'
        elif entity is None:
            label, state = '', 'source_not_collected'
        elif entity.get('missing'):
            label, state = '', 'source_entity_missing'
        else:
            label, state = hindi_candidate(herb, entity)
        proposals.append(dict(herb_id=herb['herb_id'], accepted_name=herb['accepted_name'],
            wikidata_qid=herb['wikidata_qid'], gbif_key=taxon_key(herb['gbif_key']), proposed_hi=label,
            evidence_state=state, source_reference=entity.get('source_url', '') if entity else '',
            source_revision=entity.get('revision_id', '') if entity else '',
            verdict='', corrected_value='', reviewer='', reference=''))
    names = pd.DataFrame(proposals)
    write_review_csv(names, OUT / 'hindi_name_gaps.csv')

    gbif_path = OUT / 'gbif_gap_snapshots.json'
    gbif = json.loads(gbif_path.read_text(encoding="utf-8")) if gbif_path.exists() else {}
    unresolved = herbs[herbs.gbif_key.eq('') | herbs.family.eq('')]
    if args.fetch:
        for name in sorted(set(unresolved.accepted_name) - set(gbif)):
            data, sha = fetch_json('https://api.gbif.org/v1/species/match',
                {'name':name, 'kingdom':'Plantae', 'verbose':'true'})
            gbif[name] = {'response':data, 'response_sha256':sha,
                'retrieved_utc':datetime.now(timezone.utc).isoformat(),
                'source_url':'https://api.gbif.org/v1/species/match', 'query_name':name}
            gbif_path.write_text(json.dumps(gbif, ensure_ascii=False, indent=2) + '\n', encoding="utf-8")
            print('GBIF snapshot: ' + name, flush=True)
            time.sleep(1)
    taxonomy = []
    for herb in unresolved.to_dict('records'):
        snapshot = gbif.get(herb['accepted_name'], {})
        data = snapshot.get('response', {})
        taxonomy.append(dict(herb_id=herb['herb_id'], name_in_current_master=herb['accepted_name'],
            match_type=data.get('matchType', ''), candidate_name=data.get('canonicalName', ''),
            candidate_key=data.get('acceptedUsageKey', data.get('usageKey', '')),
            rank=data.get('rank', ''), status=data.get('status', ''), family=data.get('family', ''),
            interpretation='Candidate only; no species merge or correction approved. Mineral and higher-rank entries may be legitimate non-species records.',
            verdict='', corrected_value='', reviewer='', reference=''))
    write_review_csv(pd.DataFrame(taxonomy), OUT / 'taxonomy_gap_candidates.csv')
    report = dict(missing_hindi_names=len(missing), existing_qids=len(qids),
        wikidata_snapshots=len(entities), name_states=names.evidence_state.value_counts().to_dict(),
        taxonomy_gap_records=len(unresolved), gbif_snapshots=len(gbif),
        canonical_names_changed=0, qualified_reviews_supplied=0)
    (OUT / 'status.json').write_text(json.dumps(report, indent=2) + '\n', encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
