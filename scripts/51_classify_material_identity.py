#!/usr/bin/env python3
"""Make botanical/non-botanical identity scope explicit while preserving records and IDs."""
import json
from pathlib import Path
import pandas as pd
from lib.materials import apply_material_types, apply_ingredient_material_types

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'data/processed/herbs.csv'
    before = pd.read_csv(path, keep_default_na=False)
    result = apply_material_types(before)
    if not before.herb_id.equals(result.herb_id) or not before.accepted_name.equals(result.accepted_name):
        raise ValueError('Classification must preserve historical IDs and names')
    result.to_csv(path, index=False)
    result.to_parquet(path.with_suffix('.parquet'), index=False)
    ingredient_path = ROOT / 'data/processed/formulation_ingredients.csv'
    ingredients, corrected = apply_ingredient_material_types(pd.read_csv(ingredient_path, keep_default_na=False), result)
    ingredients.to_csv(ingredient_path, index=False)
    ingredients.to_parquet(ingredient_path.with_suffix('.parquet'), index=False)
    report_path = ROOT / 'reports/material_identity_status.json'
    old_report = json.loads(report_path.read_text()) if report_path.exists() else {}
    history = old_report.get('previous_ingredient_records', [])
    for row in corrected:
        if not any(r['form_id'] == row['form_id'] and r['rank'] == row['rank'] for r in history):
            history.append(row)
    report = dict(records=len(result), categories=result.material_type.value_counts().to_dict(),
        ids_preserved=True, names_changed=0, species_merges=0, safety_assessments_created=0,
        previous_ingredient_records=history, linked_non_botanical_ingredient_rows=int(ingredients.herb_id.isin(set(result.loc[result.material_type.eq('non_botanical_material'),'herb_id'])).sum()),
        note='The historical herbs table is a materia-medica inventory; not every row is an identified plant species.')
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
