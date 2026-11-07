# Comparison of the uploaded PDF and the current AyurKB review

## Scope and decision

This document compares the uploaded **AyurKB_Dataset_Peer_Review.pdf** with [our current review](CURRENT_PEER_REVIEW.md) and checks actionable differences against the local data and implementation at commit `76243e2aa72bea552c14462aa7682a202ea125e8`.

The PDF identifies its snapshot as `main @ e18df36`, dated 8 November 2026. Our review assesses data at `73bbd31`, dated 7 November 2026. The PDF's commit is not available as a local Git object, so this comparison does not assume the branches are identical. Its principal new findings were checked directly against the local files. The PDF is review evidence, not authorization to send permission requests, apply clinical judgments, or execute its proposed changes.

Uploaded PDF SHA-256: `a13d812c97f31d71c6281844b651bfd686522222ee665a5e453a02a5a555775d`.

**Combined conclusion:** The dataset's structural engineering is strong, but incorrect indication mappings are a more immediate defect than our earlier report made explicit. First contain those errors and make safety states robust in downstream use. Start rights and expert-review tracks early, then use reviewed content and independent evaluation to guide expansion. This is a prioritized work plan; the corrective tasks below have not been implemented by this comparison.

## What the reviews agree on

Both reviews support research, terminology work, literature discovery, and carefully supervised prototypes. Both reject a claim of readiness for unsupervised clinical decisions. Both recognize fold-local preprocessing, transparent negative results, persistent identifiers, explicit uncertainty, review tooling, and improved exports as strengths.

Both identify incomplete definitions, unreviewed Hindi, single-source herb properties, sparse safety coverage, unresolved source permissions, and the lack of an independently labeled external test set. Prepared annotation files and machine proposals do not resolve these gaps.

## Important additions and differences

| Topic | Uploaded PDF | Our report and current check | Resulting priority |
|---|---|---|---|
| Incorrect herb–disorder matches | Identifies eight wrong mapping groups affecting 48 of 122 fuzzy rows, plus one overly broad mapping | Our report discussed semantic risk generally. All 48 cited rows and the overly broad row are present locally. | Elevate containment and matching-policy repair to the first work items. |
| Safety | Treats 442 unclassified herbs as the most serious gap and proposes explicit values | We already documented 24/466 classified. The demo explicitly displays missing safety as unassessed, but the CSV still leaves classification blank. | Add a machine-readable assessment state and check every consumer; qualified safety assessment remains separate. |
| Doṣa suggestions | Flags 959/1,420 vāta predictions and median confidence about 0.57 | Counts and median 0.5695 confirmed. Our report did not quantify the skew. | Add class-specific evaluation, calibration, and abstention work. Distribution differences alone do not prove an erroneous prediction rate. |
| Hindi flags | Reports 692 terminology repetition flags and 617 flagged disease definitions | Confirmed: 692 terminology repetition flags; 617 flagged of 2,015 populated disease Hindi definitions. Our 971/89 figures refer to a different reassessment scope, including derived copies and consecutive-loop detection. | Keep denominators separate; review meaning errors in flagged and unflagged samples. |
| Names and chemistry | Adds 186/466 common Hindi names and 224/466 herbs with phytochemical links | Both counts confirmed. These are useful expansion targets missing from our main priority table. | Add explicit naming and phytochemical coverage work after semantic containment. |
| Missing links outside herb indications | Quantifies group, image, ingredient, and formulation gaps | Confirmed: 24 group-member herb links, 81 image herb links, 115 ingredient herb links, and 34 formulation-indication disorder links are blank. | Triage by reason; do not force links for legitimate non-herbal or out-of-inventory records. |
| Rights | Calls licensing a minor weakness but notes it constrains reuse | Our report treats unresolved rights as a release-scope issue; all 14 ledger entries remain unreviewed in the existing audit. | Begin decisions early because of lead time and redistribution impact. No letters are sent by this plan. |
| External evaluation | Proposes two-reviewer annotation of the 736 publication candidates | Our report additionally requires patient/publication separation, presentation-only input, strongest baselines, and paired intervals. | Retain the fuller protocol rather than treating annotation alone as clinical validation. |
| Structural validity | Reports zero orphaned references across 31 checked columns and no duplicates | Compatible with strong engineering evidence, but a valid ID can still identify the wrong disorder. | Keep structural checks and add semantic checks. Do not infer semantic correctness from key validity. |
| Test results | Reports Windows: 135 passed, one ZIP check skipped | Our recorded environment reports 136 passed, none skipped. | Report environment and execution scope; these are not necessarily contradictory results. |
| Reproducibility and provenance | Generally positive | Our report retains limits on historical assertion attribution, full upstream reconstruction, model distribution, and missing historical case inputs. | Preserve those limitations and complete targeted work below. |

