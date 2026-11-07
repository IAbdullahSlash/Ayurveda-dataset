# Source coverage and clean-environment follow-up

Work continued on 8 November 2026 (Asia/Calcutta), after pushing the 11 accumulated local commits through `e83be4d` to `codex/ayurkb-review-fixes`. The remote tip was verified; `main` was not changed. New work below is committed separately.

## Hindi-name and taxonomy source checks

`scripts/49_research_source_gaps.py` collected public, versioned Wikidata metadata for all **213** existing QIDs whose herb records lack a common Hindi label. Every one still lacks a primary Hindi label in the collected source response. Another **67** name-missing records have no existing QID. Therefore the current 186/466 common-Hindi-label coverage cannot be improved by merely refreshing those same identifiers. An existing Hindi alias is retained as an alias; it is not promoted to a primary common name without a decision.

Candidate Hindi labels require both the exact existing QID and a matching, non-deprecated GBIF identifier claim, plus Devanagari content. No English fallback, guessed QID or generated Hindi label is inserted. Source revision identifiers, retrieval times, response hashes and URLs are retained in [the source audit](../reports/source_gap_research/status.json) and its snapshots. Two regression checks exercise the identifier/script guard and deprecated-claim exclusion.

All **13** records with missing GBIF keys or family fields were also queried against GBIF. The returned matches are higher-rank matches (kingdom, family or genus), not established species identities. `status=ACCEPTED` at kingdom rank is not a successful identification: even “Ferrum haematite” returns an accepted Plantae-level fallback. Existing botanical IDs are not renumbered or merged, and no candidate name is promoted to the master table. See [taxonomy candidates](../reports/source_gap_research/taxonomy_gap_candidates.csv).

The source audit changes **zero canonical names** and supplies **zero expert approvals**. Remaining name and identity work requires additional source identifiers, botanical alignment evidence, or reviewed native-language labels; increasing filled-cell counts with invented values would not resolve the gaps.

## Material identity and ingredient categories

The historical `herbs` master now distinguishes **453 botanical taxon links**, **two source-identified non-botanical materials**, and **11 unresolved identities**. Source-linked category overrides identify mineral pitch (`HERB-0045`, Amidha `AMD-085`) and gairika/Ferrum haematite (`HERB-0189`, SAT-F.233 member 6). All 466 IDs and source names are preserved; no species or records were merged and no safety assessment was generated.

Three linked formulation-ingredient rows had incorrectly labeled these materials as `herb`. Their material IDs are retained, and their ingredient category is now `mineral/animal/other`: śilājatu in FORM-023 and FORM-024, and gairika in FORM-026. Previous ingredient records are preserved in [the classification audit](../reports/material_identity_status.json). The build pipeline reproduces the classification; export refuses contradictory material/ingredient categories.

The corpus, demo and generated indication-QA wording use materia-medica terminology where appropriate. The legacy table name `herbs` and ID prefix remain compatible. Safety-review batches expose material and taxon-identity scope and prioritize the non-botanical records for qualified review. Source category is not independent authentication of a physical preparation, species identification, safety approval or efficacy evidence.

Both herb embedding indexes were rebuilt, and all 12 base/fine-tuned indexes were checked against their current source/model hashes, finite arrays and unit norms. Updated classification, source references and scope are documented in the dictionary and datasheet.

## Chemistry coverage: six concrete alignment leads

`scripts/52_audit_chemistry_coverage.py` checks the existing Duke taxon and chemistry tables before acquiring new data. Of the 466 materia-medica records, 224 currently have chemistry and 242 do not. Those 242 comprise 229 botanical taxon links, 11 unresolved identities and the two non-botanical materials. None of their current master names occurs verbatim among Duke taxa with chemistry, so a simple exact-name join does not recover missing coverage.

Six records do have a recorded source-name variant present in Duke's chemistry layer:

| Current master record | Recorded variant with Duke observations | Candidate source rows |
|---|---|---:|
| HERB-0031, Anethum sowa | Anethum graveolens | 420 |
| HERB-0228, Hippophae tibetana | Hippophae rhamnoides | 65 |
| HERB-0152, Curcuma aromatica | Curcuma zedoaria | 49 |
| HERB-0412, Swertia chirayita | Swertia chirata | 25 |
| HERB-0035, Aquilaria malaccensis | Aquilaria agallocha | 18 |
| HERB-0138, Crateva magna | Crateva religiosa | 1 |

These counts are source observation rows, not independent compounds, clinical studies or verified synonym relationships. The Curcuma and Swertia source names also identify other published master records. Transferring their chemistry automatically could mix species or silently merge identities. The [protected chemistry review queue](../reports/source_gap_research/chemistry_gap_review.csv) therefore records source taxon IDs, compound counts, existing master-name collisions and blank decision fields. [Input hashes and summary](../reports/source_gap_research/chemistry_gap_status.json) make the audit reproducible.

No chemistry rows or biological aliases were added. Qualified botanical alignment can resolve these six leads before expanding searches to additional sources; the remaining gaps are not treated as evidence that the plants contain no chemicals.
