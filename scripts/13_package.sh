#!/usr/bin/env bash
# Package only a validated export. Publish the archive by atomic rename.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN=${PYTHON_BIN:-python3}
"$PYTHON_BIN" - <<'PY'
import hashlib,json
from pathlib import Path
manifest=json.loads(Path('release/current_export.json').read_text())
for name, expected in manifest['sha256'].items():
    with open(name,'rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:
            raise SystemExit('Export changed since validation: '+name+'; rerun stage 08')
PY
OUT=release/AyurKB_v1.2.zip
TEMP_ARCHIVE=$(mktemp release/.AyurKB-package-XXXXXX.zip)
rm "$TEMP_ARCHIVE"
trap 'rm -f "$TEMP_ARCHIVE"' EXIT
inputs=(README.md requirements.txt CITATION.cff run_all.sh docs curation scripts tests examples
  data/raw data/processed data/interim/cache
  release/ayurkb.sqlite release/ayurkb_corpus.jsonl release/ayurkb_provenance.jsonl
  release/datapackage.json release/report.html release/tools review reports models/trained)
for optional in release/embeddings release/chembl; do
  if [ -d "$optional" ]; then inputs+=("$optional"); fi
done
zip -qr "$TEMP_ARCHIVE" "${inputs[@]}" -x '*/__pycache__/*' '*.pyc' \
  'data/interim/cache/epmc_fulltext/*' 'data/interim/cache/epmc_case_reports.json' \
  'reports/revision_full/MOD/*' 'reports/revision_full/P/*' 'reports/revision_validation/*'
unzip -tq "$TEMP_ARCHIVE"
mv "$TEMP_ARCHIVE" "$OUT"
# Processed tables include extracted clauses; see the distribution inventory and source terms.
ls -lh "$OUT"
