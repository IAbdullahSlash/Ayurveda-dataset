"""
Test-suite for AyurKB.  Run:  python3 -m pytest -q tests/
Covers: transliteration correctness, schema/keys/referential integrity, text hygiene, domain rules,
bilingual coverage, safety flags, provenance/licences, ML artefacts.
"""
import json, re, sys, unicodedata
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from lib.indic import phonetic_to_iast, iast_to_deva, deva_to_iast, hindi_usage_form, iso_to_iast, fix_text
from lib.keys import skeleton

P = ROOT / "data/processed"
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)

# ----------------------------------------------------------------------------- transliteration units
@pytest.mark.parametrize("ph,iast", [
    ("vAtavyAdhiH", "vātavyādhiḥ"), ("doShavaiShamyam", "doṣavaiṣamyam"), ("vAtasa~jcayaH", "vātasañcayaḥ"),
    ("a~ggamardaH", "aṅgamardaḥ"), ("kaPajapalitaH", "kaphajapalitaḥ"), ("kRucCrasAdhyavAtavyAdhiH", "kṛcchrasādhyavātavyādhiḥ"),
    ("jRumBA", "jṛmbhā"), ("kaNThaH", "kaṇṭhaḥ"), ("dravyaguNa-vij~jAnam", "dravyaguṇa-vijñānam"), ("aMsaPalaka", "aṃsaphalaka")])
def test_phonetic_to_iast(ph, iast):
    assert phonetic_to_iast(ph) == iast

@pytest.mark.parametrize("iast,deva", [("vātavyādhiḥ", "वातव्याधिः"), ("aśvagandhā", "अश्वगन्धा"), ("haridrā", "हरिद्रा"),
                                       ("pañcakarma", "पञ्चकर्म"), ("kṛmiḥ", "कृमिः")])
def test_iast_to_devanagari(iast, deva):
    assert iast_to_deva(iast) == deva and deva_to_iast(deva) == iast

@pytest.mark.parametrize("deva,hi", [("व्याधिः", "व्याधि"), ("चूर्णम्", "चूर्ण"), ("अङ्गमर्दः", "अंगमर्द"), ("वातसञ्चयः", "वातसंचय")])
def test_hindi_usage_form(deva, hi):
    assert hindi_usage_form(deva) == hi

def test_iso_and_mojibake():
    assert iso_to_iast("dōṣa br̥hati") == "doṣa bṛhati"
    assert fix_text("cafÃ©   x") == "café x"

@pytest.mark.parametrize("a,b", [("kuṣṭham", "Kushta"), ("śvāsaḥ", "Shwasa"), ("jvaraḥ", "Jwara"), ("vātavyādhiḥ", "Vata Vyadhi")])
def test_skeleton_joins_romanisations(a, b):
    assert skeleton(a) == skeleton(b)

# ----------------------------------------------------------------------------- integrity
PK = {"terminology": "term_uid", "diseases": "disease_id", "symptoms": "symptom_id", "herbs": "herb_id",
      "herb_groups": "group_id", "diagnostic_methods": "dx_id", "formulations": "form_id", "sources": "source_id"}

@pytest.mark.parametrize("table,key", PK.items())
def test_primary_keys_unique(table, key):
    df = rd(table)
    assert len(df) > 0 and df[key].is_unique and (df[key] != "").all()

FK = [("disease_symptom", "disease_id", "diseases", "disease_id"), ("disease_symptom", "symptom_id", "symptoms", "symptom_id"),
      ("herb_indication", "disease_id", "diseases", "disease_id"), ("herb_indication", "herb_id", "herbs", "herb_id"),
      ("herb_group_members", "herb_id", "herbs", "herb_id"), ("herb_phytochemicals", "herb_id", "herbs", "herb_id"),
      ("formulation_ingredients", "herb_id", "herbs", "herb_id"), ("diseases", "parent_disease_id", "diseases", "disease_id")]

@pytest.mark.parametrize("t,c,rt,rc", FK)
def test_foreign_keys(t, c, rt, rc):
    a, b = rd(t), rd(rt)
    v = a[c][a[c] != ""]
    assert v.isin(set(b[rc])).all()

def test_disease_hierarchy_acyclic():
    d = rd("diseases"); par = dict(zip(d.disease_id, d.parent_disease_id))
    for node in d.disease_id:
        seen, cur = set(), node
        while cur:
            assert cur not in seen, f"cycle at {node}"
            seen.add(cur); cur = par.get(cur, "")

# ----------------------------------------------------------------------------- text hygiene
@pytest.mark.parametrize("table", ["diseases", "symptoms", "terminology", "herbs", "formulations", "diagnostic_methods"])
def test_no_mojibake(table):
    df = rd(table)
    bad = re.compile(r"Ã.|â€|�")
    for c in df.columns:
        if df[c].dtype == object:
            assert not df[c].astype(str).str.contains(bad).any(), f"{table}.{c}"

@pytest.mark.parametrize("table,col", [("diseases", "term_deva"), ("symptoms", "term_sa_deva"), ("herbs", "name_sa_deva"),
                                       ("terminology", "term_sa_deva_primary")])
def test_devanagari_columns_are_devanagari(table, col):
    s = rd(table)[col]
    s = s[s != ""]
    assert s.str.match(r"^[ऀ-ॿ\s\-,/;()\[\].:'0-9॥।ऽ‍‌]*$").mean() > 0.995

