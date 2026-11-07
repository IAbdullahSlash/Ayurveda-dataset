#!/usr/bin/env python3
"""
Stage 04 - Integrate all sources into the AyurKB knowledge base (English / Hindi / Sanskrit).

Tables written to data/processed/ (CSV + Parquet):
  terminology            WHO + SAT standard terms (fundamentals, anatomy, diagnosis, pharmacology,
                         pharmaceutics, diet, treatment, prevention) with WHO<->SAT cross-links
  diseases               NAMASTE morbidity codes + hierarchy + ICD-11 TM2 codes + doṣa involvement
  symptoms               SAT-D signs & symptoms lexicon (+ symptoms only found in NAMASTE definitions)
  disease_symptom        edges parsed from NAMASTE clinical definitions
  herbs, herb_names      materia medica master (SAT + Amidha + mahākaṣāya + GBIF + Wikidata + safety)
  herb_indication        herb -> NAMASTE disease (from Amidha indications)
  herb_karma             herb -> pharmacological action
  herb_groups, herb_group_members   Caraka's 50 mahākaṣāya
  herb_phytochemicals, phytochemical_activities, herb_ethnobotany   (USDA Duke, modern layer)
  diagnostic_methods     classical + modern/computational diagnostics (curated, referenced)
  therapies, pharmaceutics, diet_lifestyle   (WHO + SAT subsets with categories)
  formulations, formulation_ingredients, formulation_indications   (curated classical remedies)
  sources                provenance and licences
"""
import json, re, sys
from collections import defaultdict
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.indic import fix_text, iast_to_deva, hindi_usage_form, ascii_fold, iso_to_iast, has_devanagari, deva_to_iast
from lib.keys import skeleton, skeleton_variants
from lib.indication_policy import apply_mapping_policy
from lib.safety import apply_safety_states

ROOT = Path(__file__).resolve().parents[1]
INT, OUT, CUR = ROOT / "data/interim", ROOT / "data/processed", ROOT / "curation"
OUT.mkdir(parents=True, exist_ok=True)

SOURCES = [
    ("S0", "Curated layer of this project (controlled vocabulary, glossary, diagnostic correspondences, safety, classical formulations)", "this repository /curation", "CC BY 4.0 (curation); classical texts are public domain", "curated"),
    ("S1", "NAMASTE - National Ayurveda Morbidity Codes, Ministry of Ayush, Govt. of India", "https://namaste.ayush.gov.in/ayurveda", "Govt. of India public standard; attribution; no explicit open licence", "authoritative"),
    ("S2", "NAMASTE - Standardised Ayurveda Terminologies (SAT A-J), Ministry of Ayush", "https://namaste.ayush.gov.in/sat_Ayurveda", "Govt. of India public standard; attribution; no explicit open licence", "authoritative"),
    ("S3", "WHO international standard terminologies on Ayurveda (2022), ISBN 9789240064935", "https://iris.who.int/handle/10665/365543", "CC BY-NC-SA 3.0 IGO", "authoritative"),
    ("S4", "USDA-ARS Dr. Duke's Phytochemical and Ethnobotanical Databases", "https://doi.org/10.15482/USDA.ADC/1239279", "CC0 1.0", "authoritative"),
    ("S5", "Amidha Ayurveda Herb Database v2.0 (S. Varshney)", "https://doi.org/10.5281/zenodo.20581467", "CC BY 4.0", "community_open"),
    ("S6", "Wikidata (plant taxon labels in hi/sa/en)", "https://query.wikidata.org", "CC0 1.0", "linked_open_data"),
    ("S7", "GBIF Backbone Taxonomy (species match API)", "https://www.gbif.org/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c", "CC BY 4.0", "linked_open_data"),
    ("S8", "NCBI PubMed E-utilities (literature counts)", "https://eutils.ncbi.nlm.nih.gov", "public domain (US Gov) - counts are facts", "modern_evidence"),
    ("S9", "ClinicalTrials.gov API v2 (registered trials)", "https://clinicaltrials.gov/data-api/api", "public domain (US Gov)", "modern_evidence"),
    ('S10', 'Europe PMC - Ayurveda case reports (REST API; open-access subset text-mined)', 'https://europepmc.org/RestfulWebService', 'bibliographic metadata, extracted identifiers and short source-derived phrases; full article caches excluded; per-article terms require review', 'real_world_evidence'),
    ('S11', 'PubChem (NCBI) compound identifiers and properties (PUG REST)', 'https://pubchem.ncbi.nlm.nih.gov', 'public domain (US Gov)', 'linked_open_data'),
    ('S12', 'Medicinal-plant image datasets on Mendeley Data (MED117; Medicinal Leaf Dataset; Indian Medicinal Leaves) - class labels only', 'https://data.mendeley.com/datasets/dtvbwrhznz/4', 'CC BY 4.0', 'linked_open_data'),
    ('S13', 'WHO International Clinical Trials Registry Platform (ICTRP, incl. CTRI) - optional manual export', 'https://trialsearch.who.int', 'WHO ICTRP terms: non-commercial, attribution, show processing date', 'modern_evidence'),
]
LIC = {s[0]: s[3] for s in SOURCES}

WHO_DOMAIN = {1: "fundamentals", 2: "fundamentals", 3: "anatomy_physiology", 4: "diagnosis", 5: "disease",
              6: "pharmacology", 7: "pharmaceutics", 8: "diet", 9: "treatment", 10: "prevention_lifestyle"}
SAT_DOMAIN = {"A": "fundamentals", "B": "anatomy_physiology", "C": "diagnosis", "D": "symptom", "F": "pharmacology",
              "G": "pharmaceutics", "H": "diet", "I": "treatment", "J": "prevention_lifestyle"}

