#!/usr/bin/env python3
"""Collect publication metadata for annotation; never manufacture external gold labels."""
import argparse,hashlib,json
from pathlib import Path
import pandas as pd
import requests
ROOT=Path(__file__).resolve().parents[1]
ENDPOINT='https://www.ebi.ac.uk/europepmc/webservices/rest/search'

def normalize(value):
    return str(value or '').strip().casefold().removeprefix('https://doi.org/').removeprefix('doi:').strip()

def candidates(results,internal):
    known={field:{normalize(v) for v in internal[field] if str(v).strip()} for field in ['pmcid','pmid','doi']}
    rows=[];seen=set()
    for result in results:
        ids={field:str(result.get(field,'') or '') for field in known}
        if not any(ids.values()):continue
        if any(normalize(value) in known[field] for field,value in ids.items() if value):continue
        key=ids['pmcid'] or ids['pmid'] or ids['doi']
        if key in seen:continue
        seen.add(key)
        rows.append({'candidate_id':key,**ids,'title':result.get('title',''),
            'publication_year':result.get('pubYear',''),'first_publication_date':result.get('firstPublicationDate',''),
            'status':'unannotated_candidate; not an external test result',
            'adjudicated_label':'','reviewer_1':'','reviewer_2':'','adjudication_reference':''})
    return rows

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--query',default='Ayurveda AND ("case report" OR "case series") AND FIRST_PDATE:[2026-11-05 TO *]')
    parser.add_argument('--pages',type=int,default=5)
    args=parser.parse_args()
    if args.pages<1:raise ValueError('pages must be positive')
    internal=pd.read_csv(ROOT/'data/processed/case_reports.csv',keep_default_na=False)
    all_results=[];cursor='*'
    for _ in range(args.pages):
        response=requests.get(ENDPOINT,params={'query':args.query,'format':'json','pageSize':100,
            'cursorMark':cursor,'resultType':'lite'},timeout=60)
        response.raise_for_status()
        body=response.json();results=body.get('resultList',{}).get('result',[])
        all_results.extend(results)
        next_cursor=body.get('nextCursorMark')
        if not results or not next_cursor or next_cursor==cursor:break
        cursor=next_cursor
    rows=candidates(all_results,internal)
    out=ROOT/'reports/external_candidates';out.mkdir(exist_ok=True)
    # Write metadata only after successful collection; a network failure is not a zero-case result.
    payload=json.dumps(all_results,ensure_ascii=False,sort_keys=True)
    digest=hashlib.sha256(payload.encode()).hexdigest()
    folder=out/digest;folder.mkdir(exist_ok=True)
    if not (folder/'candidates.csv').exists():
        pd.DataFrame(rows,columns=['candidate_id','pmcid','pmid','doi','title','publication_year','first_publication_date',
            'status','adjudicated_label','reviewer_1','reviewer_2','adjudication_reference']).to_csv(folder/'candidates.csv',index=False)
    (folder/'collection_manifest.json').write_text(json.dumps({'endpoint':ENDPOINT,'query':args.query,
        'metadata_response_sha256':digest,'retrieved_records':len(all_results),'candidate_records':len(rows),
        'gold_labels_supplied':False,'article_text_downloaded':False,'internal_snapshot_sha256':
        hashlib.sha256((ROOT/'data/processed/case_reports.csv').read_bytes()).hexdigest()},indent=2)+'\n')
    print(folder)
if __name__=='__main__':main()
