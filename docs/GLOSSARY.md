# Glossary

Plain-language explanations of the Ayurveda, standards and technical terms used in AyurKB's tables, code and
documents. Sanskrit is given in IAST, with Devanagari and the usual English rendering. The column names in brackets
show where a concept appears in the data.

## Ayurveda: core concepts

| Term | Devanagari | Meaning |
|---|---|---|
| Ayurveda | आयुर्वेद | the classical medical system of India ("knowledge of life") |
| doṣa | दोष | the three regulatory principles of the body; disease is their imbalance (`diseases.dosha_*`, `herbs.dosha_pacify / dosha_aggravate`) |
| vāta, pitta, kapha | वात, पित्त, कफ | the three doṣas: movement / air, transformation / heat, structure / cohesion |
| prakṛti | प्रकृति | a person's inborn constitution, the balance of doṣas they are born with (`prakriti_synthetic_cohort`, the Prakṛti questionnaire) |
| vikṛti | विकृति | the current, disturbed state |
| prakopa, duṣṭi | प्रकोप, दुष्टि | aggravation / vitiation of a doṣa |
| dhātu | धातु | the seven body tissues |
| mala | मल | waste products (faeces, urine, sweat) |
| srotas | स्रोतस् | body channels |
| agni | अग्नि | digestive and metabolic "fire" |
| āma | आम | undigested, toxic residue from weak agni |
| ojas | ओज | vital essence, immunity |
| marma | मर्म | vital points of the body |

## Diagnosis

| Term | Devanagari | Meaning |
|---|---|---|
| vyādhi, roga | व्याधि, रोग | disease, disorder (`diseases`) |
| lakṣaṇa, rūpa | लक्षण, रूप | sign, symptom (`symptoms`); Hindi definitions start with "लक्षण:" (symptoms:) |
| pūrvarūpa | पूर्वरूप | prodrome, early warning sign; prodrome disorders never inherit symptom profiles |
| nidāna | निदान | cause / aetiology; also diagnosis |
| nidāna pañcaka | निदान पञ्चक | the five-fold diagnostic framework: cause, prodrome, symptoms, relieving factors, pathogenesis |
| samprāpti | सम्प्राप्ति | pathogenesis |
| aṣṭavidha parīkṣā | अष्टविध परीक्षा | eight-fold examination (pulse, urine, stool, tongue, voice, touch, eyes, general appearance) (`diagnostic_methods`) |
| nāḍī parīkṣā | नाड़ी परीक्षा | pulse examination |
| kriyākāla | क्रियाकाल | the six stages of disease development |
| jvara | ज्वर | fever (Hindi colloquial बुखार) |
| chardi | छर्दि | vomiting (Hindi उल्टी) |
| hṛllāsa, utkleśa | हृल्लास, उत्क्लेश | nausea (Hindi मतली, जी मिचलाना); utkleśa also means "provocation of doṣa" |
| dāha | दाह | burning sensation (Hindi जलन) |
| bhrama | भ्रम | giddiness, vertigo, confusion |

## Materia medica (Dravyaguṇa)

| Term | Devanagari | Meaning |
|---|---|---|
| dravya | द्रव्य | a medicinal substance |
| Dravyaguṇa | द्रव्यगुण | Ayurvedic pharmacology, the study of substances and their properties |
| rasa | रस | taste: sweet, sour, salty, pungent, bitter, astringent (`herbs.rasa`) |
| guṇa | गुण | physical quality, e.g. heavy/light, oily/dry, hot/cold (`herbs.guna`) |
| vīrya | वीर्य | potency: hot (uṣṇa) or cold (śīta) (`herbs.virya`) |
| vipāka | विपाक | post-digestive taste (`herbs.vipaka`) |
| prabhāva | प्रभाव | a specific action not explained by the other properties |
| karma | कर्म | pharmacological action, e.g. dīpana (appetiser), kṛmighna (anthelmintic) (`herb_karma`) |
| mahākaṣāya | महाकषाय | Caraka's 50 groups of 10 herbs sharing an action (`herb_groups`, `herb_group_members`) |
| viṣa, mahāviṣa, upaviṣa | विष | poison; major and minor poisons. Such herbs require purification (`herbs.safety_class`, `requires_shodhana`) |
| bhasma | भस्म | calcined (often metallic or mineral) preparation (`formulations.contains_metal_or_toxic`) |
| kvātha, cūrṇa, vaṭī, ghṛta, taila, avaleha, āsava, ariṣṭa | | dosage forms: decoction, powder, tablet, medicated ghee, medicated oil, linctus, fermented infusion, fermented decoction (`pharmaceutics`, `formulations.dosage_form`) |

