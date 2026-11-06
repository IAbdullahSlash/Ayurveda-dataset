import importlib
import sys
from pathlib import Path
import numpy as np
import pytest
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.dummy import DummyClassifier
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
export = importlib.import_module("08_validate_export")


def test_preserve_modifier_scope():
    build = importlib.import_module('04_build_kb')
    assert build.parse_symptoms('The disorder is characterized by frequent and excessive urination') == [('', 'frequent and excessive urination')]

@pytest.mark.parametrize('phrase',[
    'pain without fever', 'no fever or chills', 'severe pain with intermittent vomiting',
    'frequent and excessive urination', 'nausea or vomiting'])
def test_keep_negation_severity_and_alternative_scope(phrase):
    build=importlib.import_module('04_build_kb')
    assert build.parse_symptoms('Characterized by '+phrase)==[('',phrase)]

def test_bracketed_gloss_preserves_internal_coordination():
    build=importlib.import_module('04_build_kb')
    result=build.parse_symptoms('characterized by jvara [fever with chills]; chardi [vomiting]')
    assert [en for _,en in result]==['fever with chills','vomiting']
