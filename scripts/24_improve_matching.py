#!/usr/bin/env python3
"""
Stage 24 - Better symptom -> disorder matching on REAL case reports (experiment E6, improved).

Adds, step by step, and measures each step on the same cases as the stage-14 baseline:
  V0  baseline: lexical SAT-symptom matching, flat ranking of disorders (stage 14)
  V1  + clinical-term crosswalk: ~170 modern clinical expressions ('morning stiffness', 'pedal oedema' ...) mapped to
        SAT symptoms (exact gloss > all-words entry > multilingual-embedding neighbours) -> curation/clinical_symptom_crosswalk.csv
  V2  + semantic clause matching: complaint clauses embedded with multilingual-e5 and matched to the symptom index
  V3  + group-level ranking: disorders collapsed to their disorder group (depth <= 3 ancestor) before taking the top k
  V4  + profiles learned from real cases: symptoms of TRAINING cases added to their diagnosis (5-fold cross-validation;
        a test case never contributes to its own profile)
  V5  + modern diagnosis: the article's MeSH major topics mapped to disorders through the curated biomedical
        correspondence table (a separate condition: it assumes the biomedical diagnosis is already known)
Output: reports/ml/E6b_matching_improvements.json, data/processed/case_report_symptoms_semantic.csv,
        curation/clinical_symptom_crosswalk.csv
"""
import json, math, re, sys
from collections import Counter, defaultdict
from importlib import import_module
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
cr = import_module("14_case_reports")
xl = import_module("10_crosslingual")

ROOT = Path(__file__).resolve().parents[1]
P, CACHE, CUR, REP = ROOT / "data/processed", ROOT / "data/interim/cache", ROOT / "curation", ROOT / "reports/ml"
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)
KS = (1, 3, 10, 30)

CLINICAL_TERMS = """joint pain; knee pain; back pain; low back pain; lower back pain; neck pain; shoulder pain; hip pain; abdominal pain;
epigastric pain; chest pain; headache; pain on movement; radiating pain; burning pain; pricking pain; throbbing pain; muscle pain;
body ache; bone pain; heel pain; painful micturition; painful defecation; painful menstruation; morning stiffness; joint stiffness;
restricted movement; restricted range of motion; difficulty in walking; difficulty walking; limping; joint swelling;
swelling of joints; pedal oedema; facial puffiness; swelling of feet; localized swelling; itching; pruritus; scaling; scaly lesions;
erythema; redness of skin; plaques; papules; vesicles; blisters; discoloration; hyperpigmentation; hypopigmentation; white patches;
dryness of skin; dry skin; cracking of skin; fissures; oozing; discharge; pus discharge; foul smell; crusting; ulcer; non healing ulcer;
wound; rash; urticaria; wheals; hair fall; dandruff; burning sensation; loss of appetite; decreased appetite; anorexia; indigestion;
acidity; heartburn; sour belching; bloating; abdominal distension; flatulence; constipation; hard stools; diarrhoea; loose stools;
frequent stools; mucus in stools; blood in stool; bleeding per rectum; nausea; vomiting; hiccups; excessive thirst; dry mouth;
bitter taste; coated tongue; incomplete evacuation; tenesmus; weight loss; weight gain; cough; productive cough; dry cough;
breathlessness; shortness of breath; wheezing; chest tightness; sneezing; nasal discharge; nasal blockage; sore throat;
hoarseness of voice; fever; chills; night sweats; frequent urination; increased frequency of urination; burning micturition;
painful urination; urgency of urination; nocturia; incontinence of urine; retention of urine; blood in urine; numbness; tingling;
paresthesia; weakness of limbs; weakness; fatigue; giddiness; dizziness; vertigo; tremors; loss of sensation; facial deviation;
slurred speech; difficulty in speech; inability to walk; paralysis; convulsions; seizures; loss of consciousness; insomnia;
disturbed sleep; excessive sleep; anxiety; depression; irritability; anger; fear; poor concentration; forgetfulness; memory loss;
restlessness; low mood; irregular menstruation; irregular periods; heavy menstrual bleeding; excessive bleeding; scanty menstruation;
absence of menstruation; white discharge; vaginal discharge; infertility; blurred vision; diminished vision; redness of eyes;
watering of eyes; itching of eyes; ear pain; ear discharge; tinnitus; hearing loss; lethargy; heaviness of body; pallor; jaundice;
yellowish discoloration; palpitations; sweating; excessive sweating; generalized weakness; body pain; malaise""".replace("\n", " ")
CLINICAL_TERMS = [t.strip() for t in CLINICAL_TERMS.split(";") if t.strip()]

