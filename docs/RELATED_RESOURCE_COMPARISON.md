# Preliminary comparison with related resources

Prepared 8 November 2026 (Asia/Calcutta). This is a bounded primary-publication comparison, not a completed systematic review or an independently reproduced census of the other databases. Public Europe PMC metadata and primary-publication abstracts were read; full abstracts and bulk database records are not redistributed here. [Search manifest](../reports/related_resources/search_manifest.json) and [publication metadata](../reports/related_resources/publications.json) record the evidence boundary.

## What can already be concluded

AyurKB cannot claim that integrating plants, phytochemicals, indications and formulations is itself new. IMPPAT and GRAYU provide relevant prior work. AyurKB's contribution should instead be evaluated around its particular NAMASTE/WHO terminology integration, disorder hierarchy and symptom representation, Hindi/Sanskrit access, explicit transformation/review states, and reproducible tooling. These are candidate differentiators: the absence of a feature from another paper's abstract does not establish its absence from the resource.

| Resource | Primary-publication scope | Relationship to AyurKB | What remains unverified |
|---|---|---|---|
| IMPPAT, original publication | Authors report 1,742 plants, 9,596 phytochemicals, 1,124 therapeutic uses; 27,074 plant–chemical and 11,514 plant–therapeutic associations. Includes chemical identifiers, structures and computed properties. | Establishes prior integrated plant/chemical/therapeutic data and computational drug-discovery use. It is the predecessor of IMPPAT 2.0, not an independent resource to double-count in coverage comparisons. | Current accessibility, redistribution terms, field-level overlap, terminology granularity, multilingual coverage and independently measured accuracy were not audited here. |
| IMPPAT 2.0 | Authors report 4,010 plants, 17,967 phytochemicals and 1,095 therapeutic uses, with plant-part associations and a stereo-aware chemical library. | Particularly relevant for chemistry and plant-part coverage. AyurKB currently has 466 herb records, a selected 1,959-chemical master and phytochemical links for 224 herbs. | Chemical selection, identity conventions and cohort differences prevent direct quality ratios. API/export permissions and a record-level comparison remain necessary. |
| GRAYU | Authors report 1,039 formulations, 12,743 plants, 129,542 phytochemicals and 13,480 indicated diseases; reported association counts span plants, chemicals, formulations and diseases. | Direct prior work on an integrative Ayurvedic graph. It should be included when explaining AyurKB's graph and formulation contribution. AyurKB currently has 43 formulations and 2,892 NAMASTE disorder/category/pattern records. | GRAYU disease entities cannot be assumed equivalent to NAMASTE codes. Counts need normalization, overlap analysis and inspection of source/validation practices before comparative superiority claims. |
| AyurKB, current working revision | Direct local counts: 43 tables, 180,899 rows, 466 herbs, 43 formulations, 2,892 disorder records, 11,082 symptoms and 4,790 generated QA pairs. Current indication links include 1,044 active source matches, with uncertain/quarantined targets retained separately. | Supports a testable integration contribution involving standardized terminology, symptoms, multilingual research access and transparent data engineering. | Independent semantic/language and clinical evaluation, source-use decisions, completeness and comparative utility remain open. |

The compared counts describe different units, inclusion criteria and versions. More rows, author-described manual curation or open web access do not establish higher accuracy, clinical validity, or permission to redistribute. In particular, GRAYU's publication also says outputs need contextual interpretation and further experimental validation; computational associations should not be presented as established clinical causality.

## Evidence-backed next comparison

1. Define the intended research tasks and a reference date before selecting comparable resource versions. Search additional terminology, formulation, classical-text and knowledge-graph resources systematically; broad discovery queries here were limited to the first page and were not exhaustive.
2. Verify live access, export/API terms, licence documents, version histories and source dependencies. Obtain permission before acquiring or redistributing restricted bulk content. Keep accessibility distinct from permission.
3. Compare botanical records using accepted names and external taxon IDs, and chemicals using structure-aware identifiers. Record synonym, stereochemistry and plant-part ambiguity rather than forcing matches.
4. Compare indications with relation breadth and terminology sense preserved. Do not equate a therapeutic-use string, a broad disease label and a NAMASTE subtype automatically.
5. Measure source and assertion overlap on a permitted sample. Separate shared upstream content from new curation and newly created relations, and retain provenance for each claimed addition.
6. Evaluate shared tasks on independent queries or adjudicated cases with the same candidate scope and baselines. Report uncertainty, missingness, language-specific failures and abstention, including negative results.
7. Rewrite novelty claims around demonstrated improvements. Current evidence supports a specific integration and tooling contribution; it does not support calling AyurKB the first, largest, most complete, most accurate or clinically validated Ayurveda knowledge base.

## Primary references

- **IMPPAT:** “IMPPAT: A curated database of Indian Medicinal Plants, Phytochemistry And Therapeutics.” PMID [29531263](https://pubmed.ncbi.nlm.nih.gov/29531263/), DOI [10.1038/s41598-018-22631-z](https://doi.org/10.1038/s41598-018-22631-z).
- **IMPPAT 2.0:** “IMPPAT 2.0: An Enhanced and Expanded Phytochemical Atlas of Indian Medicinal Plants.” PMID [36910986](https://pubmed.ncbi.nlm.nih.gov/36910986/), DOI [10.1021/acsomega.3c00156](https://doi.org/10.1021/acsomega.3c00156).
- **GRAYU:** “GRAYU: graph-based database integrating Ayurvedic formulations, medicinal plants, phytochemicals and diseases.” PMID [41657773](https://pubmed.ncbi.nlm.nih.gov/41657773/), DOI [10.3389/fphar.2025.1727224](https://doi.org/10.3389/fphar.2025.1727224).

Resource URLs reported by the publications are [IMPPAT](https://cb.imsc.res.in/imppat/) and [GRAYU](https://caps.ncbs.res.in/GRAYU/). Their live interfaces, current bulk exports and licence terms were not inspected in this bounded pass.
