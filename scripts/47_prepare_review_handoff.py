#!/usr/bin/env python3
"""Prepare source-visible review batches; never supplies reviewer verdicts."""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd
from lib.review import write_review_csv
from lib.provenance import identity

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'data/processed'
OUT = ROOT / 'reports/review_handoff'


def read(name):
    return pd.read_csv(P / f'{name}.csv', keep_default_na=False)


def annotation_columns(frame):
    return frame.assign(verdict='', corrected_value='', reviewer='', reference='', comment='')


def main():
    OUT.mkdir(exist_ok=True)
    herbs, cases = read('herbs'), read('case_reports')
    ingredients, forms = read('formulation_ingredients'), read('formulations')
    form_refs = defaultdict(set)
    for row in ingredients.itertuples():
        if row.herb_id:
            form_refs[row.herb_id].add(row.form_id)
    case_refs = defaultdict(set)
    adverse_refs = defaultdict(set)
    for row in cases.itertuples():
        for herb in row.herb_ids.split(';'):
            if herb.strip():
                case_refs[herb.strip()].add(row.case_id)
                if row.case_kind == 'adverse_event':
                    adverse_refs[herb.strip()].add(row.case_id)
    safety = herbs[['herb_id', 'accepted_name', 'name_sa_iast', 'parts_used', 'safety_class',
                    'safety_hazard_en', 'safety_assessment_status', 'source_ids']].copy()
    safety['formulation_ids'] = safety.herb_id.map(lambda h: ';'.join(sorted(form_refs[h])))
    safety['case_report_ids'] = safety.herb_id.map(lambda h: ';'.join(sorted(case_refs[h])))
    safety['adverse_report_mentions'] = safety.herb_id.map(lambda h: len(adverse_refs[h]))
    safety['priority'] = [0 if flag or adverse_refs[h] else 1 if form_refs[h] else 2 if case_refs[h] else 3
                          for h, flag in zip(safety.herb_id, safety.safety_class)]
    safety['interpretation'] = 'Review priority only: article mentions do not establish herb-specific causation; unassessed is not safe.'
    write_review_csv(annotation_columns(safety.sort_values(['priority', 'herb_id'])), OUT / 'safety_review_batch.csv')
    form_batch = forms[['form_id', 'name_sa_iast', 'classical_reference', 'ingredients_sa_iast',
                        'contains_metal_or_toxic', 'safety_note']].copy()
    form_batch['priority'] = (~form_batch.contains_metal_or_toxic.str.startswith('yes')).astype(int)
    write_review_csv(annotation_columns(form_batch.sort_values(['priority', 'form_id'])), OUT / 'formulation_safety_batch.csv')

    # Two percent per table/field, reproducibly sampled; this is a review batch,
    # not a claim that its size establishes any particular error bound.
    samples, strata = [], []
    for path in sorted(P.glob('*.csv')):
        frame = pd.read_csv(path, keep_default_na=False)
        for flags in [c for c in frame if c.endswith('_hi_qe_flags')]:
            field = flags.removesuffix('_qe_flags')
            if field not in frame:
                continue
            eligible = frame[frame[field].ne('') & frame[flags].eq('')]
            n = min(len(eligible), max(1, math.ceil(len(eligible) * .02))) if len(eligible) else 0
            sample = eligible.sample(n=n, random_state=42)
            strata.append(dict(table=path.stem, field=field, unflagged_population=len(eligible), sampled=n))
            for row in sample.to_dict('records'):
                key = next((k for k in ['disease_id', 'term_uid', 'symptom_id', 'herb_id', 'form_id', 'dx_id', 'group_id', 'therapy_id', 'pharmaceutic_id', 'lifestyle_id'] if k in row), None)
                source_field = field[:-3] if field.endswith('_en_hi') else field.removesuffix('_hi') + '_en'
                samples.append(dict(table=path.stem, record_id=row.get(key, '') if key else '',
                    field=field, source_text=row.get(source_field, ''), translated_text=row[field],
                    source_row_ref=identity(path.stem, row), sampling_seed=42))
    write_review_csv(annotation_columns(pd.DataFrame(samples)), OUT / 'unflagged_hindi_sample.csv')
    pd.DataFrame(strata).to_csv(OUT / 'unflagged_hindi_sampling_frame.csv', index=False)

    indications = read('herb_indication')
    unmatched = indications[indications.mapping_status.eq('unmatched')].groupby('indication_raw', sort=True).agg(
        affected_rows=('herb_id', 'size'), herb_ids=('herb_id', lambda s: ';'.join(sorted(set(s))))).reset_index()
    write_review_csv(annotation_columns(unmatched.sort_values(['affected_rows', 'indication_raw'], ascending=[False, True])), OUT / 'unmatched_indication_terms.csv')
    gaps = []
    for table, field, note in [
        ('formulation_ingredients', 'herb_id', 'Review herbal ingredient identity; non-herbal materials require a different entity class.'),
        ('formulation_indications', 'disease_id', 'Review sense and disorder scope; no forced match.'),
        ('herb_group_members', 'herb_id', 'Review botanical identity and source spelling.'),
        ('herb_image_datasets', 'herb_id', 'May be an out-of-inventory species; blank alone is not an error.')]:
        frame = read(table)
        for row in frame[frame[field].eq('')].to_dict('records'):
            gaps.append(dict(table=table, missing_field=field, source_row_ref=identity(table, row),
                source_row=json.dumps(row, ensure_ascii=False, sort_keys=True), interpretation=note))
    write_review_csv(annotation_columns(pd.DataFrame(gaps)), OUT / 'link_gap_triage.csv')

    suggestions = read('dosha_suggestions')
    diseases = read('diseases')
    own_term = diseases[diseases.dosha_source.eq('term')]
    confidence = pd.to_numeric(suggestions.confidence)
    distribution = dict(suggestions=len(suggestions), predicted_classes=suggestions.suggested_dosha.value_counts().to_dict(),
        own_term_labelled_records=len(own_term), own_term_classes=own_term.dosha_label.value_counts().to_dict(),
        median_confidence=float(confidence.median()),
        confidence_quartiles={str(q): float(confidence.quantile(q)) for q in [.25, .75]},
        expert_target_labels_available=False, calibrated_threshold_selected=False,
        note='Descriptive distribution shift, not an error rate. Class-specific calibration needs independent target labels; no class quotas imposed.')
    (OUT / 'dosha_distribution_audit.json').write_text(json.dumps(distribution, indent=2) + '\n')
    ledger = pd.read_csv(ROOT / 'curation/source_rights_review.csv', keep_default_na=False)
    inventory = ledger[['source_id', 'title', 'licence', 'review_status', 'approved_scope']].copy()
    inventory['required_decision'] = 'Exact terms/permission; redistribution and transformations; attribution; allowed scope; model/article conditions where applicable.'
    inventory['external_contact_sent'] = False
    write_review_csv(annotation_columns(inventory), OUT / 'rights_review_batch.csv')
    summary = dict(safety_herbs=len(safety), formulation_records=len(form_batch),
        unflagged_hindi_fields_sampled=len(samples), seed=42,
        unmatched_indication_groups=len(unmatched), link_gaps=len(gaps), rights_sources=len(inventory),
        expert_verdicts_created=0, clinical_labels_created=0, permissions_granted=0, external_messages_sent=0)
    (OUT / 'status.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
