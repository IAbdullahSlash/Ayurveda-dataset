#!/usr/bin/env python3
"""
Stage 05 - Modern-evidence layer.

* PubMed (NCBI E-utilities): number of indexed papers per herb (title/abstract), per herb restricted
  to Ayurveda context, per classical formulation, per diagnostic method and per key therapy.
* ClinicalTrials.gov API v2: registered interventional/observational studies per herb & formulation
  (NCT id, title, status, phase, conditions, enrollment, start date).
Counts are facts (not copyrightable); every query string is stored with its result for reproducibility.
Outputs: data/processed/clinical_trials.*, evidence_queries.*, and evidence columns merged into
herbs / formulations / diagnostic_methods / therapies.
"""
import json, re, sys, time
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT, CACHE = ROOT / "data/processed", ROOT / "data/interim/cache"
UA = {"User-Agent": "ayurveda-open-dataset-builder/1.0 (research)"}
S = requests.Session()

def cached(name):
    f = CACHE / name
    return f, (json.loads(f.read_text()) if f.exists() else {})

PM_FILE, PM = cached("pubmed_counts.json")
CT_FILE, CT = cached("ctgov_studies.json")

def pubmed_count(term):
    if term in PM:
        return PM[term]
    for attempt in range(5):
        try:
            r = S.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                      params={"db": "pubmed", "term": term, "rettype": "count", "retmode": "json",
                              "tool": "ayurveda_dataset_builder"}, headers=UA, timeout=30)
            if r.status_code == 200:
                PM[term] = int(r.json()["esearchresult"]["count"])
                time.sleep(0.36)                       # NCBI: <= 3 requests/second without API key
                return PM[term]
        except Exception:
            pass
        time.sleep(2 ** (attempt + 1))
    return None

FIELDS = "NCTId,BriefTitle,OverallStatus,Phase,Condition,EnrollmentCount,StartDate,StudyType,InterventionName"

def ctgov(query):
    if query in CT:
        return CT[query]
    studies, token, total = [], None, None
    for page in range(3):                               # up to 300 studies per query
        p = {"query.intr": query, "countTotal": "true", "pageSize": 100, "fields": FIELDS}
        if token:
            p["pageToken"] = token
        for attempt in range(5):
            try:
                r = S.get("https://clinicaltrials.gov/api/v2/studies", params=p, headers=UA, timeout=60)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(2 ** (attempt + 1))
        js = r.json()
        total = js.get("totalCount", total)
        for st in js.get("studies", []):
            ps = st.get("protocolSection", {})
            studies.append(dict(
                nct_id=ps.get("identificationModule", {}).get("nctId"),
                title=ps.get("identificationModule", {}).get("briefTitle"),
                status=ps.get("statusModule", {}).get("overallStatus"),
                start_date=ps.get("statusModule", {}).get("startDateStruct", {}).get("date"),
                study_type=ps.get("designModule", {}).get("studyType"),
                phases=";".join(ps.get("designModule", {}).get("phases", []) or []),
                enrollment=ps.get("designModule", {}).get("enrollmentInfo", {}).get("count"),
                conditions=";".join(ps.get("conditionsModule", {}).get("conditions", []) or []),
                interventions=";".join(i.get("name", "") for i in ps.get("armsInterventionsModule", {}).get("interventions", []) or []),
            ))
        token = js.get("nextPageToken")
        time.sleep(0.4)
        if not token:
            break
    CT[query] = {"total": total, "studies": studies}
    return CT[query]

def flush():
    PM_FILE.write_text(json.dumps(PM))
    CT_FILE.write_text(json.dumps(CT))

GENERIC = {"amla", "bala", "neem", "rasna", "musta", "vacha", "kusta", "arka", "bhanga"}