def build_crosswalk(lex, enc, X, sym_ids, write=True):
    """clinical phrase -> SAT symptom ids. Exact gloss first, then lexicon entries containing all words, then embeddings."""
    S = lex["S"]
    entries = [(sid, set(cr.norm_words(g))) for sid, g in zip(S.symptom_id, S.gloss_en) if g]
    Q = enc.encode(CLINICAL_TERMS, "query: ")
    sims = Q @ X.T
    rows = []
    for i, term in enumerate(CLINICAL_TERMS):
        key = tuple(cr.norm_words(term))
        ids, method = set(), ""
        if key in lex["sym_en"]:
            ids, method = set(lex["sym_en"][key]), "exact_gloss"
        else:
            q = set(key)
            cand = sorted((len(w), sid) for sid, w in entries if q and q <= w)[:8]
            if cand:
                ids, method = {sid for _, sid in cand}, "all_words_entry"
        order = np.argsort(-sims[i])[:10]
        top = float(sims[i, order[0]])
        emb = [sym_ids[j] for j in order if sims[i, j] >= max(0.86, top - 0.02)][:5]
        if not ids and emb:
            ids, method = set(emb), "embedding_neighbours"
        rows.append(dict(clinical_term=term, symptom_ids=";".join(sorted(ids)), method=method or "unmapped",
                         best_similarity=round(top, 3),
                         sat_glosses=" | ".join(dict.fromkeys(S.set_index("symptom_id").loc[sorted(ids)].gloss_en))[:300] if ids else ""))
    cw = pd.DataFrame(rows)
    cw["review_status"] = "auto-mapped; needs expert review"
    if write:
        cw.to_csv(CUR / "clinical_symptom_crosswalk.csv", index=False)
    return {tuple(cr.norm_words(r.clinical_term)): set(r.symptom_ids.split(";")) for r in cw.itertuples() if r.symptom_ids}

CLAUSE_SPLIT = re.compile(r"[.;:,()\[\]]|\band\b|\bwith\b|\balong with\b|\bassociated with\b|\bwhich\b|\bsince\b", re.I)

def clauses(text):
    out = []
    for c in CLAUSE_SPLIT.split(text or ""):
        w = re.findall(r"[A-Za-z]+", c)
        if 2 <= len(w) <= 8 and not re.search(r"\d{2,}|year|old|male|female|patient|hospital|department|visited|admitted", c, re.I):
            out.append(" ".join(w).lower())
    return list(dict.fromkeys(out))

def semantic_ids(cases, enc, X, sym_ids, floor=0.87, margin=0.02):
    allc = [(c["case_id"], cl) for c in cases for cl in clauses(c.get("_pres") or "")]
    if not allc:
        return {}, pd.DataFrame()
    Q = enc.encode([cl for _, cl in allc], "query: ")
    out, rows = defaultdict(set), []
    for (cid, cl), q in zip(allc, Q):
        sims = X @ q
        order = np.argpartition(-sims, 5)[:5]
        order = order[np.argsort(-sims[order])]
        top = float(sims[order[0]])
        for j in order:
            if sims[j] >= max(floor, top - margin):
                out[cid].add(sym_ids[j]); rows.append((cid, cl, sym_ids[j], round(float(sims[j]), 3)))
    return out, pd.DataFrame(rows, columns=["case_id", "clause", "symptom_id", "similarity"])

