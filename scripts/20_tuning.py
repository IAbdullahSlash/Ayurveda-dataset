#!/usr/bin/env python3
"""
Stage 20 - Hyperparameter tuning with NESTED cross-validation (E1a, E2a, E4).

The model zoo in stage 07 uses fixed, untuned hyperparameters (a fair 'out of the box' comparison).  Here each model
family gets a hyperparameter search INSIDE every outer training fold (inner CV), so the outer score estimates generalization of 'model + tuning procedure'.  Default and tuned versions are scored on the SAME outer folds, giving a
paired comparison.  Output: reports/ml/E7_tuning.json, reports/ml/E7_tuning.csv, reports/figures/E7_tuning.png
"""
import json, sys, time, warnings, tempfile
from functools import partial
from importlib import import_module
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import f1_score
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, RepeatedStratifiedKFold, StratifiedKFold
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from scipy.stats import loguniform, randint, wilcoxon

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
ml = import_module("07_ml")
from lib.ml_utils import tabular_zoo, text_zoo, SEED
from lib.herb_features import HerbFeatures

ROOT = Path(__file__).resolve().parents[1]
REP, FIG = ROOT / "reports/ml", ROOT / "reports/figures"
CACHE_DIR = None

def nested(name, X, y, model, space, outer, inner_k=3, n_iter=None, n_jobs=2, preprocessor=None):
    if preprocessor is not None:
        model = Pipeline([("preprocess", clone(preprocessor)), ("model", model)], memory=CACHE_DIR)
        space = {"model__" + key: value for key,value in space.items()}
    yi = np.searchsorted(np.unique(y), y)
    d_scores, t_scores, chosen = [], [], []
    for tr, te in outer.split(np.zeros(len(yi)), yi):
        xtr = X.iloc[tr] if hasattr(X, "iloc") else X[tr]
        xte = X.iloc[te] if hasattr(X, "iloc") else X[te]
        d = clone(model).fit(xtr, yi[tr])
        d_scores.append(f1_score(yi[te], d.predict(xte), average="macro", zero_division=0))
        inner = StratifiedKFold(inner_k, shuffle=True, random_state=SEED)
        if n_iter:
            s = RandomizedSearchCV(clone(model), space, n_iter=n_iter, cv=inner, scoring="f1_macro", n_jobs=n_jobs,
                                   random_state=SEED, refit=True)
        else:
            s = GridSearchCV(clone(model), space, cv=inner, scoring="f1_macro", n_jobs=n_jobs, refit=True)
        s.fit(xtr, yi[tr])
        t_scores.append(f1_score(yi[te], s.predict(xte), average="macro", zero_division=0))
        chosen.append({k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in s.best_params_.items()})
    d_scores, t_scores = np.array(d_scores), np.array(t_scores)
    try:
        p = float(wilcoxon(t_scores, d_scores).pvalue) if np.any(t_scores != d_scores) else 1.0
    except ValueError:
        p = 1.0
    row = dict(model=name, default_macro_f1_mean=d_scores.mean(), default_macro_f1_std=d_scores.std(),
               tuned_macro_f1_mean=t_scores.mean(), tuned_macro_f1_std=t_scores.std(),
               gain=t_scores.mean() - d_scores.mean(), wilcoxon_p=p, n_outer_folds=len(t_scores),
               chosen_params_per_fold=json.dumps(chosen, default=str))
    print(f"    {name:32s} default {row['default_macro_f1_mean']:.3f}±{row['default_macro_f1_std']:.3f}  ->  tuned "
          f"{row['tuned_macro_f1_mean']:.3f}±{row['tuned_macro_f1_std']:.3f}  (gain {row['gain']:+.3f}, p={p:.3f})", flush=True)
    return row

def task_e1a():
    d = ml.rd("diseases"); d = d[d.definition_en.str.len() >= 30]
    vc = d.system_code.value_counts(); a = d[d.system_code.isin(vc[vc >= 20].index)]
    X = np.asarray((a.name_en + " . " + a.definition_en).tolist(), dtype=object); y = ml.lab(a.system_code)
    run = partial(nested, preprocessor=ml.text_preprocessor())
    outer = StratifiedKFold(5, shuffle=True, random_state=SEED)
    z = text_zoo()
    from sklearn.svm import LinearSVC
    return [
        run("Logistic Regression", X, y, z["Logistic Regression"], {"C": [1, 4, 8, 16, 32]}, outer),
        run("Linear SVM", X, y, LinearSVC(C=0.5, class_weight="balanced"), {"C": [0.1, 0.3, 0.5, 1, 3]}, outer),
        run("Complement Naive Bayes", X, y, z["Complement Naive Bayes"], {"alpha": [0.03, 0.1, 0.3, 1.0]}, outer),
        run("SGD (modified Huber)", X, y, z["SGD (modified Huber)"], {"alpha": [1e-5, 3e-5, 1e-4, 3e-4]}, outer),
    ]

