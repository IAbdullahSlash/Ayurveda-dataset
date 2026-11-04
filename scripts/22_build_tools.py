#!/usr/bin/env python3
"""
Stage 22 - Build the two interactive tools (published as claude.ai Artifacts with runtime capabilities):
  release/tools/review_desk.html            expert review of herb -> disorder and procedure -> disorder links
                                            (verdicts stored per reviewer in the artifact's database)
  release/tools/prakriti_questionnaire.html bilingual Prakṛti questionnaire with consent screen, classical scoring
                                            (same rule as experiment E4) and optional anonymous saving by the study team
Both pages degrade to read-only / local use when opened outside claude.ai.
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P, OUT = ROOT / "data/processed", ROOT / "release/tools"
OUT.mkdir(parents=True, exist_ok=True)
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)

def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None

def review_items():
    H, D, T = rd("herbs").set_index("herb_id"), rd("diseases").set_index("disease_id"), rd("therapies").set_index("therapy_id")
    hi = rd("herb_indication"); hi = hi[hi.disease_id != ""].drop_duplicates(["herb_id", "disease_id"])
    ev = rd("herb_indication_evidence").set_index(["herb_id", "disease_id"]) if (P / "herb_indication_evidence.csv").exists() else None
    items = []
    for r in hi.itertuples():
        h, d = H.loc[r.herb_id], D.loc[r.disease_id]
        e = ev.loc[(r.herb_id, r.disease_id)] if ev is not None and (r.herb_id, r.disease_id) in ev.index else None
        tier = e.evidence_tier if e is not None else "not_queryable"
        # active learning: possible name-mapping errors first, then links with no / sparse literature
        pr, why = ({"no_literature": 1, "sparse": 2, "literature_supported": 3, "clinical_evidence": 4}.get(tier, 3), "")
        if r.match_method == "fuzzy_skeleton":
            pr, why = 0, "possible name-mapping error"
        elif tier == "no_literature":
            why = "classical claim with no literature found"
        items.append(dict(pr=pr, why=why, k=f"{r.herb_id}__{r.disease_id}", s="h", b=h.accepted_name, hd=h.name_sa_deva, hi=h.name_sa_iast or h.name_ascii,
                          hl=f"{h.name_sa_iast or h.name_ascii} ({h.accepted_name})", dd=d.term_deva, di=d.term_iast, de=d.name_en_who or d.name_en,
                          src=f"Amidha indication '{r.indication_raw}' ({r.match_method.replace('_', ' ')})", tier=tier,
                          np=num(e.n_pair) if e is not None else None, nc=num(e.n_clinical) if e is not None else None,
                          pm=[x for x in (e.clinical_pmids or e.top_pmids).split(";") if x] if e is not None else [], ref=""))
    td = rd("therapy_disease")
    td = td[(td.relation == "disorder_protocol") & (td.disease_id.map(D.depth) <= 3)]   # subtypes inherit the parent's verdict
    for r in td.itertuples():
        d, t = D.loc[r.disease_id], T.loc[r.therapy_id]
        items.append(dict(pr=3, why="", k=f"{r.disease_id}__{r.therapy_id}", s="t", b=t.term_en, hd=t.term_sa_deva_primary, hi=t.term_sa_iast_primary,
                          hl=f"{t.term_sa_iast_primary} ({t.term_en})", dd=d.term_deva, di=d.term_iast, de=d.name_en_who or d.name_en,
                          src="rule-based link (classical protocol)", tier="classical", np=None, nc=None, pm=[], ref=r.reference))
    # practice-derived candidates (stage 14): medicine x diagnosis pairs seen in >= 2 case reports but missing from the KB
    if (P / "case_report_links.csv").exists():
        cl = rd("case_report_links")
        cl = cl[(cl.in_kb_for_disorder_family.astype(str) == "False") & (cl.n_cases >= 2)]
        F = rd("formulations").set_index("form_id")
        for r in cl.itertuples():
            d = D.loc[r.disease_id]
            if r.entity_type == "herb":
                h = H.loc[r.entity_id]; deva, iast, bot = h.name_sa_deva, h.name_sa_iast or h.name_ascii, h.accepted_name
            else:
                fo = F.loc[r.entity_id]; deva, iast, bot = fo.name_sa_deva, fo.name_sa_iast, fo.name_en
            items.append(dict(pr=0.8, why=f"seen in {r.n_cases} case reports, not yet in the KB", k=f"{r.entity_id}__{r.disease_id}__case", s="c",
                              b=bot, hd=deva, hi=iast, hl=f"{iast} ({bot})", dd=d.term_deva, di=d.term_iast, de=d.name_en_who or d.name_en,
                              src=f"{r.entity_type} used for this diagnosis in {r.n_cases} published case reports", tier="practice",
                              np=None, nc=None, pm=[], cs=[c.replace("CASE-", "") for c in r.case_ids.split(";") if c][:5], ref=""))
    # doṣa suggestions (stage 25): the most uncertain ones teach the model most; the most confident are quick to confirm
    if (P / "dosha_suggestions.csv").exists():
        sg = rd("dosha_suggestions")
        sg = pd.concat([sg.nsmallest(300, "margin"), sg.nlargest(300, "confidence")]).drop_duplicates("disease_id")
        for r in sg.itertuples():
            d = D.loc[r.disease_id]
            unsure = r.margin < 0.2
            items.append(dict(pr=0.5 if unsure else 2.5, why="model unsure" if unsure else "model confident: quick check",
                              k=f"{r.disease_id}__dosha", s="d", b="", hd=r.suggested_dosha.replace("+", " + "), hi=f"doṣa: {r.suggested_dosha}",
                              hl=f"doṣa {r.suggested_dosha}", dd=d.term_deva, di=d.term_iast, de=d.name_en_who or d.name_en,
                              src=f"model suggestion (confidence {r.confidence:.2f}; second choice {r.second_choice})",
                              tier="suggestion", np=None, nc=None, pm=[], ref=d.definition_en[:220]))
    return items

def prakriti_items():
    q = pd.read_csv(ROOT / "curation/prakriti_questionnaire.csv", keep_default_na=False)
    return [dict(id=r.item_id, domain=r.domain, q={"en": r.question_en, "hi": r.question_hi},
                 opts={d: {"en": getattr(r, f"option_{n}_en"), "hi": getattr(r, f"option_{n}_hi")} for d, n in (("V", "vata"), ("P", "pitta"), ("K", "kapha"))})
            for r in q.itertuples()]

def build(template, data, out):
    html = (ROOT / "docs" / template).read_text(encoding="utf-8")
    assert "/*__DATA__*/null" in html
    html = html.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    (OUT / out).write_text(html, encoding="utf-8")
    return len(html)

def main():
    gen = pd.Timestamp.now().strftime("%d %b %Y")
    items = review_items()
    n1 = build("review_desk_template.html", {"generated": gen, "items": items}, "review_desk.html")
    n2 = build("prakriti_template.html", {"generated": gen, "version": "1.0", "items": prakriti_items()}, "prakriti_questionnaire.html")
    print(f"review_desk.html: {len(items)} links ({n1 / 1024:.0f} KB); prakriti_questionnaire.html ({n2 / 1024:.0f} KB)")

if __name__ == "__main__":
    main()
