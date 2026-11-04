#!/usr/bin/env python3
"""
Stage 02b - Parse NAMASTE (Ministry of Ayush) morbidity codes + Standardised Ayurveda Terminologies.

Data-quality issues found in the official files and how they are handled
  1. Diacritic / Devanagari columns of the morbidity file are empty (14%) or shifted to a
     neighbouring row (~1%).  -> canonical IAST is DERIVED from the always-present phonetic column
     (converter verified at 97% exact / ~100% modulo source typos on aligned rows); the official
     Devanagari is kept when it agrees with the derived form, otherwise the derived one is used and
     the row is flagged.
  2. SAT definitions lost their diacritics in the portal's database ('k?yacikitsa', '?yurveda').
     -> each corrupted token is repaired against a vocabulary of ~25k clean IAST words (WHO
     terminology + morbidity + SAT headwords); unresolved tokens are flagged.
  3. Mojibake (UTF-8 read as cp1252), stray HTML tags, NBSP -> fix_text().
Outputs: data/interim/namaste_morbidity.csv, data/interim/namaste_sat.csv, reports/namaste_parse_report.json
"""
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.indic import (fix_text, phonetic_to_iast, iso_to_iast, iast_to_deva, deva_to_iast,
                       ascii_fold, hindi_usage_form)
from lib.ngram_repair import CharNgram, evaluate

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data/raw/namaste", ROOT / "data/interim"
SAT_SECTIONS = {
    "A": "Basic and fundamental terminologies (mūlabhūta-śabdaḥ)",
    "B": "Structure and function (śārīraḥ)",
    "C": "Diagnosis and disorders - general, aetiology (vyādhi viniścaya / nidāna)",
    "D": "Signs and symptoms (liṅgam)",
    "F": "Pharmacognosy and pharmacology (dravyam / dravyaguṇa)",
    "G": "Preparation of medicine (auṣadhakalpanā, rasaśāstra)",
    "H": "Preparation of food (āhārakalpanā)",
    "I": "Treatment (cikitsā)",
    "J": "Preventive and promotive health (svasthavṛtta)",
}

def strip_paren(s):
    return re.sub(r"\s*\(.*?\)\s*$", "", s).strip()

def split_alts(s):
    return [a.strip() for a in re.split(r"\s*[/,]\s*", s) if a.strip()]

def deva_agrees(official, derived):
    if not official:
        return False
    return fuzz.ratio(ascii_fold(deva_to_iast(official)), ascii_fold(deva_to_iast(derived))) >= 85

