# AyurKB: current dataset peer review

**Review date:** 7 November 2026 (UTC)

**Repository:** IAbdullahSlash/Ayurveda-dataset

**Assessed snapshot:** `73bbd3189a0ad70a524375bb1302d0a32b7c3a44`

**Scope:** Current processed data, source and review records, implementation, evaluation artifacts, release validation, and suitability for research and practical use.

## Overall assessment

AyurKB is a substantial integration of Ayurvedic terminology, disorder descriptions, herbs, formulations, symptom relationships, literature links, and multilingual representations. Its strongest present contribution is an inspectable research knowledge base with working retrieval and reproducible computational experiments. Its breadth and explicit links between otherwise separate resources make it useful for terminology research, exploratory knowledge graphs, source-aware search, and testing data-processing methods.

The current revision is materially stronger than the version assessed in the supplied 5 November peer review. Important preprocessing, export, identity, attribution, and packaging defects have been addressed, and affected computational experiments have been rerun. Those improvements deserve credit. The main remaining weaknesses are incomplete and uneven coverage, unadjudicated semantic content and translations, selective safety information, unresolved component permissions, and the absence of an independently adjudicated clinical test set.

**Recommendation:** Suitable for exploratory research and supervised information retrieval, subject to applicable source terms and visible uncertainty. **Major revision remains appropriate for claims of a clinically validated knowledge resource.** Current evidence does not support autonomous diagnosis, treatment selection, prescribing, or a claim that the combined release is cleared for commercial reuse. This is a technical peer-review judgment, not a journal decision or a clinical or legal approval.

| Dimension | Current assessment |
|---|---|
| Contribution | Useful integration; superiority or novelty relative to other Ayurveda resources still needs a systematic comparison. |
| Structural condition | Substantially improved, with validation gates, persistent IDs, tested exports, and executable examples. |
| Knowledge quality | Mixed: authoritative source material coexists with inferred, translated, community-sourced, and model-generated content. |
| Coverage | Broad terminology coverage, but shallow and uneven clinical and therapeutic coverage. |
| Computational viability | Good for bounded research tasks with frozen inputs and correctly scoped claims. |
| Clinical viability | Unestablished; expert adjudication, safety assessment, and independent clinical evaluation remain necessary. |
| Reuse viability | Conditional on component-level permission and attribution decisions. |

## Review method and evidence boundary

This assessment uses direct counts from all 43 current processed CSVs and a fresh inspection of the expert workbook and rights ledger. A machine-readable companion records the counts, reviewed commit, and SHA-256 hashes of every CSV: [current audit](../reports/peer_review_current_audit.json). The supplied Word review was treated as an earlier assessment to compare against the current repository, rather than as instructions to execute.

Benchmark and software-test results below come from the repository's recorded execution artifacts. Models and the full test suite were not rerun solely to write this report. Benchmarks refer to their frozen input snapshots; later content repairs do not constitute a new benchmark run. The latest recorded suite reports **136 passed, zero failed, zero skipped, and zero errors**. Historical case-matching results are identified separately because they were not reproduced in the latest network-enabled run. Neither software tests nor this review substitute for independent clinical, linguistic, or rights review.

## 1. Composition, coverage, and present condition

The dataset contains **181,333 rows across 43 tables**. This is a count of heterogeneous entities, links, derived representations, and synthetic records. It is not a patient count or a count of independent verified assertions. Disorder rows also include categories and patterns, so coverage percentages describe repository records rather than a definitive inventory of individual diseases.

