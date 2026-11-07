#!/usr/bin/env python3
"""Collect citation leads for missing herb properties, without inferring property values."""
import argparse,hashlib,json,time
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
import requests
ROOT=Path(__file__).resolve().parents[1]
ENDPOINT='https://www.ebi.ac.uk/europepmc/webservices/rest/search'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=0);args=ap.parse_args()
    herbs=pd.read_csv(ROOT/'data/processed/herbs.csv',keep_default_na=False)
    herbs=herbs[herbs.rasa.eq('')]
    if args.limit:herbs=herbs.head(args.limit)
    out=ROOT/'reports/herb_property_research';out.mkdir(exist_ok=True)
    path=out/'queries.jsonl';cache={}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            row=json.loads(line);cache[row['herb_id']]=row
    session=requests.Session();last=0
    with path.open('a',encoding='utf-8') as stream:
        for number,herb in enumerate(herbs.itertuples(),1):
            query=f'TITLE_ABS:"{herb.accepted_name}" AND (Ayurveda OR Ayurvedic) AND (rasa OR virya OR vipaka OR dravyaguna)'
            if herb.herb_id in cache and cache[herb.herb_id]['query']==query:continue
            time.sleep(max(0,1-(time.monotonic()-last)));last=time.monotonic()
            response=session.get(ENDPOINT,params={'query':query,'format':'json','pageSize':20,'resultType':'lite'},timeout=60)
            response.raise_for_status();body=response.json()
            citations=[{'source':r.get('source',''),'id':r.get('id',''),'pmcid':r.get('pmcid',''),
                'doi':r.get('doi',''),'title':r.get('title',''),'year':r.get('pubYear','')}
                for r in body.get('resultList',{}).get('result',[])]
            row={'herb_id':herb.herb_id,'accepted_name':herb.accepted_name,'query':query,'endpoint':ENDPOINT,
                'retrieved_utc':datetime.now(timezone.utc).isoformat(),'hit_count':body.get('hitCount'),
                'citations':citations,'property_values_inferred':False,'review_status':'citation_leads_only'}
            cache[herb.herb_id]=row;stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
            print(f'{number}/{len(herbs)} {herb.herb_id}: {row["hit_count"]} citation leads',flush=True)
    selected=[cache[r.herb_id] for r in herbs.itertuples()]
    rows=[{key:value for key,value in row.items() if key!='citations'} for row in selected]
    pd.DataFrame(rows).to_csv(out/'coverage.csv',index=False)
    status={'herbs_queried':len(selected),'herbs_with_citation_leads':sum(bool(r['hit_count']) for r in selected),
        'canonical_properties_filled':0,'note':'Exact botanical-name keyword search; zero hits do not prove absence of evidence'}
    (out/'summary.json').write_text(json.dumps(status,indent=2)+'\n', encoding="utf-8");print(json.dumps(status))
if __name__=='__main__':main()