### The concrete mapping defect

The local CSV contains 1,310 `exact_skeleton`, 122 `fuzzy_skeleton`, and 261 unmatched indication rows. The PDF's reported wrong groups are:

| Raw indication | Current target | Rows |
|---|---|---:|
| Kshaya | Psychic constitution (`AYD-02923`) | 32 |
| Kantharoga | Ear diseases (`AYD-01860`) | 3 |
| Kaphaja Roga | Scalp affliction (`AYD-01535`) | 3 |
| Kapha Roga | Scalp affliction (`AYD-01535`) | 3 |
| Kshata | Whitlow (`AYD-02260`) | 3 |
| Vataroga | Eyelid disorders (`AYD-01689`) | 2 |
| Vata Roga | Eyelid disorders (`AYD-01689`) | 1 |
| Manasa Roga | Nose diseases (`AYD-01813`) | 1 |
| **Total** | | **48** |

This is 39.3% of fuzzy rows and 3.35% of all 1,432 linked indication rows. It is the PDF reviewer's judgment over the fuzzy mapping groups, with their presence verified here; it is not an independently adjudicated error rate for all mappings. The additional mixed-script `V विषम Jwara` row maps to generic fever and is reported as overly broad. It should be reviewed separately from the 48 rows labeled wrong.

### Qualifications to retain

- A blank safety field can be misused by a consumer, but the PDF's claim that *any* filter treats blanks as safe is too broad. The current demo already warns users about unassessed safety. The remaining engineering task is to make the state explicit and consistent everywhere.
- A head-noun compatibility rule can block some bad fuzzy matches. Shared `roga` or `jvara` does not establish equivalence, and legitimate variants may have different surface forms. Approved aliases, sense checks, ambiguity handling, and abstention are still needed.
- The PDF's “unctuous complexion → unstable skin” example is present locally, but the terminology row does carry a repetition flag. Other related disease rows have empty flags and problematic renderings. The defensible point is that quality flags do not certify semantic adequacy, rather than that this exact terminology row is unflagged.
- A 12-edge symptom spot check is useful for finding errors, not for establishing overall precision or describing the entire graph as faithful. Complete the stratified review before making quantitative accuracy claims.
- Calibration can improve probability interpretation, but it does not necessarily remove vāta skew. Assess target-population shift, class-specific errors, and abstention before choosing a correction; do not impose equal class counts.
- A small same-cohort leakage effect does not justify the blanket claim that every historical estimate was unaffected. Compare the same inputs, labels, folds, and models; keep NAMASTE-only and WHO-enriched cohorts separate.
- Finding a matching clinical publication is not equivalent to verifying a clinical study that supports efficacy. Permission and model-use conditions also require source-specific decisions; a combined licence declaration is not proof of compatibility.

## Ordered work list

**Ownership:** Engineering tasks can be implemented in the repository. Mixed tasks need engineering plus supplied source evidence or expert decisions. Expert tasks require qualified clinical, linguistic, or rights reviewers; automation can prepare and process their work but cannot supply their approvals.

Priorities indicate urgency, not a requirement to serialize independent review tracks. Start items 5–7 and external-label recruitment early while engineering proceeds. Corrections from every later item should use the provenance and rebuild rules in items 3 and 8.

### 1. Quarantine the reported incorrect indication links — P0, engineering

Preserve original source text, current target, mapping method, reason, and audit history. Prevent the 48 reported wrong rows from being used as accepted disorder links in recommendations and evidence lookup. Put the additional overly broad fever mapping into explicit review. Do not invent replacement targets or erase source records.

**Done when:** A versioned quarantine decision identifies every affected row, downstream consumers exclude it from accepted links, and regression checks cover the cited examples. Existing herbal evidence rows shared with other indications must be traced before removal or relabeling.

### 2. Repair the indication matcher and introduce reviewed aliases — P0, mixed

Replace unconditional acceptance of spelling similarity with explicit candidate/accepted/rejected states, curated sense-specific aliases, ambiguity checks, and abstention. Review all 20 distinct fuzzy mapping groups, including the groups the PDF judged correct. Audit a stratified sample of the 1,310 exact-skeleton rows because normalization can also conflate senses. Include mixed-script and compound-word cases.

