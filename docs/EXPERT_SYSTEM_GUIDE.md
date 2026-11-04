# Building an Ayurveda expert system on AyurKB

A reference architecture. `examples/expert_system_demo.py` implements modules 1–5 in about 200 lines.

```
 complaint text (EN / HI / Sanskrit)
        │
 1. Symptom normalisation  ── symptoms (+ release/embeddings/symptoms.npy for semantic matching)
        │
 2. Differential diagnosis ── disease_symptom graph · diseases (hierarchy, doṣa, ICD-11 TM2)
        │                     optional learned ranker: models/trained/E3_symptom_to_disease_naive_bayes.joblib
 3. Constitution context   ── models/trained/E4_prakriti_classifier.joblib (questionnaire: curation/prakriti_questionnaire.csv)
        │
 4. Knowledge retrieval    ── herb_indication · herbs · formulation_indications · formulations · therapies · diet_lifestyle
        │
 5. Safety & evidence gate ── herbs.safety_class / requires_shodhana · formulations.contains_metal_or_toxic
        │                     herbs.pubmed_count / clinicaltrials_count · clinical_trials
 6. Bilingual explanation  ── *_hi columns · controlled_vocabulary · qa_pairs · ayurkb_corpus.jsonl (RAG)
        ▼
 practitioner review (mandatory)
```

## 1. Symptom normalisation

- **Lexical.** Accept a lexicon entry only if it contains every content word of the complaint; prefer
  short, specific entries. This avoids matching "excessive thirst" to the bare word "excessive".
- **Semantic.** Encode the complaint with `intfloat/multilingual-e5-small` using the `query: ` prefix and
  take the nearest `symptoms.npy` vectors (the index was built with `passage: `). This bridges synonyms
  ("loss of appetite" → *aruci*) and Hindi input ("बुखार" → *jvara*).
- Keep up to about 25 entries per complaint. Many SAT-D entries are near-synonyms.

## 2. Differential diagnosis

Rank disorders by the number of complaints they explain, then by IDF-weighted overlap with the disorder's
symptom profile. Also count a complaint as explained when it names the disorder itself: match it against
`name_en`, `name_en_who` and `term_hi` (for example "cough" → *kāsa*).

In experiment E3 this no-training matcher reached 0.967 top-1 on 60 disorders, ahead of every learned
model (`reports/ml/E3a_top60.json`). Learned rankers add value when they are trained on real case data.

Walk `parent_disease_id` upward to collect knowledge recorded at the general level (e.g. *jvara*).

## 3. Constitution (Prakṛti)

The bundled classifier was trained on a **synthetic** cohort. Use it to demonstrate the workflow, or
retrain it on real questionnaire data. Its abstain-and-refer curve is in `reports/ml/E4_prakriti.json`:
answer automatically only above a confidence threshold and refer the rest.

## 4. Knowledge retrieval

| Need | Query |
|---|---|
| single herbs for a disorder | `herb_indication` ⋈ `herbs` on `herb_id`, filtered by `disease_id` ∈ {disorder and its ancestors} |
| classical formulations | `formulation_indications` ⋈ `formulations` (curated; verify against the AFI) |
| purification principle by doṣa | vāta → basti, pitta → virecana, kapha → vamana (Caraka Saṃhitā Sūtrasthāna 25.40); `therapies` tagged `pañcakarma` |
| diet and regimen | `diet_lifestyle` (pathya, dinacaryā, ṛtucaryā) |
| what a herb does | `herbs.rasa / guna / virya / vipaka / dosha_*`, `herb_karma`, `herb_groups` (mahākaṣāya) |

## 5. Safety and evidence gate (do not skip)

- Never suggest a herb with `safety_class` *mahāviṣa* or *upaviṣa* without an explicit warning. These
  require classical purification (`requires_shodhana = yes`) and specialist supervision.
- Formulations with `contains_metal_or_toxic` starting with "yes" contain processed metals or minerals,
  or toxic herbs. Surface the warning and recommend quality-tested products only.
- Show `pubmed_count`, `clinicaltrials_count` and the linked `clinical_trials` as research volume, not as
  proof of efficacy.
- AyurKB gives no doses. Dosing belongs to the practitioner.

## 6. Bilingual output

