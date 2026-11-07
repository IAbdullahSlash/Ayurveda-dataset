#!/usr/bin/env python3
"""Reproduce fold-local E1 upgrades with model/input-addressed encoding reuse."""
import hashlib,importlib,json,os
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

def main():
    upgrades=importlib.import_module('26_model_upgrades')
    records=json.loads((ROOT/'reports/model_weight_verification.json').read_text(encoding="utf-8"))
    expected=next(row['sha256'] for row in records if row['model']=='multilingual-e5-small')
    model=ROOT/'models/multilingual-e5-small'
    with (model/'model.safetensors').open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:raise ValueError('Base model changed')
    encoder=upgrades.xl.E5(threads=2,model=model)
    cache=ROOT/'models/benchmark_encoding_cache';cache.mkdir(exist_ok=True)
    code_hash=hashlib.sha256((ROOT/'scripts/10_crosslingual.py').read_bytes()).hexdigest()
    class CachedEncoder:
        def encode(self,texts,prefix):
            key=hashlib.sha256(json.dumps({'texts':texts,'prefix':prefix,'model_sha256':expected,
                'encoder_code_sha256':code_hash,'threads':2},ensure_ascii=False).encode()).hexdigest()
            path=cache/(key+'.npy')
            if path.exists():
                matrix=np.load(path,allow_pickle=False)
                if matrix.shape!=(len(texts),384) or not np.isfinite(matrix).all():raise ValueError('Invalid cached encoding')
                return matrix
            matrix=encoder.encode(texts,prefix)
            temporary=cache/(key+'.pending.npy');np.save(temporary,matrix);os.replace(temporary,path)
            return matrix
    upgrades.REP=ROOT/'reports/revision_semantic';upgrades.REP.mkdir(exist_ok=True)
    os.environ['AYURKB_SPLIT_DIR']=str(upgrades.REP/'splits')
    upgrades.e1_plus(CachedEncoder())
if __name__=='__main__':main()