## Treatment and lifestyle

| Term | Devanagari | Meaning |
|---|---|---|
| śodhana | शोधन | purification therapy (also: purification of a toxic herb before use) |
| śamana | शमन | palliative therapy that pacifies doṣas |
| pañcakarma | पञ्चकर्म | the five purification procedures: vamana (therapeutic emesis), virecana (purgation), basti (medicated enema), nasya (nasal medication), raktamokṣaṇa (bloodletting) (`therapies`, `therapy_disease`) |
| pūrvakarma | पूर्वकर्म | preparatory procedures: snehana (oleation), svedana (sudation) |
| kriyākalpa | क्रियाकल्प | local eye procedures, e.g. netratarpaṇa |
| rasāyana | रसायन | rejuvenation therapy |
| vājīkaraṇa | वाजीकरण | aphrodisiac therapy |
| pathya, apathya | पथ्य, अपथ्य | wholesome / unwholesome diet and conduct (`diet_lifestyle`) |
| dinacaryā, ṛtucaryā | दिनचर्या, ऋतुचर्या | daily and seasonal regimens |
| vaidya | वैद्य | Ayurveda practitioner |

## Standards and sources

| Term | Meaning |
|---|---|
| NAMASTE | the Ministry of Ayush's National AYUSH Morbidity and Standardized Terminologies Electronic portal (sources S1, S2) |
| NAMC code | NAMASTE morbidity code, one per disorder (`diseases.namc_code`, `namc_code_clean`) |
| SAT | NAMASTE Standardised Ayurveda Terminologies, sections A–J (SAT-D = symptom lexicon, SAT-F = plants) (`terminology`, `symptoms.sat_code`) |
| WHO ITA | WHO international standard terminologies on Ayurveda (2022), ids `ITA-x.y.z` (`terminology`, `diseases.who_term_id`) |
| ICD-11 TM2 | the Traditional Medicine Module 2 chapter of WHO's ICD-11 (`diseases.icd11_tm2_code`) |
| AFI | Ayurvedic Formulary of India, the official formulation reference |
| Ministry of Ayush, CCRAS, PCIM&H | Indian government ministry, research council and pharmacopoeia commission (see `docs/permission_requests/`) |
| Caraka Saṃhitā, Suśruta Saṃhitā, Aṣṭāṅga Hṛdaya | the classical texts cited in curated references |

## Scripts, languages and transliteration

| Term | Meaning |
|---|---|
| IAST | the International Alphabet of Sanskrit Transliteration (ā, ṛ, ś, ṣ, ṃ, ḥ …); the romanisation used throughout |
| ISO 15919 | a related standard (ō, ē, r̥) used by NAMASTE; normalised to IAST |
| Devanagari | the script for Sanskrit and Hindi |
| Hindi usage form | how a Sanskrit term is written in everyday Hindi, e.g. व्याधिः → व्याधि (`term_hi`) |
| NAMASTE phonetic | the ASCII input scheme of the NAMASTE exports (e.g. `vAtavyAdhiH`), converted by `02b` |
| matching key / skeleton | a loose spelling key that joins romanisations such as "kuṣṭham" and "Kushta" (`scripts/lib/keys.py`) |
| mojibake | text garbled by a wrong encoding (e.g. "Ã©"), repaired with ftfy |

## Technical terms

| Term | Meaning |
|---|---|
| NLLB-200 | Meta's machine-translation model (600M distilled), used for English → Hindi (stage 06) |
| glossary injection | replacing known English terms with curated Hindi before translation (`curation/glossary_en_hi.csv`) |
| QE flags | automatic quality-estimation warnings on a translation (`*_qe_flags`) |
| back-translation chrF | translating Hindi back to English and scoring character overlap with the source (`reports/translation_qe.json`) |
| composed definition | a Hindi disorder definition assembled from symptom terms and their Hindi glosses rather than translated as a paragraph |
| post-edit rule | a deterministic find-and-replace fix for a systematic translation error (`curation/mt_postedit_rules.csv`, stage 25) |
| multilingual-e5 | the sentence-embedding model behind semantic search (stage 11) |
| RAG | retrieval-augmented generation; `release/ayurkb_corpus.jsonl` is the corpus |
| Frictionless data package | the `release/datapackage.json` metadata standard describing the tables |
| GBIF | Global Biodiversity Information Facility, used to validate botanical names |
| IDF | inverse document frequency; rarer symptoms weigh more when ranking disorders |
| macro-F1, top-1, hit@10 | evaluation metrics used in `reports/ml/` |
| `data_origin` | per-row label: authoritative, integrated, curated, derived, inferred or synthetic |
