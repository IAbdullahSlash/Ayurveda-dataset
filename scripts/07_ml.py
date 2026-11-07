#!/usr/bin/env python3
"""
Stage 07 - Machine-learning experiments on AyurKB (pre-processing -> training -> post-processing).

  E1  Clinical text -> diagnosis (REAL NAMASTE definitions)
        E1a organ-system category of the disorder (NAMASTE top-level system)
        E1b doṣa involvement inferred from symptom text with explicit doṣa words MASKED
        E1c same as E1a but trained/tested on the Hindi (machine-translated) definitions  [--bilingual]
  E2  Herb pharmacology (REAL Amidha + SAT herbs)
        E2a vīrya (uṣṇa / śīta) from rasa, guṇa, vipāka, karma, parts, family  vs. classical rasa rule
        E2b doṣa-pacifying profile (V / P / K, multi-label)                   vs. classical vīrya rule
        E2c indication prediction (top indications, multi-label) from pharmacodynamic properties only
  E3  Symptom-based differential diagnosis (HYBRID: cases simulated from the real disease-symptom graph)
        vs. a pure knowledge-base matcher (cosine to disease profile, i.e. a classical expert system)
  E4  Prakṛti (constitution) classification (SYNTHETIC cohort generated from WHO ITA-2.8.3-2.8.5 traits)
        vs. classical questionnaire scoring; with calibration + abstain-and-refer post-processing
Each model is evaluated with repeated stratified k-fold CV; results -> reports/ml/, figures -> reports/figures/
"""
import argparse, json, re, sys, time
from collections import Counter
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse
import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.herb_features import HerbFeatures
from lib.ml_utils import (tabular_zoo, text_zoo, evaluate_cv, selective_curve, plot_bars, plot_confusion,
                          plot_selective, ece, SEED)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline, make_pipeline, FeatureUnion
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import f1_score, roc_auc_score, accuracy_score, classification_report
from sklearn.inspection import permutation_importance
from sklearn.base import clone

ROOT = Path(__file__).resolve().parents[1]
P, REP, FIG, MOD = ROOT / "data/processed", ROOT / "reports/ml", ROOT / "reports/figures", ROOT / "models/trained"
for d in (REP, FIG, MOD):
    d.mkdir(parents=True, exist_ok=True)
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)
# pandas 3 returns Arrow-backed string arrays from .values; scikit-learn indexing needs plain numpy
lab = lambda s: np.asarray(s.astype(str).tolist(), dtype=object)

def save_result(name, res, extra):
    res.to_csv(REP / f"{name}_cv_results.csv", index=False)
    (REP / f"{name}.json").write_text(json.dumps({"results": res.to_dict(orient="records"), **extra}, indent=2, default=float), encoding="utf-8")

# ============================================================================== E1 text -> diagnosis
DOSHA_MASK = re.compile(r"\b(v[aā]t\w*|pitt\w*|paitt\w*|kaph\w*|[sś][lḷ]e[sṣ]m\w*|[sś]lai[sṣ]m\w*|sann?ip[aā]t\w*|"
                        r"s[aā]nnip[aā]t\w*|trido[sṣ]\w*|v[aā]y[uū]\w*|d[oō][sṣ]a\w*|prāṇa\w*|udāna\w*|vyāna\w*|apāna\w*|samāna\w*)",
                        re.I)

def text_preprocessor():
    w = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=30000)
    c = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True, max_features=40000)
    return FeatureUnion([("word", w), ("character", c)])

def text_features(texts, fit=None):
    """Full-corpus features for final fitting only; CV must use text_preprocessor."""
    return text_preprocessor().fit_transform(texts)

