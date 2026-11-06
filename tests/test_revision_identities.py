import importlib
import sys
from pathlib import Path
import numpy as np
import pytest
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.dummy import DummyClassifier
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
export = importlib.import_module("08_validate_export")


def test_identity_survives_earlier_sorting_insertion(tmp_path, monkeypatch):
    import json
    from lib import stable_ids
    registry = tmp_path / 'ids.json'
    registry.write_text(json.dumps({'herbs': {'Zea mays': 'HERB-0466'}}))
    monkeypatch.setattr(stable_ids, 'REGISTRY', registry)
    mapping = stable_ids.allocate('herbs', ['A new species', 'Zea mays'])
    assert mapping['Zea mays'] == 'HERB-0466'
    assert mapping['A new species'] == 'HERB-0467'
    assert stable_ids.allocate('herbs', ['A new species']) == mapping

def test_reviewed_alias_keeps_identity(tmp_path, monkeypatch):
    import json
    from lib import stable_ids
    registry=tmp_path/'ids.json'; aliases=tmp_path/'aliases.csv'
    registry.write_text(json.dumps({'herbs':{'Old taxon':'HERB-0007'}}))
    aliases.write_text('namespace,alias,canonical_key,reference,reviewer,decision\nherbs,New taxon,Old taxon,source-123,reviewer-A,approved\n')
    monkeypatch.setattr(stable_ids,'REGISTRY',registry)
    monkeypatch.setattr(stable_ids,'ALIASES',aliases)
    assert stable_ids.allocate('herbs',['New taxon'])['New taxon']=='HERB-0007'
    assert json.loads(registry.read_text())['herbs']=={'Old taxon':'HERB-0007'}

def test_alias_cannot_merge_published_ids(tmp_path, monkeypatch):
    import json
    from lib import stable_ids
    registry=tmp_path/'ids.json'; aliases=tmp_path/'aliases.csv'
    registry.write_text(json.dumps({'herbs':{'A':'HERB-0001','B':'HERB-0002'}}))
    aliases.write_text('namespace,alias,canonical_key,reference,reviewer,decision\nherbs,A,B,source,R,approved\n')
    monkeypatch.setattr(stable_ids,'REGISTRY',registry)
    monkeypatch.setattr(stable_ids,'ALIASES',aliases)
    with pytest.raises(ValueError,match='merge distinct'):
        stable_ids.allocate('herbs',['A'])

def test_registry_preserves_all_current_ids():
    import json
    import pandas as pd
    from lib.keys import skeleton
    root=Path(__file__).resolve().parents[1]
    registry=json.loads((root/'curation/id_registry.json').read_text())
    for row in pd.read_csv(root/'data/processed/herbs.csv',keep_default_na=False).itertuples():
        assert registry['herbs'][row.accepted_name]==row.herb_id
    for row in pd.read_csv(root/'data/processed/symptoms.csv',keep_default_na=False).itertuples():
        if row.symptom_id.startswith('SYM-N'):
            key=skeleton(row.term_sa_iast) if row.term_sa_iast else row.gloss_en.lower()
            assert registry['symptoms'][key]==row.symptom_id