def task_e2a():
    h = ml.rd("herbs"); h = h[(h.rasa != "") & (h.virya != "") & (~h.virya.str.contains(";"))]
    X = h.copy(); y = ml.lab(h.virya)
    run = partial(nested, preprocessor=HerbFeatures(use=("rasa", "guna", "vipaka", "karma", "parts", "family")))
    outer = RepeatedStratifiedKFold(n_splits=5, n_repeats=2, random_state=SEED)
    z = tabular_zoo(2)
    return [
        run("Logistic Regression", X, y, z["Logistic Regression"], {"C": loguniform(1e-2, 1e2)}, outer, n_iter=12),
        run("SVM (RBF)", X, y, z["SVM (RBF)"], {"C": loguniform(1e-1, 1e2), "gamma": loguniform(1e-3, 1)}, outer, n_iter=15),
        run("k-Nearest Neighbours", X, y, z["k-Nearest Neighbours"], {"n_neighbors": [3, 5, 7, 9, 15, 21], "weights": ["uniform", "distance"]}, outer),
        run("Random Forest", X, y, z["Random Forest"].set_params(n_estimators=200),
               {"max_features": ["sqrt", "log2", 0.3, 0.5], "min_samples_leaf": [1, 2, 4, 8], "max_depth": [None, 6, 12]}, outer, n_iter=12),
        run("LightGBM", X, y, z["LightGBM"], {"num_leaves": randint(4, 32), "learning_rate": loguniform(0.01, 0.2),
               "n_estimators": randint(100, 500), "min_child_samples": randint(3, 30), "reg_lambda": loguniform(1e-3, 10)}, outer, n_iter=15),
    ]

def task_e4():
    q = pd.read_csv(ROOT / "curation/prakriti_questionnaire.csv", keep_default_na=False)
    df = pd.read_csv(ml.P / "prakriti_synthetic_cohort.csv", keep_default_na=False)
    items = q.item_id.tolist()
    for c in items:
        df[c] = df[c].replace("", np.nan)
    df["age"] = pd.to_numeric(df.age, errors="coerce"); df["bmi"] = pd.to_numeric(df.bmi, errors="coerce")
    pre = ColumnTransformer([
        ("items", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="missing")), ("oh", OneHotEncoder(handle_unknown="ignore"))]), items),
        ("sex", OneHotEncoder(handle_unknown="ignore"), ["sex"]),
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), ["age", "bmi"])])
    pre.set_params(sparse_threshold=0)
    X = df[items + ["sex", "age", "bmi"]]
    run = partial(nested, preprocessor=pre)
    y = ml.lab(df.prakriti_label)
    outer = StratifiedKFold(5, shuffle=True, random_state=SEED)
    z = tabular_zoo(7)
    return [
        run("Logistic Regression", X, y, z["Logistic Regression"], {"C": loguniform(1e-2, 1e2)}, outer, n_iter=10),
        run("Random Forest", X, y, z["Random Forest"].set_params(n_estimators=200),
               {"max_features": ["sqrt", 0.2, 0.4], "min_samples_leaf": [1, 3, 6], "max_depth": [None, 10, 20]}, outer, n_iter=8),
        run("LightGBM", X, y, z["LightGBM"], {"num_leaves": randint(7, 63), "learning_rate": loguniform(0.02, 0.2),
               "n_estimators": randint(100, 400), "min_child_samples": randint(5, 40)}, outer, n_iter=8),
        run("MLP (neural net)", X, y, z["MLP (neural net)"], {"alpha": loguniform(1e-5, 1e-1),
               "hidden_layer_sizes": [(64,), (128,), (128, 64), (256, 128)]}, outer, n_iter=8),
    ]

def main():
    global CACHE_DIR
    with tempfile.TemporaryDirectory(prefix="ayurkb-nested-") as cache:
        CACHE_DIR = cache
        try:
            return run_tasks()
        finally:
            CACHE_DIR = None

def run_tasks():
    rows = []
    for task, fn in (("E1a organ-system from text", task_e1a), ("E2a herb vīrya", task_e2a), ("E4 prakṛti (synthetic)", task_e4)):
        t0 = time.time(); print(f"[E7] {task}", flush=True)
        for r in fn():
            rows.append({"task": task, **r})
        print(f"    ({time.time() - t0:.0f}s)", flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(REP / "E7_tuning.csv", index=False)
    (REP / "E7_tuning.json").write_text(json.dumps({"results": R.to_dict(orient="records"),
        "method": "nested CV: inner 3-fold grid/random search on macro-F1 inside each outer fold; default vs tuned on identical "
                  "outer folds; transforms fitted inside inner and outer folds. Wilcoxon fold-score p-values are descriptive because CV training sets overlap",
        "outer_cv": {"E1a": "5-fold", "E2a": "5-fold x 2 repeats", "E4": "5-fold"}}, indent=2, default=float), encoding="utf-8")
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 0.42 * len(R) + 1.2))
        lab = (R.task.str.split(" ").str[0] + "  " + R.model).tolist()[::-1]
        yy = np.arange(len(R))
        ax.barh(yy - 0.18, R.default_macro_f1_mean[::-1], 0.34, color="#9aa5b1", label="default (fixed)")
        ax.barh(yy + 0.18, R.tuned_macro_f1_mean[::-1], 0.34, color="#0f8a5f", label="tuned (nested CV)")
        ax.set_yticks(yy, lab, fontsize=8); ax.set_xlabel("macro-F1 (outer folds)"); ax.legend(loc="lower right", frameon=False)
        ax.set_title("E7  hyperparameter tuning: default vs tuned (nested CV)"); ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout(); fig.savefig(FIG / "E7_tuning.png", dpi=150); plt.close(fig)
    except Exception as e:
        print("plot failed:", e)
    print(R[["task", "model", "default_macro_f1_mean", "tuned_macro_f1_mean", "gain", "wilcoxon_p"]].round(3).to_string(index=False))

if __name__ == "__main__":
    main()
