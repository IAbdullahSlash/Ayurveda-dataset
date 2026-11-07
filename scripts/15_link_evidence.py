#!/usr/bin/env python3
"""
Stage 15 - Literature evidence for every herb->disorder and formulation->disorder link.

The indication links come from classical/curated sources (Amidha, the curated formulary).  For each link we ask
PubMed how often the plant (accepted Latin binomial + binomials used by the sources) or formulation is studied
together with the disorder, using a curated biomedical query per disorder (curation/disorder_biomedical_queries.csv,
an approximate Ayurveda->biomedicine correspondence).  We also count the subset that are clinical studies
(clinical trial / RCT / meta-analysis / systematic review publication types) and store the top PMIDs.

Association: lift = N * n_pair / (n_entity * n_disorder)  (N = all PubMed records); lift > 1 means the pair is
studied together more often than chance.  Tiers:
    clinical_evidence      >=1 clinical study (trial / RCT / meta-analysis / systematic review)
    literature_supported   >=3 co-occurring papers and lift >= 2
    sparse                 1-2 papers or lift < 2
    no_literature          0 papers
    not_queryable          disorder without biomedical counterpart or entity without a searchable name
Counts are facts; queries are stored for reproducibility.  This is co-occurrence, not proof of efficacy.
Outputs: data/processed/herb_indication_evidence.csv, formulation_indication_evidence.csv,
         reports/link_evidence_report.json
"""
import json, re, sys, time
from pathlib import Path
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.indic import ascii_fold

ROOT = Path(__file__).resolve().parents[1]
P, CACHE, CUR = ROOT / "data/processed", ROOT / "data/interim/cache", ROOT / "curation"
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)
UA = {"User-Agent": "ayurveda-open-dataset-builder/1.0 (research)"}
S = requests.Session()
CF = CACHE / "pubmed_esearch.json"
C = json.loads(CF.read_text(encoding="utf-8")) if CF.exists() else {}
CLINICAL = ('(clinical trial[pt] OR randomized controlled trial[pt] OR meta-analysis[pt] OR '
            'systematic review[pt] OR "clinical study"[pt])')
_calls = 0

def esearch(term, retmax=3):
    global _calls
    if term in C:
        return C[term]
    for attempt in range(6):
        try:
            r = S.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                      params={"db": "pubmed", "term": term, "retmode": "json", "retmax": retmax, "sort": "relevance",
                              "tool": "ayurveda_dataset_builder"}, headers=UA, timeout=40)
            time.sleep(0.36)                                   # NCBI: <= 3 requests/s without an API key
            if r.status_code == 200:
                js = r.json().get("esearchresult", {})
                if "count" in js:
                    C[term] = {"count": int(js["count"]), "ids": js.get("idlist", [])[:retmax]}
                    _calls += 1
                    if _calls % 50 == 0:
                        CF.write_text(json.dumps(C), encoding="utf-8")
                    return C[term]
        except Exception:
            pass
        time.sleep(2 ** (attempt + 1))
    return None

def herb_clause(row):
    names = [row.accepted_name] + [b.strip() for b in row.botanical_names_in_sources.split(";")]
    bins = []
    for n in names:
        m = re.match(r"^([A-Z][a-z]+) ([a-z][a-z\-]+)", n.strip())
        if m and m.group(2) not in ("sp", "spp", "var", "subsp", "x") and f"{m.group(1)} {m.group(2)}" not in bins:
            bins.append(f"{m.group(1)} {m.group(2)}")
    return " OR ".join(f'"{b}"[tiab]' for b in bins[:4]) if bins else ""

def form_clause(row):
    """search variants are '|'-separated ASCII spellings (e.g. 'avipattikar|avipattikara'); fall back to the folded name"""
    vs = [v.strip().strip('"') for v in re.split(r"[|;]", row.search_variants) if v.strip().strip('"')]
    if not vs:
        vs = [ascii_fold(row.name_sa_iast)]
    vs = [re.sub(r"[^A-Za-z \-]", "", v).strip() for v in vs]
    return " OR ".join(f'"{v}"[tiab]' for v in dict.fromkeys(vs) if len(v) >= 5)

