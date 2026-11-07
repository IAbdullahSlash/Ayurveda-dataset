#!/usr/bin/env python3
"""Find source-visible chemistry leads without transferring compounds across taxa."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from lib.review import write_review_csv

ROOT = Path(__file__).resolve().parents[1]


def main():
    herbs_path = ROOT / 'data/processed/herbs.csv'
    tax_path = ROOT / 'data/interim/duke_fnftax.parquet'
    chemistry_path = ROOT / 'data/interim/duke_farmacy_new.parquet'
    herbs = pd.read_csv(herbs_path, keep_default_na=False)
    taxa = pd.read_parquet(tax_path, columns=['FNFNUM', 'TAXON'])
    chemistry = pd.read_parquet(chemistry_path, columns=['FNFNUM', 'CHEM'])
    available = taxa[taxa.FNFNUM.isin(set(chemistry.FNFNUM))]
    source_names = set(available.TAXON)
    missing = herbs[pd.to_numeric(herbs.n_phytochemicals).eq(0)]
    queue = []
    for herb in missing.itertuples():
        variants = {n.strip() for n in herb.botanical_names_in_sources.split(';') if n.strip()}
        matches = sorted(variants & source_names)
        fnfs = set(available.loc[available.TAXON.isin(matches), 'FNFNUM'])
        rows = chemistry[chemistry.FNFNUM.isin(fnfs)]
        current_targets = sorted(set(herbs.loc[herbs.accepted_name.isin(matches), 'herb_id']))
        queue.append(dict(herb_id=herb.herb_id, accepted_name=herb.accepted_name,
            material_type=herb.material_type, recorded_botanical_names=herb.botanical_names_in_sources,
            exact_master_name_present=herb.accepted_name in source_names,
            recorded_variant_source_taxa=';'.join(matches), duke_taxon_ids=';'.join(sorted(fnfs)),
            candidate_source_rows=len(rows), candidate_distinct_chemicals=rows.CHEM.nunique(),
            existing_master_ids_named_by_source_taxa=';'.join(current_targets),
            interpretation='Recorded variant is a review lead, not permission to transfer chemical observations across species or preparations.',
            verdict='', corrected_value='', reviewer='', reference=''))
    out = ROOT / 'reports/source_gap_research'
    out.mkdir(exist_ok=True)
    frame = pd.DataFrame(queue)
    write_review_csv(frame.sort_values(['candidate_source_rows', 'herb_id'], ascending=[False, True]), out / 'chemistry_gap_review.csv')
    inputs = {}
    for path in [herbs_path, tax_path, chemistry_path]:
        with path.open('rb') as stream:
            inputs[str(path.relative_to(ROOT))] = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = dict(materia_medica_records=len(herbs), with_current_chemistry=len(herbs)-len(missing),
        without_current_chemistry=len(missing), missing_by_material_category=missing.material_type.value_counts().to_dict(),
        exact_master_names_with_unused_source_chemistry=int(frame.exact_master_name_present.sum()),
        records_with_recorded_variant_leads=int(frame.recorded_variant_source_taxa.ne('').sum()),
        canonical_chemistry_rows_added=0, taxonomic_adjudication=False, input_sha256=inputs)
    (out / 'chemistry_gap_status.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
