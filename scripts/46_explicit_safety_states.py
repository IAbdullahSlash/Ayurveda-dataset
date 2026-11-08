#!/usr/bin/env python3
"""Persist explicit safety states without generating clinical assessments."""
import json
from pathlib import Path
import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I omits the script folder
from lib.safety import apply_safety_states

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'data/processed/herbs.csv'
    frame = apply_safety_states(pd.read_csv(path, keep_default_na=False))
    frame.to_csv(path, index=False)
    frame.to_parquet(path.with_suffix('.parquet'), index=False)
    result = dict(herbs=len(frame), states=frame.safety_assessment_status.value_counts().to_dict(),
        note='Existing hazard flags remain unreviewed; assessed never means universally safe.')
    (ROOT / 'reports/safety_assessment_status.json').write_text(json.dumps(result, indent=2) + '\n', encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
