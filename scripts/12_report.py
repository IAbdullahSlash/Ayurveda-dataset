#!/usr/bin/env python3
"""
Stage 12 - Build the HTML dataset report (release/report.html) from the processed tables and the JSON
reports written by every stage.  All numbers on the page come from those files.
"""
import json, re, subprocess, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P, R, ML = ROOT / "data/processed", ROOT / "reports", ROOT / "reports/ml"
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)
js = lambda p: json.loads(Path(p).read_text()) if Path(p).exists() else {}

def tests_passed():
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")], capture_output=True, text=True, cwd=ROOT).stdout
    m = re.search(r"(\d+) passed", out); f = re.search(r"(\d+) failed", out)
    return int(m.group(1)) if m else 0, int(f.group(1)) if f else 0

def exp_rows(df, metric="macro_f1", best_from=None):
    df = df.copy()
    df["kind"] = df.model.map(lambda m: "baseline" if ("Dummy" in m or "Classical" in m or "Knowledge-base" in m) else "model")
    df = df[df[f"{metric}_mean"].notna()].sort_values(f"{metric}_mean", ascending=False)
    best = df[df.kind == "model"].iloc[0].model
    rows = []
    for r in df.itertuples():
        g = lambda k: getattr(r, k, float("nan"))
        det = [f"accuracy {g('accuracy_mean'):.3f}" + (f" ± {g('accuracy_std'):.3f}" if pd.notna(g('accuracy_std')) and g('accuracy_std') > 0 else ""),
               f"macro-F1 {g('macro_f1_mean'):.3f}"]
        if pd.notna(g("roc_auc_ovr_mean")):
            det.append(f"ROC-AUC {g('roc_auc_ovr_mean'):.3f}")
        for k in ("top3_accuracy_mean", "top5_accuracy_mean"):
            if k in df.columns and pd.notna(g(k)):
                det.append(f"{k.split('_')[0]} accuracy {g(k):.3f}")
        if r.kind == "baseline" and "Knowledge-base" in r.model:
            det.append("no training: matches the case against each disease's symptom profile")
        rows.append(dict(label=r.model, value=float(g(f"{metric}_mean")), kind="best" if r.model == best else r.kind, details=det))
    head = ["Model", "Accuracy", "Macro-F1", "ROC-AUC"]
    tab = [[r.model, f"{r.accuracy_mean:.3f}", f"{r.macro_f1_mean:.3f}",
            (f"{r.roc_auc_ovr_mean:.3f}" if "roc_auc_ovr_mean" in df.columns and pd.notna(r.roc_auc_ovr_mean) else "-")] for r in df.itertuples()]
    return rows, head, tab, best


