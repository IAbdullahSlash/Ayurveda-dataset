#!/usr/bin/env python3
"""Repair the verified coordination-fragment example without deleting referenced IDs."""
import json
from pathlib import Path
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I omits the script folder
from lib.stable_ids import allocate
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=ROOT/'data/processed'
    d=pd.read_csv(p/'diseases.csv',keep_default_na=False).set_index('disease_id')
    source=d.loc['AYD-01110','long_definition']
    if 'frequent and excessive urination' not in source:raise ValueError('Source definition changed')
    symptoms=pd.read_csv(p/'symptoms.csv',keep_default_na=False)
    edges=pd.read_csv(p/'disease_symptom.csv',keep_default_na=False)
    phrase='frequent and excessive urination'
    sid=allocate('symptoms',[phrase])[phrase]
    if sid not in set(symptoms.symptom_id):
        row={key:'' for key in symptoms.columns}
        row.update(symptom_id=sid,source_id='S1',gloss_en=phrase,licence=d.loc['AYD-01110','licence'],
            data_origin='source-derived coordination repair; not clinically adjudicated',gloss_hi='बार-बार और अत्यधिक पेशाब आना',
            gloss_hi_method='ai_postedit_unreviewed',gloss_hi_qe_flags='expert_review_pending')
        symptoms=pd.concat([symptoms,pd.DataFrame([row])],ignore_index=True)
    mask=edges.disease_id.eq('AYD-01110')
    allowed={'frequent','excessive urination',phrase}
    if not set(edges.loc[mask,'mention_en'])<=allowed:raise ValueError('Unexpected profile; manual review needed')
    removed=edges.loc[mask].to_dict('records')
    edges=edges.loc[~mask].copy()
    row={key:'' for key in edges.columns}
    row.update(disease_id='AYD-01110',symptom_id=sid,mention_rank=1,mention_en=phrase,
               link_method='source_coordination_preserved_unreviewed',source_id='S1')
    edges=pd.concat([edges,pd.DataFrame([row])],ignore_index=True)
    symptoms['n_diseases']=symptoms.symptom_id.map(edges.groupby('symptom_id').disease_id.nunique()).fillna(0).astype(int)
    # Retired fragment nodes remain for references in other derived layers.
    symptoms.to_csv(p/'symptoms.csv',index=False);edges.to_csv(p/'disease_symptom.csv',index=False)
    report=ROOT/'reports/revision_audit/prameha_scope_repair.json'
    if not report.exists():
        report.write_text(json.dumps({'source_definition':source,'previous_edges':removed,'replacement':row,
            'clinical_adjudication':False,'retired_ids_preserved':True},ensure_ascii=False,indent=2)+'\n', encoding="utf-8")
    print(sid)
if __name__=='__main__':main()
