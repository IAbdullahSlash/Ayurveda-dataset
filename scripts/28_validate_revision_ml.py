#!/usr/bin/env python3
"""Reproduce corrected benchmarks without overwriting historical release results."""
import argparse
import importlib
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all-models', action='store_true')
    ap.add_argument('--exp', choices=['e1','e4','both'], default='both')
    args = ap.parse_args()
    m = importlib.import_module('07_ml')
    out = ROOT / 'reports' / ('revision_full' if args.all_models else 'revision_validation')
    out.mkdir(exist_ok=True)
    for name in ['REP','FIG','MOD','P']:
        path = out / name
        path.mkdir(exist_ok=True)
        setattr(m, name, path)
    os.environ['AYURKB_SPLIT_DIR'] = str(out / 'splits')
    m.rd = lambda n: m.pd.read_csv(ROOT / 'data/processed' / f'{n}.csv', keep_default_na=False, low_memory=False)
    if not args.all_models:
        original_text, original_tabular = m.text_zoo, m.tabular_zoo
        keep = ['Dummy (majority)', 'Logistic Regression']
        m.text_zoo = lambda: {k:v for k,v in original_text().items() if k in keep}
        m.tabular_zoo = lambda *a,**kw: {k:v for k,v in original_tabular(*a,**kw).items() if k in keep}
    d = m.rd('diseases')
    d[['disease_id','definition_en','definition_hi','system_code','dosha_label']].to_csv(out / 'input_records.csv',index=False)
    if args.exp in ['e1','both']:
        m.e1(True)
    if args.exp in ['e4','both']:
        m.e4()
    print('Requested corrected benchmark run complete')
if __name__ == '__main__':
    main()
