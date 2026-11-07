import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from lib.embedding_integrity import record_index,verify_index

def test_embedding_manifest_rejects_changed_model_or_source(tmp_path):
    folder=tmp_path/'index';folder.mkdir();model=tmp_path/'model';model.mkdir()
    weights=model/'model.safetensors';weights.write_bytes(b'weights')
    source=tmp_path/'symptoms.csv';source.write_text('id,text\nS1,fever\n', encoding="utf-8")
    (folder/'symptoms.npy').write_bytes(b'array');(folder/'symptoms_ids.csv').write_text('id\nS1\n', encoding="utf-8")
    record_index(folder,'symptoms',model,source);verify_index(folder,'symptoms',model,source)
    weights.write_bytes(b'changed weights')
    with pytest.raises(ValueError,match='stale'):verify_index(folder,'symptoms',model,source)
    weights.write_bytes(b'weights');source.write_text('id,text\nS1,cough\n', encoding="utf-8")
    with pytest.raises(ValueError,match='stale'):verify_index(folder,'symptoms',model,source)
