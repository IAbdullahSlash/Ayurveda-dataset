import importlib
import sys
from pathlib import Path
import numpy as np
import pytest
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.dummy import DummyClassifier
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
export = importlib.import_module("08_validate_export")


class FoldGuard(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        self.seen = set(X[:, 0])
        assert len(self.seen) == 8
        return self
    def transform(self, X):
        ids = set(X[:, 0])
        assert ids == self.seen or ids.isdisjoint(self.seen)
        return np.ones((len(X), 1))

def test_preprocessor_never_fits_heldout_rows():
    from lib.ml_utils import evaluate_cv
    result, *_ = evaluate_cv({'dummy': DummyClassifier()}, np.arange(12).reshape(-1, 1),
                            np.array([0, 1] * 6), n_splits=3, n_repeats=1,
                            preprocessor=FoldGuard())
    assert len(result) == 1

def test_herb_vocabulary_is_learned_on_training_rows_only():
    import pandas as pd
    from lib.herb_features import HerbFeatures
    train=pd.DataFrame({'rasa':['common','common','rare']})
    test=pd.DataFrame({'rasa':['test-only','rare']})
    transformer=HerbFeatures(use=('rasa',),min_count=2).fit(train)
    assert transformer.features_==[('rasa','common')]
    assert transformer.transform(test).tolist()==[[0.0],[0.0]]

class NestedFoldGuard(BaseEstimator, TransformerMixin):
    sizes=[]
    def fit(self,X,y=None):
        self.seen=set(X[:,0]); self.sizes.append(len(self.seen))
        assert len(self.seen) in (8,12)
        return self
    def transform(self,X):
        assert set(X[:,0])==self.seen or set(X[:,0]).isdisjoint(self.seen)
        return np.ones((len(X),1))

def test_tuning_fits_preprocessing_inside_inner_folds():
    from sklearn.model_selection import StratifiedKFold
    tuning=importlib.import_module('20_tuning')
    NestedFoldGuard.sizes=[]
    result=tuning.nested('dummy',np.arange(18).reshape(-1,1),np.array([0,1]*9),
        DummyClassifier(),{'strategy':['prior','most_frequent']},StratifiedKFold(3),
        n_jobs=1,preprocessor=NestedFoldGuard())
    assert result['n_outer_folds']==3
    assert set(NestedFoldGuard.sizes)=={8,12}

def test_embedding_baseline_scale_is_preserved(tmp_path,monkeypatch):
    import pandas as pd
    upgrades=importlib.import_module('26_model_upgrades')
    d=pd.DataFrame({'definition_en':['persistent clinical presentation lasting several days']*40,
        'definition_source':['NAMASTE']*40,'name_en':['record']*40,'system_code':['A']*20+['B']*20,
        'dosha_source':['term']*40,'dosha_label':['vata']*20+['pitta']*20,
        'name_en_hi':['नाम']*40,'definition_hi':['लक्षणों का विस्तृत विवरण']*40})
    monkeypatch.setattr(upgrades,'rd',lambda name:d)
    monkeypatch.setattr(upgrades,'REP',tmp_path)
    seen=[]
    def evaluate(zoo,X,y,**kwargs):
        name=next(iter(zoo));seen.append(name)
        if name=='e5 embeddings + LR':
            assert np.allclose(X,[3.,4.])
        if name=='TF-IDF + e5 + LR':
            assert np.allclose(X[[0,1]],[1.8,2.4])
        return pd.DataFrame([{'accuracy_mean':0.,'macro_f1_mean':0.,'roc_auc_ovr_mean':0.}]),None,None,None
    monkeypatch.setattr(upgrades,'evaluate_cv',evaluate)
    class Encoder:
        def encode(self,texts,prefix):return np.tile([3.,4.],(len(texts),1))
    upgrades.e1_plus(Encoder())
    assert len(seen)==15