def main():
    herbs = pd.read_csv(OUT / "herbs.csv", keep_default_na=False)
    forms = pd.read_csv(OUT / "formulations.csv", keep_default_na=False)
    dx = pd.read_csv(OUT / "diagnostic_methods.csv", keep_default_na=False)
    queries, trials = [], []
    for c in ["pubmed_count", "pubmed_ayurveda_count", "clinicaltrials_count"]:
        herbs[c] = pd.Series([None] * len(herbs), dtype="Float64")
    forms["search_term"] = ""
    for c in ["pubmed_count", "clinicaltrials_count"]:
        forms[c] = pd.Series([None] * len(forms), dtype="Float64")
    dx["pubmed_count"] = pd.Series([None] * len(dx), dtype="Float64")
    # ------------------------------------------------------------------ herbs
    for i, r in enumerate(herbs.itertuples(), 1):
        a = r.accepted_name
        if not re.match(r"^[A-Z][a-z]+ [a-z\-]+", a):
            herbs.loc[r.Index, ["pubmed_count", "pubmed_ayurveda_count", "clinicaltrials_count"]] = [None, None, None]
            continue
        q1 = f'"{a}"[tiab]'
        q2 = f'"{a}"[tiab] AND (ayurved*[tiab] OR "Indian traditional medicine"[tiab])'
        c1, c2 = pubmed_count(q1), pubmed_count(q2)
        alt = re.sub(r"[^A-Za-z ]", "", r.name_ascii or "").strip()
        ctq = f'"{a}"' + (f' OR "{alt}"' if len(alt) >= 5 and alt.lower() not in GENERIC else "")
        ct = ctgov(ctq)
        herbs.loc[r.Index, ["pubmed_count", "pubmed_ayurveda_count", "clinicaltrials_count"]] = [c1, c2, ct["total"]]
        queries += [dict(entity_type="herb", entity_id=r.herb_id, api="pubmed", query=q1, count=c1),
                    dict(entity_type="herb", entity_id=r.herb_id, api="pubmed", query=q2, count=c2),
                    dict(entity_type="herb", entity_id=r.herb_id, api="clinicaltrials.gov(query.intr)", query=ctq, count=ct["total"])]
        for s in ct["studies"]:
            trials.append(dict(entity_type="herb", entity_id=r.herb_id, **s))
        if i % 50 == 0:
            flush(); print(f"   herbs {i}/{len(herbs)}")
    # ------------------------------------------------------------------ formulations
    for r in forms.itertuples():
        # curated spelling variants (curation/classical_formulations.csv: search_variants) - the formulation
        # name must be searched as a whole ('triphala guggulu'), never reduced to its first herb
        variants = [v.strip() for v in str(getattr(r, "search_variants", "")).split("|") if v.strip()] or [r.name_en]
        q = " OR ".join(f'"{v}"[tiab]' for v in variants)
        ctq = " OR ".join(f'"{v}"' for v in variants)
        c = pubmed_count(q)
        ct = ctgov(ctq)
        forms.loc[r.Index, ["search_term", "pubmed_count", "clinicaltrials_count"]] = [ctq, c, ct["total"]]
        queries += [dict(entity_type="formulation", entity_id=r.form_id, api="pubmed", query=q, count=c),
                    dict(entity_type="formulation", entity_id=r.form_id, api="clinicaltrials.gov(query.intr)", query=ctq, count=ct["total"])]
        for s in ct["studies"]:
            trials.append(dict(entity_type="formulation", entity_id=r.form_id, **s))
    flush()
    # ------------------------------------------------------------------ diagnostics & therapies
    for r in dx.itertuples():
        c = pubmed_count(r.pubmed_query)
        dx.loc[r.Index, "pubmed_count"] = c
        queries.append(dict(entity_type="diagnostic_method", entity_id=r.dx_id, api="pubmed", query=r.pubmed_query, count=c))
    therapy_queries = {
        "pañcakarma": '"panchakarma"[tiab] OR "panchakarma therapy"[tiab]', "vamana": '"vamana"[tiab]',
        "virecana": '"virechana"[tiab] OR "virecana"[tiab]', "basti": '"basti"[tiab] AND (ayurved*[tiab] OR enema[tiab])',
        "nasya": '"nasya"[tiab]', "raktamokṣaṇa / jalaukāvacaraṇa": '"leech therapy"[tiab] OR "jalaukavacharana"[tiab] OR "hirudotherapy"[tiab]',
        "śirodhārā": '"shirodhara"[tiab]', "abhyaṅga": '"abhyanga"[tiab] OR ("ayurvedic massage"[tiab])',
        "kṣārasūtra": '"kshara sutra"[tiab] OR "ksharasutra"[tiab]', "agnikarma": '"agnikarma"[tiab]',
        "rasāyana": '"rasayana"[tiab]', "yoga (svasthavṛtta)": '"yoga"[tiab] AND ayurved*[tiab]'}
    tq = []
    for k, q in therapy_queries.items():
        c = pubmed_count(q)
        tq.append(dict(therapy=k, pubmed_query=q, pubmed_count=c))
        queries.append(dict(entity_type="therapy", entity_id=k, api="pubmed", query=q, count=c))
    flush()
    ts = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    qdf = pd.DataFrame(queries); qdf["retrieved_utc"] = ts
    tr = pd.DataFrame(trials).drop_duplicates(["entity_type", "entity_id", "nct_id"])
    tr["source_id"] = "S9"
    for name, df in [("herbs", herbs), ("formulations", forms), ("diagnostic_methods", dx)]:
        df.to_csv(OUT / f"{name}.csv", index=False)
        d2 = df.copy()
        for c in d2.columns:
            if d2[c].dtype == object:
                d2[c] = d2[c].astype(str)
        d2.to_parquet(OUT / f"{name}.parquet", index=False)
    for name, df in [("clinical_trials", tr), ("evidence_queries", qdf), ("therapy_evidence", pd.DataFrame(tq))]:
        df.to_csv(OUT / f"{name}.csv", index=False)
        df.astype({c: str for c in df.columns if df[c].dtype == object}).to_parquet(OUT / f"{name}.parquet", index=False)
    rep = dict(herbs_with_pubmed=int((pd.to_numeric(herbs.pubmed_count, errors="coerce") > 0).sum()),
               herbs_with_trials=int((pd.to_numeric(herbs.clinicaltrials_count, errors="coerce") > 0).sum()),
               trial_links=len(tr), distinct_trials=int(tr.nct_id.nunique()) if len(tr) else 0,
               formulations_with_pubmed=int((pd.to_numeric(forms.pubmed_count, errors="coerce") > 0).sum()),
               formulations_with_trials=int((pd.to_numeric(forms.clinicaltrials_count, errors="coerce") > 0).sum()),
               queries=len(qdf), retrieved_utc=ts)
    (ROOT / "reports/evidence_report.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))

if __name__ == "__main__":
    main()
