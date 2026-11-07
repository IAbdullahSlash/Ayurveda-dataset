#!/usr/bin/env python3
"""
Stage 08 - Post-processing: validation, bilingual QA corpus, exports.

  * data-quality & integrity checks  -> reports/data_quality_report.json (also enforced by tests/)
  * bilingual question-answer pairs generated from KB records (each with provenance record ids)
  * bilingual document corpus (JSONL) for retrieval / RAG / LLM grounding
  * relational SQLite database with unique indexes and pre-export reference validation  -> release/ayurkb.sqlite
  * Frictionless Data package descriptor  -> release/datapackage.json
"""
import json, re, sqlite3, sys, unicodedata, tempfile, shutil
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.export_transaction import publish, export_lock
from lib.provenance import write_sidecar, build_index, metadata
from lib.indic import iast_to_deva, deva_to_iast, has_devanagari
from lib.indication_policy import active_indications

ROOT = Path(__file__).resolve().parents[1]
P, REL = ROOT / "data/processed", ROOT / "release"
REL.mkdir(exist_ok=True)
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)

PK = {"terminology": "term_uid", "diseases": "disease_id", "symptoms": "symptom_id", "herbs": "herb_id",
      "herb_groups": "group_id", "diagnostic_methods": "dx_id", "formulations": "form_id", "sources": "source_id",
      "therapies": "therapy_id", "pharmaceutics": "pharmaceutic_id", "diet_lifestyle": "lifestyle_id",
      "case_reports": "case_id", "headword_concepts": "concept_id", "phytochemicals": "chemical"}
FK = [("disease_symptom", "disease_id", "diseases", "disease_id"), ("disease_symptom", "symptom_id", "symptoms", "symptom_id"),
      ("herb_indication", "herb_id", "herbs", "herb_id"), ("herb_indication", "disease_id", "diseases", "disease_id"),
      ("herb_karma", "herb_id", "herbs", "herb_id"), ("herb_names", "herb_id", "herbs", "herb_id"),
      ("herb_group_members", "group_id", "herb_groups", "group_id"), ("herb_group_members", "herb_id", "herbs", "herb_id"),
      ("herb_phytochemicals", "herb_id", "herbs", "herb_id"), ("herb_ethnobotany", "herb_id", "herbs", "herb_id"),
      ("formulation_ingredients", "form_id", "formulations", "form_id"), ("formulation_ingredients", "herb_id", "herbs", "herb_id"),
      ("formulation_indications", "form_id", "formulations", "form_id"), ("formulation_indications", "disease_id", "diseases", "disease_id"),
      ("diseases", "parent_disease_id", "diseases", "disease_id"),
      ("therapy_disease", "disease_id", "diseases", "disease_id"), ("therapy_disease", "therapy_id", "therapies", "therapy_id"),
      ("herb_indication_evidence", "herb_id", "herbs", "herb_id"), ("herb_indication_evidence", "disease_id", "diseases", "disease_id"),
      ("formulation_indication_evidence", "form_id", "formulations", "form_id"),
      ("formulation_indication_evidence", "disease_id", "diseases", "disease_id"),
      ("case_report_entities", "case_id", "case_reports", "case_id"), ("case_report_links", "disease_id", "diseases", "disease_id"),
      ("concept_members", "concept_id", "headword_concepts", "concept_id"), ("herb_image_datasets", "herb_id", "herbs", "herb_id"),
      ("disease_symptom_who", "disease_id", "diseases", "disease_id"), ("disease_symptom_who", "symptom_id", "symptoms", "symptom_id"),
      ("disease_symptom_inferred", "disease_id", "diseases", "disease_id"), ("disease_symptom_inferred", "symptom_id", "symptoms", "symptom_id"),
      ("disease_symptom_inferred", "inherited_from", "diseases", "disease_id"),
      ("disease_symptom_from_cases", "disease_id", "diseases", "disease_id"), ("disease_symptom_from_cases", "symptom_id", "symptoms", "symptom_id"),
      ("dosha_suggestions", "disease_id", "diseases", "disease_id"),
      ("case_report_symptoms_semantic", "case_id", "case_reports", "case_id"), ("case_report_symptoms_semantic", "symptom_id", "symptoms", "symptom_id")]
