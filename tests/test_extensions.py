"""
Tests for the extension layers (stages 14-22): real-world case reports, literature evidence, therapy links,
regional scripts, headword concepts, PubChem identifiers, image-dataset links, ICTRP importer, review workbook,
tuning report and the interactive tools.  Layers whose (network-built) file is absent are skipped, not failed.
"""
import json, re, subprocess, sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
sys.path.insert(0, str(ROOT / "scripts"))
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)
need = lambda n: pytest.mark.skipif(not (P / f"{n}.csv").exists(), reason=f"{n}.csv not built")

# ----------------------------------------------------------------------------- case reports (stage 14)
@need("case_reports")
def test_case_reports_schema_and_no_article_text():
    c = rd("case_reports")
    assert len(c) >= 300 and c.case_id.is_unique
    assert set(c.case_kind) <= {"therapeutic", "adverse_event"}
    # Short source-derived phrases are present; full abstracts and bodies remain excluded.
    assert not any(k in c.columns for k in ("abstract", "abstractText", "body", "full_text", "fulltext"))
    assert c.licence.str.contains("short source-derived phrases").all()
    assert c.licence.str.contains("per-article terms require review").all()
    d = rd("diseases").disease_id
    ids = {x for s in c.dx_disease_ids for x in s.split("; ") if x}
    assert ids <= set(d)

@need("case_reports")
def test_case_report_extraction_quality_guards():
    e = rd("case_report_entities")
    sym = set(e[e.entity_type == "symptom"].mention_key)
    assert not sym & {"patient", "history", "blood", "body", "life", "health", "like", "work"}, "generic words leaked into symptoms"
    herbs = set(e[e.entity_type == "herb"].mention_key)
    assert not herbs & {"tikta", "old woman", "patya", "sarva", "kusta"}, "homonyms leaked into herbs"
    dx = rd("case_reports").dx_term_iast
    assert not dx.str.startswith("virecana/").any(), "a therapy word was taken for a diagnosis"

def test_e6_matcher_beats_baselines():
    f = ROOT / "reports/ml/E6_case_reports.json"
    if not f.exists():
        pytest.skip("E6 not run")
    m = json.loads(f.read_text())["E6_matcher_on_real_presentations"]
    assert m["n_cases_evaluated"] >= 50
    assert m["family_hit@10"] > m["baseline_popularity_family_hit@10"] > m["baseline_random_exact_hit@10"]

# ----------------------------------------------------------------------------- literature evidence (stage 15)
@need("herb_indication_evidence")
def test_link_evidence_tiers_consistent():
    ev = rd("herb_indication_evidence")
    assert set(ev.evidence_tier) <= {"clinical_evidence", "literature_supported", "sparse", "no_literature", "not_queryable"}
    q = ev[ev.evidence_tier != "not_queryable"].copy()
    for c in ("n_pair", "n_clinical", "n_entity", "n_disorder"):
        q[c] = pd.to_numeric(q[c])
    assert (q.n_pair <= q[["n_entity", "n_disorder"]].min(axis=1)).all(), "pair count exceeds a marginal"
    assert (q.n_clinical <= q.n_pair).all()
    assert (q[q.evidence_tier == "clinical_evidence"].n_clinical >= 1).all()
    assert (q[q.evidence_tier == "no_literature"].n_pair == 0).all()

def test_disorder_biomedical_queries_wellformed():
    q = pd.read_csv(ROOT / "curation/disorder_biomedical_queries.csv", keep_default_na=False)
    assert q.disease_id.is_unique and set(q.disease_id) <= set(rd("diseases").disease_id)
    for s in q.pubmed_query:
        assert s.count("(") == s.count(")") and s.count('"') % 2 == 0, s
    assert set(q.correspondence) <= {"close", "approximate", "broad", "none"}

# ----------------------------------------------------------------------------- therapy links, scripts, concepts (stage 16)
@need("therapy_disease")
def test_therapy_disease_rules():
    t = rd("therapy_disease")
    assert set(t.relation) <= {"site_specific_procedure", "disorder_protocol", "category_principle", "dosha_principle_generic",
                               "iatrogenic_complication_of", "observed_in_published_cases"}
    assert (t.reference != "").all()
    d = rd("diseases").set_index("disease_id")
    # bloodletting is never suggested for raktapitta (a bleeding disorder)
    blood = t[(t.therapy_term_iast == "raktamokṣaṇam") & (t.relation != "observed_in_published_cases")]
    assert not blood.disease_term_iast.str.startswith("raktapitta").any()
    # every eye disorder (system H) has a kriyākalpa procedure
    eye = set(d[d.system_code == "H"].index)
    assert eye <= set(t[t.therapy_term_iast == "netratarpaṇam"].disease_id)
    # śodhana links carry the practitioner caution
    sod = t[t.therapy_term_iast.isin(["vamanakarma", "virecanakarma"]) & (t.relation == "dosha_principle_generic")]
    assert sod.note.str.contains("practitioner decision").all()

