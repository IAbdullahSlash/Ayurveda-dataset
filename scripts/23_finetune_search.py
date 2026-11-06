#!/usr/bin/env python3
"""
Stage 23 - Domain fine-tuning of the multilingual search model (improves experiment E5).

multilingual-e5-small is fine-tuned contrastively (InfoNCE with in-batch negatives) on AyurKB's own parallel data:
  Hindi / Sanskrit headword (Devanagari)  ->  English description      ("query: " / "passage: ")
  Hindi gloss (machine translation)        ->  English description
drawn from WHO + SAT terminology, herbs, and every disorder and symptom record that is NOT in the E5 test sample.
Leakage guard: any training pair whose headword skeleton equals the skeleton of a test-set headword is dropped, and known concept memberships and description overlaps are excluded. Unannotated paraphrases may remain.
The E5 benchmark (same 800-query samples against the complete eligible corpus) is then re-run with the base and the fine-tuned model.
Output: models/multilingual-e5-small-ayurkb/ (safetensors, not packaged: ~470 MB, rebuilt by this script),
        reports/ml/E5b_finetuned_retrieval.json
"""
import json, math, random, sys, time
from importlib import import_module
from pathlib import Path
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.keys import skeleton
from lib.retrieval_guard import concept_exclusions, DescriptionGuard
xl = import_module("10_crosslingual")

ROOT = Path(__file__).resolve().parents[1]
OUTM = ROOT / "models/multilingual-e5-small-ayurkb"
REP = ROOT / "reports/ml"
rd = xl.rd
SEED = 7

def e5_samples(limit=800):
    """exactly the candidate sets of stage 10 (same filters, same shuffle, first 800)"""
    d = rd("diseases"); d = d[(d.definition_en != "") & (d.term_hi != "")]
    s = rd("symptoms"); s = s[(s.term_sa_iast != "") & (s.gloss_en != "")]
    tasks = {
        "diseases": ((d.name_en + ". " + d.definition_en).tolist(), d.term_hi.tolist(),
                     (d.name_en_hi + "। " + d.definition_hi).tolist(), d.disease_id.tolist()),
        "symptoms": (s.gloss_en.tolist(), s.term_hi.tolist(), s.gloss_hi.tolist(), s.symptom_id.tolist()),
    }
    out = {}
    for name, (docs, qt, qx, ids) in tasks.items():
        idx = [i for i in range(len(docs)) if docs[i].strip() and qt[i].strip() and qx[i].strip()]
        random.Random(SEED).shuffle(idx)
        if limit is not None:
            idx = idx[:limit]
        out[name] = dict(docs=[docs[i] for i in idx], q_term=[qt[i] for i in idx], q_text=[qx[i] for i in idx],
                         ids=[ids[i] for i in idx])
    return out

def training_pairs(test):
    from lib.indic import deva_to_iast
    banned_ids = set(test["diseases"]["ids"]) | set(test["symptoms"]["ids"])
    banned_ids = concept_exclusions(banned_ids, rd("concept_members"))
    description_guard = DescriptionGuard([p for task in test.values() for p in task["docs"]])
    banned_sk = {skeleton(deva_to_iast(q)) for t in test.values() for q in t["q_term"]}
    pairs = []
    def add(q, p, kind, record_id):
        if (record_id not in banned_ids and q and p and len(p) > 2
                and skeleton(deva_to_iast(q)) not in banned_sk and not description_guard.overlaps(p)):
            pairs.append((q, p[:400], kind))
    t = rd("terminology")
    for r in t.itertuples():
        en = (r.term_en + ". " + r.definition_en).strip(". ")
        add(r.term_hi or r.term_sa_deva_primary, en, "term_headword", r.term_uid)
        if getattr(r, "term_en_hi", ""):
            add(r.term_en_hi, en, "term_gloss", r.term_uid)
    h = rd("herbs")
    for r in h.itertuples():
        en = f"{r.accepted_name} {r.name_en}. {r.description_en}".strip()
        add(r.name_sa_deva, en, "herb_headword", r.herb_id); add(r.name_hi_common, en, "herb_hindi", r.herb_id)
    d = rd("diseases")
    for r in d.itertuples():
        if r.disease_id in banned_ids or not r.definition_en:
            continue
        en = r.name_en + ". " + r.definition_en
        add(r.term_hi, en, "disease_headword", r.disease_id); add(r.name_en_hi + "। " + r.definition_hi, en, "disease_gloss", r.disease_id)
    s = rd("symptoms")
    for r in s.itertuples():
        if r.symptom_id in banned_ids or not r.gloss_en:
            continue
        add(r.term_hi, r.gloss_en, "symptom_headword", r.symptom_id); add(r.gloss_hi, r.gloss_en, "symptom_gloss", r.symptom_id)
    random.Random(SEED).shuffle(pairs)
    # the headword task is the weak one (gloss queries already reach R@10 0.86-0.93): train on all headword pairs plus a
    # 25% sample of gloss pairs so the model keeps its cross-lingual alignment
    head = [p for p in pairs if p[2].endswith(("headword", "hindi"))]
    gloss = [p for p in pairs if not p[2].endswith(("headword", "hindi"))]
    # CPU budget: 6,000 headword pairs (all disease/herb/term kinds kept, symptoms sampled) + 1,500 gloss pairs
    keep = [p for p in head if not p[2].startswith("symptom")]
    sym = [p for p in head if p[2].startswith("symptom")]
    mixed = keep[:3500] + sym[:2500] + gloss[:1500]      # both test tasks represented; gloss pairs keep the alignment
    random.Random(SEED).shuffle(mixed)
    return mixed

