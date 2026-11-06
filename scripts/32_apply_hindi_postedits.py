#!/usr/bin/env python3
"""Apply source-hash-checked AI language post-edits, preserving their unreviewed state."""
import hashlib
import json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]

def apply(root=ROOT):
    edits=pd.read_csv(root/'curation/hindi_definition_postedits.csv',keep_default_na=False)
    if edits.term_uid.duplicated().any():raise ValueError('Duplicate correction IDs')
    tables={name:pd.read_csv(root/f'data/processed/{name}.csv',keep_default_na=False) for name in
            ['terminology','therapies','pharmaceutics','diet_lifestyle','diseases']}
    terms=tables['terminology'].set_index('term_uid')
    # Validate all edits before touching any file.
    for row in edits.itertuples():
        if hashlib.sha256(terms.loc[row.term_uid,'definition_en'].encode()).hexdigest()!=row.source_sha256:
            raise ValueError('Source changed: '+row.term_uid)
        if row.status!='ai_postedit_unreviewed' or not row.replacement_hi.strip():raise ValueError('Invalid edit')
    counts={}
    for name,df in tables.items():
        count=0
        for row in edits.itertuples():
            mask=df.term_uid.eq(row.term_uid) if name!='diseases' else (
                df.who_term_id.eq(row.term_uid.removeprefix('WHO:'))&df.definition_source.str.startswith('WHO'))
            mask &= df.definition_en.eq(row.source_en)
            changed=mask & df.definition_hi.ne(row.replacement_hi)
            count+=int(changed.sum())
            df.loc[mask,'definition_hi']=row.replacement_hi
            df.loc[mask,'definition_hi_method']='ai_postedit_unreviewed: source-checked language correction'
            df.loc[mask,'definition_hi_qe_flags']='expert_review_pending'
        counts[name]=count
    for name,df in tables.items():
        df.to_csv(root/f'data/processed/{name}.csv',index=False)
    return counts
if __name__=='__main__':print(json.dumps(apply()))
