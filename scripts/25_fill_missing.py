#!/usr/bin/env python3
"""
Stage 25 - Fill gaps with clearly flagged, source-traceable additions (never silently overwriting curated values).

  1. Disorder definitions: disorders without a NAMASTE definition get the WHO (2022) definition of the linked WHO term,
     with its Hindi translation; `definition_source` says which source each definition comes from.
  2. WHO symptom lists -> disease_symptom_who: WHO definitions of the form "A disorder characterized by some or all
     the following signs and symptoms: a; b; c" are split and each sign mapped to the SAT symptom lexicon
     (exact gloss, else the shortest entries containing every word).
  3. disease_symptom_inferred: disorders that still have no symptom profile inherit their parent's (flagged).
  4. dosha_suggestions: a text classifier trained on disorders whose doṣa is stated in the term suggests the doṣa
     for 'unspecified' disorders, with confidence and margin (for expert review; diseases.dosha_label is unchanged).
  5. herb_property_suggestions: vīrya suggested for herbs without a recorded vīrya from plant family and
     phytochemistry - written only if cross-validated macro-F1 >= 0.65.
Output: the tables above + reports/fill_missing_report.json
"""
import json, re, sys
from collections import Counter, defaultdict
from importlib import import_module
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
cr = import_module("14_case_reports")
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import f1_score, accuracy_score

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)
SEED = 42
SIGNS = re.compile(r"(?:signs and symptoms|following symptoms|following features|characterized by)\s*:\s*(.+)$", re.I | re.S)

def gloss_index(S):
    exact, entries = defaultdict(set), []
    for sid, g in zip(S.symptom_id, S.gloss_en):
        for part in re.split(r"[/;]", g):
            w = cr.norm_words(part)
            if 1 <= len(w) <= 8:
                exact[tuple(w)].add(sid); entries.append((sid, set(w), len(w)))
    return exact, entries

def map_sign(sign, exact, entries):
    for alt in [sign] + [a for a in re.split(r"/", sign) if a.strip()]:
        w = cr.norm_words(alt)
        if not w:
            continue
        if tuple(w) in exact:
            return exact[tuple(w)], "exact_gloss"
    w = set(cr.norm_words(sign))
    if not w or len(w) > 6:
        return set(), ""
    cand = sorted((n, sid) for sid, ws, n in entries if w <= ws)[:3]
    return {sid for _, sid in cand}, ("all_words_entry" if cand else "")

def postedit(df, en_col, hi_col, method_col, rules):
    """deterministic post-edits for systematic machine-translation errors (curation/mt_postedit_rules.csv)"""
    n = 0
    for r in rules.itertuples():
        m = (df[en_col].str.contains(r.en_regex, case=False, regex=True) & ~df[en_col].str.contains(r.en_exclude_regex, case=False, regex=True)
             & df[hi_col].str.contains(r.hi_wrong_regex, regex=True))
        if m.any():
            df.loc[m, hi_col] = df.loc[m, hi_col].str.replace(r.hi_wrong_regex, r.hi_right, regex=True)
            if method_col in df:
                df.loc[m & ~df[method_col].str.contains("post-edited"), method_col] += " + post-edited (mt_postedit_rules)"
            n += int(m.sum())
    return n