def rd(name, d=INT):
    return pd.read_csv(d / name, keep_default_na=False, low_memory=False)

def save(df, name):
    df = df.copy()
    df.to_csv(OUT / f"{name}.csv", index=False)
    for c in df.columns:                      # parquet needs uniform column types
        if df[c].dtype == object:
            df[c] = df[c].astype(str)
    df.to_parquet(OUT / f"{name}.parquet", index=False)
    print(f"  {name:28s} {len(df):7d} rows x {df.shape[1]} cols")
    return df

def first_syn(s):
    return re.split(r"\s*[,/;]\s*", s.strip())[0].strip(" .()[]") if s else ""

def clean_binomial(s):
    s = re.sub(r"\s+", " ", str(s or "")).strip(" -.,")
    m = re.match(r"^([A-Z][a-z]+)\s+(×\s*)?([a-z][a-z\-]+)(?:\s+(subsp\.|var\.|f\.)\s+([a-z\-]+))?", s)
    if not m:
        return ""
    g, hyb, sp, rank, infra = m.groups()
    return f"{g} {'× ' if hyb else ''}{sp.strip('-')}" + (f" {rank} {infra}" if rank else "")

# =============================================================================== terminology
def build_terminology():
    who = rd("who_terms.csv")
    w = pd.DataFrame({
        "term_uid": "WHO:" + who.term_id, "source_id": "S3", "source_code": who.term_id,
        "domain": who.chapter.astype(int).map(WHO_DOMAIN), "section_code": "ITA-" + who.section_id,
        "section_title": who.section_title, "term_sa_iast": who.iast, "term_sa_iast_primary": who.iast.map(first_syn),
        "term_sa_deva": who.devanagari, "term_en": who.english_term, "definition_en": who.description,
        "parent_code": "ITA-" + who.section_id,
        "qa_flag": (~who.iast_annex_ok.astype(str).isin(["True", ""])).map({True: "iast_differs_from_annex", False: ""}),
    })
    w["term_sa_deva_primary"] = [first_syn(d) if d else iast_to_deva(i) for d, i in zip(w.term_sa_deva, w.term_sa_iast_primary)]
    sat = rd("namaste_sat.csv")
    sat = sat[sat.section != "D"].copy()
    par = sat.set_index(["section", "t_id"]).sat_id.to_dict()
    is_bot = sat.section.eq("F") & sat.short_definition.str.match(r"^\s*[A-Z][a-z]+ (×\s*)?[a-z]")
    s = pd.DataFrame({
        "term_uid": "SAT:" + sat.sat_id, "source_id": "S2", "source_code": sat.sat_id,
        "domain": sat.section.map(SAT_DOMAIN), "section_code": "SAT-" + sat.section, "section_title": sat.section_title,
        "term_sa_iast": sat.term_iast, "term_sa_iast_primary": sat.term_iast.map(first_syn), "term_sa_deva": sat.term_deva,
        "term_en": [ (ld.split(";")[0] if b else sd) for sd, ld, b in zip(sat.short_definition, sat.long_definition, is_bot)],
        "definition_en": [ (f"{sd}. {ld}" if b else ld) for sd, ld, b in zip(sat.short_definition, sat.long_definition, is_bot)],
        "parent_code": [par.get((sec, str(p)), "") for sec, p in zip(sat.section, sat.parent_id)],
        "qa_flag": sat.definition_has_unresolved_diacritics.astype(str).map({"True": "unresolved_diacritics_in_definition", "False": ""}),
    })
    s["term_sa_deva_primary"] = s.term_sa_iast_primary.map(iast_to_deva)
    t = pd.concat([w, s], ignore_index=True)
    t["term_hi"] = t.term_sa_deva_primary.map(hindi_usage_form)
    t["term_ascii"] = t.term_sa_iast_primary.map(ascii_fold)
    t["skel"] = t.term_sa_iast_primary.map(skeleton)
    # cross-link WHO <-> SAT concepts with the same Sanskrit headword (same broad domain family)
    by = defaultdict(list)
    for uid, k, src in zip(t.term_uid, t.skel, t.source_id):
        if k:
            by[k].append(uid)
    t["xref_same_headword"] = [";".join(u for u in by.get(k, []) if u.split(":")[0] != uid.split(":")[0])
                               for uid, k in zip(t.term_uid, t.skel)]
    t["licence"] = t.source_id.map(LIC)
    t["data_origin"] = "authoritative"
    cols = ["term_uid", "source_id", "source_code", "domain", "section_code", "section_title", "parent_code",
            "term_sa_iast", "term_sa_iast_primary", "term_sa_deva", "term_sa_deva_primary", "term_hi", "term_ascii",
            "term_en", "definition_en", "xref_same_headword", "qa_flag", "data_origin", "licence"]
    stats = dict(who_terms=int((t.source_id == "S3").sum()), sat_terms=int((t.source_id == "S2").sum()),
                 who_terms_with_sat_xref=round(float(((t.source_id == "S3") & (t.xref_same_headword != "")).sum()
                                                    / max(1, (t.source_id == "S3").sum())), 4))
    return t[cols], stats

# =============================================================================== diseases
TM2_RE = re.compile(r"\bS[A-Z][0-9A-Z]{2}(?:\.[0-9A-Z]+)?\b")
DOSHA_PAT = {
    "vata": re.compile(r"vāt|vāy|vatik|\bvata|vāta|vayu"),
    "pitta": re.compile(r"pitt|paitt"),
    "kapha": re.compile(r"kaph|śleṣm|ślaiṣm|slesm|ślēṣm"),
}
TRI_PAT = re.compile(r"sannipāt|sānnipāt|tridoṣ|tridōṣ|three d[oō]ṣa|three dosha|tridosh")

