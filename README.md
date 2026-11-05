# AyurKB: a bilingual, hybrid Ayurveda knowledge base for expert systems

AyurKB links Ayurvedic **diagnosis, materia medica, remedies and modern scientific evidence** in one
relational dataset. It is in **English and Hindi**, with every Sanskrit term in **IAST and Devanagari**.
It was built only from authoritative or openly licensed sources (Ministry of Ayush NAMASTE, WHO, USDA,
GBIF, Wikidata, NLM, PubChem, Europe PMC and one DOI-registered CC-BY herb database), cleaned and cross-validated,
checked against 565 published case reports, and benchmarked with 16 machine-learning setups across 7 experiments.

> Decision-support data, not medical advice. Curated layers are flagged for expert review (see *Limitations*).

## What's inside (`data/processed/`, CSV + Parquet; `release/ayurkb.sqlite`)

| Area | Table | Rows | Highlights |
|---|---|---:|---|
| **Diagnosis** | `diseases` | 2,892 | NAMASTE morbidity codes, hierarchy, 789 WHO ICD-11 TM2 codes, 1,188 linked to WHO terms, doṣa labels |
| | `symptoms` | 11,081 | SAT-D lexicon (9,400 Sanskrit symptom phrases + English glosses) and 1,681 more from NAMASTE definitions |
| | `disease_symptom` | 11,880 | disease → symptom graph parsed from clinical definitions |
| | `diagnostic_methods` | 43 | trividha, ṣaḍvidha, aṣṭasthāna (nāḍī, mūtra, jihvā …), daśavidha, nidāna pañcaka, kriyākāla, plus modern and computational counterparts with PubMed evidence |
| **Herbs** | `herbs` | 466 | official Sanskrit names, GBIF-accepted botanical names, Hindi names, rasa / guṇa / vīrya / vipāka / karma / doṣa, safety class, PubMed & trial counts |
| | `herb_indication`, `herb_karma`, `herb_names` | 1,693 / 829 / 3.6k | herb → disease, herb → action, multilingual synonyms |
| | `herb_groups`, `herb_group_members` | 50 / 500 | Caraka's 50 mahākaṣāya |
| **Remedies** | `formulations` (+ ingredients, indications) | 43 | classical compound remedies with classical source, dosage form, doṣa action, safety (curated, flagged) |
| | `therapies` | 1,325 | pañcakarma, pūrvakarma, rasāyana, surgery & para-surgery, external therapies |
| | `pharmaceutics`, `diet_lifestyle` | 393 / 381 | dosage forms and processes; pathya, dinacaryā, ṛtucaryā |
| **Terminology** | `terminology` | 6,233 | WHO (3,554) + NAMASTE SAT (2,679) standard terms with WHO↔SAT cross-links |
| **Modern science** | `herb_phytochemicals`, `phytochemical_activities` | 23.8k / 13.5k | USDA Duke phytochemistry and bioactivities |
| | `herb_ethnobotany` | 2.9k | documented Indian ethnobotanical uses |
| | `clinical_trials` | 6.4k links (5.3k trials) | ClinicalTrials.gov studies per herb and formulation |
| **Real world** | `case_reports`, `case_report_entities` | 565 / 8,023 | published Ayurveda case reports (Europe PMC): NAMASTE diagnosis, presenting symptoms, herbs, formulations, procedures, modern tests; 115 adverse-event reports with implicated metals |
| | `case_report_links` | 867 | diagnosis × medicine pairs seen in practice, flagged when the KB lacks them (curation queue) |
| **Evidence** | `herb_indication_evidence`, `formulation_indication_evidence` | 1,427 / 121 | PubMed co-occurrence, clinical-study counts, lift over chance, top PMIDs and an evidence tier for every link |
| **Remedies** | `therapy_disease` | 6,474 | disorder → procedure links from classical rules with text references, iatrogenic complications, procedures seen in case reports |
| **Linked data** | `phytochemicals` | 1,959 | PubChem CID, InChIKey, formula, SMILES for key phytochemicals |
| | `herb_image_datasets` | 214 | links to 3 CC BY 4.0 leaf-image datasets for plant identification |
| **Language** | `multiscript_names`, `headword_concepts` | 20,895 / 3,347 | names in 8 regional scripts; Sanskrit headwords shared across WHO, SAT and NAMASTE |
| **Accuracy layers** | `disease_symptom_who`, `disease_symptom_inferred` | 13,639 / 10,082 | symptom profiles from WHO definitions' sign lists; inherited profiles for subtypes (flagged) |
| | `disease_symptom_from_cases` | 3,905 | symptom associations learned from published case reports (used by the expert system) |
| | `dosha_suggestions` | 1,420 | **model suggestions** for disorders whose doṣa is unspecified (confidence, second choice); to be confirmed by experts |
| | `curation/clinical_symptom_crosswalk.csv` | 183 | modern clinical expressions → SAT symptoms (auto-mapped, to review) |
| **AI-ready** | `qa_pairs` | bilingual | Q&A generated from records (traceable ids) |
| | `prakriti_synthetic_cohort` | 3,000 | **synthetic** constitution questionnaire cohort (WHO-grounded) |
| | `release/ayurkb_corpus.jsonl`, `release/embeddings/` | 20k docs | RAG corpus and multilingual semantic index |

