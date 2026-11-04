#!/usr/bin/env python3
"""
AyurKB expert-system demo (bilingual).  NOT medical advice - a demonstration of how the knowledge base
can drive a decision-support tool that a qualified Ayurveda practitioner reviews.

  python3 examples/expert_system_demo.py --symptoms "fever; burning sensation; excessive thirst"
  python3 examples/expert_system_demo.py --symptoms "बुखार; जलन; प्यास" --lang hi

Steps: (1) map free-text symptoms (English / Hindi / Sanskrit) to the KB symptom lexicon,
(2) rank NAMASTE disorders with the IDF-weighted knowledge-base matcher (same as experiment E3),
(3) for the top disorder show doṣa, ICD-11 TM2 code, indicated herbs (+ safety flags), classical
formulations and the classical śodhana principle for the dominant doṣa.
"""
import argparse, math, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz, process

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)

# Caraka Saṃhitā, Sūtrasthāna 25.40 (agrya-saṅgraha): basti is foremost for vāta, virecana for pitta, vamana for kapha
SHODHANA = {"vata": ("basti (medicated enema)", "बस्ति"), "pitta": ("virecana (therapeutic purgation)", "विरेचन"),
            "kapha": ("vamana (therapeutic emesis)", "वमन")}

def load():
    kb = {n: rd(n) for n in ["symptoms", "diseases", "disease_symptom", "herb_indication", "herbs",
                             "formulation_indications", "formulations"]}
    for n in ["herb_indication_evidence", "therapy_disease", "case_report_links",          # optional layers (stages 14-16)
              "disease_symptom_from_cases"]:                                                # case-learned profiles (stage 24)
        kb[n] = rd(n) if (P / f"{n}.csv").exists() else pd.DataFrame()
    return kb

TIER = {"clinical_evidence": "clinical studies", "literature_supported": "literature", "sparse": "sparse literature",
        "no_literature": "no literature found", "not_queryable": "not searchable"}

STOP = {"in", "of", "the", "a", "an", "with", "and", "due", "to", "at", "on", "or", "is", "में", "की", "के", "का", "और", "से", "एवं"}

def words(s):
    return {re.sub(r"(es|s)$", "", w) if len(w) > 4 else w for w in re.findall(r"[\wऀ-ॿ]+", s.lower()) if w not in STOP}

def semantic_symptoms(phrases, lang="en", k=15, margin=0.035, floor=0.85):
    """semantic matching against the precomputed e5 index (release/embeddings, stage 11).
    English queries use the English/IAST index, Hindi queries the Hindi index (monolingual matching is far
    more reliable than Hindi->English with a small model, see E5).  e5 similarities are compressed, so
    candidates are kept RELATIVE to the best hit (within `margin`) above an absolute `floor`."""
    import numpy as np
    name = "symptoms_hi" if lang == "hi" else "symptoms"
    emb, model = ROOT / "release/embeddings", None
    ft_model, ft_emb = ROOT / "models/multilingual-e5-small-ayurkb", ROOT / "release/embeddings_ft"
    # the domain fine-tuned model (stage 23) is used for Hindi queries, where it raised recall@10 from 0.86 to 0.97
    # (E5b); for English clinical phrases the base model matched as well (E6b), so it stays the default there
    if lang == "hi" and ft_model.exists() and (ft_emb / f"{name}.npy").exists():
        emb, model = ft_emb, ft_model
    if not (emb / f"{name}.npy").exists():
        return []
    sys.path.insert(0, str(ROOT / "scripts"))
    from importlib import import_module
    enc = import_module("10_crosslingual").E5(threads=2, model=model)
    X = np.load(emb / f"{name}.npy").astype("float32")
    ids = pd.read_csv(emb / f"{name}_ids.csv", keep_default_na=False)
    Q = enc.encode(phrases, "query: ")
    out = []
    for ph, q in zip(phrases, Q):
        sims = X @ q
        order = np.argsort(-sims)[:k]
        top = float(sims[order[0]])
        for j in order:
            if sims[j] >= max(floor, top - margin):
                out.append((ph, ids.text[j], ids.id[j], float(sims[j])))
    return out

def match_symptoms(phrases, sym, lang, per_phrase=30):
    """each phrase -> lexicon entries that contain ALL its content words (shorter = more specific first);
    fuzzy fallback only when no entry covers the phrase."""
    cols = ["gloss_en", "term_sa_iast"] if lang == "en" else [c for c in ["gloss_hi", "term_hi", "term_sa_deva"] if c in sym]
    entries = [(sid, txt, words(txt)) for c in cols for sid, txt in zip(sym.symptom_id, sym[c]) if txt]
    out = []
    for ph in phrases:
        q = words(ph)
        cand = sorted(((len(q) / len(w), sid, txt) for sid, txt, w in entries if q and q <= w), reverse=True)
        if not cand:
            texts = [t for _, t, _ in entries]
            best = process.extract(ph, texts, scorer=fuzz.WRatio, limit=5, score_cutoff=85)
            cand = [(b[1] / 100, entries[b[2]][0], b[0]) for b in best]
        seen = set()
        for prec, sid, txt in cand:
            if sid not in seen:
                seen.add(sid); out.append((ph, txt, sid, prec))
            if len(seen) >= per_phrase:
                break
    return out

