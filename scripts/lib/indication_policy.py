"""Conservative indication containment; a review finding is not a replacement label."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TARGET_FIELDS = ('disease_id', 'disease_term_iast', 'disease_name_en')
BLOCKED = {'quarantined', 'candidate_review_pending', 'unmatched'}


def contain_indications(frame, decisions=None):
    """Clear active targets while preserving originals and the evidence for containment."""
    out = frame.copy()
    if decisions is None:
        decisions = pd.read_csv(ROOT / 'curation/indication_quarantine.csv', keep_default_na=False)
    for field in TARGET_FIELDS:
        if 'original_' + field not in out:
            out['original_' + field] = out[field]
    if 'mapping_status' not in out:
        out['mapping_status'] = out.disease_id.ne('').map({True: 'source_matched_unreviewed', False: 'unmatched'})
    for field in ('mapping_reason', 'mapping_reference'):
        if field not in out:
            out[field] = ''
    if decisions.duplicated(['indication_raw', 'disease_id']).any():
        raise ValueError('Duplicate quarantine decisions')
    for decision in decisions.itertuples():
        mask = out.indication_raw.eq(decision.indication_raw) & out.original_disease_id.eq(decision.disease_id)
        if not decision.reason or not decision.reference:
            raise ValueError('Containment requires a reason and reference')
        out.loc[mask, list(TARGET_FIELDS)] = ''
        out.loc[mask, 'mapping_status'] = 'quarantined'
        out.loc[mask, 'mapping_reason'] = decision.reason
        out.loc[mask, 'mapping_reference'] = decision.reference
    return out


def active_indications(frame):
    out = contain_indications(frame)
    return out.loc[out.disease_id.ne('') & ~out.mapping_status.isin(BLOCKED)].copy()


def supported_evidence(evidence, indications):
    """A literature result cannot authorize an unsupported indication mapping."""
    pairs = active_indications(indications)[['herb_id', 'disease_id']].drop_duplicates()
    return evidence.merge(pairs, on=['herb_id', 'disease_id'], how='inner', validate='many_to_one')