How the dataset covers the brief:

- **Remedies:** herb indications, mahākaṣāya groups, 43 classical formulations, therapies, diet and lifestyle.
- **Herbs:** 466 with full Dravyaguṇa profiles.
- **Diagnosing techniques:** classical examination methods with their references.
- **Old and modern methods:** classical texts and standards alongside phytochemistry, clinical trials,
  ICD-11 coding and computational diagnostics.
- **Hybrid:** authoritative, community and linked open data; tabular, text, graph and numeric records;
  real and clearly labelled synthetic or derived rows.
- **Bilingual:** English and Hindi, with Sanskrit in IAST and Devanagari.

## Pipeline

| Stage | Script | What it does |
|---|---|---|
| Fetch | `01_fetch_sources.py` | downloads every source through its official download/API; SHA-256 provenance manifest |
| Pre-process | `02a_parse_who.py` | WHO PDF → table by word coordinates; validated against the book's own index (99.85% of IDs) |
| | `02b_parse_namaste.py` | NAMASTE phonetic → IAST → Devanagari; repairs lost diacritics (vocabulary + char 4-gram LM, 90% of damaged tokens) |
| | `02c_parse_herbs.py` | SAT-F plant list, mahākaṣāya, karma; Amidha herbs; USDA Duke tables |
| | `03_enrich_taxonomy.py` | GBIF validation (97% of names resolved, synonyms updated, ambiguity left unresolved); Wikidata Hindi names |
| In-process | `04_build_kb.py` | integration, hierarchy, ICD-11 TM2, doṣa labels, symptom graph, herb master, safety, curated layers |
| | `05_evidence.py` | PubMed and ClinicalTrials.gov evidence |
| | `06_translate.py` | English → Hindi: NLLB-200 with Ayurveda glossary injection, Sanskrit protection, quality estimation |
| | `07_ml.py`, `10_crosslingual.py` | ML experiments E1–E5 |
| Post-process | `08_validate_export.py` | integrity checks, bilingual Q&A, RAG corpus, SQLite, Frictionless `datapackage.json` |
| | `09_docs.py`, `11_embed_index.py` | data dictionary; multilingual embedding index |
| Real world | `14_case_reports.py` | Europe PMC case reports → diagnosis, symptoms, herbs, formulations, procedures, modern tests, adverse events; experiment E6 |
| | `15_link_evidence.py` | PubMed evidence tier for every herb / formulation → disorder link |
| | `16_links_scripts_concepts.py` | disorder → procedure rules, 8 regional scripts, cross-source headword concepts |
| | `17_phytochem_ids.py`, `18_image_datasets.py` | PubChem identifiers (+ ChEMBL targets, separate file); plant-image dataset links |
| | `19_ictrp_import.py` | optional: import a manual WHO ICTRP / CTRI export (drops personal data) |
| | `20_tuning.py` | experiment E7: nested-CV hyperparameter tuning |
| | `21_review_workbooks.py`, `22_build_tools.py` | expert-review workbook (build / merge) and the interactive tools |
| Test | `tests/` | 80 automated checks (transliteration, keys, references, encoding, domain and safety rules, bilingual coverage, ML baselines) |

