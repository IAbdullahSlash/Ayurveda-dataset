#!/usr/bin/env python3
"""
Stage 26 - Model upgrades measured against the original experiments on IDENTICAL rows and folds.

  E2c+  herb indications: original pharmacodynamic features  +  phytochemical activity profile (Dr. Duke: how many
        of the plant's chemicals carry each reported activity, log-scaled, top 300 activities)  +  plant family
  E1+   text tasks (E1a organ system, E1b doṣa from masked text, E1c Hindi): TF-IDF  vs  multilingual-e5 sentence
        embeddings  vs  both concatenated, all with logistic regression; rows restricted to NAMASTE definitions so the
        comparison with stage 07 is like-for-like.  A second run adds the WHO definitions filled in by stage 25
        (more training data) and reports it separately.
Output: reports/ml/E2c_plus.json, reports/ml/E1_plus.json
"""
import json, sys
from collections import Counter
from importlib import import_module
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
ml = import_module("07_ml")
xl = import_module("10_crosslingual")
from lib.ml_utils import tabular_zoo, evaluate_cv, SEED
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import normalize, MaxAbsScaler, OneHotEncoder
from lib.herb_features import HerbFeatures
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports/ml"
rd = ml.rd

def chem_features(h):
    hp, pa = rd("herb_phytochemicals"), rd("phytochemical_activities")
    act = pa.groupby("chemical").activity.apply(set)
    top = [a for a, _ in Counter(a for s in act for a in s).most_common(300)]
    ai = {a: i for i, a in enumerate(top)}
    idx = {hid: i for i, hid in enumerate(h.herb_id)}
    F = np.zeros((len(h), len(top)))
    for hid, ch in zip(hp.herb_id, hp.chemical):
        if hid in idx:
            for a in act.get(ch, ()):
                if a in ai:
                    F[idx[hid], ai[a]] += 1
    F = np.log1p(F)
    return np.hstack([F, (F.sum(1, keepdims=True) > 0).astype(float)]), len(top)

def e2c_plus():
    h = rd("herbs")
    h = h[(h.rasa != "") & (h.virya != "") & (~h.virya.str.contains(";"))].copy().reset_index(drop=True)
    use=("rasa", "guna", "vipaka", "virya", "dosha_pacify", "dosha_aggravate", "parts")
    Xc, n_act = chem_features(h)
    frame=h.copy()
    chemistry_columns=[f"chemistry_{i}" for i in range(n_act)]
    frame=pd.concat([frame,pd.DataFrame(Xc[:,:n_act],columns=chemistry_columns)],axis=1)
    frame["has_chemistry"]=Xc[:,-1]
    ind = Counter(x for s in h.indications_sa_ascii for x in s.split("; ") if x)
    top = [k for k, _ in ind.most_common(12)]
    Y = pd.DataFrame({k: h.indications_sa_ascii.map(lambda s, k=k: int(k in s.split("; "))) for k in top})
    names = ["Logistic Regression", "Random Forest", "LightGBM", "XGBoost", "Dummy (majority)"]
    out = {}
    from sklearn.decomposition import TruncatedSVD
    base=("herb",HerbFeatures(use=use),list(h.columns))
    family=("family",OneHotEncoder(handle_unknown="ignore",sparse_output=False),["family"])
    presence=("present","passthrough",["has_chemistry"])
    variants = [
        ("original features",HerbFeatures(use=use)),
        ("+ chemistry + family",ColumnTransformer([base,("chemistry","passthrough",chemistry_columns),family,presence])),
        ("+ chemistry compressed to 20 components",ColumnTransformer([
            base,("chemistry",make_pipeline(TruncatedSVD(20,random_state=SEED),MaxAbsScaler()),chemistry_columns),presence]))]
    for label, preprocessor in variants:
        X=frame
        zoo = {k: v for k, v in tabular_zoo(2).items() if k in names}
        rows = []
        for lab in top:
            y = Y[lab].values
            res, *_ = evaluate_cv(zoo, X, y, n_splits=5, n_repeats=2, topk=(),
                                  preprocessor=preprocessor, sample_ids=h.herb_id.tolist())
            res["label"] = lab; rows.append(res)
        allr = pd.concat(rows)
        summ = allr.groupby("model")[["accuracy_mean", "macro_f1_mean", "roc_auc_ovr_mean"]].mean().sort_values("macro_f1_mean", ascending=False)
        out[label] = summ.round(4).reset_index().to_dict(orient="records")
        print(f"[E2c+] {label}: features={X.shape[1]}\n{summ.round(3)}", flush=True)
    out["n_herbs"] = len(h); out["herbs_with_chemistry"] = int((Xc[:, :n_act].sum(1) > 0).sum()); out["labels"] = top
    (REP / "E2c_plus.json").write_text(json.dumps(out, indent=2, default=float))
    return out