MOJIBAKE = re.compile(r"Ã.|â€|Â\s|�")
DEVA_OK = re.compile(r"^[ऀ-ॿ\s\-,/;()\[\].:ʼ'0-9॥।ऽ‍‌]*$")

def checks():
    rep, fails = {}, []
    tables = {f.stem: rd(f.stem) for f in sorted(P.glob("*.csv"))}
    rep["tables"] = {k: dict(rows=len(v), columns=v.shape[1]) for k, v in tables.items()}
    for t, k in PK.items():
        if t in tables:
            dup = int(tables[t][k].duplicated().sum()); empty = int((tables[t][k] == "").sum())
            rep[f"pk:{t}.{k}"] = dict(duplicates=dup, empty=empty)
            if dup or empty:
                fails.append(f"primary key {t}.{k}: {dup} duplicates / {empty} empty")
    for t, c, rt, rc in FK:
        if t in tables and rt in tables:
            vals = tables[t][c][tables[t][c] != ""]
            bad = int((~vals.isin(set(tables[rt][rc]))).sum())
            rep[f"fk:{t}.{c}->{rt}.{rc}"] = dict(checked=int(len(vals)), orphans=bad)
            if bad:
                fails.append(f"foreign key {t}.{c}: {bad} orphans")
    # text hygiene across all tables
    moj, deva_bad = {}, {}
    for t, df in tables.items():
        for c in df.columns:
            if df[c].dtype != object:
                continue
            n = int(df[c].astype(str).str.contains(MOJIBAKE).sum())
            if n:
                moj[f"{t}.{c}"] = n
            if c.endswith(("_deva", "_deva_primary")):
                s = df[c][df[c] != ""]
                b = int((~s.map(lambda x: bool(DEVA_OK.match(x)))).sum())
                if b:
                    deva_bad[f"{t}.{c}"] = b
    rep["mojibake_cells"] = moj; rep["non_devanagari_in_devanagari_columns"] = deva_bad
    # transliteration round-trip on IAST headwords
    s = tables["diseases"].term_iast.head(2000)
    rt = [deva_to_iast(iast_to_deva(x)) == unicodedata.normalize("NFC", x) for x in s if x]
    rep["iast_devanagari_roundtrip_rate"] = round(sum(rt) / len(rt), 4)
    # bilingual coverage
    cov = {}
    for t, en, hi in [("diseases", "name_en", "term_hi"), ("diseases", "name_en", "name_en_hi"), ("diseases", "definition_en", "definition_hi"),
                      ("symptoms", "gloss_en", "gloss_hi"), ("symptoms", "term_sa_iast", "term_hi"), ("terminology", "term_en", "term_en_hi"),
                      ("terminology", "definition_en", "definition_hi"), ("herbs", "name_en", "name_hi_ayurvedic"),
                      ("herbs", "name_en", "name_hi_common"), ("herbs", "description_en", "description_hi")]:
        if t in tables and hi in tables[t].columns:
            df = tables[t]; m = df[en] != ""
            cov[f"{t}.{hi}"] = round(float((df.loc[m, hi] != "").mean()), 4) if m.any() else None
    h = tables["herbs"]
    cov["herbs.any_hindi_or_devanagari_name"] = round(float(((h.name_hi_ayurvedic != "") | (h.name_hi_common != "") |
                                                             (h.get("name_en_hi", pd.Series([""] * len(h))) != "")).mean()), 4)
    rep["bilingual_coverage"] = cov
    # domain rules
    d = tables["diseases"]
    lab_ok = all((lab == "unspecified") == (not (v or p or k)) for lab, v, p, k in
                 zip(d.dosha_label, d.dosha_vata.astype(str) == "True", d.dosha_pitta.astype(str) == "True", d.dosha_kapha.astype(str) == "True"))
    rep["dosha_label_consistent_with_flags"] = lab_ok
    if not lab_ok:
        fails.append("dosha_label inconsistent with dosha_* flags")
    toxic = h[h.safety_class.str.contains("viṣa")]
    rep["toxic_herbs_flagged"] = int(len(toxic))
    rep["toxic_herbs_without_shodhana_flag"] = toxic[toxic.requires_shodhana != "yes"].accepted_name.tolist()
    f = tables["formulations"]
    rep["formulations_with_metal_or_toxic_flag"] = int(f.contains_metal_or_toxic.str.startswith("yes").sum())
    rep["licence_missing_rows"] = {t: int((df["licence"] == "").sum()) for t, df in tables.items() if "licence" in df.columns}
    rep["failures"] = fails
    return rep, tables

