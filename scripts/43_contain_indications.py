#!/usr/bin/env python3
"""Apply source-linked indication containment without rebuilding upstream tables."""
import json
from pathlib import Path
import pandas as pd
from lib.indication_policy import contain_indications

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'data/processed/herb_indication.csv'
    original = pd.read_csv(path, keep_default_na=False)
    result = contain_indications(original)
    result.to_csv(path, index=False)
    result.to_parquet(path.with_suffix('.parquet'), index=False)
    report = {'rows_preserved': len(result), 'states': result.mapping_status.value_counts().to_dict(),
              'replacement_labels_invented': 0, 'independent_expert_approval': False}
    (ROOT / 'reports/indication_containment.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
