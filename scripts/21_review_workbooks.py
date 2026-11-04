#!/usr/bin/env python3
"""
Stage 21 - Expert-review workbooks (build) and merge-back of completed reviews (merge).

  python3 scripts/21_review_workbooks.py --build    -> review/AyurKB_expert_review.xlsx
  python3 scripts/21_review_workbooks.py --merge    -> curation/expert_reviews.csv + reports/expert_review_agreement.json
                                                       (reads every completed workbook in review/returned/)
The workbook has one sheet per curation question (herb properties, herb->disorder links, therapy->disorder links,
Ayurveda->biomedicine correspondences, classical formulations, Hindi translations, case-report extractions) with
drop-down verdict columns, so qualified vaidyas can review offline without touching the data files.  Merging keeps
every reviewer's verdict (no silent overwrite) and computes agreement (Cohen / Fleiss kappa) when >= 2 reviewers
answered the same item.
"""
import argparse, datetime, json, re
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
P, OUT = ROOT / "data/processed", ROOT / "review"
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)
HEAD = PatternFill("solid", fgColor="0F8A5F")
REVIEW = PatternFill("solid", fgColor="FFF4D6")
VERDICTS = {
    "herb_properties": ["Correct", "Partly correct", "Incorrect", "Unsure"],
    "herb_disorder_links": ["Valid", "Valid with condition", "Invalid", "Unsure"],
    "therapy_disorder_links": ["Indicated", "Indicated with condition", "Not indicated", "Unsure"],
    "biomedical_map": ["Correct", "Approximate", "Incorrect", "Unsure"],
    "formulations": ["Matches AFI/classical text", "Minor difference", "Major difference", "Unsure"],
    "hindi_translations": ["Acceptable", "Minor edit needed", "Major error", "Not Hindi / garbled"],
    "case_reports": ["Extraction correct", "Partly correct", "Incorrect", "Unsure"],
}
REVIEW_COLS = ["verdict", "corrected_value", "classical_or_literature_reference", "comment"]

def sheet(wb, name, df, key, widths=None, intro=""):
    ws = wb.create_sheet(name)
    cols = list(df.columns) + REVIEW_COLS
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = HEAD; c.alignment = Alignment(wrap_text=True, vertical="top")
    for row in df.itertuples(index=False):
        ws.append([("" if v is None else v) for v in row] + [""] * len(REVIEW_COLS))
    n = len(df) + 1
    first_review = len(df.columns) + 1
    for j in range(first_review, len(cols) + 1):
        for i in range(2, n + 1):
            ws.cell(i, j).fill = REVIEW
    dv = DataValidation(type="list", formula1='"' + ",".join(VERDICTS[name]) + '"', allow_blank=True,
                        showErrorMessage=True, errorTitle="Choose a verdict", error="Pick one of the listed verdicts")
    col = ws.cell(1, first_review).column_letter
    dv.add(f"{col}2:{col}{max(n, 2)}")
    ws.add_data_validation(dv)
    ws.freeze_panes = "B2"
    for j, c in enumerate(cols, 1):
        w = (widths or {}).get(c, 14 if j < first_review else 22)
        ws.column_dimensions[ws.cell(1, j).column_letter].width = w
        for i in range(2, min(n, 3000) + 1):
            ws.cell(i, j).alignment = Alignment(wrap_text=True, vertical="top")
    ws.sheet_properties.tabColor = "0F8A5F"
    ws["A1"].comment = None
    return ws

