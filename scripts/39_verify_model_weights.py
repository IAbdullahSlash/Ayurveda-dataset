#!/usr/bin/env python3
"""Verify pinned model weights against the Hub's revision-specific LFS SHA-256."""
import hashlib,importlib,json
from pathlib import Path
from huggingface_hub import HfApi
ROOT=Path(__file__).resolve().parents[1]

def main():
    specs=importlib.import_module('00_get_models').MODELS
    records=[]
    for name,(repo,revision) in specs.items():
        path=ROOT/'models'/name/'model.safetensors'
        if not path.exists():raise FileNotFoundError(path)
        info=HfApi().model_info(repo,revision=revision,files_metadata=True)
        sibling=next(file for file in info.siblings if file.rfilename=='model.safetensors')
        expected=sibling.lfs.sha256
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=expected:raise ValueError('Model checksum mismatch: '+name)
        records.append({'model':name,'repository':repo,'revision':revision,'resolved_revision':info.sha,
                        'file':'model.safetensors','sha256':actual,'bytes':path.stat().st_size,'verified':True})
    out=ROOT/'reports/model_weight_verification.json'
    out.write_text(json.dumps(records,indent=2)+'\n', encoding="utf-8")
    print('Verified pinned weight checksums for '+', '.join(record['model'] for record in records))
if __name__=='__main__':main()
