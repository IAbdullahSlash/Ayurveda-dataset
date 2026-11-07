#!/usr/bin/env python3
"""
Stage 03 - Taxonomic validation & bilingual name enrichment (pre-processing).

1. Every botanical name found in any source (SAT plants + synonyms + substitutes, Amidha herbs,
   mahākaṣāya members, Duke taxa in the same genera) is matched against the GBIF Backbone Taxonomy
   (api.gbif.org/v1/species/match).  Result: accepted name, status (ACCEPTED/SYNONYM/DOUBTFUL),
   family, match type & confidence.  Outdated names used in Ayurvedic literature are resolved to
   current accepted names (e.g. Adhatoda vasica -> Justicia adhatoda) - this is what lets records
   from different sources be joined reliably.
2. Wikidata (CC0) is queried by GBIF taxon ID (P846) for Hindi / Sanskrit / English labels and Hindi
   aliases, giving native-script common names for the bilingual layer.
All HTTP responses are cached in data/interim/cache/ so the stage is reproducible offline.
"""
import json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
CACHE = INT / "cache"
CACHE.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "ayurveda-open-dataset-builder/1.0 (research; python-requests)"}

def clean_binomial(s):
    s = re.sub(r"\s+", " ", str(s or "")).strip(" -.,")
    m = re.match(r"^([A-Z][a-z]+)\s+(×\s*)?([a-z][a-z\-]+)(?:\s+(subsp\.|var\.|f\.)\s+([a-z\-]+))?", s)
    if not m:
        return ""
    g, hyb, sp, rank, infra = m.groups()
    return f"{g} {'× ' if hyb else ''}{sp.strip('-')}" + (f" {rank} {infra}" if rank else "")

# ----------------------------------------------------------------------------- GBIF
def gbif_match_all(names):
    cf = CACHE / "gbif_match.json"
    cache = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
    todo = [n for n in names if n and n not in cache]
    s = requests.Session()
    def one(n):
        for attempt in range(4):
            try:
                r = s.get("https://api.gbif.org/v1/species/match", params={"name": n, "kingdom": "Plantae", "verbose": "false"},
                          headers=UA, timeout=30)
                if r.status_code == 200:
                    return n, r.json()
            except Exception:
                pass
            time.sleep(2 ** (attempt + 1))
        return n, {"matchType": "ERROR"}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for i, (n, js) in enumerate(ex.map(one, todo), 1):
            cache[n] = js
            if i % 200 == 0:
                cf.write_text(json.dumps(cache), encoding="utf-8")
                print(f"   gbif {i}/{len(todo)}")
    cf.write_text(json.dumps(cache), encoding="utf-8")
    rows = []
    for n in names:
        js = cache.get(n, {})
        status = js.get("status", "")
        accepted = js.get("species") if js.get("rank") in ("SPECIES", "SUBSPECIES", "VARIETY", "FORM") else js.get("canonicalName", "")
        if js.get("rank") == "SPECIES" and status == "ACCEPTED":
            accepted = js.get("canonicalName")
        rows.append(dict(name_in_source=n, gbif_match_type=js.get("matchType", "NONE"), gbif_confidence=js.get("confidence"),
                         gbif_status=status, gbif_rank=js.get("rank", ""), gbif_matched_name=js.get("canonicalName", ""),
                         gbif_scientific_name=js.get("scientificName", ""),
                         accepted_name=accepted or "", accepted_key=js.get("speciesKey") or js.get("acceptedUsageKey") or js.get("usageKey"),
                         family=js.get("family", ""), genus=js.get("genus", "")))
    df = pd.DataFrame(rows)
    # names that GBIF only matched at genus level (or not at all) are NOT accepted as species identifications
    ok = df.gbif_match_type.isin(["EXACT", "FUZZY"]) & df.gbif_rank.isin(["SPECIES", "SUBSPECIES", "VARIETY", "FORM"])
    df["taxon_resolved"] = ok
    df["resolution_method"] = ok.map({True: "gbif_match", False: ""})
    df.loc[~ok, ["accepted_name", "accepted_key"]] = ["", None]
    return df

BACKBONE = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"

def _epithet_stem(name):
    parts = (name or "").split()
    return parts[1][:-2] if len(parts) > 1 and len(parts[1]) > 4 else (parts[1] if len(parts) > 1 else "")

