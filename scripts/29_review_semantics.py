#!/usr/bin/env python3
"""Compare revised extraction with released edges and prepare a reproducible review sample."""
import importlib
import json
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]

def main():
    build = importlib.import_module('04_build_kb')
    diseases = pd.read_csv(ROOT/'data/processed/diseases.csv',keep_default_na=False)
    edges = pd.read_csv(ROOT/'data/processed/disease_symptom.csv',keep_default_na=False)
    out = ROOT/'reports/revision_audit'
    out.mkdir(exist_ok=True)
    changes=[]
    for row in diseases.itertuples():
        old = list(edges.loc[edges.disease_id==row.disease_id,'mention_en'])
        new = [en for _,en in build.parse_symptoms(row.long_definition)]
        if set(old) != set(new):
            changes.append(dict(disease_id=row.disease_id, term_iast=row.term_iast,
                source_definition=row.long_definition, released_phrases=json.dumps(old,ensure_ascii=False),
                candidate_phrases=json.dumps(new,ensure_ascii=False),
                review_status='pending', reviewer_1='', reviewer_2='', adjudicated_phrases='',reference=''))
    pd.DataFrame(changes).to_csv(out/'symptom_extraction_changes.csv',index=False)
    # Stratify existing edges by extraction method, retain the source context.
    sampled=pd.concat([group.sample(min(50,len(group)),random_state=42)
                       for _, group in edges.groupby('link_method')],ignore_index=True)
    sampled=sampled.merge(diseases[['disease_id','long_definition']],on='disease_id',validate='many_to_one')
    sampled['verdict']='';sampled['reviewer']='';sampled['error_category']=''
    sampled.to_csv(out/'symptom_edge_review_sample.csv',index=False)
    (out/'semantic_review_status.json').write_text(json.dumps({
        'changed_disorders':len(changes),'sampled_edges':len(sampled),'sampling_seed':42,
        'precision':None,'recall':None,'reason':'No independently adjudicated gold annotations supplied',
        'processed_tables_rebuilt':False},indent=2)+'\n')
    print(f'{len(changes)} candidate disorder changes; {len(sampled)} stratified review edges')
if __name__=='__main__':
    main()
