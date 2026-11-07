#!/usr/bin/env python3
"""Refresh mapping-dependent metadata offline, preserving withdrawn literature rows.

This reuses original literature searches; it does not acquire new studies or claim
fresh query counts. A newly approved pair requires stage 15 before this refresh.
"""
import hashlib
import importlib
import json
from pathlib import Path
import pandas as pd
from lib.indication_policy import active_indications, supported_evidence

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'data/processed'


def main():
    links = pd.read_csv(P / 'herb_indication.csv', keep_default_na=False)
    evidence_path = P / 'herb_indication_evidence.csv'
    previous = pd.read_csv(evidence_path, keep_default_na=False)
    current = supported_evidence(previous, links)
    active = active_indications(links)
    wanted = set(zip(active.herb_id, active.disease_id))
    present = set(zip(current.herb_id, current.disease_id))
    if wanted - present:
        raise ValueError('Newly supported pairs have no literature record; run stage 15 first')
    keep = pd.MultiIndex.from_frame(previous[['herb_id', 'disease_id']]).isin(pd.MultiIndex.from_frame(current[['herb_id', 'disease_id']]))
    withdrawn = previous.loc[~keep].copy()
    out = ROOT / 'reports/indication_review'
    out.mkdir(exist_ok=True)
    history_path = out / 'withdrawn_evidence.csv'
    if history_path.exists():
        history = pd.read_csv(history_path, keep_default_na=False)
        withdrawn = pd.concat([history, withdrawn], ignore_index=True).drop_duplicates(['herb_id', 'disease_id', 'query'])
    withdrawn.to_csv(history_path, index=False)
    current.to_csv(evidence_path, index=False)
    current.to_parquet(evidence_path.with_suffix('.parquet'), index=False)

    # Existing observed case links remain observations; only their KB-overlap flag changes.
    cases = pd.read_csv(P / 'case_report_links.csv', keep_default_na=False)
    forms = pd.read_csv(P / 'formulation_indications.csv', keep_default_na=False)
    herb_pairs = set(zip(active.disease_id, active.herb_id))
    form_pairs = set(zip(forms.disease_id, forms.form_id))
    _, family, _, _ = importlib.import_module('14_case_reports').kb_matcher()
    old_flags = cases.in_kb_for_disorder_family.astype(str).str.lower().eq('true')
    flags = [any((d, row.entity_id) in (herb_pairs if row.entity_type == 'herb' else form_pairs)
                 for d in family(row.disease_id)) for row in cases.itertuples()]
    cases['in_kb_for_disorder_family'] = flags
    cases.to_csv(P / 'case_report_links.csv', index=False)
    cases.to_parquet(P / 'case_report_links.parquet', index=False)
    report = dict(active_indication_rows=len(active), active_evidence_pairs=len(current),
        withdrawn_historical_pairs=len(withdrawn), case_flags_changed=int((old_flags != pd.Series(flags)).sum()),
        source_indication_sha256=hashlib.sha256((P / 'herb_indication.csv').read_bytes()).hexdigest(),
        literature_counts='retained from original queries; no network queries performed',
        historical_evidence='withdrawn_evidence.csv is audit history, not accepted indication support',
        external_clinical_validation=False)
    (out / 'derivative_refresh.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
