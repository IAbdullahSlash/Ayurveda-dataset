# Revision validation

Executed test suite: **135 passed, 1 skipped, 0 failed, 0 errors**.

Current processed data: **43 tables, 181,333 rows**. Rows include links, derived records and synthetic observations; they are not independent patients.

## Corrected benchmark results

| Experiment | Model | Macro-F1 | Scope |
|---|---|---:|---|
| E1a_system_from_text  | Logistic Regression | 0.811 | internal CV; not external clinical validation |
| E1b_dosha_from_masked_text  | Logistic Regression | 0.604 | internal CV; not external clinical validation |
| E1c_bilingual_system_from_text English | Logistic Regression | 0.805 | internal CV; not external clinical validation |
| E1c_bilingual_system_from_text Hindi (MT) | Logistic Regression | 0.729 | internal CV; not external clinical validation |
| E2a_virya  | Extra Trees | 0.792 | internal CV; not external clinical validation |
| E2b_dosha_pacify  | SVM (RBF) | 0.852 | internal CV; not external clinical validation |
| E2c_indications  | LightGBM | 0.606 | internal CV; not external clinical validation |
| E4_prakriti  | Naive Bayes | 0.636 | synthetic development CV; 750 final holdout records |

## Corrected nested tuning

| Task | Model | Default macro-F1 | Tuned macro-F1 |
|---|---|---:|---:|
| E1a organ-system from text | Logistic Regression | 0.811 | 0.816 |
| E1a organ-system from text | Linear SVM | 0.819 | 0.820 |
| E1a organ-system from text | Complement Naive Bayes | 0.711 | 0.765 |
| E1a organ-system from text | SGD (modified Huber) | 0.793 | 0.807 |
| E2a herb vīrya | Logistic Regression | 0.780 | 0.776 |
| E2a herb vīrya | SVM (RBF) | 0.774 | 0.776 |
| E2a herb vīrya | k-Nearest Neighbours | 0.775 | 0.773 |
| E2a herb vīrya | Random Forest | 0.788 | 0.786 |
| E2a herb vīrya | LightGBM | 0.784 | 0.778 |
| E4 prakṛti (synthetic) | Logistic Regression | 0.631 | 0.650 |
| E4 prakṛti (synthetic) | Random Forest | 0.494 | 0.593 |
| E4 prakṛti (synthetic) | LightGBM | 0.565 | 0.572 |
| E4 prakṛti (synthetic) | MLP (neural net) | 0.629 | 0.630 |

Preprocessing is fitted inside both inner and outer folds. Fold-score p-values are descriptive because CV training sets overlap.

## Corrected chemistry comparison

| Features | Best model | Mean label macro-F1 |
|---|---|---:|
| original features | LightGBM | 0.606 |
| + chemistry + family | Logistic Regression | 0.600 |
| + chemistry compressed to 20 components | Logistic Regression | 0.599 |

Results and split manifests are in `reports/revision_full/`. The historical v1.2 reports remain in `reports/ml/` for comparison. E4 reserves a final holdout before model selection; its revised CV denominator differs from the original release.

The E2c chemistry-upgrade report is stored separately as `E2c_plus.json` because it compares feature variants. Embedding-dependent and retrieval results, when present below, use their own recorded source snapshots and candidate scopes.

Benchmark results refer to their frozen input snapshots in `reports/revision_full/`; subsequent language and graph repairs are not a new benchmark rerun.

Independent clinical review, bilingual adjudication, source-rights decisions and an external test set remain pending. See `REVISION_STATUS.md` and the dedicated review protocols.

## Full-corpus bilingual retrieval

| Task / query | Base recall@10 | Fine-tuned recall@10 |
|---|---:|---:|
| diseases / hindi_headword | 0.161 | 0.440 |
| diseases / hindi_text | 0.882 | 0.943 |
| symptoms / hindi_headword | 0.069 | 0.199 |
| symptoms / hindi_text | 0.720 | 0.854 |

Candidate counts: {'diseases': 2015, 'symptoms': 10049}. Fixed record-derived queries; this is retrieval evaluation, not independent clinical validation. Old 800-candidate scores are not directly comparable.

## Source-stratified embedding upgrades

| Task / source scope | Rows | TF-IDF macro-F1 | Combined macro-F1 |
|---|---:|---:|---:|
| E1a organ system | NAMASTE-only source definitions | 1548 | 0.799 | 0.842 |
| E1b doṣa from masked text | NAMASTE-only source definitions | 351 | 0.738 | 0.751 |
| E1c Hindi (MT) | NAMASTE-only source definitions | 1548 | 0.717 | 0.803 |
| E1a organ system | + WHO-filled definitions (stage 25) | 1950 | 0.811 | 0.856 |
| E1b doṣa from masked text | + WHO-filled definitions (stage 25) | 484 | 0.604 | 0.613 |
