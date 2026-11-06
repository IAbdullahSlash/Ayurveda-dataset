#!/usr/bin/env python3
"""Build reproducible review queues; never marks machine output as expert-approved."""
import json
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]

def main():
    out = ROOT / 'reports/revision_audit'
    out.mkdir(exist_ok=True)
    inventory, missing, translations = [], [], []
    for path in sorted((ROOT / 'data/processed').glob('*.csv')):
        df = pd.read_csv(path, keep_default_na=False)
        for col in df:
            missing.append(dict(table=path.stem, field=col, rows=len(df), empty=int(df[col].eq('').sum())))
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                inventory.append(dict(table=path.stem, field=col, nonempty=int(df[col].ne('').sum()),
                                      maximum_length=int(df[col].astype(str).str.len().max()),
                                      rights_review='not_adjudicated'))
            if col.endswith('_qe_flags'):
                for index in df.index[df[col].ne('')]:
                    translations.append(dict(table=path.stem, row=index, field=col.removesuffix('_qe_flags'),
                                             flags=df.at[index,col], verdict='', corrected_value=''))
    pd.DataFrame(missing).to_csv(out / 'missingness.csv',index=False)
    pd.DataFrame(inventory).to_csv(out / 'text_inventory.csv',index=False)
    pd.DataFrame(translations).to_csv(out / 'translation_queue.csv',index=False)
    cases = pd.read_csv(ROOT / 'data/processed/case_reports.csv',keep_default_na=False)
    cases[['case_id','pmcid','doi','case_kind','presentation_source','article_licence']].assign(
        split='unassigned', independent_case_unit='', adjudicated_label='', reviewer='', verdict=''
    ).to_csv(out / 'case_annotation_manifest.csv',index=False)
    (out / 'status.json').write_text(json.dumps(dict(
        independently_adjudicated=False, external_test_set=False,
        note='Current published cases are a review pool, not an independent external test set.'),indent=2)+'\n')
    print(f'Wrote review inventories to {out}')
if __name__ == '__main__':
    main()
