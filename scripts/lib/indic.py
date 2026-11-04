"""
Indic text utilities used across the pipeline.

* fix_text            - repair mojibake / broken encodings, NFC normalise, clean whitespace
* phonetic_to_iast    - NAMASTE 'phonetic' ASCII scheme (vAtavyAdhiH, doShaH, a~ggam) -> IAST
* iso_to_iast         - ISO-15919 style diacritics used by NAMASTE (ō ē r̥ ṁ) -> IAST (o e ṛ ṃ)
* iast_to_deva        - IAST -> Devanagari (deterministic)
* deva_to_iast        - Devanagari -> IAST
* hindi_usage_form    - Sanskrit citation form -> form used in Hindi text (drop visarga / -m ending)
* ascii_fold          - IAST -> plain ASCII search key (vatavyadhi)
"""
import re
import unicodedata
import ftfy
from indic_transliteration import sanscript

# ----------------------------------------------------------------------------- generic cleaning
_WS = re.compile(r"[\s  -​ ]+")

def fix_text(s):
    if s is None:
        return ""
    s = str(s)
    if s.lower() in ("nan", "none", "-", "--"):
        return ""
    s = ftfy.fix_text(s, normalization="NFC")
    s = s.replace("�", " ")
    s = re.sub(r"</?em>|</em<|<[^>]{1,20}>", "", s)      # stray html emphasis tags in NAMASTE text
    s = _WS.sub(" ", s).strip()
    return unicodedata.normalize("NFC", s)

# ----------------------------------------------------------------------------- NAMASTE phonetic
# longest match first. Scheme learnt from (and verified against) the 2,910 morbidity codes, which
# carry phonetic + diacritic + Devanagari spellings of every term.
_PHON = [
    ("RRu", "ṝ"), ("RU", "ṝ"), ("Ru", "ṛ"), ("Lu", "ḷ"),
    ("~gh", "ṅh"), ("~g", "ṅ"), ("~j", "ñ"), ("~n", "ñ"), ("~M", "m̐"),
    ("Sh", "ṣ"), ("Th", "ṭh"), ("Dh", "ḍh"),
    ("ai", "ai"), ("au", "au"),
    ("A", "ā"), ("I", "ī"), ("U", "ū"), ("E", "e"), ("O", "o"),
    ("K", "kh"), ("G", "gh"), ("C", "ch"), ("J", "jh"), ("P", "ph"), ("B", "bh"),
    ("T", "ṭ"), ("D", "ḍ"), ("N", "ṇ"), ("S", "ś"), ("M", "ṃ"), ("H", "ḥ"),
    ("^", ""), ("&", "'"),          # '&' = avagraha (ऽ) in the NAMASTE scheme: ajIrNe&nne -> ajīrṇe'nne -> अजीर्णेऽन्ने
]
_PHON_RE = re.compile("|".join(re.escape(k) for k, _ in sorted(_PHON, key=lambda kv: -len(kv[0]))))
_PHON_MAP = dict(_PHON)

def phonetic_to_iast(s):
    s = fix_text(s)
    return _PHON_RE.sub(lambda m: _PHON_MAP[m.group(0)], s)

# ----------------------------------------------------------------------------- ISO 15919 -> IAST
_ISO = [("r̥̄", "ṝ"), ("l̥̄", "ḹ"), ("r̥", "ṛ"), ("l̥", "ḷ"), ("ō", "o"), ("ē", "e"), ("ṁ", "ṃ"),
        ("Ō", "O"), ("Ē", "E"), ("R̥", "Ṛ")]

def iso_to_iast(s):
    s = unicodedata.normalize("NFC", fix_text(s))
    for a, b in _ISO:
        s = s.replace(unicodedata.normalize("NFC", a), b)
    return unicodedata.normalize("NFC", s)

# ----------------------------------------------------------------------------- IAST <-> Devanagari
def iast_to_deva(s):
    s = unicodedata.normalize("NFC", s or "").lower().replace("m̐", "ṁ")
    out = sanscript.transliterate(s, sanscript.IAST, sanscript.DEVANAGARI)
    return unicodedata.normalize("NFC", out)

def deva_to_iast(s):
    return unicodedata.normalize("NFC", sanscript.transliterate(s or "", sanscript.DEVANAGARI, sanscript.IAST))

def ascii_fold(s):
    """IAST/any latin with diacritics -> lowercase ascii key."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("ṃ", "m").replace("ḥ", "h")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# ----------------------------------------------------------------------------- Hindi usage
_VIRAMA = "्"

def hindi_usage_form(deva):
    """Sanskrit nominative citation form -> stem as used in Hindi technical prose.
    व्याधिः->व्याधि, विकारः->विकार, चूर्णम्->चूर्ण, दोषवैषम्यम्->दोषवैषम्य, अष्टाङ्ग->अष्टांग (anusvara usage)."""
    out = []
    for tok in re.split(r"(\s+|[,/;()\[\]-])", deva or ""):
        t = tok
        if t.endswith("ः"):
            t = t[:-1]
        elif t.endswith("म्") and len(t) > 2:
            t = t[:-2]
        # Hindi orthography prefers anusvara before a homorganic stop (अङ्ग -> अंग, सञ्चय -> संचय)
        t = re.sub(r"[ङञणनम]" + _VIRAMA + r"(?=[कखगघचछजझटठडढतथदधपफबभ])", "ं", t)
        out.append(t)
    return unicodedata.normalize("NFC", "".join(out))

def has_devanagari(s):
    return bool(re.search(r"[ऀ-ॿ]", s or ""))
