# Evaluation and independent-validation protocol

`python scripts/30_evaluation_manifest.py` writes fixed-seed internal publication-group and QA split manifests plus coverage by organ system. Existing published cases are not new external cases and are not necessarily independent patients. The current case split has 396 train, 56 validation and 113 test reports. Group identity uses PMCID, then DOI, then case ID; potential duplicate publications and multiple patients still require adjudication.

QA groups are connected components over every referenced record ID. English and Hindi equivalents and shared herb/disorder facts stay together. The current largest group has 696 records, so split fractions are approximate. Additional disease-family holdouts are needed for claims about unseen disease families. Retain the exact source snapshot and split manifests with each run.

For independent validation, collect a separate source pool, preserve publication and patient-unit linkage, define exclusions before scoring, and have two qualified reviewers adjudicate presentation-only inputs and gold labels. Keep diagnosis-bearing text out of model inputs. Lock the candidate set, ranking unit (exact disorder or ancestor group), model configuration, and comparison baselines before evaluating. Record externality, annotation provenance and any ethical requirements; the present manifests do not supply these approvals.

Report the same cases for the lexical matcher, training-frequency baseline, case-only profile model and combined model. Store one paired row per case with `case_id`, `independence_group`, `model_rank`, and `baseline_rank`. Use positive 1-based ranks; infinity denotes a gold record absent from the ranked candidates. Do not silently drop failures or missing ranks. All paired results must use the same candidate set and gold-label definition.

`python scripts/30_evaluation_manifest.py --paired-results FILE.csv` reports the model-minus-baseline hit@10 difference and a 95% percentile interval from 5,000 publication-cluster bootstrap samples (seed 42). This is sampling uncertainty, not the standard deviation across random model seeds. A toy-data test checks pairing and clustering. No empirical interval is reported yet: the old rank file lacks paired strongest-baseline predictions, and no independently adjudicated external results have been supplied.

## Learned feature audit

E1 TF-IDF and E4 imputation/encoding/scaling now fit within training folds; E4 reserves 750 synthetic records before choosing its model. Stage 26 TF-IDF and chemistry SVD/scaling use the same fold-local API. Frozen pretrained embedding inference is allowed across the corpus; corpus-fitted transforms are not.

Additional E2 feature/label choices in `herb_matrix(min_count=6)`, the top-12 indication target definition and stage 26 family/activity selection are cohort-defined. Those historical E2 scores remain exploratory and must not be represented as fully nested prospective estimates. Repeating the complete E2 model-selection study is a separate remaining scientific validation step; no change to E1/E4 repairs those estimates by implication.

Synthetic E3/E4 results remain explicitly synthetic. They cannot certify patient-level performance. Matched original-versus-revised score comparisons should use the same models, records and ranking units; the altered E4 development/holdout design changes its denominator.