def e1(bilingual=False):
    d = rd("diseases")
    d = d[d.definition_en.str.len() >= 30].copy()
    out = {}
    # ---- E1a organ-system category
    vc = d.system_code.value_counts()
    keep = vc[vc >= 20].index
    a = d[d.system_code.isin(keep)].copy()
    names = a.drop_duplicates("system_code").set_index("system_code").system_name_en.to_dict()
    texts = (a.name_en + " . " + a.definition_en).tolist()
    X = np.asarray(texts, dtype=object)
    print(f"[E1a] organ-system from text: n={len(a)} classes={a.system_code.nunique()} inputs={len(X)}")
    res, oof, cls, yi = evaluate_cv(text_zoo(), X, lab(a.system_code), sample_ids=lab(a.disease_id), n_splits=5, n_repeats=1, preprocessor=text_preprocessor())
    best = res.iloc[0].model
    plot_bars(res, "macro_f1", "E1a  NAMASTE disorder -> organ-system category (text, 5-fold CV)", FIG / "E1a_models_macroF1.png")
    plot_confusion(yi, oof[best].argmax(1), [f"{c}:{names.get(c, '')[:18]}" for c in cls], f"E1a confusion ({best})", FIG / "E1a_confusion.png")
    save_result("E1a_system_from_text", res, dict(n=len(a), classes={c: names.get(c, "") for c in cls}, best_model=best,
                class_counts=a.system_code.value_counts().to_dict(), data_origin="real (NAMASTE S1)"))
    out["E1a"] = res.iloc[0].to_dict()
    # ---- E1b doṣa involvement from MASKED symptom text
    b = d[(d.dosha_source == "term") & (d.dosha_label != "unspecified")].copy()
    vc = b.dosha_label.value_counts(); b = b[b.dosha_label.isin(vc[vc >= 15].index)]
    masked = b.definition_en.map(lambda t: DOSHA_MASK.sub(" ", t))
    X = np.asarray(masked.tolist(), dtype=object)
    print(f"[E1b] dosha from masked symptom text: n={len(b)} classes={b.dosha_label.value_counts().to_dict()}")
    res, oof, cls, yi = evaluate_cv(text_zoo(), X, lab(b.dosha_label), sample_ids=lab(b.disease_id), n_splits=5, n_repeats=1, preprocessor=text_preprocessor())
    plot_bars(res, "macro_f1", "E1b  doṣa involvement from symptom text (doṣa words masked)", FIG / "E1b_models_macroF1.png")
    plot_confusion(yi, oof[res.iloc[0].model].argmax(1), list(cls), f"E1b confusion ({res.iloc[0].model})", FIG / "E1b_confusion.png")
    save_result("E1b_dosha_from_masked_text", res, dict(n=len(b), class_counts=b.dosha_label.value_counts().to_dict(),
                masking_regex=DOSHA_MASK.pattern, data_origin="real (NAMASTE S1)"))
    out["E1b"] = res.iloc[0].to_dict()
    if bilingual:
        out.update(e1c())
    return out

def e1c():
    """E1c: the same organ-system task trained/tested on English vs Hindi (machine-translated) text."""
    out = {}
    d = rd("diseases")
    d = d[d.definition_en.str.len() >= 30].copy()
    vc = d.system_code.value_counts()
    a = d[d.system_code.isin(vc[vc >= 20].index)].copy()
    if "definition_hi" in d.columns:
        h = a.copy()
        h = h[h.definition_hi.str.len() > 10]
        Xh = np.asarray((h.name_en_hi + " । " + h.definition_hi).tolist(), dtype=object)
        Xe = np.asarray((h.name_en + " . " + h.definition_en).tolist(), dtype=object)
        print(f"[E1c] bilingual: n={len(h)}")
        zoo = {k: v for k, v in text_zoo().items() if k in ("Logistic Regression", "Linear SVM (calibrated)", "Multinomial Naive Bayes", "LightGBM", "Dummy (majority)")}
        rh, *_ = evaluate_cv(zoo, Xh, lab(h.system_code), sample_ids=lab(h.disease_id), n_splits=5, n_repeats=1, preprocessor=text_preprocessor())
        re_, *_ = evaluate_cv(zoo, Xe, lab(h.system_code), sample_ids=lab(h.disease_id), n_splits=5, n_repeats=1, preprocessor=text_preprocessor())
        rh["language"], re_["language"] = "Hindi (MT)", "English"
        both = pd.concat([re_, rh])
        save_result("E1c_bilingual_system_from_text", both, dict(n=len(h), data_origin="real text; Hindi = NLLB machine translation"))
        out["E1c"] = both.to_dict(orient="records")
    return out

# ============================================================================== E2 herb pharmacology
HOT_RASA, COLD_RASA = {"Amla", "Lavana", "Katu"}, {"Madhura", "Tikta", "Kashaya"}
DOSHA_KARMA = {"Vatahara", "Pittahara", "Kaphahara"}