def namc_parent(code):
    if not code or code in ("AYU", "DIS"):
        return "AYU" if code == "DIS" else ""
    m = re.match(r"^([A-Z]+)-(\d+(?:\.\d+)*)$", code)
    if m:
        letters, num = m.groups()
        return f"{letters}-{num.rsplit('.', 1)[0]}" if "." in num else letters
    if re.fullmatch(r"[A-Z]+", code):
        return code[:-1] if len(code) > 1 else "DIS"
    return ""

def detect_dosha(text):
    t = (text or "").lower()
    if TRI_PAT.search(t):
        return {"vata", "pitta", "kapha"}
    return {d for d, p in DOSHA_PAT.items() if p.search(t)}

def parse_symptoms(defn):
    """symptom mentions from a NAMASTE clinical definition -> list of (sanskrit_iast, english)"""
    out = []
    d = defn or ""
    seg = re.split(r"characteri[sz]ed by", d, maxsplit=1, flags=re.I)
    body = seg[1] if len(seg) > 1 else ""
    if not body:
        return out
    body = re.split(r"\.\s+(?:This|It|The)\b|\s+This may be explained", body)[0]
    pairs = re.findall(r"([^\[\],;:]+?)\s*\[([^\]]+)\]", body)
    if pairs:
        for sa, en in pairs:
            sa = re.sub(r"^(and|or|with)\s+", "", sa.strip(" ,;.")).strip()
            out.append((iso_to_iast(sa), fix_text(en).strip(" ,;.")))
    else:
        for part in re.split(r",|;", body):
            p = fix_text(part).strip(" ,;.")
            p = re.sub(r"^(by|of|the|a|an)\s+", "", p)
            if 3 <= len(p) <= 90:
                out.append(("", p))
    return out

def build_diseases():
    m = rd("namaste_morbidity.csv")
    # NAMASTE marks names that map onto a WHO TM2 entity with a trailing '⇒'; keep it as a flag, not as text
    m["tm2_mapping_marker"] = m.name_en.str.contains("⇒") | m.name_en_alt.str.contains("⇒")
    for c in ["name_en", "name_en_alt"]:
        m[c] = m[c].str.replace("⇒", "", regex=False).str.strip()
    m["icd11_tm2_code"] = m.namc_code.map(lambda c: (TM2_RE.findall(c) or [""])[0])
    m["namc_code_clean"] = m.namc_code.map(lambda c: re.sub(r"\s+", "", TM2_RE.sub("", c)).strip("()"))
    m["namc_code_clean"] = m.namc_code_clean.str.replace(r"^\((.*)\)$", r"\1", regex=True).str.replace(r"[()]", "", regex=True)
    before = len(m)
    m = m.drop_duplicates(["namc_code_clean", "term_iast", "name_en"]).copy()
    dup_removed = before - len(m)
    m["disease_id"] = "AYD-" + m.namc_id.astype(int).map(lambda x: f"{x:05d}")
    m["parent_code"] = m.namc_code_clean.map(namc_parent)
    coded = m[m.namc_code_clean != ""]                       # a few source rows carry no NAMASTE code
    code2id = coded.drop_duplicates("namc_code_clean").set_index("namc_code_clean").disease_id.to_dict()
    m["parent_disease_id"] = [code2id.get(p, "") if p else "" for p in m.parent_code]
    m["qa_flag"] = (m.namc_code_clean == "").map({True: "missing_namc_code_in_source", False: ""})
    m["system_code"] = m.namc_code_clean.str.extract(r"^([A-Z])")[0].fillna("")
    m["category_code"] = m.namc_code_clean.str.extract(r"^([A-Z]{1,2})")[0].fillna("")
    name_of = m.drop_duplicates("namc_code_clean").set_index("namc_code_clean").name_en.to_dict()
    iast_of = m.drop_duplicates("namc_code_clean").set_index("namc_code_clean").term_iast.to_dict()
    m["system_name_en"] = m.system_code.map(name_of).fillna("")
    # NAMASTE has no single-letter root row for every system; name those from their sub-categories
    SYSTEM_FALLBACK = {"E": "disorders of body channels (srotovikāra)"}
    m["system_name_en"] = [n if n else SYSTEM_FALLBACK.get(c, "") for n, c in zip(m.system_name_en, m.system_code)]
    m["category_name_en"] = m.category_code.map(name_of).fillna("")
    m["category_sa_iast"] = m.category_code.map(iast_of).fillna("")
    m["depth"] = m.namc_code_clean.map(lambda c: len(re.findall(r"[A-Z]", c.split("-")[0])) + (c.count(".") + 1 if "-" in c else 0))
    # doṣa involvement: from the term itself, else inherited from the nearest ancestor
    own = [detect_dosha(" ".join([a, b, c, d])) for a, b, c, d in zip(m.term_iast, m.qualifier_iast, m.name_en, m.name_en_alt)]
    m["_own"] = own
    by_code = dict(zip(m.namc_code_clean, own))
    par = dict(zip(m.namc_code_clean, m.parent_code))
    dos, src = [], []
    for code, o in zip(m.namc_code_clean, own):
        if o:
            dos.append(o); src.append("term"); continue
        p, found = par.get(code, ""), set()
        while p and not found:
            found = by_code.get(p, set())
            p = par.get(p, "")
        dos.append(found); src.append("ancestor" if found else "none")
    for d in ["vata", "pitta", "kapha"]:
        m[f"dosha_{d}"] = [d in s for s in dos]
    m["dosha_source"] = src
    m["dosha_label"] = ["+".join(x for x in ["vata", "pitta", "kapha"] if x in s) if s else "unspecified" for s in dos]
    m["is_pattern_tm2"] = m.icd11_tm2_code.ne("") & m.name_en.str.contains("pattern", case=False)
    # cross-link to the WHO disorder terminology (chapters 4-5): same Sanskrit headword -> WHO English name,
    # which is plain English ('Cough due to kapha') where NAMASTE keeps Sanskrit ('kāsa due to kapha')
    who = rd("who_terms.csv")
    who = who[who.chapter.astype(int).isin([4, 5])]
    widx = {}
    for tid, iast, en in zip(who.term_id, who.iast, who.english_term):
        for k in skeleton_variants(iast):
            widx.setdefault(k, (tid, en))
    link = []
    for t in m.term_iast:
        hit = next((widx[k] for k in skeleton_variants(t) if k in widx), ("", ""))
        link.append(hit)
    m["who_term_id"] = [l[0] for l in link]
    m["name_en_who"] = [l[1] for l in link]
    m["definition_en"] = [l if l else s for l, s in zip(m.long_definition, m.short_definition)]
    m["source_id"], m["licence"], m["data_origin"] = "S1", LIC["S1"], "authoritative"
    cols = ["disease_id", "namc_id", "namc_code", "namc_code_clean", "icd11_tm2_code", "icd11_tm2_linked", "tm2_mapping_marker", "is_pattern_tm2",
            "parent_code", "parent_disease_id", "depth", "system_code", "system_name_en", "category_code", "category_name_en",
            "category_sa_iast", "term_phonetic", "term_iast", "qualifier_iast", "term_iast_official", "term_deva", "deva_source",
            "term_hi", "term_ascii", "name_en", "name_en_alt", "name_en_who", "who_term_id", "short_definition", "long_definition", "definition_en",
            "ontology_branches", "primary_index", "dosha_vata", "dosha_pitta", "dosha_kapha", "dosha_label", "dosha_source",
            "qa_flag", "source_id", "data_origin", "licence"]
    stats = dict(rows=len(m), duplicates_removed=dup_removed, with_tm2_code=int((m.icd11_tm2_code != "").sum()),
                 linked_to_who_term=int((m.who_term_id != "").sum()),
                 dosha_from_term=int((m.dosha_source == "term").sum()), dosha_inherited=int((m.dosha_source == "ancestor").sum()),
                 dosha_unspecified=int((m.dosha_source == "none").sum()))
    return m[cols], stats