| Component | Current observation | Interpretation |
|---|---:|---|
| Disorders | 2,892 | Substantial terminology and hierarchy coverage. |
| English disorder definitions | 2,019/2,892 (69.8%) | 873 records remain undefined in English. |
| WHO-linked disorders | 1,188/2,892 (41.1%) | A cross-link does not establish complete semantic equivalence. |
| Records with ICD-11 TM2 codes | 789/2,892 (27.3%) | Count of populated rows, not unique codes or adjudicated mappings. |
| Base symptom profiles | 1,595/2,892 (55.2%) | Many disorders lack direct extracted profiles. |
| Expanded symptom profiles | 2,243/2,892 (77.6%) | Combines base, WHO, and inherited layers; 649 remain uncovered. |
| Symptom master / base symptom links | 11,082 / 11,883 | Vocabulary breadth exceeds independently established extraction accuracy. |
| Unspecified doṣa | 1,956/2,892 (67.6%) | 1,420 model suggestions remain unconfirmed. |
| Herbs / complete core-property records | 466 / 344 (73.8%) | 122 lack rasa, guna, vīrya, vipāka, and karma fields. |
| Herb indications | 1,693 | 261 (15.4%) lack a linked disorder ID. |
| Directly linked disorders in herb indications | 105/2,892 (3.6%) | Therapeutic coverage is concentrated in a small subset of the disorder inventory. |
| Formulations / ingredient rows | 43 / 500 | Formulation coverage is small relative to terminology coverage. |
| Clinical-trial links / distinct trial IDs | 6,435 / 5,289 | Registrations can link to several entities; registration does not imply a positive result. |
| Published case-report records | 565 | 450 therapeutic and 115 adverse-event records; not necessarily 565 individual patients. |
| QA pairs | 4,836 | Mostly templated from the same knowledge base, not independently authored user questions. |
| Synthetic prakṛti cohort | 3,000 | Generated questionnaire records, not observed clinical participants. |
| Multiscript name rows | 20,895 | Transliteration-derived coverage is not equivalent to native-language validation. |

Missingness is not evenly distributed. For example, the system-coverage table records no direct herb links for 242 iatrogenic-disorder records, while 59 of 1,003 body-channel disorder records have such links. Some gaps reflect the appropriate scope of a category rather than an error. Consequently, aggregate completeness should be supplemented with per-system, per-source, and per-task coverage rather than treated as a universal quality score.

The ingredient-link gap also requires careful interpretation: 115 ingredient rows have no herb ID, but these comprise **67 unlinked herbal ingredients and 48 mineral, animal, or other ingredients**. Assigning herb IDs to all 115 would introduce errors rather than improve completeness.

## 2. Principal strengths

### 2.1 Useful integration and multilingual access

The resource connects disorder terminology, hierarchies, symptom profiles, botanical identities, traditional properties, formulations, phytochemicals, bibliographic evidence, and published observations. These connections enable questions that would otherwise require joining multiple source systems manually. Sanskrit representations, Hindi fields, and regional-script names make multilingual retrieval research feasible.

The value lies chiefly in integration and accessibility. The presence of authoritative terminology sources strengthens source traceability, while botanical and chemical identifiers facilitate interoperability. These strengths do not establish that every cross-source match is correct or that a biomedical label is an exact equivalent of an Ayurvedic concept.

### 2.2 Much stronger engineering and traceability

The current implementation fits learned preprocessing inside training folds, reserves the synthetic E4 holdout before model selection, and performs nested tuning with preprocessing inside both levels. Persistent append-only identifiers reduce accidental identity changes when records are inserted. Export validation now gates publication; immutable snapshots and an atomic pointer provide a consistent multi-file reading interface.

Provenance now covers every processed row and retains selected field overrides, including WHO-filled definitions and transformation flags. Packaging checks cover descriptor paths, source-file consistency, SQLite integrity, and example execution. The latest archive was tested from a fresh extraction in an arbitrary working directory using the existing pinned Python environment and locally supplied verified base-model weights. Model weights are not bundled. This supports practical reuse without implying that a complete rebuild from every upstream source has been independently established.

### 2.3 More defensible experimental reporting

Corrected reports preserve split membership, input scope, comparisons, and limitations. Full-corpus retrieval uses 2,015 eligible disorder candidates and 10,049 eligible symptom candidates rather than the earlier restricted candidate setting. Fine-tuning exclusions address known concepts, normalized headwords, exact descriptions, and high textual overlap. QA splits group shared source records and bilingual variants.

The repository also retains negative findings. Chemistry enrichment did not improve the best herb-indication baseline, and the historical case ablation shows only a small incremental contribution from the base KB. Reporting such outcomes makes the research more informative than presenting only favorable metrics.

### 2.4 Review infrastructure is ready to use

Source-visible annotation queues, content hashes, protected reviewer fields, a rights ledger, external-candidate collection, and paired evaluation tooling reduce the work needed to conduct independent review. Review preparation is a real contribution, although it must remain distinct from completed review.

## 3. Major weaknesses and their implications

### 3.1 Expert validation remains incomplete