def gbif_search_exact(names, authors=None):
    """2nd pass for names the match API leaves at genus level because of homonyms/ambiguity:
    exact canonical-name search in the GBIF backbone; synonyms are followed to the accepted species.
    Synonym choice is conservative: (1) accepted name keeps the source epithet (homotypic transfer,
    Acacia catechu -> Senegalia catechu); (2) authorship agrees with the author given by the source;
    (3) otherwise, if candidates point to >1 accepted species, the name is left UNRESOLVED (ambiguous)."""
    from rapidfuzz import fuzz
    authors = authors or {}
    cf = CACHE / "gbif_search.json"
    cache = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
    s = requests.Session()
    for n in names:
        if n in cache:
            continue
        r = s.get("https://api.gbif.org/v1/species/search", params={"q": n, "datasetKey": BACKBONE, "rank": "SPECIES", "limit": 20},
                  headers=UA, timeout=30)
        cache[n] = r.json().get("results", []) if r.status_code == 200 else []
        time.sleep(0.2)
    cf.write_text(json.dumps(cache), encoding="utf-8")
    out, ambiguous = {}, {}
    for n in names:
        hits = [h for h in cache.get(n, []) if h.get("canonicalName") == n]
        acc = [h for h in hits if h.get("taxonomicStatus") == "ACCEPTED"]
        syn = [h for h in hits if "SYNONYM" in str(h.get("taxonomicStatus")) and h.get("accepted")]
        h, how = None, ""
        if acc:
            h, how = acc[0], "accepted"
        elif syn:
            # evidence score per candidate; winner needs a margin >= 1 over any candidate that points
            # to a DIFFERENT accepted species, otherwise the name is left unresolved (ambiguous)
            stem, genus, au = _epithet_stem(n), n.split()[0], authors.get(n, "")
            def score(x):
                st = str(x.get("taxonomicStatus"))
                s = 2.0 if st in ("SYNONYM", "HOMOTYPIC_SYNONYM") else (0.5 if st == "HETEROTYPIC_SYNONYM" else 0.0)
                sp = x.get("species", "") or ""
                s += 1.0 if stem and _epithet_stem(sp).startswith(stem[:5]) else 0.0
                s += 1.0 if sp.split()[:1] == [genus] else 0.0
                s += 3.0 if au and fuzz.partial_ratio(au, x.get("authorship", "") or "") >= 80 else 0.0
                return s
            ranked = sorted(syn, key=score, reverse=True)
            best = ranked[0]
            rivals = [score(x) for x in ranked[1:] if x.get("species") != best.get("species")]
            # positive evidence required: synonym status alone (score < 3) is not enough
            if score(best) >= 3.0 and (not rivals or score(best) - max(rivals) >= 1.0):
                h, how = best, f"synonym_scored({score(best):.1f})"
            else:
                ambiguous[n] = sorted({x.get("species") for x in syn if x.get("species")})
        if h:
            accepted = h.get("species") or (h["canonicalName"] if how == "accepted" else clean_binomial(h.get("accepted", "")))
            out[n] = dict(accepted_name=accepted, accepted_key=h.get("speciesKey") or h.get("acceptedKey") or h.get("key"),
                          family=h.get("family", ""), genus=h.get("genus", ""),
                          gbif_status=h.get("taxonomicStatus", ""), how=how)
    return out, ambiguous

def fuzzy_correct(df):
    """3rd pass: obvious misspellings ('Bocopa monnieri', 'Tisnpora cordifolia') corrected to a resolved
    name from the pool when string similarity >= 90 and the genus initial agrees."""
    from rapidfuzz import process, fuzz
    good = df[df.taxon_resolved]
    pool = {**dict(zip(good.name_in_source, good.index)), **dict(zip(good.accepted_name, good.index))}
    blocked = set(df[~df.taxon_resolved].name_in_source)          # never 'correct' towards an unresolved name
    keys = list(pool) + sorted(blocked)
    fixes = {}
    # only Ayurveda-source names are spell-corrected (Duke-only names stay unresolved = conservative)
    for i, r in df[~df.taxon_resolved & df.in_ayurveda_sources].iterrows():
        n = r.name_in_source
        if len(n.split()) < 2 or r.get("ambiguous_candidates", ""):
            continue
        best = process.extractOne(n, [k for k in keys if k != n], scorer=fuzz.ratio, score_cutoff=90)
        if best and best[0][0] == n[0] and best[0] not in blocked:
            fixes[i] = (pool[best[0]], best[0], best[1])
    for i, (j, name, score) in fixes.items():
        for c in ["accepted_name", "accepted_key", "family", "genus"]:
            df.at[i, c] = df.at[j, c]
        df.at[i, "taxon_resolved"] = True
        df.at[i, "resolution_method"] = f"spelling_corrected_to:{name} ({score:.0f})"
    return df

