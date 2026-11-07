# Export provenance contract

Stage 08 exports `release/ayurkb_provenance.jsonl`, one content-addressed record per processed CSV row, and embeds the same contract in corpus documents. All 43 tables have conservative source dependencies. Source terms are copied from the versioned sources table, not interpreted as legal permission.

`default_field_attribution=conservative_record_dependencies` means the listed sources support the construction of the record collectively. It does **not** claim each source independently supports every field. `field_overrides` refines attribution where the pipeline records it; WHO-filled disease definitions resolve to S3 and their WHO term IDs. Hindi overrides retain transformation and quality flags. Unmapped new tables or source IDs are exposed as `unresolved`, never silently approved.

`source_record_ids` includes referenced KB records. `record_ref` is a SHA-256 content address of the original row, so it changes with content and does not replace stable entity IDs. Metadata inheritance is defined in `scripts/lib/provenance.py` and tested over every processed row. Broad source dependencies are deliberately conservative; exact assertion-level historical attribution cannot be recovered where upstream input lacks it.

Every record retains an explicit review state and `rights_status=requires_review`. No filtering operation in this module certifies a commercial-safe subset. Such a release needs field-specific source review and independently recorded permission decisions.

Indication mapping overrides distinguish `active_target`, `historical_target` and `candidate_targets`. Only the active target is a current link; proposed and historical IDs support audit history. Decision references, reasons, review states and policy version are retained in the sidecar. A PDF-reported error is evidence for containment, not a qualified approval of another target. Alias decisions require their own reviewer and source reference. Exact upstream indication attribution remains conservative where the original record was not captured.

Herb safety metadata separates assessment state from hazard class and preserves the supplied reference and scope. A blank review ledger cannot produce an assessed state. An assessed state is bounded by its recorded scope and is never a claim of universally safe use.
