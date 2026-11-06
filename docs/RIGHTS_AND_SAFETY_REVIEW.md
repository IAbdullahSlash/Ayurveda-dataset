# Rights and safety review handoff

`curation/source_rights_review.csv` records the terms reported by the repository and their known retrieval dates. Every approval field is intentionally blank. A source's open-licence label, authoritative status, or presence in a repository does not substitute for a rights assessment of a combined or transformed export. Draft permission letters in `docs/permission_requests/` are not evidence of permission granted.

The processed release contains text, not only identifiers: case titles, presenting-symptom phrases, and 1,539 semantic-matching rows containing extracted clauses, as well as descriptions and translations from other sources. `reports/revision_audit/text_inventory.csv` inventories all text-bearing columns. Preserve article IDs and per-article licence fields when assessing the case-derived tables. An exclusion decision must be applied to the CSV, corpus, SQLite, review materials and archive together and then tested. No text was silently removed by this revision.

A qualified rights reviewer should record: source, exact permission/terms document, retrieval date, allowed use and redistribution, transformation requirements, attribution, and any restrictions. Assess model weights, model use and generated translations separately. No commercial-safe subset is certified by source-ID filtering.

Safety data is selective. All 466 herbs require an explicit assessment state; blank classifications remain unassessed. The demo now displays that state and preserves populated hazard flags. Populated flags have not been independently adjudicated. Literature tiers are retrieval signals, with no encoded claim of efficacy. The demo continues to exclude iatrogenic-complication relations from indicated procedures.

Clinical reviewers should prioritize flagged toxic herbs, metal-containing formulations and commonly displayed remedies; record preparation/plant-part scope, contraindications, interactions, source references, reviewer qualifications, disagreements, adjudication and date. Do not infer safe use from blank fields or absent literature.
