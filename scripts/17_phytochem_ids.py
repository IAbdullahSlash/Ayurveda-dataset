#!/usr/bin/env python3
"""
Stage 17 - Chemical identifiers and protein targets for the phytochemical layer.

1. PubChem (NCBI, public domain): Dr. Duke compound names -> PubChem CID, InChIKey, formula, molecular weight,
   SMILES, IUPAC name.  Scope: compounds with a recorded biological activity or present in >= 3 herbs, excluding
   nutritional aggregates (fat, protein, ash ...).  -> data/processed/phytochemicals.csv (merged into the KB)
2. ChEMBL (EMBL-EBI, CC BY-SA 3.0): human single-protein targets with potency pChEMBL >= 6 (<= 1 µM) for the
   compounds that occur in the most herbs.  Share-alike data cannot be merged into the CC BY-NC-SA release, so it is
   written to a SEPARATE file with its own licence notice: release/chembl/phytochemical_targets_chembl.csv.
   The ChEMBL API is retried; if it is unavailable the step is skipped and reported (re-run later).
"""
import json, re, sys, time, urllib.parse
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
P, CACHE = ROOT / "data/processed", ROOT / "data/interim/cache"
CH = ROOT / "release/chembl"
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)
UA = {"User-Agent": "ayurveda-open-dataset-builder/1.0 (research)"}
S = requests.Session()
AGG = {"FAT", "PROTEIN", "ASH", "FIBER", "WATER", "CARBOHYDRATES", "KILOCALORIES", "EO", "ESSENTIAL-OIL", "MUCILAGE",
       "TANNIN", "TANNINS", "RESIN", "GUM", "STARCH", "SUGARS", "SUGAR", "ALKALOIDS", "SAPONIN", "SAPONINS", "FLAVONOIDS",
       "PROTEIN-NITROGEN", "NITROGEN", "DIETARY-FIBER", "FIXED-OIL", "OIL", "WAX", "PECTIN", "CELLULOSE", "LIGNIN",
       "PENTOSANS", "HEMICELLULOSE", "CRUDE-FIBER", "VOLATILE-OIL", "TOCOPHEROL", "FATTY-ACIDS", "PHENOLS", "GLUCOSIDES",
       "STEROLS", "TERPENES", "VITAMIN-A", "VITAMIN-B", "VITAMIN-C", "VITAMIN-E", "NIACIN-EQUIVALENTS"}

def cache(name):
    f = CACHE / name
    return f, (json.loads(f.read_text()) if f.exists() else {})

PCF, PC = cache("pubchem_names.json")
CHF, CHC = cache("chembl.json")

def get_json(url, tries=4, pause=0.21, timeout=40):
    for a in range(tries):
        try:
            r = S.get(url, headers=UA, timeout=timeout)
            time.sleep(pause)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return {}
            if r.status_code in (400,):
                return {}
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 ** (a + 1))
    return None                                   # service failure (distinct from 'not found' = {})

def name_variants(n):
    low = n.lower()
    keep_hyphen = re.sub(r"(?<![0-9a-z,()'+\-])-|-(?=(acid|ester|oxide|glucoside|glycoside|ol|one)\b)", " ", low)
    v = [low.replace("-", " "), low, re.sub(r"(?<=[a-z]{3})-(?=[a-z]{3})", " ", low), keep_hyphen]
    return list(dict.fromkeys(x.strip() for x in v if x.strip()))

PROPS = "MolecularFormula,MolecularWeight,InChIKey,IUPACName,SMILES,ConnectivitySMILES"

def pubchem(name):
    if name in PC:
        return PC[name]
    res = {"status": "not_found"}
    for v in name_variants(name):
        js = get_json(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.parse.quote(v)}/property/{PROPS}/JSON")
        if js is None:
            res = {"status": "service_error"}
            break
        props = (js.get("PropertyTable") or {}).get("Properties") or []
        if props:
            p = props[0]
            res = {"status": "matched" if len(props) == 1 else "matched_first_of_many", "lookup_name": v, "cid": p.get("CID"),
                   "formula": p.get("MolecularFormula", ""), "mw": p.get("MolecularWeight", ""),
                   "inchikey": p.get("InChIKey", ""), "iupac": p.get("IUPACName", ""),
                   "smiles": p.get("SMILES") or p.get("ConnectivitySMILES", "")}
            break
    if res["status"] != "service_error":
        PC[name] = res
    return res

def chembl_targets(inchikey):
    if inchikey in CHC:
        return CHC[inchikey]
    base = "https://www.ebi.ac.uk/chembl/api/data"
    m = get_json(f"{base}/molecule.json?molecule_structures__standard_inchi_key={inchikey}&only=molecule_chembl_id,pref_name",
                 pause=0.3, timeout=60)
    if m is None:
        return None
    mols = m.get("molecules") or []
    if not mols:
        CHC[inchikey] = {"chembl_id": "", "targets": []}
        return CHC[inchikey]
    cid = mols[0]["molecule_chembl_id"]
    url = (f"{base}/activity.json?molecule_chembl_id={cid}&pchembl_value__gte=6&target_type=SINGLE%20PROTEIN"
           f"&target_organism=Homo%20sapiens&limit=500")   # note: the `only=` field filter makes this endpoint fail (HTTP 500)
    a = get_json(url, tries=3, pause=0.3, timeout=120)    # one page: up to 500 potent activities is plenty for a target list
    if a is None:
        return None
    acts = a.get("activities") or []
    agg = {}
    for x in acts:
        t = x.get("target_chembl_id")
        if not t:
            continue
        d = agg.setdefault(t, {"target_chembl_id": t, "target_pref_name": x.get("target_pref_name", ""),
                               "best_pchembl": 0.0, "n_measurements": 0, "activity_types": set()})
        try:
            d["best_pchembl"] = max(d["best_pchembl"], float(x.get("pchembl_value") or 0))
        except ValueError:
            pass
        d["n_measurements"] += 1
        d["activity_types"].add(x.get("standard_type", ""))
    targets = [dict(v, activity_types=";".join(sorted(s for s in v["activity_types"] if s))) for v in agg.values()]
    CHC[inchikey] = {"chembl_id": cid, "pref_name": mols[0].get("pref_name") or "", "targets": targets}
    return CHC[inchikey]

