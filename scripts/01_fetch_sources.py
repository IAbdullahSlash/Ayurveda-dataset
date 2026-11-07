#!/usr/bin/env python3
"""
Stage 01 - Fetch all vetted, openly-available source datasets into data/raw/.

Every file gets a provenance record (URL, licence, retrieval time, SHA-256),
written to data/raw/PROVENANCE.json. Re-running is idempotent (use --force to refetch).

Sources (all vetted for licence + provenance, see docs/SOURCES.md):
  S1  NAMASTE National Ayurveda Morbidity Codes     Ministry of Ayush, Govt. of India
  S2  NAMASTE Standardised Ayurveda Terminologies    Ministry of Ayush, Govt. of India (SAT A-D, F-J)
  S3  WHO International Standard Terminologies on Ayurveda (2022)   CC BY-NC-SA 3.0 IGO
  S4  USDA-ARS Dr. Duke's Phytochemical & Ethnobotanical Databases  CC0 1.0
  S5  Amidha Ayurveda Herb Database v2.0 (Zenodo 10.5281/zenodo.20581467)  CC BY 4.0
"""
import argparse, hashlib, json, re, sys, time, datetime as dt
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ayurveda-open-dataset-builder/1.0"}

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def record(manifest, source_id, path, url, licence, publisher, note=""):
    manifest.append({
        "source_id": source_id, "file": path.relative_to(ROOT).as_posix(), "url": url,
        "licence": licence, "publisher": publisher, "note": note,
        "retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "bytes": path.stat().st_size, "sha256": sha256(path),
    })

def get(session, url, out: Path, force=False, method="GET", data=None, referer=None, timeout=300):
    if out.exists() and out.stat().st_size > 0 and not force:
        return out
    hdr = dict(UA)
    if referer:
        hdr["Referer"] = referer
    for attempt in range(4):
        try:
            r = session.request(method, url, data=data, headers=hdr, timeout=timeout)
            r.raise_for_status()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(r.content)
            return out
        except Exception as e:  # network hiccup -> exponential backoff
            if attempt == 3:
                raise
            print(f"   retry {attempt+1} {url}: {e}")
            time.sleep(2 ** (attempt + 1))

def csrf_from(html: str) -> str:
    m = re.search(r'name="_csrf" value="([^"]+)"', html)
    if not m:
        raise RuntimeError("CSRF token not found on NAMASTE page")
    return m.group(1)

def fetch_namaste(manifest, force):
    base = "https://namaste.ayush.gov.in/"
    lic = ("Government of India (Ministry of Ayush) public standard terminology; "
           "no explicit open licence published - reuse with attribution, verify before commercial use")
    s = requests.Session()
    # S1 morbidity codes (the public 'Download Excel' button on /ayurveda)
    page = s.get(base + "ayurveda", headers=UA, timeout=60).text
    out = RAW / "namaste" / "NATIONAL_AYURVEDA_MORBIDITY_CODES.xls"
    get(s, base + "ayurveda_morb_code_downexceldb_url", out, force, "POST",
        {"_csrf": csrf_from(page)}, base + "ayurveda")
    record(manifest, "S1", out, base + "ayurveda", lic, "Ministry of Ayush, Govt. of India (NAMASTE portal)")
    print("  S1 morbidity codes ok")
    # S2 SAT tables (public 'Download Excel' buttons on /sat_Ayurveda). SAT-E == morbidity codes (S1).
    page = s.get(base + "sat_Ayurveda", headers=UA, timeout=60).text
    tok = csrf_from(page)
    for sec in "abcdfghij":
        out = RAW / "namaste" / f"SAT_{sec.upper()}.xls"
        get(s, base + f"ayurveda_sat_{sec}_downexceldb_url", out, force, "POST", {"_csrf": tok}, base + "sat_Ayurveda")
        record(manifest, "S2", out, base + "sat_Ayurveda", lic, "Ministry of Ayush, Govt. of India (NAMASTE portal)",
               note=f"Standardised Ayurveda Terminologies section {sec.upper()}")
        print(f"  S2 SAT-{sec.upper()} ok")
        time.sleep(1)

def fetch_who(manifest, force):
    s = requests.Session()
    api = "https://iris.who.int/server/api"
    item = "82f0af4b-e7c5-4a56-a328-2f702b87336e"  # handle 10665/365543, ISBN 9789240064935
    out = RAW / "who" / "WHO_international_standard_terminologies_on_ayurveda_2022.pdf"
    if not out.exists() or force:
        bundles = s.get(f"{api}/core/items/{item}/bundles", headers=UA, timeout=60).json()
        orig = [b for b in bundles["_embedded"]["bundles"] if b["name"] == "ORIGINAL"][0]
        bs = s.get(orig["_links"]["bitstreams"]["href"], headers=UA, timeout=60).json()
        pdf = [b for b in bs["_embedded"]["bitstreams"] if b["name"].endswith(".pdf")][0]
        get(s, pdf["_links"]["content"]["href"], out, True)
    record(manifest, "S3", out, "https://iris.who.int/handle/10665/365543", "CC BY-NC-SA 3.0 IGO",
           "World Health Organization", note="ISBN 978-92-4-006493-5")
    print("  S3 WHO terminology ok")

def fetch_duke(manifest, force):
    s = requests.Session()
    meta = s.get("https://api.figshare.com/v2/articles/24660351", headers=UA, timeout=60).json()
    for f in meta["files"]:
        out = RAW / "usda_duke" / f["name"]
        get(s, f["download_url"], out, force)
        record(manifest, "S4", out, "https://doi.org/10.15482/USDA.ADC/1239279", meta["license"]["name"],
               "USDA Agricultural Research Service (Ag Data Commons)")
    print("  S4 Duke ok")

def fetch_amidha(manifest, force):
    s = requests.Session()
    base = "https://raw.githubusercontent.com/sciencewithsaucee-sudo/herb-database/main/"
    for name in ["herb.json", "LICENSE", "CITATION.cff", "README.md"]:
        out = RAW / "amidha_herb_db" / name
        get(s, base + name, out, force)
        record(manifest, "S5", out, "https://github.com/sciencewithsaucee-sudo/herb-database", "CC BY 4.0",
               "Amidha Ayurveda (S. Varshney), Zenodo 10.5281/zenodo.20581467")
    print("  S5 Amidha herb DB ok")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    manifest = []
    for fn in (fetch_namaste, fetch_who, fetch_duke, fetch_amidha):
        print(f"[{fn.__name__}]")
        fn(manifest, a.force)
    (RAW / "PROVENANCE.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(manifest)} provenance records -> data/raw/PROVENANCE.json")

if __name__ == "__main__":
    sys.exit(main())
