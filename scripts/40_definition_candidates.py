#!/usr/bin/env python3
"""Find source-backed alternate headword matches; do not turn matches into clinical definitions."""
from collections import defaultdict
import hashlib,json
from pathlib import Path
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I omits the script folder
from lib.keys import skeleton_variants
ROOT=Path(__file__).resolve().parents[1]
def main():
    terms=pd.read_csv(ROOT/'data/processed/terminology.csv',keep_default_na=False)
    diseases=pd.read_csv(ROOT/'data/processed/diseases.csv',keep_default_na=False)
    index=defaultdict(set);records={}
    for row in terms[terms.definition_en.str.len()>15].itertuples():
        records[row.term_uid]=row
        for key in skeleton_variants(row.term_sa_iast_primary):
            if key:index[key].add(row.term_uid)
    rows=[]
    for disease in diseases[diseases.definition_en.eq('')].itertuples():
        hits=set().union(*(index.get(key,set()) for key in skeleton_variants(disease.term_iast)))
        for uid in sorted(hits):
            term=records[uid]
            rows.append({'disease_id':disease.disease_id,'disease_headword':disease.term_iast,
                'source_record_id':uid,'source_id':term.source_id,'source_headword':term.term_sa_iast_primary,
                'candidate_definition_en':term.definition_en,'source_sha256':hashlib.sha256(term.definition_en.encode()).hexdigest(),
                'licence_as_recorded':term.licence,'match_method':'exact_normalized_headword_candidate',
                'review_status':'unreviewed_semantic_alignment','verdict':'','reviewer':'','reference':''})
    out=ROOT/'reports/revision_audit'
    from lib.review import write_review_csv
    frame=pd.DataFrame(rows,columns=['disease_id','disease_headword','source_record_id','source_id','source_headword',
        'candidate_definition_en','source_sha256','licence_as_recorded','match_method','review_status','verdict','reviewer','reference'])
    write_review_csv(frame,out/'alternative_definition_candidates.csv')
    status={'undefined_disorders':int(diseases.definition_en.eq('').sum()),'candidate_pairs':len(rows),
        'disorders_with_alternative_candidates':frame.disease_id.nunique(),'canonical_definitions_filled':0,
        'note':'Headword matching may conflate senses; clinical alignment review required'}
    (out/'alternative_definition_status.json').write_text(json.dumps(status,indent=2)+'\n', encoding="utf-8");print(json.dumps(status))
if __name__=='__main__':main()
