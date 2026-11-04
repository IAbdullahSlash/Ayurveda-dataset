#!/usr/bin/env python3
"""
Stage 06 - Bilingual layer: English -> Hindi for every free-text English field.

  --translate   translate all unique English strings (resumable cache: data/interim/cache/mt_en_hi.jsonl)
  --qe          back-translation quality estimate (hi -> en, chrF vs. source) on a random sample
  --merge       add <field>_hi + <field>_hi_qe columns to the processed tables

Hindi for NAMES does not come from MT: Sanskrit terms already have a Devanagari / Hindi-usage form
(stage 02/04), plant common names come from Wikidata.  MT is used for English descriptions/glosses
and is always labelled (method + QE flags) so it can be filtered or reviewed.
"""
import argparse, json, random, sys, time
from collections import Counter
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[1]
OUT, CACHE = ROOT / "data/processed", ROOT / "data/interim/cache/mt_en_hi.jsonl"
MODEL, GLOSS = ROOT / "models/nllb-200-distilled-600M", ROOT / "curation/glossary_en_hi.csv"

# (table, english column, hindi column) - ordered by priority (short, user-facing first)
FIELDS = [
    ("diseases", "name_en", "name_en_hi"), ("terminology", "term_en", "term_en_hi"),
    ("herbs", "name_en", "name_en_hi"), ("herb_groups", "action_en", "action_hi"),
    ("diagnostic_methods", "what_is_assessed_en", "what_is_assessed_hi"),
    ("formulations", "indications_en", "indications_hi"), ("formulations", "safety_note", "safety_note_hi"),
    ("symptoms", "gloss_en", "gloss_hi"), ("herbs", "description_en", "description_hi"),
    ("terminology", "definition_en", "definition_hi"),
]
# Disorder definitions are NOT machine-translated as whole paragraphs: 1,595 of 1,604 are symptom lists
# ("characterized by X [gloss], Y [gloss] ..."), and every symptom already has a Hindi gloss.  The Hindi
# definition is COMPOSED from Devanagari symptom terms + their Hindi glosses; only the explanatory
# sentence ("This may be explained by ...") and the few unparsed definitions go through MT.
DERIVED = [("therapies", "terminology"), ("pharmaceutics", "terminology"), ("diet_lifestyle", "terminology")]
EXPL = r"(This may be explained by.*)$"

def disease_mt_strings():
    import re
    d = pd.read_csv(OUT / "diseases.csv", keep_default_na=False, usecols=["disease_id", "definition_en"])
    ds = pd.read_csv(OUT / "disease_symptom.csv", keep_default_na=False, usecols=["disease_id"])
    with_sym = set(ds.disease_id)
    out = []
    for did, t in zip(d.disease_id, d.definition_en):
        if not t:
            continue
        if did not in with_sym:
            out.append(t)
        else:
            m = re.search(EXPL, t, flags=re.I)
            if m:
                out.append(m.group(1).strip())
    return out