def herb_matrix(h, use=("rasa", "guna", "vipaka", "virya", "karma", "parts", "family", "dosha_pacify", "dosha_aggravate"),
                min_count=6):
    cols = {}
    def multi(prefix, series, exclude=()):
        c = Counter(x for s in series for x in s.split("; ") if x and x not in exclude)
        for k, n in c.items():
            if n >= min_count:
                cols[f"{prefix}={k}"] = series.map(lambda s, k=k: int(k in s.split("; ")))
    if "rasa" in use: multi("rasa", h.rasa)
    if "guna" in use: multi("guna", h.guna)
    if "vipaka" in use: multi("vipaka", h.vipaka)
    if "virya" in use: multi("virya", h.virya)
    if "karma" in use: multi("karma", h.karma_actions, exclude=DOSHA_KARMA)
    if "parts" in use: multi("part", h.parts_used)
    if "family" in use: multi("family", h.family)
    if "dosha_pacify" in use: multi("pacify", h.dosha_pacify)
    if "dosha_aggravate" in use: multi("aggravate", h.dosha_aggravate)
    return pd.DataFrame(cols, index=h.index)

def multilabel_eval(X, Y, labels, zoo_names, title, fname, baseline=None, preprocessor=None):
    zoo = {k: v for k, v in tabular_zoo(2).items() if k in zoo_names}
    rows = []
    for lab in labels:
        y = Y[lab].values
        if y.sum() < 10 or (1 - y).sum() < 10:
            continue
        res, oof, cls, yi = evaluate_cv(zoo, X, y, n_splits=5, n_repeats=2, topk=(), preprocessor=preprocessor)
        res["label"] = lab
        if baseline is not None and lab in baseline:
            bp = baseline[lab]
            res = pd.concat([res, pd.DataFrame([{"model": "Classical rule (Ayurvedic theory)", "label": lab,
                                                  "accuracy_mean": accuracy_score(y, bp), "macro_f1_mean": f1_score(y, bp, average="macro"),
                                                  "roc_auc_ovr_mean": roc_auc_score(y, bp)}])])
        rows.append(res)
    allr = pd.concat(rows)
    summ = allr.groupby("model")[["accuracy_mean", "macro_f1_mean", "roc_auc_ovr_mean"]].mean().sort_values("macro_f1_mean", ascending=False)
    summ = summ.reset_index().rename(columns={c: c for c in summ.columns})
    s2 = summ.rename(columns={"accuracy_mean": "accuracy_mean", "macro_f1_mean": "macro_f1_mean"}).copy()
    s2["macro_f1_std"] = 0.0; s2["accuracy_std"] = 0.0
    plot_bars(s2, "macro_f1", title, FIG / f"{fname}_models_macroF1.png", err=False)
    return allr, summ