def build_symptoms(diseases):
    sat = rd("namaste_sat.csv")
    d = sat[sat.section == "D"].copy()
    d = d[d.t_id.astype(str) != "1"]                       # root node 'liṅgam' (signs and symptoms)
    sym = pd.DataFrame({
        "symptom_id": "SYM-" + d.t_id.astype(int).map(lambda x: f"{x:05d}"), "source_id": "S2", "sat_code": d.sat_id,
        "term_sa_iast": d.term_iast, "term_sa_deva": d.term_deva, "term_hi": d.term_hi, "term_ascii": d.term_ascii,
        "gloss_en": [l if l else s for l, s in zip(d.long_definition, d.short_definition)],
    })
    # edges from NAMASTE definitions
    skel_idx = defaultdict(list)
    for sid, iast in zip(sym.symptom_id, sym.term_sa_iast):
        for k in skeleton_variants(iast):
            skel_idx[k].append(sid)
    gloss_idx = defaultdict(list)
    for sid, g in zip(sym.symptom_id, sym.gloss_en):
        gloss_idx[g.lower().strip()].append(sid)
    edges, extra, extra_key = [], [], {}
    for did, defn in zip(diseases.disease_id, diseases.long_definition):
        for rank, (sa, en) in enumerate(parse_symptoms(defn), 1):
            sid, how = "", ""
            if sa:
                for k in skeleton_variants(sa):
                    if k in skel_idx:
                        sid, how = skel_idx[k][0], "sanskrit_headword"
                        break
            if not sid and en.lower() in gloss_idx:
                sid, how = gloss_idx[en.lower()][0], "english_gloss"
            if not sid:                                    # new symptom concept only seen in NAMASTE
                key = skeleton(sa) if sa else en.lower()
                if key not in extra_key:
                    from lib.stable_ids import allocate
                    extra_key[key] = allocate("symptoms", [key])[key]
                    extra.append(dict(symptom_id=extra_key[key], source_id="S1", sat_code="", term_sa_iast=sa,
                                      term_sa_deva=iast_to_deva(sa) if sa else "", term_hi=hindi_usage_form(iast_to_deva(sa)) if sa else "",
                                      term_ascii=ascii_fold(sa), gloss_en=en))
                sid, how = extra_key[key], "new_from_namaste"
            edges.append(dict(disease_id=did, symptom_id=sid, mention_rank=rank, mention_sa_iast=sa, mention_en=en,
                              link_method=how, source_id="S1"))
    sym = pd.concat([sym, pd.DataFrame(extra)], ignore_index=True)
    e = pd.DataFrame(edges).drop_duplicates(["disease_id", "symptom_id"])
    sym["n_diseases"] = sym.symptom_id.map(e.groupby("symptom_id").size()).fillna(0).astype(int)
    sym["licence"] = sym.source_id.map(LIC)
    sym["data_origin"] = "authoritative"
    stats = dict(symptoms_sat=int((sym.source_id == "S2").sum()), symptoms_new_from_namaste=len(extra),
                 edges=len(e), diseases_with_symptoms=int(e.disease_id.nunique()),
                 link_methods=e.link_method.value_counts().to_dict())
    return sym, e, stats

