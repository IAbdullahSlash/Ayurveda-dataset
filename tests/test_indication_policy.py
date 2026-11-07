import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lib.indication_policy import contain_indications, active_indications, supported_evidence


def test_reported_bad_targets_are_contained_and_history_survives():
    frame = pd.read_csv(ROOT / 'data/processed/herb_indication.csv', keep_default_na=False)
    result = contain_indications(frame)
    blocked = result[result.mapping_status.eq('quarantined')]
    assert len(blocked) == 49  # 48 reported wrong, one reported over-broad
    assert blocked.disease_id.eq('').all()
    assert blocked.original_disease_id.ne('').all()
    assert blocked.mapping_reference.ne('').all()
    pd.testing.assert_frame_equal(result, contain_indications(result))


def test_uncontained_input_cannot_reintroduce_bad_mapping_or_evidence():
    row = dict(herb_id='H1', indication_raw='Kshaya', disease_id='AYD-02923',
               disease_term_iast='kāyaḥ', disease_name_en='psychic constitution')
    links = pd.DataFrame([row])
    assert active_indications(links).empty
    evidence = pd.DataFrame([dict(herb_id='H1', disease_id='AYD-02923', evidence_tier='clinical_evidence')])
    assert supported_evidence(evidence, links).empty


def test_evidence_survives_if_a_separate_active_indication_supports_same_pair():
    links = pd.DataFrame([
        dict(herb_id='H1', indication_raw='Kshaya', disease_id='AYD-02923', disease_term_iast='', disease_name_en=''),
        dict(herb_id='H1', indication_raw='different source indication', disease_id='AYD-02923', disease_term_iast='', disease_name_en='')])
    evidence = pd.DataFrame([dict(herb_id='H1', disease_id='AYD-02923')])
    assert len(supported_evidence(evidence, links)) == 1