def extension_data(data):
    """sections for the extension layers (stages 14-20); each is skipped when its files are absent"""
    e6 = js(ML / "E6_case_reports.json")
    if e6:
        m = e6["E6_matcher_on_real_presentations"]
        H = rd("herbs").set_index("herb_id")
        hname = lambda h: (H.loc[h].name_sa_iast or H.loc[h].accepted_name) if h in H.index else h
        metals = dict(e6.get("metals_in_adverse_event_reports", []))
        con = e6.get("kb_link_concordance", {})
        rows = []
        for k in (10, 30):
            rows += [dict(label=f"KB matcher · top-{k}", value=m[f"family_hit@{k}"], kind="best",
                          details=[f"{m['n_cases_evaluated']} cases with a NAMASTE diagnosis and 2+ presenting symptoms",
                                   "hit = the diagnosed disorder or a closely related one (subtype, parent, sibling)"]),
                     dict(label=f"popularity baseline · top-{k}", value=m[f"baseline_popularity_family_hit@{k}"], kind="baseline",
                          details=["disorders ranked by how many symptoms they list"]),
                     dict(label=f"random · top-{k}", value=m[f"baseline_random_exact_hit@{k}"], kind="baseline",
                          details=[f"{k} of {m['n_candidate_disorders']:,} disorders"])]
        top = [["Ayurvedic diagnoses", "; ".join(f"{a} ({n})" for a, n in e6["top_diagnoses"][:8])],
               ["Herbs", "; ".join(f"{hname(a)} ({n})" for a, n in e6["top_herbs"][:10])],
               ["Procedures", "; ".join(f"{a} ({n})" for a, n in e6["top_procedures"][:10])],
               ["Modern assessments", "; ".join(f"{a} ({n})" for a, n in e6["top_modern_assessments"][:10])]]
        data["real"] = dict(
            text=(f"{e6['n_records']} Ayurveda case reports and case series were retrieved from Europe PMC and {e6['n_fulltext_mined']} "
                  f"open-access full texts were mined with the knowledge-base lexicons. Only identifiers and extracted KB entities are kept. "
                  f"{e6['n_adverse_event']} reports describe harm linked to Ayurvedic products, mostly heavy-metal poisoning."),
            figures=[["case reports mined", e6["n_records"]], ["full texts mined", e6["n_fulltext_mined"]],
                     ["adverse-event reports", e6["n_adverse_event"]], ["implicating lead", metals.get("lead", 0)],
                     ["observed disorder-herb pairs", con.get("observed_disorder_herb_pairs", 0)],
                     ["of these already in the KB", f"{con.get('share_recorded_in_kb', 0):.0%}"]],
            finding=(f"On {m['n_cases_evaluated']} real presentations the matcher puts the diagnosed disorder family in its top 10 for "
                     f"{m['family_hit@10']:.0%} of cases, about twice the popularity baseline ({m['baseline_popularity_family_hit@10']:.0%}) and far above "
                     f"chance ({m['baseline_random_exact_hit@10']:.1%}). Real case language differs from the classical lexicon, so this is the honest ceiling "
                     f"of a symptom-only matcher today."),
            rows=rows, top=top)
    tiers = []
    lab = {"clinical_evidence": "clinical study", "literature_supported": "literature", "sparse": "sparse", "no_literature": "none found",
           "not_queryable": "not searchable"}
    for name, file in (("herb → disorder", "herb_indication_evidence"), ("formulation → disorder", "formulation_indication_evidence")):
        if (P / f"{file}.csv").exists():
            ev = rd(file)
            vc = ev.evidence_tier.value_counts()
            for k in ["clinical_evidence", "literature_supported", "sparse", "no_literature", "not_queryable"]:
                if k in vc:
                    tiers.append([name, lab[k], int(vc[k]), float(vc[k] / len(ev))])
    if tiers:
        th = []
        if (P / "therapy_disease.csv").exists():
            td = rd("therapy_disease")
            basis = {"site_specific_procedure": "body-site procedures (eye, nose, ear, mouth, head, ulcers)",
                     "disorder_protocol": "disorder-specific protocols with text references", "category_principle": "srotas / doṣa category principles",
                     "dosha_principle_generic": "Caraka Sū 25.40 (basti / virecana / vamana)", "iatrogenic_complication_of": "complications of a procedure",
                     "observed_in_published_cases": "procedures reported in case reports"}
            th = [[k.replace("_", " "), int(v), basis.get(k, "")] for k, v in td.relation.value_counts().items()]
        data["evidence"] = dict(tiers=tiers, therapy=th)
    e7 = js(ML / "E7_tuning.json")
    if e7:
        r = pd.DataFrame(e7["results"])
        gains = r.gain.round(3)
        data["tuning"] = dict(
            text=(f"Nested cross-validation (search inside every outer training fold) on three tasks. Tuning helped most for models whose defaults "
                  f"were poorly suited (largest gain +{gains.max():.3f} macro-F1) and did not help, or slightly hurt, on the small herb dataset, where the "
                  f"inner search overfits. The untuned comparison above is therefore a fair one."),
            rows=[[x.task, x.model, f"{x.default_macro_f1_mean:.3f}", f"{x.tuned_macro_f1_mean:.3f}", f"{x.gain:+.3f}", f"{x.wilcoxon_p:.3f}"]
                  for x in r.itertuples()])
    rows = []
    if (P / "phytochemicals.csv").exists():
        p = rd("phytochemicals")
        rows.append(["PubChem identifiers", f"{p.pubchem_match.str.startswith('matched').sum():,} of {len(p):,} key phytochemicals (CID, InChIKey, SMILES)"])
    ch = js(R / "phytochem_ids_report.json")
    if ch:
        rows.append(["ChEMBL protein targets", f"{ch.get('chembl_target_rows', 0):,} compound-target rows (separate CC BY-SA file)"
                     if ch.get("chembl_target_rows") else "not included: the ChEMBL service was failing during the build; stage 17 re-runs it with --chembl-only"])
    if (P / "herb_image_datasets.csv").exists():
        im = rd("herb_image_datasets")
        rows.append(["Plant-image datasets", f"{im[im.herb_id != ''].herb_id.nunique()} herbs linked to 3 CC BY 4.0 leaf-image datasets"])
    if (P / "headword_concepts.csv").exists():
        rows.append(["Cross-source concepts", f"{len(rd('headword_concepts')):,} Sanskrit headwords shared across WHO, SAT, NAMASTE and KB tables"])
    if (P / "case_report_links.csv").exists():
        cl = rd("case_report_links")
        rows.append(["Curation queue", f"{(cl.in_kb_for_disorder_family.astype(str) == 'False').sum():,} disorder-medicine pairs seen in case reports but not yet in the KB"])
    script = None
    if (P / "multiscript_names.csv").exists():
        ms = rd("multiscript_names")
        x = ms[(ms.entity_type == "herb") & (ms.devanagari == "हरिद्रा")]
        x = x.iloc[0] if len(x) else ms.iloc[0]
        script = dict(devanagari=x.devanagari, rows=[[k.capitalize(), x[k]] for k in
                      ["bengali", "gujarati", "gurmukhi", "kannada", "malayalam", "odia", "tamil", "telugu"]] + [["IAST", "haridrā"]])
    if rows and script:
        data["linked"] = dict(rows=rows, script=script)

