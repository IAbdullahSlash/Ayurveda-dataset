#!/usr/bin/env python3
"""Resume token-budgeted Hindi proposals without overwriting curated or reviewed text."""
import argparse,hashlib,json
from pathlib import Path
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I omits the script folder
from lib.translation_qe import has_decoding_loop
ROOT=Path(__file__).resolve().parents[1]

def split_budget(text,length,budget=180):
    words=text.split();chunks=[];current=[]
    for word in words:
        candidate=' '.join(current+[word])
        if length(candidate)>budget:
            if not current:raise ValueError('Single source token exceeds translation budget')
            chunks.append(' '.join(current));current=[word]
            if length(word)>budget:raise ValueError('Single source token exceeds translation budget')
        else:current.append(word)
    if current:chunks.append(' '.join(current))
    return chunks

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--scope',choices=['loops','all'],default='loops')
    ap.add_argument('--limit',type=int,default=0)
    ap.add_argument('--retry-loops',action='store_true')
    args=ap.parse_args()
    queue=pd.read_csv(ROOT/'reports/revision_audit/translation_queue.csv',keep_default_na=False)
    queue=queue[queue.source_text.ne('') & queue['flags'].str.contains('repetition',regex=False)]
    if args.scope=='loops':queue=queue[queue.translated_text.map(has_decoding_loop)]
    out=ROOT/'reports/retranslation';out.mkdir(exist_ok=True)
    cache_path=out/'proposals.jsonl';cache={}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            item=json.loads(line);cache[item['source_sha256']]=item
    todo=list(dict.fromkeys(queue.source_text))
    if args.limit:todo=todo[:args.limit]
    from lib.mt import Translator
    translator=Translator(ROOT/'models/nllb-200-distilled-600M',ROOT/'curation/glossary_en_hi.csv',threads=2)
    length=lambda text:len(translator.tok(translator.prepare(text)[0],add_special_tokens=True)['input_ids'])
    with cache_path.open('a',encoding='utf-8') as stream:
        for number,source in enumerate(todo,1):
            digest=hashlib.sha256(source.encode()).hexdigest()
            if digest in cache and not (args.retry_loops and cache[digest]["consecutive_loop"]):continue
            parts=split_budget(source,length)
            translations=translator.translate(parts,beams=2,batch_size=4,prevent_repetition=args.retry_loops)
            candidate=' '.join(row['hi'] for row in translations)
            flags=sorted({flag for row in translations for flag in row['qe_flags'].split(';') if flag})
            item={'source_sha256':digest,'source_en':source,'candidate_hi':candidate,'segments':len(parts),
                  'max_prepared_tokens':max(map(length,parts),default=0),'quality_flags':';'.join(flags),
                  'consecutive_loop':has_decoding_loop(candidate),'status':'machine_proposal_unreviewed',
                  'model_revision':'38bd1c6a0f58097b26ef7c7cd73a0dcac034350a',
                  'decoding_recipe':'no_repeat_ngram_4_retry' if args.retry_loops else 'standard_beam_2'}
            cache[digest]=item;stream.write(json.dumps(item,ensure_ascii=False)+'\n');stream.flush()
            print(f'{number}/{len(todo)}: segments={len(parts)} new_loop={item["consecutive_loop"]}',flush=True)
    records=[]
    for row in queue.itertuples():
        digest=hashlib.sha256(row.source_text.encode()).hexdigest()
        if digest in cache:
            records.append({'table':row.table,'record_id':row.record_id,'field':row.field,
                'previous_hi':row.translated_text,**cache[digest]})
    pd.DataFrame(records).to_csv(out/'record_proposals.csv',index=False)
    summary={'scope':args.scope,'unique_sources_selected':len(todo),'sources_cached':len(cache),
        'record_proposals':len(records),'proposals_with_loops':sum(r['consecutive_loop'] for r in records),
        'canonical_records_overwritten':0,'independent_language_approval':False}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n', encoding="utf-8");print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