**Done when:** Bad examples no longer auto-link, reviewed valid aliases resolve reproducibly, uncertain terms remain unresolved, and held-out source-linked mapping evaluation reports precision and coverage. Head-noun rules supplement semantic review.

### 3. Rebuild and audit everything affected by mapping corrections — P0, engineering

Trace dependencies through evidence queries/tiers, QA, retrieval corpus, demo, CSV/SQLite exports, provenance, and archive. Recompute affected outputs and evaluate whether old derived assertions remain supported by another valid source link. Retain historical benchmarks under their original input hashes.

**Done when:** No quarantined mapping survives as an accepted assertion in current outputs; archive and consumer checks pass, and changed counts and hashes are recorded. Repeat this targeted procedure after later approved corrections.

### 4. Make safety assessment state explicit throughout the dataset — P0, engineering

Add an assessment-state field that distinguishes unassessed, assessed, and review-pending records without presenting any state as a blanket guarantee of safety. Keep hazard classification separate from whether it has been reviewed. Check filters, rankings, corpus text, exports, and displayed remedies for all 466 herbs.

**Done when:** All 442 currently unclassified herbs have an explicit unassessed state, current warnings remain accurate, and consumers cannot select “safe” by merely excluding known poisons. A backfill of state is not a safety assessment.

### 5. Resolve source permissions and define the release scope — P0, expert plus engineering

Review the 14-source ledger, starting with NAMASTE, WHO, article-derived text, and model-related conditions. Record exact documents, permitted uses, transformations, redistribution, attribution, dates, and exclusions. Prepare any needed correspondence for the maintainer to send or explicitly authorize.

**Done when:** Each included component has a recorded decision supporting the intended release; unresolved material is explicitly scoped or excluded consistently across outputs. No “commercial-safe” claim is made from filtering alone. This track should start immediately because external responses can take time.

### 6. Conduct safety review of the highest-risk and most-used materials — P0, expert

Prioritize flagged toxic herbs, metal-containing formulations, herbs used in the 43 formulations, and materials implicated in adverse reports. Consult appropriate monographs and literature under their terms. Record species, plant part, preparation, contraindications, interactions, adverse events, evidence, reviewer qualifications, and assessment date.

**Done when:** A clearly bounded reviewed subset has evidence-backed assessment records and adjudicated disagreements; remaining materials stay unassessed. Full clinical safety coverage is a longer-term objective.

### 7. Complete semantic expert review — P1, expert plus engineering

Begin with mapping errors, the 151-edge stratified symptom sample, the 211 candidate disorder-profile changes, and high-impact workbook items. Review herb–disorder, therapy–disorder, formulation, and biomedical correspondence semantics. Preserve negation, alternatives, modifier scope, and relation breadth.

**Done when:** Independent verdicts and adjudication are recorded, extraction precision is measured, recall is measured only against complete gold annotations, and approved corrections are rebuilt. The 3,970-item workbook currently records no verdicts; a reviewed sample does not complete every sheet.

### 8. Capture assertion-level provenance for corrections and new content — P1, engineering plus reviewers

Extend conservative row dependencies where exact evidence becomes available. Attach source record/locator, original text, assertion type, mapping or extraction method/version, reviewer decision, and uncertainty. Preserve conflicting interpretations and historical values.

**Done when:** Each newly corrected or expanded assertion resolves to its evidence and decision; older records without exact lineage remain labeled conservatively. Establish this contract before merging new reviewer corrections even though bulk backfilling can proceed later.

### 9. Complete Hindi review and establish terminology control — P1, bilingual experts plus engineering

Review the 89 retranslation proposals, 21 unreviewed post-edits, and priority flagged fields. Also draw a reproducible, stratified unflagged sample to detect hidden meaning errors. The PDF suggests 2%; choose sample sizes based on the language/source strata and uncertainty needed, rather than treating 2% as automatic validation. Maintain a glossary covering technical terms, negation, anatomy, frequency, and severity.

**Done when:** Accepted/rejected/uncertain verdicts and corrections are recorded; semantic adequacy and error categories are reported with denominators and uncertainty; dependent translations and QA are refreshed without overwriting unresolved meanings.

### 10. Build an independent adjudicated evaluation set — P1, clinical reviewers plus engineering