# ----------------------------------------------------------------------------- Wikidata
SPARQL = """SELECT ?gbif ?item ?en ?hi ?sa (GROUP_CONCAT(DISTINCT ?hialt; separator="|") AS ?hi_alias) WHERE {
  VALUES ?gbif { %s }
  ?item wdt:P846 ?gbif .
  OPTIONAL { ?item rdfs:label ?en FILTER(lang(?en)="en") }
  OPTIONAL { ?item rdfs:label ?hi FILTER(lang(?hi)="hi") }
  OPTIONAL { ?item rdfs:label ?sa FILTER(lang(?sa)="sa") }
  OPTIONAL { ?item skos:altLabel ?hialt FILTER(lang(?hialt)="hi") }
} GROUP BY ?gbif ?item ?en ?hi ?sa"""

def wikidata_by_gbif(keys):
    cf = CACHE / "wikidata_by_gbif.json"
    cache = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
    todo = [k for k in keys if k not in cache]
    for i in range(0, len(todo), 80):
        batch = todo[i:i + 80]
        q = SPARQL % " ".join(f'"{k}"' for k in batch)
        for attempt in range(5):
            r = requests.get("https://query.wikidata.org/sparql", params={"query": q},
                             headers={**UA, "Accept": "application/sparql-results+json"}, timeout=90)
            if r.status_code == 200:
                break
            time.sleep(int(r.headers.get("Retry-After", 2 ** (attempt + 2))))
        r.raise_for_status()
        for k in batch:
            cache[k] = []
        for b in r.json()["results"]["bindings"]:
            g = lambda f: b.get(f, {}).get("value", "")
            cache[g("gbif")].append(dict(qid=g("item").rsplit("/", 1)[-1], en=g("en"), hi=g("hi"), sa=g("sa"),
                                         hi_alias=g("hi_alias")))
        cf.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        print(f"   wikidata {min(i+80, len(todo))}/{len(todo)}")
        time.sleep(1.5)
    rows = []
    for k in keys:
        hits = cache.get(k, [])
        if hits:
            h = hits[0]
            rows.append(dict(accepted_key=k, wikidata_qid=h["qid"], wd_label_en=h["en"], wd_label_hi=h["hi"],
                             wd_label_sa=h["sa"], wd_alias_hi=h["hi_alias"]))
    return pd.DataFrame(rows)

