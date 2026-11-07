import importlib,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
module=importlib.import_module('37_retranslate_flagged')
def test_chunking_preserves_source_and_budget():
    source=' '.join(['fever;','pain','without','vomiting.']*20)
    pieces=module.split_budget(source,lambda text:len(text.split())+2,budget=12)
    assert ' '.join(pieces)==source
    assert all(len(piece.split())+2<=12 for piece in pieces)
def test_oversized_single_token_is_not_silently_truncated():
    with pytest.raises(ValueError):module.split_budget('unbreakable',len,budget=2)

def test_constrained_retry_does_not_change_default_decoding():
    import torch
    from lib.mt import Translator
    calls=[]
    class Tokenizer:
        def __call__(self,batch,**kwargs):return {'input_ids':torch.zeros((1,4),dtype=torch.long)}
        def batch_decode(self,output,**kwargs):return ['candidate']
    class Model:
        def generate(self,**kwargs):calls.append(kwargs);return torch.zeros((1,1),dtype=torch.long)
    tr=Translator.__new__(Translator);tr.tok=Tokenizer();tr.model=Model()
    tr._gen(['source'],2,2)
    tr._gen(['source'],2,2,prevent_repetition=True)
    assert calls[0]['no_repeat_ngram_size']==0
    assert calls[1]['no_repeat_ngram_size']==4