def e2():
    h = rd("herbs")
    h = h[(h.rasa != "") & (h.virya != "") & (~h.virya.str.contains(";"))].copy()
    out = {}
    # ---- E2a vīrya
    X = h.copy()
    pre = HerbFeatures(use=("rasa", "guna", "vipaka", "karma", "parts", "family"))
    y = lab(h.virya)
    print(f"[E2a] virya: n={len(h)} inputs={len(X)} classes={Counter(y)}")
    res, oof, cls, yi = evaluate_cv(tabular_zoo(2), X, y, n_splits=5, n_repeats=3, topk=(), preprocessor=pre)
    # classical rule baselines
    def rasa_rule(r):
        rs = set(r.split("; ")); hot, cold = len(rs & HOT_RASA), len(rs & COLD_RASA)
        return "Ushna" if (hot > cold or (hot == cold and "Katu" in rs)) else "Sheeta"
    vip_rule = lambda v: "Sheeta" if v == "Madhura" else "Ushna"
    rule_rows = []
    for nm, pred in [("Classical rule: rasa majority (hot vs cold tastes)", h.rasa.map(rasa_rule)),
                     ("Classical rule: vipāka (madhura -> śīta)", h.vipaka.map(vip_rule))]:
        rule_rows.append({"model": nm, "accuracy_mean": accuracy_score(y, pred), "accuracy_std": 0.0,
                          "macro_f1_mean": f1_score(y, pred, average="macro"), "macro_f1_std": 0.0,
                          "balanced_accuracy_mean": float(np.mean([np.mean(pred[y == c] == c) for c in np.unique(y)]))})
    res = pd.concat([res, pd.DataFrame(rule_rows)]).sort_values("macro_f1_mean", ascending=False)
    plot_bars(res, "macro_f1", "E2a  herb vīrya (uṣṇa / śīta) from rasa, guṇa, vipāka, karma (CV)", FIG / "E2a_models_macroF1.png")
    best = [m for m in res.model if m in oof][0]
    # explainability: permutation importance for best tree/linear model on full data
    feat = herb_matrix(h, use=("rasa", "guna", "vipaka", "karma", "parts", "family")).columns.tolist()
    est = clone(tabular_zoo(2)["Logistic Regression"]).fit(herb_matrix(h, use=("rasa", "guna", "vipaka", "karma", "parts", "family")).values.astype(float), np.searchsorted(cls, y))
    coef = sorted(zip(feat, est.coef_[0]), key=lambda t: -abs(t[1]))[:15]
    save_result("E2a_virya", res, dict(n=len(h), features=feat, class_counts=dict(Counter(y)), best_model=best,
                logistic_top_coefficients={k: float(v) for k, v in coef},
                interpretation="positive coefficient -> Ushna (classes sorted: %s)" % list(cls), data_origin="real (Amidha S5)"))
    out["E2a"] = res.iloc[0].to_dict()
    # ---- E2b doṣa-pacifying profile
    X = h.copy()
    pre = HerbFeatures(use=("rasa", "guna", "vipaka", "virya", "karma", "parts", "family"))
    Y = pd.DataFrame({d: h.dosha_pacify.map(lambda s, d=d: int(d in s.split("; "))) for d in ["Vata", "Pitta", "Kapha"]})
    # classical: uṣṇa vīrya pacifies vāta & kapha; śīta vīrya pacifies pitta
    base = {"Vata": (h.virya == "Ushna").astype(int).values, "Kapha": (h.virya == "Ushna").astype(int).values,
            "Pitta": (h.virya == "Sheeta").astype(int).values}
    print(f"[E2b] dosha-pacify multi-label: n={len(h)} prevalence={Y.mean().round(3).to_dict()}")
    names = ["Logistic Regression", "Naive Bayes", "k-Nearest Neighbours", "SVM (RBF)", "Decision Tree", "Random Forest",
             "Extra Trees", "Gradient Boosting (HistGB)", "XGBoost", "LightGBM", "MLP (neural net)", "Dummy (majority)"]
    allr, summ = multilabel_eval(X, Y, ["Vata", "Pitta", "Kapha"], names,
                                 "E2b  doṣa-pacifying profile (mean over V/P/K, CV)", "E2b", baseline=base, preprocessor=pre)
    allr.to_csv(REP / "E2b_dosha_pacify_per_label.csv", index=False)
    (REP / "E2b_dosha_pacify.json").write_text(json.dumps({"summary": summ.to_dict(orient="records"),
                                                           "prevalence": Y.mean().to_dict(), "n": len(h),
                                                           "data_origin": "real (Amidha S5)"}, indent=2, default=float), encoding="utf-8")
    out["E2b"] = summ.iloc[0].to_dict()
    # ---- E2c indications from pharmacodynamic properties only (no karma -> no lexical leakage)
    X = h.copy()
    pre = HerbFeatures(use=("rasa", "guna", "vipaka", "virya", "dosha_pacify", "dosha_aggravate", "parts"))
    ind = Counter(x for s in h.indications_sa_ascii for x in s.split("; ") if x)
    top = [k for k, n in ind.most_common(12)]
    Y = pd.DataFrame({k: h.indications_sa_ascii.map(lambda s, k=k: int(k in s.split("; "))) for k in top})
    print(f"[E2c] indications multi-label: n={len(h)} labels={top}")
    allr, summ = multilabel_eval(X, Y, top, ["Logistic Regression", "Random Forest", "LightGBM", "k-Nearest Neighbours",
                                            "MLP (neural net)", "XGBoost", "Dummy (majority)"],
                                 "E2c  indication prediction from rasa/guṇa/vīrya/vipāka/doṣa (mean over 12 labels)", "E2c", preprocessor=pre)
    allr.to_csv(REP / "E2c_indications_per_label.csv", index=False)
    (REP / "E2c_indications.json").write_text(json.dumps({"summary": summ.to_dict(orient="records"), "labels": top,
                                                          "label_prevalence": Y.mean().to_dict(), "n": len(h),
                                                          "data_origin": "real (Amidha S5)"}, indent=2, default=float), encoding="utf-8")
    out["E2c"] = summ.iloc[0].to_dict()
    return out