Screen the 736 publication candidates for eligibility and overlap. Define individual patient units, identify duplicate publications/patients, isolate presentation-only inputs, and obtain independent labels with adjudication. Freeze membership before model selection. If another eligible data source is used, preserve its acquisition and consent/terms requirements.

**Done when:** A documented test set has reviewer references, publication/patient grouping, exclusion reasons, target labels, and no model-development contamination. Candidate metadata alone does not meet this condition.

### 11. Evaluate strongest baselines and the incremental KB contribution — P1, engineering after item 10

Run frequency, lexical, semantic, case-learned-only, and case-learned-plus-KB systems on identical eligible cases. Save paired per-case predictions, evaluate exact and family labels separately, and calculate publication/patient-cluster intervals and subgroup errors. Reassess the historical 47.3% versus 48.5% top-ten ablation rather than assuming the KB helps.

**Done when:** Reproducible paired results quantify both performance and uncertainty. Report negative findings; do not describe seed variability as a confidence interval or use internal published cases as external clinical validation.

### 12. Evaluate retrieval with independent natural-language queries — P1, mixed

Collect independently authored Hindi and English queries, spelling variation, mixed-script queries, and genuinely unanswerable requests. Group bilingual and shared-source QA facts across splits, and audit paraphrase overlap. Compare source-derived descriptions and short headwords separately.

**Done when:** Frozen independent queries have reviewed relevance labels, full-corpus baselines, recall/MRR and failure analysis, plus an abstention evaluation. Current fine-tuned Hindi symptom-headword recall@10 of 0.199 remains a particular target.

### 13. Audit and calibrate doṣa suggestions — P1, mixed

Analyze the 959 vāta predictions, class-specific precision/recall, calibration, confidence, and target-population differences using held-out expert labels. Choose per-class acceptance or abstention rules without optimizing on the final test set. Keep suggestions separate from authoritative labels.

**Done when:** Validated thresholds and coverage/precision tradeoffs are published; low-confidence and out-of-scope records abstain. Equalizing class proportions is not an acceptance criterion.

### 14. Fill missing disorder definitions selectively — P1, mixed

Prioritize the 873 undefined records by intended use and source availability. Review the 56 alternate matches for 37 disorders. Use recorded WHO source locations where helpful, but do not claim that re-querying the same linked parsed records will supply missing text. Maintain category/pattern distinctions.

**Done when:** Every added definition has a permitted source, sense alignment decision, provenance, and language-review state; remaining gaps have reasons. Regenerate profiles only from accepted text.

### 15. Recover unmatched indication coverage — P1, mixed

Review the most frequent of the 261 unmatched rows: Grahani, Krimi variants, Pandu, Pradara, Agnimandya, and Yakrit Roga. Map only where the sense and parent/subtype relationship are justified. Some terms may describe a process or traditional indication rather than a single NAMASTE disorder.

**Done when:** Approved aliases recover valid links with relation scope, while ambiguous or out-of-inventory terms retain explicit reasons. Apply the matcher policy from item 2; do not choose a convenient disorder just to reduce missingness.

### 16. Expand herb properties with source diversity — P1, mixed

Address 122 property-missing herbs, beginning with citation leads already found for 26. Add reviewed, permission-compatible sources and preserve disagreements, botanical identity, plant-part/preparation scope, and classical references.

**Done when:** Added properties are source-linked and adjudicated, and alternative authorities can be represented without silently replacing one view. Citation leads alone are not filled properties.

### 17. Resolve ingredient, formulation, and group links appropriately — P2, mixed

Review 67 unlinked herbal ingredients, 34 formulation-indication disorder gaps, and 24 herb-group member gaps. Represent the 48 mineral/animal/other ingredients with appropriate material classes. Triage 81 blank image-dataset herb links as potentially out of inventory rather than automatically erroneous.

**Done when:** Each gap has either a supported link or a documented non-link reason. Any added entity preserves stable IDs and reviewed botanical/material identity.

### 18. Add study-level evidence appraisal — P2, expert plus engineering

Separate bibliographic co-occurrence, traditional indication, case-observed use, and appraised clinical support. Extract study design, preparation, population, comparator, outcomes, effect measures, harms, and risk of bias for a prioritized subset. Include negative and uncertain findings.

**Done when:** Displayed efficacy-related summaries resolve to appraised studies and their limitations; no search tier implies efficacy. Keep article-use conditions attached to extracted material.

### 19. Improve botanical, common-name, and phytochemical coverage — P2, mixed

