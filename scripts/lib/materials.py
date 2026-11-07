"""Describe materia-medica identity scope without renumbering historical herb IDs."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def apply_material_types(herbs, overrides=None):
    if overrides is None:
        overrides = pd.read_csv(ROOT / 'curation/material_type_overrides.csv', keep_default_na=False)
    out = herbs.copy()
    linked = out.gbif_key.astype(str).str.strip().ne('')
    out['material_type'] = linked.map({True:'botanical_taxon_linked', False:'identity_unresolved'})
    out['taxon_identity_status'] = linked.map({True:'linked_gbif_taxon', False:'unresolved'})
    out['material_type_source_id'] = linked.map({True:'S7', False:''})
    out['material_type_source_record'] = out.gbif_key.astype(str).str.replace(r'\.0$', '', regex=True)
    out['material_type_note'] = linked.map({
        True:'Taxon identifier linkage; not independent authentication of a physical medicinal material.',
        False:'Source name retained; no species identity or botanical family inferred from a higher-rank fallback.'})
    if overrides.herb_id.duplicated().any():
        raise ValueError('Duplicate material category overrides')
    for row in overrides.itertuples():
        mask = out.herb_id.eq(row.herb_id)
        if mask.sum() != 1 or out.loc[mask, 'accepted_name'].iloc[0] != row.accepted_name:
            raise ValueError('Material override identity changed; source review required')
        if row.material_type != 'non_botanical_material' or not row.source_id or not row.source_record or not row.source_text:
            raise ValueError('Material override requires an explicit category and source evidence')
        if linked.loc[mask].any():
            raise ValueError('Non-botanical override conflicts with an existing taxon link')
        out.loc[mask, 'material_type'] = row.material_type
        out.loc[mask, 'taxon_identity_status'] = 'not_applicable_non_botanical'
        out.loc[mask, 'material_type_source_id'] = row.source_id
        out.loc[mask, 'material_type_source_record'] = row.source_record
        out.loc[mask, 'material_type_note'] = row.source_text + '; source material category only; no safety or efficacy approval.'
    return out


def apply_ingredient_material_types(ingredients, herbs):
    """A legacy herb_id may identify a non-botanical material; retain the link."""
    out = ingredients.copy()
    non_botanical = set(herbs.loc[herbs.material_type.eq('non_botanical_material'), 'herb_id'])
    mask = out.herb_id.isin(non_botanical) & out.ingredient_type.ne('mineral/animal/other')
    history = out.loc[mask].to_dict('records')
    out.loc[mask, 'ingredient_type'] = 'mineral/animal/other'
    return out, history
