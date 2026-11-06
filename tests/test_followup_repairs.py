from pathlib import Path
import importlib,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))

def test_hindi_postedits_are_idempotent():
    m=importlib.import_module('32_apply_hindi_postedits')
    assert sum(m.apply().values())==0
    terms=pd.read_csv(ROOT/'data/processed/terminology.csv',keep_default_na=False).set_index('term_uid')
    assert terms.loc['SAT:SAT-G.58','definition_hi']=='लंबे हत्थे वाली लोहे की कलछी।'
    assert terms.loc['SAT:SAT-G.58','definition_hi_qe_flags']=='expert_review_pending'

def test_prameha_retains_coordination_and_old_ids():
    edges=pd.read_csv(ROOT/'data/processed/disease_symptom.csv',keep_default_na=False)
    assert edges.loc[edges.disease_id.eq('AYD-01110'),'mention_en'].tolist()==['frequent and excessive urination']
    symptoms=pd.read_csv(ROOT/'data/processed/symptoms.csv',keep_default_na=False)
    assert {'SYM-N00779','SYM-N00780'}<=set(symptoms.symptom_id)