Review unresolved taxonomy and synonyms, validate common Hindi names beyond the present 186 herbs, and investigate chemistry gaps beyond the present 224 linked herbs. Maintain species/plant-part scope and distinguish a source's missing coverage from absence of a compound. Regional-script names need native-language evaluation where linguistic correctness is claimed.

**Done when:** Additions have source identity and review state, botanical ambiguity is visible, and coverage is reported by source and species. Database name resolution alone is not identification of a physical medicinal material.

### 20. Complete clean-environment reproducibility evidence — P2, engineering

Freeze accessible source snapshots, dependency/model revisions, encoding recipe versions, and output hashes. Test a clean dependency install and documented model acquisition, then reproduce the claimed pipeline scope. Recover the original historical case cache where legitimately available or create a separately versioned new collection and experiment.

**Done when:** A documented clean run reproduces its declared scope, with unavailable inputs and tolerances disclosed. Never substitute newly retrieved articles into an old experiment without changing its identity.

### 21. Synchronize schema, documentation, and release governance — P2, engineering plus maintainer decisions

Fix stale push/status wording and overbroad citation claims. Document or deprecate the entirely empty `short_definition` field with compatibility planning. Explain component licence/provenance access for tables without inline licence columns rather than duplicating an unreviewed blanket licence. Publish versioned counts, uncertainty, correction/deprecation logs, and review ownership. Use the snapshot pointer as the consistent export interface.

**Done when:** README, citation, datasheet, schema, evaluation tables, and release manifests describe the same identified revision; maintaining and refreshing scientific review has an assigned owner. Actual publication remains a separate action.

### 22. Establish comparative scientific positioning — P2, research

Compare relevant Ayurveda terminology, herb, phytochemical, and evidence resources by scope, overlap, unique content, languages, validation, licence, interoperability, and access. Identify the specific research tasks improved by the integration.

**Done when:** Contribution and novelty claims cite a reproducible related-resource comparison. More rows alone do not establish superior quality or scientific novelty.

### 23. Conduct prospective clinical studies only if clinical use is intended — later, clinical collaborators

After the preceding prerequisites, define the intended population, workflow, benefit/harms, abstention behavior, and clinician oversight. Validate constitution assessment on independently observed participants if making clinical prakṛti claims; validate diagnostic or treatment-support behavior separately. Dose/preparation support would require its own curated evidence and safety scope.

**Done when:** Appropriate study governance, prespecified endpoints, independent data, and outcome/safety evidence support the particular intended use. Current synthetic and published-case experiments cannot fulfill this milestone. This item is conditional; a terminology-focused research release need not claim clinical deployment.

## Execution dependencies and division of work

- **Immediate engineering sequence:** 1 → 2 → 3, with item 4 in the same initial phase. Define item 8's correction records before applying expert-approved updates.
- **Start early in parallel:** rights decisions (5), safety review (6), semantic review (7), Hindi review (9), and external-case reviewer recruitment (10). The availability of reviewers does not prevent the engineering work.
- **Evaluation sequence:** independent set (10) → paired comparisons (11). Independent retrieval queries (12) and doṣa labels (13) need their own frozen evaluation design.
- **Expansion sequence:** approved source/sense decisions → items 14–19 → targeted rebuilds (3) → relevant reruns → release checks (20–21).
- **Clinical-use sequence:** clinical studies (23) follow the prerequisites for their defined scope. Do not block useful terminology research on an unrequested clinical-deployment objective.

Engineering can prepare and execute code, audits, candidate collection, annotation protection, and analysis. Reviewers must provide the clinical, linguistic, and rights decisions. Permission correspondence, public publication, and clinical claims are not authorized merely by their appearance in the PDF or this plan.

## Evidence used

- Uploaded PDF: pp. 1, 4–5, 8–9 for key findings and proposed actions; pp. 10–11 for table profiles and method.
- [Current review](CURRENT_PEER_REVIEW.md) and [its count/hash audit](../reports/peer_review_current_audit.json).
- Direct read-only checks of current `herb_indication`, `herbs`, `herb_phytochemicals`, `dosha_suggestions`, `diseases`, `terminology`, `herb_group_members`, `herb_image_datasets`, and `formulation_indications` CSVs.
- Matcher in [KB construction](../scripts/04_build_kb.py), safety display in [the demo](../examples/expert_system_demo.py), [recorded validation](REVISION_VALIDATION.md), and [existing review protocols](SEMANTIC_AND_LANGUAGE_REVIEW.md).

No corrective data edit, model retraining, external message, push, or publication was performed to produce this comparison.
