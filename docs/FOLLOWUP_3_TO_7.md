# Follow-up on remaining items 3–7

Clinical/safety review and permissions review were excluded from this batch.

- Hindi: 11 malformed or inaccurate terminology definitions were replaced with source-checked AI post-edits, propagated to three derived records. Old text, English source and source hashes are preserved in `curation/hindi_definition_postedits.csv`. Every correction remains `expert_review_pending`; these are not independent language approvals.
- Extraction: the Prameha coordination defect is repaired in the processed graph, with the complete source phrase retained and a corresponding Hindi gloss. Legacy symptom IDs remain available to other layers. The remaining 211 candidate disorder changes require semantic adjudication; no blanket approval was manufactured.
- Provenance: recorded herb properties resolve to Amidha IDs and Hindi common names to Wikidata QIDs where those references exist. Unknown historical attribution remains explicit.
- Content gaps: all 873 undefined disorders were checked against their existing WHO links. None has an available definition in that linked record. The 122 missing herb-property records require additional source material. See the gap-evidence CSVs under `reports/revision_audit/`.
- Independent validation: `python scripts/30_evaluation_manifest.py --external-cases FILE.csv` checks annotation completeness, distinct reviewer IDs and overlap with internal publication identifiers/titles. Passing this check does not certify reviewer qualifications or case independence beyond the available metadata. No new independently adjudicated cases were supplied, so no external accuracy is reported.
- Semantic reruns: the current enforced network policy still excludes huggingface.co. The previously saved draft remains unapplied. The pinned models cannot be downloaded until the environment settings change; no alternative route was used to bypass the policy.

The remaining language review, semantic adjudication, genuinely new annotated cases and model-host access cannot be supplied by automated code changes alone. Current tests and exports are regenerated with the applied repairs.