def build():
    OUT.mkdir(exist_ok=True)
    wb = Workbook()
    rm = wb.active; rm.title = "README"
    lines = [
        ("AyurKB expert review workbook / AyurKB विशेषज्ञ समीक्षा कार्यपुस्तिका", True),
        (f"Generated {datetime.date.today().isoformat()} from the AyurKB release. Each sheet = one curation question.", False),
        ("Reviewer ID (initials or code, no e-mail) / समीक्षक कोड:", True),
        ("", False),
        ("How to review: fill ONLY the yellow columns. 'verdict' has a drop-down list. Put a corrected value and a classical"
         " reference (e.g. 'Caraka Ci 7.41', 'API Vol. I p. 23', 'AFI Part I 4:12') where you disagree.", False),
        ("समीक्षा कैसे करें: केवल पीले कॉलम भरें। 'verdict' में सूची से चुनें। असहमति होने पर सही मान और शास्त्रीय संदर्भ लिखें।", False),
        ("Skip anything outside your expertise - 'Unsure' is a valid, useful answer. Partial reviews are welcome.", False),
        ("Return the file as review/returned/<reviewer_id>.xlsx; scripts/21_review_workbooks.py --merge collects all verdicts.", False),
        ("Your answers are attributed only by the reviewer code above. Thank you! / धन्यवाद!", False),
    ]
    for i, (t, b) in enumerate(lines, 1):
        rm.cell(i, 1, t).font = Font(bold=b, size=13 if i == 1 else 11)
        rm.cell(i, 1).alignment = Alignment(wrap_text=True, vertical="top")
    rm["B3"].fill = REVIEW
    rm.column_dimensions["A"].width = 110; rm.column_dimensions["B"].width = 24
    # 1 herb properties
    H = rd("herbs")
    h = H[H.rasa != ""][["herb_id", "name_sa_iast", "name_sa_deva", "accepted_name", "rasa", "guna", "virya", "vipaka",
                         "dosha_pacify", "dosha_aggravate", "karma_actions", "property_variants"]]
    sheet(wb, "herb_properties", h, "herb_id", {"karma_actions": 40, "property_variants": 30, "accepted_name": 24})
    # 2 herb -> disorder links (+ literature evidence tier)
    hi = rd("herb_indication"); hi = hi[hi.disease_id != ""].drop_duplicates(["herb_id", "disease_id"])
    hi = hi.merge(H[["herb_id", "name_sa_iast", "accepted_name"]], on="herb_id", how="left")
    if (P / "herb_indication_evidence.csv").exists():
        ev = rd("herb_indication_evidence")[["herb_id", "disease_id", "evidence_tier", "n_pair", "n_clinical"]]
        hi = hi.merge(ev, on=["herb_id", "disease_id"], how="left")
    hi["review_priority"] = hi.get("evidence_tier", pd.Series("", index=hi.index)).map(
        {"no_literature": 1, "sparse": 2, "literature_supported": 3, "clinical_evidence": 4}).fillna(5).astype(int)
    keep = [c for c in ["herb_id", "name_sa_iast", "accepted_name", "disease_id", "disease_term_iast", "disease_name_en",
                        "indication_raw", "match_method", "evidence_tier", "n_pair", "n_clinical", "review_priority"] if c in hi]
    sheet(wb, "herb_disorder_links", hi.sort_values(["review_priority", "herb_id"])[keep], "herb_id",
          {"disease_name_en": 26, "accepted_name": 22})
    # 3 therapy -> disorder (rule-based, non-generic)
    if (P / "therapy_disease.csv").exists():
        td = rd("therapy_disease")
        td = td[td.relation.isin(["site_specific_procedure", "disorder_protocol", "category_principle"])]
        D = rd("diseases").set_index("disease_id")
        td = td[td.disease_id.map(D.depth).fillna(9) <= 3]
        sheet(wb, "therapy_disorder_links", td[["disease_id", "disease_term_iast", "therapy_id", "therapy_term_iast",
              "therapy_term_en", "relation", "reference", "note"]], "disease_id", {"reference": 40, "note": 30, "therapy_term_en": 28})
    # 4 Ayurveda -> biomedicine correspondences
    bq = pd.read_csv(ROOT / "curation/disorder_biomedical_queries.csv", keep_default_na=False)
    sheet(wb, "biomedical_map", bq[["disease_id", "term_iast", "biomedical_concept_en", "correspondence", "note"]], "disease_id",
          {"biomedical_concept_en": 40, "note": 30})
    # 5 classical formulations
    F = rd("formulations")
    sheet(wb, "formulations", F[["form_id", "name_sa_iast", "name_en", "dosage_form", "classical_reference", "ingredients_sa_iast",
          "indications_sa_iast", "contains_metal_or_toxic", "safety_note"]], "form_id",
          {"ingredients_sa_iast": 40, "classical_reference": 30, "indications_sa_iast": 30})
    # 6 Hindi translations: flagged items + a random calibration sample
    rows = []
    for tab, idc, en, hi_col in [("terminology", "term_uid", "definition_en", "definition_hi"), ("symptoms", "symptom_id", "gloss_en", "gloss_hi"),
                                 ("herbs", "herb_id", "description_en", "description_hi"), ("terminology", "term_uid", "term_en", "term_en_hi")]:
        T = rd(tab)
        if hi_col not in T:
            continue
        flags = T[f"{hi_col}_qe_flags"] if f"{hi_col}_qe_flags" in T else pd.Series("", index=T.index)
        fl = T[flags != ""].sample(min(60, int((flags != "").sum())), random_state=1)
        ok = T[(flags == "") & (T[hi_col] != "")].sample(min(40, int(((flags == "") & (T[hi_col] != "")).sum())), random_state=1)
        for part, lab in ((fl, "flagged by QE"), (ok, "random unflagged (calibration)")):
            for r in part.itertuples():
                rows.append(dict(table=tab, record_id=getattr(r, idc), field=hi_col, english=getattr(r, en)[:600],
                                 hindi=getattr(r, hi_col)[:600], qe_flags=flags.loc[r.Index], sample=lab))
    sheet(wb, "hindi_translations", pd.DataFrame(rows), "record_id", {"english": 50, "hindi": 50, "qe_flags": 18})
    # 7 case-report extractions
    if (P / "case_reports.csv").exists():
        C = rd("case_reports")
        C = C[C.dx_disease_ids != ""].sample(min(150, int((C.dx_disease_ids != "").sum())), random_state=7)
        C["article_url"] = "https://europepmc.org/article/" + C.pmcid.where(C.pmcid != "", "MED/" + C.pmid.astype(str)).map(
            lambda x: x if x.startswith("MED/") else f"PMC/{x}")
        sheet(wb, "case_reports", C[["case_id", "article_url", "title", "case_kind", "dx_term_iast", "presenting_symptom_phrases",
              "herb_ids", "form_ids", "procedures", "modern_assessments"]], "case_id", {"title": 50, "presenting_symptom_phrases": 40})
    f = OUT / "AyurKB_expert_review.xlsx"
    wb.save(f)
    (OUT / "returned").mkdir(exist_ok=True)
    print(f"wrote {f} with sheets {wb.sheetnames}")