# =============================================================================== herbs
def build_herbs(diseases):
    tax = rd("taxonomy_gbif.csv")
    tax_map = {r.name_in_source: r for r in tax.itertuples()}
    def acc(name):
        c = clean_binomial(name)
        r = tax_map.get(c)
        if r is not None and str(r.taxon_resolved) == "True" and r.accepted_name:
            return r.accepted_name, str(int(float(r.accepted_key))) if r.accepted_key not in ("", None) else "", r.family, r.gbif_status
        return c, "", "", "UNRESOLVED" if c else ""
    wd = rd("wikidata_plant_labels.csv")
    wd_map = {str(k): r for k, r in zip(wd.accepted_key.astype(str), wd.itertuples())}
    plants = rd("sat_plants.csv")
    amidha = rd("amidha_herbs.csv")
    mem = rd("mahakashaya_members.csv")
    groups = rd("mahakashaya_groups.csv")
    safety = pd.read_csv(CUR / "herb_safety.csv", keep_default_na=False)
    vocab = pd.read_csv(CUR / "controlled_vocabulary.csv", keep_default_na=False)

    recs = defaultdict(lambda: defaultdict(list))
    for r in plants.itertuples():
        a, k, fam, st = acc(r.botanical_name)
        if not a:
            continue
        h = recs[a]; h["key"] = k; h["fam"].append(fam); h["status"].append(st)
        h["sat"].append(r); h["bot_src"].append(r.botanical_name)
        for syn in str(r.botanical_synonyms).split(";"):
            if syn.strip():
                h["bot_src"].append(syn.strip())
    for r in amidha.itertuples():
        a, k, fam, st = acc(r.botanical_name)
        if not a:
            continue
        h = recs[a]; h["key"] = h.get("key") or k; h["fam"].append(fam or r.family); h["status"].append(st)
        h["amidha"].append(r); h["bot_src"].append(r.botanical_name)
    gname = groups.set_index("group_id").group_sa_iast.to_dict()
    gact = groups.set_index("group_id").action_en.to_dict()
    for r in mem.itertuples():
        if not r.member_botanical:
            continue
        a, k, fam, st = acc(r.member_botanical)
        if not a:
            continue
        h = recs[a]; h["key"] = h.get("key") or k; h["fam"].append(fam); h["status"].append(st)
        h["mk"].append(r); h["bot_src"].append(r.member_botanical)

    # IAST lookup for Amidha's ASCII names (e.g. 'Tulsi' has no IAST form in the source)
    iast_pool = {}
    for n in list(plants.name_sa_iast) + list(mem.member_sa_iast):
        if n and "?" not in n:
            iast_pool.setdefault(skeleton(n), n)
    saf_map = {}
    for r in safety.itertuples():
        a, *_ = acc(r.botanical_name)
        saf_map[a or r.botanical_name] = r
        saf_map[r.botanical_name] = r
    from lib.stable_ids import allocate
    herb_ids = allocate("herbs", recs.keys())
    rows, names_long = [], []
    for i, (a, h) in enumerate(sorted(recs.items()), 1):
        hid = herb_ids[a]
        sat = h["sat"][0] if h["sat"] else None
        am = h["amidha"]
        mk = h["mk"]
        name_iast, name_src = "", ""
        if sat is not None:
            name_iast, name_src = sat.name_sa_iast, "SAT-F (official)"
        elif mk and "?" not in mk[0].member_sa_iast:
            name_iast, name_src = mk[0].member_sa_iast, "SAT-F mahākaṣāya member"
        elif am:
            cand = iast_pool.get(skeleton(am[0].name))
            if cand:
                name_iast, name_src = cand, "Amidha name matched to SAT IAST"
        name_ascii = am[0].name if am else ascii_fold(name_iast)
        deva = iast_to_deva(name_iast) if name_iast else ""
        w = wd_map.get(h.get("key", ""))
        props = defaultdict(set)
        # descriptive lists are unioned; contradictory-capable fields (doṣa effects, vīrya, vipāka) come
        # from the PRIMARY record only - alternatives are preserved in property_variants
        for r in am:
            for f in ["rasa", "guna", "karma_actions", "parts_used", "indications", "sanskrit_synonyms"]:
                props[f] |= {x.strip() for x in str(getattr(r, f)).split(";") if x.strip()}
        if am:
            for f in ["dosha_pacify", "dosha_aggravate"]:
                props[f] = {x.strip() for x in str(getattr(am[0], f)).split(";") if x.strip()}
        variants = sorted({f"{r.amidha_id}: virya={r.virya}, vipaka={r.vipaka}, pacify={r.dosha_pacify}, aggravate={r.dosha_aggravate}"
                           for r in am}) if len(am) > 1 else []
        differs = len({(r.virya, r.vipaka, r.dosha_pacify, r.dosha_aggravate) for r in am}) > 1
        vir = [am[0].virya] if am and am[0].virya else []
        vip = [am[0].vipaka] if am and am[0].vipaka else []
        safety_r = saf_map.get(a)
        if safety_r is None:
            for b in h["bot_src"]:
                safety_r = saf_map.get(clean_binomial(b))
                if safety_r is not None:
                    break
        en_names = (sat.english_names if sat is not None else "") or (am[0].english_name if am else "") or (w.wd_label_en if w is not None else "")
        fam = next((f for f in h["fam"] if f), "")
        rows.append(dict(
            herb_id=hid, accepted_name=a, gbif_key=h.get("key", ""), gbif_status=";".join(sorted(set(h["status"]))),
            family=fam, botanical_names_in_sources="; ".join(dict.fromkeys(b for b in h["bot_src"] if b)),
            name_sa_iast=name_iast, name_sa_deva=deva, name_source=name_src, name_ascii=name_ascii,
            name_hi_ayurvedic=hindi_usage_form(deva) if deva else "",
            name_hi_common=(w.wd_label_hi if w is not None else ""), name_hi_alias=(w.wd_alias_hi if w is not None else ""),
            name_sa_wikidata=(w.wd_label_sa if w is not None else ""),
            name_en=en_names, wikidata_qid=(w.wikidata_qid if w is not None else ""),
            sa_synonyms="; ".join(sorted(props["sanskrit_synonyms"] | ({x.strip() for x in sat.formula_synonyms_iast.split(",")} - {""} if sat is not None else set()))),
            parts_used="; ".join(sorted(props["parts_used"])), rasa="; ".join(sorted(props["rasa"])),
            guna="; ".join(sorted(props["guna"])), virya="; ".join(vir), vipaka="; ".join(vip),
            karma_actions="; ".join(sorted(props["karma_actions"])),
            dosha_pacify="; ".join(d for d in ["Vata", "Pitta", "Kapha"] if d in props["dosha_pacify"]),
            dosha_aggravate="; ".join(d for d in ["Vata", "Pitta", "Kapha"] if d in props["dosha_aggravate"]),
            indications_sa_ascii="; ".join(sorted(props["indications"])),
            description_en=(am[0].description_en if am else ""),
            substitutes=(sat.substitutes if sat is not None else ""),
            mahakashaya_groups="; ".join(dict.fromkeys(gname.get(r.group_id, "") for r in mk)),
            mahakashaya_actions_en="; ".join(dict.fromkeys(gact.get(r.group_id, "") for r in mk)),
            property_conflict=differs, property_variants=" | ".join(variants) if differs else "",
            safety_class=(safety_r.safety_class if safety_r is not None else ""),
            safety_hazard_en=(safety_r.hazard_en if safety_r is not None else ""),
            safety_hazard_hi=(safety_r.hazard_hi if safety_r is not None else ""),
            requires_shodhana=(safety_r.requires_shodhana if safety_r is not None else ""),
            sat_id=(sat.sat_id if sat is not None else ""), amidha_ids="; ".join(r.amidha_id for r in am),
            in_sat=sat is not None, in_amidha=bool(am), in_mahakashaya=bool(mk),
            source_ids=";".join(s for s, ok in [("S2", sat is not None or bool(mk)), ("S5", bool(am)), ("S6", w is not None), ("S7", bool(h.get("key")))] if ok),
        ))
        nl = [(name_iast, "sa-Latn-IAST", "S2"), (deva, "sa-Deva", "derived")]
        if w is not None:
            nl.append((w.wd_label_hi, "hi-Deva", "S6"))
            nl += [(x.strip(), "hi-Deva", "S6") for x in str(w.wd_alias_hi or "").split("|")]
            nl.append((w.wd_label_sa, "sa-Deva", "S6"))
        nl += [(x.strip(), "en", "S2/S5") for x in re.split(r",|;", en_names)]
        nl += [(b, "la-botanical", "S2/S5") for b in dict.fromkeys(h["bot_src"])]
        nl += [(x, "sa-Latn-ascii", "S5") for x in sorted(props["sanskrit_synonyms"])]
        for nm, lang, src in nl:
            if nm and str(nm).strip():
                names_long.append(dict(herb_id=hid, name=str(nm).strip(), language_script=lang, source=src))
    herbs = apply_safety_states(pd.DataFrame(rows))
    herbs["data_origin"] = "integrated"
    names = pd.DataFrame(names_long).drop_duplicates()

    # ---- herb -> disease (Amidha indications -> NAMASTE disease ids)
    dis = diseases.copy()
    idx = defaultdict(list)
    for did, term, depth in zip(dis.disease_id, dis.term_iast, dis.depth):
        for k in skeleton_variants(term):
            idx[k].append((depth, did))
    keys = list(idx)
    hi_rows = []
    for hid, inds in zip(herbs.herb_id, herbs.indications_sa_ascii):
        for ind in [x.strip() for x in inds.split(";") if x.strip()]:
            k = skeleton(ind)
            how, score = "exact_skeleton", 100.0
            if k not in idx:
                best = process.extractOne(k, keys, scorer=fuzz.ratio, score_cutoff=88)
                if best:
                    k, score, how = best[0], float(best[1]), "fuzzy_skeleton"
                else:
                    hi_rows.append(dict(herb_id=hid, indication_raw=ind, disease_id="", match_method="unmatched", match_score=0.0))
                    continue
            did = sorted(idx[k])[0][1]                     # most general matching disease
            hi_rows.append(dict(herb_id=hid, indication_raw=ind, disease_id=did, match_method=how, match_score=score))
    hind = pd.DataFrame(hi_rows)
    t = dis.set_index("disease_id")
    hind["disease_term_iast"] = hind.disease_id.map(t.term_iast).fillna("")
    hind["disease_name_en"] = hind.disease_id.map(t.name_en).fillna("")
    hind["source_id"] = "S5"
    hind = apply_mapping_policy(hind, diseases=diseases)

    # ---- herb -> karma
    kv = vocab[vocab.vocab_type == "karma"].set_index("source_key")
    kr = []
    for hid, ks in zip(herbs.herb_id, herbs.karma_actions):
        for k in [x.strip() for x in ks.split(";") if x.strip()]:
            v = kv.loc[k] if k in kv.index else None
            if isinstance(v, pd.DataFrame):
                v = v.iloc[0]
            kr.append(dict(herb_id=hid, karma_key=k, karma_sa_iast=(v.sa_iast if v is not None else ""),
                           karma_sa_deva=(v.sa_deva if v is not None else ""), karma_hi=(v.hi if v is not None else ""),
                           karma_en=(v.en if v is not None else ""), in_controlled_vocab=v is not None, source_id="S5"))
    hk = pd.DataFrame(kr)

    # ---- mahākaṣāya groups + members linked to herbs
    a2id = dict(zip(herbs.accepted_name, herbs.herb_id))
    mem2 = mem.copy()
    mem2["herb_id"] = [a2id.get(acc(b)[0], "") if b else "" for b in mem2.member_botanical]
    groups2 = groups.copy()
    groups2["source_id"] = "S2"

    stats = dict(herbs=len(herbs), with_iast_name=int((herbs.name_sa_iast != "").sum()),
                 with_hindi_common_name=int((herbs.name_hi_common != "").sum()),
                 with_properties=int((herbs.rasa != "").sum()), with_gbif_key=int((herbs.gbif_key != "").sum()),
                 in_sat=int(herbs.in_sat.sum()), in_amidha=int(herbs.in_amidha.sum()),
                 in_both_sat_and_amidha=int((herbs.in_sat & herbs.in_amidha).sum()),
                 with_safety_flag=int((herbs.safety_class != "").sum()),
                 indication_links=len(hind), indication_link_rate=round(float((hind.disease_id != "").mean()), 4),
                 karma_links=len(hk), mahakashaya_members_linked=round(float((mem2.herb_id != "").mean()), 4))
    return herbs, names, hind, hk, groups2, mem2, stats, acc

