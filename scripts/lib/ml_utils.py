"""
Shared ML machinery: model zoo, repeated stratified cross-validation, metrics, calibration (ECE),
selective prediction (abstain-and-refer curves) and plotting.
"""
import json, time, warnings, hashlib, os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (RandomForestClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier,
                              StackingClassifier, VotingClassifier)
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score, log_loss,
                             top_k_accuracy_score, confusion_matrix)
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold
from sklearn.naive_bayes import BernoulliNB, MultinomialNB, ComplementNB, GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC, LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

warnings.filterwarnings("ignore")
SEED = 42

def tabular_zoo(n_classes, binary_features=True):
    nb = BernoulliNB() if binary_features else GaussianNB()
    zoo = {
        "Dummy (majority)": DummyClassifier(strategy="most_frequent"),
        "Logistic Regression": LogisticRegression(max_iter=3000, C=1.0, class_weight="balanced"),
        "Naive Bayes": nb,
        "k-Nearest Neighbours": KNeighborsClassifier(n_neighbors=9, weights="distance"),
        "SVM (RBF)": SVC(C=2.0, gamma="scale", probability=True, class_weight="balanced", random_state=SEED),
        "Decision Tree": DecisionTreeClassifier(min_samples_leaf=3, class_weight="balanced", random_state=SEED),
        "Random Forest": RandomForestClassifier(n_estimators=400, min_samples_leaf=1, class_weight="balanced_subsample", n_jobs=1, random_state=SEED),
        "Extra Trees": ExtraTreesClassifier(n_estimators=400, class_weight="balanced_subsample", n_jobs=1, random_state=SEED),
        "Gradient Boosting (HistGB)": HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, random_state=SEED),
        "XGBoost": XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.08, subsample=0.9, colsample_bytree=0.8,
                                 tree_method="hist", n_jobs=1, random_state=SEED, verbosity=0),
        "LightGBM": LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=5,
                                   subsample=0.9, colsample_bytree=0.8, n_jobs=1, random_state=SEED, verbose=-1),
        "MLP (neural net)": MLPClassifier(hidden_layer_sizes=(128, 64), alpha=1e-3, max_iter=600, early_stopping=True, random_state=SEED),
    }
    zoo["Soft-Voting Ensemble (LR+RF+LGBM)"] = VotingClassifier(
        [("lr", clone(zoo["Logistic Regression"])), ("rf", clone(zoo["Random Forest"])), ("lgbm", clone(zoo["LightGBM"]))], voting="soft")
    zoo["Stacking Ensemble (LR,RF,SVM -> LR)"] = StackingClassifier(
        [("lr", clone(zoo["Logistic Regression"])), ("rf", clone(zoo["Random Forest"])), ("svm", clone(zoo["SVM (RBF)"]))],
        final_estimator=LogisticRegression(max_iter=3000), cv=3)
    return zoo

def text_zoo():
    return {
        "Dummy (majority)": DummyClassifier(strategy="most_frequent"),
        "Multinomial Naive Bayes": MultinomialNB(alpha=0.1),
        "Complement Naive Bayes": ComplementNB(alpha=0.3),
        "Logistic Regression": LogisticRegression(max_iter=4000, C=8.0, class_weight="balanced"),
        "Linear SVM (calibrated)": CalibratedClassifierCV(LinearSVC(C=0.5, class_weight="balanced"), cv=3),
        "SGD (modified Huber)": SGDClassifier(loss="modified_huber", alpha=1e-4, class_weight="balanced", random_state=SEED),
        "k-Nearest Neighbours (cosine)": KNeighborsClassifier(n_neighbors=7, metric="cosine", weights="distance"),
        "Random Forest": RandomForestClassifier(n_estimators=300, class_weight="balanced_subsample", n_jobs=1, random_state=SEED),
        "LightGBM": LGBMClassifier(n_estimators=250, learning_rate=0.08, num_leaves=31, n_jobs=1, random_state=SEED, verbose=-1),
        "MLP (neural net)": MLPClassifier(hidden_layer_sizes=(256,), alpha=1e-4, max_iter=60, early_stopping=True, random_state=SEED),
    }

def ece(y_true_idx, proba, n_bins=10):
    conf = proba.max(1); pred = proba.argmax(1); acc = (pred == y_true_idx).astype(float)
    bins = np.linspace(0, 1, n_bins + 1); e = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            e += m.mean() * abs(acc[m].mean() - conf[m].mean())
    return float(e)

