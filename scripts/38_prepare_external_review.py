#!/usr/bin/env python3
"""Prepare annotation-ready publication groups without inventing case labels."""
import argparse,json
from pathlib import Path
import pandas as pd
from lib.review import write_review_csv

def prepare(path):
    data=pd.read_csv(path,keep_default_na=False)
    data['case_id']='EXT-'+data.candidate_id.astype(str)
    data['independence_group']=data.pmcid.where(data.pmcid.ne(''),data.doi).where(lambda s:s.ne(''),data.pmid)
    if data.independence_group.eq('').any():raise ValueError('Publication identifier missing')
    data['eligibility_verdict']=''
    data['patient_unit_definition']=''
    data['presentation_only_text']=''
    data['case_kind']=''
    output=path.with_name('annotation_template.csv')
    if output.exists() and pd.read_csv(output,keep_default_na=False)['case_kind'].ne('').any():
        raise ValueError('Refusing to overwrite assigned case kinds')
    write_review_csv(data,output)
    return output
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('candidates',type=Path);args=parser.parse_args()
    print(prepare(args.candidates))
