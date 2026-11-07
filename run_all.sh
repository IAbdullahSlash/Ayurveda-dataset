#!/usr/bin/env bash
# Rebuild AyurKB end to end. API responses and translations are cached under data/interim/cache/,
# so a re-run is fast and deterministic; delete that folder to refetch everything.
set -euo pipefail
cd "$(dirname "$0")"
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1} OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-1}
py() { python3 -I -u "$@"; }

py scripts/00_get_models.py             # NLLB-200 + multilingual-e5 weights (skipped when present)
py scripts/01_fetch_sources.py            # sources + PROVENANCE.json (sha256)
py scripts/02a_parse_who.py               # WHO terminology (validated against Annex 2)
py scripts/02b_parse_namaste.py           # NAMASTE morbidity + SAT (transliteration, diacritic repair)
py scripts/02c_parse_herbs.py             # SAT-F plants, mahākaṣāya, Amidha, USDA Duke
py scripts/03_enrich_taxonomy.py          # GBIF validation + Wikidata Hindi names
py scripts/04_build_kb.py                 # integration -> data/processed/
py scripts/05_evidence.py                 # PubMed + ClinicalTrials.gov
py scripts/06_translate.py --translate --beams 1 --threads 3   # English -> Hindi (cached)
py scripts/06_translate.py --qe 300 --merge                     # back-translation QE + merge *_hi columns
py scripts/07_ml.py --exp e1 e2 e3 e4 e1c # ML experiments E1-E4 (+ bilingual E1c)
py scripts/10_crosslingual.py             # E5 bilingual retrieval
py scripts/11_embed_index.py --part all   # multilingual semantic index (English + Hindi)
py scripts/14_case_reports.py             # Europe PMC case reports -> real-world layer + experiment E6
py scripts/15_link_evidence.py            # PubMed evidence tier for every herb / formulation link
py scripts/16_links_scripts_concepts.py   # disorder -> procedure rules, 8 regional scripts, headword concepts
py scripts/17_phytochem_ids.py            # PubChem identifiers (+ ChEMBL targets in a separate CC BY-SA file)
py scripts/18_image_datasets.py           # links to CC BY 4.0 plant-image datasets
# optional: py scripts/19_ictrp_import.py --csv <manual WHO ICTRP export>
py scripts/25_fill_missing.py             # WHO definitions + sign lists, inherited profiles, doṣa suggestions, MT post-edits
py scripts/32_apply_hindi_postedits.py    # source-hash-checked Hindi definition fixes (curation/hindi_definition_postedits.csv)
py scripts/33_repair_symptom_scope.py     # Prameha coordination repair in the symptom graph (idempotent)
py scripts/24_improve_matching.py         # experiment E6b: crosswalk, semantic matching, group ranking, case-learned profiles
py scripts/26_model_upgrades.py           # E2c+ (chemistry features) and E1+ (multilingual embeddings) vs the originals
py scripts/23_finetune_search.py          # E5b: domain fine-tuning of the multilingual search model (~40 min CPU)
py scripts/20_tuning.py                   # experiment E7: nested-CV hyperparameter tuning
py scripts/08_validate_export.py          # integrity checks, QA pairs, corpus, SQLite, datapackage
py scripts/09_docs.py                     # data dictionary
py scripts/21_review_workbooks.py --build # expert-review workbook
py scripts/22_build_tools.py              # interactive review desk + Prakṛti questionnaire
python3 -m pytest -q tests/               # all checks
py scripts/12_report.py                   # release/report.html + README ML table
