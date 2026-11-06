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