Fresh inspection found **3,970 items across seven review sheets, with zero populated verdicts**. The returned-review directory contains no completed review files. This establishes the state of the supplied repository materials; it does not establish whether discussions or reviews exist elsewhere.

The workbook spans herb properties, herb–disorder and therapy–disorder relationships, biomedical correspondences, formulations, Hindi translations, and case records. These are central components, so the absence of recorded adjudication materially limits claims of semantic reliability. Agreement, reviewer qualifications, correction rates, and residual error rates are unavailable.

**Needed improvement:** Two independent qualified reviewers should assess a stratified sample, with adjudication of disagreements and explicit error categories. Safety-sensitive and frequently surfaced records should receive priority. Report agreement alongside adjudicated accuracy; extraction recall additionally requires reviewers to enumerate missed gold items.

### 3.2 Relationship semantics are still uncertain

The parser now preserves conjunctions and modifiers more carefully. A specific Prameha error has been repaired: “frequent and excessive urination” had been split into “frequent” and “excessive urination.” The correction retains a combined concept and preserves existing published IDs. This is a meaningful repair with an auditable example.

However, **211 additional disorder profiles remain in the candidate-change queue**, and the 151-edge stratified sample has no independently adjudicated gold labels. Precision and recall therefore remain unknown. Broader candidate changes have not replaced the processed graph.

Inherited symptoms, WHO descriptions, case-observed associations, generic indications, and direct source statements should remain distinguishable. A parent-level feature may not apply to every child; a reported intervention does not establish effectiveness; a negated finding should not become a positive symptom. Biomedical crosswalks also need relation types such as approximate, broader, narrower, or disputed where equivalence is uncertain.

### 3.3 Evidence tiers describe search results, not efficacy

Among 1,427 herb–disorder evidence rows, 518 are `no_literature`, 431 `sparse`, 241 `literature_supported`, 204 `clinical_evidence`, and 33 `not_queryable`. Thus **66.5% are sparse or have no literature hits under the implemented query**. Among 121 formulation evidence rows, only six carry the clinical-publication tier.

The label `clinical_evidence` means a matching clinical-publication search result was found. It does not encode risk of bias, population relevance, intervention equivalence, effect size, certainty, or benefit–harm balance. Likewise, no search hits do not prove no evidence exists. Search ambiguity and botanical synonyms can affect both positive and negative results.

**Needed improvement:** Add study-level records with design, population, preparation, comparator, outcomes, adverse events, article identity, and structured appraisal. Keep traditional indication, observed use, bibliographic co-occurrence, and appraised clinical support as separate assertions.

### 3.4 Safety coverage is selective

Only **24 of 466 herbs have a safety classification**; the other **442 (94.8%) are unclassified**. Existing hazard flags are useful warnings but are not a completed safety review. Safety depends on species identity, plant part, preparation, dose, duration, interactions, patient characteristics, and monitoring, none of which can be inferred from an empty field.

**Needed improvement:** Record explicit assessed/unassessed states, preparation-specific scope, contraindications, interactions, adverse-event references, reviewer qualifications, and assessment dates. Prioritize toxic or metal-containing materials and commonly displayed remedies. A research search interface can display source-linked uncertainty; prescribing readiness requires substantially more evidence.

### 3.5 Hindi and multiscript quality remain uneven

The repository has 21 unique source-linked Hindi post-edits, but they remain explicitly unreviewed AI edits. The repetition reassessment contains 971 flagged fields including derived copies, of which 89 contain detected consecutive loops. These are field counts, not independent concept counts or estimates of total translation error.

Retranslation generated proposals for 69 unique English sources and 89 record fields. After a bounded retry, those proposals have zero detected consecutive loops, but **zero canonical records were overwritten and independent language approval remains false**. Removing repetition is not evidence that negation, anatomy, severity, frequency, or technical terminology was translated correctly.

**Needed improvement:** Use bilingual domain reviewers, an approved terminology glossary, and error categories covering clinical meaning. Evaluate native Hindi questions separately from machine-translated source descriptions. Regional-script expansions should be labeled as transliterations unless native-speaker validation supports a stronger claim.

### 3.6 Provenance is improved but not fully assertion-specific