def rank_diseases(hits, kb, top=5):
    """rank disorders by number of complaints explained, then IDF-weighted overlap"""
    ds = kb["disease_symptom"][["disease_id", "symptom_id"]]
    # + symptoms seen in published case reports (stage 24), when present. WHO sign lists are NOT used for ranking:
    # they are broad 'some or all of the following' lists and lowered real-case accuracy (E6b: 28% -> 11% top-10)
    extra = [kb[n][["disease_id", "symptom_id"]] for n in ("disease_symptom_from_cases",) if len(kb.get(n, []))]
    prof = pd.concat([ds] + extra).groupby("disease_id").symptom_id.apply(set)
    df = Counter(s for v in prof for s in v)
    n = len(prof)
    idf = {s: math.log(n / c) + 1 for s, c in df.items()}
    by_phrase = defaultdict(set)
    for ph, _, sid, _ in hits:
        by_phrase[ph].add(sid)
    # a chief complaint may be the disease itself ('cough' -> kāsa): match complaint words to the disease name too
    dis = kb["diseases"]
    name_words = {d: words(f"{a} {b} {c} {e} {f}") for d, a, b, c, e, f in
                  zip(dis.disease_id, dis.name_en, dis.name_en_alt, dis.get("name_en_hi", dis.name_en), dis.term_hi,
                      dis.get("name_en_who", dis.name_en))}
    sym_lang = {ph: words(ph) for ph in by_phrase}
    scores = []
    for d, ss in prof.items():
        by_sym = [ph for ph, ids in by_phrase.items() if ids & ss]
        by_name = [ph for ph, q in sym_lang.items() if q and q <= name_words.get(d, set())]
        covered = sorted(set(by_sym) | set(by_name))
        if covered:
            matched = set().union(*(by_phrase[ph] & ss for ph in by_sym)) if by_sym else set()
            w = (sum(idf[s] for s in matched) / math.sqrt(sum(idf[s] ** 2 for s in ss))) + 0.5 * len(by_name)
            scores.append((len(covered), w, d, covered))
    scores.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return scores[:top]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symptoms", required=True, help="semicolon-separated symptoms (English, Hindi or Sanskrit)")
    ap.add_argument("--lang", default="en", choices=["en", "hi"])
    ap.add_argument("--no-semantic", action="store_true", help="lexical matching only (no embedding model)")
    a = ap.parse_args()
    kb = load()
    phrases = [p.strip() for p in re.split(r"[;,،|]", a.symptoms) if p.strip()]
    hits = match_symptoms(phrases, kb["symptoms"], a.lang)
    sem = [] if a.no_semantic else semantic_symptoms(phrases, a.lang)
    seen = {(h[0], h[2]) for h in hits}
    hits += [h for h in sem if (h[0], h[2]) not in seen]
    print("\n1) Symptom mapping / लक्षण मिलान  (first 3 lexicon entries per complaint; lexical + multilingual semantic)")
    sym = kb["symptoms"].set_index("symptom_id")
    shown = Counter()
    for ph, txt, sid, sc in hits:
        if shown[ph] < 3:
            shown[ph] += 1
            print(f"   '{ph}' -> {sid}  {sym.loc[sid].term_sa_iast or '-'} | {sym.loc[sid].gloss_en} | {sym.loc[sid].get('gloss_hi', '')}")
    print(f"   ({len(hits)} lexicon entries used in total)")
    ranked = rank_diseases(hits, kb)
    if not ranked:
        print("No matching disorder in the knowledge base."); return
    dis = kb["diseases"].set_index("disease_id")
    print("\n2) Candidate disorders (knowledge-base matcher) / संभावित रोग")
    for k, w, d, cov in ranked:
        r = dis.loc[d]
        print(f"   explains {k}/{len(phrases)} complaints (score {w:.2f})  {d}  {r.term_iast} ({r.term_deva}) - {r.name_en}"
              f" | NAMASTE {r.namc_code_clean}" + (f" | ICD-11 TM2 {r.icd11_tm2_code}" if r.icd11_tm2_code else "")
              + f" | doṣa: {r.dosha_label}")
    top = ranked[0][2]; r = dis.loc[top]
    lead = ", ".join(f"{dis.loc[x[2]].term_iast}" for x in ranked[:3])
    print(f"\n3) Knowledge for the leading candidates ({lead}) / प्रमुख संभावित रोगों हेतु ज्ञान")
    print(f"   Top candidate {r.term_iast} / {r.term_hi}:")
    print(f"   Definition: {r.definition_en[:300]}")
    if r.get("definition_hi", ""):
        print(f"   परिभाषा: {r.definition_hi[:300]}")
    herbs = kb["herbs"].set_index("herb_id")
    hi = kb["herb_indication"]
    # indications are often recorded for the general disease (e.g. jvara) - walk up the NAMASTE hierarchy
    related, cur = set(), top
    while cur and cur not in related:
        related.add(cur); cur = dis.loc[cur].parent_disease_id if cur in dis.index else ""
    for k, w, d, cov in ranked[:3]:
        related.add(d)
    hl = hi[hi.disease_id.isin(related)].herb_id.unique()
    ev = kb["herb_indication_evidence"]
    best = {}
    if len(ev):
        rank = {"clinical_evidence": 0, "literature_supported": 1, "sparse": 2, "no_literature": 3, "not_queryable": 4}
        for r in ev[ev.disease_id.isin(related)].itertuples():
            cur = best.get(r.herb_id)
            if cur is None or rank.get(r.evidence_tier, 9) < rank.get(cur.evidence_tier, 9):
                best[r.herb_id] = r
        order = {"clinical_evidence": 0, "literature_supported": 1, "sparse": 2, "no_literature": 3}
        hl = sorted(hl, key=lambda h: order.get(getattr(best.get(h), "evidence_tier", ""), 4))
    # poisonous plants (mahāviṣa / upaviṣa) go last: they need classical purification and specialist supervision
    hl = sorted(hl, key=lambda h: "viṣa" in str(herbs.loc[h].safety_class))
    hl = list(hl)[:12]
    if len(hl):
        print("   Herbs recorded for this condition (sorted by literature evidence) / औषधियाँ:")
        for h in hl:
            x = herbs.loc[h]
            warn = f"  ⚠ {x.safety_class}: {x.safety_hazard_en}" if x.safety_class else ""
            e = best.get(h)
            evs = (f" | evidence: {TIER.get(e.evidence_tier, e.evidence_tier)}"
                   + (f" ({int(e.n_clinical)} clinical / {int(e.n_pair)} papers)" if str(e.n_pair) not in ("", "nan") else "")) if e is not None else ""
            print(f"     - {x.name_sa_iast or x.name_ascii} ({x.accepted_name}) {x.name_hi_common or x.name_hi_ayurvedic} | "
                  f"vīrya {x.virya or '-'} | pacifies {x.dosha_pacify or '-'}{evs}{warn}")
    fi = kb["formulation_indications"]; fo = kb["formulations"].set_index("form_id")
    fl = fi[fi.disease_id.isin(related)].form_id.unique()
    if len(fl):
        print("   Classical formulations (curated; verify against AFI) / शास्त्रीय योग:")
        for f in fl:
            x = fo.loc[f]
            print(f"     - {x.name_sa_iast} ({x.name_en}, {x.dosage_form}) - {x.classical_reference}" + (f"  ⚠ {x.safety_note}" if x.safety_note else ""))
    td = kb["therapy_disease"]
    if len(td):
        sp = td[td.disease_id.isin(related) & td.relation.isin(["site_specific_procedure", "disorder_protocol", "category_principle"])]
        if len(sp):
            print("   Classical procedures for this condition / शास्त्रीय चिकित्सा-कर्म:")
            for (tname, ten), g in list(sp.groupby(["therapy_term_iast", "therapy_term_en"], sort=False))[:8]:
                print(f"     - {tname} ({ten}) - {g.reference.iloc[0]}" + (f"  ⚠ {g.note.iloc[0]}" if g.note.iloc[0] else ""))
        ob = td[td.disease_id.isin(related) & (td.relation == "observed_in_published_cases")]
        if len(ob):
            print("   Procedures reported in published case reports: " + "; ".join(
                f"{a} ({b.split(' case')[0]})" for a, b in zip(ob.therapy_term_iast, ob.reference)))
    cl = kb["case_report_links"]
    if len(cl):
        seen = cl[cl.disease_id.isin(related)].sort_values("n_cases", ascending=False).head(6)
        if len(seen):
            print("   Medicines used in published case reports for this condition (not curated; verify): " + "; ".join(
                f"{n} (x{k}{'' if kb_ else ', not yet in KB'})" for n, k, kb_ in zip(seen.entity_name, seen.n_cases, seen.in_kb_for_disorder_family)))
    for d in [x for x in ["vata", "pitta", "kapha"] if str(r[f"dosha_{x}"]) == "True"]:
        en, hi_ = SHODHANA[d]
        print(f"   Classical śodhana principle for {d}: {en} / {hi_}  (Caraka Saṃhitā Sūtrasthāna 25.40)")
    print("\n   This output is decision support for a qualified practitioner, not a diagnosis or prescription.")
    print("   यह परिणाम योग्य चिकित्सक के लिए निर्णय-सहायता है, निदान या पर्चा नहीं।")

if __name__ == "__main__":
    main()