# ============================================================================== E3 symptom -> disease
def synonym_groups(sym_df):
    """symptoms whose English glosses share all content words of a short gloss form a near-synonym group
    ('fever' ~ 'high grade fever' ~ 'fever with chills'); used to simulate patients describing a feature differently."""
    stop = {"in", "of", "the", "a", "an", "with", "and", "due", "to", "at", "on", "or", "like", "as", "if", "is"}
    toks = {sid: frozenset(w for w in re.findall(r"[a-z]+", g.lower()) if w not in stop and len(w) > 2)
            for sid, g in zip(sym_df.symptom_id, sym_df.gloss_en)}
    by_word = {}
    for sid, t in toks.items():
        for w in t:
            by_word.setdefault(w, set()).add(sid)
    groups = {}
    for sid, t in toks.items():
        if not t or len(t) > 3:
            continue
        cand = set.intersection(*(by_word[w] for w in t)) - {sid}
        if cand:
            groups[sid] = sorted(cand)
    return groups

def simulate_cases(profiles, sym_freq, n_per=40, noise_lambda=1.0, k_range=(2, 6), p_synonym=0.25, groups=None, rng=None):
    """realistic presentations: 2-6 presenting features (cardinal features more likely), Poisson(noise)
    unrelated complaints, and a share of features reported through a near-synonym."""
    rng = rng or np.random.default_rng(SEED)
    groups = groups or {}
    all_sym = np.array(list(sym_freq)); p = np.array([sym_freq[s] for s in all_sym], float); p /= p.sum()
    rows, labels = [], []
    for dis, syms in profiles.items():
        syms = list(syms); w = 1 / np.sqrt(np.arange(1, len(syms) + 1)); w /= w.sum()
        for _ in range(n_per):
            k = int(rng.integers(k_range[0], min(k_range[1], len(syms)) + 1))
            chosen = set()
            for s in rng.choice(syms, size=k, replace=False, p=w):
                if s in groups and rng.random() < p_synonym:
                    s = groups[s][int(rng.integers(len(groups[s])))]
                chosen.add(s)
            for s in rng.choice(all_sym, size=rng.poisson(noise_lambda), p=p):
                chosen.add(s)
            rows.append(chosen); labels.append(dis)
    return rows, np.array(labels)