def fleiss_kappa(table):
    """table: items x categories counts (each row sums to the number of raters of that item, >= 2)"""
    import numpy as np
    T = np.asarray(table, dtype=float)
    T = T[T.sum(1) >= 2]
    if len(T) == 0:
        return None
    n = T.sum(1)
    p = T.sum(0) / T.sum()
    Pi = ((T ** 2).sum(1) - n) / (n * (n - 1))
    Pbar, Pe = Pi.mean(), (p ** 2).sum()
    return float((Pbar - Pe) / (1 - Pe)) if Pe < 1 else None

def merge():
    files = sorted((OUT / "returned").glob("*.xlsx"))
    rows = []
    for f in files:
        wb = load_workbook(f, read_only=True, data_only=True)
        reviewer = str(wb["README"]["B3"].value or f.stem).strip()
        for name in wb.sheetnames:
            if name == "README":
                continue
            ws = wb[name]
            it = ws.iter_rows(values_only=True)
            hdr = list(next(it))
            if "verdict" not in hdr:
                continue
            iv = {c: hdr.index(c) for c in REVIEW_COLS}
            for r in it:
                if not r or not r[iv["verdict"]]:
                    continue
                key = "|".join(str(r[i]) for i in range(min(2, len(hdr))) if r[i] is not None)
                if name in ("herb_disorder_links",):
                    key = f"{r[hdr.index('herb_id')]}|{r[hdr.index('disease_id')]}"
                elif name == "therapy_disorder_links":
                    key = f"{r[hdr.index('disease_id')]}|{r[hdr.index('therapy_id')]}"
                elif name == "hindi_translations":
                    key = f"{r[hdr.index('table')]}|{r[hdr.index('record_id')]}|{r[hdr.index('field')]}"
                rows.append(dict(sheet=name, item_key=key, reviewer_id=reviewer, verdict=r[iv["verdict"]],
                                 corrected_value=r[iv["corrected_value"]] or "", reference=r[iv["classical_or_literature_reference"]] or "",
                                 comment=r[iv["comment"]] or "", source_file=f.name))
    R = pd.DataFrame(rows, columns=["sheet", "item_key", "reviewer_id", "verdict", "corrected_value", "reference", "comment", "source_file"])
    R.to_csv(ROOT / "curation/expert_reviews.csv", index=False)
    agree = {}
    for name, g in R.groupby("sheet"):
        cats = VERDICTS.get(name, sorted(g.verdict.unique()))
        tab = []
        for _, gi in g.groupby("item_key"):
            c = Counter(gi.verdict)
            if sum(c.values()) >= 2:
                tab.append([c.get(k, 0) for k in cats])
        agree[name] = {"items_reviewed": int(g.item_key.nunique()), "reviewers": int(g.reviewer_id.nunique()),
                       "items_with_>=2_reviewers": len(tab), "fleiss_kappa": fleiss_kappa(tab) if tab else None,
                       "verdicts": g.verdict.value_counts().to_dict()}
    (ROOT / "reports/expert_review_agreement.json").write_text(json.dumps(agree, indent=2))
    print(f"merged {len(R)} verdicts from {len(files)} workbook(s)"); print(json.dumps(agree, indent=1))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true"); ap.add_argument("--merge", action="store_true")
    a = ap.parse_args()
    if a.build or not a.merge:
        build()
    if a.merge:
        merge()