- Sanskrit terms: Devanagari plus the Hindi usage form (`term_hi`).
- Descriptions: `*_hi` columns. When `*_hi_qe_flags` is non-empty, prefer the English text or show both.
- Controlled values (rasa, guṇa, vīrya, vipāka, doṣa): `controlled_vocabulary.hi`.

## 7. Evidence, procedures and real-world signals (extension layers)

- **Evidence tier per link.** Join `herb_indication_evidence` / `formulation_indication_evidence` on
  (herb_id or form_id, disease_id). Show the tier next to every suggested herb: `clinical_evidence` (at least one trial,
  RCT, meta-analysis or systematic review co-mentioning the plant and the disorder's biomedical concept),
  `literature_supported` (3+ papers, lift >= 2), `sparse`, `no_literature`. A tier is a pointer to literature, never a
  claim of efficacy; the PMIDs let a practitioner check.
- **Procedures.** `therapy_disease` gives classical procedures with their text references. Prefer `strength` =
  `specific` (site-specific procedures, disorder protocols) and `category`; treat `generic` (the doṣa principle of Caraka
  Sū 25.40) as background reasoning only. Rows with relation `iatrogenic_complication_of` are complications, not
  indications. Śodhana rows carry the caution that strength, age, season and contraindications decide.
- **What practitioners report.** `case_report_links` lists medicines used for a diagnosis in published case reports
  (`n_cases`), flagged when the KB has no such link. Show them as "reported in practice", separately from curated links.
- **Safety signals.** `case_reports` with `case_kind = adverse_event` (115 reports, mostly lead, arsenic and mercury
  poisoning from metal-containing products) support the safety gate in section 5: products with
  `contains_metal_or_toxic = yes` need quality-tested sources and supervision.
- **Measured accuracy on real cases (E6).** A symptom-only matcher ranks the right disorder family in the top 10 for
  about a fifth of real presentations. Use it to suggest candidates for the practitioner, never to decide.
- **Plant identification.** `herb_image_datasets` maps KB herbs to classes of three CC BY 4.0 leaf-image datasets, so a
  classifier trained on them can hand its prediction to the KB.
- **Regional scripts.** `multiscript_names` lets the interface show Sanskrit names in Bengali, Gujarati, Gurmukhi,
  Kannada, Malayalam, Odia, Tamil or Telugu script.

## 8. Expert review loop

Use `release/tools/review_desk.html` (published as an artifact; invite reviewers as editors) or the offline workbook
`review/AyurKB_expert_review.xlsx`. Merge returned workbooks with `python3 scripts/21_review_workbooks.py --merge`;
verdicts land in `curation/expert_reviews.csv` with inter-rater agreement in `reports/expert_review_agreement.json`.
Apply corrections to the curated layers only after two reviewers agree.

## 9. Accuracy upgrades you can use directly

- **Symptom matching on real descriptions.** Use `curation/clinical_symptom_crosswalk.csv` (modern clinical
  expressions → SAT symptoms, auto-mapped, to be reviewed) before lexical matching, then the multilingual embedding
  index for anything left over.
- **Richer disorder profiles.** Rank with `disease_symptom` + `disease_symptom_from_cases` (symptoms seen in published
  cases). Do NOT add `disease_symptom_who` to the ranking: WHO sign lists are broad "some or all of the following" lists
  and lowered real-case top-10 accuracy from 28% to 11% (E6b). Use them to explain a candidate, not to rank it.
  `disease_symptom_inferred` (inherited from a parent) is roughly neutral and is a fallback for disorders with no profile.
- **Rank disorder groups first.** Collapse subtypes to their group (depth-3 ancestor), show the top groups, then let
  the practitioner pick the doṣa subtype. On real cases this, plus case-learned profiles, raised top-10 accuracy from
  about 20% to about 49% (experiment E6b).
- **Doṣa suggestions.** `dosha_suggestions` proposes a doṣa for disorders the sources leave unspecified. Treat as a
  hint until an expert confirms it in the Review Desk.

## Evaluation checklist before deployment

1. Re-run `python3 -m pytest tests/`.
2. Have an Ayurveda expert review the `curation/` files.
3. Evaluate on real, consented case records. The E3 and E4 benchmarks are simulated.
4. Log every suggestion together with the record ids that produced it. Every table has stable ids, so
   explanations stay traceable.
