#!/usr/bin/env python3
"""Apply conservative mapping policy and prepare protected review queues offline."""
import json
from pathlib import Path
import pandas as pd
from lib.indication_policy import apply_mapping_policy
from lib.review import write_review_csv
from lib.provenance import identity

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'data/processed/herb_indication.csv'
    source = pd.read_csv(path, keep_default_na=False)
    result = apply_mapping_policy(source)
    out = ROOT / 'reports/indication_review'
    out.mkdir(exist_ok=True)
    groups = []
    for (raw, method), frame in result.groupby(['indication_raw', 'original_match_method'], sort=True):
        if method != 'fuzzy_skeleton' and not frame.candidate_disease_ids.ne('').any():
            continue
        first = frame.iloc[0]
        groups.append(dict(indication_raw=raw, method=method, affected_rows=len(frame),
            original_disease_id=first.original_disease_id, original_disease_name_en=first.original_disease_name_en,
            candidate_disease_ids=first.candidate_disease_ids, containment_reason=first.mapping_reason,
            containment_reference=first.mapping_reference, verdict='', corrected_value='', reviewer='', reference=''))
    queue = pd.DataFrame(groups)
    exact = result[result.original_match_method.eq('exact_skeleton')].sample(n=min(60, int(result.original_match_method.eq('exact_skeleton').sum())), random_state=42).copy()
    exact['source_row_ref'] = [identity('herb_indication', row) for row in exact.to_dict('records')]
    for field in ('verdict', 'corrected_value', 'reviewer', 'reference'):
        exact[field] = ''
    # Protect both review files before publishing canonical changes.
    write_review_csv(queue, out / 'candidate_groups.csv')
    write_review_csv(exact, out / 'exact_match_sample.csv')
    result.to_csv(path, index=False)
    result.to_parquet(path.with_suffix('.parquet'), index=False)
    report = dict(rows=len(result), states=result.mapping_status.value_counts().to_dict(),
        fuzzy_groups=int(queue.method.eq('fuzzy_skeleton').sum()),
        ambiguous_exact_groups=int(queue.method.eq('exact_skeleton').sum()),
        exact_sample=len(exact), seed=42, expert_approval=False,
        note='Conservative abstention reduces active coverage; candidates are not all established errors.')
    (out / 'status.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
