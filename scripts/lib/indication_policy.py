"""Conservative indication containment; a review finding is not a replacement label."""
from pathlib import Path
import unicodedata
from collections import defaultdict
import pandas as pd
from lib.keys import skeleton, skeleton_variants

ROOT = Path(__file__).resolve().parents[2]
TARGET_FIELDS = ('disease_id', 'disease_term_iast', 'disease_name_en')
BLOCKED = {'quarantined', 'candidate_review_pending', 'unmatched'}
ACTIVE = {'source_matched_unreviewed', 'alias_reviewed'}


def contain_indications(frame, decisions=None):
    """Clear active targets while preserving originals and the evidence for containment."""
    out = frame.copy()
    if decisions is None:
        decisions = pd.read_csv(ROOT / 'curation/indication_quarantine.csv', keep_default_na=False)
    for field in TARGET_FIELDS:
        if 'original_' + field not in out:
            out['original_' + field] = out[field]
    if 'mapping_status' not in out:
        out['mapping_status'] = out.disease_id.ne('').map({True: 'source_matched_unreviewed', False: 'unmatched'})
    for field in ('mapping_reason', 'mapping_reference'):
        if field not in out:
            out[field] = ''
    if decisions.duplicated(['indication_raw', 'disease_id']).any():
        raise ValueError('Duplicate quarantine decisions')
    for decision in decisions.itertuples():
        mask = out.indication_raw.eq(decision.indication_raw) & out.original_disease_id.eq(decision.disease_id)
        if not decision.reason or not decision.reference:
            raise ValueError('Containment requires a reason and reference')
        out.loc[mask, list(TARGET_FIELDS)] = ''
        out.loc[mask, 'mapping_status'] = 'quarantined'
        out.loc[mask, 'mapping_reason'] = decision.reason
        out.loc[mask, 'mapping_reference'] = decision.reference
    return out


def active_indications(frame):
    out = apply_mapping_policy(frame)
    return out.loc[out.disease_id.ne('') & out.mapping_status.isin(ACTIVE)].copy()


def alias_key(text):
    # Unlike a consonant skeleton, this never erases vowel or compound differences.
    return unicodedata.normalize('NFC', str(text)).strip().casefold()


def validated_aliases(aliases, disease_ids):
    result = {}
    for row in aliases.to_dict('records'):
        key = alias_key(row['indication_raw'])
        if not key or key in result:
            raise ValueError('Empty or duplicate indication alias')
        if row['decision'] not in {'accepted', 'rejected'}:
            raise ValueError('Alias decisions must be explicitly accepted or rejected')
        if not row['reviewer'].strip() or not row['reference'].strip():
            raise ValueError('Alias requires reviewer and source reference')
        if row['decision'] == 'accepted' and (row['relation'] != 'equivalent' or row['disease_id'] not in disease_ids):
            raise ValueError('Accepted alias requires a valid disease and equivalent sense')
        result[key] = row
    return result


def apply_mapping_policy(frame, diseases=None, aliases=None):
    """Spelling suggests candidates; fuzzy and ambiguous exact targets cannot auto-link.

    Unique exact skeleton matches remain explicitly unreviewed. Only a source-linked
    alias decision can promote a candidate; a reviewer name is an audit field, not
    independent verification of that person's qualifications.
    """
    if diseases is None:
        diseases = pd.read_csv(ROOT / 'data/processed/diseases.csv', keep_default_na=False)
    if aliases is None:
        aliases = pd.read_csv(ROOT / 'curation/indication_aliases.csv', keep_default_na=False)
    decisions = validated_aliases(aliases, set(diseases.disease_id))
    index = defaultdict(set)
    for row in diseases.itertuples():
        for key in skeleton_variants(row.term_iast):
            index[key].add(row.disease_id)
    names = diseases.set_index('disease_id')
    out = contain_indications(frame)
    if not out.mapping_status.isin(ACTIVE | BLOCKED).all():
        raise ValueError('Unknown indication mapping status')
    for field in ('match_method', 'match_score'):
        if 'original_' + field not in out:
            out['original_' + field] = out[field] if field in out else ''
    if 'match_score' in out:
        out['match_score'] = out['match_score'].astype(object)
    if 'candidate_disease_ids' not in out:
        out['candidate_disease_ids'] = ''
    for i, row in out.iterrows():
        candidates = index.get(skeleton(row.indication_raw), set())
        fuzzy = row.original_match_method == 'fuzzy_skeleton'
        ambiguous = row.original_match_method == 'exact_skeleton' and len(candidates) > 1
        if fuzzy or ambiguous:
            proposals = {row.original_disease_id} - {''} if fuzzy else candidates
            out.at[i, 'candidate_disease_ids'] = ';'.join(sorted(proposals))
            out.loc[i, list(TARGET_FIELDS)] = ''
            if row.mapping_status != 'quarantined':
                out.at[i, 'mapping_status'] = 'candidate_review_pending'
                out.at[i, 'mapping_reason'] = 'fuzzy spelling is not semantic equivalence' if fuzzy else 'multiple disorders share normalized spelling'
                out.at[i, 'mapping_reference'] = 'indication policy v1; source targets retained for review'
        alias = decisions.get(alias_key(row.indication_raw))
        if row.mapping_status == 'alias_reviewed' and (not alias or alias['decision'] != 'accepted'):
            raise ValueError('Reviewed indication state has no accepted alias decision')
        if alias:
            if alias['decision'] == 'accepted':
                did = alias['disease_id']
                out.loc[i, list(TARGET_FIELDS)] = [did, names.loc[did, 'term_iast'], names.loc[did, 'name_en']]
                out.at[i, 'mapping_status'] = 'alias_reviewed'
                out.at[i, 'match_method'] = 'reviewed_alias'
                out.at[i, 'match_score'] = ''
            else:
                out.loc[i, list(TARGET_FIELDS)] = ''
                out.at[i, 'mapping_status'] = 'quarantined'
            out.at[i, 'mapping_reason'] = f"alias {alias['decision']}; reviewer {alias['reviewer']}"
            out.at[i, 'mapping_reference'] = alias['reference']
    return out


def supported_evidence(evidence, indications):
    """A literature result cannot authorize an unsupported indication mapping."""
    pairs = active_indications(indications)[['herb_id', 'disease_id']].drop_duplicates()
    return evidence.merge(pairs, on=['herb_id', 'disease_id'], how='inner', validate='many_to_one')
