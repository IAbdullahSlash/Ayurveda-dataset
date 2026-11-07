# Follow-up review work progress

Work follows [the ordered comparison plan](REVIEW_COMPARISON_AND_WORK_PLAN.md). Changes are local; no push or public release is authorized by this log. Dates use the user's Asia/Calcutta timezone.

## 1. Contain reported indication errors — completed, 8 November 2026

All 1,693 source indication rows are preserved. The 48 PDF-reported wrong mappings plus the one overly broad fever mapping have blank active targets, retained original targets/names, explicit quarantine states, reasons, and a reference to the uploaded PDF's checksum and page. This is containment, not independent clinical adjudication or approval of a replacement.

Stage 04 reapplies containment, stage 15 excludes contained links from new literature queries, and the demo filters both indications and stale unsupported evidence. QA generation also uses active links. Targeted regression checks passed (five tests including existing safety checks). Rebuilt distributed derivatives are tracked under task 3 rather than claimed complete here.

## 2. Conservative matcher and reviewed-alias interface — engineering complete; adjudication pending

Fuzzy spelling alone no longer supplies an active target. Exact-skeleton matches with multiple disorder candidates also abstain: 266 rows across 19 raw indication groups have that ambiguity. These are candidates, not newly established errors. Current states are 1,044 unique exact source matches (still unreviewed), 339 pending candidates, 49 quarantined rows, and 261 unmatched rows.

`curation/indication_aliases.csv` is intentionally empty. An accepted alias needs an existing disorder ID, an equivalent-sense decision, a reviewer identifier and source reference; rejected aliases are supported too. Reviewer fields record supplied decisions rather than certifying qualifications. No clinical approval was generated. All 20 fuzzy groups and 19 ambiguous exact groups are in the protected review queue; a fixed-seed 60-row exact-match sample is also prepared. Candidate targets, historical methods/scores, reasons and references survive reruns.

Five policy regression tests pass, covering idempotence, blocking old inputs and evidence, preserving separately supported pairs, ambiguous/fuzzy abstention, and reviewed-alias requirements. Independent precision/recall and alias adjudication remain pending.