# =============================================================================== Duke (modern layer)
def build_duke(herbs, acc):
    a2id = dict(zip(herbs.accepted_name, herbs.herb_id))
    tax = pd.read_parquet(INT / "duke_fnftax.parquet")
    tax["herb_id"] = tax.TAXON.map(lambda t: a2id.get(acc(t)[0], ""))
    fn2herb = dict(zip(tax.FNFNUM, tax.herb_id))
    far = pd.read_parquet(INT / "duke_farmacy_new.parquet")
    parts = pd.read_parquet(INT / "duke_parts.parquet").set_index("PPCO").PPNA.to_dict()
    far["herb_id"] = far.FNFNUM.map(fn2herb).fillna("")
    far = far[far.herb_id != ""]
    num = lambda s: pd.to_numeric(s.replace("", None), errors="coerce")
    ph = pd.DataFrame({"herb_id": far.herb_id, "chemical": far.CHEM, "chem_id": far.CHEMID,
                       "plant_part_code": far.PPCO, "plant_part": far.PPCO.map(parts).fillna(""),
                       "amount_low_ppm": num(far.AMT_OR_LO), "amount_high_ppm": num(far.AMT_HI),
                       "reference": far.REFERENCE, "source_id": "S4"}).drop_duplicates()
    agg = pd.read_parquet(INT / "duke_aggregac.parquet")
    act = agg[agg.CHEM.isin(set(ph.chemical))]
    pa = pd.DataFrame({"chemical": act.CHEM, "activity": act.ACTIVITY, "dosage": act.DOSAGE,
                       "reference": act.REFERENCE, "source_id": "S4"}).drop_duplicates()
    eth = pd.read_parquet(INT / "duke_ethnobot.parquet")
    eth = eth[eth.COUNTRY.str.contains("India", case=False, na=False)].copy()
    eth["herb_id"] = eth.TAXON.map(lambda t: a2id.get(acc(t)[0], ""))
    eth = eth[eth.herb_id != ""]
    he = pd.DataFrame({"herb_id": eth.herb_id, "use_activity": eth.ACTIVITY, "country_community": eth.COUNTRY,
                       "taxon_in_source": eth.TAXON, "reference": eth.REFERENCE, "source_id": "S4"}).drop_duplicates()
    stats = dict(herbs_with_phytochemicals=int(ph.herb_id.nunique()), phytochemical_rows=len(ph),
                 distinct_chemicals=int(ph.chemical.nunique()), activity_rows=len(pa),
                 herbs_with_indian_ethnobotany=int(he.herb_id.nunique()), ethnobotany_rows=len(he))
    return ph, pa, he, stats

