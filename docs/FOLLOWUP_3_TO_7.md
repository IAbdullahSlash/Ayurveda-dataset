# Follow-up on remaining items 3–7

**Current status:** network access is now active and computational reruns are complete. Earlier blocker descriptions below are historical; see [network-enabled work](NETWORK_ENABLED_WORK.md).

Clinical/safety review and permissions review were excluded from this batch.

- Hindi: 11 malformed or inaccurate terminology definitions were replaced with source-checked AI post-edits, propagated to three derived records. Old text, English source and source hashes are preserved in `curation/mt_field_corrections.csv` (formerly `hindi_definition_postedits.csv`). Every correction remains `expert_review_pending`; these are not independent language approvals.
- Extraction: the Prameha coordination defect is repaired in the processed graph, with the complete source phrase retained and a corresponding Hindi gloss. Legacy symptom IDs remain available to other layers. The remaining 211 candidate disorder changes require semantic adjudication; no blanket approval was manufactured.
- Provenance: recorded herb properties resolve to Amidha IDs and Hindi common names to Wikidata QIDs where those references exist. Unknown historical attribution remains explicit.
- Content gaps: all 873 undefined disorders were checked against their existing WHO links. None has an available definition in that linked record. The 122 missing herb-property records require additional source material. See the gap-evidence CSVs under `reports/revision_audit/`.
- Independent validation: `python scripts/30_evaluation_manifest.py --external-cases FILE.csv` checks annotation completeness, distinct reviewer IDs and overlap with internal publication identifiers/titles. Passing this check does not certify reviewer qualifications or case independence beyond the available metadata. No new independently adjudicated cases were supplied, so no external accuracy is reported.
- Semantic reruns: blocked at the time because the model host could not be reached; since completed with the pinned models (see [network-enabled work](NETWORK_ENABLED_WORK.md)).

The remaining language review, semantic adjudication, genuinely new annotated cases and model-host access cannot be supplied by automated code changes alone. Current tests and exports are regenerated with the applied repairs.


## Continued work after the progress push

The accumulated branch was pushed through `4fb526f` to `codex/ayurkb-review-fixes`. Later work adds ten further source-checked Hindi post-edits (21 terminology definitions in total), including the weaning/abortion and atrophy/instability errors; all retain unreviewed status. All 119 undefined linked WHO entries were located in the original PDF and indexed with page numbers and source excerpts. The empty definition cells are not filled by inventing prose from names.

`35_collect_external_candidates.py` prepares a metadata-only, overlap-filtered publication pool with blank annotation fields. Its first live request could not reach Europe PMC; the full query has since run (see [network-enabled work](NETWORK_ENABLED_WORK.md)).

`36_reassess_translation_flags.py` distinguishes consecutive decoding loops from distributed repetition without clearing original flags or approving translations. This avoids treating an ordinary list such as head/shoulder/eye/chest pain as proof of a decoding loop. Review priority is improved while language validation remains explicit.
