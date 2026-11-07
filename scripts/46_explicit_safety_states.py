#!/usr/bin/env python3
"""Persist explicit safety states without generating clinical assessments."""
import json
from pathlib import Path
import pandas as pd
from lib.safety import apply_safety_states

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'data/processed/herbs.csv'
    frame = apply_safety_states(pd.read_csv(path, keep_default_na=False))
    frame.to_csv(path, index=False)
    frame.to_parquet(path.with_suffix('.parquet'), index=False)
    result = dict(herbs=len(frame), states=frame.safety_assessment_status.value_counts().to_dict(),
        note='Existing hazard flags remain unreviewed; assessed never means universally safe.')
    (ROOT / 'reports/safety_assessment_status.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
