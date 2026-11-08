"""The AI pre-review must stay a suggestion until a reviewer signs it (stages 53 and 54)."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from lib.indication_policy import ACTIVE, apply_mapping_policy

promote = importlib.import_module("54_promote_alias_reviews")
rd = lambda p: pd.read_csv(ROOT / p, keep_default_na=False, dtype=str, low_memory=False)


@pytest.fixture(scope="module")
def prereview():
    return rd("reports/indication_review/ai_prereview.csv")


@pytest.fixture(scope="module")
def diseases():
    return rd("data/processed/diseases.csv")


def test_suggestions_point_at_real_disorders_and_source_terms(prereview, diseases):
    ids = set(diseases.disease_id)
    raw = set(rd("data/processed/herb_indication.csv").indication_raw)
    assert prereview.indication_raw.is_unique
    assert set(prereview.indication_raw) <= raw
    assert set(prereview.suggestion) <= {"accept", "accept_replacement", "needs_expert", "no_target"}
    targeted = prereview[prereview.suggestion.ne("no_target")]
    assert targeted.suggested_disease_id.isin(ids).all()
    assert prereview.loc[prereview.suggestion.eq("no_target"), "suggested_disease_id"].eq("").all()
    assert prereview.rationale.str.len().gt(20).all()


def test_suggestions_carry_no_reviewer_sign_off(prereview):
    """Drafts are labelled as AI and every reviewer field starts blank."""
    assert prereview.drafted_by.str.contains("AI pre-review").all()
    for col in ("reviewer_verdict", "reviewer_disease_id", "reviewer", "reference", "reviewer_comment"):
        assert prereview[col].eq("").all(), f"{col} must be filled by a reviewer, not generated"


def test_policy_ignores_the_prereview(diseases):
    """Only the ledger can activate links; the pre-review file changes nothing on its own."""
    links = rd("data/processed/herb_indication.csv")
    ledger = rd("curation/indication_aliases.csv")
    assert not ledger.reviewer.str.contains("AI|Claude|SIMULATION", case=False).any()
    applied = apply_mapping_policy(links, diseases=diseases)
    assert applied.mapping_status.equals(links.mapping_status)


def _signed(prereview, **fields):
    row = prereview.iloc[[0]].copy()
    for k, v in fields.items():
        row[k] = v
    return row


def test_unsigned_rows_are_skipped(prereview, diseases):
    rows, skipped = promote.ledger_rows(prereview, set(diseases.disease_id))
    assert rows.empty and skipped == len(prereview)


def test_confirm_writes_an_accepted_alias(prereview, diseases):
    row = _signed(prereview[prereview.suggestion.eq("accept")], reviewer_verdict="confirm", reviewer="Dr A", reference="Caraka Ci. 1.2")
    rows, _ = promote.ledger_rows(row, set(diseases.disease_id))
    r = rows.iloc[0]
    assert (r.decision, r.relation, r.disease_id) == ("accepted", "equivalent", row.suggested_disease_id.iloc[0])


def test_change_and_reject(prereview, diseases):
    ids = set(diseases.disease_id)
    base = prereview[prereview.suggestion.eq("accept")]
    changed, _ = promote.ledger_rows(_signed(base, reviewer_verdict="change", reviewer_disease_id="AYD-00002", reviewer="R", reference="ref"), ids)
    assert changed.disease_id.iloc[0] == "AYD-00002"
    rejected, _ = promote.ledger_rows(_signed(base, reviewer_verdict="reject", reviewer="R", reference="ref"), ids)
    assert rejected.decision.iloc[0] == "rejected"


@pytest.mark.parametrize("fields", [
    dict(reviewer_verdict="confirm", reviewer="", reference="ref"),             # no reviewer
    dict(reviewer_verdict="confirm", reviewer="R", reference=""),               # no reference
    dict(reviewer_verdict="maybe", reviewer="R", reference="ref"),              # unknown verdict
    dict(reviewer_verdict="change", reviewer_disease_id="AYD-99999", reviewer="R", reference="ref"),  # bad disorder
])
def test_invalid_signatures_are_refused(prereview, diseases, fields):
    with pytest.raises(ValueError):
        promote.ledger_rows(_signed(prereview, **fields), set(diseases.disease_id))


def test_ledger_decisions_are_not_silently_overwritten():
    old = pd.DataFrame([dict(indication_raw="Kamala", disease_id="AYD-00874", decision="accepted", relation="equivalent", reviewer="R1", reference="a")])
    new = old.assign(disease_id="AYD-00274", reviewer="R2")
    with pytest.raises(ValueError):
        promote.merge(old, new)
    merged, added, changed = promote.merge(old, new, replace=True)
    assert (added, changed) == (0, 1) and merged.disease_id.iloc[0] == "AYD-00274"
    same, added, changed = promote.merge(old, old)
    assert (added, changed) == (0, 0)


def test_confirmed_suggestions_would_activate_links(prereview, diseases):
    """Simulated sign-off of every accept/replacement passes the policy's own validation."""
    links = rd("data/processed/herb_indication.csv")
    ok = prereview[prereview.suggestion.isin(["accept", "accept_replacement"])]
    signed = ok.assign(reviewer_verdict="confirm", reviewer="test", reference="test")
    rows, _ = promote.ledger_rows(signed, set(diseases.disease_id))
    after = apply_mapping_policy(links, diseases=diseases, aliases=rows)
    active = lambda f: int((f.disease_id.ne("") & f.mapping_status.isin(ACTIVE)).sum())
    assert active(after) > active(apply_mapping_policy(links, diseases=diseases))
    assert not after.mapping_status.eq("quarantined").any()
