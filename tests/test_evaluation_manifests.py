import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from lib.evaluation import grouped_partition, connected_record_groups, paired_cluster_interval

def test_shared_sources_and_translations_stay_in_one_split():
    qa=pd.DataFrame({'qa_id':['a','a-hi','b','c','d','e'],'record_ids':['D1;H1','D1;H1','D2;H1','D3','D4','D5']})
    qa['group']=connected_record_groups(qa)
    result=grouped_partition(qa,'qa_id','group')
    assert result.iloc[:3].split.nunique()==1
    assert result.groupby('group').split.nunique().eq(1).all()

def test_paired_interval_uses_same_cases():
    frame=pd.DataFrame({'case_id':['a','b','c','d'],'independence_group':['A','A','B','B'],
                       'model_rank':[1,1,2,2],'baseline_rank':[20,20,30,30]})
    result=paired_cluster_interval(frame,repetitions=100)
    assert result['paired_difference']==1
    assert result['percentile_95_interval']==[1,1]
    with pytest.raises(ValueError,match='exactly one'):
        paired_cluster_interval(pd.concat([frame,frame]))

def test_external_case_validation_rejects_reused_publications():
    from lib.evaluation import validate_external_cases
    row={'case_id':'new','pmcid':'PMC-new','doi':'10.1/new','title':'new report','independence_group':'publication-new',
         'adjudicated_label':'AYD-test','reviewer_1':'A','reviewer_2':'B','adjudication_reference':'record-123'}
    internal=pd.DataFrame([{'case_id':'old','pmcid':'PMC-old','doi':'10.1/old','title':'old report'}])
    assert validate_external_cases(pd.DataFrame([row]),internal)['cases']==1
    row['doi']='https://doi.org/10.1/old'
    with pytest.raises(ValueError,match='overlaps internal doi'):
        validate_external_cases(pd.DataFrame([row]),internal)