class Matcher:
    """IDF-weighted overlap / profile norm (same formula as stage 14), with optional extra profile symptoms."""
    def __init__(self, enriched=False, extra=None):
        ds, D = rd("disease_symptom"), rd("diseases")
        tables = extra if extra is not None else (("disease_symptom_who", "disease_symptom_inferred") if enriched else ())
        if tables:                                     # + WHO sign lists and/or inherited profiles (stage 25)
            more = [rd(n)[["disease_id", "symptom_id"]] for n in tables if (P / f"{n}.csv").exists()]
            ds = pd.concat([ds[["disease_id", "symptom_id"]]] + more)
        self.base = ds.groupby("disease_id").symptom_id.apply(set).to_dict()
        n = len(self.base)
        df = Counter(s for v in self.base.values() for s in v)
        self.idf = defaultdict(lambda: math.log(n) + 1, {s: math.log(n / c) + 1 for s, c in df.items()})
        self.parent = dict(zip(D.disease_id, D.parent_disease_id)); self.depth = dict(zip(D.disease_id, D.depth))
        self.children = defaultdict(set)
        for c, p in self.parent.items():
            if p:
                self.children[p].add(c)
        self.set_profiles(self.base)

    def set_profiles(self, prof):
        self.prof = prof
        self.ids = sorted(prof)
        syms = sorted({s for v in prof.values() for s in v})
        self.col = {s: i for i, s in enumerate(syms)}
        r, c, v = [], [], []
        for i, d in enumerate(self.ids):
            for s in prof[d]:
                r.append(i); c.append(self.col[s]); v.append(self.idf[s])
        self.M = sparse.csr_matrix((v, (r, c)), shape=(len(self.ids), len(syms)))
        self.norm = np.sqrt(np.asarray(self.M.multiply(self.M).sum(1)).ravel()) + 1e-9

    def rank(self, sids, boost=None):
        q = np.zeros(len(self.col))
        for s in sids:
            if s in self.col:
                q[self.col[s]] = 1.0
        sc = (self.M @ q) / self.norm
        if boost:
            for d, b in boost.items():
                if d in self.prof:
                    sc[self.ids.index(d)] += b
        nz = np.nonzero(sc)[0]
        return [self.ids[i] for i in nz[np.argsort(-sc[nz])]]

    def group(self, d):
        cur = d
        while self.depth.get(cur, 0) > 3 and self.parent.get(cur):
            cur = self.parent[cur]
        return cur

    def family(self, d):
        fam, stack = {d}, [d]
        while stack:
            for c in self.children.get(stack.pop(), ()):
                if c not in fam:
                    fam.add(c); stack.append(c)
        cur = self.parent.get(d, "")
        while cur and self.depth.get(cur, 0) >= 3 and cur not in fam:
            fam.add(cur); fam |= self.children.get(cur, set()); cur = self.parent.get(cur, "")
        return fam

def hits(m, ranked, gold, grouped):
    fam = set().union(*(m.family(g) for g in gold))
    if grouped:
        seen, order = set(), []
        for d in ranked:
            g = m.group(d)
            if g not in seen:
                seen.add(g); order.append(g)
        famg = {m.group(x) for x in fam}
        pos = next((i for i, g in enumerate(order) if g in famg), None)
    else:
        pos = next((i for i, d in enumerate(ranked) if d in fam), None)
    return pos

def score(positions, n_total):
    s = {f"hit@{k}": round(float(np.mean([p is not None and p < k for p in positions])), 3) for k in KS}
    s["MRR"] = round(float(np.sum([1 / (p + 1) for p in positions if p is not None]) / len(positions)), 3)
    s["n_cases"] = len(positions)
    return s

def mesh_boosts():
    """MeSH descriptor / biomedical concept (lower-case) -> disorders, from the curated correspondence table"""
    q = pd.read_csv(CUR / "disorder_biomedical_queries.csv", keep_default_na=False)
    m = defaultdict(set)
    for r in q.itertuples():
        for t in re.findall(r'"?([^"()\[\]]+?)"?\[mh\]', r.pubmed_query):
            m[t.strip().lower()].add(r.disease_id)
        for t in re.split(r"[/,;()]", r.biomedical_concept_en):
            t = t.strip().lower()
            if len(t) > 4 and not t.startswith(("disorders", "diseases of", "not a disorder")):
                m[t].add(r.disease_id)
    return m

def mesh_terms(topics):
    out = set()
    for t in [x.strip().lower() for x in topics.split(";") if x.strip()]:
        out.add(t)
        if ", " in t:                                  # 'arthritis, rheumatoid' -> 'rheumatoid arthritis'
            a, b = t.split(", ", 1); out.add(f"{b} {a}")
    return out

