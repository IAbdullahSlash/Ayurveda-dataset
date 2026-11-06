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