def test_iast_roundtrip():
    s = rd("diseases").term_iast
    ok = [deva_to_iast(iast_to_deva(x)) == unicodedata.normalize("NFC", x) for x in s if x]
    assert sum(ok) / len(ok) > 0.99

# ----------------------------------------------------------------------------- domain rules
def test_dosha_flags_consistent():
    d = rd("diseases")
    for lab, v, p, k in zip(d.dosha_label, d.dosha_vata, d.dosha_pitta, d.dosha_kapha):
        flags = [x for x, f in zip(["vata", "pitta", "kapha"], [v, p, k]) if str(f) == "True"]
        assert lab == ("+".join(flags) if flags else "unspecified")

def test_herb_properties_in_vocabulary():
    h = rd("herbs"); v = rd("controlled_vocabulary")
    for col, kind in [("rasa", "rasa"), ("virya", "virya"), ("vipaka", "vipaka")]:
        allowed = set(v[v.vocab_type == kind].source_key)
        vals = {x.strip() for s in h[col] for x in s.split(";") if x.strip()}
        assert vals <= allowed, f"{col}: {vals - allowed}"

def test_no_herb_both_pacifies_and_aggravates_same_dosha():
    h = rd("herbs")
    for p, a in zip(h.dosha_pacify, h.dosha_aggravate):
        assert not ({x.strip() for x in p.split(";") if x.strip()} & {x.strip() for x in a.split(";") if x.strip()})

def test_toxic_herbs_flagged():
    h = rd("herbs")
    names = set(h[h.safety_class != ""].accepted_name)
    for must in ["Aconitum ferox", "Strychnos nux-vomica", "Abrus precatorius", "Semecarpus anacardium"]:
        assert must in names
    tox = h[h.safety_class.str.contains("viṣa")]
    assert (tox.requires_shodhana == "yes").all()

def test_formulations_with_metals_have_safety_note():
    f = rd("formulations")
    m = f[f.contains_metal_or_toxic.str.startswith("yes")]
    assert len(m) >= 5 and (m.safety_note != "").all()
    assert (f.data_origin == "curated_requires_expert_verification").all()

def test_tm2_codes_wellformed():
    d = rd("diseases"); s = d.icd11_tm2_code[d.icd11_tm2_code != ""]
    assert s.str.match(r"^S[A-Z][0-9A-Z]{2}(\.[0-9A-Z]+)?$").all() and len(s) > 500

def test_taxonomy_resolution_rate():
    h = rd("herbs")
    assert (h.gbif_key != "").mean() > 0.95

# ----------------------------------------------------------------------------- bilingual & provenance
def test_bilingual_names():
    d, s, t = rd("diseases"), rd("symptoms"), rd("terminology")
    s_sa = s[s.term_sa_iast != ""]          # symptoms found only as English phrases get Hindi via gloss_hi
    assert (d.term_hi != "").mean() > 0.99 and (s_sa.term_hi != "").mean() > 0.99 and (t.term_hi != "").mean() > 0.97
    h = rd("herbs")
    any_hi = (h.name_hi_ayurvedic != "") | (h.name_hi_common != "") | (h.get("name_en_hi", "") != "")
    assert any_hi.mean() > 0.8

def test_machine_translations_labelled():
    d = rd("diseases")
    if "definition_hi" in d.columns:
        tr = d[d.definition_hi != ""]
        assert (tr.definition_hi_method != "").all()
        assert tr.definition_hi.str.contains(r"[ऀ-ॿ]").mean() > 0.95

def test_every_row_has_licence():
    for t in ["diseases", "symptoms", "terminology", "formulations", "diagnostic_methods"]:
        assert (rd(t).licence != "").all()
    src = set(rd("sources").source_id)
    for t, c in [("diseases", "source_id"), ("symptoms", "source_id"), ("terminology", "source_id")]:
        assert set(rd(t)[c]) <= src

# ----------------------------------------------------------------------------- ML artefacts
def test_ml_reports_beat_baselines():
    rep = ROOT / "reports/ml"
    files = list(rep.glob("*_cv_results.csv"))
    assert files, "run scripts/07_ml.py first"
    for f in files:
        r = pd.read_csv(f)
        if "Dummy (majority)" in set(r.model):
            dummy = r[r.model == "Dummy (majority)"].macro_f1_mean.max()
            assert r.macro_f1_mean.max() > dummy + 0.1, f.name

# ----------------------------------------------------------------------------- expert-system behaviour
def test_expert_system_ranks_pitta_disorders_for_pitta_complaints():
    import importlib.util
    spec = importlib.util.spec_from_file_location("demo", ROOT / "examples/expert_system_demo.py")
    demo = importlib.util.module_from_spec(spec); spec.loader.exec_module(demo)
    kb = demo.load()
    phrases = ["fever", "burning sensation", "excessive thirst", "vomiting"]
    hits = demo.match_symptoms(phrases, kb["symptoms"], "en")
    assert {h[0] for h in hits} == set(phrases)                      # every complaint mapped to the lexicon
    ranked = demo.rank_diseases(hits, kb, top=5)
    assert ranked and ranked[0][0] == len(phrases)                    # top candidate explains all complaints
    d = kb["diseases"].set_index("disease_id")
    assert any(str(d.loc[r[2]].dosha_pitta) == "True" for r in ranked)  # pitta disorders appear among candidates