def e3():
    ds, dis, sym = rd("disease_symptom"), rd("diseases"), rd("symptoms")
    ds = ds.sort_values(["disease_id", "mention_rank"])
    prof = ds.groupby("disease_id").symptom_id.apply(list)
    prof = prof[prof.map(len) >= 5]
    # remove near-identical profiles (sub-types that share every symptom) - they are indistinguishable by design
    seen, keep = {}, []
    for d, s in prof.items():
        key = frozenset(s)
        if key not in seen:
            seen[key] = d; keep.append(d)
    prof = prof[keep]
    freq = Counter(s for v in prof for s in v)
    groups = synonym_groups(sym)
    name = dis.set_index("disease_id").name_en.to_dict()
    out = {}
    for setting, n_dis, zoo_names in [
        ("E3a_top60", 60, ["Dummy (majority)", "Naive Bayes", "Logistic Regression", "k-Nearest Neighbours", "SVM (RBF)",
                           "Decision Tree", "Random Forest", "Extra Trees", "LightGBM", "XGBoost", "MLP (neural net)"]),
        ("E3b_all", len(prof), ["Naive Bayes", "Logistic Regression", "k-Nearest Neighbours"])]:
        pr = prof.sort_values(key=lambda s: s.map(len), ascending=False).head(n_dis)
        cases, y = simulate_cases(pr.to_dict(), freq, n_per=30 if setting.endswith("all") else 40, groups=groups)
        vocab = sorted({s for c in cases for s in c}); vi = {s: i for i, s in enumerate(vocab)}
        X = sparse.lil_matrix((len(cases), len(vocab)))
        for r, c in enumerate(cases):
            for s in c:
                X[r, vi[s]] = 1
        X = X.tocsr()
        print(f"[{setting}] diseases={len(pr)} cases={len(cases)} symptoms={len(vocab)}")
        zoo = {k: v for k, v in tabular_zoo(len(pr)).items() if k in zoo_names}
        # multi-class boosting builds one tree per class per round: keep the budget proportionate
        for k in ("XGBoost", "LightGBM"):
            if k in zoo:
                zoo[k].set_params(n_estimators=120)
        for k in ("Random Forest", "Extra Trees"):
            if k in zoo:
                zoo[k].set_params(n_estimators=200)
        if setting.endswith("all"):
            # ~900 classes: multinomial LR on the very sparse symptom matrix is cheap (cost ~ nnz x classes);
            # one-vs-rest SGD / an MLP output layer of this width are not, so they run only in E3a
            zoo["Logistic Regression"].set_params(max_iter=500, class_weight=None)
        res, oof, cls, yi = evaluate_cv(zoo, X, y, n_splits=3 if setting.endswith("all") else 5, n_repeats=1, topk=(3, 5))
        # knowledge-based expert system: cosine similarity of the case to each disease's IDF-weighted profile
        dfc = Counter(s for v in pr for s in set(v))
        idf = np.log(len(pr) / np.array([dfc.get(vocab[j], 0) or 1 for j in range(len(vocab))])) + 1
        D = np.zeros((len(cls), len(vocab)), dtype=np.float32)
        for i, dname in enumerate(cls):
            for s in pr[dname]:
                if s in vi: D[i, vi[s]] = idf[vi[s]]
        Xd = sparse.csr_matrix(X.multiply(idf.astype(np.float32)))          # stays sparse (E3b is large)
        xn = np.sqrt(np.asarray(Xd.multiply(Xd).sum(1))).ravel()
        sim = np.asarray(Xd @ D.T) / (xn[:, None] * np.linalg.norm(D, axis=1)[None, :] + 1e-9)
        order = np.argsort(-sim, 1)
        kb = {"model": "Knowledge-base matcher (IDF-cosine, no training)",
              "accuracy_mean": float(np.mean(order[:, 0] == yi)), "accuracy_std": 0.0,
              "top3_accuracy_mean": float(np.mean([yi[i] in order[i, :3] for i in range(len(yi))])),
              "top5_accuracy_mean": float(np.mean([yi[i] in order[i, :5] for i in range(len(yi))])),
              "macro_f1_mean": f1_score(yi, order[:, 0], average="macro"), "macro_f1_std": 0.0}
        res = pd.concat([res, pd.DataFrame([kb])]).sort_values("accuracy_mean", ascending=False)
        plot_bars(res, "accuracy", f"{setting}: symptom-set -> disease, top-1 accuracy ({len(pr)} disorders, simulated cases)",
                  FIG / f"{setting}_models_top1.png")
        # robustness: accuracy vs noise for NB and KB matcher
        rob = []
        if setting == "E3a_top60":
            from sklearn.naive_bayes import BernoulliNB
            nb = BernoulliNB().fit(X, yi)
            for lam in [0.0, 0.5, 1.0, 2.0, 3.0, 4.0]:
                ct, yt = simulate_cases(pr.to_dict(), freq, n_per=15, noise_lambda=lam, groups=groups, rng=np.random.default_rng(7))
                Xt = sparse.lil_matrix((len(ct), len(vocab)))
                for r, c in enumerate(ct):
                    for s in c:
                        if s in vi: Xt[r, vi[s]] = 1
                Xt = Xt.tocsr(); yti = np.searchsorted(cls, yt)
                Xtd = sparse.csr_matrix(Xt.multiply(idf.astype(np.float32)))
                tn = np.sqrt(np.asarray(Xtd.multiply(Xtd).sum(1))).ravel()
                st = np.asarray(Xtd @ D.T) / (tn[:, None] * np.linalg.norm(D, axis=1)[None, :] + 1e-9)
                rob.append(dict(noise_lambda=lam, naive_bayes_top1=float(np.mean(nb.predict(Xt) == yti)),
                                kb_matcher_top1=float(np.mean(st.argmax(1) == yti))))
            joblib.dump({"model": nb, "vocab": vocab, "classes": list(cls)}, MOD / "E3_symptom_to_disease_naive_bayes.joblib")
        save_result(setting, res, dict(n_diseases=len(pr), n_cases=len(cases), n_symptoms=len(vocab),
                    simulation=dict(presenting_features="2-6, cardinal features weighted 1/sqrt(rank)", unrelated_complaints="Poisson(1.0)",
                                    synonym_substitution=0.25, synonym_groups=len(groups)),
                    diseases={d: name.get(d, "") for d in cls[:80]}, noise_robustness=rob,
                    data_origin="hybrid: real NAMASTE disease-symptom graph, simulated patient presentations"))
        out[setting] = res.iloc[0].to_dict()
    return out

