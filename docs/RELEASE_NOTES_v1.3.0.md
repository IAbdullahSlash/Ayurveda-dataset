# AyurKB v1.3.0 release notes

**Status: draft for maintainer approval.** Merging the `release/v1.3.0` branch approves the version bump; tagging and publishing a GitHub release remain separate steps.

v1.3.0 is the peer-review revision of v1.2 (5 November 2026). It makes the data more cautious, more traceable and easier to review. It adds no expert-approved content: every curated layer, translation and safety record that was unreviewed in v1.2 is still unreviewed, and the new review material consists of drafts waiting for qualified reviewers.

## At a glance

| | v1.2 | v1.3.0 |
|---|---:|---:|
| Processed tables | 43 | 43 |
| Rows | 181,333 | 180,899 |
| Active herb → disorder links | 1,432 | 1,044 |
| Herbs with an explicit safety state | 0 | 466 (442 unassessed, 24 review pending) |
| Q&A pairs | 4,836 | 4,790 |
| Automated tests | 94 | 184 |

Rows fell because unsupported literature-evidence rows and Q&A pairs built on withdrawn links were removed. They are kept as history under `reports/indication_review/`.

## Data changes

- **Wrong herb → disorder links switched off.** The 48 approximate matches that pointed at the wrong disorder (for example *Kshaya*, wasting disease, matched to "psychic constitution") are quarantined, with the original target and the reason kept. Approximate matches and exact matches that fit more than one disorder no longer link automatically; they wait for a reviewed alias. Active links fell from 1,432 to 1,044.
- **Explicit safety states.** Every herb has `safety_assessment_status`. A blank never means safe, and the demo and Q&A text say so in English and Hindi.
- **Material identity.** Two minerals are no longer classed as plants (`material_type`), and formulation ingredients follow.
- **Exact source locators.** `terminology.source_locator` gives the WHO term ID and PDF page or the NAMASTE SAT code for all 6,233 terms; `diseases.definition_locator` does the same for 2,018 of 2,019 definitions.
- **Hindi.** 21 broken WHO/SAT definitions (decoding loops, wrong senses) are replaced, marked `expert_review_pending`. All Hindi corrections now run in one place (stage 25) from three curated files.
- **Symptom graph.** The Prameha profile keeps "frequent and excessive urination" as one symptom instead of two fragments.
- **Stable identifiers.** An append-only registry keeps herb and symptom IDs across rebuilds.

## Evaluation changes

- Benchmark preprocessing is fitted inside each cross-validation fold, and cohorts are reported separately. On identical data the earlier leak was negligible (+0.004 macro-F1 on E1a, 0.000 on E1b). The E1b change from 0.738 to 0.604 comes from a larger, harder cohort, not the leak fix.
- Embedding upgrades and bilingual retrieval were rerun with the pinned, checksum-verified models. Hindi headword retrieval recall@10 rose from 0.16 to 0.44 after fine-tuning.
- 736 candidate publications are collected for an external test set; none is annotated yet, so no external accuracy is claimed.

## Review material (drafts, not decisions)

- **Indication pre-review** (`docs/INDICATION_PREREVIEW.md`): a recommendation, confidence and rationale for all 118 inactive indication groups (649 rows). Confirming every accept and replacement would restore 1,622 of 1,693 links. Stage 54 copies only reviewer-signed rows into the alias ledger.
- **Herb-property and chemistry drafts**, safety, rights, Hindi and link-gap review batches (`docs/REVIEW_HANDOFF.md`).

## Engineering

- The pipeline runs on Windows: UTF-8 file handling throughout, imports that work under `python -I`, forward-slash paths in manifests, and SQLite connections closed before cleanup. A portability test blocks regressions.
- GitHub Actions runs the test suite on Linux and Windows for every push and pull request.
- Stage 02b is deterministic, and `.gitattributes` keeps raw source files byte-exact.
- Export publishes validated, content-addressed snapshots atomically; a clean CPU install is recorded in `requirements.cpu-py313.lock`.
- A glossary of Ayurveda and technical terms (`docs/GLOSSARY.md`).

## Reproducibility

A full `bash run_all.sh` rebuild was attempted on Windows on 8 November 2026 (see `docs/REBUILD_CHECK.md`). Stages 00, 01 and 02b–06 ran; stage 02a needs Poppler's `pdftotext`, and the run was stopped in the stage 06 quality check when disk space ran low. The check found and fixed three reproducibility bugs: stage 02b's diacritic repair depended on Python's per-run hash seed, stage 01 rewrote download timestamps on every run, and on Windows git converted the line endings of raw source files so they no longer matched their recorded hashes. The committed interim parse reflects one random 02b run; regenerating it would change 104 SAT definitions and 61 mahākaṣāya names (mostly restoring long final vowels) and is left for review. **A complete end-to-end rebuild has not been verified.**

## Known limitations

Unchanged from v1.2 except where noted above: curated layers, Hindi translations and herb safety need qualified review; NAMASTE has no explicit open licence and WHO content is non-commercial, so the release stays CC BY-NC-SA 4.0; case reports are an internal pool, not independent validation. See `docs/DATASHEET.md`.