# =============================================================================== curated layers
def build_diagnostics():
    d = pd.read_csv(CUR / "diagnostic_methods.csv", keep_default_na=False)
    d["name_sa_deva"] = [iast_to_deva(x) if x and x != "—" else "" for x in d.name_sa_iast]
    d["source_id"], d["data_origin"], d["licence"] = "S0", "curated", LIC["S0"]
    return d

def subset_terms(term, domains, kind):
    t = term[term.domain.isin(domains)].copy()
    t.insert(0, f"{kind}_id", [f"{kind.upper()[:3]}-{i:05d}" for i in range(1, len(t) + 1)])
    return t

def tag_therapy(row):
    s = (row.term_sa_iast + " " + row.term_en + " " + row.section_title).lower()
    tags = []
    for k, pat in {"pañcakarma": r"vamana|virecana|basti|nasya|raktamokṣ|pañcakarma|emesis|purgation|enema|bloodletting|errhine",
                   "pūrvakarma": r"snehan|svedan|oleation|sudation|fomentation",
                   "rasāyana": r"rasāyan|rejuvenat", "vājīkaraṇa": r"vājīkaraṇ|aphrodisiac|virility",
                   "surgery_parasurgery": r"śastra|śalya|kṣārasūtra|kṣāra|agnikarma|jalauk|surg|incision|excision|cauter|leech",
                   "śamana": r"śaman|palliat", "toxicology": r"viṣ|poison", "psychotherapy": r"sattvāvajaya|daiva|psych|counsel",
                   "external_therapy": r"abhyaṅg|lepa|seka|dhārā|pichu|bastiḥ|śirodhār|massage|ointment"}.items():
        if re.search(pat, s):
            tags.append(k)
    return ";".join(tags)