def load_cache():
    """main cache + any parallel-worker cache files (mt_en_hi*.jsonl)"""
    c = {}
    for f in sorted(CACHE.parent.glob("mt_en_hi*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:      # a worker killed mid-line
                    continue
                c[r["en"]] = r
    return c

def strings():
    seen, out = set(), []
    def add(s):
        s = str(s).strip()
        if s and s not in seen and len(s) < 1500:
            seen.add(s); out.append(s)
    for t, c, _ in FIELDS:
        if (t, c) == ("terminology", "definition_en"):
            for s in disease_mt_strings():          # short disorder pieces before the long term definitions
                add(s)
        df = pd.read_csv(OUT / f"{t}.csv", keep_default_na=False, usecols=[c])
        for s in df[c]:
            add(s)
    return out

def do_translate(threads, beams=2, worker="", reverse=False):
    from lib.mt import Translator
    cache = load_cache()
    todo = [s for s in strings() if s not in cache]
    if reverse:                       # a second worker starts from the other end of the queue
        todo = todo[::-1]
    print(f"unique strings: {len(cache) + len(todo)}, cached {len(cache)}, to translate {len(todo)} (beams={beams})", flush=True)
    if not todo:
        return
    tr = Translator(MODEL, GLOSS, quantize=True, threads=threads)
    t0 = time.time()
    out_file = CACHE.parent / f"mt_en_hi_{worker}.jsonl" if worker else CACHE
    step = 32 if worker else 128
    with open(out_file, "a", encoding="utf-8") as fh:
        for s in range(0, len(todo), step):
            chunk = todo[s:s + step]
            if worker:                   # stop when the other worker has already done these
                done_now = load_cache()
                chunk = [x for x in chunk if x not in done_now]
                if not chunk:
                    print("  reached strings already translated by the other worker - stopping", flush=True)
                    break
            for en, r in zip(chunk, tr.translate(chunk, beams=beams, batch_size=16)):
                if beams == 1:
                    r["method"] = r["method"].replace("glossary_injected", "glossary_injected_greedy")
                fh.write(json.dumps({"en": en, **r}, ensure_ascii=False) + "\n")
            fh.flush()
            done = s + len(chunk)
            rate = done / (time.time() - t0)
            print(f"  {done}/{len(todo)}  {rate:.2f} str/s  eta {(len(todo) - done) / rate / 60:.1f} min", flush=True)

def chrf(hyp, ref, n=6, beta=2.0):
    import math
    hyp, ref = hyp.replace(" ", ""), ref.replace(" ", "")
    ps, rs = [], []
    for k in range(1, n + 1):
        h = Counter(hyp[i:i + k] for i in range(len(hyp) - k + 1))
        r = Counter(ref[i:i + k] for i in range(len(ref) - k + 1))
        if not h or not r:
            continue
        ov = sum((h & r).values())
        ps.append(ov / sum(h.values())); rs.append(ov / sum(r.values()))
    if not ps:
        return 0.0
    p, r = sum(ps) / len(ps), sum(rs) / len(rs)
    return 0.0 if p + r == 0 else (1 + beta ** 2) * p * r / (beta ** 2 * p + r) * 100

def do_qe(n, threads):
    from lib.mt import Translator
    cache = load_cache()
    rows = [r for r in cache.values() if r.get("method", "").startswith("nllb") and len(r["en"]) >= 20]
    random.Random(7).shuffle(rows)
    rows = rows[:n]
    tr = Translator(MODEL, GLOSS, quantize=True, threads=threads)
    bt = tr.back_translate([r["hi"] for r in rows])
    scores = [chrf(b.lower(), r["en"].lower()) for b, r in zip(bt, rows)]
    flagged = [s for s, r in zip(scores, rows) if r["qe_flags"]]
    clean = [s for s, r in zip(scores, rows) if not r["qe_flags"]]
    rep = dict(sample=len(rows), mean_backtranslation_chrF=round(sum(scores) / len(scores), 2),
               mean_chrF_unflagged=round(sum(clean) / max(1, len(clean)), 2),
               mean_chrF_flagged=round(sum(flagged) / max(1, len(flagged)), 2),
               share_chrF_ge_50=round(sum(s >= 50 for s in scores) / len(scores), 4),
               examples=[dict(en=r["en"][:160], hi=r["hi"][:160], back=b[:160], chrF=round(s, 1))
                         for r, b, s in list(zip(rows, bt, scores))[:12]])
    (ROOT / "reports/translation_qe.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in rep.items() if k != "examples"}, indent=2))

def write(df, name):
    df.to_csv(OUT / f"{name}.csv", index=False)
    d2 = df.copy()
    for c in d2.columns:
        if d2[c].dtype == object:
            d2[c] = d2[c].astype(str)
    d2.to_parquet(OUT / f"{name}.parquet", index=False)

def do_merge():
    cache = load_cache()
    stats = {}
    tables = {}
    for t, c, hc in FIELDS:
        df = tables.get(t) if t in tables else pd.read_csv(OUT / f"{t}.csv", keep_default_na=False, low_memory=False)
        hi = df[c].map(lambda s: cache.get(str(s).strip(), {}).get("hi", "") if str(s).strip() else "")
        qe = df[c].map(lambda s: cache.get(str(s).strip(), {}).get("qe_flags", "") if str(s).strip() else "")
        meth = df[c].map(lambda s: cache.get(str(s).strip(), {}).get("method", "") if str(s).strip() else "")
        df[hc], df[hc + "_qe_flags"], df[hc + "_method"] = hi, qe, meth
        tables[t] = df
        nonempty = df[c].astype(str).str.strip() != ""
        stats[f"{t}.{c}"] = dict(nonempty=int(nonempty.sum()), translated=int((hi != "").sum()),
                                 qe_flagged=int(((qe != "") & (hi != "")).sum()))
    # ---- disorder definitions: composed from symptom-level Hindi + translated explanation sentence
    import re
    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.indic import iast_to_deva, iso_to_iast
    d = pd.read_csv(OUT / "diseases.csv", keep_default_na=False, low_memory=False)
    ds = pd.read_csv(OUT / "disease_symptom.csv", keep_default_na=False).sort_values(["disease_id", "mention_rank"])
    sym_hi = tables["symptoms"].set_index("symptom_id").gloss_hi.to_dict()
    sym_qe = tables["symptoms"].set_index("symptom_id").gloss_hi_qe_flags.to_dict()
    def hi_of(en, sid):
        c = cache.get(str(en).strip(), {})
        return (c.get("hi", ""), c.get("qe_flags", "")) if c.get("hi") else (sym_hi.get(sid, ""), sym_qe.get(sid, ""))
    parts, flags = {}, {}
    for did, g in ds.groupby("disease_id", sort=False):
        items, fl = [], set()
        for sa, en, sid in zip(g.mention_sa_iast, g.mention_en, g.symptom_id):
            h, q = hi_of(en, sid)
            dev = iast_to_deva(iso_to_iast(sa).lower()) if sa else ""
            if q:
                fl.add("component_" + q.split(";")[0])
            items.append(f"{dev} ({h})" if dev and h else (dev or h))
        parts[did] = [x for x in items if x]
        flags[did] = fl
    hi_def, hi_flag, hi_meth = [], [], []
    for did, t in zip(d.disease_id, d.definition_en):
        if not t:
            hi_def.append(""); hi_flag.append(""); hi_meth.append(""); continue
        if did in parts and parts[did]:
            txt = "लक्षण: " + "; ".join(parts[did]) + "।"
            m = re.search(EXPL, t, flags=re.I)
            fl = set(flags[did])
            if m:
                c = cache.get(m.group(1).strip(), {})
                if c.get("hi"):
                    txt += " " + c["hi"]
                    if c.get("qe_flags"):
                        fl.add("explanation_" + c["qe_flags"].split(";")[0])
                else:
                    fl.add("explanation_untranslated")
            hi_def.append(txt); hi_flag.append(";".join(sorted(fl))); hi_meth.append("composed: symptom-level Hindi glosses + NLLB explanation")
        else:
            c = cache.get(t.strip(), {})
            hi_def.append(c.get("hi", "")); hi_flag.append(c.get("qe_flags", "")); hi_meth.append(c.get("method", ""))
    d["definition_hi"], d["definition_hi_qe_flags"], d["definition_hi_method"] = hi_def, hi_flag, hi_meth
    for c in ["name_en_hi", "name_en_hi_qe_flags", "name_en_hi_method"]:
        d[c] = tables["diseases"][c].values
    tables["diseases"] = d
    nonempty = d.definition_en != ""
    stats["diseases.definition_en"] = dict(nonempty=int(nonempty.sum()), translated=int((d.definition_hi != "").sum()),
                                           qe_flagged=int(((d.definition_hi_qe_flags != "") & (d.definition_hi != "")).sum()),
                                           composed=int(pd.Series(hi_meth).str.startswith("composed").sum()))
    for t, df in tables.items():
        write(df, t)
    term = tables["terminology"].set_index("term_uid")
    for t, base in DERIVED:
        df = pd.read_csv(OUT / f"{t}.csv", keep_default_na=False, low_memory=False)
        for c in ["term_en_hi", "term_en_hi_qe_flags", "definition_hi", "definition_hi_qe_flags", "definition_hi_method"]:
            df[c] = df.term_uid.map(term[c]).fillna("")
        write(df, t)
    (ROOT / "reports/translation_coverage.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))

def do_purge(regex):
    """drop cached translations whose English text matches REGEX (after a glossary update), so that
    --translate re-translates exactly those strings."""
    import re
    pat = re.compile(regex, re.I)
    rows = [json.loads(l) for l in CACHE.read_text(encoding="utf-8").splitlines() if l.strip()]
    keep = [r for r in rows if not pat.search(r["en"])]
    CACHE.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
    print(f"purged {len(rows) - len(keep)} of {len(rows)} cached translations")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--translate", action="store_true"); ap.add_argument("--qe", type=int, default=0)
    ap.add_argument("--merge", action="store_true"); ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--purge-regex", default="", help="re-translate cached strings matching this regex")
    ap.add_argument("--beams", type=int, default=2, help="beam size (1 = greedy, ~2x faster)")
    ap.add_argument("--worker", default="", help="parallel worker name: writes data/interim/cache/mt_en_hi_<name>.jsonl")
    ap.add_argument("--reverse", action="store_true", help="process the queue from the end (second worker)")
    a = ap.parse_args()
    if a.purge_regex:
        do_purge(a.purge_regex)
    if a.translate:
        do_translate(a.threads, a.beams, a.worker, a.reverse)
    if a.qe:
        do_qe(a.qe, a.threads)
    if a.merge:
        do_merge()