def main():
    plants = pd.read_csv(INT / "sat_plants.csv", keep_default_na=False)
    amidha = pd.read_csv(INT / "amidha_herbs.csv", keep_default_na=False)
    mem = pd.read_csv(INT / "mahakashaya_members.csv", keep_default_na=False)
    names = set()
    for col in [plants.botanical_name, amidha.botanical_name, mem.member_botanical]:
        names |= {clean_binomial(x) for x in col}
    for col in [plants.botanical_synonyms, plants.substitutes]:
        for x in col:
            names |= {clean_binomial(y) for y in str(x).split(";")}
    safety = pd.read_csv(ROOT / "curation/herb_safety.csv", keep_default_na=False)
    names |= {clean_binomial(x) for x in safety.botanical_name}
    names.discard("")
    genera = {n.split()[0] for n in names}
    # Duke taxa (ethnobotany + phytochemistry) in the same genera, so Duke records can be joined
    eth = pd.read_parquet(INT / "duke_ethnobot.parquet", columns=["TAXON"])
    tax = pd.read_parquet(INT / "duke_fnftax.parquet", columns=["TAXON"])
    duke_names = {clean_binomial(t) for t in pd.concat([eth.TAXON, tax.TAXON]).unique()}
    duke_names = {d for d in duke_names if d and d.split()[0] in genera}
    all_names = sorted(names | duke_names)
    print(f"botanical names: sources {len(names)}, duke-in-genera {len(duke_names)}, total {len(all_names)}")
    gb = gbif_match_all(all_names)
    gb["in_ayurveda_sources"] = gb.name_in_source.isin(names)
    # 2nd pass: exact backbone search for Ayurveda-source names left unresolved by the match API
    unres = gb[~gb.taxon_resolved & gb.in_ayurveda_sources].name_in_source.tolist()
    authors = {clean_binomial(b): a for b, a in zip(plants.botanical_name, plants.botanical_author)}
    found, ambiguous = gbif_search_exact(unres, authors)
    for i in gb.index[gb.name_in_source.isin(found)]:
        f = found[gb.at[i, "name_in_source"]]
        for c in ["accepted_name", "accepted_key", "family", "genus"]:
            gb.at[i, c] = f[c]
        gb.at[i, "taxon_resolved"] = True
        gb.at[i, "resolution_method"] = f"gbif_search_exact:{f['how']}"
        gb.at[i, "gbif_status"] = f["gbif_status"]
    gb["ambiguous_candidates"] = gb.name_in_source.map(lambda n: "; ".join(ambiguous.get(n, [])))
    gb.loc[gb.ambiguous_candidates != "", "resolution_method"] = "ambiguous_synonym_left_unresolved"
    # 3rd pass: misspellings (never applied to names flagged ambiguous)
    gb = fuzzy_correct(gb)
    # 4th: documented manual overrides (curation/taxonomy_overrides.csv)
    ov = pd.read_csv(ROOT / "curation/taxonomy_overrides.csv", keep_default_na=False)
    for r in ov.itertuples():
        tgt = gb[gb.accepted_name == r.accepted_name]
        src_idx = gb.index[gb.name_in_source == r.name_in_source]
        if len(src_idx) and len(tgt):
            for c in ["accepted_name", "accepted_key", "family", "genus"]:
                gb.loc[src_idx, c] = tgt.iloc[0][c]
            gb.loc[src_idx, "taxon_resolved"] = True
            gb.loc[src_idx, "resolution_method"] = "manual_override"
            gb.loc[src_idx, "ambiguous_candidates"] = ""
        elif len(src_idx):                                   # target not in table: resolve it via GBIF match
            js = requests.get("https://api.gbif.org/v1/species/match", params={"name": r.accepted_name, "kingdom": "Plantae"},
                              headers=UA, timeout=30).json()
            if js.get("rank") == "SPECIES":
                gb.loc[src_idx, "accepted_name"] = js.get("species") or js.get("canonicalName")
                gb.loc[src_idx, "accepted_key"] = js.get("speciesKey") or js.get("usageKey")
                gb.loc[src_idx, "family"] = js.get("family", "")
                gb.loc[src_idx, "taxon_resolved"] = True
                gb.loc[src_idx, "resolution_method"] = "manual_override"
                gb.loc[src_idx, "ambiguous_candidates"] = ""
    gb.to_csv(INT / "taxonomy_gbif.csv", index=False)
    src = gb[gb.in_ayurveda_sources]
    print("GBIF (Ayurveda-source names):", src.gbif_status.value_counts().to_dict(),
          "| resolved:", round(src.taxon_resolved.mean(), 4))
    keys = sorted({str(int(k)) for k in gb.loc[gb.taxon_resolved, "accepted_key"].dropna()})
    wd = wikidata_by_gbif(keys)
    wd.to_csv(INT / "wikidata_plant_labels.csv", index=False)
    print(f"Wikidata: {len(wd)} taxa matched by GBIF id; with Hindi label {int((wd.wd_label_hi!='').sum())}, "
          f"Sanskrit label {int((wd.wd_label_sa!='').sum())}")
    rep = dict(names_total=len(all_names), names_from_ayurveda_sources=len(names),
               gbif_status_counts=src.gbif_status.value_counts().to_dict(),
               gbif_match_type_counts=src.gbif_match_type.value_counts().to_dict(),
               resolved_to_species_rate=round(float(src.taxon_resolved.mean()), 4),
               resolution_methods=src.resolution_method.str.replace(r":.*", "", regex=True).value_counts().to_dict(),
               still_unresolved=src[~src.taxon_resolved].name_in_source.tolist(),
               synonyms_resolved=int((src.gbif_status == "SYNONYM").sum()),
               wikidata_taxa=len(wd), wikidata_with_hindi=int((wd.wd_label_hi != "").sum()),
               wikidata_with_sanskrit=int((wd.wd_label_sa != "").sum()))
    (ROOT / "reports/taxonomy_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
