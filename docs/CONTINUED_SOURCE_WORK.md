# Source coverage and clean-environment follow-up

Work continued on 8 November 2026 (Asia/Calcutta), after pushing the 11 accumulated local commits through `e83be4d` to `codex/ayurkb-review-fixes`. The remote tip was verified; `main` was not changed. New work below is committed separately.

## Hindi-name and taxonomy source checks

`scripts/49_research_source_gaps.py` collected public, versioned Wikidata metadata for all **213** existing QIDs whose herb records lack a common Hindi label. Every one still lacks a primary Hindi label in the collected source response. Another **67** name-missing records have no existing QID. Therefore the current 186/466 common-Hindi-label coverage cannot be improved by merely refreshing those same identifiers. An existing Hindi alias is retained as an alias; it is not promoted to a primary common name without a decision.

Candidate Hindi labels require both the exact existing QID and a matching, non-deprecated GBIF identifier claim, plus Devanagari content. No English fallback, guessed QID or generated Hindi label is inserted. Source revision identifiers, retrieval times, response hashes and URLs are retained in [the source audit](../reports/source_gap_research/status.json) and its snapshots. Two regression checks exercise the identifier/script guard and deprecated-claim exclusion.

All **13** records with missing GBIF keys or family fields were also queried against GBIF. The returned matches are higher-rank matches (kingdom, family or genus), not established species identities. `status=ACCEPTED` at kingdom rank is not a successful identification: even “Ferrum haematite” returns an accepted Plantae-level fallback. Existing botanical IDs are not renumbered or merged, and no candidate name is promoted to the master table. See [taxonomy candidates](../reports/source_gap_research/taxonomy_gap_candidates.csv).

The source audit changes **zero canonical names** and supplies **zero expert approvals**. Remaining name and identity work requires additional source identifiers, botanical alignment evidence, or reviewed native-language labels; increasing filled-cell counts with invented values would not resolve the gaps.