Rebuild everything with `bash run_all.sh` (about 2 h on 4 CPUs, mostly translation and API calls; responses are cached, so re-runs are fast). Dependencies:

```bash
pip install pandas pyarrow xlrd requests ftfy indic-transliteration rapidfuzz scikit-learn xgboost lightgbm matplotlib torch transformers sentencepiece pytest openpyxl defusedxml
```
```bash
bash run_all.sh
```

## Using it

```python
import pandas as pd
d = pd.read_csv("data/processed/diseases.csv", keep_default_na=False)
d[d.dosha_label == "pitta"][["namc_code_clean", "term_iast", "term_deva", "name_en", "name_en_hi", "icd11_tm2_code"]]
```

```sql
-- release/ayurkb.sqlite: herbs indicated for any kind of kāsa (cough), with safety flags
SELECT h.name_sa_iast, h.accepted_name, h.name_hi_common, h.virya, h.safety_class
FROM herb_indication i JOIN herbs h USING(herb_id) JOIN diseases d USING(disease_id)
WHERE d.term_iast LIKE '%kās%';
```

Expert-system demo (see `docs/EXPERT_SYSTEM_GUIDE.md`; lexical and multilingual semantic symptom matching, then disorder ranking, herbs,
formulations and the classical śodhana principle):

```bash
python3 examples/expert_system_demo.py --symptoms "fever; burning sensation; excessive thirst; vomiting"
```
```bash
python3 examples/expert_system_demo.py --symptoms "बुखार; जलन; अधिक प्यास" --lang hi
```

Literature evidence for a link, and what practitioners actually used in published cases:

```sql
SELECT h.name_sa_iast, h.accepted_name, e.evidence_tier, e.n_pair, e.n_clinical, e.clinical_pmids
FROM herb_indication_evidence e JOIN herbs h USING(herb_id) JOIN diseases d USING(disease_id)
WHERE d.term_iast = 'pramehaḥ' ORDER BY e.n_clinical DESC;
```

### Tools for experts and studies

