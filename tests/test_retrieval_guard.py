import sys
from pathlib import Path
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from lib.retrieval_guard import concept_exclusions, DescriptionGuard
from lib.review import write_review_csv

def test_concept_closure_excludes_cross_table_aliases():
    members=pd.DataFrame({'concept_id':['C1','C1','C2','C2'], 'entity_id':['test','alias','alias','translated']})
    assert concept_exclusions({'test'},members)=={'test','alias','translated'}

def test_description_guard_catches_normalized_duplicates():
    guard=DescriptionGuard(['Pain with fever and swelling of the joints'])
    assert guard.overlaps('PAIN, with fever and swelling of the joints.')
    assert not guard.overlaps('Nausea without fever')

def test_regeneration_preserves_human_review(tmp_path):
    path=tmp_path/'review.csv'
    pd.DataFrame({'verdict':['accepted']}).to_csv(path,index=False)
    with pytest.raises(ValueError,match='annotated'):
        write_review_csv(pd.DataFrame({'verdict':['']}),path)
    assert pd.read_csv(path).verdict.iloc[0]=='accepted'

def test_full_corpus_retrieval_uses_candidate_ids(monkeypatch):
    import importlib
    import numpy as np
    module=importlib.import_module('23_finetune_search')
    query={'docs':['gold'], 'ids':['D1'], 'q_term':['term'], 'q_text':['text']}
    candidates={'docs':['distractor','gold'], 'ids':['D2','D1']}
    monkeypatch.setattr(module,'e5_samples',lambda limit=None:{'diseases':candidates})
    class Encoder:
        def encode(self,texts,prefix):
            return np.array([[0.,1.] if text=='distractor' else [1.,0.] for text in texts])
    scores=module.evaluate(Encoder(),{'diseases':query})
    assert scores['diseases']['hindi_headword']['recall_at_1']==1.0
