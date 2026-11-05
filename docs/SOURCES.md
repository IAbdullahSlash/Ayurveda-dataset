# Source vetting

The brief was to use **authorized, good-quality sources only**. Every candidate below was checked for
(1) an explicit licence or public-sector publication terms, (2) traceable provenance (publisher, DOI or
official URL), (3) actual content quality (spot checks, internal consistency, comparison with other
sources). Raw files are kept unchanged in `data/raw/` with SHA-256 checksums in `data/raw/PROVENANCE.json`.

## Accepted

| ID | Source | Publisher | Licence / terms | Used for |
|----|--------|-----------|-----------------|----------|
| S1 | NAMASTE National Ayurveda Morbidity Codes (2,910 codes) | Ministry of Ayush, Govt. of India | Public national standard; attribution. No explicit open licence is stated on the portal, so verify before commercial reuse. | diseases, hierarchy, ICD-11 TM2 links, clinical definitions, symptoms |
| S2 | NAMASTE Standardised Ayurveda Terminologies, SAT A–J (12,080 terms) | Ministry of Ayush, Govt. of India | as S1 | fundamentals, anatomy, diagnosis, 9,400-entry symptom lexicon, official plant list, Caraka's 50 mahākaṣāya, karma, pharmaceutics, diet, treatment, prevention |
| S3 | WHO international standard terminologies on Ayurveda (2022), ISBN 978-92-4-006493-5 (3,554 terms) | World Health Organization | CC BY-NC-SA 3.0 IGO | bilingual terminology (English, IAST, Devanagari), diagnostic methods, Prakṛti traits, therapies |
| S4 | Dr. Duke's Phytochemical and Ethnobotanical Databases | USDA Agricultural Research Service | CC0 1.0 | phytochemicals per plant part, chemical bioactivities, Indian ethnobotanical uses |
| S5 | Amidha Ayurveda Herb Database v2.0 (360 herbs), Zenodo DOI 10.5281/zenodo.20581467 | S. Varshney (Uttarakhand Ayurved University affiliation) | CC BY 4.0 | rasa, guṇa, vīrya, vipāka, karma, doṣa effects, indications |
| S6 | Wikidata | Wikimedia | CC0 1.0 | Hindi / Sanskrit common names of plant taxa |
| S7 | GBIF Backbone Taxonomy (species match + search API) | GBIF | CC BY 4.0 | validating botanical names, resolving synonyms |
| S8 | PubMed (NCBI E-utilities) | US National Library of Medicine | public domain (counts are facts) | literature evidence counts |
| S9 | ClinicalTrials.gov API v2 | US National Library of Medicine | public domain | registered clinical trials per herb / formulation |
| S10 | Europe PMC REST API: Ayurveda case reports and case series (565 records; 374 open-access full texts mined) | EMBL-EBI | metadata freely reusable; text mining of the open-access subset permitted; per-article licence recorded. Only identifiers, titles and extracted KB entities are stored, never article text | real-world validation (E6), practice patterns, adverse-event signals |
| S11 | PubChem PUG REST | US National Library of Medicine | public domain | CID, InChIKey, formula, SMILES of key phytochemicals |
| S12 | MED117 (DOI 10.17632/dtvbwrhznz.4), Medicinal Leaf Dataset (10.17632/nnytj2v3n5.1), Indian Medicinal Leaves (10.17632/748f8jkphb.3) | Mendeley Data (dataset authors) | CC BY 4.0 | species-level links to plant-image datasets (class labels only; no images copied) |
| S13 | WHO ICTRP (includes CTRI, India) - optional manual export | World Health Organization | ICTRP terms: free download from the Search Portal, non-commercial use, attribution, keep current, show processing date. robots.txt forbids automated crawling, so the importer only reads a CSV the user exported by hand | Indian trial registrations (optional stage 19) |
| (separate) | ChEMBL (EMBL-EBI) human single-protein targets, pChEMBL >= 6 | EMBL-EBI | CC BY-SA 3.0 - share-alike, so kept OUT of the CC BY-NC-SA core in `release/chembl/` with its own licence file. Built for 195 compounds: 323 compound-target links (62 compounds, 196 human proteins); kept out of git, rebuilt with `scripts/17_phytochem_ids.py --chembl-only` | protein targets of phytochemicals |
| S0 | Curated layer of this project (`curation/`) | this project | CC BY 4.0; classical texts cited are public domain | controlled vocabulary, EN→HI glossary, diagnostic-method correspondences, herb safety, 43 classical formulations, Prakṛti questionnaire, taxonomy overrides |

## Rejected (and why)

| Candidate | Reason |
|-----------|--------|
| Hugging Face `Tweaks/Ayurvedic_QA` (82k Q&A, "apache-2.0") | Appears LLM-generated from copyrighted books; contains off-topic items (e.g. quandong oil in rats), book-metadata questions and 518 duplicate questions. Fails the "authorized and good" test. |
| Hugging Face `ASR01/ayurvedic-remedies` | Gated: login and access approval required; contents could not be verified. |
| Hugging Face `bhumika-tewari-282006/ayurvedic-affinity-training-data` | PDBbind protein–ligand complexes, not Ayurvedic compounds; its "Ayurvedic" features are mostly default values. |
| Hugging Face `abaditya26/prakriti`, `Macromrit/...`, `AmareshHebbar/...` | No data files available. |
| IMPPAT 2.0 (IMSc Chennai) | High quality, but licensed CC BY-NC-ND 4.0. *No-derivatives* forbids redistributing a transformed or merged version. Referenced only. |
| Kaggle Ayurveda datasets | Downloads require an authenticated Kaggle account. Most list an "Unknown" licence or no provenance, and several are visibly synthetic. |
| Unlicensed GitHub repositories (formulation lists, knowledge graphs) | No licence, so no right to reuse. |
| CTRI (Clinical Trials Registry - India) direct harvesting | No public API; the WHO ICTRP portal that aggregates CTRI disallows crawling. Supported only through a manual ICTRP export (S13). |
| Ayurvedic Pharmacopoeia / Formulary of India PDFs | Government publications without an open licence. Cited as the verification reference for the curated formulations; not ingested. |

## Licence of the combined release

The integrated release contains WHO-derived content (CC BY-NC-SA 3.0 IGO), so **the combined dataset is
distributed under CC BY-NC-SA** (non-commercial, share-alike). Every row carries `source_id` and `licence`
columns, so a commercial-safe subset can be cut by excluding `S3` rows and NLLB machine translations
(NLLB-200 weights are CC BY-NC 4.0). NAMASTE content (S1, S2) is a Government of India public standard
published for adoption by health systems; keep the attribution and check its terms for commercial products.

## Permission requests

Letters asking for licences or machine-readable data from PCIM&H (API/AFI), the Ministry of Ayush NAMASTE team,
WHO, the IMPPAT team and CCRAS are in `docs/permission_requests/`. Nothing from those sources is included until a
written permission is on file.
