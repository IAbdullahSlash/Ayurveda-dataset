#!/usr/bin/env python3
"""Build reproducible review queues; never marks machine output as expert-approved."""
import json, hashlib
from pathlib import Path
import pandas as pd
from lib.review import write_review_csv
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
                    field=col.removesuffix('_qe_flags')
                    row=df.loc[index].to_dict()
                    key=next((k for k in ['disease_id','term_uid','symptom_id','herb_id','form_id','dx_id','group_id'] if k in row),None)
                    source_field=field[:-3] if field.endswith('_en_hi') else field.removesuffix('_hi')+'_en'
                    translations.append(dict(table=path.stem, record_id=str(row[key]) if key else '', row=index,
                        field=field, source_text=row.get(source_field,''), translated_text=row.get(field,''),
                        row_sha256=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest(),
                        flags=row[col], priority=0 if 'repetition' in row[col] else 1,
                        verdict='',corrected_value='',reviewer='',reference=''))
    pd.DataFrame(missing).to_csv(out / 'missingness.csv',index=False)
    pd.DataFrame(inventory).to_csv(out / 'text_inventory.csv',index=False)
    write_review_csv(pd.DataFrame(translations).sort_values(['priority','table','record_id']),out / 'translation_queue.csv')
    cases = pd.read_csv(ROOT / 'data/processed/case_reports.csv',keep_default_na=False)
    case_manifest=cases[['case_id','pmcid','doi','case_kind','presentation_source','article_licence']].assign(
        split='unassigned', independent_case_unit='', adjudicated_label='', reviewer='', verdict=''
    )
    write_review_csv(case_manifest,out / 'case_annotation_manifest.csv')
    (out / 'status.json').write_text(json.dumps(dict(
        independently_adjudicated=False, external_test_set=False,
        note='Current published cases are a review pool, not an independent external test set.'),indent=2)+'\n')
    print(f'Wrote review inventories to {out}')
if __name__ == '__main__':
    main()