# ----------------------------------------------------------------------------- bilingual QA pairs
def qa_pairs(t):
    qa = []
    vocab = t["controlled_vocabulary"]
    vh = {(r.vocab_type, r.source_key): r.hi for r in vocab.itertuples()}
    def hi_list(kind, s):
        return ", ".join(vh.get((kind, x.strip()), x.strip()) for x in s.split(";") if x.strip())
    d = t["diseases"]
    for r in d[(d.definition_en != "") & (d.depth >= 2)].itertuples():
        qa.append(dict(qa_id=f"QA-D-{r.disease_id}", topic="disease_definition", record_ids=r.disease_id, language="en",
                       question=f"What is {r.term_iast} ({r.name_en}) in Ayurveda?",
                       answer=f"{r.term_iast} ({r.term_deva}) - NAMASTE code {r.namc_code_clean}"
                              + (f", WHO ICD-11 TM2 {r.icd11_tm2_code}" if r.icd11_tm2_code else "") + f". {r.definition_en}"
                              + (f" Doṣa involvement: {r.dosha_label}." if r.dosha_label != "unspecified" else "")))
        if getattr(r, "definition_hi", ""):
            qa.append(dict(qa_id=f"QA-D-{r.disease_id}-hi", topic="disease_definition", record_ids=r.disease_id, language="hi",
                           question=f"आयुर्वेद में {r.term_hi} ({r.name_en_hi}) क्या है?",
                           answer=f"{r.term_deva} - नमस्ते कोड {r.namc_code_clean}"
                                  + (f", डब्ल्यूएचओ आईसीडी-11 टीएम2 {r.icd11_tm2_code}" if r.icd11_tm2_code else "") + f"। {r.definition_hi}"))
    h = t["herbs"]
    for r in h[(h.rasa != "") & (h.name_sa_iast != "")].itertuples():
        en = (f"{r.name_sa_iast} ({r.accepted_name}): rasa {r.rasa}; guṇa {r.guna}; vīrya {r.virya}; vipāka {r.vipaka}; "
              f"pacifies {r.dosha_pacify or '-'}; aggravates {r.dosha_aggravate or '-'}."
              + (f" Main actions: {r.karma_actions}." if r.karma_actions else "")
              + (f" SAFETY: {r.safety_class} - {r.safety_hazard_en}." if r.safety_class else ""))
        hi = (f"{r.name_hi_ayurvedic} ({r.accepted_name}): रस {hi_list('rasa', r.rasa)}; गुण {hi_list('guna', r.guna)}; "
              f"वीर्य {hi_list('virya', r.virya)}; विपाक {hi_list('vipaka', r.vipaka)}; शमन {hi_list('dosha', r.dosha_pacify) or '-'}; "
              f"प्रकोप {hi_list('dosha', r.dosha_aggravate) or '-'}।" + (f" सावधानी: {r.safety_hazard_hi}।" if r.safety_class else ""))
        qa.append(dict(qa_id=f"QA-H-{r.herb_id}", topic="herb_properties", record_ids=r.herb_id, language="en",
                       question=f"What are the Ayurvedic pharmacological properties (rasa, guṇa, vīrya, vipāka) of {r.name_sa_iast}?", answer=en))
        qa.append(dict(qa_id=f"QA-H-{r.herb_id}-hi", topic="herb_properties", record_ids=r.herb_id, language="hi",
                       question=f"{r.name_hi_ayurvedic} के रस, गुण, वीर्य और विपाक क्या हैं?", answer=hi))
    hi_ = active_indications(t["herb_indication"])
    hn = h.set_index("herb_id")
    for did, g in hi_.groupby("disease_id"):
        if len(g) < 2:
            continue
        dr = d.set_index("disease_id").loc[did]
        names = [f"{hn.loc[x].name_sa_iast or hn.loc[x].name_ascii} ({hn.loc[x].accepted_name})" for x in g.herb_id.unique()[:15]]
        qa.append(dict(qa_id=f"QA-I-{did}", topic="herbs_for_condition", record_ids=";".join([did] + list(g.herb_id.unique()[:15])), language="en",
                       question=f"Which single herbs are indicated for {dr.term_iast} ({dr.name_en})?",
                       answer="Herbs recorded with this indication: " + "; ".join(names) + ". (Knowledge-base listing, not a prescription.)"))
        names_hi = [hn.loc[x].name_hi_ayurvedic or hn.loc[x].name_hi_common or hn.loc[x].accepted_name for x in g.herb_id.unique()[:15]]
        qa.append(dict(qa_id=f"QA-I-{did}-hi", topic="herbs_for_condition", record_ids=";".join([did] + list(g.herb_id.unique()[:15])), language="hi",
                       question=f"{dr.term_hi} में कौन-सी औषधियाँ बताई गई हैं?",
                       answer="इस संकेत के लिए दर्ज औषधियाँ: " + "; ".join(names_hi) + "। (ज्ञानकोश सूची - चिकित्सकीय पर्चा नहीं।)"))
    for r in t["diagnostic_methods"].itertuples():
        qa.append(dict(qa_id=f"QA-X-{r.dx_id}", topic="diagnostic_method", record_ids=r.dx_id, language="en",
                       question=f"What is {r.name_en}" + (f" ({r.name_sa_iast})" if r.name_sa_iast not in ("", "—") else "") + " and what is its modern counterpart?",
                       answer=f"It assesses: {r.what_is_assessed_en}. Reference: {r.classical_reference}. Modern counterpart: {r.modern_counterpart_en} ({r.modern_tools_or_tests})."))
        qa.append(dict(qa_id=f"QA-X-{r.dx_id}-hi", topic="diagnostic_method", record_ids=r.dx_id, language="hi",
                       question=f"{r.name_hi} क्या है और इसका आधुनिक समकक्ष क्या है?",
                       answer=f"{getattr(r, 'what_is_assessed_hi', '') or r.what_is_assessed_en}। आधुनिक समकक्ष: {r.modern_counterpart_hi}।"))
    fi = t["formulation_ingredients"]
    for r in t["formulations"].itertuples():
        ing = fi[fi.form_id == r.form_id]
        qa.append(dict(qa_id=f"QA-F-{r.form_id}", topic="formulation", record_ids=r.form_id, language="en",
                       question=f"What is {r.name_sa_iast} ({r.name_en}) and what does it contain?",
                       answer=f"A {r.dosage_form} described in {r.classical_reference}. Ingredients"
                              + ("" if r.ingredients_complete == "yes" else " (main)") + f": {r.ingredients_sa_iast.replace(';', ',')}. "
                              f"Indications: {r.indications_en}. Doṣa action: {r.dosha_action}." + (f" Safety: {r.safety_note}." if r.safety_note else "")
                              + " [curated record - verify against the Ayurvedic Formulary of India]"))
        qa.append(dict(qa_id=f"QA-F-{r.form_id}-hi", topic="formulation", record_ids=r.form_id, language="hi",
                       question=f"{r.name_hi} क्या है और इसमें क्या-क्या है?",
                       answer=f"घटक: {', '.join(ing.ingredient_sa_deva)}। संकेत: {getattr(r, 'indications_hi', '') or r.indications_en}।"
                              + (f" सावधानी: {getattr(r, 'safety_note_hi', '') or r.safety_note}।" if r.safety_note else "")))
    q = pd.DataFrame(qa)
    q["data_origin"] = "derived (templated from KB records)"
    return q

