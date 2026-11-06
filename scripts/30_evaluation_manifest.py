#!/usr/bin/env python3
"""Prepare grouped internal evaluation artifacts or score externally adjudicated pairs."""
import argparse
import json
from pathlib import Path
import pandas as pd
from lib.evaluation import grouped_partition, connected_record_groups, paired_cluster_interval, validate_external_cases
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--paired-results',type=Path)
    ap.add_argument('--external-cases',type=Path)
    args=ap.parse_args()
    out=ROOT/'reports/revision_audit';out.mkdir(exist_ok=True)
    if args.external_cases:
        print(json.dumps(validate_external_cases(pd.read_csv(args.external_cases,keep_default_na=False),
            pd.read_csv(ROOT/'data/processed/case_reports.csv',keep_default_na=False)),indent=2))
        return
    if args.paired_results:
        print(json.dumps(paired_cluster_interval(pd.read_csv(args.paired_results,keep_default_na=False)),indent=2))
        return
    cases=pd.read_csv(ROOT/'data/processed/case_reports.csv',keep_default_na=False)
    # Publication group is explicit: no claim of independent patients within a report.
    cases['independence_group']=cases.pmcid.where(cases.pmcid.ne(''),cases.doi).where(
        lambda s:s.ne(''),cases.case_id)
    cases=grouped_partition(cases,'case_id','independence_group')
    cases[['case_id','independence_group','split','case_kind','year']].to_csv(out/'internal_case_splits.csv',index=False)
    qa=pd.read_csv(ROOT/'data/processed/qa_pairs.csv',keep_default_na=False)
    qa['independence_group']=connected_record_groups(qa)
    qa=grouped_partition(qa,'qa_id','independence_group')
    qa[['qa_id','record_ids','language','independence_group','split']].to_csv(out/'qa_splits.csv',index=False)
    diseases=pd.read_csv(ROOT/'data/processed/diseases.csv',keep_default_na=False)
    indications=pd.read_csv(ROOT/'data/processed/herb_indication.csv',keep_default_na=False)
    direct=set(indications.disease_id)-{''}
    diseases['direct_herb_link']=diseases.disease_id.isin(direct)
    diseases['has_definition']=diseases.definition_en.ne('')
    coverage=diseases.groupby(['system_code','system_name_en']).agg(
        disorders=('disease_id','size'),with_definition=('has_definition','sum'),
        with_direct_herb_link=('direct_herb_link','sum')).reset_index()
    coverage.to_csv(out/'coverage_by_system.csv',index=False)
    status={'seed':42,'case_split_scope':'internal existing published reports; not an external test set',
        'case_split_counts':cases.split.value_counts().to_dict(),
        'qa_split_counts':qa.split.value_counts().to_dict(),
        'qa_largest_connected_group':int(qa.independence_group.value_counts().max()),
        'qa_grouping':'all shared record IDs, including English/Hindi versions',
        'external_validation':'requires newly sourced independent cases and adjudicated labels',
        'paired_intervals':'not computed: paired per-case baseline/model results not supplied'}
    (out/'evaluation_status.json').write_text(json.dumps(status,indent=2)+'\n')
    print(json.dumps(status,indent=2))
if __name__=='__main__':
    main()