def e1_plus(enc):
    d = rd("diseases")
    out = {}
    lr = lambda: LogisticRegression(max_iter=4000, C=8.0, class_weight="balanced")
    def run(tag, texts, y):
        Xe = enc.encode(texts, "passage: ")
        frame = pd.DataFrame(normalize(Xe) * 3.0)
        frame["text"] = texts
        embedding_columns = list(range(Xe.shape[1]))
        variants = [
            ("TF-IDF + LR (stage 07)", np.asarray(texts, dtype=object), ml.text_preprocessor()),
            ("e5 embeddings + LR", Xe, None),
            ("TF-IDF + e5 + LR", frame, ColumnTransformer([
                ("text", ml.text_preprocessor(), "text"),
                ("embeddings", "passthrough", embedding_columns)], sparse_threshold=1.0))]
        zoo_rows = {}
        for name, X, preprocessor in variants:
            res, *_ = evaluate_cv({name: lr()}, X, y, n_splits=5, n_repeats=1, topk=(), preprocessor=preprocessor)
            zoo_rows[name] = {k: round(float(res.iloc[0][k]), 4) for k in ("accuracy_mean", "macro_f1_mean", "roc_auc_ovr_mean") if k in res}
        out[tag] = dict(n=len(texts), classes=len(set(y)), results=zoo_rows)
        print(f"[E1+] {tag} n={len(texts)}: " + "; ".join(f"{k} F1={v['macro_f1_mean']:.3f}" for k, v in zoo_rows.items()), flush=True)
    for scope, mask in (("NAMASTE definitions (as stage 07)", d.definition_source == "NAMASTE" if "definition_source" in d else d.definition_en != ""),
                        ("+ WHO-filled definitions (stage 25)", d.definition_en != "")):
        x = d[mask & (d.definition_en.str.len() >= 30)].copy()
        vc = x.system_code.value_counts(); a = x[x.system_code.isin(vc[vc >= 20].index)]
        run(f"E1a organ system | {scope}", (a.name_en + " . " + a.definition_en).tolist(), ml.lab(a.system_code))
        b = x[(x.dosha_source == "term") & (x.dosha_label != "unspecified")]
        vb = b.dosha_label.value_counts(); b = b[b.dosha_label.isin(vb[vb >= 15].index)]
        run(f"E1b doṣa from masked text | {scope}", b.definition_en.map(lambda t: ml.DOSHA_MASK.sub(" ", t)).tolist(), ml.lab(b.dosha_label))
        if scope.startswith("NAMASTE"):
            hh = a[a.definition_hi.str.len() > 10]
            run(f"E1c Hindi (MT) | {scope}", (hh.name_en_hi + " । " + hh.definition_hi).tolist(), ml.lab(hh.system_code))
    (REP / "E1_plus.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out

def main(part="all"):
    if part in ("all", "e2c"):
        e2c_plus()
    if part in ("all", "e1"):
        e1_plus(xl.E5(threads=2))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