# ----------------------------------------------------------------------------- RAG corpus
def corpus(t):
    docs = []
    for r in t["diseases"].itertuples():
        docs.append(dict(doc_id=r.disease_id, type="disease", title_en=r.name_en, title_sa=r.term_iast, title_hi=r.term_hi,
                         text_en=f"{r.term_iast} | {r.name_en} | NAMASTE {r.namc_code_clean} | TM2 {r.icd11_tm2_code} | doṣa {r.dosha_label} | {r.definition_en}",
                         text_hi=f"{r.term_deva} | {getattr(r, 'name_en_hi', '')} | {getattr(r, 'definition_hi', '')}", source=";".join(sorted({r.source_id} | ({"S3"} if getattr(r, "definition_source", "").startswith("WHO") else set()))),
                         definition_source=getattr(r, "definition_source", ""),
                         definition_record_id=getattr(r, "who_term_id", "") if getattr(r, "definition_source", "").startswith("WHO") else r.disease_id,
                         review_status="not_adjudicated",
                         translation_flags=getattr(r, "definition_hi_qe_flags", "")))
    for r in t["herbs"].itertuples():
        docs.append(dict(doc_id=r.herb_id, type="herb", title_en=r.name_en, title_sa=r.name_sa_iast, title_hi=r.name_hi_common or r.name_hi_ayurvedic,
                         text_en=f"{r.name_sa_iast or r.name_ascii} | {r.accepted_name} ({r.family}) | rasa {r.rasa} | guṇa {r.guna} | vīrya {r.virya} | vipāka {r.vipaka} | pacifies {r.dosha_pacify} | aggravates {r.dosha_aggravate} | actions {r.karma_actions} | indications {r.indications_sa_ascii} | {r.description_en} | safety {r.safety_class} {r.safety_hazard_en}",
                         text_hi=f"{r.name_sa_deva} | {r.name_hi_common} | {getattr(r, 'description_hi', '')} | {r.safety_hazard_hi}", source=r.source_ids, safety_review_status="flagged_unreviewed" if r.safety_class else "unassessed"))
    for r in t["terminology"].itertuples():
        docs.append(dict(doc_id=r.term_uid, type=f"term:{r.domain}", title_en=r.term_en, title_sa=r.term_sa_iast_primary, title_hi=r.term_hi,
                         text_en=f"{r.term_sa_iast} | {r.term_en} | {r.definition_en}",
                         text_hi=f"{r.term_sa_deva} | {getattr(r, 'term_en_hi', '')} | {getattr(r, 'definition_hi', '')}", source=r.source_id))
    for r in t["symptoms"].itertuples():
        docs.append(dict(doc_id=r.symptom_id, type="symptom", title_en=r.gloss_en, title_sa=r.term_sa_iast, title_hi=r.term_hi,
                         text_en=f"{r.term_sa_iast} | {r.gloss_en}", text_hi=f"{r.term_sa_deva} | {getattr(r, 'gloss_hi', '')}", source=r.source_id))
    for r in t["formulations"].itertuples():
        docs.append(dict(doc_id=r.form_id, type="formulation", title_en=r.name_en, title_sa=r.name_sa_iast, title_hi=r.name_hi,
                         text_en=f"{r.name_sa_iast} | {r.dosage_form} | {r.classical_reference} | ingredients {r.ingredients_sa_iast} | indications {r.indications_en} | {r.dosha_action} | {r.safety_note}",
                         text_hi=f"{r.name_sa_deva} | {getattr(r, 'indications_hi', '')}", source="S0"))
    for r in t["diagnostic_methods"].itertuples():
        docs.append(dict(doc_id=r.dx_id, type="diagnostic_method", title_en=r.name_en, title_sa=r.name_sa_iast, title_hi=r.name_hi,
                         text_en=f"{r.name_sa_iast} | {r.name_en} | {r.what_is_assessed_en} | {r.classical_reference} | modern: {r.modern_counterpart_en}; {r.modern_tools_or_tests}",
                         text_hi=f"{r.name_hi} | {getattr(r, 'what_is_assessed_hi', '')} | {r.modern_counterpart_hi}", source="S0"))
    index = build_index(t)
    licences = dict(zip(t["sources"].source_id, t["sources"].licence))
    masters = [("diseases", "disease_id"), ("herbs", "herb_id"), ("terminology", "term_uid"),
               ("symptoms", "symptom_id"), ("formulations", "form_id"), ("diagnostic_methods", "dx_id")]
    rows = {str(row[key]): (table, row) for table, key in masters for row in t[table].to_dict("records")}
    for doc in docs:
        table, row = rows[doc["doc_id"]]
        doc["provenance"] = metadata(table, row, index, licences)
        doc["source"] = ";".join(doc["provenance"]["source_ids"])
    return docs

