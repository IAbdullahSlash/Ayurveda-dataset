#!/usr/bin/env bash
# Package the AyurKB release. Excludes downloaded third-party model weights (NLLB-200, opus-mt, e5:
# ~3 GB, fetchable from Hugging Face), Python caches and cached article texts.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=release/AyurKB_v1.2.zip
rm -f "$OUT"
zip -qr "$OUT" README.md run_all.sh docs curation scripts tests examples \
  data/raw data/processed data/interim/cache \
  release/ayurkb.sqlite release/ayurkb_corpus.jsonl release/datapackage.json release/report.html release/embeddings \
  release/tools review reports models/trained \
  $( [ -d release/chembl ] && echo release/chembl ) \
  -x "*/__pycache__/*" "*.pyc" \
     "data/interim/cache/epmc_fulltext/*" "data/interim/cache/epmc_case_reports.json"
# Europe PMC full texts and abstracts are third-party articles: they stay out of the package
# (stage 14 re-downloads them); only identifiers and extracted KB entities are distributed.
ls -la "$OUT"
unzip -l "$OUT" | tail -1
