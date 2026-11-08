import sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lib.materials import apply_material_types, apply_ingredient_material_types


def test_non_botanical_source_records_preserve_ids_and_do_not_become_plants():
    herbs = pd.read_csv(ROOT / 'data/processed/herbs.csv', keep_default_na=False)
    result = apply_material_types(herbs)
    assert result.herb_id.equals(herbs.herb_id)
    assert result.accepted_name.equals(herbs.accepted_name)
    assert result.material_type.value_counts().to_dict() == {'botanical_taxon_linked':453, 'identity_unresolved':11, 'non_botanical_material':2}
    non_botanical = result[result.herb_id.isin(['HERB-0045', 'HERB-0189'])]
    assert non_botanical.taxon_identity_status.eq('not_applicable_non_botanical').all()
    assert non_botanical.material_type_source_record.ne('').all()
    pd.testing.assert_frame_equal(result, apply_material_types(result))


def test_source_category_cannot_silently_override_changed_identity_or_taxon_link():
    herbs = pd.DataFrame([dict(herb_id='H1', accepted_name='source name', gbif_key='123')])
    override = dict(herb_id='H1', accepted_name='source name', material_type='non_botanical_material', source_id='S5', source_record='test-record', source_text='test source category')
    with pytest.raises(ValueError):
        apply_material_types(herbs, pd.DataFrame([override]))
    with pytest.raises(ValueError):
        apply_material_types(herbs, pd.DataFrame([{**override, 'accepted_name':'different name'}]))


def test_corpus_exposes_material_scope_without_removing_historical_documents():
    import importlib
    exporter = importlib.import_module('08_validate_export')
    report, tables = exporter.checks()
    assert not report['failures']
    documents = {d['doc_id']:d for d in exporter.corpus(tables)}
    assert documents['HERB-0189']['material_type'] == 'non_botanical_material'
    assert 'source material category only' in documents['HERB-0189']['text_en']
    assert sum(d['type']=='herb' for d in documents.values()) == 466


def test_linked_non_botanical_ingredients_keep_ids_but_not_herb_classification():
    herbs = pd.read_csv(ROOT / 'data/processed/herbs.csv', keep_default_na=False)
    ingredients = pd.read_csv(ROOT / 'data/processed/formulation_ingredients.csv', keep_default_na=False)
    fixed, history = apply_ingredient_material_types(ingredients, herbs)
    assert history == []
    subset = fixed[fixed.herb_id.isin(['HERB-0045', 'HERB-0189'])]
    assert len(subset) == 3 and subset.ingredient_type.eq('mineral/animal/other').all()
    broken = subset.copy(); broken['ingredient_type'] = 'herb'
    restored, changes = apply_ingredient_material_types(broken, herbs)
    assert len(changes) == 3
    assert restored.herb_id.equals(broken.herb_id)
