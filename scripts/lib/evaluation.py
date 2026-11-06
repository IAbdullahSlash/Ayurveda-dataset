"""Grouped partitions and paired uncertainty, without treating reports as patients."""
import hashlib
import numpy as np
import pandas as pd


def grouped_partition(frame, id_column, group_column, seed=42):
    if frame[id_column].duplicated().any() or frame[id_column].eq('').any():
        raise ValueError('Record IDs must be nonempty and unique')
    if frame[group_column].eq('').any():
        raise ValueError('Every record needs an independence group')
    groups=sorted(frame[group_column].unique())
    rng=np.random.default_rng(seed)
    rng.shuffle(groups)
    n=len(groups)
    n_test=max(1,int(round(n*0.2))) if n>=3 else 0
    n_val=max(1,int(round(n*0.1))) if n>=3 else 0
    partition={g:('test' if i<n_test else 'validation' if i<n_test+n_val else 'train') for i,g in enumerate(groups)}
    result=frame.copy()
    result['split']=result[group_column].map(partition)
    return result


def paired_cluster_interval(frame, k=10, seed=42, repetitions=5000):
    required=['case_id','independence_group','model_rank','baseline_rank']
    if not set(required)<=set(frame):
        raise ValueError('Required columns: '+', '.join(required))
    if frame.case_id.duplicated().any() or frame.case_id.eq('').any():
        raise ValueError('Each case must have exactly one paired result')
    if frame.independence_group.isna().any() or frame.independence_group.eq('').any():
        raise ValueError('Missing independence groups')
    ranks=frame[['model_rank','baseline_rank']].apply(pd.to_numeric,errors='raise')
    if ranks.isna().any().any() or (ranks<=0).any().any():
        raise ValueError('Ranks must be positive; use infinity for an unretrieved gold record')
    difference=(ranks.model_rank.le(k).astype(float)-ranks.baseline_rank.le(k).astype(float))
    sums=difference.groupby(frame.independence_group).sum().to_numpy()
    sizes=difference.groupby(frame.independence_group).size().to_numpy()
    if len(sums)<2:
        raise ValueError('At least two independent groups required')
    rng=np.random.default_rng(seed)
    samples=rng.integers(0,len(sums),size=(repetitions,len(sums)))
    draws=sums[samples].sum(1)/sizes[samples].sum(1)
    lower,upper=np.quantile(draws,[0.025,0.975])
    return {'metric':f'hit@{k}', 'paired_difference':float(difference.mean()),
            'percentile_95_interval':[float(lower),float(upper)], 'cases':len(frame),
            'independent_groups':len(sums),'bootstrap_repetitions':repetitions,'seed':seed}


def connected_record_groups(frame, ids_column='record_ids'):
    parent={}
    def find(x):
        parent.setdefault(x,x)
        if parent[x]!=x:
            parent[x]=find(parent[x])
        return parent[x]
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:
            parent[max(a,b)]=min(a,b)
    keys=[]
    for row in frame.itertuples():
        refs=[x for x in getattr(row,ids_column).split(';') if x]
        if not refs:
            raise ValueError('QA record without source record IDs')
        for ref in refs:
            union(refs[0],ref)
        keys.append(refs[0])
    return [find(key) for key in keys]
