# Response to the supplied peer review

The supplied review assessed commit `c30c158cce0a3c26d0b3fb3b9bfcc69216fe9a7e`; these revisions started from `99b53f5337260dd2e6a43f837e35e9909561eb96`. Findings were checked against the local checkout. The review's inability to execute pytest was an environment limitation and is superseded by the executed validation report.

| Finding | Response and evidence | Status |
|---|---|---|
| M1 Export attribution | WHO-filled definitions retain S3, original WHO record IDs and transformation flags; source dependencies are exported for every row | Specific defect fixed; exact historical assertion lineage remains limited by recorded inputs |
| M2 Metadata overclaims | Documentation now describes explicit and inherited metadata; all-table dependency regression check | Fixed |
| M3 Permissions | Source-rights ledger, actual text inventory and corrected commercial-subset claims | Technical disclosure fixed; qualified permissions assessment pending |
| M4 Semantic extraction | Modifier/conjunction preservation with tests, candidate diff and stratified review sample | Parser fixed; semantic accuracy requires adjudication |
| M5 Expert review | Source-visible queues and protocols; regeneration protects annotations | Review infrastructure complete; no verdicts fabricated |
| M6 Preprocessing | Training-fold transforms and E4 pre-selection holdout; additional herb/chemistry audit | Local fixes and E1/E2/E4/E7 reruns complete; suggestion validation corrected; embedding reruns completed with the pinned models |
| M7 Real-case comparators | Same-case paired evaluation interface, publication-cluster intervals, explicit baseline protocol | Tooling complete; external/adjudicated paired predictions pending |
| M8 Synthetic scope | Synthetic metrics kept separate and labelled; grouped QA manifests | Disclosure fixed; clinical study remains external work |
| M9 Hindi quality | Flagged translation queue with source text, IDs and hashes; fuller retrieval evaluation and stronger concept exclusions | Tooling complete; language review pending; model reruns completed |
| M10 Package | Relative descriptor paths, requirements/citation/provenance in archive, fresh-extraction smoke validation | Fixed locally |
| M11 Export gate | Failure gate, staged validated snapshots, rollback tests, accurate SQLite constraint description | Fixed |
| M12 Stable identities | Seeded append-only registry, reviewed aliases, migration/insertion tests; publication IDs in evaluation manifests | IDs fixed; external source membership still needs versioned collection when refreshed |
| M13 Distributed clauses | Text-bearing fields inventoried; S10 descriptions and source notes corrected | Disclosure fixed; rights decision pending |

Additional checks cover missing safety flags, iatrogenic relation filtering, translated QA references, record-level overlaps, and stale dictionary/count claims. The current full benchmark comparisons are research evidence for this snapshot, not a clinical validation certificate. A test pass does not turn unreviewed mappings, translations, safety records or permissions into approved data.
