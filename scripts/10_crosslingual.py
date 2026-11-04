#!/usr/bin/env python3
"""
Stage 10 - E5: bilingual retrieval benchmark (can a Hindi query find the right English KB record?).

Queries (Hindi side)
  Q-term : Hindi/Sanskrit headword of the record (term_hi, Devanagari) - independent of the English text
  Q-text : Hindi gloss/name produced by the bilingual layer (name_en_hi / gloss_hi)
Documents (English side): disease name + definition / symptom gloss, *without* the Sanskrit headword.
Retrievers
  (a) transliteration + char n-gram TF-IDF  (Devanagari -> IAST -> ASCII; works where English text keeps Sanskrit words)
  (b) dense multilingual embeddings (intfloat/multilingual-e5-small, MIT, safetensors; mean pooling)
  (c) hybrid = reciprocal-rank fusion of (a) and (b)
Metrics: Recall@1/5/10 and MRR.  Output: reports/ml/E5_crosslingual_retrieval.json + figure.
"""
import json, os, random, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import AutoTokenizer, AutoModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.indic import deva_to_iast, ascii_fold
from lib.ml_utils import plt

ROOT = Path(__file__).resolve().parents[1]
P, REP, FIG = ROOT / "data/processed", ROOT / "reports/ml", ROOT / "reports/figures"
MODEL = ROOT / "models/multilingual-e5-small"
MODEL_FT = ROOT / "models/multilingual-e5-small-ayurkb"      # built by stage 23 (domain fine-tuned)
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)

class E5:
    def __init__(self, threads=2, model=None):
        torch.set_num_threads(threads)
        self.path = Path(model) if model else Path(os.environ.get("AYURKB_E5_MODEL", MODEL))
        self.tok = AutoTokenizer.from_pretrained(self.path)
        self.m = AutoModel.from_pretrained(self.path, use_safetensors=True).eval()

    @torch.no_grad()
    def encode(self, texts, prefix, bs=64):
        out = []
        for i in range(0, len(texts), bs):
            b = self.tok([prefix + t for t in texts[i:i + bs]], padding=True, truncation=True, max_length=192, return_tensors="pt")
            h = self.m(**b).last_hidden_state
            mask = b["attention_mask"].unsqueeze(-1).float()
            v = (h * mask).sum(1) / mask.sum(1)
            out.append(torch.nn.functional.normalize(v, dim=-1).numpy())
        return np.vstack(out)

def ranks_from_scores(S, gold):
    order = np.argsort(-S, axis=1)
    return np.array([int(np.where(order[i] == gold[i])[0][0]) + 1 for i in range(len(gold))])

def metrics(r):
    return dict(recall_at_1=float(np.mean(r <= 1)), recall_at_5=float(np.mean(r <= 5)), recall_at_10=float(np.mean(r <= 10)),
                mrr=float(np.mean(1.0 / r)))

def rrf(*rank_mats, k=60):
    return sum(1.0 / (k + R) for R in rank_mats)

def rank_matrix(S):
    order = np.argsort(-S, axis=1)
    R = np.empty_like(order)
    rows = np.arange(S.shape[0])[:, None]
    R[rows, order] = np.arange(1, S.shape[1] + 1)
    return R

def run_task(name, docs_en, q_term, q_text, enc, n_sample=800, seed=7):
    idx = [i for i in range(len(docs_en)) if docs_en[i].strip() and q_term[i].strip() and q_text[i].strip()]
    random.Random(seed).shuffle(idx)
    idx = idx[:n_sample]
    D = [docs_en[i] for i in idx]
    gold = np.arange(len(idx))
    res = {}
    # (a) transliteration + char n-gram
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True).fit([ascii_fold(d) for d in D])
    Dm = vec.transform([ascii_fold(d) for d in D])
    De = enc.encode(D, "passage: ")
    for qname, Q in [("hindi_headword", [q_term[i] for i in idx]), ("hindi_text", [q_text[i] for i in idx])]:
        Sa = (vec.transform([ascii_fold(deva_to_iast(q)) for q in Q]) @ Dm.T).toarray()
        Sb = enc.encode(Q, "query: ") @ De.T
        Ra, Rb = rank_matrix(Sa), rank_matrix(Sb)
        Sc = rrf(Ra, Rb)
        res[qname] = {
            "transliteration_char_tfidf": metrics(ranks_from_scores(Sa, gold)),
            "multilingual_e5_dense": metrics(ranks_from_scores(Sb, gold)),
            "hybrid_rrf": metrics(ranks_from_scores(Sc, gold)),
            "examples": [dict(query=Q[j], gold=D[j][:120], top1_dense=D[int(np.argmax(Sb[j]))][:120]) for j in range(5)],
        }
        print(f"  {name:9s} {qname:15s} " + "  ".join(f"{k}: R@1={v['recall_at_1']:.3f} R@10={v['recall_at_10']:.3f}"
                                                for k, v in res[qname].items() if k != "examples"), flush=True)
    res["n_candidates"] = len(idx)
    return res

def main():
    t0 = time.time()
    enc = E5(threads=2)
    d = rd("diseases")
    d = d[(d.definition_en != "") & (d.term_hi != "")]
    s = rd("symptoms")
    s = s[(s.term_sa_iast != "") & (s.gloss_en != "")]
    out = {
        "diseases": run_task("diseases", (d.name_en + ". " + d.definition_en).tolist(), d.term_hi.tolist(),
                             (d.name_en_hi + "। " + d.definition_hi).tolist() if "definition_hi" in d else d.name_en_hi.tolist(), enc),
        "symptoms": run_task("symptoms", s.gloss_en.tolist(), s.term_hi.tolist(), s.gloss_hi.tolist(), enc),
    }
    out["note"] = ("Q-text queries are machine translations of the English side, so they measure cross-lingual alignment of the "
                   "retriever (bitext retrieval), not independent user queries. Q-term queries are independent Sanskrit/Hindi headwords.")
    out["seconds"] = round(time.time() - t0, 1)
    (REP / "E5_crosslingual_retrieval.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    # figure
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    for ax, task in zip(axes, ["diseases", "symptoms"]):
        labels, vals = [], []
        for q in ["hindi_headword", "hindi_text"]:
            for m in ["transliteration_char_tfidf", "multilingual_e5_dense", "hybrid_rrf"]:
                labels.append(f"{q.replace('hindi_', '')}\n{m.split('_')[0]}"); vals.append(out[task][q][m]["recall_at_10"])
        ax.bar(range(len(vals)), vals, color=["#9bb8ad", "#3b7d6e", "#1f4f45"] * 2)
        ax.set_xticks(range(len(vals))); ax.set_xticklabels(labels, fontsize=7); ax.set_ylim(0, 1)
        ax.set_title(f"{task}: Hindi query → English record (Recall@10, {out[task]['n_candidates']} candidates)", fontsize=9)
        ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(FIG / "E5_crosslingual_recall10.png", dpi=130); plt.close(fig)
    print(json.dumps({t: {q: {m: round(v["recall_at_10"], 3) for m, v in out[t][q].items() if m != "examples"}
                          for q in ["hindi_headword", "hindi_text"]} for t in ["diseases", "symptoms"]}, indent=1))

if __name__ == "__main__":
    main()
