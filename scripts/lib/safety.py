"""Assessment state is separate from hazard class and never implies blanket safety."""
from datetime import date
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REVIEW_FIELDS = ('reviewer', 'reference', 'assessment_date', 'scope')


def apply_safety_states(herbs, reviews=None):
    out = herbs.copy()
    if reviews is None:
        reviews = pd.read_csv(ROOT / 'curation/herb_safety_reviews.csv', keep_default_na=False)
    if reviews.herb_id.duplicated().any() or not set(reviews.herb_id) <= set(out.herb_id):
        raise ValueError('Duplicate or unknown safety review herb ID')
    flagged = out.safety_class.ne('') | out.safety_hazard_en.ne('') | out.safety_hazard_hi.ne('')
    out['safety_assessment_status'] = flagged.map({True: 'review_pending', False: 'unassessed'})
    for field in REVIEW_FIELDS:
        out['safety_review_' + field] = ''
    for row in reviews.to_dict('records'):
        if any(not str(row[field]).strip() for field in REVIEW_FIELDS):
            raise ValueError('Safety assessment requires reviewer, source, date and scope')
        if date.fromisoformat(row['assessment_date']).isoformat() != row['assessment_date']:
            raise ValueError('Safety assessment date must be YYYY-MM-DD')
        mask = out.herb_id.eq(row['herb_id'])
        out.loc[mask, 'safety_assessment_status'] = 'assessed'
        for field in REVIEW_FIELDS:
            out.loc[mask, 'safety_review_' + field] = row[field]
    return out


def safety_text(row, language='en'):
    state = row.get('safety_assessment_status') or ('review_pending' if row.get('safety_class') else 'unassessed')
    if language == 'hi':
        labels = {'unassessed': 'सुरक्षा का आकलन नहीं हुआ है',
                  'review_pending': 'सुरक्षा की जानकारी दर्ज है; स्वतंत्र समीक्षा बाकी है',
                  'assessed': 'दर्ज दायरे में सुरक्षा का आकलन हुआ है; यह सुरक्षित उपयोग की गारंटी नहीं है'}
        return labels.get(state, labels['unassessed']) + '। ' + str(row.get('safety_hazard_hi', ''))
    if state == 'assessed':
        return f"safety: assessed only within recorded scope ({row.get('safety_review_scope', '')}); assessment does not establish safe use. {row.get('safety_hazard_en', '')}"
    if state == 'review_pending':
        return f"safety: review pending; {row.get('safety_class', '')}: {row.get('safety_hazard_en', '')}; not independently adjudicated"
    return 'safety: unassessed (missing flags do not establish safety)'