def build_formulations(herbs, names, diseases):
    f = pd.read_csv(CUR / "classical_formulations.csv", keep_default_na=False)
    f["name_sa_deva"] = f.name_sa_iast.map(iast_to_deva)
    f["name_hi"] = f.name_sa_deva.map(hindi_usage_form)
    f["source_id"], f["data_origin"], f["licence"] = "S0", "curated_requires_expert_verification", LIC["S0"]
    f["verification_status"] = "curated from classical texts; verify against Ayurvedic Formulary of India (AFI) before clinical use"
    # ingredient index: herb names (IAST + synonyms) -> herb id
    idx = {}
    for hid, nm in zip(herbs.herb_id, herbs.name_sa_iast):
        if nm:
            for k in skeleton_variants(nm):
                idx.setdefault(k, hid)
    for hid, nm, lang in zip(names.herb_id, names.name, names.language_script):
        if lang.startswith("sa"):
            for k in skeleton_variants(nm):
                idx.setdefault(k, hid)
    NONHERB = {
        "sitopalā": "sugar candy", "śarkarā": "sugar", "guḍa": "jaggery", "madhu": "honey", "ghṛta": "ghee (clarified butter)",
        "tilataila": "sesame oil", "eraṇḍataila": "castor oil", "kṣīra": "milk", "saindhavalavaṇa": "rock salt",
        "viḍalavaṇa": "black salt (viḍa)", "sāmudralavaṇa": "sea salt", "sauvarcalalavaṇa": "sauvarcala salt",
        "pārada": "mercury (processed)", "gandhaka": "sulphur (purified)", "lauha": "iron (calx)", "abhraka": "mica (calx)",
        "tāmra": "copper (calx)", "gairika": "red ochre (purified)", "śilājatu": "shilajit (mineral pitch)",
        "śaṅkha": "conch shell", "godantī": "gypsum", "karpūra": "camphor", "hiṅgu": "asafoetida (resin)",
        "vaṃśalocana": "bamboo manna", "nāgavallī": "betel leaf juice"}
    ing, ind = [], []
    dis_idx = defaultdict(list)
    for did, term, depth in zip(diseases.disease_id, diseases.term_iast, diseases.depth):
        for k in skeleton_variants(term):
            dis_idx[k].append((depth, did))
    for r in f.itertuples():
        for k, x in enumerate([y.strip() for y in r.ingredients_sa_iast.split(";") if y.strip()], 1):
            hid = idx.get(skeleton(x), "")
            ing.append(dict(form_id=r.form_id, rank=k, ingredient_sa_iast=x, ingredient_sa_deva=iast_to_deva(x),
                            herb_id=hid, ingredient_type="herb" if hid else ("mineral/animal/other" if x in NONHERB else "herb (unlinked)"),
                            ingredient_en=NONHERB.get(x, "")))
        for x in [y.strip() for y in r.indications_sa_iast.split(";") if y.strip()]:
            k = skeleton(x)
            did = sorted(dis_idx[k])[0][1] if k in dis_idx else ""
            ind.append(dict(form_id=r.form_id, indication_sa_iast=x, disease_id=did))
    ing, ind = pd.DataFrame(ing), pd.DataFrame(ind)
    stats = dict(formulations=len(f), ingredients=len(ing), ingredients_linked_to_herbs=int((ing.herb_id != "").sum()),
                 ingredient_link_rate_plant=round(float((ing.herb_id != "").sum() / max(1, (ing.ingredient_type != "mineral/animal/other").sum())), 4),
                 indications=len(ind), indications_linked=round(float((ind.disease_id != "").mean()), 4))
    return f, ing, ind, stats

def main():
    report = {}
    print("[terminology]"); term, report["terminology"] = build_terminology(); save(term, "terminology")
    print("[diseases]"); dis, report["diseases"] = build_diseases(); save(dis, "diseases")
    print("[symptoms]"); sym, ds, report["symptoms"] = build_symptoms(dis); save(sym, "symptoms"); save(ds, "disease_symptom")
    print("[herbs]")
    herbs, names, hind, hk, groups, mem, report["herbs"], acc = build_herbs(dis)
    print("[duke]"); ph, pa, he, report["duke"] = build_duke(herbs, acc)
    cnt = lambda df: herbs.herb_id.map(df.groupby("herb_id").size()).fillna(0).astype(int)
    herbs["n_phytochemicals"], herbs["n_india_ethnobotany_uses"] = cnt(ph), cnt(he)
    save(herbs, "herbs"); save(names, "herb_names"); save(hind, "herb_indication"); save(hk, "herb_karma")
    save(groups, "herb_groups"); save(mem, "herb_group_members")
    save(ph, "herb_phytochemicals"); save(pa, "phytochemical_activities"); save(he, "herb_ethnobotany")
    print("[curated + subsets]")
    save(build_diagnostics(), "diagnostic_methods")
    th = subset_terms(term, ["treatment"], "therapy"); th["therapy_tags"] = [tag_therapy(r) for r in th.itertuples()]
    save(th, "therapies")
    save(subset_terms(term, ["pharmaceutics"], "pharmaceutic"), "pharmaceutics")
    save(subset_terms(term, ["diet", "prevention_lifestyle"], "lifestyle"), "diet_lifestyle")
    f, ing, ind, report["formulations"] = build_formulations(herbs, names, dis)
    save(f, "formulations"); save(ing, "formulation_ingredients"); save(ind, "formulation_indications")
    save(pd.DataFrame(SOURCES, columns=["source_id", "title", "url", "licence", "role"]), "sources")
    save(pd.read_csv(CUR / "controlled_vocabulary.csv", keep_default_na=False), "controlled_vocabulary")
    (ROOT / "reports/kb_build_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

if __name__ == "__main__":
    main()
