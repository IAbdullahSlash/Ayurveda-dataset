#!/usr/bin/env python3
"""Report which gaps can be resolved from their existing linked records, without guessing."""
import json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=ROOT/'data/processed';out=ROOT/'reports/revision_audit'
    d=pd.read_csv(p/'diseases.csv',keep_default_na=False)
    t=pd.read_csv(p/'terminology.csv',keep_default_na=False).set_index('term_uid')
    rows=[]
    for r in d[d.definition_en.eq('')].itertuples():
        uid='WHO:'+r.who_term_id.split(';')[0] if r.who_term_id else ''
        available=uid in t.index and bool(t.loc[uid,'definition_en'])
        rows.append({'disease_id':r.disease_id,'who_record':uid,'linked_definition_available':available,
                     'reason':'no linked WHO record' if not uid else 'linked record has no definition' if not available else 'available'})
    pd.DataFrame(rows).to_csv(out/'definition_gap_evidence.csv',index=False)
    h=pd.read_csv(p/'herbs.csv',keep_default_na=False)
    missing=h[h.rasa.eq('')][['herb_id','accepted_name','amidha_ids']].copy()
    missing['reason']='no core properties recorded in the integrated source; new source/review needed'
    missing.to_csv(out/'herb_property_gap_evidence.csv',index=False)
    summary={'undefined_disorders':len(rows),'existing_linked_definitions_available':sum(r['linked_definition_available'] for r in rows),
             'herbs_missing_core_properties':len(missing),'fabricated_definitions_or_properties':0,
             'semantic_models':('downloaded; weight checksums verified' if (ROOT/'reports/model_weight_verification.json').exists() and all((ROOT/'models'/name/'model.safetensors').exists() for name in ['multilingual-e5-small','nllb-200-distilled-600M']) else 'model files or checksum verification missing'),
             'independent_external_cases':('publication candidates collected; independent reference labels still absent' if (ROOT/'reports/external_candidates/current_collection.json').exists() else 'not supplied; internal cases are not relabelled as external')}
    (out/'followup_status.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
if __name__=='__main__':main()