- **Review Desk** (`release/tools/review_desk.html`): invited vaidyas give a verdict on each herb → disorder and
  procedure → disorder link; verdicts are stored per anonymous reviewer, the owner sees agreement (Fleiss' κ) and exports CSV.
- **Prakṛti questionnaire** (`release/tools/prakriti_questionnaire.html`): bilingual, with a consent screen, classical
  scoring (the E4 rule) and optional anonymous saving by the study team (interviewer mode).
- **Offline review workbook** (`review/AyurKB_expert_review.xlsx`): drop-down verdicts per sheet; return completed copies
  to `review/returned/` and run `python3 scripts/21_review_workbooks.py --merge`.
- **Permission letters** (`docs/permission_requests/`): ready-to-send requests to PCIM&H (API/AFI), Ministry of Ayush
  (NAMASTE licence), WHO, the IMPPAT team and CCRAS.

## Machine-learning results

See `reports/ml/` (JSON/CSV per experiment), `reports/figures/` and `release/report.html`.

<!-- ML_TABLE_START -->
| Exp. | Task | Data | Best model | Score | Reference point |
|---|---|---|---|---|---|
| E1a | Disorder → organ system from clinical text | real · NAMASTE | Logistic Regression | macro-F1 0.801 | Dummy (majority) 0.034 |
| E1b | Doṣa involvement from symptom text (doṣa words masked) | real · NAMASTE | Logistic Regression | macro-F1 0.738 | Dummy (majority) 0.145 |
| E1c | Same task in English vs Hindi text | real · NAMASTE | Logistic Regression · English | macro-F1 0.801 | Dummy (majority) · English 0.034; Dummy (majority) · Hindi (MT) 0.034 |
| E2a | Herb vīrya (uṣṇa / śīta) from rasa, guṇa, vipāka, karma | real · herbs | Extra Trees | macro-F1 0.797 | rule: rasa majority (hot vs cold tastes) 0.760; rule: vipāka (madhura -> śīta) 0.635 |
| E2b | Doṣa-pacifying profile (V / P / K, mean of three labels) | real · herbs | SVM (RBF) | macro-F1 0.857 | Classical rule (Ayurvedic theory) 0.743; Dummy (majority) 0.376 |
| E2c | Herb indications from rasa / guṇa / vīrya / vipāka / doṣa | real · herbs | LightGBM | macro-F1 0.604 | Dummy (majority) 0.453 |
| E3a | Symptom set → disorder (60 disorders) | hybrid · simulated cases | MLP (neural net) | top-1 accuracy 0.928 | Knowledge-base matcher (IDF-cosine, no training) 0.967; Dummy (majority) 0.017 |
| E3b | Symptom set → disorder (all distinguishable disorders) | hybrid · simulated cases | Naive Bayes | top-1 accuracy 0.882 | Knowledge-base matcher (IDF-cosine, no training) 0.893 |
| E4 | Prakṛti (7 constitution types) from questionnaire | synthetic · WHO-grounded | Naive Bayes | macro-F1 0.653 | Classical questionnaire scoring (count V/P/K answers) 0.618; Dummy (majority) 0.053 |
<!-- ML_TABLE_END -->

**E6, real case reports.** On 85 published cases with a NAMASTE diagnosis and two or more presenting symptoms, the
no-training KB matcher ranks the diagnosed disorder family in its top 10 for 20% of cases (top 30: 32%),
against 9% for a popularity baseline and 0.6% by chance among 1,595 disorders.
Case reports describe patients in modern clinical language, which the classical symptom lexicon only partly covers.
Only 13% of the diagnosis–herb pairs seen in practice are recorded in the KB, so
`case_report_links` doubles as a curation queue.

**E7, tuning.** Nested cross-validation changes macro-F1 by −0.02 to +0.10. Tuning helped models with poorly suited defaults
(Complement NB on text, Random Forest on the questionnaire) and slightly hurt on the 344-herb dataset, where the inner search overfits.

**Link evidence.** Of 1,427 herb → disorder links, 204 have at least one clinical study in PubMed,
241 have supporting literature, 431 are sparse and 518 have none (classical use only).

## Accuracy upgrades (E8)

Measured on the same rows and folds as the original experiments (generated by `scripts/12_report.py`):

<!-- UPGRADES_START -->
| Area | Before | After | What changed |
|---|---|---|---|
| Real cases: right disorder group in top 10 | 20% | 48% (±4%) | clinical-term crosswalk, meaning-based matching, group ranking, profiles learned from real cases (5-fold CV) |
| Real cases: right group ranked first | 2% | 17% | same |
| Adding WHO sign lists to the matcher (top 10) | 28% | 11% | made it worse: the lists are broad, so they are kept for explanation and left out of ranking |
| Real cases, top 10, with the fine-tuned search model | 48% | 47% | no gain on English case text (within ±4% noise); the fine-tuned model is used for Hindi search, where it helps |
| Search disorders by Sanskrit headword (recall@10) | 0.24 | 0.56 | search model fine-tuned on the dataset's own pairs, test concepts held out |
| Search symptoms by Sanskrit headword (recall@10) | 0.20 | 0.45 | search model fine-tuned on the dataset's own pairs, test concepts held out |
| Organ system from text (E1a), macro-F1 | 0.801 | 0.837 | TF-IDF + e5 + LR |
| Doṣa from symptom text (E1b), macro-F1 | 0.738 | 0.750 | TF-IDF + e5 + LR |
| Same task in Hindi (E1c), macro-F1 | 0.724 | 0.802 | TF-IDF + e5 + LR |
| Herb indications (E2c), macro-F1 | 0.604 | 0.603 | + chemistry + family: no meaningful gain - phytochemistry does not predict classical indications here |
| Disorders with a definition | 55.5% | 69.8% | 415 WHO definitions for disorders NAMASTE leaves undefined |
| Disorders with a symptom profile | 1,595 | 2,243 | 13,639 edges from WHO sign lists + inherited profiles for subtypes (flagged) |
| Disorders with a doṣa suggestion | 0 | 1,420 | text model, cross-validated accuracy 0.90; flagged for expert review |
| Hindi translation errors fixed by rule | - | 35 rows | e.g. 'stiffness' had been translated as 'bitterness' |
<!-- UPGRADES_END -->

## Status and next steps

Where the work stands (release v1.2) and what to pick up next:

- **Done:** all 26 pipeline stages, experiments E1–E8, 87 automated checks, the dataset report, the Review Desk and the
  Prakṛti questionnaire (published as claude.ai artifacts; their source pages are in `release/tools/`).
- **Needs experts:** collect verdicts with the Review Desk or `review/AyurKB_expert_review.xlsx`, then run
  `python3 scripts/21_review_workbooks.py --merge`. Start with the "possible name-mapping error", "model unsure" and
  "seen in case reports" items.
- **Needs you:** send the letters in `docs/permission_requests/`; get ethics approval before collecting Prakṛti
  responses; have a Hindi speaker correct the flagged translations (sheet `hindi_translations`).
- **ChEMBL targets:** built (323 compound-target links, 62 compounds, 196 human proteins) in `release/chembl/`, kept out of
  git because ChEMBL is share-alike; rebuild with `python3 -I scripts/17_phytochem_ids.py --chembl-only`.
- **Optional input:** a WHO ICTRP / CTRI export for `scripts/19_ictrp_import.py`.

Large files are not versioned and are rebuilt locally: model weights (`scripts/00_get_models.py`, then stage 23 for the
fine-tuned search model), the SQLite database and search corpus (stage 08), the embedding indexes (stage 11) and the
release zip (stage 13). Cached API responses and translations are versioned in `data/interim/cache/`, so a re-run
needs no new translation and few network calls.

## Limitations and responsible use

- Not for autonomous diagnosis or prescribing; no doses are given.
- Curated layers (`curation/`: formulations, diagnostic correspondences, safety list, glossary,
  questionnaire, taxonomy overrides) need review by a qualified Ayurveda expert. Formulations should be
  checked against the Ayurvedic Formulary of India.
- Hindi descriptions are machine-translated. They are labelled with `*_method` and `*_qe_flags`; quality
  estimates are in `reports/translation_qe.json`.
- The Prakṛti cohort is synthetic. E4 metrics show how well models recover the generating model, not
  clinical accuracy. E3 uses simulated presentations built from the real disease–symptom graph.
- Herb properties come from one community source (344 herbs) and reflect one reading of the classical texts.
- Case-report entities are text-mined with the KB lexicons (precision over recall). Literature tiers are PubMed
  co-occurrence counts: a pointer to evidence, not proof of efficacy.
- Procedure links are rule-based from classical references; generic doṣa-principle links (`strength = generic`) need
  patient-level judgement (strength, age, season, contraindications).

## Licence and attribution

Combined release: **CC BY-NC-SA 4.0**. This is required by the WHO component (CC BY-NC-SA 3.0 IGO) and
the NLLB-200 licence. Each row carries `source_id` and `licence`, so a commercial-safe subset can be cut.
Please attribute: Ministry of Ayush, Govt. of India (NAMASTE); World Health Organization (2022); USDA-ARS
Dr. Duke's databases; Amidha Ayurveda Herb Database (S. Varshney, Zenodo 10.5281/zenodo.20581467); GBIF;
Wikidata; NLM (PubMed, ClinicalTrials.gov, PubChem); Europe PMC; the authors of the MED117, Medicinal Leaf and Indian
Medicinal Leaves image datasets (Mendeley Data, CC BY 4.0). ChEMBL-derived targets are distributed separately
under CC BY-SA 3.0 (`release/chembl/`). Details: `docs/SOURCES.md`, `docs/DATASHEET.md`,
`docs/DATA_DICTIONARY.md`, `docs/EXPERT_SYSTEM_GUIDE.md`.
