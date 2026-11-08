# Indication mapping pre-review

[`reports/indication_review/ai_prereview.csv`](../reports/indication_review/ai_prereview.csv) holds AI-drafted recommendations for the herb → disorder mappings that the indication policy has switched off. It is a starting point for a qualified reviewer, not a decision. **No link changes until a reviewer signs a row and stage 54 copies it into the alias ledger.** The indication policy never reads the pre-review file.

Drafted on 8 November 2026 by Claude (Anthropic) from the NAMASTE entries, their definitions and parent categories, and the herbs that carry each indication.

## What it covers

| Suggestion | Groups | Rows | Meaning |
|---|---:|---:|---|
| `accept` | 35 | 453 | The suggested disorder is the same sense as the source term. Covers the 19 ambiguous duplicates, the 14 correct fuzzy matches and clear unmatched terms such as Agnimandya, Grahani and Pandu. |
| `accept_replacement` | 9 | 49 | A correct target for a quarantined wrong match, for example Kantharoga → disorders of the throat instead of ear diseases. |
| `needs_expert` | 3 | 3 | A leaning is given, but a clinical decision is needed (the three spellings of *śukrakṣaya*). |
| `no_target` | 3 | 28 | NAMASTE has no matching disorder; the term should stay unmatched (Yakrit Roga, Malabaddhata, Vibandha). |

Confidence is high for 33 groups, medium for 13 and low for 4. If a reviewer confirmed every `accept` and `accept_replacement`, active links would rise from 1,044 to 1,546 of 1,693, every quarantined row would get a correct target, and 144 rows would stay unmatched.

**Why most "ambiguous" matches are not really ambiguous.** NAMASTE lists many disorders twice: once in the single-doṣa (*nānātmaja*) lists, for example "jaundice (due only to pittadōṣa)", and once as the general clinical entry with a full definition. A plain herb indication such as *Kāmalā* means the general disorder, so the suggestion picks that entry. Two groups are true spelling collisions with unrelated disorders (Gandamala, Krimi).

## Where to look first

These groups have medium or low confidence, or carry the most rows:

| Term | Rows | Suggestion | Point to decide |
|---|---:|---|---|
| Kshaya | 32 | rājayakṣmā (AYD-00420) | Consumption, or general dhātu depletion? |
| Daha | 46 | dāhaḥ, rakta-channel entry (AYD-01054) | This entry, or the pitta-list entry AYD-00285? |
| Pradara | 14 | asṛgdara (AYD-01392) | Should śvetapradara be split off? |
| Anaha | 9 | ādhmānam (AYD-00147) | NAMASTE has no separate ānāha parent |
| Raktadosha | 6 | raktavaiṣamyam (AYD-00387) | Pattern-level target acceptable? |
| Kapha Roga, Kaphaja Roga | 3 + 3 | śleṣmavikāraḥ (AYD-00318) | Category-level target acceptable? |
| Kshata | 3 | uraḥkṣata/kṣatakṣīṇa (AYD-00511) | Or a wound (vraṇa, AYD-01913)? |
| Vidradhi | 3 | general abscess (AYD-01221) | Or internal vidradhi (AYD-00972)? |
| Udavarta | 2 | udāvartaḥ (AYD-00656) | Definition fits; English label "volvulus" is misleading |
| Śukrakṣaya (3 spellings) | 3 | dhātu-depletion pattern (AYD-00407) | Or oligospermia (AYD-00114)? |

Each row of the CSV gives the rationale and the alternatives that were considered.

## How to review

Fill in these columns for each row you decide. Leave a row blank to skip it.

| Column | Value |
|---|---|
| `reviewer_verdict` | `confirm` (accept the suggested disorder), `change` (accept a different disorder), or `reject` (keep the link off) |
| `reviewer_disease_id` | Only for `change`: the disorder ID you accept instead |
| `reviewer` | Your name or reviewer ID |
| `reference` | The text or source that supports the decision, for example a Saṃhitā locator or the API monograph |
| `reviewer_comment` | Optional |

Then copy signed rows into the ledger and refresh the data:

```bash
python scripts/54_promote_alias_reviews.py --dry-run
python scripts/54_promote_alias_reviews.py
python scripts/44_review_indication_matching.py
python scripts/15_link_evidence.py
python scripts/45_refresh_indication_derivatives.py
python scripts/08_validate_export.py
```

Stage 54 refuses a verdict without both `reviewer` and `reference`, refuses unknown disorder IDs, and never changes an existing ledger decision unless `--replace` is given. Stage 15 needs network access to fetch literature for newly accepted pairs. `scripts/53_build_indication_prereview.py` regenerates the CSV and refuses to overwrite it once any reviewer field is filled.