def sqlite_export(t):
    db = REL / "ayurkb.sqlite"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    for name, df in t.items():
        df.to_sql(name, con, index=False)
    cur = con.cursor()
    for tbl, k in PK.items():
        if tbl in t:
            cur.execute(f'CREATE UNIQUE INDEX IF NOT EXISTS ux_{tbl}_{k} ON "{tbl}"("{k}")')
    for tbl, c, *_ in FK:
        if tbl in t:
            cur.execute(f'CREATE INDEX IF NOT EXISTS ix_{tbl}_{c} ON "{tbl}"("{c}")')
    con.commit(); con.close()
    return db

def datapackage(t):
    lic = {"S0": "CC-BY-4.0", "S1": "other-attribution", "S2": "other-attribution", "S3": "CC-BY-NC-SA-3.0-IGO",
           "S4": "CC0-1.0", "S5": "CC-BY-4.0", "S6": "CC0-1.0", "S7": "CC-BY-4.0", "S8": "public-domain", "S9": "public-domain",
           "S10": "metadata-facts", "S11": "public-domain", "S12": "CC-BY-4.0", "S13": "WHO-ICTRP-terms"}
    res = []
    for name, df in t.items():
        fields = [{"name": c, "type": ("integer" if pd.api.types.is_integer_dtype(df[c]) else "number" if pd.api.types.is_float_dtype(df[c])
                                       else "boolean" if pd.api.types.is_bool_dtype(df[c]) else "string")} for c in df.columns]
        res.append({"name": name, "path": f"../data/processed/{name}.csv", "format": "csv", "encoding": "utf-8",
                    "schema": {"fields": fields, **({"primaryKey": PK[name]} if name in PK else {})}})
    pkg = {"name": "ayurkb-bilingual-ayurveda-knowledge-base", "title": "AyurKB - Bilingual (English/Hindi/Sanskrit) hybrid Ayurveda knowledge base",
           "version": "1.2.0", "licenses": [{"name": "CC-BY-NC-SA-4.0", "title": "Combined release (WHO component is CC BY-NC-SA 3.0 IGO)"}],
           "sources": [{"title": r.title, "path": r.url, "licence": r.licence} for r in t["sources"].itertuples()],
           "resources": res}
    (REL / "datapackage.json").write_text(json.dumps(pkg, indent=2, ensure_ascii=False))

