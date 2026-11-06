import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from lib.translation_qe import has_decoding_loop

def test_repeated_symptom_structure_is_not_a_decoding_loop():
    assert not has_decoding_loop('सिर में दर्द; कंधों में दर्द; आँखों में दर्द; छाती में दर्द।')

def test_decoder_loops_are_detected():
    assert has_decoding_loop('लोहे के लोहे के लोहे के लोहे के लोहे के')
    assert has_decoding_loop('संवेदी संवेदी संवेदी संवेदी संवेदी')
    assert not has_decoding_loop('लंबे हत्थे वाली लोहे की कलछी।')