# ----------------------------------------------------------------------------- morbidity codes
def parse_morbidity():
    m = pd.read_excel(RAW / "NATIONAL_AYURVEDA_MORBIDITY_CODES.xls", engine="xlrd", dtype=str).fillna("")
    m = m.rename(columns={"NAMC_ID": "namc_id", "NAMC_CODE": "namc_code", "NAMC_term": "term_phonetic",
                          "NAMC_term_diacritical": "term_iast_official_raw", "NAMC_term_DEVANAGARI": "term_deva_official_raw",
                          "Short_definition": "short_definition", "Long_definition": "long_definition",
                          "Ontology_branches": "ontology_branches", "Name English": "name_en",
                          "Name English Under Index": "name_en_alt", "Primary Index Related": "primary_index"})
    for c in m.columns:
        m[c] = m[c].map(fix_text)
    m = m.drop(columns=["Sr No."])
    # phonetic term may carry a qualifier in brackets e.g. "atipralApaH (kEvalavAta)"
    m["qualifier_phonetic"] = m.term_phonetic.str.extract(r"\(([^)]*)\)\s*$")[0].fillna("")
    base = m.term_phonetic.map(strip_paren)
    m["term_iast"] = base.map(phonetic_to_iast)
    m["qualifier_iast"] = m.qualifier_phonetic.map(phonetic_to_iast)
    m["term_deva"] = m.term_iast.map(iast_to_deva)
    off = m.term_deva_official_raw.map(lambda s: strip_paren(re.split(r"\s{2,}", s)[0]))
    agree = [deva_agrees(o, d) for o, d in zip(off, m.term_deva)]
    m["deva_source"] = ["official" if a else "derived_from_phonetic" for a in agree]
    m.loc[agree, "term_deva"] = off[agree]
    m["term_iast_official"] = m.term_iast_official_raw.map(iso_to_iast)
    m["term_hi"] = m.term_deva.map(hindi_usage_form)
    m["term_ascii"] = m.term_iast.map(ascii_fold)
    # WHO ICD-11 TM2 linkage is marked in the English name: "Accumulation of Vata pattern (TM2)"
    m["icd11_tm2_linked"] = m.name_en.str.contains(r"\(TM2\)") | m.name_en_alt.str.contains(r"\(TM2\)")
    for c in ["name_en", "name_en_alt"]:
        m[c] = m[c].str.replace(r"\s*\(TM2\)", "", regex=True).str.strip()
    m["code_root"] = m.namc_code.str.extract(r"^([A-Z]+)")[0].fillna("")
    m["source_id"] = "S1"
    rep = dict(n=len(m), official_iast_empty=round(float((m.term_iast_official == "").mean()), 4),
               deva_official_used=round(float((m.deva_source == "official").mean()), 4),
               tm2_linked=int(m.icd11_tm2_linked.sum()),
               with_long_definition=int((m.long_definition != "").sum()))
    return m, rep

# ----------------------------------------------------------------------------- SAT tables
def parse_sat():
    frames = []
    for sec in SAT_SECTIONS:
        d = pd.read_excel(RAW / f"SAT_{sec}.xls", engine="xlrd", dtype=str).fillna("")
        d.columns = ["sr", "t_id", "code", "parent_id", "word_phonetic", "short_definition_raw", "long_definition_raw", "reference"]
        d["section"] = sec
        frames.append(d)
    s = pd.concat(frames, ignore_index=True)
    for c in s.columns:
        s[c] = s[c].map(fix_text)
    s["code"] = s.code.str.replace(r"^[^S]+", "", regex=True)       # stray bytes before 'SAT-H.10'
    s["sat_id"] = s.code
    s["term_iast"] = s.word_phonetic.map(phonetic_to_iast)
    s["term_deva"] = s.term_iast.map(iast_to_deva)
    s["term_hi"] = s.term_deva.map(hindi_usage_form)
    s["term_ascii"] = s.term_iast.map(ascii_fold)
    s["section_title"] = s.section.map(SAT_SECTIONS)
    s["source_id"] = "S2"
    return s.drop(columns=["sr"])

# ----------------------------------------------------------------------------- diacritic repair
TOKEN = re.compile(r"[A-Za-zĀ-žḀ-ỿ̀-ͯ?]*\?[A-Za-zĀ-žḀ-ỿ̀-ͯ?]*")

_ISO_DECOMP = [("ṝ", "r̥̄"), ("ṛ", "r̥"), ("ḷ", "l̥")]

def _variants(w):
    """surface variants of a clean IAST word that the corrupted SAT text may contain."""
    out = {w}
    for suf in ("ḥ", "m", "ṃ"):                      # case endings: vipākaḥ -> vipāka, dravyam -> dravya
        if w.endswith(suf) and len(w) > 3:
            out.add(w[: -len(suf)])
    if w.endswith("ā") or w.endswith("ī"):
        out.add(w[:-1] + "a")                          # 'kāyacikitsa' style shortening in the source
    for v in list(out):                                # ISO-15919 decomposed forms (r + ring below)
        x = v
        for a, b in _ISO_DECOMP:
            x = x.replace(a, b)
        out.add(x)
    return out

