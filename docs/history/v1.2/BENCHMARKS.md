# AyurKB v1.2 benchmark results (historical)

*These results describe the **v1.2** release (5 November 2026) and its frozen inputs in `reports/ml/`. They are kept for comparison only. For the current release, see the Results section of the [README](../../../README.md); for what changed, see the [v1.3.0 release notes](../../releases/v1.3.0.md).*

The v1.3.0 revision found that v1.2's benchmark preprocessing was fitted outside the cross-validation folds. On identical data the effect was negligible (+0.004 macro-F1 on E1a, 0.000 on E1b), but every v1.3.0 figure is recomputed with fold-local preprocessing and uses the v1.3.0 cohorts, so the numbers below are not directly comparable.

`scripts/12_report.py` regenerates the two tables below from `reports/ml/`, and the v1.2 dataset report (`release/report.html`).

## Machine-learning benchmarks (E1–E4)

<!-- ML_TABLE_START -->
| Exp. | Task | Data | Best model | Score | Reference point |
|---|---|---|---|---|---|
| E1a | Disorder → organ system from clinical text | real · NAMASTE | Logistic Regression | macro-F1 0.801 | Dummy (majority) 0.034 |
| E1b | Doṣa involvement from symptom text (doṣa words masked) | real · NAMASTE | Logistic Regression | macro-F1 0.738 | Dummy (majority) 0.145 |
| E1c | Same task in English vs Hindi text | real · NAMASTE | Logistic Regression · English | macro-F1 0.801 | Dummy (majority) · English 0.034; Dummy (majority) · Hindi (MT) 0.034 |
| E2a | Herb vīrya (uṣṇa / śīta) from rasa, guṇa, vipāka, karma | real · herbs | Extra Trees | macro-F1 0.797 | rule: rasa majority (hot vs cold tastes) 0.760; rule: vipāka (madhura -> śīta) 0.635 |
| E2b | Doṣa-pacifying profile (V / P / K, mean of three labels) | real · herbs | SVM (RBF) | macro-F1 0.857 | Classical rule (Ayurvedic theory) 0.743; Dummy (majority) 0.376 |
| E2c | Herb indications from rasa / guṇa / vīrya / vipāka / doṣa | real · herbs | LightGBM | macro-F1 0.604 | Dummy (majority) 0.453 |
| E3a | Symptom set → disorder (60 disorders) | hybrid · simulated cases | MLP (neural net) | top-1 accuracy 0.928 | Knowledge-base matcher (IDF-cosine, no training) 0.967; Dummy (majority) 0.017 |
| E3b | Symptom set → disorder (all distinguishable disorders) | hybrid · simulated cases | Naive Bayes | top-1 accuracy 0.882 | Knowledge-base matcher (IDF-cosine, no training) 0.893 |
| E4 | Prakṛti (7 constitution types) from questionnaire | synthetic · WHO-grounded | Naive Bayes | macro-F1 0.653 | Classical questionnaire scoring (count V/P/K answers) 0.618; Dummy (majority) 0.053 |
<!-- ML_TABLE_END -->

## Real-world validation (E6) and tuning (E7)

**E6, real case reports.** On 85 published cases with a NAMASTE diagnosis and two or more presenting symptoms, the no-training KB matcher ranked the diagnosed disorder family in its top 10 for 20% of cases (top 30: 32%), against 9% for a popularity baseline and 0.6% by chance among 1,595 disorders. These were internal results on selected publications, not independent clinical validation.

**E7, tuning.** Nested cross-validation changed macro-F1 by −0.02 to +0.10. Tuning helped models with poorly suited defaults (Complement NB on text, Random Forest on the questionnaire) and slightly hurt on the 344-herb dataset, where the inner search overfit.

## Accuracy upgrades (E8)

Measured on the same rows and folds as the original v1.2 experiments:

<!-- UPGRADES_START -->
| Area | Before | After | What changed |
|---|---|---|---|
| Real cases: right disorder group in top 10 | 20% | 48% (±4%) | clinical-term crosswalk, meaning-based matching, group ranking, profiles learned from real cases (5-fold CV) |
| Real cases: right group ranked first | 2% | 17% | same |
| Adding WHO sign lists to the matcher (top 10) | 28% | 11% | made it worse: the lists are broad, so they are kept for explanation and left out of ranking |
| Real cases, top 10, with the fine-tuned search model | 48% | 47% | no gain on English case text (within ±4% noise); the fine-tuned model is used for Hindi search, where it helps |
| Search disorders by Sanskrit headword (recall@10) | 0.24 | 0.56 | search model fine-tuned on the dataset's own pairs, test concepts held out |
| Search symptoms by Sanskrit headword (recall@10) | 0.20 | 0.45 | search model fine-tuned on the dataset's own pairs, test concepts held out |
| Organ system from text (E1a), macro-F1 | 0.801 | 0.837 | TF-IDF + e5 + LR |
| Doṣa from symptom text (E1b), macro-F1 | 0.738 | 0.750 | TF-IDF + e5 + LR |
| Same task in Hindi (E1c), macro-F1 | 0.724 | 0.802 | TF-IDF + e5 + LR |
| Herb indications (E2c), macro-F1 | 0.604 | 0.603 | + chemistry + family: no meaningful gain - phytochemistry does not predict classical indications here |
| Disorders with a definition | 55.5% | 69.8% | 415 WHO definitions for disorders NAMASTE leaves undefined |
| Disorders with a symptom profile | 1,595 | 2,243 | 13,639 edges from WHO sign lists + inherited profiles for subtypes (flagged) |
| Disorders with a doṣa suggestion | 0 | 1,420 | text model, cross-validated accuracy 0.90; flagged for expert review |
| Hindi translation errors fixed by rule | - | 117 rows | curated post-edits, e.g. 'stiffness' had been translated as 'bitterness', 'nausea' as 'vomiting' |
<!-- UPGRADES_END -->
