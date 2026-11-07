import importlib
import sys
from pathlib import Path
import numpy as np
import pytest
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.dummy import DummyClassifier
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
export = importlib.import_module("08_validate_export")


def test_who_attribution_and_bilingual_references():
    _, tables = export.checks()
    docs = {d['doc_id']: d for d in export.corpus(tables)}
    affected = tables['diseases'].query('definition_source.str.startswith("WHO")', engine='python')
    assert len(affected) == 415
    for row in affected.itertuples():
        assert 'S3' in docs[row.disease_id]['source'].split(';')
        assert docs[row.disease_id]['definition_record_id'] == row.who_term_id
    qa = export.qa_pairs(tables).set_index('qa_id')
    for key in qa.index:
        if key.startswith('QA-I-') and key.endswith('-hi'):
            assert qa.loc[key, 'record_ids'] == qa.loc[key[:-3], 'record_ids']

def test_export_stops_on_invalid_input(monkeypatch, tmp_path):
    monkeypatch.setattr(export, 'checks', lambda: ({'failures': ['orphan']}, {}))
    monkeypatch.setattr(export, 'REL', tmp_path)
    with pytest.raises(ValueError, match='orphan'):
        export.main()
    assert not list(tmp_path.iterdir())

def test_descriptor_resolves_from_release_directory(tmp_path, monkeypatch):
    import json
    _, tables = export.checks()
    monkeypatch.setattr(export, 'REL', tmp_path)
    export.datapackage(tables)
    root = Path(__file__).resolve().parents[1]
    for resource in json.loads((tmp_path / 'datapackage.json').read_text(encoding="utf-8"))['resources']:
        assert (root / 'release' / resource['path']).is_file()

def test_all_tables_have_source_dependencies():
    from lib.provenance import build_index, metadata
    _, tables = export.checks()
    index = build_index(tables)
    licences = dict(zip(tables['sources'].source_id,tables['sources'].licence))
    unresolved = []
    for name, df in tables.items():
        for row in df.to_dict('records'):
            meta = metadata(name,row,index,licences)
            if meta['provenance_status'] == 'unresolved':
                unresolved.append((name,meta['record_ref']))
    assert not unresolved, unresolved[:10]