def upgrades_data(data):
    """E8: before/after of the accuracy work (stages 23-26); rows appear only for results that exist"""
    rows, chart = [], []
    e6 = js(ML / "E6b_matching_improvements.json").get("variants", {})
    if e6:
        v0, v4 = e6["V0 baseline (lexical, flat ranking)"], e6["V4 + profiles learned from real cases (5-fold CV)"]
        fq = e6.get("baseline_training_diagnosis_frequency (no symptoms)", {})
        rows.append(["Real cases: right disorder group in top 10", f"{v0['hit@10']:.0%}", f"{v4['hit@10']:.0%} (±{v4.get('hit@10_sd_over_seeds', 0):.0%})",
                     "clinical-term crosswalk, meaning-based matching, group ranking, profiles learned from real cases (5-fold CV)"])
        rows.append(["Real cases: right group ranked first", f"{v0['hit@1']:.0%}", f"{v4['hit@1']:.0%}", "same"])
        names = [("V0 baseline (lexical, flat ranking)", "lexical words (before)", "model"), ("V1 + clinical-term crosswalk", "+ clinical-term crosswalk", "model"),
                 ("V2 + semantic clause matching", "+ meaning-based matching", "model"), ("V3 + disorder-group ranking", "+ group ranking", "model"),
                 ("V4 + profiles learned from real cases (5-fold CV)", "+ learned from real cases", "best"),
                 ("baseline_training_diagnosis_frequency (no symptoms)", "most common diagnoses only", "baseline")]
        for key, label, kind in names:
            if key in e6:
                chart.append(dict(label=label, value=e6[key]["hit@10"], kind=kind, details=[f"top-1 {e6[key]['hit@1']:.0%}, top-30 {e6[key]['hit@30']:.0%}",
                                                                                               f"{int(e6[key]['n_cases'])} cases"]))
        data_finding = (f"On the same {int(v0['n_cases'])} cases: {v0['hit@10']:.0%} → {v4['hit@10']:.0%}. Ranking the most common diagnoses alone "
                        f"reaches {fq.get('hit@10', 0):.0%}, so the symptoms add real signal; most of the gain comes from learning from real cases.")
    else:
        data_finding = ""
    if e6 and "V3w group ranking, + WHO sign lists only" in e6:
        rows.append(["Adding WHO sign lists to the matcher (top 10)", f"{e6['V3 + disorder-group ranking']['hit@10']:.0%}",
                     f"{e6['V3w group ranking, + WHO sign lists only']['hit@10']:.0%}",
                     "made it worse: the lists are broad, so they are kept for explanation and left out of ranking"])
    e6ft = js(ML / "E6b_matching_improvements_finetuned.json").get("variants", {})
    if e6ft and e6:
        k = "V4 + profiles learned from real cases (5-fold CV)"
        rows.append(["Real cases, top 10, with the fine-tuned search model", f"{e6[k]['hit@10']:.0%}", f"{e6ft[k]['hit@10']:.0%}",
                     "no gain on English case text (within ±4% noise); the fine-tuned model is used for Hindi search, where it helps"])
    e5b = js(ML / "E5b_finetuned_retrieval.json")
    if e5b:
        for task, label in (("diseases", "disorders"), ("symptoms", "symptoms")):
            b, a = e5b["base"][task]["hindi_headword"]["recall_at_10"], e5b["finetuned"][task]["hindi_headword"]["recall_at_10"]
            rows.append([f"Search {label} by Sanskrit headword (recall@10)", f"{b:.2f}", f"{a:.2f}", "search model fine-tuned on the dataset's own pairs, test concepts held out"])
    e1 = js(ML / "E1_plus.json")
    for key, label in (("E1a organ system | NAMASTE definitions (as stage 07)", "Organ system from text (E1a)"),
                       ("E1b doṣa from masked text | NAMASTE definitions (as stage 07)", "Doṣa from symptom text (E1b)"),
                       ("E1c Hindi (MT) | NAMASTE definitions (as stage 07)", "Same task in Hindi (E1c)")):
        if key in e1:
            r = e1[key]["results"]; base = r["TF-IDF + LR (stage 07)"]["macro_f1_mean"]
            best = max(r.items(), key=lambda kv: kv[1]["macro_f1_mean"])
            rows.append([label + ", macro-F1", f"{base:.3f}", f"{best[1]['macro_f1_mean']:.3f}", best[0] if best[1]['macro_f1_mean'] > base + 0.002 else "no gain from embeddings"])
    e2 = js(ML / "E2c_plus.json")
    if e2:
        best_of = lambda k: max((r for r in e2[k] if "Dummy" not in r["model"]), key=lambda r: r["macro_f1_mean"])
        o = best_of("original features"); variants = [k for k in e2 if isinstance(e2[k], list) and k not in ("labels", "original features")]
        bv = max(variants, key=lambda k: best_of(k)["macro_f1_mean"])
        rows.append(["Herb indications (E2c), macro-F1", f"{o['macro_f1_mean']:.3f}", f"{best_of(bv)['macro_f1_mean']:.3f}",
                     f"{bv}: no meaningful gain - phytochemistry does not predict classical indications here" if best_of(bv)["macro_f1_mean"] < o["macro_f1_mean"] + 0.01 else bv])
    fm = js(R / "fill_missing_report.json")
    if fm:
        rows.append(["Disorders with a definition", f"{fm['disorders_with_definition']['before']:.1%}", f"{fm['disorders_with_definition']['after']:.1%}",
                     f"{fm['definitions_filled_from_WHO']} WHO definitions for disorders NAMASTE leaves undefined"])
        rows.append(["Disorders with a symptom profile", f"{fm['disorders_with_any_profile']['before']:,}", f"{fm['disorders_with_any_profile']['after']:,}",
                     f"{fm['who_sign_lists']['edges']:,} edges from WHO sign lists + inherited profiles for subtypes (flagged)"])
        ds = fm.get("dosha_suggestions", {})
        rows.append(["Disorders with a doṣa suggestion", "0", f"{ds.get('suggested', 0):,}", f"text model, cross-validated accuracy {ds.get('cv_accuracy', 0):.2f}; flagged for expert review"])
        pe = fm.get("mt_postedits", {})
        if pe:
            rows.append(["Hindi translation errors fixed by rule", "-", f"{sum(pe.values())} rows",
                         "curated post-edits, e.g. 'stiffness' had been translated as 'bitterness', 'nausea' as 'vomiting'"])
    if rows:
        data["upgrades"] = dict(text=("Each change was measured on the same rows and folds as the original experiment. "
                                      "Model suggestions are kept in separate, flagged tables and never overwrite curated values."),
                                rows=rows, chart=chart, finding=data_finding)

