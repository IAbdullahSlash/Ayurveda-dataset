#!/usr/bin/env python3
"""Prioritize actual decoding loops; retain original flags and avoid approving translations."""
from pathlib import Path
import json
import pandas as pd
from lib.translation_qe import has_decoding_loop
ROOT=Path(__file__).resolve().parents[1]
def main():
    rows=[]
    for path in sorted((ROOT/'data/processed').glob('*.csv')):
        df=pd.read_csv(path,keep_default_na=False)
        for flag in [c for c in df if c.endswith('_qe_flags')]:
            field=flag.removesuffix('_qe_flags')
            if field not in df:continue
            for index in df.index[df[flag].str.contains('repetition',regex=False)]:
                row=df.loc[index];loop=has_decoding_loop(str(row[field]))
                rows.append({'table':path.stem,'row':index,'field':field,'original_flags':row[flag],
                    'consecutive_decoding_loop':loop,'priority':'high' if loop else 'needs_language_review',
                    'approved':False})
    out=ROOT/'reports/revision_audit'
    pd.DataFrame(rows).to_csv(out/'translation_repetition_reassessment.csv',index=False)
    summary={'flagged_fields_including_derived_copies':len(rows),'consecutive_loops':sum(r['consecutive_decoding_loop'] for r in rows),
        'flags_cleared':0,'meaning_validated':False,'note':'Distributed repetition may be legitimate or erroneous; no automatic approval'}
    (out/'translation_repetition_reassessment.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
if __name__=='__main__':main()