Every row now has conservative source dependencies, and selected field overrides repair important attribution defects. Nevertheless, collective record dependencies do not tell a user exactly which source supports each individual assertion. Exact historical lineage cannot be reconstructed where it was never captured.

**Needed improvement:** For new or reviewed assertions, store source record and locator, original text, transformation method and version, assertion type, reviewer decision, and confidence or uncertainty. Preserve competing interpretations rather than forcing a single value. Retain conservative labels for historical records with incomplete attribution.

### 3.7 Component permissions remain unresolved

All **14 source-rights ledger entries remain `not_reviewed`**, with no approved scopes. The combined release declares CC BY-NC-SA 4.0, but that declaration does not resolve the conditions of every included source or transformation. NAMASTE has no explicit open licence recorded, WHO has its own terms, article-derived phrases require per-article consideration, and model-generated translations need separate assessment.

**Needed improvement:** Obtain and record qualified decisions about permitted uses, redistribution, transformations, attribution, and exclusions. Apply any exclusions consistently across CSV, corpus, SQLite, review materials, and archives. A source-ID filter alone cannot certify a commercially reusable subset. Permission-request drafts are not granted permissions.

## 4. Evaluation: what the results demonstrate

| Task | Recorded result | Defensible interpretation |
|---|---|---|
| Organ-system classification | Logistic regression macro-F1 0.811 on 1,950 records; combined TF-IDF and embeddings 0.856 in the corresponding NAMASTE+WHO scope | Internal classification of source-derived labels, not diagnosis. |
| Doṣa from masked descriptions | Logistic regression macro-F1 0.604 on 484 records | A limited labeled subset; the majority of disorder rows remain unspecified. |
| Herb-property tasks | Vīrya macro-F1 0.792; doṣa-pacification mean label macro-F1 0.852 | Internal consistency/predictability of recorded properties, with 344 property-bearing herbs. |
| Herb indications | Best original-feature mean label macro-F1 0.606; chemistry/family variant 0.600, compressed variant 0.599 | Added chemical features did not establish improvement on this experiment. |
| Synthetic prakṛti | Best reported development-CV macro-F1 0.636; final calibrated holdout accuracy 0.748 | Performance on generated records; the metrics and populations must remain separately labeled. |
| Hindi disorder headword retrieval | Recall@10 0.161 → 0.440 after fine-tuning | Improved, but the target remains outside the top ten for 56% of these queries. |
| Hindi symptom headword retrieval | Recall@10 0.069 → 0.199 | A substantial remaining retrieval weakness: about 80% miss the target in the top ten. |
| Hindi description retrieval | Disorders 0.882 → 0.943; symptoms 0.720 → 0.854 recall@10 | Stronger on record-derived translated descriptions than on short headwords. |

Retrieval uses 800 fixed queries per task. Known textual and concept overlap is controlled more carefully, but paraphrase contamination remains unmeasured. These queries originate in the resource, so results do not establish performance on independently written patient presentations or naturally occurring Hindi search queries. Earlier 800-candidate results are not directly comparable with full-corpus results.

Historical E6b case matching is more sobering. Across 85 selected published reports, lexical matching achieved 20.0% top-ten retrieval, a training diagnosis-frequency baseline achieved 34.8%, case-learned profiles alone achieved 47.3%, and case-learned profiles plus the KB achieved 48.5%. The KB increment was only 1.2 percentage points at top ten; top-one performance was slightly lower with the KB, 17.2% versus 17.6%. Reliable incremental clinical benefit from the KB is therefore not established. Seed variability is not a confidence interval. These are stored historical results, not a newly reproduced external test.

The 565 existing reports are an internal publication pool; only 176 have diagnosis IDs. Published cases are vulnerable to selection, reporting, and publication bias and may contain multiple patients. Of 867 observed medicine links, 751 are absent from the corresponding KB disorder-family relationships. This suggests a useful curation opportunity, but observed use is not sufficient evidence to add a treatment recommendation.

The newly collected **736 publication candidates** are metadata records without adjudicated labels. The collection exhausted the specific Europe PMC query at retrieval time, not all Ayurveda literature. Candidate deduplication against known identifiers does not prove patient independence. No external accuracy or paired baseline confidence interval can yet be reported.

## 5. Viability and appropriate usage

