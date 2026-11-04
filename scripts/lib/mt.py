"""
English -> Hindi machine translation for the bilingual layer (NLLB-200 distilled 600M, safetensors).

Pre-processing  (domain adaptation without fine-tuning)
  * curated Ayurveda glossary (curation/glossary_en_hi.csv) injected as Hindi terms, longest match first
  * Sanskrit words written in IAST (contain diacritics) -> Devanagari, so the model copies them
Post-processing / quality estimation (QE)
  * devanagari_ratio, length ratio, degenerate repetition, retention of injected/protected terms
  * optional back-translation chrF on a sample (computed in the calling stage)
"""
import re, unicodedata
import pandas as pd
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from .indic import iast_to_deva, iso_to_iast

DIACRITIC = re.compile(r"[āīūṛṝḷṅñṭḍṇśṣṃḥṁōēĀĪŪṚṢŚṆṬḌŌĒ]|r̥|l̥")

class Glossary:
    def __init__(self, path):
        g = pd.read_csv(path, keep_default_na=False)
        g = g[g.en.str.strip() != ""]
        self.pairs = sorted(zip(g.en.str.lower(), g.hi), key=lambda p: -len(p[0]))
        self.re = re.compile(r"\b(" + "|".join(re.escape(e) for e, _ in self.pairs) + r")\b", re.I)
        self.map = dict(self.pairs)

    def inject(self, text):
        used = []
        def sub(m):
            hi = self.map[m.group(0).lower()]
            used.append(hi.split(" (")[0])
            return hi
        return self.re.sub(sub, text), used

def protect_sanskrit(text):
    """IAST tokens -> Devanagari; returns new text and list of protected Devanagari tokens."""
    prot = []
    def sub(m):
        w = m.group(0)
        if DIACRITIC.search(w):
            d = iast_to_deva(iso_to_iast(w).lower())      # NAMASTE uses ISO-15919 (ō, ē, r̥)
            prot.append(d)
            return d
        return w
    return re.sub(r"[A-Za-zĀ-žḀ-ỿ̀-ͯ\-]+", sub, text), prot

def devanagari_ratio(s):
    letters = [c for c in s if c.isalpha() or unicodedata.category(c).startswith("M")]
    if not letters:
        return 0.0
    return sum("ऀ" <= c <= "ॿ" for c in letters) / len(letters)

def degenerate(s):
    toks = s.split()
    if len(toks) >= 6:
        for n in (1, 2, 3):
            grams = [" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)]
            for g in set(grams):
                if grams.count(g) >= 4 and len(g) > 1:
                    return True
    return False

class Translator:
    def __init__(self, model_dir, glossary_path, quantize=True, threads=4):
        torch.set_num_threads(threads)
        self.tok = AutoTokenizer.from_pretrained(model_dir, src_lang="eng_Latn")
        m = AutoModelForSeq2SeqLM.from_pretrained(model_dir, use_safetensors=True).eval()
        if quantize:
            m = torch.ao.quantization.quantize_dynamic(m, {torch.nn.Linear}, dtype=torch.qint8)
        self.model = m
        self.glossary = Glossary(glossary_path)
        self.hin = self.tok.convert_tokens_to_ids("hin_Deva")
        self.eng = self.tok.convert_tokens_to_ids("eng_Latn")

    def prepare(self, text):
        t, used = self.glossary.inject(text)
        t, prot = protect_sanskrit(t)
        return t, used + prot

    @torch.no_grad()
    def _gen(self, batch, tgt, beams, src_lang="eng_Latn"):
        self.tok.src_lang = src_lang
        enc = self.tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=256)
        out = self.model.generate(**enc, forced_bos_token_id=tgt, num_beams=beams,
                                  max_new_tokens=min(400, int(enc["input_ids"].shape[1] * 2.2) + 10))
        return self.tok.batch_decode(out, skip_special_tokens=True)

    def translate(self, texts, beams=2, batch_size=16):
        prepared = [self.prepare(t) for t in texts]
        res = [None] * len(texts)
        # inputs fully covered by the glossary / Sanskrit protection are already Hindi: do NOT send them
        # to the model (it would 'translate' Hindi as if it were English and hallucinate)
        todo = []
        for i, (p, keep) in enumerate(prepared):
            if devanagari_ratio(p) >= 0.85:
                res[i] = dict(hi=p, prepared=p, term_retention=1.0, length_ratio=round(len(p) / max(1, len(texts[i])), 3),
                              devanagari_ratio=round(devanagari_ratio(p), 3), qe_flags="", method="glossary_exact")
            else:
                todo.append(i)
        order = sorted(todo, key=lambda i: len(prepared[i][0]))
        for s in range(0, len(order), batch_size):
            idx = order[s:s + batch_size]
            b = beams if len(prepared[idx[-1]][0]) >= 40 else 1      # greedy for short phrases
            outs = self._gen([prepared[i][0] for i in idx], self.hin, b)
            for i, o in zip(idx, outs):
                src, keep = texts[i], prepared[i][1]
                retained = (sum(k in o for k in keep) / len(keep)) if keep else 1.0
                lr = len(o) / max(1, len(src))
                flags = []
                if devanagari_ratio(o) < 0.5:
                    flags.append("low_devanagari")
                if degenerate(o):
                    flags.append("repetition")
                if len(src) > 25 and not (0.45 <= lr <= 2.6):
                    flags.append("length_ratio")
                # short strings (names, glosses): every injected/protected term must survive;
                # long definitions: at least 75 %
                if (len(src) < 80 and retained < 1.0) or retained < 0.75:
                    flags.append("terms_lost")
                res[i] = dict(hi=o, prepared=prepared[i][0], term_retention=round(retained, 3),
                              length_ratio=round(lr, 3), devanagari_ratio=round(devanagari_ratio(o), 3),
                              qe_flags=";".join(flags), method="nllb200_600m_glossary_injected")
        return res

    def back_translate(self, hi_texts, batch_size=16):
        out = []
        for s in range(0, len(hi_texts), batch_size):
            out += self._gen(hi_texts[s:s + batch_size], self.eng, 2, src_lang="hin_Deva")
        return out
