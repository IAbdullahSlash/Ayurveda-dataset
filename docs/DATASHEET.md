# Datasheet: AyurKB v1.2

Structured after *Datasheets for Datasets* (Gebru et al., 2021).

## 1. Motivation

**Purpose.** AyurKB provides one clean, linked, bilingual (English / Hindi, with Sanskrit in IAST and
Devanagari) knowledge base for building Ayurveda expert systems, decision-support tools, search and
question-answering systems, and for machine-learning research on traditional medicine.

**Gap addressed.** Openly licensed Ayurveda data is scattered across official terminology portals, a WHO
publication, botanical and phytochemical databases and a few community datasets. They use different
romanisations ("kuṣṭham", "Kushta", "kuShTham"), outdated botanical names and inconsistent encodings, and
none links diagnosis, materia medica, remedies and modern evidence together.

**Created by.** Assembled reproducibly by the scripts in `scripts/` from the sources listed in
`docs/SOURCES.md`.

## 2. Composition

| Layer | Tables | Origin |
|---|---|---|
| Diagnosis | `diseases` (2,892 NAMASTE codes, 789 with ICD-11 TM2 codes, 1,188 linked to WHO terms), `symptoms` (11,081), `disease_symptom` (11,880 edges), `diagnostic_methods` (43) | authoritative + curated |
| Terminology | `terminology` (6,233 WHO + SAT terms), `therapies` (1,325), `pharmaceutics` (393), `diet_lifestyle` (381), `controlled_vocabulary` (135) | authoritative |
| Materia medica | `herbs` (466), `herb_names` (3.6k), `herb_indication` (1,693), `herb_karma` (829), `herb_groups` (50 mahākaṣāya), `herb_group_members` (500) | authoritative + community + linked open data |
| Remedies | `formulations` (43 classical), `formulation_ingredients` (500), `formulation_indications` (155), plus herb indications, therapies, diet & lifestyle | curated (flagged) + authoritative |
| Modern science | `herb_phytochemicals` (23.8k), `phytochemical_activities` (13.5k), `herb_ethnobotany` (2.9k), `clinical_trials` (6.4k links / 5.3k trials), `evidence_queries`, `therapy_evidence` | authoritative (USDA, NLM) |
| ML / AI-ready | `qa_pairs` (bilingual Q&A), `prakriti_synthetic_cohort` (3,000, synthetic), `release/ayurkb_corpus.jsonl`, `release/embeddings/` | derived / synthetic |

**Hybrid by design.** The dataset mixes:
- authoritative standards, community-curated open data, linked open data and modern evidence;
- record types: categorical, text, graph edges, numeric (ppm, counts) and multilingual text;
- real records and clearly labelled synthetic or derived records. Every row has a `data_origin` column.

**Languages.** English. Sanskrit in IAST and Devanagari. Hindi comes from four routes:
- the Hindi usage form of each Sanskrit term (rule-based);
- Wikidata Hindi plant names;
- **composed** Hindi disorder definitions, built from Devanagari symptom terms and their translated
  symptom glosses, with only the explanatory sentence machine-translated;
- machine-translated descriptions (NLLB-200 with glossary injection).

Every Hindi field is marked by its `*_method` and `*_qe_flags` columns.

**Identifiers.** Stable prefixed ids: `AYD-`, `SYM-`, `HERB-`, `FORM-`, `DX-`, `WHO:ITA-…`, `SAT:SAT-…`.
Source codes (NAMASTE, ICD-11 TM2, WHO ITA, GBIF keys, Wikidata QIDs, NCT ids) are kept for linking.

**Sensitive data.** None. There are no patient records. The Prakṛti cohort is simulated.

**Extension layers (v1.1).** Real-world layer from 565 published Ayurveda case reports (Europe PMC; 450 therapeutic,
115 adverse-event); PubMed evidence tiers for 1,427 herb and 121 formulation links; 6,474 disorder → procedure links;
1,959 phytochemicals with PubChem identifiers; links to three CC BY 4.0 plant-image datasets; names in 8 regional
scripts; 3,347 cross-source headword concepts.

**Accuracy upgrades (v1.2).** 415 WHO definitions fill disorders NAMASTE leaves undefined (definitions 55.5% → 69.8%);
13,639 disorder → symptom edges from WHO sign lists; inherited profiles for 470 subtypes (flagged); 1,420 doṣa
suggestions (model output, flagged); symptom associations learned from published cases; a clinical-term crosswalk;
curated fixes for systematic Hindi translation errors ('stiffness' rendered as 'bitterness', 'nausea' as 'vomiting').

## 3. Collection

All sources were downloaded programmatically (`scripts/01_fetch_sources.py`) through the publishers'
public download functions or APIs. URL, retrieval time and SHA-256 are recorded in
`data/raw/PROVENANCE.json`. Enrichment API responses (GBIF, Wikidata, PubMed, ClinicalTrials.gov) are
cached in `data/interim/cache/`. Retrieval date: 2026-11-04.

