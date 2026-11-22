# AyurKB status report

*Checked 22 November 2026. Describes release v1.3.0 (tag `v1.3.0`); data unchanged since the tag.*

**In short:** v1.3.0 is released, CI passes and the data is internally consistent. Nothing in it has been reviewed by a qualified expert yet: every curated layer, every translation and every safety record is a draft. The dataset's main limit is now expert review, not engineering. The plan for that review is in [EXPERT_REVIEW_PLAN.md](EXPERT_REVIEW_PLAN.md).

## 1. Repository and release

| Item | State |
|---|---|
| Latest release | **v1.3.0**, tagged and pushed on 11 November 2026 ([release notes](../releases/v1.3.0.md)) |
| `main` | Release v1.3.0 data, plus documentation updates; holds only the core docs |
| CI (GitHub Actions, Linux and Windows) | Passing on the release commit |
| Automated tests | 184 (183 pass, 1 skipped) |
| GitHub release page | Not created yet; the tag exists |
| Branches | `main`; `review/testing` (this branch: `main` plus review material in `docs/review/` and the record of the v1.3.0 revision in `docs/history/v1.3.0-revision/`); `regenerate-02b` (local only), a kept rebuild for after the symptom-splitting review |

## 2. Size and contents

**43 tables, 180,899 rows.** Published as CSV and Parquet tables, a SQLite database, a JSONL corpus, `datapackage.json` and the v1.2 HTML report (`release/`, 207 MB; `data/`, 93 MB).

| Area | Contents |
|---|---|
| Terminology | 6,233 terms (3,554 WHO ITA 2022, 2,679 NAMASTE SAT) |
| Disorders | 2,892 NAMASTE disorders; 70% have an English definition and 70% a Hindi one |
| Symptoms | 11,082 symptoms; 11,883 NAMASTE disorder–symptom links, 13,639 WHO links, 10,082 inferred |
| Herbs | 466 herbs; 74% have rasa, guṇa, vīrya, vipāka and karma. 453 are linked to a GBIF taxon, 11 are unresolved and 2 are non-botanical (minerals) |
| Chemistry | 1,959 phytochemicals, 23,771 herb–compound links, 13,538 activity records |
| Real-world layer | 565 published case reports (378 open access), 6,435 clinical-trial records |
| Other | 20,895 multi-script names, 4,790 Q&A pairs (2,397 English, 2,393 Hindi), a synthetic prakṛti cohort of 3,000 records |

## 3. Quality and review state

### Herb → disorder links (1,693)

| State | Rows |
|---|---:|
| Active, source-matched but unreviewed | 1,044 |
| Candidate waiting for review | 339 |
| Unmatched | 261 |
| Quarantined (wrong match, kept with the reason) | 49 |

The reviewed alias ledger (`curation/indication_aliases.csv`) has **no signed rows yet**. An AI pre-review drafts a recommendation for all 118 inactive groups, but those are recommendations only ([INDICATION_PREREVIEW.md](INDICATION_PREREVIEW.md)).

### Literature evidence for the links (1,039)

| Tier | Links |
|---|---:|
| Clinical evidence | 162 |
| Literature-supported | 191 |
| Sparse | 324 |
| No literature found | 361 |
| Not queryable | 1 |

These tiers count publications found by search. They are not efficacy judgements.

### Safety

442 herbs are `unassessed` and 24 are `review_pending`. **No herb has an approved safety assessment.** A blank or unassessed state never means safe.

### Hindi

Every Hindi field is machine-translated (NLLB-200) and none has been reviewed by an expert.

- Quality checks flag 1,101 of 5,497 term definitions and 572 of 11,081 symptom glosses.
- On a 300-string sample, the back-translation similarity score (chrF) averages 52.4; 55% of samples score 50 or more.
- 21 broken definitions were replaced by AI post-edits, marked `expert_review_pending`.

### Review hand-off

Batches are ready for safety, rights, Hindi, symptom extraction, mappings and link gaps ([REVIEW_HANDOFF.md](REVIEW_HANDOFF.md)). So far: **0 expert verdicts, 0 clinical labels, 0 permissions granted.**

## 4. Benchmarks

Internal cross-validation on the v1.3.0 data, with preprocessing fitted inside each fold. None is a clinical
validation. Full tables are in the README's Results section.

| Experiment | Result (macro-F1) |
|---|---|
| E1a: organ system from clinical text | 0.811 (0.856 with multilingual embeddings) |
| E1b: doṣa from masked symptom text (484 records) | 0.604 (0.613 with embeddings) |
| E1c: organ system from English vs Hindi text | English 0.805 · Hindi (MT) 0.729 |
| E2a: herb vīrya | 0.792 |
| E2b: doṣa-pacifying profile | 0.852 |
| E2c: herb indications | 0.606; adding chemistry features gives no gain (0.600) |
| E4: prakṛti from questionnaire (synthetic, 750-record holdout) | 0.636 |
| E5b: Hindi headword search, recall@10 | disorders 0.161 → 0.440 and symptoms 0.069 → 0.199 after fine-tuning |

The simulated benchmark (E3) and the case-report matching experiments (E6, E6b, E8) were measured on the v1.2
snapshot and have not been rerun for v1.3.0; their v1.2 results are in `docs/history/v1.2/BENCHMARKS.md`.

## 5. Known gaps and open items

1. **Expert review of every curated layer.** This is the main blocker for any clinical or research claim. See [EXPERT_REVIEW_PLAN.md](EXPERT_REVIEW_PLAN.md).
2. **Pending symptom-splitting review.** 211 disorders ([symptom_extraction_changes.csv](../../reports/revision_audit/symptom_extraction_changes.csv)). Until it is decided, the data keeps the older stage 02b parse and cannot be reproduced exactly from the current code ([REBUILD_CHECK.md](../history/v1.3.0-revision/REBUILD_CHECK.md)).
   The case-report matching experiments also wait for this, since they depend on the symptom graph.
3. **End-to-end rebuild not fully verified.** Stages 02b–22 completed on 10–11 November; stages 00–02a (which need Poppler) and the benchmark stages have not been rerun.
4. **Licensing.** NAMASTE has no explicit open licence and WHO content is non-commercial, so the release stays CC BY-NC-SA 4.0. Rights review of the 14 sources has not started.
5. **No external test set.** 736 candidate publications are collected; none is annotated.
6. **Coverage gaps:**
   - 26% of herbs have no classical properties;
   - 30% of disorders have no definition;
   - 261 indication terms are unmatched;
   - 11 herb identities are unresolved.
7. **GitHub release page** for v1.3.0 still needs to be created from the tag.
