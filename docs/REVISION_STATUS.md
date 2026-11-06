# Peer-review revision status

This revision addresses the nine agreed work areas. Technical changes are committed locally; nothing has been pushed. Completed engineering work is distinguished below from independent review or access prerequisites. No review verdict or clinical result has been invented.

| Task | Completed technical work | Remaining prerequisite or limitation |
|---|---|---|
| 1 Evaluation | Fold-local TF-IDF, E4 imputation/encoding/scaling, herb vocabulary, chemistry SVD/scaling and family encoding; E4 holdout before model selection; full E1/E2/E4 and nested E7 reruns; corrected suggestion validation; split manifests and model comparisons | Embedding-dependent stage 26 E1 rerun needs model-host access; cohort-defined indication labels remain part of the task definition |
| 2 Provenance | Source-dependency sidecar for every processed row; corpus metadata; WHO definition overrides; bilingual QA references; all-table regression validation | Conservative record dependencies are explicit; exact historical field attribution is unavailable where source data never recorded it; rights approval is separate |
| 3 Export/release | Validate before generation, staged immutable snapshots, atomic publication pointer, rollback of compatibility paths, correct descriptor paths, manifest verification and atomic ZIP publication | Snapshot pointer is the consistent multi-file reader API; legacy paths can be interrupted by process termination |
| 4 Rights/safety | Source-rights ledger and text inventory; corrected excerpt disclosures; explicit unassessed safety in demo/corpus; retrieval tiers distinguished from efficacy | Qualified rights and safety decisions; permission evidence is not supplied by request templates |
| 5 Identity | Append-only registry preserving existing IDs; locked atomic writes; reviewed alias mechanism; insertion, alias and full-current-ID tests | Future biological renames need explicit reviewed alias entries; distinct published IDs cannot be silently merged |
| 6 Semantics | Conjunction/modifier-scope fix; 212 candidate disorder changes; 150 stratified source-visible edges; negation/alternative tests | Expert adjudication before replacing the processed graph; precision/recall require a gold annotation set |
| 7 Hindi/retrieval | Prioritized source-visible translation queue with IDs/hashes; annotation protection; transitive concept and duplicate-description exclusions; full-corpus retrieval evaluator | Hindi expert approval, independent user queries, model download and semantic reruns; paraphrase overlap remains unmeasured |
| 8 Independent validation | Publication-group case manifests, connected-source bilingual QA splits, coverage by organ system, paired cluster-bootstrap evaluator | Existing case reports are an internal pool; new external cases, adjudicated labels and paired predictions are required for external claims |
| 9 Documentation | Corrected distribution/provenance/licensing claims, generated dictionary, current validation report, peer-review response and reproducible review protocols | Update review states only when actual decisions or new evidence arrive |

## Validation

See [current counts and benchmark evidence](REVISION_VALIDATION.md). E1/E2/E4 corrected reports and exact split manifests are retained under `reports/revision_full/`; original reports remain under `reports/ml/`. Full-model and smoke-test outputs are labelled separately. The lexical demo and a fresh extracted archive were exercised locally. This does not certify a complete offline rebuild of upstream sources or clinical correctness.

## Review workflows

- `python scripts/27_review_audit.py`: missingness, text-rights inventory, translation queue and case annotation template. Existing human annotations are protected.
- `python scripts/29_review_semantics.py`: candidate extraction changes and fixed-seed edge review sample. Regeneration refuses to overwrite human annotations.
- `python scripts/30_evaluation_manifest.py`: internal case/QA partitions and coverage; use `--paired-results FILE.csv` only with genuinely paired adjudicated predictions.
- `python scripts/28_validate_revision_ml.py --all-models`: E1/E4 reproduction; add `--exp e2` for the herb experiments.
- `python scripts/08_validate_export.py` then `bash scripts/13_package.sh`: validated snapshots and archive publication.

The identity registry is append-only. Unknown safety states remain unknown, and model suggestions remain unconfirmed. Source licences are recorded terms, not a legal certification of a combined or commercial subset.

## Model access blocker

The configured network proxy returned HTTP 403 for the pinned model at `huggingface.co`. A draft addition for that domain was saved to environment settings; runtime access remains restricted. Review and save the network change, then publish the environment as required by the configuration UI. Recheck the pinned download afterward; any redirected artifact host must also be assessed through the supported network settings. No credentials are requested or embedded.