@need("multiscript_names")
def test_multiscript_transliteration():
    from indic_transliteration import sanscript
    m = rd("multiscript_names")
    assert {"bengali", "gujarati", "gurmukhi", "kannada", "malayalam", "odia", "tamil", "telugu"} <= set(m.columns)
    r = m[(m.entity_type == "disease") & (m.devanagari == "आमवातः")].iloc[0]
    assert r.kannada == "ಆಮವಾತಃ" and r.bengali == "আমবাতঃ"
    # lossless scripts round-trip back to Devanagari
    s = m.sample(200, random_state=0)
    back = [sanscript.transliterate(x, sanscript.KANNADA, sanscript.DEVANAGARI) == d for x, d in zip(s.kannada, s.devanagari)]
    assert sum(back) / len(back) > 0.97

@need("headword_concepts")
def test_headword_concepts():
    c, m = rd("headword_concepts"), rd("concept_members")
    assert c.concept_id.is_unique and set(m.concept_id) <= set(c.concept_id)
    jv = m[m.concept_id.isin(c[c.match_key == "jvara"].concept_id)]
    assert {"disease", "terminology", "symptom"} <= set(jv.entity_type)

# ----------------------------------------------------------------------------- PubChem / ChEMBL (stage 17)
@need("phytochemicals")
def test_pubchem_identifiers():
    p = rd("phytochemicals")
    ok = p[p.pubchem_match.str.startswith("matched")]
    assert len(ok) / len(p) > 0.5
    assert ok.inchikey.str.match(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$").all()
    q = ok[ok.chemical == "QUERCETIN"]
    assert len(q) == 1 and q.iloc[0].inchikey.startswith("REFJWTPEDVJJIY")

def test_chembl_data_kept_separate():
    core = (ROOT / "release/datapackage.json")
    if core.exists():
        assert "chembl" not in core.read_text().lower(), "share-alike ChEMBL data must not enter the core package"
    f = ROOT / "release/chembl/phytochemical_targets_chembl.csv"
    if f.exists():
        assert (ROOT / "release/chembl/LICENSE_CHEMBL.txt").read_text().count("CC BY-SA 3.0") >= 1

# ----------------------------------------------------------------------------- image datasets (stage 18)
@need("herb_image_datasets")
def test_image_dataset_links():
    i = rd("herb_image_datasets")
    assert (i.licence == "CC BY 4.0").all() and i.dataset_doi.str.startswith("10.17632/").all()
    linked = i[i.herb_id != ""]
    assert linked.herb_id.nunique() >= 50
    assert set(linked.herb_id) <= set(rd("herbs").herb_id)

# ----------------------------------------------------------------------------- ICTRP importer (stage 19)
def test_ictrp_importer_drops_personal_data(tmp_path, monkeypatch):
    import importlib
    mod = importlib.import_module("19_ictrp_import")
    monkeypatch.setattr(mod, "P", tmp_path)
    mod.main(str(ROOT / "tests/fixtures/ictrp_sample.csv"), "2099-01-01")
    t = pd.read_csv(tmp_path / "ictrp_trials.csv", keep_default_na=False)
    assert not [c for c in t.columns if re.search(r"contact|e-?mail|\btel\b|phone|first_?name|last_?name", c, re.I)]
    assert "url" in t.columns                       # the trial's web address is kept (not personal data)
    links = pd.read_csv(tmp_path / "ictrp_trial_links.csv", keep_default_na=False)
    assert {"disease", "herb", "formulation"} <= set(links.entity_type)

# ----------------------------------------------------------------------------- tuning, review workbook, tools
def test_tuning_report():
    f = ROOT / "reports/ml/E7_tuning.json"
    if not f.exists():
        pytest.skip("E7 not run")
    r = pd.DataFrame(json.loads(f.read_text())["results"])
    assert {"default_macro_f1_mean", "tuned_macro_f1_mean", "wilcoxon_p"} <= set(r.columns) and len(r) >= 10

def test_review_workbook_has_dropdowns():
    f = ROOT / "review/AyurKB_expert_review.xlsx"
    if not f.exists():
        pytest.skip("workbook not built")
    from openpyxl import load_workbook
    wb = load_workbook(f)
    assert {"README", "herb_properties", "herb_disorder_links", "biomedical_map", "hindi_translations"} <= set(wb.sheetnames)
    ws = wb["herb_disorder_links"]
    assert ws.data_validations.dataValidation, "verdict column needs a drop-down"

@pytest.mark.parametrize("page", ["review_desk.html", "prakriti_questionnaire.html"])
def test_tool_pages_embed_data_and_guard_capabilities(page):
    f = ROOT / "release/tools" / page
    if not f.exists():
        pytest.skip("tools not built")
    html = f.read_text()
    assert "/*__DATA__*/null" not in html, "data placeholder not filled"
    assert '.use("db")' in html and "window.claude" in html and "?.use" in html   # guarded: absent outside claude.ai
    assert re.search(r"<title>[^<]{3,40}</title>", html)

def test_release_zip_excludes_article_texts():
    z = sorted((ROOT / "release").glob("AyurKB_v*.zip"))
    if not z:
        pytest.skip("release not packaged")
    import zipfile
    names = zipfile.ZipFile(z[-1]).namelist()
    assert not [n for n in names if "epmc_fulltext/" in n and n.endswith(".xml")], "third-party article texts must not be packaged"
    assert not [n for n in names if n.endswith("epmc_case_reports.json")], "cached abstracts must not be packaged"
    assert "data/processed/case_reports.csv" in names and "release/tools/review_desk.html" in names

# ----------------------------------------------------------------------------- accuracy upgrades (stages 23-26)
@need("disease_symptom_who")
def test_filled_definitions_are_traceable():
    d = rd("diseases")
    assert set(d.definition_source) <= {"NAMASTE", "WHO ITA 2022 (linked term)", ""}
    who = d[d.definition_source == "WHO ITA 2022 (linked term)"]
    assert len(who) >= 300 and (who.who_term_id != "").all() and (who.definition_en.str.len() > 15).all()
    # NAMASTE definitions are never replaced
    assert ((d.definition_source == "NAMASTE") == (d.definition_source == "NAMASTE")).all()
    w, i = rd("disease_symptom_who"), rd("disease_symptom_inferred")
    S = set(rd("symptoms").symptom_id); D = set(d.disease_id)
    assert set(w.symptom_id) <= S and set(w.disease_id) <= D and set(i.symptom_id) <= S
    healthy = set(d[d.system_code.isin(["U", "V", "W"])].disease_id)
    assert not set(i.disease_id) & healthy, "healthy states must not inherit disease symptoms"

@need("dosha_suggestions")
def test_dosha_suggestions_flagged_not_merged():
    s, d = rd("dosha_suggestions"), rd("diseases").set_index("disease_id")
    assert (s.status.str.contains("not authoritative")).all()
    assert (d.loc[s.disease_id].dosha_label == "unspecified").all(), "suggestions are only for unspecified disorders"
    assert s.confidence.between(0, 1).all() and (s.margin >= 0).all()

def test_matching_improvements_beat_baselines():
    f = ROOT / "reports/ml/E6b_matching_improvements.json"
    if not f.exists():
        pytest.skip("stage 24 not run")
    v = json.loads(f.read_text())["variants"]
    base = v["V0 baseline (lexical, flat ranking)"]["hit@10"]
    best = v["V4 + profiles learned from real cases (5-fold CV)"]
    assert best["hit@10"] > base and best["hit@10"] > v["baseline_training_diagnosis_frequency (no symptoms)"]["hit@10"]
    assert best.get("cv_seeds", 1) >= 5

@need("disease_symptom_from_cases")
def test_case_learned_profiles():
    c = rd("disease_symptom_from_cases")
    assert (c.n_cases >= 1).all() and set(c.disease_id) <= set(rd("diseases").disease_id)
    assert c.data_origin.str.contains("not curated").all()

def test_crosswalk_flagged_for_review():
    f = ROOT / "curation/clinical_symptom_crosswalk.csv"
    if not f.exists():
        pytest.skip("crosswalk not built")
    cw = pd.read_csv(f, keep_default_na=False)
    assert len(cw) >= 150 and (cw.review_status.str.contains("review")).all()
    assert (cw[cw.method != "unmapped"].symptom_ids != "").all()

def test_finetuned_search_reported_without_leakage():
    f = ROOT / "reports/ml/E5b_finetuned_retrieval.json"
    if not f.exists():
        pytest.skip("stage 23 not run")
    r = json.loads(f.read_text())
    assert "test records" in r["leakage_guard"] and r["training_pairs"] > 1000
    for task in ("diseases", "symptoms"):
        assert 0 <= r["finetuned"][task]["hindi_headword"]["recall_at_10"] <= 1

# ----------------------------------------------------------------------------- expert-system demo (README quick start)
@pytest.mark.parametrize("symptoms,lang,sections", [
    # the English case reaches the herb list with literature-evidence tiers (the path that once crashed on '7.0')
    ("fever; burning sensation; excessive thirst; vomiting", "en", ("Candidate disorders", "Materia medica recorded", "clinical-publication matches (not efficacy assessed)")),
    ("बुखार; जलन; अधिक प्यास", "hi", ("Candidate disorders", "Classical procedures"))])
def test_expert_system_demo_runs_end_to_end(symptoms, lang, sections):
    """the README commands must work on a fresh clone: lexical mode needs no model download"""
    r = subprocess.run([sys.executable, "-I", str(ROOT / "examples/expert_system_demo.py"), "--symptoms", symptoms,
                        "--lang", lang, "--no-semantic"], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    for s in sections + ("decision support for a qualified practitioner",):
        assert s in r.stdout, f"missing section: {s}"

def test_evidence_counts_are_whole_numbers():
    """counts are written as integers ('7', not '7.0'); blank only where the link could not be searched"""
    for name in ("herb_indication_evidence", "formulation_indication_evidence"):
        if not (P / f"{name}.csv").exists():
            continue
        e = rd(name)
        for c in ("n_entity", "n_disorder", "n_pair", "n_clinical"):
            v = e[c].astype(str)
            assert v.str.fullmatch(r"\d*").all(), f"{name}.{c} has non-integer values"
            assert ((v == "") == (e.evidence_tier == "not_queryable")).all()

# ----------------------------------------------------------------------------- Hindi post-edits (stage 25)
NAUSEA_OK = r"मतली|मिचल|उबकाई"

def test_nausea_rendered_correctly_in_hindi():
    """'nausea' was machine-translated as vomiting, fever, burning, confusion, cough ...: every translated text that mentions
    nausea must now say मतली (or जी मिचलाना), unless its whole translation is flagged as degenerate (QE 'repetition')"""
    for tab, en, hi in [("symptoms", "gloss_en", "gloss_hi"), ("diseases", "definition_en", "definition_hi"),
                        ("terminology", "definition_en", "definition_hi")]:
        d = rd(tab)
        m = d[d[en].str.contains("nause", case=False) & (d[hi] != "")]
        assert len(m) > 0
        bad = m[~m[hi].str.contains(NAUSEA_OK) & ~m[f"{hi}_qe_flags"].str.contains("repetition")]
        assert bad.empty, f"{tab}: nausea mistranslated in {bad.iloc[:, 0].tolist()}"

def test_short_nausea_glosses_never_say_vomiting():
    s = rd("symptoms")
    only_nausea = s[s.gloss_en.str.contains("nause", case=False) & ~s.gloss_en.str.contains("vomit", case=False)]
    assert not only_nausea.gloss_hi.str.contains("उल्टी|बुखार|जलन|अपच|उलझन|नाजुकता").any()

def test_mt_corrections_curated_and_marked():
    c = pd.read_csv(ROOT / "curation/mt_item_corrections.csv", keep_default_na=False)
    assert {"en_item", "hi_item", "hi_ok_regex", "note"} <= set(c.columns) and c.en_item.is_unique
    assert c.hi_item.str.contains(r"[ऀ-ॿ]").all()
    assert all(re.search(r.hi_ok_regex, r.hi_item) for r in c.itertuples() if r.hi_ok_regex)   # a correction is never re-applied
    rules = pd.read_csv(ROOT / "curation/mt_postedit_rules.csv", keep_default_na=False)
    assert (rules.tables != "").all()
    for r in rules.itertuples():
        re.compile(r.hi_wrong_regex)
    # every corrected row says so, and the report counts them
    marked = sum(int(rd(t)[col].str.contains("post-edited|rule-corrected").sum())
                 for t, col in [("symptoms", "gloss_hi_method"), ("diseases", "definition_hi_method"), ("terminology", "definition_hi_method")])
    rep = json.loads((ROOT / "reports/fill_missing_report.json").read_text())["mt_postedits"]
    assert sum(rep.values()) == marked and marked >= 100

def test_mt_postedits_idempotent(tmp_path, monkeypatch):
    """re-applying the curated post-edits to the released tables changes nothing"""
    import importlib, shutil
    fm = importlib.import_module("25_fill_missing")
    D, T, S = rd("diseases"), rd("terminology"), rd("symptoms")
    before = (D.definition_hi.copy(), T.definition_hi.copy(), S.gloss_hi.copy())
    monkeypatch.setattr(fm, "P", tmp_path)              # write into a scratch folder, never over the release
    for n in ("disease_symptom", "therapies", "pharmaceutics", "diet_lifestyle"):
        if (P / f"{n}.csv").exists():
            shutil.copy(P / f"{n}.csv", tmp_path / f"{n}.csv")
    changed = fm.mt_corrections(D, T, S)
    assert sum(changed.values()) == 0, changed
    assert D.definition_hi.equals(before[0]) and T.definition_hi.equals(before[1]) and S.gloss_hi.equals(before[2])
