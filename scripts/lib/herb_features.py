"""Train-fold vocabulary selection for multilabel herb properties."""
from collections import Counter
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

FIELDS={'rasa':'rasa','guna':'guna','vipaka':'vipaka','virya':'virya','karma':'karma_actions',
        'parts':'parts_used','family':'family','dosha_pacify':'dosha_pacify','dosha_aggravate':'dosha_aggravate'}

class HerbFeatures(BaseEstimator,TransformerMixin):
    def __init__(self,use=('rasa','guna','vipaka','virya'),min_count=6):
        self.use=use
        self.min_count=min_count
    def fit(self,X,y=None):
        self.features_=[]
        for kind in self.use:
            field=FIELDS[kind]
            counts=Counter(token for value in X[field] for token in str(value).split('; ') if token)
            excluded={'Vatahara','Pittahara','Kaphahara'} if kind=='karma' else set()
            self.features_.extend((field,token) for token,count in sorted(counts.items())
                                  if count>=self.min_count and token not in excluded)
        if not self.features_:
            raise ValueError('No herb features meet training-fold frequency threshold')
        return self
    def transform(self,X):
        return np.column_stack([X[field].map(lambda value:float(token in str(value).split('; '))).to_numpy()
                                for field,token in self.features_])
