from pathlib import Path
import importlib,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))

def test_hindi_field_corrections_are_applied_and_idempotent():
    """Whole-field Hindi corrections now run in stage 25 with the other curated Hindi corrections."""
    m=importlib.import_module('25_fill_missing')
    rd=lambda n: pd.read_csv(ROOT/f'data/processed/{n}.csv',keep_default_na=False)
    tables={n: rd(n) for n in m.FIELD_TABLES}
    edits=m.load_field_corrections(tables['terminology'])
    assert len(edits)==21
    assert sum(m.field_fix(tables, edits).values())==0
    terms=pd.read_csv(ROOT/'data/processed/terminology.csv',keep_default_na=False).set_index('term_uid')
    assert terms.loc['SAT:SAT-G.58','definition_hi']=='लंबे हत्थे वाली लोहे की कलछी।'
    assert terms.loc['SAT:SAT-G.58','definition_hi_qe_flags']=='expert_review_pending'

def test_field_fix_tolerates_fresh_disease_table():
    """On a from-scratch build, diseases has no definition_source yet when the first correction pass runs."""
    m=importlib.import_module('25_fill_missing')
    rd=lambda n: pd.read_csv(ROOT/f'data/processed/{n}.csv',keep_default_na=False)
    tables={n: rd(n) for n in m.FIELD_TABLES}
    tables['diseases']=tables['diseases'].drop(columns='definition_source')
    edits=m.load_field_corrections(tables['terminology'])
    assert 'diseases' not in m.field_fix(tables, edits)

def test_prameha_retains_coordination_and_old_ids():
    edges=pd.read_csv(ROOT/'data/processed/disease_symptom.csv',keep_default_na=False)
    assert edges.loc[edges.disease_id.eq('AYD-01110'),'mention_en'].tolist()==['frequent and excessive urination']
    symptoms=pd.read_csv(ROOT/'data/processed/symptoms.csv',keep_default_na=False)
    assert {'SYM-N00779','SYM-N00780'}<=set(symptoms.symptom_id)