def build_vocab(*series):
    v = Counter()
    for ser in series:
        for txt in ser:
            for w in re.findall(r"[A-Za-zĀ-žḀ-ỿ̀-ͯ]+", txt or ""):   # hyphens split compounds
                if any(ord(ch) > 127 for ch in w):          # only words that carry diacritics
                    for x in _variants(w.lower()):
                        v[x] += 1
    by_len = defaultdict(list)
    for w, c in v.items():
        by_len[len(w)].append((w, c))
    return v, by_len

def repair_token(tok, by_len, cache):
    if tok in cache:
        return cache[tok]
    low = tok.lower()
    pat = re.compile("^" + re.escape(low).replace(r"\?", ".") + "$")
    cands = [(w, c) for w, c in by_len.get(len(low), []) if pat.match(w)]
    res = None
    if cands:
        res = iso_to_iast(max(cands, key=lambda wc: wc[1])[0])   # back to canonical NFC IAST
        if tok[:1].isupper():
            res = res[:1].upper() + res[1:]
    cache[tok] = res
    return res

NGRAM_MIN_MARGIN = 2.0   # held-out precision 0.94 at this margin (see reports/namaste_parse_report.json)

def repair_text(txt, by_len, cache, stats, lm=None):
    def sub(mt):
        tok = mt.group(0)
        if tok.strip("?") == "":
            return tok
        stats["tokens"] += 1
        r = repair_token(tok, by_len, cache)                  # stage 1+2: exact vocabulary pattern
        if r:
            stats["repaired_vocab"] += 1
            return r
        if lm is not None:                                     # stage 3: char 4-gram LM restoration
            best, margin = lm.restore(tok.lower())
            if margin >= NGRAM_MIN_MARGIN:
                stats["repaired_ngram"] += 1
                return best if not tok[:1].isupper() else best[:1].upper() + best[1:]
        stats["unresolved"] += 1
        return tok
    return TOKEN.sub(sub, txt or "")

def main():
    morb, mrep = parse_morbidity()
    sat = parse_sat()
    who = pd.read_csv(OUT / "who_terms.csv", keep_default_na=False)
    vocab, by_len = build_vocab(who.iast, who.description, who.english_term, morb.term_iast,
                                morb.long_definition, morb.short_definition, sat.term_iast)
    # character LM over clean IAST words, evaluated on held-out words before use
    clean_words = [w for w in vocab if not any(ch in w for ch in "̥̄") and re.fullmatch(r"[a-zāīūṛṝḷṅñṭḍṇśṣṃḥ]+", w)]
    lm_eval = evaluate(clean_words)
    lm = CharNgram().fit(clean_words)
    cache, stats = {}, Counter()
    for c in ["short_definition", "long_definition"]:
        sat[c] = [repair_text(t, by_len, cache, stats, lm) for t in sat[c + "_raw"]]
    sat["definition_has_unresolved_diacritics"] = sat.short_definition.str.contains(r"\w\?|\?\w") | \
        sat.long_definition.str.contains(r"\w\?|\?\w")
    srep = dict(n=len(sat), per_section=sat.section.value_counts().sort_index().to_dict(),
                corrupted_tokens=stats["tokens"], repaired_by_vocabulary=stats["repaired_vocab"],
                repaired_by_char_ngram=stats["repaired_ngram"], unresolved=stats["unresolved"],
                repair_rate=round((stats["repaired_vocab"] + stats["repaired_ngram"]) / max(1, stats["tokens"]), 4),
                rows_still_flagged=int(sat.definition_has_unresolved_diacritics.sum()),
                vocab_size=len(vocab), char_ngram_heldout_evaluation=lm_eval,
                char_ngram_min_margin=NGRAM_MIN_MARGIN)
    morb.to_csv(OUT / "namaste_morbidity.csv", index=False)
    sat.to_csv(OUT / "namaste_sat.csv", index=False)
    rep = {"morbidity": mrep, "sat": srep}
    (ROOT / "reports/namaste_parse_report.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print(json.dumps(rep, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
