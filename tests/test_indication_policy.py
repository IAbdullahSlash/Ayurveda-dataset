import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from lib.indication_policy import contain_indications, active_indications, supported_evidence
from lib.indication_policy import apply_mapping_policy
import pytest


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


def test_fuzzy_and_ambiguous_exact_matches_abstain():
    diseases = pd.DataFrame([dict(disease_id='D1', term_iast='jvaraḥ', name_en='fever'),
                             dict(disease_id='D2', term_iast='jvaraḥ', name_en='other sense')])
    links = pd.DataFrame([dict(herb_id='H1', indication_raw='Jwara', disease_id='D1',
        disease_term_iast='jvaraḥ', disease_name_en='fever', match_method='exact_skeleton', match_score=100.0),
        dict(herb_id='H2', indication_raw='Jwraa', disease_id='D1', disease_term_iast='jvaraḥ',
             disease_name_en='fever', match_method='fuzzy_skeleton', match_score=90.0)])
    out = apply_mapping_policy(links, diseases, pd.DataFrame())
    assert out.disease_id.eq('').all()
    assert out.mapping_status.eq('candidate_review_pending').all()
    assert out.iloc[0].candidate_disease_ids == 'D1;D2'
    pd.testing.assert_frame_equal(out, apply_mapping_policy(out, diseases, pd.DataFrame()))


def test_reviewed_alias_requires_equivalent_target_and_audit_fields():
    diseases = pd.DataFrame([dict(disease_id='D1', term_iast='jvaraḥ', name_en='fever')])
    links = pd.DataFrame([dict(herb_id='H1', indication_raw='Jwraa', disease_id='D1',
        disease_term_iast='jvaraḥ', disease_name_en='fever', match_method='fuzzy_skeleton', match_score=90.0)])
    alias = dict(indication_raw='Jwraa', disease_id='D1', decision='accepted', relation='equivalent', reviewer='test-fixture reviewer', reference='test-fixture source')
    out = apply_mapping_policy(links, diseases, pd.DataFrame([alias]))
    assert out.iloc[0].disease_id == 'D1' and out.iloc[0].mapping_status == 'alias_reviewed'
    for field, value in [('reviewer', ''), ('reference', ''), ('relation', 'broader'), ('disease_id', 'missing')]:
        with pytest.raises(ValueError):
            apply_mapping_policy(links, diseases, pd.DataFrame([{**alias, field: value}]))


def test_current_evidence_and_qa_do_not_reintroduce_withdrawn_targets():
    import importlib
    links = pd.read_csv(ROOT / 'data/processed/herb_indication.csv', keep_default_na=False)
    evidence = pd.read_csv(ROOT / 'data/processed/herb_indication_evidence.csv', keep_default_na=False)
    assert len(evidence) == len(supported_evidence(evidence, links))
    qa = pd.read_csv(ROOT / 'data/processed/qa_pairs.csv', keep_default_na=False)
    indication_qa = qa[qa.topic.eq('herbs_for_condition')]
    active = active_indications(links)
    pairs = set(zip(active.herb_id, active.disease_id))
    for row in indication_qa.itertuples():
        disease, *herbs = row.record_ids.split(';')
        assert all((herb, disease) in pairs for herb in herbs)
    exporter = importlib.import_module('08_validate_export')
    report, _ = exporter.checks()
    assert not report['failures']


def test_decision_provenance_distinguishes_history_and_active_assertions():
    from lib.provenance import metadata
    row = dict(herb_id='H1', indication_raw='Kshaya', disease_id='',
        original_disease_id='AYD-02923', candidate_disease_ids='AYD-02923',
        match_method='fuzzy_skeleton', mapping_status='quarantined',
        mapping_reference='test-fixture PDF reference', mapping_reason='test-fixture wrong sense', source_id='S5')
    result = metadata('herb_indication', row, {'AYD-02923': {'S1'}}, {'S1': 'test', 'S5': 'test'})
    decision = result['field_overrides']['disease_id']
    assert decision['active_target'] == ''
    assert decision['historical_target'] == 'AYD-02923'
    assert decision['review_status'] == 'quarantined'
    assert decision['decision_reference'] == row['mapping_reference']
    assert 'not accepted assertions' in decision['note']


def test_unknown_or_forged_reviewed_mapping_states_fail_closed():
    diseases = pd.DataFrame([dict(disease_id='D1', term_iast='jvaraḥ', name_en='fever')])
    row = dict(herb_id='H1', indication_raw='Jwara', disease_id='D1', disease_term_iast='jvaraḥ',
        disease_name_en='fever', match_method='exact_skeleton', match_score=100.0)
    for state in ['unknown', 'alias_reviewed']:
        with pytest.raises(ValueError):
            apply_mapping_policy(pd.DataFrame([{**row, 'mapping_status': state}]), diseases, pd.DataFrame())