## 4. Pre-processing, cleaning, labelling

1. **Parsing.** The WHO PDF is parsed by word coordinates, with two row-segmentation models chosen per
   page. It is validated against the book's own index (Annex 2): 99.85% of index IDs are recovered.
   NAMASTE Excel exports are parsed directly.
2. **Encoding repair.** Mojibake is fixed with ftfy, and stray HTML and non-breaking spaces are removed.
   SAT definitions had lost their diacritics in the source database; 90.2% of the 2,251 damaged tokens are
   repaired (vocabulary match, then a character 4-gram model at 96% held-out precision), and 146 rows stay
   flagged.
3. **Transliteration.** NAMASTE's phonetic scheme is converted to IAST and Devanagari. The converter
   matches the official spelling exactly on 97% of aligned rows; the remaining differences are typos in
   the source. Official Devanagari is kept when it agrees with the derived form. Round-trip
   IAST↔Devanagari is 100%.
4. **Normalisation.** Unicode NFC throughout. ISO-15919 diacritics are normalised to IAST. Sanskrit is
   converted to its Hindi usage form, and a cross-romanisation matching key is used to join the
   loosely spelled Amidha names.
5. **Taxonomy.** 605 botanical names were validated against the GBIF backbone; 97% resolve to an accepted
   species. 116 outdated synonyms were updated, 10 misspellings corrected, and ambiguous synonyms are left
   unresolved rather than guessed. Three documented overrides are in `curation/taxonomy_overrides.csv`.
6. **De-duplication and conflicts.** Duplicate NAMASTE rows are removed. Duplicate herb records are merged
   on the accepted name. Contradictory property records are not unioned: the primary record wins, and the
   alternatives are kept in `property_variants`.
7. **Labelling.** Doṣa involvement comes from the term text or is inherited from the NAMASTE hierarchy,
   and the method is recorded in `dosha_source`. Therapies are tagged by category. Herb safety classes
   (mahāviṣa / upaviṣa / caution) come from the curated list.

## 5. Uses

**Intended:** expert systems and clinical decision support reviewed by qualified practitioners; terminology
services and NAMASTE ↔ ICD-11 TM2 coding; bilingual search, RAG and question answering; research on
Ayurvedic pharmacology (rasa–vīrya–doṣa relations) and on phytochemistry of Ayurvedic herbs; teaching.

**Not intended:** autonomous diagnosis or prescribing; dosage decisions (no doses are given); any use of
the synthetic Prakṛti cohort as evidence about real people.

## 6. Known limitations

- The curated layers (formulations, diagnostic correspondences, safety list, glossary, questionnaire) were
  written for this project from classical texts and standard references. They are flagged
  `curated…` and need review by a qualified Ayurveda expert. Formulations should be checked against the
  Ayurvedic Formulary of India.
- Hindi descriptions are machine translations: NLLB-200 with an injected Ayurveda glossary, with quality
  flags and back-translation QE (see `reports/translation_qe.json`). Hindi names of Sanskrit terms are
  rule-derived and reliable; translated English glosses are less so. Systematic errors are corrected by curated
  post-edits (`curation/mt_postedit_rules.csv`, `curation/mt_item_corrections.csv`), marked in each row's
  `*_method`. 713 WHO definitions flagged `repetition` are degenerate translations that need re-translation.
- Herb properties (rasa, guṇa, vīrya, vipāka, doṣa) come from one community database (Amidha, 344 herbs)
  and reflect one reading of the classical texts.
- 76 Amidha-only herbs have no authoritative Sanskrit IAST spelling. Rather than invent one, the ASCII name
  is kept.
- Evidence counts (PubMed, trials) measure research volume, not efficacy.
- Case-report extraction uses the KB lexicons; diagnoses were found for 38% of therapeutic reports. Literature tiers are
  co-occurrence counts. Procedure links are rule-based and need practitioner judgement.

## 7. Distribution and licence

Combined release: **CC BY-NC-SA 4.0**. This is required by the WHO component (CC BY-NC-SA 3.0 IGO) and
the NLLB-200 model licence (CC BY-NC 4.0). Per-row `source_id` / `licence` columns allow commercial-safe
subsets. Attribute the Ministry of Ayush (NAMASTE), WHO, USDA-ARS (Dr. Duke), Amidha Ayurveda (S. Varshney),
GBIF, Wikidata and NLM as listed in `docs/SOURCES.md`.

## 8. Maintenance

Re-run `scripts/01…11` to refresh from the sources. All API responses are cached, so a rebuild is
deterministic offline. Run `python3 -m pytest tests/` after any change; the suite has 64 checks covering
keys, references, encoding, domain rules, bilingual coverage, safety flags, ML baselines and expert-system behaviour.
