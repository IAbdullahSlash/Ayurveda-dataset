import importlib,sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
module=importlib.import_module('35_collect_external_candidates')
def test_collection_excludes_known_publications_and_keeps_labels_empty():
    internal=pd.DataFrame([{'pmcid':'PMC1','pmid':'1','doi':'10.1/old'}])
    result=module.candidates([{'pmcid':'PMC2','doi':'https://doi.org/10.1/old'},
        {'pmcid':'PMC3','title':'New report','authorString':'excluded','abstractText':'excluded'}],internal)
    assert len(result)==1 and result[0]['pmcid']=='PMC3'
    assert result[0]['adjudicated_label']==''
    assert 'abstractText' not in result[0] and 'authorString' not in result[0]
