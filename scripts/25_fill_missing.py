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
import argparse, json, re, sys, unicodedata
from collections import Counter, defaultdict
from importlib import import_module
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
cr = import_module("14_case_reports")
from lib.indic import iast_to_deva, iso_to_iast
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

# ------------------------------------------------------------------------------------------------ Hindi post-edits
# Machine-translated Hindi (stage 06) lives in these columns.  Disorder definitions are composed from symptom-level
# glosses; terminology definitions are copied to the derived tables, so every copy is corrected the same way.
MT_COLUMNS = {"symptoms": ("gloss_en", "gloss_hi", "gloss_hi_method"),
              "terminology": ("definition_en", "definition_hi", "definition_hi_method"),
              "therapies": ("definition_en", "definition_hi", "definition_hi_method"),
              "pharmaceutics": ("definition_en", "definition_hi", "definition_hi_method"),
              "diet_lifestyle": ("definition_en", "definition_hi", "definition_hi_method"),
              "diseases": ("definition_en", "definition_hi", "definition_hi_method")}

def mark(df, m, method_col, source):
    if method_col in df:
        df.loc[m & ~df[method_col].str.contains(source, regex=False), method_col] += f" + post-edited ({source})"

def postedit(df, table, en_col, hi_col, method_col, rules):
    """regex post-edits for systematic machine-translation errors (curation/mt_postedit_rules.csv): a rule applies to the
    tables in its `tables` column, to rows whose English matches en_regex and not en_exclude_regex (when given)"""
    n = 0
    for r in rules.itertuples():
        if table not in [t.strip() for t in r.tables.split(";")]:
            continue
        m = df[en_col].str.contains(r.en_regex, case=False, regex=True) & df[hi_col].str.contains(r.hi_wrong_regex, regex=True)
        if r.en_exclude_regex:
            m &= ~df[en_col].str.contains(r.en_exclude_regex, case=False, regex=True)
        if m.any():
            df.loc[m, hi_col] = df.loc[m, hi_col].str.replace(r.hi_wrong_regex, r.hi_right, regex=True)
            mark(df, m, method_col, "mt_postedit_rules")
            n += int(m.sum())
    return n

def item_key(s):
    """English list item -> lookup key; case, diacritics (doṣa = dōṣa), spacing and end punctuation are ignored"""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"\s*/\s*", "/", s)).strip(" .,;:")

def load_item_corrections():
    """curation/mt_item_corrections.csv: reviewed Hindi for English items that the MT model got wrong"""
    f = ROOT / "curation/mt_item_corrections.csv"
    if not f.exists():
        return {}
    c = pd.read_csv(f, keep_default_na=False)
    return {item_key(r.en_item): (r.hi_item, re.compile(r.hi_ok_regex) if r.hi_ok_regex else None) for r in c.itertuples()}

def corrected(en, hi, corr):
    """reviewed Hindi for one English item, or None if there is none or the current Hindi is already acceptable"""
    c = corr.get(item_key(en))
    if not c or not hi.strip():
        return None
    new, ok = c
    return None if (ok and ok.search(hi)) or hi.strip() == new else new

def fix_list(en, hi, corr):
    """'... signs and symptoms: a; b; c.' (WHO style): correct the Hindi item aligned with a corrected English item.
    Used only when the translation kept the list (same number of ';'-separated items on both sides)."""
    if ":" not in en or not hi:
        return hi
    e_items = en.split(":", 1)[1].split(";")
    if not any(item_key(e) in corr for e in e_items):
        return hi
    m = re.search(r"[:ः]\s", hi)          # the Hindi lead-in ends with ':' or a visarga used as a colon
    if not m:
        return hi
    h_items = hi[m.end():].split(";")
    if len(h_items) != len(e_items):
        return hi
    changed = False
    for i, (e, h) in enumerate(zip(e_items, h_items)):
        core = h.strip()
        end = re.search(r"\s*[।.]$", core)
        suffix = end.group(0) if end else ""
        new = corrected(e, core[:len(core) - len(suffix)], corr)
        if new:
            h_items[i] = h[:len(h) - len(h.lstrip())] + new + suffix + h[len(h.rstrip()):]
            changed = True
    return hi[:m.end()] + ";".join(h_items) if changed else hi