def chembl_step(out, top_chembl):
    from concurrent.futures import ThreadPoolExecutor
    CH.mkdir(parents=True, exist_ok=True)
    top = out[(out.inchikey != "")].head(top_chembl)
    keys = list(dict.fromkeys(top.inchikey))
    done, failed = 0, 0
    with ThreadPoolExecutor(3) as ex:
        for k, res in zip(keys, ex.map(chembl_targets, keys)):
            done += 1; failed += res is None
            if done % 10 == 0:
                CHF.write_text(json.dumps(dict(CHC))); print(f"  chembl {done}/{len(keys)} (failed {failed})", flush=True)
    CHF.write_text(json.dumps(dict(CHC)))
    trows = []
    for r in top.itertuples():
        t_ = CHC.get(r.inchikey)
        for x in (t_ or {}).get("targets", []):
            trows.append(dict(chemical=r.chemical, pubchem_cid=r.pubchem_cid, inchikey=r.inchikey, molecule_chembl_id=t_["chembl_id"], **x))
    return len(keys), failed, trows

def main(top_chembl=300, chembl_only=False):
    hp, pa = rd("herb_phytochemicals"), rd("phytochemical_activities")
    nh = hp.groupby("chemical").herb_id.nunique()
    na = pa.groupby("chemical").activity.nunique()
    df = pd.DataFrame({"n_herbs": nh}).join(na.rename("n_activities"), how="outer").fillna(0).astype(int)
    df = df[~df.index.isin(AGG) & ((df.n_activities > 0) | (df.n_herbs >= 3))]
    df = df.sort_values(["n_herbs", "n_activities"], ascending=False)
    rows, errors = [], 0
    if chembl_only:
        df = df.iloc[0:0]
    for i, (chem, r) in enumerate(df.iterrows(), 1):
        res = pubchem(chem)
        errors += res["status"] == "service_error"
        rows.append(dict(chemical=chem, n_herbs=r.n_herbs, n_activities=r.n_activities, **{k: res.get(k, "") for k in
                         ["status", "lookup_name", "cid", "inchikey", "formula", "mw", "smiles", "iupac"]}))
        if i % 200 == 0:
            PCF.write_text(json.dumps(PC)); print(f"  pubchem {i}/{len(df)}", flush=True)
    if chembl_only:
        out = pd.read_csv(P / "phytochemicals.csv", keep_default_na=False)
    else:
        PCF.write_text(json.dumps(PC))
        out = pd.DataFrame(rows).rename(columns={"status": "pubchem_match", "cid": "pubchem_cid", "iupac": "iupac_name",
                                             "lookup_name": "pubchem_lookup_name", "mw": "molecular_weight"})
        out["pubchem_cid"] = out.pubchem_cid.astype(str).str.replace(r"\.0$", "", regex=True).replace("nan", "")
        out["source_id"] = "S11"
        out["licence"] = "PubChem (NCBI) - public domain"
        out.to_csv(P / "phytochemicals.csv", index=False)
        print(f"  phytochemicals: {len(out)}; matched {out.pubchem_match.str.startswith('matched').mean():.3f}; service errors {errors}")
    # ---- ChEMBL targets (separate, share-alike) ----
    n_try, failed, trows = chembl_step(out, top_chembl)
    status = {"chembl_compounds_attempted": n_try, "chembl_failures": failed,
              "chembl_target_rows": len(trows), "date": time.strftime("%Y-%m-%d")}
    if trows:
        T = pd.DataFrame(trows)
        T.to_csv(CH / "phytochemical_targets_chembl.csv", index=False)
        (CH / "LICENSE_CHEMBL.txt").write_text(
            "phytochemical_targets_chembl.csv is derived from ChEMBL (EMBL-EBI), https://www.ebi.ac.uk/chembl/\n"
            "Licence: Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0).\n"
            "Cite: Zdrazil B. et al. The ChEMBL Database in 2023. Nucleic Acids Res. 2024;52(D1):D1180-D1192.\n"
            "This file is distributed separately from the AyurKB core (CC BY-NC-SA 4.0) because of share-alike terms.\n"
            "Filter: human SINGLE PROTEIN targets, pChEMBL >= 6 (potency <= 1 uM); compounds matched by InChIKey.\n")
    (ROOT / "reports/phytochem_ids_report.json").write_text(json.dumps({
        "compounds_in_scope": len(out), "pubchem_matched": int(out.pubchem_match.str.startswith("matched").sum()),
        "pubchem_service_errors": errors, **status}, indent=2))
    print(json.dumps(status))

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--chembl-only", action="store_true", help="reuse phytochemicals.csv; only (re)fetch ChEMBL targets")
    ap.add_argument("--top", type=int, default=300, help="compounds (most widespread first) to look up in ChEMBL")
    a = ap.parse_args()
    main(a.top, a.chembl_only)