| Proposed use | Current suitability | Conditions or missing evidence |
|---|---|---|
| Terminology browsing and source discovery | Good for supervised research | Show original source, transformation, and review state; respect source terms. |
| Knowledge-graph/data-engineering research | Good | Preserve relation types, stable IDs, source dependencies, and snapshot versions. |
| Bilingual retrieval experiments | Useful with limitations | Use full candidates, independent queries, and language-specific error analysis. |
| Educational reference prototypes | Conditional | Link to sources, expose uncertainty, and obtain subject-matter review of displayed content. |
| NLP training or evaluation | Conditional | Separate translations and shared facts across splits; distinguish templates and synthetic records from independent examples. |
| Evidence synthesis | Useful for finding leads | Requires article-level selection, extraction, and appraisal before conclusions. |
| Clinician-facing decision support | Insufficiently validated | Needs adjudicated semantics, safety scope, external validation, and prospective workflow assessment. |
| Autonomous diagnosis, dosing, or prescribing | Unsupported | Current evaluations and safety fields do not establish clinical suitability. |
| Commercial redistribution | Unestablished | Requires component-specific rights decisions and a verified release scope. |

The current resource is viable to maintain as a research project because it has inspectable data, runnable tools, stable identities, and explicit correction workflows. Sustainability will depend on assigning maintainers for scientific review as well as code, recording source refresh costs, and preventing machine-generated suggestions from silently becoming accepted facts.

## 6. Prioritized improvement and expansion plan

The next release should prioritize validation of high-value content before maximizing row counts. Priority below reflects claim and user impact; the human-review tracks can proceed alongside engineering work.

| Priority | Work package | Practical completion evidence |
|---|---|---|
| P0 | Define intended uses and permitted release scope | Consistent dataset card, citation metadata, interfaces, and source-rights decisions; explicit exclusions where required. |
| P0 | Adjudicate high-risk semantic and safety content | Qualified independent decisions for prioritized herbs, formulations, symptom edges, and biomedical mappings; references, disagreements, and correction logs. |
| P1 | Complete a defensible Hindi review cycle | Reviewed priority queue, glossary, source-linked corrections, independent adequacy/error assessment, rebuilt dependent artifacts. |
| P1 | Establish an independent evaluation set | Eligibility-reviewed publications or consented clinical data, defined patient units, two-reviewer labels, publication/patient separation, presentation-only inputs, and frozen membership. |
| P1 | Test strongest baselines on identical cases | Per-case paired predictions, frequency and lexical baselines, case-only and KB ablations, cluster-bootstrap intervals, subgroup errors, and documented exclusions. |
| P1 | Improve sparse clinical coverage selectively | Reviewed definitions, herb properties, ingredient links, and direct indications prioritized by coverage gaps and research demand. |
| P2 | Capture assertion-level provenance prospectively | Source locators, extraction versions, transformation flags, review dates, and disagreement-preserving assertions. |
| P2 | Strengthen release and maintenance discipline | Distinct release version, frozen hashes and inputs, change/deprecation log, clean-environment reconstruction evidence, and clearly documented optional model downloads. |
| P2 | Establish comparative scientific positioning | Related-resource comparison of scope, overlap, validation, licences, languages, access, and unique contribution. |

Several bounded expansion opportunities are already prepared:

- **Missing definitions:** 56 alternate headword matches cover 37 of the 873 undefined disorder records. These need sense alignment review, not automatic copying. Source-location evidence exists for 119 WHO-linked undefined records, but their linked parsed WHO records provide no available definition to fill directly.
- **Herb properties:** Searches covered all 122 property-missing herbs and found citation leads for 26. No properties have been inferred or filled. Reviewers should extract preparation- and species-specific statements with exact citations.
- **Formulations:** Resolve the 67 unlinked herbal ingredients using reviewed synonyms and botanical identities. Keep the 48 non-herbal ingredients in suitable material classes. Expansion should retain preparation, composition variants, and references.
- **Independent language coverage:** Collect naturally written Hindi and regional-language questions with consent and appropriate terms. Add spelling variation and mixed-script evaluation, rather than treating transliteration as equivalent to translated clinical content.
- **Evidence and adverse events:** Expand structured appraisal and safety coverage alongside efficacy literature. Retain negative, uncertain, and conflicting findings to reduce selective reporting.