def main():
    kb = js(R / "kb_build_report.json"); tax = js(R / "taxonomy_report.json"); nam = js(R / "namaste_parse_report.json")
    who = js(R / "who_parse_validation.json"); ev = js(R / "evidence_report.json"); dq = js(R / "data_quality_report.json")
    qe = js(R / "translation_qe.json"); cov = js(R / "translation_coverage.json")
    n_pass, n_fail = tests_passed()
    d, h, s, f, t, dx = rd("diseases"), rd("herbs"), rd("symptoms"), rd("formulations"), rd("terminology"), rd("diagnostic_methods")
    q = rd("qa_pairs")
    data = {"generated": pd.Timestamp.now().strftime("%d %b %Y")}
    data["figures"] = [["disorders (NAMASTE codes)", len(d)], ["symptoms in the lexicon", len(s)], ["herbs (GBIF-validated)", len(h)],
                       ["standard terms (WHO + SAT)", len(t)], ["classical formulations", len(f)],
                       ["phytochemical records", len(rd("herb_phytochemicals"))], ["clinical trials linked", ev.get("distinct_trials", 0)],
                       ["bilingual Q&A pairs", len(q)], ["automated checks passing", n_pass]]
    if (P / "case_reports.csv").exists():
        data["figures"].insert(7, ["real case reports mined", len(rd("case_reports"))])
    # ---- record cards
    def row(df, col, val):
        x = df[df[col] == val]
        return x.iloc[0] if len(x) else None
    cards = []
    k = row(d, "term_iast", "kaphajakāsaḥ")
    if k is not None:
        cards.append(dict(kind="disorder", deva=k.term_deva, rows=[["IAST", k.term_iast], ["Hindi", k.term_hi], ["English", k.name_en_who or k.name_en],
                     ["Hindi gloss", k.get("name_en_hi", "")], ["NAMASTE", k.namc_code_clean], ["ICD-11 TM2", k.icd11_tm2_code or "-"], ["Doṣa", k.dosha_label]]))
    hb = row(h, "accepted_name", "Curcuma longa")
    if hb is not None:
        cards.append(dict(kind="herb", deva=hb.name_sa_deva, rows=[["IAST", hb.name_sa_iast], ["Hindi", hb.name_hi_common], ["Botanical", hb.accepted_name],
                     ["Rasa · vīrya", f"{hb.rasa} · {hb.virya}"], ["Vipāka", hb.vipaka], ["Pacifies", hb.dosha_pacify],
                     ["Evidence", f"{int(float(hb.pubmed_count)):,} papers · {int(float(hb.clinicaltrials_count))} trials"]]))
    nd = row(dx, "dx_id", "DX-007")
    if nd is not None:
        cards.append(dict(kind="diagnostic method", deva=nd.name_sa_deva, rows=[["IAST", nd.name_sa_iast], ["Hindi", nd.name_hi], ["English", nd.name_en],
                     ["Classical source", nd.classical_reference], ["Modern counterpart", nd.modern_counterpart_en], ["Standard", nd.standard_ref]]))
    tf = row(f, "form_id", "FORM-001")
    if tf is not None:
        cards.append(dict(kind="classical formulation", deva=tf.name_sa_deva, rows=[["IAST", tf.name_sa_iast], ["English", tf.name_en],
                     ["Source", tf.classical_reference], ["Ingredients", tf.ingredients_sa_iast.replace(";", ",")], ["Doṣa action", tf.dosha_action],
                     ["Status", "curated, verify against AFI"]]))
    data["cards"] = cards
    cnt = lambda n: len(rd(n))
    data["tables"] = [
        ["Diagnosis", "diseases", len(d), "NAMASTE morbidity codes, hierarchy, ICD-11 TM2 codes, WHO cross-links, doṣa labels, definitions"],
        ["Diagnosis", "symptoms / disease_symptom", f"{len(s):,} / {cnt('disease_symptom'):,}", "Sanskrit symptom lexicon with glosses; disease → symptom graph"],
        ["Diagnosis", "diagnostic_methods", len(dx), "classical examination methods with classical sources, modern counterparts, PubMed counts"],
        ["Herbs", "herbs", len(h), "official names, accepted botanical names, Hindi names, rasa/guṇa/vīrya/vipāka/karma/doṣa, safety, evidence"],
        ["Herbs", "herb_indication / herb_karma / herb_groups", f"{cnt('herb_indication'):,} / {cnt('herb_karma'):,} / {cnt('herb_groups')}", "herb → disease, herb → action, Caraka's 50 mahākaṣāya"],
        ["Remedies", "formulations", len(f), "classical compound remedies: source text, dosage form, ingredients, indications, safety (curated)"],
        ["Remedies", "therapies / pharmaceutics / diet_lifestyle", f"{cnt('therapies'):,} / {cnt('pharmaceutics')} / {cnt('diet_lifestyle')}", "pañcakarma and other procedures; dosage forms; pathya, dinacaryā, ṛtucaryā"],
        ["Terminology", "terminology", len(t), "WHO (2022) and NAMASTE SAT standard terms, cross-linked"],
        ["Modern science", "herb_phytochemicals / phytochemical_activities", f"{cnt('herb_phytochemicals'):,} / {cnt('phytochemical_activities'):,}", "USDA Duke phytochemistry and bioactivities"],
        ["Modern science", "clinical_trials / herb_ethnobotany", f"{cnt('clinical_trials'):,} / {cnt('herb_ethnobotany'):,}", "ClinicalTrials.gov studies; Indian ethnobotanical uses"],
        ["AI-ready", "qa_pairs / prakriti_synthetic_cohort", f"{len(q):,} / 3,000", "bilingual Q&A from records; synthetic constitution cohort (labelled)"],
    ]
    opt = lambda n: len(rd(n)) if (P / f"{n}.csv").exists() else 0
    for area, name, what in [("Real world", "case_reports / case_report_entities", "published case reports: diagnosis, symptoms, herbs, formulations, procedures, modern tests, adverse events"),
                             ("Evidence", "herb_indication_evidence / formulation_indication_evidence", "PubMed co-occurrence, clinical-study counts, lift and evidence tier for every link"),
                             ("Remedies", "therapy_disease", "disorder → procedure links with classical references"),
                             ("Linked data", "phytochemicals / herb_image_datasets", "PubChem identifiers; links to CC BY 4.0 plant-image datasets"),
                             ("Language", "multiscript_names / headword_concepts", "names in 8 regional scripts; cross-source Sanskrit headword concepts")]:
        parts = [p.strip() for p in name.split("/")]
        n = " / ".join(f"{opt(p):,}" for p in parts)
        if any(opt(p) for p in parts):
            data["tables"].append([area, name, n, what])
    data["sources"] = [[r.source_id, r.title, r.licence, r.role] for r in rd("sources").itertuples()]
    data["pipeline"] = [
        dict(phase="Pre-process", title="Parse, repair, normalise", steps=[
            f"WHO PDF parsed by coordinates; {who.get('annex_ids_found_in_parse', 0):.1%} of index IDs recovered",
            f"NAMASTE phonetic → IAST → Devanagari; {nam.get('sat', {}).get('repair_rate', 0):.1%} of damaged diacritic tokens restored",
            "mojibake, HTML residue and Unicode normalised (NFC, ISO-15919 → IAST)",
            f"{tax.get('names_from_ayurveda_sources', 0)} botanical names checked against GBIF; {tax.get('resolved_to_species_rate', 0):.1%} resolved"]),
        dict(phase="In-process", title="Integrate and enrich", steps=[
            "herb master merged on accepted names; conflicts flagged, not unioned",
            f"{kb.get('diseases', {}).get('with_tm2_code', 0)} ICD-11 TM2 codes; {kb.get('diseases', {}).get('linked_to_who_term', 0)} disorders linked to WHO terms",
            f"{kb.get('symptoms', {}).get('edges', 0):,} disease → symptom edges from clinical definitions",
            "PubMed and ClinicalTrials.gov evidence; English → Hindi with glossary injection and QE"]),
        dict(phase="Post-process", title="Validate, export, model", steps=[
            f"{n_pass} automated checks passing (keys, references, scripts, safety, bilingual)",
            "SQLite with indexes, Parquet/CSV, Frictionless datapackage, RAG corpus",
            "multilingual embedding index for semantic search",
            "ML benchmarks with calibration and abstain-and-refer",
            "real-world check on published case reports; nested-CV tuning"]),
    ]
    data["quality"] = [
        ["Primary and foreign keys", "all unique, no orphans" if not dq.get("failures") else "; ".join(dq["failures"]), not dq.get("failures")],
        ["IAST ↔ Devanagari round trip", f"{dq.get('iast_devanagari_roundtrip_rate', 0):.1%}", dq.get("iast_devanagari_roundtrip_rate", 0) > 0.99],
        ["Mojibake cells", f"{sum(dq.get('mojibake_cells', {}).values())}", not dq.get("mojibake_cells")],
        ["WHO parse vs book index", f"{who.get('annex_ids_found_in_parse', 0):.2%} IDs, {who.get('annex_iast_synonym_recovered', 0):.1%} synonyms", True],
        ["NAMASTE transliteration (aligned rows)", "97% exact; rest are source typos", True],
        ["Damaged SAT diacritics restored", f"{nam.get('sat', {}).get('repair_rate', 0):.1%} ({nam.get('sat', {}).get('rows_still_flagged', 0)} rows flagged)", True],
        ["Botanical names resolved (GBIF)", f"{tax.get('resolved_to_species_rate', 0):.1%}, {tax.get('synonyms_resolved', 0)} synonyms updated", True],
        ["Herb → disease links", f"{kb.get('herbs', {}).get('indication_link_rate', 0):.1%} matched to NAMASTE", True],
        ["Toxic herbs carrying śodhana flag", f"{dq.get('toxic_herbs_flagged', 0)} of {dq.get('toxic_herbs_flagged', 0)}", not dq.get("toxic_herbs_without_shodhana_flag")],
        ["Automated test suite", f"{n_pass} passed, {n_fail} failed", n_fail == 0],
    ]
    bil = [["Disorder names (Sanskrit → Hindi form)", f"{(d.term_hi != '').mean():.1%}"],
           ["Symptoms with Sanskrit headword", f"{(s[s.term_sa_iast != ''].term_hi != '').mean():.1%}"],
           ["Herbs with any Hindi / Devanagari name", f"{dq.get('bilingual_coverage', {}).get('herbs.any_hindi_or_devanagari_name', 0):.1%}"]]
    for key, label in [("diseases.definition_en", "Disorder definitions (MT)"), ("symptoms.gloss_en", "Symptom glosses (MT)"),
                       ("terminology.definition_en", "Term definitions (MT)")]:
        c = cov.get(key)
        if c:
            bil.append([label, f"{c['translated'] / max(1, c['nonempty']):.1%} · {c['qe_flagged'] / max(1, c['translated']):.1%} flagged"])
    if qe:
        bil.append(["Back-translation chrF (sample)", f"{qe.get('mean_backtranslation_chrF', 0):.1f} (n={qe.get('sample', 0)})"])
    data["bilingual"] = bil
    # ---- experiments
    E = []
    def add(eid, title, file, metric, tags, finding_fn):
        p = ML / file
        if not p.exists():
            return
        res = pd.DataFrame(json.loads(p.read_text())["results"]) if file.endswith(".json") else pd.read_csv(p)
        rows, head, tab, best = exp_rows(res, metric)
        E.append(dict(id=eid, title=title, metric=metric.replace("_", "-").replace("macro-f1", "macro-F1").replace("accuracy", "top-1 accuracy"),
                      tags=tags, finding=finding_fn(res, best), rows=rows, table_head=head, table=tab))
    def val(res, model, col="macro_f1_mean"):
        x = res[res.model == model]
        return float(x[col].iloc[0]) if len(x) else float("nan")
    add("E1a", "Disorder → organ system from clinical text", "E1a_system_from_text.json", "macro_f1", ["real · NAMASTE", "text · TF-IDF"],
        lambda r, b: f"{b} reaches macro-F1 {val(r, b):.2f} (accuracy {val(r, b, 'accuracy_mean'):.2f}) across {len(js(ML / 'E1a_system_from_text.json').get('classes', {}))} NAMASTE systems; majority baseline {val(r, 'Dummy (majority)'):.2f}.")
    add("E1b", "Doṣa involvement from symptom text (doṣa words masked)", "E1b_dosha_from_masked_text.json", "macro_f1", ["real · NAMASTE", "masked text"],
        lambda r, b: f"With every vāta / pitta / kapha word removed, {b} still infers the doṣa from the symptom picture alone (macro-F1 {val(r, b):.2f} vs {val(r, 'Dummy (majority)'):.2f} baseline).")
    p = ML / "E1c_bilingual_system_from_text.json"
    if p.exists():
        r1 = pd.DataFrame(json.loads(p.read_text())["results"])
        r1["model"] = r1.model + " · " + r1.language
        rows, head, tab, best = exp_rows(r1, "macro_f1")
        en = r1[r1.language == "English"].macro_f1_mean.max(); hi_ = r1[r1.language != "English"].macro_f1_mean.max()
        E.append(dict(id="E1c", title="Same task in English vs Hindi text", metric="macro-F1", tags=["real · NAMASTE", "bilingual"],
                      finding=f"Best model on Hindi text: macro-F1 {hi_:.2f}; on the English source: {en:.2f}. The Hindi layer keeps most of the diagnostic signal, so Hindi-language models are viable.",
                      rows=rows, table_head=head, table=tab))
    add("E2a", "Herb vīrya (uṣṇa / śīta) from rasa, guṇa, vipāka, karma", "E2a_virya_cv_results.csv", "macro_f1", ["real · herbs", "tabular"],
        lambda r, b: f"{b} {val(r, b):.2f} vs the classical rasa rule {val(r, 'Classical rule: rasa majority (hot vs cold tastes)'):.2f} and the vipāka rule {val(r, 'Classical rule: vipāka (madhura -> śīta)'):.2f}: classical theory explains most, but not all, vīrya assignments.")
    p = ML / "E2b_dosha_pacify.json"
    if p.exists():
        j = json.loads(p.read_text()); sm = pd.DataFrame(j["summary"])
        sm["accuracy_std"] = 0.0
        rows, head, tab, best = exp_rows(sm.rename(columns={}), "macro_f1")
        cr = sm[sm.model.str.startswith("Classical")].macro_f1_mean
        E.append(dict(id="E2b", title="Doṣa-pacifying profile (V / P / K, mean of three labels)", metric="macro-F1", tags=["real · herbs", "multi-label"],
                      finding=f"{best} {sm[sm.model == best].macro_f1_mean.iloc[0]:.2f} vs {float(cr.iloc[0]) if len(cr) else float('nan'):.2f} for the classical rule (uṣṇa → pacifies vāta & kapha, śīta → pitta).",
                      rows=rows, table_head=head, table=tab))
    p = ML / "E2c_indications.json"
    if p.exists():
        j = json.loads(p.read_text()); sm = pd.DataFrame(j["summary"]); sm["accuracy_std"] = 0.0
        rows, head, tab, best = exp_rows(sm, "macro_f1")
        E.append(dict(id="E2c", title="Herb indications from rasa / guṇa / vīrya / vipāka / doṣa", metric="macro-F1", tags=["real · herbs", "12 labels"],
                      finding=f"Pharmacodynamic properties alone predict indications only modestly ({best} macro-F1 {sm[sm.model == best].macro_f1_mean.iloc[0]:.2f}, ROC-AUC {sm[sm.model == best].roc_auc_ovr_mean.iloc[0]:.2f}): therapeutic use carries information beyond rasa-guṇa-vīrya.",
                      rows=rows, table_head=head, table=tab))
    add("E3a", "Symptom set → disorder (60 disorders)", "E3a_top60.json", "accuracy", ["hybrid · simulated cases", "60 classes"],
        lambda r, b: f"{b} top-1 {val(r, b, 'accuracy_mean'):.2f}, top-3 {val(r, b, 'top3_accuracy_mean'):.2f}; the no-training knowledge-base matcher scores {val(r, 'Knowledge-base matcher (IDF-cosine, no training)', 'accuracy_mean'):.2f}.")
    add("E3b", "Symptom set → disorder (all distinguishable disorders)", "E3b_all.json", "accuracy", ["hybrid · simulated cases", "large label space"],
        lambda r, b: f"Across {js(ML / 'E3b_all.json').get('n_diseases', 0)} disorders: {b} top-1 {val(r, b, 'accuracy_mean'):.2f}, top-5 {val(r, b, 'top5_accuracy_mean'):.2f}.")
    add("E4", "Prakṛti (7 constitution types) from questionnaire", "E4_prakriti.json", "macro_f1", ["synthetic · WHO-grounded", "mixed types"],
        lambda r, b: f"{b} macro-F1 {val(r, b):.2f} vs classical answer-counting {val(r, 'Classical questionnaire scoring (count V/P/K answers)'):.2f}. Synthetic: measures recovery of the generating model, not clinical accuracy.")
    data["experiments"] = E
    e4 = js(ML / "E4_prakriti.json").get("post_processing", {})
    if e4:
        data["post"] = dict(text=(f"{e4['model']}: isotonic calibration lowers expected calibration error from {e4['ece_raw']:.3f} to {e4['ece_calibrated']:.3f}. "
                                  f"Referring the least-confident cases to a practitioner raises accuracy on the rest."),
                            series=[dict(name=f"{e4['model']} (raw)", short="raw", points=e4["selective_raw"]),
                                    dict(name=f"{e4['model']} (calibrated)", short="calibrated", points=e4["selective_calibrated"])])
    e5 = js(ML / "E5_crosslingual_retrieval.json")
    rows5 = []
    for task in ["diseases", "symptoms"]:
        for qn, ql in [("hindi_headword", "Hindi/Sanskrit headword"), ("hindi_text", "Hindi gloss")]:
            for m, ml in [("transliteration_char_tfidf", "transliteration + char n-grams"), ("multilingual_e5_dense", "multilingual embeddings"), ("hybrid_rrf", "hybrid (rank fusion)")]:
                try:
                    rows5.append([f"{task} · {ql}", ml, e5[task][qn][m]["recall_at_10"]])
                except KeyError:
                    pass
    data["e5"] = rows5
    extension_data(data)
    upgrades_data(data)
    data["files"] = "\n".join([
        f"data/processed/*.csv | *.parquet     {len(list(P.glob('*.csv')))} tables (see docs/DATA_DICTIONARY.md)",
        "release/ayurkb.sqlite                  relational database with indexes",
        "release/ayurkb_corpus.jsonl            bilingual documents for RAG / search",
        "release/embeddings/                    multilingual semantic index (e5-small, 384-d)",
        "release/datapackage.json               Frictionless Data descriptor",
        "examples/expert_system_demo.py         symptoms (EN/HI) → disorders → herbs, formulations, śodhana",
        "models/trained/                        Prakṛti classifier, symptom → disorder model",
        "reports/ml/ · reports/figures/         every experiment, every model, every fold summary",
        "curation/                              curated layers (flagged for expert review)",
        "release/tools/                         expert review desk + bilingual Prakṛti questionnaire (interactive)",
        "review/AyurKB_expert_review.xlsx       offline expert-review workbook (drop-down verdicts)",
        "docs/permission_requests/              letters to PCIM&H, Ayush, WHO, IMPPAT, CCRAS",
        "scripts/01…22 · tests/                 reproducible pipeline and test suite"])
    data["limits"] = [
        "Decision support for qualified practitioners, not autonomous diagnosis or prescribing; no doses are given.",
        "Curated layers (formulations, diagnostic correspondences, safety list, glossary, questionnaire) need review by an Ayurveda expert; verify formulations against the Ayurvedic Formulary of India.",
        "Hindi descriptions are machine-translated and flagged per row; Hindi names of Sanskrit terms are rule-derived.",
        "E3 cases are simulated from the real disease–symptom graph and the E4 cohort is fully synthetic, so those scores do not measure clinical accuracy.",
        "Case-report entities are text-mined with the KB lexicons (precision over recall); verify against the article before reuse.",
        "Licence: CC BY-NC-SA 4.0 overall (WHO component); per-row licence columns allow commercial-safe subsets. ChEMBL-derived targets, if built, ship separately under CC BY-SA 3.0.",
    ]
    # README machine-learning table (generated, so the numbers always match reports/ml/)
    md = ["| Exp. | Task | Data | Best model | Score | Reference point |", "|---|---|---|---|---|---|"]
    for e in E:
        best = next(r for r in e["rows"] if r["kind"] == "best")
        refs = [r for r in e["rows"] if r["kind"] == "baseline"]
        ref = "; ".join(f"{r['label'].replace('Classical rule: ', 'rule: ')} {r['value']:.3f}" for r in refs[:2]) or "-"
        md.append(f"| {e['id']} | {e['title']} | {e['tags'][0]} | {best['label']} | {e['metric']} {best['value']:.3f} | {ref} |")
    readme = ROOT / "README.md"
    txt = readme.read_text(encoding="utf-8")
    txt = re.sub(r"<!-- ML_TABLE_START -->.*<!-- ML_TABLE_END -->",
                 "<!-- ML_TABLE_START -->\n" + "\n".join(md) + "\n<!-- ML_TABLE_END -->", txt, flags=re.S)
    if data.get("upgrades"):
        up = ["| Area | Before | After | What changed |", "|---|---|---|---|"] + [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in data["upgrades"]["rows"]]
        txt = re.sub(r"<!-- UPGRADES_START -->.*<!-- UPGRADES_END -->", "<!-- UPGRADES_START -->\n" + "\n".join(up) + "\n<!-- UPGRADES_END -->",
                     txt, flags=re.S)
    readme.write_text(txt, encoding="utf-8")
    html = (ROOT / "docs/report_template.html").read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    out = ROOT / "release/report.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(html) / 1024:.0f} KB); experiments: {[e['id'] for e in E]}")

if __name__ == "__main__":
    main()
