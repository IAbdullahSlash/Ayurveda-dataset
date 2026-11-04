"""
Infer IAST spelling of Sanskrit names written in loose ASCII ('Lata Kasturi', 'Shatavari', 'Gunja').

Each ASCII grapheme expands to its plausible IAST readings (a -> a/ā, sh -> ś/ṣ, t -> t/ṭ, n -> n/ṇ/ṅ/ñ/ṃ,
ri -> ṛ/ri, ...); a character 4-gram model of real Sanskrit words (lib.ngram_repair.CharNgram, trained on
WHO + NAMASTE vocabulary) picks the most probable reading by beam search.  Accuracy is measured on
herbs whose ASCII name (Amidha) and official IAST name (SAT) are both known.
"""
import re
from .ngram_repair import CharNgram

GRAPHEMES = [
    ("ksh", ["kṣ"]), ("chh", ["ch"]), ("shh", ["ṣ"]),
    ("aa", ["ā"]), ("ee", ["ī"]), ("oo", ["ū"]), ("ai", ["ai"]), ("au", ["au"]),
    ("sh", ["ś", "ṣ"]), ("ch", ["c", "ch"]), ("kh", ["kh"]), ("gh", ["gh"]), ("jh", ["jh"]),
    ("th", ["th", "ṭh"]), ("dh", ["dh", "ḍh"]), ("ph", ["ph"]), ("bh", ["bh"]), ("ri", ["ṛ", "ri"]),
    ("gy", ["jñ", "gy"]), ("jn", ["jñ"]), ("x", ["kṣ"]), ("w", ["v"]),
    ("a", ["a", "ā"]), ("i", ["i", "ī"]), ("u", ["u", "ū"]), ("e", ["e"]), ("o", ["o"]),
    ("t", ["t", "ṭ"]), ("d", ["d", "ḍ"]), ("n", ["n", "ṇ", "ṅ", "ñ", "ṃ"]), ("m", ["m", "ṃ"]),
    ("s", ["s", "ś"]), ("h", ["h", "ḥ"]),
]
_G = sorted(GRAPHEMES, key=lambda g: -len(g[0]))

def graphemes(word):
    out, i = [], 0
    while i < len(word):
        for g, opts in _G:
            if word.startswith(g, i):
                out.append(opts); i += len(g); break
        else:
            out.append([word[i]]); i += 1
    return out

def infer_iast(name, lm: CharNgram, beam=128):
    """'Lata Kasturi' -> 'latākastūrī' (words joined: Sanskrit names are compounds)."""
    w = re.sub(r"[^a-z]", "", (name or "").lower())
    if not w:
        return "", 0.0
    pad = "^" * (lm.n - 1)
    beams = [("", 0.0)]
    for opts in graphemes(w) + [["$"]]:
        nxt = []
        for pre, sc in beams:
            for o in opts:
                s, hist = sc, (pad + pre)[-(lm.n - 1):]
                for ch in o:                       # multi-char options are scored char by char
                    s += lm.logp(hist, ch)
                    hist = (hist + ch)[-(lm.n - 1):]
                nxt.append((pre + (o if o != "$" else ""), s))
        nxt.sort(key=lambda x: -x[1])
        beams = nxt[:beam]
    margin = beams[0][1] - beams[1][1] if len(beams) > 1 else 99.0
    return beams[0][0], margin