Engineering can automate collection, deduplication, provenance capture, packaging, reviewer queues, and evaluation. Qualified reviewers must supply semantic, linguistic, safety, and permission decisions; automation cannot manufacture those approvals.

## 7. Remaining reproducibility and documentation issues

The release's computational improvements do not yet demonstrate a complete clean-room reconstruction of every upstream layer. The latest extracted-archive test reused pinned dependencies and supplied base weights locally. Historical case-pipeline reproduction is limited by an unavailable original case-report cache. Future source refreshes should produce new versioned collections rather than silently substituting inputs into old experiments.

The atomic snapshot pointer is the consistent export-reading interface. Legacy multi-file compatibility paths can still be interrupted by process termination. SQLite integrity and export-time referential checks do not imply that all later database writes are protected by SQL foreign-key constraints. These are manageable engineering limitations when documented accurately.

Documentation also needs a final consistency pass: `REVISION_STATUS.md` still opens with an outdated statement that nothing has been pushed, while progress commits have since been pushed. Citation wording such as “checked against 565” case reports could be read more strongly than the selective historical experiments support. A distinct revision identifier and dated evidence links would make the current state easier to cite without confusing historical v1.2 results with corrected experiments.

## 8. Relationship to the earlier peer review

| Earlier concern | Current judgment |
|---|---|
| Held-out-data preprocessing and model-selection contamination | Specific engineering defects addressed; corrected E1/E2/E4/E7 and embedding/retrieval results recorded. External validity remains open. |
| Missing or overstated export attribution | Substantially improved across all tables; exact historical assertion attribution is still incomplete. |
| Export gates, descriptor paths, archive behavior | Addressed with tested validation and publication mechanisms, subject to documented runtime boundaries. |
| Identifier instability | Addressed prospectively through a persistent registry and reviewed alias rules. |
| Distributed-text disclosure | Improved through explicit text inventory and source descriptions. Permissions remain unresolved. |
| Symptom extraction and Hindi meaning | Targeted fixes and better tooling completed; independent accuracy remains unestablished. |
| Expert review and safety validation | Still incomplete in the repository evidence. |
| Independent cases and strongest paired comparisons | Candidate pool and tooling prepared; adjudicated test data and paired predictions still missing. |

AyurKB should be presented as a promising, substantially improved research knowledge base whose engineering maturity currently exceeds its independently demonstrated semantic and clinical validity. The most valuable next milestone is a reviewed, clearly scoped subset with credible external evaluation and documented reuse conditions.

## Evidence register

1. [Fresh count, workbook, rights-state and CSV-hash audit](../reports/peer_review_current_audit.json).
2. [Data dictionary](DATA_DICTIONARY.md), [datasheet](DATASHEET.md), and [system coverage](../reports/revision_audit/coverage_by_system.csv).
3. [Current recorded validation and benchmark summary](REVISION_VALIDATION.md), [machine-readable validation](../reports/revision_validation_summary.json), and [corrected experiment artifacts](../reports/revision_full/).
4. [Semantic experiment artifacts](../reports/revision_semantic/) and [historical case-matching results](../reports/ml/E6b_matching_improvements.json).
5. [Semantic/language protocol](SEMANTIC_AND_LANGUAGE_REVIEW.md) (the offline workbook was retired in v1.3.0).
6. [Provenance contract](PROVENANCE_CONTRACT.md), [rights ledger](../curation/source_rights_review.csv), and [rights/safety handoff](RIGHTS_AND_SAFETY_REVIEW.md).
7. [Translation reassessment](../reports/revision_audit/translation_repetition_reassessment.json), [retranslation outcome](../reports/retranslation/summary.json), and [herb-property search outcome](../reports/herb_property_research/summary.json).
8. [Evaluation protocol](EVALUATION_PROTOCOL.md), [partition/evaluation status](../reports/revision_audit/evaluation_status.json), and [external-candidate pointer](../reports/external_candidates/current_collection.json).
9. [Archive validation](../reports/network_enabled_archive_validation.json), [export publication contract](EXPORT_PUBLICATION.md), and [network-enabled work](NETWORK_ENABLED_WORK.md).
10. [Response to the original peer review](PEER_REVIEW_RESPONSE.md). The supplied Word review assessed commit `c30c158cce0a3c26d0b3fb3b9bfcc69216fe9a7e`, rather than the current snapshot.
