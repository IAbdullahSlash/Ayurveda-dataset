#!/usr/bin/env python3
"""Add exact source locators where the inputs already record them.

terminology.source_locator     WHO terms: term ID and PDF page of the WHO ITA 2022 book (from the stage 02a parse);
                               NAMASTE SAT terms: the SAT code.
diseases.definition_locator    where the definition text comes from: the NAMASTE morbidity code, or the linked WHO term
                               and its PDF page for definitions filled from WHO (stage 25). Blank when there is no
                               definition.

Nothing is inferred: a locator is written only when the parsed source records it. Idempotent; run after stage 25.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
WHO_BOOK = "WHO ITA 2022"


def who_pages():
    who = pd.read_csv(ROOT / "data/interim/who_terms.csv", keep_default_na=False, dtype=str)
    if who.term_id.duplicated().any():
        raise ValueError("Duplicate WHO term IDs in data/interim/who_terms.csv")
    return dict(zip(who.term_id, who.page))


def who_locator(term_id, pages):
    page = pages.get(term_id, "")
    return f"{WHO_BOOK}, {term_id}, PDF p. {page}" if page else ""


def terminology_locators(t, pages):
    def one(r):
        if r.source_id == "S3":
            return who_locator(r.source_code, pages)
        if r.source_id == "S2" and r.source_code:
            return f"NAMASTE {r.source_code}"
        return ""
    return [one(r) for r in t.itertuples()]


def definition_locators(d, pages):
    def one(r):
        if not r.definition_en:
            return ""
        if r.definition_source.startswith("WHO"):
            return who_locator(r.who_term_id.split(";")[0], pages)
        if r.definition_source == "NAMASTE" and r.namc_code_clean:
            return f"NAMASTE morbidity code {r.namc_code_clean}"
        return ""
    return [one(r) for r in d.itertuples()]


def write(df, name):
    df.to_csv(P / f"{name}.csv", index=False)
    parquet = P / f"{name}.parquet"
    if parquet.exists():
        df.astype({c: str for c in df.columns if df[c].dtype == object}).to_parquet(parquet, index=False)


def main():
    pages = who_pages()
    t = pd.read_csv(P / "terminology.csv", keep_default_na=False, dtype=str)
    d = pd.read_csv(P / "diseases.csv", keep_default_na=False, dtype=str)
    t["source_locator"] = terminology_locators(t, pages)
    d["definition_locator"] = definition_locators(d, pages)
    missing_who = int(((t.source_id == "S3") & (t.source_locator == "")).sum())
    if missing_who:
        raise SystemExit(f"{missing_who} WHO terms have no page in the stage 02a parse")
    write(t, "terminology")
    write(d, "diseases")
    report = {"terminology_with_locator": int((t.source_locator != "").sum()), "terminology_rows": len(t),
              "definitions_with_locator": int((d.definition_locator != "").sum()),
              "definitions": int((d.definition_en != "").sum())}
    print(json.dumps(report))


if __name__ == "__main__":
    sys.exit(main())
