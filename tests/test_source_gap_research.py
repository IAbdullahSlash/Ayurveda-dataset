import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
research = importlib.import_module('49_research_source_gaps')


def test_name_candidate_requires_both_existing_identifiers_and_native_script():
    herb = dict(wikidata_qid='Q1', gbif_key='123.0')
    entity = dict(qid='Q1', gbif_ids=['123'], labels={'hi':'परीक्षण'})
    assert research.hindi_candidate(herb, entity)[0] == 'परीक्षण'
    assert research.hindi_candidate(herb, {**entity, 'qid':'Q2'})[0] == ''
    assert research.hindi_candidate(herb, {**entity, 'gbif_ids':['124']})[0] == ''
    assert research.hindi_candidate(herb, {**entity, 'labels':{}})[0] == ''
    assert research.hindi_candidate(herb, {**entity, 'labels':{'hi':'English fallback'}})[0] == ''


def test_deprecated_identity_claims_cannot_support_name_alignment():
    claim = dict(mainsnak={'datavalue':{'value':'123'}})
    entity = dict(id='Q1', claims={'P846':[dict(**claim, rank='deprecated'),
                                         dict(mainsnak={'snaktype':'novalue'}, rank='normal')]})
    selected = research.selected_entity(entity, 'test-time', 'test-hash')
    assert selected['gbif_ids'] == []