def evaluate_cv(zoo, X, y, n_splits=5, n_repeats=2, label=None, fit_kw=None, topk=(3,), skip_slow=(), preprocessor=None, sample_ids=None):
    """repeated stratified k-fold; returns per-model mean/std metrics and pooled out-of-fold probabilities."""
    classes = np.unique(y)
    yi = np.searchsorted(classes, y)
    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=SEED)
    splits = list(cv.split(np.zeros(len(y)), yi))
    manifest_dir = os.environ.get("AYURKB_SPLIT_DIR")
    if manifest_dir:
        digest = hashlib.sha256(np.asarray(y, dtype=str).tobytes()).hexdigest()
        manifest = {"label": label, "sample_ids": list(map(str,sample_ids)) if sample_ids is not None else None, "label_sha256": digest, "seed": SEED,
                    "n_splits": n_splits, "n_repeats": n_repeats,
                    "folds": [{"train": tr.tolist(), "test": te.tolist()} for tr, te in splits]}
        directory = Path(manifest_dir)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{digest[:16]}-{n_splits}-{n_repeats}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    rows, oof = [], {}
    for name, model in zoo.items():
        if name in skip_slow:
            continue
        m = {k: [] for k in ["accuracy", "balanced_accuracy", "macro_f1", "weighted_f1", "roc_auc_ovr", "log_loss", "ece", "fit_s"]}
        for k in topk:
            m[f"top{k}_accuracy"] = []
        P = np.zeros((len(y), len(classes)))
        for r, (tr, te) in enumerate(splits):
            est = clone(model)
            t0 = time.time()
            xtr = X.iloc[tr] if hasattr(X, "iloc") else X[tr]
            xte = X.iloc[te] if hasattr(X, "iloc") else X[te]
            if preprocessor is not None:
                transform = clone(preprocessor)
                xtr = transform.fit_transform(xtr, yi[tr])
                xte = transform.transform(xte)
            est.fit(xtr, yi[tr])
            m["fit_s"].append(time.time() - t0)
            if hasattr(est, "predict_proba"):
                pr = est.predict_proba(xte)
                full = np.zeros((len(te), len(classes)))
                full[:, est.classes_.astype(int)] = pr
            else:
                d = est.decision_function(xte); full = np.zeros((len(te), len(classes)))
                full[:, est.classes_.astype(int)] = np.exp(d) / np.exp(d).sum(1, keepdims=True)
            pred = full.argmax(1)
            m["accuracy"].append(accuracy_score(yi[te], pred))
            m["balanced_accuracy"].append(balanced_accuracy_score(yi[te], pred))
            m["macro_f1"].append(f1_score(yi[te], pred, average="macro", zero_division=0))
            m["weighted_f1"].append(f1_score(yi[te], pred, average="weighted", zero_division=0))
            try:
                if len(classes) == 2:
                    m["roc_auc_ovr"].append(roc_auc_score(yi[te], full[:, 1]))
                else:
                    present = np.unique(yi[te])
                    sub = full[:, present]; sub = sub / np.clip(sub.sum(1, keepdims=True), 1e-12, None)
                    m["roc_auc_ovr"].append(roc_auc_score(yi[te], sub, multi_class="ovr", labels=present))
            except Exception:
                pass
            m["log_loss"].append(log_loss(yi[te], np.clip(full, 1e-7, 1), labels=np.arange(len(classes))))
            m["ece"].append(ece(yi[te], full))
            for k in topk:
                if len(classes) > k:
                    m[f"top{k}_accuracy"].append(top_k_accuracy_score(yi[te], full, k=k, labels=np.arange(len(classes))))
            if r < n_splits:            # first repeat -> pooled out-of-fold predictions
                P[te] = full
        row = {"model": name}
        for k, v in m.items():
            if v:
                row[f"{k}_mean"] = float(np.mean(v)); row[f"{k}_std"] = float(np.std(v))
        rows.append(row); oof[name] = P
        print(f"    {name:38s} acc={row['accuracy_mean']:.3f}±{row['accuracy_std']:.3f}  macroF1={row['macro_f1_mean']:.3f}"
              + (f"  AUC={row.get('roc_auc_ovr_mean', float('nan')):.3f}") + f"  ({np.sum(m['fit_s']):.0f}s)", flush=True)
    res = pd.DataFrame(rows).sort_values("macro_f1_mean", ascending=False)
    return res, oof, classes, yi

def selective_curve(yi, proba, steps=11):
    conf = proba.max(1); pred = proba.argmax(1)
    out = []
    for q in np.linspace(0, 0.9, steps):
        thr = np.quantile(conf, q)
        keep = conf >= thr
        out.append(dict(coverage=float(keep.mean()), accuracy=float((pred[keep] == yi[keep]).mean()), threshold=float(thr)))
    return out

def plot_bars(res, metric, title, path, err=True):
    r = res.sort_values(f"{metric}_mean")
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(r) + 1.2))
    ax.barh(r.model, r[f"{metric}_mean"], xerr=r[f"{metric}_std"] if err else None, color="#3b7d6e", alpha=0.85)
    ax.set_xlabel(metric.replace("_", " ")); ax.set_title(title, fontsize=11)
    ax.set_xlim(0, 1.0); ax.grid(axis="x", alpha=0.3)
    for i, v in enumerate(r[f"{metric}_mean"]):
        ax.text(min(v + 0.01, 0.93), i, f"{v:.3f}", va="center", fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)

def plot_confusion(yi, pred, labels, title, path):
    cm = confusion_matrix(yi, pred, labels=np.arange(len(labels)), normalize="true")
    fig, ax = plt.subplots(figsize=(0.55 * len(labels) + 3, 0.55 * len(labels) + 2.5))
    im = ax.imshow(cm, cmap="Greens", vmin=0, vmax=1)
    ax.set_xticks(range(len(labels))); ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=8); ax.set_yticklabels(labels, fontsize=8)
    for i in range(len(labels)):
        for j in range(len(labels)):
            if cm[i, j] >= 0.05:
                ax.text(j, i, f"{cm[i, j]:.2f}", ha="center", va="center", fontsize=6.5, color="white" if cm[i, j] > 0.5 else "black")
    ax.set_xlabel("predicted"); ax.set_ylabel("true"); ax.set_title(title, fontsize=10)
    fig.colorbar(im, fraction=0.046); fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)

def plot_selective(curves, title, path):
    fig, ax = plt.subplots(figsize=(6, 4))
    for name, c in curves.items():
        ax.plot([p["coverage"] for p in c], [p["accuracy"] for p in c], marker="o", ms=3, label=name)
    ax.set_xlabel("coverage (share of cases answered automatically)"); ax.set_ylabel("accuracy on answered cases")
    ax.invert_xaxis(); ax.grid(alpha=0.3); ax.legend(fontsize=7); ax.set_title(title, fontsize=10)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
