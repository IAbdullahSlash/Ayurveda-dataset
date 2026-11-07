import importlib
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from lib import export_transaction as transaction

def test_failure_preserves_previous_publication(tmp_path,monkeypatch):
    root, stage = tmp_path/'root', tmp_path/'stage'
    for directory in [root,stage]:
        (directory/'release').mkdir(parents=True)
    for name in ['a','b']:
        (root/'release'/name).write_text('old', encoding="utf-8")
        (stage/'release'/name).write_text('new', encoding="utf-8")
    real = transaction.os.replace
    failed = False
    def fail_once(source,target):
        nonlocal failed
        if str(target)==str(root/'release/b') and not failed:
            failed=True
            raise OSError('injected failure')
        real(source,target)
    monkeypatch.setattr(transaction.os,'replace',fail_once)
    with pytest.raises(OSError,match='injected'):
        transaction.publish(root,stage,['release/a','release/b'])
    assert (root/'release/a').read_text(encoding="utf-8")=='old'
    assert (root/'release/b').read_text(encoding="utf-8")=='old'
    assert not (root/'release/current_export.json').exists()
    transaction.publish(root,stage,['release/a','release/b'])
    pointer=json.loads((root/'release/current_export.json').read_text(encoding="utf-8"))
    assert (root/pointer['snapshot']/'release/a').read_text(encoding="utf-8")=='new'