def fix_composed(hi, mentions, corr):
    """composed disorder definitions 'लक्षण: i1; ...; in।[ explanation]' (stage 06 builds one item per symptom mention,
    '<Devanagari term> (<Hindi gloss>)'): correct the gloss of items whose English mention has a reviewed translation.
    The split is trusted only if every item with a Sanskrit term starts with that term."""
    head = "लक्षण: "
    if not hi.startswith(head) or not any(item_key(en) in corr for _, en in mentions):
        return hi
    n = len(mentions)
    parts = hi[len(head):].split("; ")
    if len(parts) < n:
        return hi
    last, sep, tail = "; ".join(parts[n - 1:]).partition("।")
    items = parts[:n - 1] + [last]
    if any(dev and not it.startswith(dev) for (dev, _), it in zip(mentions, items)):
        return hi
    changed = False
    for i, ((dev, en), it) in enumerate(zip(mentions, items)):
        if dev and it.startswith(dev + " (") and it.endswith(")"):
            new = corrected(en, it[len(dev) + 2:-1], corr)
            if new:
                items[i], changed = f"{dev} ({new})", True
        elif not dev:
            new = corrected(en, it, corr)
            if new:
                items[i], changed = new, True
    return head + "; ".join(items) + sep + tail if changed else hi

def item_fix(df, table, en_col, hi_col, method_col, corr, mentions):
    def fix(r):
        en, hi = r[en_col], r[hi_col]
        if not hi:
            return hi
        if table == "symptoms":
            return corrected(en, hi, corr) or hi
        if table == "diseases" and str(r.get(method_col, "")).startswith("composed"):
            return fix_composed(hi, mentions.get(r["disease_id"], []), corr)
        return fix_list(en, hi, corr)
    if not corr or not len(df):
        return 0
    out = df.apply(fix, axis=1)
    m = out != df[hi_col]
    df.loc[m, hi_col] = out[m]
    mark(df, m, method_col, "mt_item_corrections")
    return int(m.sum())

def write_table(df, name):
    df.to_csv(P / f"{name}.csv", index=False)
    df.astype({c: str for c in df.columns if df[c].dtype == object}).to_parquet(P / f"{name}.parquet", index=False)

def mt_corrections(D, T, S):
    """apply both curated post-edit files to every machine-translated column; writes S, T and the derived tables
    (D is written by the caller).  Idempotent: an applied correction no longer matches."""
    rules = pd.read_csv(ROOT / "curation/mt_postedit_rules.csv", keep_default_na=False)
    corr = load_item_corrections()
    ds = rd("disease_symptom").sort_values(["disease_id", "mention_rank"], kind="stable")
    mentions = {d: [(iast_to_deva(iso_to_iast(sa).lower()) if sa else "", en) for sa, en in zip(g.mention_sa_iast, g.mention_en)]
                for d, g in ds.groupby("disease_id", sort=False)}
    tables = {"symptoms": S, "terminology": T, "diseases": D}
    tables.update({t: rd(t) for t in ("therapies", "pharmaceutics", "diet_lifestyle") if (P / f"{t}.csv").exists()})
    changed = {}
    for name, df in tables.items():
        en, hi, meth = MT_COLUMNS[name]
        if {en, hi} <= set(df.columns):
            changed[name] = postedit(df, name, en, hi, meth, rules) + item_fix(df, name, en, hi, meth, corr, mentions)
    for name, df in tables.items():
        if name != "diseases":
            write_table(df, name)
    return changed

def mt_counts(D, T, S):
    """cumulative: rows carrying a post-edit mark from this or an earlier run (derived tables mirror terminology)"""
    pe = lambda df, c: int(df[c].str.contains("post-edited|rule-corrected").sum()) if c in df else 0
    return {"symptom_glosses": pe(S, "gloss_hi_method"), "disorder_definitions": pe(D, "definition_hi_method"),
            "term_definitions": pe(T, "definition_hi_method")}

def main(mt_only=False):
    rep = {"mt_postedits": None}
    D, T, S = rd("diseases"), rd("terminology"), rd("symptoms")
    changed = mt_corrections(D, T, S)          # before the WHO definitions are copied, so copies are corrected too
    print("Hindi post-edits applied now:", changed)
    if mt_only:                                # quick path after editing curation/mt_*.csv
        D.to_csv(P / "diseases.csv", index=False)
        if (P / "diseases.parquet").exists():
            D.to_parquet(P / "diseases.parquet", index=False)
        f = ROOT / "reports/fill_missing_report.json"
        old = json.loads(f.read_text()) if f.exists() else {}
        old["mt_postedits"] = mt_counts(D, T, S)
        f.write_text(json.dumps(old, indent=2, default=int))
        print("cumulative:", old["mt_postedits"])
        return
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
    rep["mt_postedits"] = mt_counts(D, T, S)
    (ROOT / "reports/fill_missing_report.json").write_text(json.dumps(rep, indent=2, default=int))
    print(json.dumps(rep, indent=1, default=int))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mt-only", action="store_true",
                    help="only re-apply the curated Hindi post-edits (curation/mt_postedit_rules.csv, curation/mt_item_corrections.csv)")
    main(mt_only=ap.parse_args().mt_only)