def train(enc, pairs, epochs=1, bs=32, lr=4e-5, scale=20.0, max_q=32, max_p=64):
    m, tok = enc.m, enc.tok
    m.train()
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=0.01)
    steps = epochs * math.ceil(len(pairs) / bs)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / (0.06 * steps)) * max(0.0, (steps - s) / steps))
    def emb(texts, maxlen):
        b = tok(texts, padding=True, truncation=True, max_length=maxlen, return_tensors="pt")
        hdn = m(**b).last_hidden_state
        mask = b["attention_mask"].unsqueeze(-1).float()
        return torch.nn.functional.normalize((hdn * mask).sum(1) / mask.sum(1), dim=-1)
    step, t0 = 0, time.time()
    for ep in range(epochs):
        for i in range(0, len(pairs), bs):
            batch = pairs[i:i + bs]
            # de-duplicate passages inside the batch (identical positives would be false negatives)
            seen, qs, ps = set(), [], []
            for q, p, _ in batch:
                if p not in seen:
                    seen.add(p); qs.append("query: " + q); ps.append("passage: " + p)
            if len(qs) < 4:
                continue
            qv, pv = emb(qs, max_q), emb(ps, max_p)
            logits = scale * qv @ pv.T
            labels = torch.arange(len(qs))
            loss = (torch.nn.functional.cross_entropy(logits, labels) + torch.nn.functional.cross_entropy(logits.T, labels)) / 2
            opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); sched.step()
            step += 1
            if step % 25 == 0:
                print(f"  step {step}/{steps}  loss {loss.item():.3f}  {time.time() - t0:.0f}s", flush=True)
    m.eval()

def evaluate(enc, test, full_corpus=True):
    out = {}
    candidates = e5_samples(limit=None) if full_corpus else test
    for name, t in test.items():
        candidate = candidates[name]
        De = enc.encode(candidate["docs"], "passage: ")
        lookup = {record_id:i for i,record_id in enumerate(candidate["ids"])}
        gold = np.array([lookup[record_id] for record_id in t["ids"]])
        out[name] = {}
        for qn in ("q_term", "q_text"):
            S = enc.encode(t[qn], "query: ") @ De.T
            out[name][{"q_term": "hindi_headword", "q_text": "hindi_text"}[qn]] = xl.metrics(xl.ranks_from_scores(S, gold))
    return out

def main(epochs=1):
    torch.manual_seed(SEED)
    test = e5_samples()
    pairs = training_pairs(test)
    kinds = pd.Series([k for _, _, k in pairs]).value_counts().to_dict()
    print(f"training pairs: {len(pairs)} {kinds}", flush=True)
    enc = xl.E5(threads=3)
    base = evaluate(enc, test)
    print("base:", json.dumps({t: {q: round(v['recall_at_10'], 3) for q, v in r.items()} for t, r in base.items()}), flush=True)
    t0 = time.time()
    train(enc, pairs, epochs=epochs)
    tuned = evaluate(enc, test)
    print("tuned:", json.dumps({t: {q: round(v['recall_at_10'], 3) for q, v in r.items()} for t, r in tuned.items()}), flush=True)
    OUTM.mkdir(parents=True, exist_ok=True)
    enc.m.save_pretrained(OUTM, safe_serialization=True); enc.tok.save_pretrained(OUTM)
    (REP / "E5b_finetuned_retrieval.json").write_text(json.dumps({
        "candidate_scope": "complete eligible corpus", "query_scope": "800 record-derived queries per task; not independently authored",
        "test_ids": {name:task["ids"] for name,task in test.items()},
        "candidate_counts": {name:len(task["ids"]) for name,task in e5_samples(limit=None).items()},
        "base": base, "finetuned": tuned, "training_pairs": len(pairs), "pair_kinds": kinds, "epochs": epochs,
        "train_seconds": round(time.time() - t0), "leakage_guard": "test IDs, transitive concept members, exact/near-duplicate descriptions and test headword skeletons excluded; semantic paraphrase overlap remains unmeasured",
        "model_dir": str(OUTM.relative_to(ROOT))}, indent=2))

if __name__ == "__main__":
    main()
