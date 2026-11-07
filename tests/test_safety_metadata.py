import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('demo_safety',ROOT/'examples/expert_system_demo.py')
demo=importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

def test_unknown_safety_is_visible():
    assert 'unassessed' in demo.safety_notice('', '')
    assert 'missing flags do not establish safety' in demo.safety_notice('', '')
    assert 'cardiac' in demo.safety_notice('toxic','cardiac hazard')
    assert 'not independently adjudicated' in demo.safety_notice('toxic','cardiac hazard')

def test_retrieval_tier_is_not_efficacy_claim():
    assert 'not efficacy assessed' in demo.TIER['clinical_evidence']


def test_explicit_states_do_not_promote_existing_flags_to_reviewed():
    import sys
    import pandas as pd
    sys.path.insert(0, str(ROOT / 'scripts'))
    from lib.safety import apply_safety_states, safety_text
    herbs = pd.read_csv(ROOT / 'data/processed/herbs.csv', keep_default_na=False)
    result = apply_safety_states(herbs)
    assert result.safety_assessment_status.value_counts().to_dict() == {'unassessed': 442, 'review_pending': 24}
    assert not result.safety_assessment_status.eq('assessed').any()
    pd.testing.assert_frame_equal(result, apply_safety_states(result))
    for row in result.to_dict('records'):
        assert safety_text(row) and safety_text(row, 'hi')


def test_safety_assessment_requires_complete_scoped_review_record():
    import pandas as pd
    import pytest
    from lib.safety import apply_safety_states, safety_text
    herbs = pd.DataFrame([dict(herb_id='H1', safety_class='', safety_hazard_en='', safety_hazard_hi='')])
    review = dict(herb_id='H1', reviewer='test-fixture reviewer', reference='test-fixture source', assessment_date='2026-11-08', scope='test-fixture preparation')
    result = apply_safety_states(herbs, pd.DataFrame([review]))
    assert result.iloc[0].safety_assessment_status == 'assessed'
    assert 'does not establish safe use' in safety_text(result.iloc[0].to_dict())
    for field in ['reviewer', 'reference', 'assessment_date', 'scope']:
        with pytest.raises(ValueError):
            apply_safety_states(herbs, pd.DataFrame([{**review, field: ''}]))
    with pytest.raises(ValueError):
        apply_safety_states(herbs, pd.DataFrame([{**review, 'herb_id': 'missing'}]))


def test_generated_herb_documents_and_property_qa_expose_safety_state():
    import importlib
    exporter = importlib.import_module('08_validate_export')
    report, tables = exporter.checks()
    assert not report['failures']
    herbs = [doc for doc in exporter.corpus(tables) if doc['type'] == 'herb']
    assert len(herbs) == 466
    assert all(doc['safety_review_status'] in {'unassessed', 'review_pending'} for doc in herbs)
    assert all('safety:' in doc['text_en'] for doc in herbs)
    qa = exporter.qa_pairs(tables)
    props = qa[qa.topic.eq('herb_properties')]
    assert props.loc[props.language.eq('en'), 'answer'].str.contains('safety:').all()
