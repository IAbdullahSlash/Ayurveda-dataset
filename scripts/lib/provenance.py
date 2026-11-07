"""Conservative source dependencies, with explicit field overrides and review states.

Source dependency is not permission to redistribute or proof of clinical validity.
Unmapped sources remain visible rather than being assigned an invented licence.
"""
import hashlib
import json
import re

# These policies identify construction inputs for tables without direct source columns.
POLICIES = {
    'controlled_vocabulary': ['S0'], 'formulation_ingredients': ['S0'],
    'formulation_indications': ['S0'], 'herb_group_members': ['S2'],
    'case_report_entities': ['S10'], 'case_report_symptoms_semantic': ['S10'],
    'dosha_suggestions': ['S1'], 'prakriti_synthetic_cohort': ['S0', 'S3'],
    'therapy_evidence': ['S8'], 'evidence_queries': ['S8', 'S9'],
    'ictrp_trial_links': ['S13'],
}
ID_FIELDS = ('disease_id', 'herb_id', 'form_id', 'symptom_id', 'term_uid', 'case_id',
             'therapy_id', 'dx_id', 'group_id', 'concept_id', 'qa_id', 'person_id')
REFERENCE_FIELDS = set(ID_FIELDS) | {'entity_id', 'kb_ids', 'record_ids', 'case_ids',
    'herb_ids', 'form_ids', 'dx_disease_ids', 'inherited_from', 'who_term_id', 'term_uid',
    'original_disease_id', 'candidate_disease_ids'}

def source_ids(row):
    return set(re.findall(r'\bS\d+\b', ';'.join(str(row.get(k, '')) for k in
        ['source_id','source_ids','source','sources'])))

def identity(table, row):
    # Content address also distinguishes relation rows sharing their parent entity IDs.
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)
    return table + ':' + hashlib.sha256(payload.encode()).hexdigest()

def references(row):
    return {v.strip() for key in REFERENCE_FIELDS for v in str(row.get(key, '')).split(';') if v.strip()}

def build_index(tables):
    index = {}
    for table, df in tables.items():
        unique_keys = [key for key in ID_FIELDS if key in df and df[key].is_unique]
        for row in df.to_dict('records'):
            own = source_ids(row) | set(POLICIES.get(table, []))
            if table == 'diseases' and str(row.get('definition_source', '')).startswith('WHO'):
                own.add('S3')
            for key in unique_keys:
                value = str(row.get(key, ''))
                # Only entity masters contribute identity attribution; edges must not
                # contaminate a parent entity with every other source linked to it.
                if value:
                    index.setdefault(value, set()).update(own)
    return index

def metadata(table, row, index, licences):
    direct = source_ids(row) | set(POLICIES.get(table, []))
    refs = references(row)
    inherited = set().union(*(index.get(ref, set()) for ref in refs)) if refs else set()
    sources = direct | inherited
    fields = {}
    if table == 'diseases':
        is_who = str(row.get('definition_source', '')).startswith('WHO')
        origin = 'S3' if is_who else 'S1'
        record = row.get('who_term_id', '') if is_who else row.get('disease_id', '')
        for field in ['definition_en','definition_hi']:
            if row.get(field):
                fields[field] = {'source_ids':[origin], 'source_record_ids':[record],
                    'method':row.get(field + '_method', row.get('definition_source','')),
                    'quality_flags':row.get(field + '_qe_flags','')}
                sources.add(origin)
    if table == 'herbs':
        for field in ['rasa','guna','virya','vipaka','karma_actions','dosha_pacify','dosha_aggravate','parts_used','description_en']:
            if row.get(field) and row.get('amidha_ids'):
                fields[field] = {'source_ids':['S5'],
                    'source_record_ids':[str(row['amidha_ids'])], 'method':'Amidha property extraction; variants retained'}
        if row.get('name_hi_common') and row.get('wikidata_qid'):
            fields['name_hi_common']={'source_ids':['S6'],'source_record_ids':[str(row['wikidata_qid'])]}
        for field in ['safety_class','safety_hazard_en','safety_hazard_hi','requires_shodhana']:
            fields[field] = {'source_ids':['S0'] if row.get(field) else [],
                'source_record_ids':[row.get('herb_id','')],
                'review_status':'not_independently_adjudicated' if row.get('safety_class') else 'unassessed'}
        if row.get('safety_class'):
            sources.add('S0')
        for field in ['safety_assessment_status', 'safety_review_reviewer', 'safety_review_reference', 'safety_review_assessment_date', 'safety_review_scope']:
            if field in row:
                fields[field] = {'method': 'explicit assessment state; herb_safety_reviews.csv',
                    'review_status': row.get('safety_assessment_status', 'unassessed'),
                    'reference': row.get('safety_review_reference', ''),
                    'scope': row.get('safety_review_scope', '')}
    for field in row:
        if field.endswith('_hi') and row.get(field) and field not in fields:
            fields[field] = {'source_ids':sorted(sources), 'attribution':'record_dependency',
                'method':row.get(field + '_method','unspecified'),
                'quality_flags':row.get(field + '_qe_flags','')}
    unresolved = sorted(sources - set(licences))
    return {'record_ref':identity(table,row), 'source_ids':sorted(sources),
        'source_record_ids':sorted(refs), 'source_terms':{s:licences[s] for s in sorted(sources) if s in licences},
        'default_field_attribution':'conservative_record_dependencies', 'field_overrides':fields,
        'data_origin':row.get('data_origin','derived_or_inherited; see construction script'),
        'review_status':row.get('verification_status', row.get('status','not_adjudicated')),
        'rights_status':'requires_review',
        'unresolved_sources':unresolved,
        'provenance_status':'resolved_dependencies' if sources and not unresolved else 'unresolved'}

def write_sidecar(tables, path):
    index = build_index(tables)
    licences = dict(zip(tables['sources'].source_id, tables['sources'].licence))
    counts = {}
    with path.open('w',encoding='utf-8') as stream:
        for table, df in sorted(tables.items()):
            unresolved = 0
            for row in df.to_dict('records'):
                meta = metadata(table,row,index,licences)
                unresolved += meta['provenance_status'] == 'unresolved'
                stream.write(json.dumps({'table':table, **meta},ensure_ascii=False,default=str)+'\n')
            counts[table] = {'rows':len(df),'unresolved':unresolved}
    return counts
