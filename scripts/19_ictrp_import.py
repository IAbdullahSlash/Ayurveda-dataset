#!/usr/bin/env python3
"""
Stage 19 (optional, manual input) - Import Ayurveda trials from a WHO ICTRP export (includes CTRI, India).

Why manual: CTRI has no public API, and the WHO ICTRP Search Portal (https://trialsearch.who.int) disallows automated
crawling (robots.txt: Disallow /).  WHO's terms do allow downloading records from the Search Portal at no charge,
for non-commercial use, with attribution ("WHO ICTRP") and the processing date displayed.
  1. Search https://trialsearch.who.int  (e.g. Intervention or Condition: ayurved*  OR  Source register: CTRI)
  2. Export the results as CSV (or request the full ICTRP dataset from WHO).
  3. python3 scripts/19_ictrp_import.py --csv path/to/ICTRP_export.csv [--processed-date YYYY-MM-DD]
The importer keeps trial-level fields only - investigator names, e-mails, phone numbers and addresses are DROPPED
(personal data) - and links each trial to KB herbs, formulations and NAMASTE disorders with the KB lexicons.
Output: data/processed/ictrp_trials.csv, ictrp_trial_links.csv
"""
import argparse, re, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib import import_module
cr = import_module("14_case_reports")                     # reuse the KB lexicons and matchers

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
WANT = {  # canonical column -> patterns matched against lower-cased export headers
    "trial_id": [r"^trialid$", r"trial ?id"], "public_title": [r"public title"], "scientific_title": [r"scientific title"],
    "source_register": [r"source regist"], "url": [r"web address", r"^url$"], "registration_date": [r"date registration$", r"date of registration", r"date registration"],
    "recruitment_status": [r"recruitment status"], "study_type": [r"study type"], "study_design": [r"study design"],
    "phase": [r"^phase$"], "target_size": [r"target size", r"sample size"], "countries": [r"countr"],
    "condition": [r"^condition", r"health condition"], "intervention": [r"^intervention"],
    "primary_outcome": [r"primary outcome"], "primary_sponsor": [r"primary sponsor"], "last_refreshed": [r"last refreshed"]}
PERSONAL = re.compile(r"contact|e-?mail|\btel\b|phone|first ?name|last ?name|investigator|affiliation", re.I)

def pick(cols):
    out = {}
    for k, pats in WANT.items():
        for c in cols:
            if any(re.search(p, c.lower()) for p in pats) and not PERSONAL.search(c):
                out[k] = c
                break
    return out

def main(csv, processed_date=""):
    raw = pd.read_csv(csv, dtype=str, keep_default_na=False, encoding_errors="replace")
    m = pick(raw.columns)
    if "trial_id" not in m:
        raise SystemExit(f"no TrialID column found in {csv}; columns: {list(raw.columns)[:20]}")
    T = pd.DataFrame({k: raw[v] for k, v in m.items()})
    T["ayurveda_related"] = (T.get("public_title", "") + " " + T.get("scientific_title", "") + " " + T.get("intervention", "")
                             + " " + T.get("condition", "")).str.contains(r"ayurved|panchakarma|rasayana|churna|kwath|vati|ghrita|taila|bhasma",
                                                                          case=False, regex=True)
    lex = cr.build_lexicons()
    links = []
    for r in T.itertuples():
        title = f"{getattr(r, 'public_title', '')} {getattr(r, 'scientific_title', '')}"
        cond, intv = getattr(r, "condition", ""), getattr(r, "intervention", "")
        _, _, dx, _ = cr.diagnosis(title + " " + cond, "", "", lex)
        for d in dx[:3]:
            links.append((r.trial_id, "disease", d))
        for k, ids in {**cr.find_sk(intv + " " + title, lex["herb_sk"], 2), **cr.find_phrase(intv + " " + title, lex["herb_phrase"])}.items():
            for h in ids:
                links.append((r.trial_id, "herb", h))
        for k, ids in cr.find_sk(intv + " " + title, lex["form_sk"], 4).items():
            for f in ids:
                links.append((r.trial_id, "formulation", f))
    T["source_id"] = "S13"
    T["attribution"] = "WHO International Clinical Trials Registry Platform (ICTRP)" + (f"; processed by WHO ICTRP on {processed_date}" if processed_date else "")
    T["licence"] = "WHO ICTRP terms: non-commercial use, attribution, keep current, show processing date"
    T.to_csv(P / "ictrp_trials.csv", index=False)
    L = pd.DataFrame(links, columns=["trial_id", "entity_type", "entity_id"]).drop_duplicates()
    L.to_csv(P / "ictrp_trial_links.csv", index=False)
    print(f"ICTRP trials imported: {len(T)} (Ayurveda-related {int(T.ayurveda_related.sum())}); links: {L.entity_type.value_counts().to_dict()}")
    print("dropped personal-data columns:", [c for c in raw.columns if PERSONAL.search(c)])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="CSV exported from https://trialsearch.who.int")
    ap.add_argument("--processed-date", default="", help="date WHO ICTRP processed the export (shown for attribution)")
    a = ap.parse_args()
    main(a.csv, a.processed_date)