# ============================================================================== E4 prakṛti
TYPES = {"V": (1, 0, 0), "P": (0, 1, 0), "K": (0, 0, 1), "VP": (1, 1, 0), "PK": (0, 1, 1), "VK": (1, 0, 1), "VPK": (1, 1, 1)}
PREV = {"V": .12, "P": .12, "K": .12, "VP": .20, "PK": .17, "VK": .17, "VPK": .10}

def label_from_shares(s, single_gap=0.15, dual_gap=0.10):
    o = np.argsort(-s); a, b, c = s[o]
    if a - b > single_gap:
        return "VPK"[o[0]]
    if b - c > dual_gap:
        return "".join(sorted("VPK"[o[0]] + "VPK"[o[1]], key="VPK".index))
    return "VPK"

def simulate_prakriti(q, n=3000, careless=0.05, missing=0.03, gamma=2.2, seed=SEED):
    rng = np.random.default_rng(seed)
    types = rng.choice(list(PREV), size=n, p=list(PREV.values()))
    rows = []
    for i, t in enumerate(types):
        alpha = np.array(TYPES[t], float) * 6 + 1.5
        s = rng.dirichlet(alpha)
        rec = {"person_id": f"PRK-{i+1:05d}", "latent_vata": s[0], "latent_pitta": s[1], "latent_kapha": s[2],
               "prakriti_label": label_from_shares(s)}
        careless_resp = rng.random() < careless
        for it in q.itertuples():
            if rng.random() < missing:
                rec[it.item_id] = np.nan; continue
            pr = s ** gamma; pr /= pr.sum()
            pr = it.reliability * pr + (1 - it.reliability) / 3
            if careless_resp:
                pr = np.ones(3) / 3
            rec[it.item_id] = "VPK"[rng.choice(3, p=pr)]
        rec["age"] = int(np.clip(rng.normal(38, 13), 18, 85))
        rec["sex"] = rng.choice(["F", "M"])
        rec["bmi"] = round(float(np.clip(rng.normal(22 + 6 * (s[2] - s[0]), 2.6), 14, 42)), 1)
        rows.append(rec)
    return pd.DataFrame(rows)

