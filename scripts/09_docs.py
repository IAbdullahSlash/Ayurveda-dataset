#!/usr/bin/env python3
"""
Stage 09 - Documentation generator: docs/DATA_DICTIONARY.md (every table, every column: type, fill-rate,
example, description) and reports/kb_summary.json (headline counts used by README / report).
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"

TABLE_DOC = {
    "diseases": "NAMASTE Ayurveda morbidity codes: 2,892 disorders and patterns with hierarchy, WHO ICD-11 TM2 codes, doṣa involvement and clinical definitions. Sanskrit (IAST / Devanagari), Hindi and English.",
    "symptoms": "Signs-and-symptoms lexicon: NAMASTE SAT-D (9,400 Sanskrit symptom phrases with English glosses) plus symptoms that occur only in NAMASTE clinical definitions.",
    "disease_symptom": "Disease → symptom edges parsed from NAMASTE clinical definitions (mention order kept).",
    "terminology": "Unified standard terminology from WHO (2022) and NAMASTE SAT: fundamentals, anatomy/physiology, diagnosis, pharmacology, pharmaceutics, diet, treatment and prevention, with WHO↔SAT cross-links.",
    "herbs": "Historical materia-medica master: botanical taxon links, non-botanical materials and unresolved identities are distinguished explicitly. Source names and herb IDs are retained; a linked taxon is not physical-material authentication. Includes SAT-F/Amidha names, properties, groups, safety states and evidence counts.",
    "herb_names": "Multilingual synonym table (Sanskrit IAST / Devanagari, Hindi, English, botanical synonyms).",
    "herb_indication": "Herb → NAMASTE disease links (from Amidha indications; match method and score kept).",
    "herb_karma": "Herb → pharmacological action (karma), mapped to the controlled vocabulary.",
    "herb_groups": "Caraka's 50 mahākaṣāya (therapeutic groups of ten herbs) from SAT-F.",
    "herb_group_members": "Members of each mahākaṣāya with botanical identity and herb link.",
    "herb_phytochemicals": "USDA Duke: phytochemicals reported per plant and part, with amounts (ppm) and references.",
    "phytochemical_activities": "USDA Duke: reported biological activities of those chemicals.",
    "herb_ethnobotany": "USDA Duke: documented ethnobotanical uses in India (incl. Ayurvedic and tribal sources).",
    "diagnostic_methods": "Classical Ayurvedic examination methods (trividha, ṣaḍvidha, aṣṭasthāna, daśavidha, nidāna pañcaka, kriyākāla …) with classical references, WHO/SAT ids and integrative modern counterparts; also computational and biomedical methods.",
    "therapies": "Treatment terminology (WHO ch. 9 + SAT-I), tagged pañcakarma / pūrvakarma / rasāyana / surgery / external therapy …",
    "pharmaceutics": "Dosage forms and pharmaceutical processes (WHO ch. 7 + SAT-G).",
    "diet_lifestyle": "Diet, daily/seasonal regimen and preventive health (WHO ch. 8, 10 + SAT-H, J).",
    "formulations": "43 classical compound formulations (curated from classical texts, flagged for expert verification) with dosage form, indications, doṣa action, safety and evidence counts.",
    "formulation_ingredients": "Ingredients of each formulation, linked to the historical materia-medica master where possible. A nonempty herb_id can refer to a non-botanical material; ingredient_type preserves that distinction.",
    "formulation_indications": "Formulation → NAMASTE disease links.",
    "clinical_trials": "ClinicalTrials.gov studies registered for each herb or formulation (modern evidence).",
    "evidence_queries": "Every PubMed / ClinicalTrials.gov query issued, with its result count (reproducibility).",
    "therapy_evidence": "PubMed counts for key therapies (pañcakarma, śirodhārā, kṣārasūtra …).",
    "controlled_vocabulary": "Trilingual controlled vocabulary: doṣa, rasa, guṇa, vīrya, vipāka, plant parts, karma.",
    "qa_pairs": "Bilingual (EN / HI) question-answer pairs generated from KB records, each traceable to record ids.",
    "prakriti_synthetic_cohort": "SYNTHETIC Prakṛti questionnaire cohort (3,000 simulated people) generated from WHO ITA-2.8.3–2.8.5 trait definitions, for training/benchmarking constitution classifiers.",
    "sources": "Provenance and licence of every source.",
    "case_reports": "REAL-WORLD layer: 565 published Ayurveda case reports / case series (Europe PMC), with the Ayurvedic diagnosis mapped to NAMASTE, presenting symptoms, herbs, formulations, procedures, modern assessments (lab, imaging, scales) and, for adverse-event reports, the implicated metals. Text-mined with the KB lexicons; bibliographic metadata, extracted identifiers and short source-derived phrases; full article caches are excluded.",
    "case_report_entities": "Every entity mention extracted from each case report (symptom, herb, formulation, formulation name not in the KB, procedure, modern assessment, implicated metal) with its KB ids.",
    "case_report_links": "Diagnosis x herb / formulation co-occurrences across real case reports, with a flag telling whether the KB already records the link for that disorder family (curation queue, not merged).",
    "herb_indication_evidence": "PubMed co-occurrence evidence for every herb -> disorder link: paper counts, clinical-study counts, lift over chance, top PMIDs and an evidence tier (clinical_evidence / literature_supported / sparse / no_literature / not_queryable).",
    "formulation_indication_evidence": "Same literature evidence for every formulation -> disorder link.",
    "therapy_disease": "Disorder -> procedure links (WHO/SAT therapy records) from explicit classical rules with references (site-specific procedures, disorder protocols, category principles, the doṣa principle of Caraka Sū 25.40), iatrogenic complications, and procedures observed in published case reports.",
    "multiscript_names": "Every Devanagari name (disorders, symptoms, herbs, formulations, terminology, therapies) transliterated into Bengali, Gujarati, Gurmukhi, Kannada, Malayalam, Odia, Tamil and Telugu scripts.",
    "headword_concepts": "Cross-source lexical concepts: records of WHO, SAT, NAMASTE, symptom, therapy, herb and formulation tables that share a Sanskrit headword (skeleton key).",
    "concept_members": "Members of each headword concept (entity type, id, source, term, English gloss).",
    "phytochemicals": "Phytochemicals with a recorded activity or present in >= 3 herbs, resolved to PubChem CID, InChIKey, formula, molecular weight, SMILES and IUPAC name (public domain).",
    "herb_image_datasets": "Species-level links from KB herbs to three CC BY 4.0 medicinal-plant image datasets (Mendeley Data), for plant-identification models.",
    "disease_symptom_who": "Disorder → symptom edges from the sign lists in WHO (2022) definitions, mapped to the SAT symptom lexicon (exact gloss, else shortest entry containing every word). Broad 'some or all of the following' lists: use to explain a disorder, not to rank candidates (lowered matcher accuracy in E6b).",
    "disease_symptom_inferred": "FLAGGED inference: disorders with no symptom profile of their own inherit the profile of their nearest ancestor (healthy states, interventions and prodromes excluded).",
    "disease_symptom_from_cases": "Disorder → symptom associations learned from published case reports (count of reports), for the expert system's matcher. Not curated.",
    "dosha_suggestions": "MODEL SUGGESTIONS (not authoritative) for disorders whose doṣa is unspecified: suggested doṣa, confidence, second choice and margin; for expert confirmation in the Review Desk.",
    "case_report_symptoms_semantic": "Complaint clauses of case reports matched to SAT symptoms by multilingual embeddings (clause text, symptom id, similarity).",
}
COL_DOC = {
    "ingredient_type": "herb / herb (unlinked) / mineral/animal/other; linked non-botanical material IDs retain the latter category",
    "material_type": "botanical_taxon_linked / non_botanical_material / identity_unresolved; source classification, not clinical approval",
    "taxon_identity_status": "linked_gbif_taxon / unresolved / not_applicable_non_botanical",
    "material_type_source_id": "Source supporting the material category (S7 for a taxon linkage; S2/S5 for recorded non-botanical source categories)",
    "material_type_source_record": "GBIF key or exact recorded source/category locator",
    "material_type_note": "Category evidence and scope limitations; no species identity inferred from higher-rank fallback",
    "safety_assessment_status": "unassessed / review_pending / assessed; independent of hazard classification and never a blanket safe-use claim",
    "safety_review_reviewer": "Reviewer identifier supplied with the scoped safety assessment; qualifications require separate verification",
    "safety_review_reference": "Source evidence supporting the scoped safety assessment",
    "safety_review_assessment_date": "Assessment date (YYYY-MM-DD)",
    "safety_review_scope": "Species, preparation, population or other scope of the recorded assessment",
    "mapping_status": "source_matched_unreviewed / candidate_review_pending / quarantined / unmatched / alias_reviewed; only active disease_id supplies a link",
    "mapping_reason": "Reason for containment, ambiguity or a supplied reviewed alias decision",
    "mapping_reference": "Evidence for the mapping decision; a PDF review finding is containment evidence, not expert approval",
    "candidate_disease_ids": "Proposed disorder IDs retained for review; these are not accepted links",
    "original_disease_id": "Historical target before containment or alias correction; not an active assertion",
    "original_disease_term_iast": "Historical target name retained for audit only",
    "original_disease_name_en": "Historical English target name retained for audit only",
    "original_match_method": "Historical matching method before the current policy",
    "original_match_score": "Historical spelling-similarity score; not a probability of semantic correctness",
    "match_method": "Entity-linking procedure (for example exact_skeleton, exact_gloss or gbif_accepted_key)",
    "term_iast": "Sanskrit term in IAST transliteration", "term_deva": "Sanskrit term in Devanagari",
    "term_hi": "Form used in Hindi (Sanskrit stem without case ending, Hindi orthography)",
    "name_en": "English name", "name_en_hi": "Hindi translation of the English name (machine translation, see *_method / *_qe_flags)",
    "definition_en": "English definition / description", "definition_hi": "Hindi translation of the definition (NLLB-200 + Ayurveda glossary; QE flags)",
    "icd11_tm2_code": "WHO ICD-11 Traditional Medicine Chapter (TM2) code embedded in the NAMASTE code",
    "namc_code_clean": "NAMASTE morbidity code", "parent_disease_id": "Parent node in the NAMASTE hierarchy",
    "dosha_label": "Doṣa(s) involved: vata / pitta / kapha combinations or 'unspecified'",
    "dosha_source": "'term' = stated in the term itself, 'ancestor' = inherited from a parent category",
    "accepted_name": "Currently accepted botanical name (GBIF Backbone)", "gbif_key": "GBIF taxon key",
    "name_sa_iast": "Official Sanskrit name (IAST)", "name_hi_common": "Hindi common name (Wikidata)",
    "name_hi_ayurvedic": "Sanskrit name in Hindi usage form", "rasa": "Taste(s)", "guna": "Qualities", "virya": "Potency (Ushna = hot, Sheeta = cold)",
    "vipaka": "Post-digestive effect", "karma_actions": "Pharmacological actions", "dosha_pacify": "Doṣas pacified",
    "dosha_aggravate": "Doṣas aggravated", "safety_class": "mahāviṣa / upaviṣa / caution class", "requires_shodhana": "Classical purification required before use",
    "pubmed_count": "PubMed papers mentioning the name in title/abstract", "pubmed_ayurveda_count": "Same, restricted to Ayurveda context",
    "clinicaltrials_count": "ClinicalTrials.gov registered studies", "source_id": "Source (see sources table)", "licence": "Licence of the row",
    "data_origin": "authoritative / community_open / integrated / curated / derived / synthetic", "qa_flag": "Data-quality flag raised during processing",
    "evidence_tier": "clinical_evidence (>=1 trial/RCT/meta-analysis) / literature_supported (>=3 papers, lift >= 2) / sparse / no_literature / not_queryable",
    "lift": "Co-occurrence over chance: N x n_pair / (n_entity x n_disorder); > 1 = studied together more often than chance",
    "n_pair": "PubMed papers mentioning both the entity and the disorder's biomedical concept", "n_clinical": "Of those, clinical trials / RCTs / meta-analyses / systematic reviews",
    "relation": "Kind of link (site_specific_procedure, disorder_protocol, category_principle, dosha_principle_generic, iatrogenic_complication_of, observed_in_published_cases)",
    "strength": "specific / category / generic / observed", "reference": "Classical text reference or supporting case reports",
    "case_kind": "therapeutic (Ayurvedic management) or adverse_event (toxicity / poisoning associated with an Ayurvedic product)",
    "dx_disease_ids": "NAMASTE disorder(s) named as the Ayurvedic diagnosis (title > keywords > abstract)",
    "pubchem_cid": "PubChem compound id", "inchikey": "Standard InChIKey", "concept_id": "Headword concept id (AYC-...)",
    "definition_source": "Where the definition comes from: NAMASTE, or WHO ITA 2022 (linked term) when NAMASTE has none",
    "definition_locator": "Exact source of the definition text: the NAMASTE morbidity code, or the WHO term ID and PDF page (stage 55)",
    "source_locator": "Exact source of the term: WHO term ID and PDF page of WHO ITA 2022, or the NAMASTE SAT code (stage 55)",
    "suggested_dosha": "Doṣa suggested by the text model (review before use)", "confidence": "Model probability of the suggestion",
    "margin": "Probability gap between the first and second choice (small = model unsure)",
    "inherited_from": "Ancestor disorder whose profile was inherited", "sign_text_who": "The sign as written in the WHO definition",
}

def main():
    out = ["# Data dictionary", "", "Generated by `scripts/09_docs.py` from the files in `data/processed/`.", ""]
    summary = {}
    for f in sorted(P.glob("*.csv")):
        df = pd.read_csv(f, keep_default_na=False, low_memory=False)
        name = f.stem
        summary[name] = dict(rows=len(df), columns=df.shape[1])
        out += [f"## `{name}`  ({len(df):,} rows × {df.shape[1]} columns)", "", TABLE_DOC.get(name, ""), "",
                "| column | type | filled | example | description |", "|---|---|---|---|---|"]
        for c in df.columns:
            s = df[c]
            filled = (s.astype(str).str.strip() != "").mean()
            ex = next((str(v) for v in s if str(v).strip()), "")
            ex = (ex[:60] + "…") if len(ex) > 60 else ex
            ex = ex.replace("|", "\\|").replace("\n", " ")
            typ = "number" if pd.api.types.is_numeric_dtype(s) else "bool" if pd.api.types.is_bool_dtype(s) else "text"
            desc = COL_DOC.get(c, "")
            if not desc and c.endswith("_qe_flags"):
                desc = "Automated translation quality flags (empty does not establish human validation)"
            if not desc and c.endswith("_method"):
                desc = "How the Hindi text was produced (glossary_exact / nllb200_600m_glossary_injected)"
            out.append(f"| `{c}` | {typ} | {filled:.0%} | {ex} | {desc} |")
        out.append("")
    (ROOT / "docs/DATA_DICTIONARY.md").write_text("\n".join(out), encoding="utf-8")
    (ROOT / "reports/kb_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"documented {len(summary)} tables")

if __name__ == "__main__":
    main()