def main(ft=False):
    """ft=True: same experiment with the domain fine-tuned search model (stage 23); writes only its JSON"""
    recs = json.loads((CACHE / "epmc_case_reports.json").read_text())
    seen, uniq = set(), []
    for r in recs:
        k = r.get("pmcid") or r.get("pmid") or r.get("id")
        if k not in seen:
            seen.add(k); uniq.append(r)
    lex = cr.build_lexicons()
    rows, _, _ = cr.extract(uniq, lex, keep_text=True)
    S = lex["S"]
    lex["sym_key"] = {sid: cr.skeleton(t) for sid, t in zip(S.symptom_id, S.term_sa_iast)}
    emb = ROOT / ("release/embeddings_ft" if ft else "release/embeddings")
    X = np.load(emb / "symptoms.npy").astype("float32")
    sym_ids = pd.read_csv(emb / "symptoms_ids.csv", keep_default_na=False).id.tolist()
    enc = xl.E5(threads=2, model=xl.MODEL_FT if ft else None)
    cw = build_crosswalk(lex, enc, X, sym_ids, write=not ft)
    m = Matcher()
    with_prof = set(m.base)
    cases = [c for c in rows if c["case_kind"] == "therapeutic" and [d for d in c["dx_ids"] if d in with_prof]]
    # V1 crosswalk ids / V2 semantic ids
    cw_ids = {}
    for c in cases:
        words = cr.norm_words(c.get("_pres") or "")
        found = set()
        for n_ in range(4, 0, -1):
            for i in range(len(words) - n_ + 1):
                found |= cw.get(tuple(words[i:i + n_]), set())
        cw_ids[c["case_id"]] = found
    sem, sem_rows = semantic_ids(cases, enc, X, sym_ids)
    if not ft:
        sem_rows.to_csv(P / "case_report_symptoms_semantic.csv", index=False)
    dx_key_block = lambda c: {c["dx_term_key"], *c["dx_other_keys"]}
    def sids(c, level):
        s = set(c["presentation_symptom_ids"])
        if level >= 1: s |= cw_ids.get(c["case_id"], set())
        if level >= 2: s |= sem.get(c["case_id"], set())
        return {x for x in s if lex["sym_key"].get(x, "") not in dx_key_block(c)}      # never count the diagnosis name itself
    base_cases = [c for c in cases if len(c["presentation_phrases"]) >= 2]            # the stage-14 evaluation set
    gold = {c["case_id"]: [d for d in c["dx_ids"] if d in with_prof] for c in cases}
    res = {}
    def run(name, case_set, level, grouped, learned=False, boost=False, seeds=(42,), kb=True):
        per_seed = []
        mb = mesh_boosts() if boost else None
        for seed in seeds:
            per_seed.append(run_once(case_set, level, grouped, learned, mb, seed, kb))
        res[name] = {k: round(float(np.mean([s[k] for s in per_seed])), 3) for k in per_seed[0]}
        if len(seeds) > 1:
            res[name]["hit@10_sd_over_seeds"] = round(float(np.std([s["hit@10"] for s in per_seed])), 3)
            res[name]["cv_seeds"] = len(seeds)
        print(f"  {name:58s} {res[name]}", flush=True)
    def run_once(case_set, level, grouped, learned, mb, seed, kb):
        pos = []
        folds = np.array_split(np.random.RandomState(seed).permutation(len(case_set)), 5) if learned else [np.arange(len(case_set))]
        for f in folds:
            test = set(f.tolist())
            if learned:
                prof = {d: (set(v) if kb else set()) for d, v in m.base.items()}
                for j, c in enumerate(case_set):
                    if j not in test:
                        for g in gold[c["case_id"]]:
                            for tgt in {g, m.group(g)}:
                                if tgt in prof:
                                    prof[tgt] |= sids(c, level)
                m.set_profiles(prof)
            for j in sorted(test):
                c = case_set[j]
                bst = None
                if mb is not None:
                    terms = mesh_terms(c.get("mesh_major_topics_str", ""))
                    bst = {d: 1.0 for t in terms for d in mb.get(t, ())}
                pos.append(hits(m, m.rank(sids(c, level), bst), gold[c["case_id"]], grouped))
        if learned and not kb:
            pass
        m.set_profiles(m.base)
        return score(pos, len(case_set))
    for c in cases:
        c["mesh_major_topics_str"] = "; ".join(c["mesh_major"])
    print(f"cases with a profiled diagnosis: {len(cases)}; stage-14 evaluation set: {len(base_cases)}")
    run("V0 baseline (lexical, flat ranking)", base_cases, 0, False)
    run("V1 + clinical-term crosswalk", base_cases, 1, False)
    run("V2 + semantic clause matching", base_cases, 2, False)
    run("V3 + disorder-group ranking", base_cases, 2, True)
    SEEDS = (42, 7, 11, 23, 99)
    run("V4 + profiles learned from real cases (5-fold CV)", base_cases, 2, True, learned=True, seeds=SEEDS)
    run("V4-ablation: case-learned profiles only, no KB knowledge", base_cases, 2, True, learned=True, seeds=SEEDS, kb=False)
    run("V5 + modern diagnosis (MeSH) [diagnosis known]", base_cases, 2, True, learned=True, boost=True, seeds=SEEDS)
    # how much of V4 is just "common diagnoses first"? rank groups by their frequency among the TRAINING cases only
    fq = []
    for seed in SEEDS:
        pos = []
        for f in np.array_split(np.random.RandomState(seed).permutation(len(base_cases)), 5):
            test = set(f.tolist())
            cnt = Counter(m.group(g) for j, c in enumerate(base_cases) if j not in test for g in gold[c["case_id"]])
            order = [g for g, _ in cnt.most_common()]
            pos += [hits(m, order, gold[base_cases[j]["case_id"]], True) for j in sorted(test)]
        fq.append(score(pos, len(base_cases)))
    res["baseline_training_diagnosis_frequency (no symptoms)"] = {k: round(float(np.mean([s[k] for s in fq])), 3) for k in fq[0]}
    print("  baseline: most frequent training diagnoses     ", res["baseline_training_diagnosis_frequency (no symptoms)"])
    wider = [c for c in cases if len(sids(c, 2)) >= 2]
    run("V4 on all cases with 2+ symptoms after V2", wider, 2, True, learned=True, seeds=SEEDS)
    # popularity baseline at group level, same set, for reference
    pop = sorted(m.base, key=lambda d: -len(m.base[d]))
    res["baseline_popularity_group_level"] = score([hits(m, pop, gold[c["case_id"]], True) for c in base_cases], len(base_cases))
    # the same variants with the enriched knowledge base (NAMASTE + WHO sign lists + inherited profiles)
    m = Matcher(enriched=True)
    run("V3e group ranking, enriched KB profiles", base_cases, 2, True)
    run("V4e case-learned + enriched KB profiles (5-fold CV)", base_cases, 2, True, learned=True, seeds=SEEDS)
    m = Matcher(extra=("disease_symptom_who",))      # which part hurts? WHO sign lists alone ...
    run("V3w group ranking, + WHO sign lists only", base_cases, 2, True)
    run("V4w case-learned + WHO sign lists (5-fold CV)", base_cases, 2, True, learned=True, seeds=SEEDS)
    m = Matcher(extra=("disease_symptom_inferred",))  # ... or the inherited profiles alone
    run("V3i group ranking, + inherited profiles only", base_cases, 2, True)
    m = Matcher()
    # learned profiles from ALL therapeutic cases (for use by the expert system; evaluation above used CV)
    agg, who = Counter(), defaultdict(set)
    for c in cases:
        for g in gold[c["case_id"]]:
            for s in sids(c, 2):
                agg[(g, s)] += 1; who[(g, s)].add(c["case_id"])
    Sx = S.set_index("symptom_id")
    learned = pd.DataFrame([dict(disease_id=d, symptom_id=s, n_cases=n, gloss_en=Sx.gloss_en.get(s, ""),
                                 case_ids=";".join(sorted(who[(d, s)])[:10]), source_id="S10",
                                 data_origin="learned from published case reports (lexical + crosswalk + semantic matching); not curated")
                            for (d, s), n in agg.items()])
    if not ft:
        learned.to_csv(P / "disease_symptom_from_cases.csv", index=False)
    print(f"case-learned disorder-symptom associations: {len(learned)} ({learned.disease_id.nunique()} disorders)")
    out = {"variants": res, "n_crosswalk_terms": len(CLINICAL_TERMS), "n_crosswalk_mapped": len(cw),
           "median_symptom_ids": {"V0": float(np.median([len(sids(c, 0)) for c in base_cases])),
                                  "V2": float(np.median([len(sids(c, 2)) for c in base_cases]))},
           "notes": "Same cases and gold labels as stage 14 (diagnosis named in title/keywords/abstract). Group = disorder or its "
                    "depth-3 ancestor. V4 uses 5-fold CV over cases; V5 assumes the biomedical diagnosis is known."}
    out["search_model"] = "domain fine-tuned (stage 23)" if ft else "multilingual-e5-small (base)"
    (REP / ("E6b_matching_improvements_finetuned.json" if ft else "E6b_matching_improvements.json")).write_text(json.dumps(out, indent=2))
    print(json.dumps(out["median_symptom_ids"]))

if __name__ == "__main__":
    main("--ft" in sys.argv)
