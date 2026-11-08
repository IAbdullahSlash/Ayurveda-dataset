# Review handoff after indication containment

These batches were prepared on 8 November 2026 (Asia/Calcutta). They contain source evidence and blank decision fields, not completed reviews. Regeneration refuses to overwrite recorded annotations. A reviewer identifier records who supplied a decision; reviewer qualifications must be verified separately.

## Materials ready for review

| Work-plan items | Material | Current scope |
|---|---|---|
| 2, 7 | [Mapping candidates](../reports/indication_review/candidate_groups.csv) and [exact-match sample](../reports/indication_review/exact_match_sample.csv) | 20 fuzzy groups, 19 ambiguous exact groups, 60 sampled exact rows. Quarantine is containment, not final adjudication. An [AI pre-review](INDICATION_PREREVIEW.md) drafts a recommendation for each group and the main unmatched terms; reviewers sign rows and stage 54 copies them into the ledger. |
| 5 | [Rights review batch](../reports/review_handoff/rights_review_batch.csv) | 14 sources; decisions and permission evidence are still missing. Existing permission-request drafts remain in `docs/permission_requests/`. |
| 6 | [Herb safety batch](../reports/review_handoff/safety_review_batch.csv) and [formulation safety batch](../reports/review_handoff/formulation_safety_batch.csv) | 466 herbs and 43 formulations, prioritized using existing flags, formulation membership and published mentions. Mentions do not establish causation. |
| 7 | [Symptom review sample](../reports/revision_audit/symptom_edge_review_sample.csv) and [expert workbook](../review/AyurKB_expert_review.xlsx) | Existing 151-edge sample and workbook; source-visible semantic decisions remain pending. The workbook is a historical review pool, not the current accepted graph. |
| 9 | [Unflagged Hindi sample](../reports/review_handoff/unflagged_hindi_sample.csv), [sampling frame](../reports/review_handoff/unflagged_hindi_sampling_frame.csv), [flagged queue](../reports/revision_audit/translation_queue.csv), and [retranslation proposals](../reports/retranslation/record_proposals.csv) | 598 unflagged fields sampled at 2% per table/field (rounded up), alongside existing priority materials. Fields can include copies of shared content. |
| 10–11 | [External collection pointer](../reports/external_candidates/current_collection.json) and [evaluation protocol](EVALUATION_PROTOCOL.md) | 736 unannotated publication candidates; external performance cannot be calculated without eligible patient units, independent labels and paired predictions. |
| 12 | [Independent-query template](../curation/independent_query_template.csv) | Empty. Queries must be collected independently of KB descriptions; no independent queries have been invented. |
| 13 | [Doṣa distribution audit](../reports/review_handoff/dosha_distribution_audit.json) | 959/1,420 suggestions are vāta; median confidence 0.5695. This is descriptive shift, not measured error or calibration. |
| 14 | [Definition candidates](../reports/revision_audit/alternative_definition_candidates.csv) | Existing 56 candidate matches for 37 undefined records; sense and source-use decisions are pending. |
| 15 | [Unmatched indication queue](../reports/review_handoff/unmatched_indication_terms.csv) | 261 rows grouped into 79 terms and ordered by affected-row count. |
| 16 | [Herb-property research coverage](../reports/herb_property_research/coverage.csv) and [AI property drafts](../reports/herb_property_research/ai_property_drafts.csv) | Citation leads for 26 of 122 queried property-missing herbs; no properties approved. The drafts screen all 45 lead abstracts: only two state properties (*Leonotis nepetifolia*: tikta, kaṣāya rasa; *Vetiveria zizanioides*: śīta), each with its citation and quote. The other 24 need the full text. |
| 19 | [AI chemistry-alignment drafts](../reports/source_gap_research/ai_chemistry_alignment_drafts.csv) | Six variant-name chemistry leads: transfer suggested for *Swertia chirata* → *S. chirayita* and *Aquilaria agallocha* → *A. malaccensis* (both commonly treated as synonyms), reject for three distinct species, *Anethum sowa* left to an expert. GBIF lists every pair as separate accepted names, so each transfer needs a reviewed identity decision. |
| 17 | [Link-gap triage](../reports/review_handoff/link_gap_triage.csv) | 254 rows across ingredient, formulation-indication, herb-group and image links. Distinguish legitimate non-links from unresolved identities. |
| 18 | [Study-appraisal template](../curation/study_appraisal_template.csv) | Empty. Clinical-publication search tiers have not been converted into efficacy judgments. |

## How decisions become reviewable changes

1. Reviewers work on copies of the batches and supply a verdict, precise correction where justified, and a source locator/reference. Preserve source IDs and row references. Record independent decisions and disagreements before adjudication.
2. For semantic extraction, enumerate missed source facts before calculating recall. For Hindi, score meaning separately from fluency and repetition. Estimate hidden error using the sampling frame and appropriate uncertainty; the 2% sample is a starting batch, not an accuracy certificate.
3. For indication aliases, place accepted equivalent-sense or rejected decisions in `curation/indication_aliases.csv` with reviewer and reference. Preserve broad/narrow or uncertain relationships in the review queue until represented explicitly. An accepted alias must identify a real disorder; a similarity score is insufficient.
4. For safety assessments, supply evidence, reviewer, date and species/preparation/population scope in `curation/herb_safety_reviews.csv`. Record hazard corrections separately with their evidence. An assessment state never means universally safe.
5. Rights reviewers or the maintainer record the exact terms or granted permission and permitted scope. No draft letter is evidence of permission. No correspondence has been sent by this work. Apply any exclusion across every representation before making a release claim.
6. Engineering validates and merges supplied decisions, refreshes dependent outputs, reruns relevant checks, and commits each bounded correction. Newly approved indication pairs need their own literature records before the derivative refresh can proceed. Keep old experiments attached to their frozen inputs.

## Remaining prerequisites

Clinical/safety and Hindi adjudication require qualified reviewers. Source-use decisions require permission/terms evidence. External evaluation and calibration require independent labels; prospective clinical claims require an appropriately governed study. These dependencies do not prevent offline engineering or continued terminology research.

Run `python scripts/47_prepare_review_handoff.py` to regenerate unannotated batches. It uses current local records and performs no network queries, external messaging, or clinical approvals. See [work progress](REVIEW_WORK_PROGRESS.md) for completed changes and remaining states.
