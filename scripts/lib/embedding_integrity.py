"""Bind generated embedding arrays to model weights and source snapshots."""
import hashlib,json,os
from pathlib import Path

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def record_index(folder,name,model,source):
    folder=Path(folder);path=folder/'manifest.json'
    manifest=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {'version':1,'indexes':{}}
    manifest['indexes'][name]={'model_sha256':digest(Path(model)/'model.safetensors'),
        'source_csv_sha256':digest(source),'array_sha256':digest(folder/f'{name}.npy'),
        'ids_sha256':digest(folder/f'{name}_ids.csv')}
    temporary=path.with_suffix('.pending');temporary.write_text(json.dumps(manifest,indent=2)+'\n', encoding="utf-8");os.replace(temporary,path)

def verify_index(folder,name,model,source):
    folder=Path(folder);path=folder/'manifest.json'
    if not path.exists():raise ValueError('Embedding manifest missing; rebuild stage 11')
    info=json.loads(path.read_text(encoding="utf-8"))['indexes'][name]
    actual={'model_sha256':digest(Path(model)/'model.safetensors'),'source_csv_sha256':digest(source),
            'array_sha256':digest(folder/f'{name}.npy'),'ids_sha256':digest(folder/f'{name}_ids.csv')}
    if info!=actual:raise ValueError('Embedding index is stale or incomplete; rebuild stage 11')
