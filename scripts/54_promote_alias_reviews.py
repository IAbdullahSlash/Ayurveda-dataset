#!/usr/bin/env python3
"""Copy reviewer-signed rows from the AI pre-review into the indication alias ledger.

reports/indication_review/ai_prereview.csv holds AI-drafted suggestions; the indication policy never
reads it. A row reaches curation/indication_aliases.csv only when a reviewer has filled in
reviewer_verdict, reviewer and reference:

  confirm  accept the suggested disorder (suggestion accept, accept_replacement or needs_expert)
  change   accept reviewer_disease_id instead of the suggestion
  reject   record a rejected alias, which keeps the link switched off

Rows left blank, and confirmations of no_target suggestions, are skipped. An existing ledger row is
never changed unless --replace is given.

  python scripts/54_promote_alias_reviews.py --dry-run
  python scripts/54_promote_alias_reviews.py

Afterwards run stage 44 (reapply the policy), stage 15 for literature on newly accepted pairs
(network), stage 45 (refresh evidence) and stage 08 (export).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I omits the script folder
from lib.indication_policy import alias_key, validated_aliases

ROOT = Path(__file__).resolve().parents[1]
PREREVIEW = ROOT / "reports/indication_review/ai_prereview.csv"
LEDGER = ROOT / "curation/indication_aliases.csv"
FIELDS = ["indication_raw", "disease_id", "decision", "relation", "reviewer", "reference"]


def ledger_rows(prereview, disease_ids):
    """Turn signed pre-review rows into ledger rows; raise on an incomplete or invalid signature."""
    rows, skipped = [], 0
    for r in prereview.to_dict("records"):
        verdict = r["reviewer_verdict"].strip().lower()
        if not verdict:
            skipped += 1
            continue
        if verdict not in {"confirm", "change", "reject"}:
            raise ValueError(f"{r['indication_raw']}: reviewer_verdict must be confirm, change or reject")
        if not r["reviewer"].strip() or not r["reference"].strip():
            raise ValueError(f"{r['indication_raw']}: a verdict needs both reviewer and reference")
        if verdict == "confirm" and r["suggestion"] == "no_target":
            skipped += 1          # nothing to record: the term stays unmatched
            continue
        if verdict == "reject":
            did, decision, relation = r["suggested_disease_id"], "rejected", ""
        else:
            did = r["suggested_disease_id"] if verdict == "confirm" else r["reviewer_disease_id"].strip()
            decision, relation = "accepted", "equivalent"
            if did not in disease_ids:
                raise ValueError(f"{r['indication_raw']}: disorder {did or '(blank)'} does not exist")
        rows.append(dict(indication_raw=r["indication_raw"], disease_id=did, decision=decision, relation=relation,
                         reviewer=r["reviewer"].strip(), reference=r["reference"].strip()))
    return pd.DataFrame(rows, columns=FIELDS), skipped


def merge(ledger, new, replace=False):
    """Add new decisions to the ledger; refuse to overwrite a different existing decision."""
    current = {alias_key(r["indication_raw"]): r for r in ledger.to_dict("records")}
    added = changed = 0
    for r in new.to_dict("records"):
        key = alias_key(r["indication_raw"])
        old = current.get(key)
        if old == r:
            continue
        if old is not None and not replace:
            raise ValueError(f"{r['indication_raw']}: the ledger already holds a different decision; use --replace")
        added += old is None
        changed += old is not None
        current[key] = r
    return pd.DataFrame(list(current.values()), columns=FIELDS), added, changed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="report what would change without writing")
    ap.add_argument("--replace", action="store_true", help="allow changing an existing ledger decision")
    args = ap.parse_args()
    diseases = set(pd.read_csv(ROOT / "data/processed/diseases.csv", keep_default_na=False, dtype=str).disease_id)
    prereview = pd.read_csv(PREREVIEW, keep_default_na=False, dtype=str)
    ledger = pd.read_csv(LEDGER, keep_default_na=False, dtype=str)
    new, skipped = ledger_rows(prereview, diseases)
    merged, added, changed = merge(ledger, new, args.replace)
    validated_aliases(merged, diseases)       # the policy's own checks, before anything is written
    print(f"signed rows: {len(new)}  (added {added}, changed {changed}); unsigned or no-target rows skipped: {skipped}")
    if args.dry_run or not (added or changed):
        print("ledger not written" + (" (dry run)" if args.dry_run else " (no changes)"))
        return
    merged.to_csv(LEDGER, index=False, encoding="utf-8")
    print(f"wrote {LEDGER.relative_to(ROOT).as_posix()}: {len(merged)} decisions")
    print("next: stage 44, then stage 15 for new pairs (network), stage 45 and stage 08")


if __name__ == "__main__":
    main()