def main():
    rep = {}
    D, T, S = rd("diseases"), rd("terminology"), rd("symptoms")
    rules = pd.read_csv(ROOT / "curation/mt_postedit_rules.csv", keep_default_na=False)
    n_s = postedit(S, "gloss_en", "gloss_hi", "gloss_hi_method", rules)
    n_d = postedit(D, "definition_en", "definition_hi", "definition_hi_method", rules)
    S.to_csv(P / "symptoms.csv", index=False); S.to_parquet(P / "symptoms.parquet", index=False)
    rep["mt_postedits"] = {   # cumulative: rows carrying a post-edit mark from this or an earlier run
        "symptom_glosses": int(S.gloss_hi_method.str.contains("post-edited|rule-corrected").sum()),
        "disorder_definitions": int(D.definition_hi_method.str.contains("post-edited|rule-corrected").sum())}
    who = T.set_index("term_uid")
    # ---- 1. definitions from WHO
    if "definition_source" not in D:                      # idempotent: a re-run never relabels filled rows
        D["definition_source"] = np.where(D.definition_en != "", "NAMASTE", "")
    for c in ("definition_hi", "definition_hi_method", "definition_hi_qe_flags"):
        if c not in D:
            D[c] = ""
    filled = 0
    for i, r in D[(D.definition_en == "") & (D.who_term_id != "")].iterrows():
        uid = "WHO:" + r.who_term_id.split(";")[0]
        if uid in who.index and len(who.at[uid, "definition_en"]) > 15:
            D.at[i, "definition_en"] = who.at[uid, "definition_en"]
            D.at[i, "definition_hi"] = who.at[uid, "definition_hi"] if "definition_hi" in who else ""
            D.at[i, "definition_hi_method"] = (who.at[uid, "definition_hi_method"] if "definition_hi_method" in who else "") + " (WHO term)"
            D.at[i, "definition_hi_qe_flags"] = who.at[uid, "definition_hi_qe_flags"] if "definition_hi_qe_flags" in who else ""
            D.at[i, "definition_source"] = "WHO ITA 2022 (linked term)"
            filled += 1
    D.to_csv(P / "diseases.csv", index=False)
    if (P / "diseases.parquet").exists():
        D.to_parquet(P / "diseases.parquet", index=False)
    rep["definitions_filled_from_WHO"] = int((D.definition_source == "WHO ITA 2022 (linked term)").sum())   # cumulative
    rep["disorders_with_definition"] = {"before": round(float((D.definition_source == "NAMASTE").mean()), 3),
                                        "after": round(float((D.definition_en != "").mean()), 3)}
    # ---- 2. WHO symptom lists -> SAT symptoms
    exact, entries = gloss_index(S)
    rows, n_signs, n_mapped = [], 0, 0
    for r in D[D.who_term_id != ""].itertuples():
        uid = "WHO:" + r.who_term_id.split(";")[0]
        if uid not in who.index:
            continue
        m = SIGNS.search(who.at[uid, "definition_en"])
        if not m:
            continue
        for k, sign in enumerate([x.strip(" .") for x in re.split(r";", m.group(1)) if x.strip(" .")]):
            n_signs += 1
            ids, how = map_sign(sign, exact, entries)
            n_mapped += bool(ids)
            for sid in sorted(ids):
                rows.append(dict(disease_id=r.disease_id, symptom_id=sid, mention_order=k + 1, sign_text_who=sign[:120],
                                 match_method=how, source_id="S3", data_origin="WHO definition sign list mapped to the SAT lexicon"))
    W = pd.DataFrame(rows).drop_duplicates(["disease_id", "symptom_id"])
    W.to_csv(P / "disease_symptom_who.csv", index=False)
    base = rd("disease_symptom")
    had = set(base.disease_id)
    rep["who_sign_lists"] = {"signs": n_signs, "signs_mapped": n_mapped, "edges": len(W),
                             "disorders": int(W.disease_id.nunique()), "new_disorders_with_a_profile": int(len(set(W.disease_id) - had))}
    # ---- 3. inherit the parent's profile when a disorder still has none
    prof = base.groupby("disease_id").symptom_id.apply(set).to_dict()
    for d, g in W.groupby("disease_id"):
        prof.setdefault(d, set()).update(g.symptom_id)
    parent = dict(zip(D.disease_id, D.parent_disease_id))
    inh = []
    clinical = set(D[~D.system_code.isin(["U", "V", "W"]) & ~D.term_iast.str.contains("pūrvarūp")].disease_id)
    for d in D.disease_id:
        if d in prof or d not in clinical:          # healthy states, interventions and prodromes never inherit
            continue
        cur = parent.get(d, "")
        while cur and cur not in prof:
            cur = parent.get(cur, "")
        if cur:
            for s in sorted(prof[cur]):
                inh.append(dict(disease_id=d, symptom_id=s, inherited_from=cur, source_id="S1",
                                data_origin="inferred: inherited from the nearest ancestor with a profile (flagged)"))
    I = pd.DataFrame(inh)
    I.to_csv(P / "disease_symptom_inferred.csv", index=False)
    rep["inherited_profiles"] = {"disorders": int(I.disease_id.nunique()) if len(I) else 0, "edges": len(I)}
    rep["disorders_with_any_profile"] = {"before": len(had), "after": len(had | set(W.disease_id) | set(I.disease_id if len(I) else []))}
    # ---- 4. doṣa suggestions for 'unspecified' disorders
    txt = (D.name_en + " . " + D.definition_en).str.lower()
    lab = D[(D.dosha_source == "term") & (D.dosha_label != "unspecified") & (D.definition_en.str.len() >= 30)]
    vc = lab.dosha_label.value_counts(); lab = lab[lab.dosha_label.isin(vc[vc >= 15].index)]
    vec_w = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    vec_c = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True)
    Xl = sparse.hstack([vec_w.fit_transform(txt[lab.index]), vec_c.fit_transform(txt[lab.index])]).tocsr()
    y = np.asarray(lab.dosha_label.astype(str).tolist(), dtype=object)     # pandas 3 Arrow strings -> numpy
    clf = LogisticRegression(max_iter=4000, C=8.0, class_weight="balanced")
    oof = cross_val_predict(clf, Xl, y, cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
    cv_f1, cv_acc = f1_score(y, oof, average="macro"), accuracy_score(y, oof)
    clf.fit(Xl, y)
    tgt = D[(D.dosha_label == "unspecified") & (D.definition_en.str.len() >= 30)]
    Xt = sparse.hstack([vec_w.transform(txt[tgt.index]), vec_c.transform(txt[tgt.index])]).tocsr()
    pr = clf.predict_proba(Xt)
    o = np.argsort(-pr, axis=1)
    sug = pd.DataFrame(dict(disease_id=tgt.disease_id.values, term_iast=tgt.term_iast.values,
                            suggested_dosha=clf.classes_[o[:, 0]], confidence=pr[np.arange(len(pr)), o[:, 0]].round(3),
                            second_choice=clf.classes_[o[:, 1]], margin=(pr[np.arange(len(pr)), o[:, 0]] - pr[np.arange(len(pr)), o[:, 1]]).round(3),
                            model=f"TF-IDF word+char + logistic regression (CV macro-F1 {cv_f1:.3f}, accuracy {cv_acc:.3f})",
                            status="model suggestion - not authoritative; confirm with an expert"))
    sug.to_csv(P / "dosha_suggestions.csv", index=False)
    rep["dosha_suggestions"] = {"suggested": len(sug), "cv_macro_f1_on_labelled": round(cv_f1, 3), "cv_accuracy": round(cv_acc, 3),
                                "confidence>=0.6": int((sug.confidence >= 0.6).sum()), "labels": vc[vc >= 15].to_dict()}
    # ---- 5. vīrya suggestions from family + phytochemistry
    H = rd("herbs")
    hp, pa = rd("herb_phytochemicals"), rd("phytochemical_activities")
    act = pa.groupby("chemical").activity.apply(set)
    top_act = Counter(a for s in act for a in s).most_common(300)
    top_act = [a for a, _ in top_act]
    ai = {a: i for i, a in enumerate(top_act)}
    F = np.zeros((len(H), len(top_act)))
    hidx = {h: i for i, h in enumerate(H.herb_id)}
    for h, ch in zip(hp.herb_id, hp.chemical):
        for a in act.get(ch, ()):
            if a in ai and h in hidx:
                F[hidx[h], ai[a]] += 1
    F = np.log1p(F)
    fam = pd.get_dummies(H.family.where(H.family.map(H.family.value_counts()) >= 3, "other")).values.astype(float)
    X = np.hstack([F, fam, (F.sum(1, keepdims=True) > 0)])
    known = (H.virya != "") & (~H.virya.str.contains(";"))
    Xk, yk = X[known.values], np.asarray(H.virya[known].astype(str).tolist(), dtype=object)
    rf = LogisticRegression(max_iter=3000, C=0.5, class_weight="balanced")
    oofv = cross_val_predict(rf, Xk, yk, cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
    f1v = f1_score(yk, oofv, average="macro")
    rep["virya_from_family_and_chemistry"] = {"cv_macro_f1": round(f1v, 3), "n_train": int(known.sum())}
    if f1v >= 0.65:
        rf.fit(Xk, yk)
        miss = H[(H.virya == "") & (X.sum(1) > 0)]
        prv = rf.predict_proba(X[miss.index])
        hs = pd.DataFrame(dict(herb_id=miss.herb_id.values, accepted_name=miss.accepted_name.values,
                               suggested_virya=rf.classes_[prv.argmax(1)], confidence=prv.max(1).round(3),
                               model=f"family + phytochemical activity profile, logistic regression (CV macro-F1 {f1v:.3f})",
                               status="model suggestion - not authoritative; confirm with an expert"))
        hs.to_csv(P / "herb_property_suggestions.csv", index=False)
        rep["virya_from_family_and_chemistry"]["suggested"] = len(hs)
    else:
        rep["virya_from_family_and_chemistry"]["suggested"] = 0
        rep["virya_from_family_and_chemistry"]["note"] = "below the 0.65 macro-F1 bar: no suggestions written"
        (P / "herb_property_suggestions.csv").unlink(missing_ok=True)
    (ROOT / "reports/fill_missing_report.json").write_text(json.dumps(rep, indent=2, default=int))
    print(json.dumps(rep, indent=1, default=int))

if __name__ == "__main__":
    main()
