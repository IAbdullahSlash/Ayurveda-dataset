# Follow-up review work progress

Work follows [the ordered comparison plan](REVIEW_COMPARISON_AND_WORK_PLAN.md). Changes are local; no push or public release is authorized by this log. Dates use the user's Asia/Calcutta timezone.

## 1. Contain reported indication errors — completed, 8 November 2026

All 1,693 source indication rows are preserved. The 48 PDF-reported wrong mappings plus the one overly broad fever mapping have blank active targets, retained original targets/names, explicit quarantine states, reasons, and a reference to the uploaded PDF's checksum and page. This is containment, not independent clinical adjudication or approval of a replacement.

Stage 04 reapplies containment, stage 15 excludes contained links from new literature queries, and the demo filters both indications and stale unsupported evidence. QA generation also uses active links. Targeted regression checks passed (five tests including existing safety checks). Rebuilt distributed derivatives are tracked under task 3 rather than claimed complete here.

## 2. Conservative matcher and reviewed-alias interface — engineering complete; adjudication pending

Fuzzy spelling alone no longer supplies an active target. Exact-skeleton matches with multiple disorder candidates also abstain: 266 rows across 19 raw indication groups have that ambiguity. These are candidates, not newly established errors. Current states are 1,044 unique exact source matches (still unreviewed), 339 pending candidates, 49 quarantined rows, and 261 unmatched rows.

`curation/indication_aliases.csv` is intentionally empty. An accepted alias needs an existing disorder ID, an equivalent-sense decision, a reviewer identifier and source reference; rejected aliases are supported too. Reviewer fields record supplied decisions rather than certifying qualifications. No clinical approval was generated. All 20 fuzzy groups and 19 ambiguous exact groups are in the protected review queue; a fixed-seed 60-row exact-match sample is also prepared. Candidate targets, historical methods/scores, reasons and references survive reruns.

Five policy regression tests pass, covering idempotence, blocking old inputs and evidence, preserving separately supported pairs, ambiguous/fuzzy abstention, and reviewed-alias requirements. Independent precision/recall and alias adjudication remain pending.

## 3. Refresh mapping-dependent outputs — completed

The offline derivative refresh retains 1,039 evidence pairs supported by active indications and preserves 388 withdrawn pairs as explicitly historical audit material. It checks for a separate active indication before withdrawing a shared pair and refuses to manufacture literature records for newly approved targets. Original literature counts retain their old query scope; no fresh searches are claimed. Eight case-report KB-overlap flags changed; the observations themselves are unchanged.

QA, corpus, source dependencies, SQLite, descriptor, dictionary, system coverage, grouped QA splits, review desk and local archive were rebuilt. Current QA has 4,790 rows, and the 43 processed tables total 180,899 rows. Historical review and benchmark artifacts retain their original snapshot meaning. Export now fails if indication policy is violated or unsupported evidence remains. The full suite passes: **142 tests, zero failures/skips/errors**. Fresh archive extraction, CSV equality, SQLite integrity and lexical execution from an arbitrary working directory also passed; this check did not reinstall dependencies or bundle model weights.