def tier(n_pair, n_clin, lift):
    if n_pair is None:
        return "not_queryable"
    if n_clin:
        return "clinical_evidence"
    if n_pair >= 3 and lift >= 2:
        return "literature_supported"
    return "sparse" if n_pair else "no_literature"

def run(links, entity_col, clause_of, label):
    Q = pd.read_csv(CUR / "disorder_biomedical_queries.csv", keep_default_na=False).set_index("disease_id")
    N = esearch("all[sb]", 0)["count"]
    out, pairs = [], links[[entity_col, "disease_id"]].drop_duplicates()
    pairs = pairs[pairs.disease_id != ""]
    for i, (e, d) in enumerate(pairs.itertuples(index=False), 1):
        ec = clause_of.get(e, "")
        dq = Q.pubmed_query.get(d, "") if d in Q.index else ""
        rec = dict(entity_id=e, disease_id=d, biomedical_concept=Q.biomedical_concept_en.get(d, "") if d in Q.index else "",
                   correspondence=Q.correspondence.get(d, "") if d in Q.index else "", query="", n_entity=None,
                   n_disorder=None, n_pair=None, n_clinical=None, lift=None, top_pmids="", clinical_pmids="")
        if ec and dq:
            q = f"({ec}) AND {dq}"
            a, b, ab = esearch(f"({ec})", 0), esearch(dq, 0), esearch(q, 3)
            cl = esearch(f"{q} AND {CLINICAL}", 3) if ab and ab["count"] else {"count": 0, "ids": []}
            if a and b and ab and cl is not None:
                lift = (N * ab["count"] / (a["count"] * b["count"])) if a["count"] and b["count"] else 0.0
                rec.update(query=q, n_entity=a["count"], n_disorder=b["count"], n_pair=ab["count"], n_clinical=cl["count"],
                           lift=round(lift, 2), top_pmids=";".join(ab["ids"]), clinical_pmids=";".join(cl["ids"]))
        rec["evidence_tier"] = tier(rec["n_pair"], rec["n_clinical"], rec["lift"] or 0)
        out.append(rec)
        if i % 100 == 0:
            print(f"  {label}: {i}/{len(pairs)}", flush=True)
    CF.write_text(json.dumps(C), encoding="utf-8")
    df = pd.DataFrame(out).rename(columns={"entity_id": entity_col})
    for c in ("n_entity", "n_disorder", "n_pair", "n_clinical"):
        df[c] = df[c].astype("Int64")   # whole numbers, blank when the link is not queryable (not '7.0')
    df["pubmed_total_N"] = N
    df["source_id"] = "S8"
    df["data_origin"] = "PubMed co-occurrence (E-utilities); counts are facts - not proof of efficacy"
    return df

def main():
    H, F = rd("herbs"), rd("formulations")
    hc = {r.herb_id: herb_clause(r) for r in H.itertuples()}
    fc = {r.form_id: form_clause(r) for r in F.itertuples()}
    he = run(rd("herb_indication"), "herb_id", hc, "herb links")
    fe = run(rd("formulation_indications"), "form_id", fc, "formulation links")
    he.to_csv(P / "herb_indication_evidence.csv", index=False)
    fe.to_csv(P / "formulation_indication_evidence.csv", index=False)
    rep = {}
    for name, df in (("herb_indication", he), ("formulation_indications", fe)):
        q = df[df.evidence_tier != "not_queryable"]
        rep[name] = {"links": int(len(df)), "queryable": int(len(q)),
                     "tiers": df.evidence_tier.value_counts().to_dict(),
                     "share_with_any_literature": round(float((q.n_pair > 0).mean()), 3) if len(q) else None,
                     "share_enriched_lift>=2": round(float((q.lift >= 2).mean()), 3) if len(q) else None,
                     "share_with_clinical_study": round(float((q.n_clinical > 0).mean()), 3) if len(q) else None,
                     "median_lift_when_cooccurring": float(q[q.n_pair > 0].lift.median()) if (q.n_pair > 0).any() else None}
    (ROOT / "reports/link_evidence_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=1))

if __name__ == "__main__":
    main()