def write_exports(rep, t):
    if rep["failures"]:
        raise ValueError("Export blocked: " + "; ".join(rep["failures"]))
    q = qa_pairs(t)
    q.to_csv(P / "qa_pairs.csv", index=False); t["qa_pairs"] = q
    docs = corpus(t)
    with open(REL / "ayurkb_corpus.jsonl", "w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    rep["qa_pairs"] = dict(total=len(q), by_language=q.language.value_counts().to_dict(), by_topic=q.topic.value_counts().to_dict())
    rep["corpus_documents"] = len(docs)
    rep["provenance"] = write_sidecar(t, REL / "ayurkb_provenance.jsonl")
    db = sqlite_export(t)
    datapackage(t)
    rep["sqlite_bytes"] = db.stat().st_size
    (ROOT / "reports/data_quality_report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
    print(json.dumps({k: v for k, v in rep.items() if k not in ("tables",) and not k.startswith(("pk:", "fk:"))}, indent=2, ensure_ascii=False, default=str))
    print("integrity:", {k: v for k, v in rep.items() if k.startswith(("pk:", "fk:")) and (v.get("orphans") or v.get("duplicates"))} or "all keys OK")

def main():
    global ROOT, P, REL
    original = ROOT, P, REL
    # Serialize builders; readers use the immutable snapshot pointer.
    with export_lock(ROOT / "release/.export.lock"):
        rep, tables = checks()
        if rep["failures"]:
            raise ValueError("Export blocked: " + "; ".join(rep["failures"]))
        with tempfile.TemporaryDirectory(prefix=".export-stage-", dir=original[0]) as directory:
            stage = Path(directory)
            try:
                ROOT, P, REL = stage, stage / "data/processed", stage / "release"
                P.mkdir(parents=True)
                REL.mkdir()
                (stage / "reports").mkdir()
                # Include the descriptor's resources in the immutable snapshot.
                for source in original[1].glob("*.csv"):
                    shutil.copy2(source, P / source.name)
                write_exports(rep, tables)
                with sqlite3.connect(REL / "ayurkb.sqlite") as connection:
                    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("SQLite integrity check failed")
                paths = [str(path.relative_to(stage)) for path in stage.rglob("*") if path.is_file()]
            finally:
                ROOT, P, REL = original
            publish(ROOT, stage, paths)

if __name__ == "__main__":
    main()
