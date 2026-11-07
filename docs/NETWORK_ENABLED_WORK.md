# Network-enabled continuation — 7 November 2026

On 7 November 2026 the model host and Europe PMC were reachable, so the network-dependent steps below were run.

## Verified models and corrected experiments

The pinned NLLB and E5 weights match revision-specific Hub SHA-256 values (`reports/model_weight_verification.json`). Full-corpus retrieval uses 800 fixed record-derived queries per task, against 2,015 disorder and 10,049 eligible symptom candidates. Recall@10 for headword queries changed from 0.161 to 0.440 for disorders and from 0.069 to 0.199 for symptoms after one fine-tuning epoch. Translated-text recall@10 changed from 0.882 to 0.943 and from 0.720 to 0.854 respectively. These are retrieval scores, not clinical accuracy, and are not directly comparable to the old 800-candidate experiment.

Source-stratified E1 comparisons and exact fold identities are under `reports/revision_semantic/`. On NAMASTE-only rows, combined TF-IDF/embeddings macro-F1 is 0.842 versus 0.799 for the lexical baseline; the corresponding dosha figures are 0.751 versus 0.738. Hindi organ-system classification is 0.803 versus 0.717. Added-WHO scopes are reported separately, not treated as the same cohort. The actual run exposed and fixed mixed DataFrame feature-name types; the regression now fits the combined transformer.

## Translation proposals

Sixty-nine unique sources produced 89 field-level proposals for records with detected consecutive loops. Five sources needed one constrained retry; the final proposals have zero detected consecutive loops. Token-budgeted source chunks remain below the tokenizer truncation limit. This does not establish meaning preservation, and other automated quality flags remain visible. Canonical text was not overwritten. Prior and proposed text, source hashes, model revision and retry recipe are preserved in `reports/retranslation/`.

## New source material for review

The complete Europe PMC query returned 1,131 metadata records. After known-identifier filtering, 736 publication candidates have protected annotation templates. This is not 736 independently diagnosed patients: eligibility, patient units and labels remain unadjudicated. The current collection pointer is `reports/external_candidates/current_collection.json`. No article bodies were downloaded.

All 122 incomplete herb records were queried for botanical-name/property-keyword citation leads; 26 have leads. Zero hits do not prove no evidence. No rasa, virya or vipaka values were inferred. Source headword matching also provides 56 alternate definition candidates for 37 undefined disorders, all requiring alignment review before canonical use.

## Semantic artifacts and reproduction

Indexes carry per-entity model/source/array/ID fingerprints. The demo verifies them before retrieval. Existing matching indexes can be reused; use `--force` after changing the encoding recipe. Model weights and index binaries are generated local artifacts rather than Git source files.

Commands:

```bash
# optional cache locations (POSIX shell; on Windows PowerShell use $env:NAME = "...")
export HF_HOME=/tmp/ayurkb-hf-cache
export HF_HUB_DISABLE_XET=1
export MPLCONFIGDIR=/tmp/ayurkb-mpl
python scripts/00_get_models.py
python scripts/39_verify_model_weights.py
python scripts/23_finetune_search.py --report-dir reports/revision_semantic
python scripts/42_embedding_upgrade_rerun.py
python scripts/37_retranslate_flagged.py --scope loops
python scripts/37_retranslate_flagged.py --scope loops --retry-loops
python scripts/11_embed_index.py --part all --threads 3
python scripts/11_embed_index.py --part all --model models/multilingual-e5-small-ayurkb --out release/embeddings_ft --threads 3
```

The retrieval report-directory argument preserves historical release reports. Independent clinical/safety and permissions review remain excluded. Independent language approval and annotated external validation are still required for those claims.