def e4():
    q = pd.read_csv(ROOT / "curation/prakriti_questionnaire.csv", keep_default_na=False)
    df = simulate_prakriti(q)
    df["data_origin"] = "synthetic (simulated from WHO ITA-2.8.3-2.8.5 trait definitions)"
    df.to_csv(P / "prakriti_synthetic_cohort.csv", index=False)
    items = q.item_id.tolist()
    y = lab(df.prakriti_label)
    pre = ColumnTransformer([
        ("items", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="missing")),
                            ("oh", OneHotEncoder(handle_unknown="ignore"))]), items),
        ("sex", OneHotEncoder(handle_unknown="ignore"), ["sex"]),
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), ["age", "bmi"])])
    pre.set_params(sparse_threshold=0)
    development, holdout = train_test_split(np.arange(len(df)), test_size=0.25, stratify=y, random_state=SEED)
    final_df, final_y = df.iloc[holdout].copy(), y[holdout]
    df, y = df.iloc[development].copy(), y[development]
    X = df[items + ["sex", "age", "bmi"]]
    print(f"[E4] prakriti: n={len(df)} inputs={len(X)} classes={Counter(y)}")
    res, oof, cls, yi = evaluate_cv(tabular_zoo(len(set(y)), binary_features=True), X, y, n_splits=5, n_repeats=2, preprocessor=pre, sample_ids=lab(df.person_id))
    # classical questionnaire scoring = share of V/P/K answers -> same labelling rule
    cnt = np.stack([(df[items] == d).sum(1).values for d in "VPK"], 1).astype(float)
    sh = cnt / cnt.sum(1, keepdims=True)
    rule = np.array([label_from_shares(s) for s in sh])
    rule_row = {"model": "Classical questionnaire scoring (count V/P/K answers)", "accuracy_mean": accuracy_score(y, rule),
                "accuracy_std": 0.0, "macro_f1_mean": f1_score(y, rule, average="macro"), "macro_f1_std": 0.0}
    res = pd.concat([res, pd.DataFrame([rule_row])]).sort_values("macro_f1_mean", ascending=False)
    plot_bars(res, "macro_f1", "E4  Prakṛti classification (7 classes, synthetic cohort, CV)", FIG / "E4_models_macroF1.png")
    best = [m for m in res.model if m in oof][0]
    plot_confusion(yi, oof[best].argmax(1), list(cls), f"E4 confusion ({best})", FIG / "E4_confusion.png")
    # ---- post-processing: calibration + abstention, on a held-out split
    Xtr, Xte, ytr, yte = X, final_df[items + ["sex", "age", "bmi"]], yi, np.searchsorted(cls, final_y)
    base_name = best if "Ensemble" not in best else "Logistic Regression"
    raw = make_pipeline(clone(pre), clone(tabular_zoo(7)[base_name])).fit(Xtr, ytr)
    cal = CalibratedClassifierCV(make_pipeline(clone(pre), clone(tabular_zoo(7)[base_name])), method="isotonic", cv=5).fit(Xtr, ytr)
    pr_raw, pr_cal = raw.predict_proba(Xte), cal.predict_proba(Xte)
    post = dict(development_ids=df.person_id.tolist(), holdout_ids=final_df.person_id.tolist(), model=base_name, test_accuracy_raw=float((pr_raw.argmax(1) == yte).mean()),
                test_accuracy_calibrated=float((pr_cal.argmax(1) == yte).mean()),
                ece_raw=ece(yte, pr_raw), ece_calibrated=ece(yte, pr_cal),
                selective_raw=selective_curve(yte, pr_raw), selective_calibrated=selective_curve(yte, pr_cal))
    plot_selective({f"{base_name} (raw)": post["selective_raw"], f"{base_name} (isotonic-calibrated)": post["selective_calibrated"]},
                   "E4  abstain-and-refer: accuracy vs coverage", FIG / "E4_selective_prediction.png")
    # explainability: permutation importance of questionnaire items
    lr = clone(tabular_zoo(7)["Logistic Regression"])
    pipe = make_pipeline(pre, lr).fit(df.loc[:, items + ["sex", "age", "bmi"]].iloc[:2250], y[:2250])
    pi = permutation_importance(pipe, Xte, final_y, n_repeats=5, random_state=SEED, n_jobs=1)
    imp = sorted(zip(items + ["sex", "age", "bmi"], pi.importances_mean), key=lambda t: -t[1])
    qtext = dict(zip(q.item_id, q.question_en))
    post["permutation_importance"] = [{"feature": f, "question": qtext.get(f, f), "importance": float(v)} for f, v in imp]
    joblib.dump({"pipeline": CalibratedClassifierCV(make_pipeline(clone(pre), clone(tabular_zoo(7)[base_name])), method="isotonic", cv=5).fit(
                    df[items + ["sex", "age", "bmi"]], y), "items": items}, MOD / "E4_prakriti_classifier.joblib")
    save_result("E4_prakriti", res, dict(n=len(df), class_counts=dict(Counter(y)), best_model=best, post_processing=post,
                data_origin="synthetic - metrics measure recovery of the generating model, NOT clinical validity"))
    return {"E4": res.iloc[0].to_dict(), "E4_post": {k: v for k, v in post.items() if not k.startswith("selective")}}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", nargs="+", default=["e1", "e2", "e3", "e4"])
    ap.add_argument("--bilingual", action="store_true")
    a = ap.parse_args()
    summary_f = REP / "summary.json"
    summary = json.loads(summary_f.read_text(encoding="utf-8")) if summary_f.exists() else {}
    for e in a.exp:
        t0 = time.time()
        r = {"e1": lambda: e1(a.bilingual), "e1c": e1c, "e2": e2, "e3": e3, "e4": e4}[e]()
        summary.update(r)
        summary_f.write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
        print(f"== {e} done in {time.time()-t0:.0f}s")
