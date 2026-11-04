"""
Matching keys for joining Sanskrit terms written in different romanisations.

Sources spell the same word very differently: 'kuṣṭham' (IAST, NAMASTE), 'Kushta' (Amidha ASCII),
'kuShTham' (NAMASTE phonetic).  `skeleton()` maps all of them to one comparable key by
folding diacritics, ASCII digraphs (sh, ch, w, ee, oo), aspiration, gemination and case endings.
"""
import re
from .indic import ascii_fold, iso_to_iast

def skeleton(s: str) -> str:
    s = iso_to_iast(s or "").lower()
    s = s.replace("ṛ", "ri").replace("ṝ", "ri").replace("ḷ", "li")
    s = ascii_fold(s)
    s = re.sub(r"[^a-z]", "", s)
    s = s.replace("sh", "s").replace("ch", "c").replace("w", "v").replace("ee", "i").replace("oo", "u")
    s = re.sub(r"(?<=[kgcjtdpb])h", "", s)          # drop aspiration: kh->k, dh->d ...
    s = re.sub(r"(.)\1+", r"\1", s)                  # gemination / long vowels written double
    s = re.sub(r"(?<=[aiu])[hm]$", "", s)            # case endings -ḥ / -m
    s = re.sub(r"ri(?=[^aeiou]|$)", "r", s)           # 'kri' vs 'kr' (ṛ) spelling variants
    return s

def skeleton_variants(s: str):
    """skeleton of the whole term plus each '/'- or ','-separated alternative."""
    out = {skeleton(s)}
    for part in re.split(r"[/,;]", s or ""):
        if part.strip():
            out.add(skeleton(part))
    out.discard("")
    return out
