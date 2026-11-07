#!/usr/bin/env python3
"""
Stage 11 - Multilingual semantic index (AI-ready layer).

Precomputes normalised sentence embeddings (intfloat/multilingual-e5-small, 384-d, MIT) for every symptom,
disease, herb and terminology record.  A query in English, Hindi or romanised Sanskrit can then be matched
semantically ('loss of appetite' ~ 'tastelessness' / 'diminution of agni'; 'बुखार' ~ 'fever').
Output: release/embeddings/<entity>.npy (float16) + <entity>_ids.csv
"""
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib import import_module
E5 = import_module("10_crosslingual").E5
from lib.embedding_integrity import record_index, verify_index
from lib.export_transaction import export_lock

ROOT = Path(__file__).resolve().parents[1]
P, OUT = ROOT / "data/processed", ROOT / "release/embeddings"
OUT.mkdir(parents=True, exist_ok=True)
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)

def main(part="all", model=None, out=None, threads=3, force=False):
    folder=Path(out) if out else OUT
    folder.mkdir(parents=True,exist_ok=True)
    with export_lock(folder / '.embedding.lock'):
        return build_indexes(part,model,out,threads,force)

def build_indexes(part="all", model=None, out=None, threads=3, force=False):
    global OUT
    if out:
        OUT = Path(out); OUT.mkdir(parents=True, exist_ok=True)
    enc = E5(threads=threads, model=model)
    (OUT / "MODEL.txt").write_text(str(enc.path.relative_to(ROOT) if enc.path.is_relative_to(ROOT) else enc.path) + "\n", encoding="utf-8")
    s, d, h, t = rd("symptoms"), rd("diseases"), rd("herbs"), rd("terminology")
    hindi = {}
    if "gloss_hi" in s.columns:          # Hindi-side indices (after 06 --merge): Hindi query -> Hindi passage
        hindi = {
            "symptoms_hi": (s.symptom_id, (s.gloss_hi + " (" + s.term_sa_deva + ")").str.replace(r"\s*\(\)$", "", regex=True)),
            "diseases_hi": (d.disease_id, (d.term_deva + " " + d.term_hi + ". " + d.get("name_en_hi", "") + ". " + d.get("definition_hi", "").str.slice(0, 300))),
        }
    if part == "hi":
        sets = hindi
    else:
        sets = {
        "symptoms": (s.symptom_id, (s.gloss_en + " (" + s.term_sa_iast + ")").str.replace(r"\s*\(\)$", "", regex=True)),
        "diseases": (d.disease_id, ((d.name_en_who.where(d.name_en_who != "", d.name_en)) + " (" + d.term_iast + "). " + d.definition_en.str.slice(0, 300))),
        "herbs": (h.herb_id, (h.name_sa_iast.where(h.name_sa_iast != "", h.name_ascii) + " " + h.accepted_name + " " + h.name_en + ". " + h.description_en)),
        "terminology": (t.term_uid, (t.term_en + " (" + t.term_sa_iast_primary + "). " + t.definition_en.str.slice(0, 300))),
        }
        if part == "all":
            sets.update(hindi)
    for name, (ids, texts) in sets.items():
        if not force and (OUT / 'manifest.json').exists():
            try:
                verify_index(OUT,name,enc.path,P / f"{name.removesuffix('_hi')}.csv")
            except (ValueError,OSError,KeyError):
                pass
            else:
                print(f"  {name}: reusing verified model/source index",flush=True)
                continue
        t0 = time.time()
        X = enc.encode(texts.tolist(), "passage: ").astype(np.float16)
        np.save(OUT / f"{name}.npy", X)
        pd.DataFrame({"id": ids, "text": texts}).to_csv(OUT / f"{name}_ids.csv", index=False)
        record_index(OUT,name,enc.path,P / f"{name.removesuffix('_hi')}.csv")
        print(f"  {name:12s} {X.shape}  {time.time() - t0:.0f}s", flush=True)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="all", choices=["all", "en", "hi"],
                    help="en = English/IAST indices, hi = Hindi indices (needs 06 --merge), all = both")
    ap.add_argument("--model", default=None, help="encoder directory (default: models/multilingual-e5-small)")
    ap.add_argument("--out", default=None, help="output directory (default: release/embeddings)")
    ap.add_argument("--threads",type=int,default=3)
    ap.add_argument("--force",action="store_true",help="rebuild after changes to the encoding recipe")
    a = ap.parse_args()
    main(a.part, a.model, a.out, a.threads, a.force)
