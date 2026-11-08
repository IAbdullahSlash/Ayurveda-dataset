#!/usr/bin/env python3
"""Build reports/indication_review/ai_prereview.csv: AI-drafted alias suggestions for human sign-off.

Judgments are written once below; IDs, names, row counts and current states are looked up from the data
so nothing is copied by hand. Nothing here is read by the indication policy; reviewers sign rows in the
CSV and stage 54 copies signed rows into curation/indication_aliases.csv.

Re-running overwrites the CSV, so do it only before reviewers start filling it in.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I omits the script folder
from lib.review import write_review_csv

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
rd = lambda p: pd.read_csv(ROOT / p, keep_default_na=False, dtype=str, low_memory=False)
d = rd("data/processed/diseases.csv").set_index("disease_id")
hi = rd("data/processed/herb_indication.csv")

NANATMAJA = "The other candidate sits in the single-doṣa (nānātmaja) list and is narrower than a plain herb indication."
# raw term -> (suggestion, disease_id, confidence, rationale, alternatives considered)
S = {
 # ---- ambiguous exact matches: NAMASTE lists the same term twice ----
 "Ardita": ("accept", "AYD-00135", "high", "General facial-palsy entry with a clinical definition. " + NANATMAJA, "AYD-00022 (vāta-only listing)"),
 "Bhrama": ("accept", "AYD-01521", "high", "General vertigo/giddiness disorder with a definition. " + NANATMAJA, "AYD-00088 (vāta-only listing, no definition)"),
 "Daha": ("accept", "AYD-01054", "medium", "The dāha disease entry among the rakta-channel disorders, parent of the dāha subtypes, consistent with the choice for Kāmalā and Raktapitta. Its definition stresses whole-body burning, so an expert may prefer the pitta listing.", "AYD-00285 (pitta-only listing)"),
 "Galaganda": ("accept", "AYD-01643", "high", "Goitre entry under throat disorders. " + NANATMAJA, "AYD-00338 (kapha-only listing)"),
 "Gandamala": ("accept", "AYD-01641", "high", "Gaṇḍamālā is cervical lymphadenopathy. The other candidate is an unrelated skin vesicle that only shares the spelling skeleton.", "AYD-02253 (gandhanāmā, solitary vesicle: different disorder)"),
 "Gridhrasi": ("accept", "AYD-00157", "high", "General sciatica entry with a definition. " + NANATMAJA, "AYD-00053 (vāta-only listing)"),
 "Hikka": ("accept", "AYD-00471", "high", "Hiccough disorder among prāṇavaha-channel disorders, with a definition. " + NANATMAJA, "AYD-00127 (vāta-only listing, no definition)"),
 "Kamala": ("accept", "AYD-00874", "high", "General jaundice disorder with a clinical definition. " + NANATMAJA, "AYD-00274 (pitta-only listing)"),
 "Karnashoola": ("accept", "AYD-01897", "high", "Otalgia entry under ear diseases, with a definition. " + NANATMAJA, "AYD-00039 (vāta-only listing, no definition)"),
 "Kita-visha": ("accept", "AYD-02481", "high", "The parent insect-venom poisoning entry; the other candidates are its doṣa subtypes.", "AYD-02485, AYD-02486 (subtypes)"),
 "Krimi": ("accept", "AYD-02184", "high", "General worm-infestation disorder. Snāyuka is a specific infestation that only shares the spelling.", "AYD-02231 (snāyuka: specific subtype)"),
 "Nidranasha": ("accept", "AYD-02584", "medium", "Insomnia disorder with a definition. The other entry is an undefined item under the rakta-channel group.", "AYD-00850 (undefined listing)"),
 "Pakshaghata": ("accept", "AYD-00163", "high", "General hemiplegia entry with a definition. " + NANATMAJA, "AYD-00069 (vāta-only listing)"),
 "Raktapitta": ("accept", "AYD-00944", "high", "General bleeding-disorder entry with a clinical definition. " + NANATMAJA, "AYD-00295 (pitta-only listing)"),
 "Shukra Kshaya": ("needs_expert", "AYD-00407", "low", "Leaning to the śukra-dhātu depletion pattern because the herbs are vṛṣya/rasāyana drugs given to replenish śukra. Oligospermia (AYD-00114) is a narrower modern reading. A clinical decision is needed.", "AYD-00114 (oligospermia)"),
 "Shukra-kshaya": ("needs_expert", "AYD-00407", "low", "Same term as 'Shukra Kshaya' with a different spelling; decide all three together.", "AYD-00114 (oligospermia)"),
 "Shukrakshaya": ("needs_expert", "AYD-00407", "low", "Same term as 'Shukra Kshaya' with a different spelling; decide all three together.", "AYD-00114 (oligospermia)"),
 "Udavarta": ("accept", "AYD-00656", "medium", "The definition (retention of faeces, flatus and urine with abdominal pain) matches udāvarta. Its English label 'volvulus' is misleading and is worth correcting separately.", "AYD-00033 (vāta-only listing)"),
 "Vidradhi": ("accept", "AYD-01221", "medium", "General abscess disorder with a definition. Varuṇa and śigru are also classical for internal (deep) vidradhi, which an expert may prefer.", "AYD-00972 (deep/internal abscess); AYD-01148 (prameha piḍakā)"),
 # ---- fuzzy matches that are correct ----
 "Arochak": ("accept", "AYD-00569", "high", "Arocaka is anorexia; only the final vowel differs.", ""),
 "Mutrakrichha": ("accept", "AYD-01278", "high", "Mūtrakṛcchra is dysuria; only the spelling differs.", ""),
 "Palitya": ("accept", "AYD-01537", "high", "Pālitya is greying of hair; the entry also lists palita.", ""),
 "Raktabhishandya": ("accept", "AYD-01744", "high", "Raktābhiṣyanda is the same term.", ""),
 "Raktarsha": ("accept", "AYD-01081", "high", "Raktārśa is haemorrhoids due to rakta, the same term.", ""),
 "Sannipata Jwara": ("accept", "AYD-00700", "high", "Sannipātajvara is fever from all three doṣa, the same term.", ""),
 "Shirashoola": ("accept", "AYD-01522", "high", "Śiraḥśūla is listed in this entry's own name.", ""),
 "Urakshata": ("accept", "AYD-00511", "high", "Uraḥkṣata is the same term.", ""),
 "Visha-jwara": ("accept", "AYD-00758", "high", "Viṣajajvara is fever due to poison, the same term.", ""),
 "Vrana-shotha": ("accept", "AYD-01914", "high", "Vraṇaśopha is the same term.", ""),
 "Vranashotha": ("accept", "AYD-01914", "high", "Vraṇaśopha is the same term.", ""),
 # ---- quarantined wrong matches: proposed replacement targets ----
 "Kshaya": ("accept_replacement", "AYD-00420", "low", "Wrong target was 'psychic constitution'. In herb texts kṣaya usually means consumption/wasting (rājayakṣmā); the herbs are nourishing (śilājatu, panasa, caṇaka). It can also mean general dhātu depletion, so an expert should confirm.", "the specific dhātu-kṣaya patterns (AYD-00385…)"),
 "Kantharoga": ("accept_replacement", "AYD-01616", "high", "Wrong target was ear diseases. Kaṇṭharoga means disorders of the throat, which is this category.", ""),
 "Kapha Roga": ("accept_replacement", "AYD-00318", "medium", "Wrong target was a scalp disorder. 'Kapha roga' means disorders of kapha, which is this category entry.", ""),
 "Kaphaja Roga": ("accept_replacement", "AYD-00318", "medium", "Wrong target was a scalp disorder. 'Kaphaja roga' means disorders caused by kapha, which is this category entry.", ""),
 "Kshata": ("accept_replacement", "AYD-00511", "medium", "Wrong target was whitlow. With nourishing herbs (kharjūra, priyāla, akṣoṭa) kṣata usually pairs with kṣīṇa, which this entry names. As an alternative it could mean a wound (vraṇa).", "AYD-01913 (vraṇa, wound)"),
 "Manasa Roga": ("accept_replacement", "AYD-01421", "medium", "Wrong target was nose diseases. 'Mānasa roga' means mental disorders; this is the category of mind-channel disorders.", "AYD-01423 (unmāda: narrower)"),
 "Vata Roga": ("accept_replacement", "AYD-00004", "high", "Wrong target was eyelid disorders. 'Vāta roga' means disorders due to vāta, which is this category.", ""),
 "Vataroga": ("accept_replacement", "AYD-00004", "high", "Wrong target was eyelid disorders. 'Vātaroga' means disorders due to vāta, which is this category.", ""),
 "V विषम Jwara": ("accept_replacement", "AYD-00761", "high", "The source text reads viṣama jvara; it was matched to plain fever. Viṣamajvara is intermittent fever, a child of that entry.", "AYD-00689 (jvara: too broad)"),
 # ---- unmatched terms with a clear NAMASTE entry ----
 "Agnimandya": ("accept", "AYD-00463", "high", "Agnimāndya is subdued digestive power; this entry lists mandāgni/agnisāda.", "AYD-00464 (pattern variant)"),
 "Grahani": ("accept", "AYD-00601", "high", "Grahaṇī as a disorder is grahaṇīdoṣa (malabsorption).", "AYD-00602 (prodromes)"),
 "Krimiroga": ("accept", "AYD-02184", "high", "General worm-infestation disorder.", ""),
 "Krimi Vyadhi": ("accept", "AYD-02184", "high", "General worm-infestation disorder.", ""),
 "Pandu": ("accept", "AYD-00812", "high", "Pāṇḍu is pāṇḍuroga (anaemia).", ""),
 "Pradara": ("accept", "AYD-01392", "medium", "Pradara alone usually means asṛgdara/raktapradara. It can also cover śvetapradara (leucorrhoea), so an expert may split it.", "AYD-01398 (śvetapradara)"),
 "Anaha": ("accept", "AYD-00147", "medium", "NAMASTE files the ānāha types (āmaja, purīṣaja) under this distension entry; there is no separate ānāha parent.", ""),
 "Raktadosha": ("accept", "AYD-00387", "medium", "Rakta-doṣa means vitiation of blood; this is the rakta-vitiation pattern entry.", "its doṣa-specific children"),
 "Yakrit Roga": ("no_target", "", "high", "NAMASTE has no liver-disorder entry (only spleen). Keep unmatched.", ""),
 "Malabaddhata": ("no_target", "", "medium", "Constipation has no general NAMASTE entry; the closest items are purgation complications. Keep unmatched.", ""),
 "Vibandha": ("no_target", "", "medium", "Constipation has no general NAMASTE entry; vibandhavyāpat is a purgation complication. Keep unmatched.", ""),
 # ---- remaining unmatched terms (second batch, 8 November 2026) ----
 'Anidra': ('accept', 'AYD-02584', 'high', 'Anidrā is sleeplessness; same target as Nidranasha.', 'AYD-00850 (undefined listing)'),
 'Udara Shoola': ('accept', 'AYD-00633', 'high', "Udaraśūla is abdominal pain; NAMASTE's śūla entry is the abdominal-pain disorder.", ''),
 'Ojo Kshaya': ('accept', 'AYD-00416', 'high', 'Ojakṣaya, diminution of ojas, is the same term.', 'AYD-00415 (impaired immunity)'),
 'Sandhivata': ('accept', 'AYD-00248', 'high', 'Sandhivāta is sandhigatavāta (osteoarthritis).', ''),
 'Sandhi Vata': ('accept', 'AYD-00248', 'high', 'Sandhivāta is sandhigatavāta (osteoarthritis).', ''),
 'Dantaroga': ('accept', 'AYD-01583', 'high', 'Dantaroga means tooth disorders, which is this category.', ''),
 'Dadru': ('accept', 'AYD-00900', 'high', 'Dadru is dadru-kuṣṭha (ringworm).', ''),
 'Stanya Alpata': ('accept', 'AYD-00413', 'high', 'Stanya alpatā is reduced breast milk, the same as stanyakṣaya.', ''),
 'Ama': ('accept', 'AYD-00458', 'high', 'Āma as an indication is āmadoṣa, the state of incomplete digestion.', 'AYD-00536 (ajīrṇa)'),
 'Artava Vikara': ('accept', 'AYD-00409', 'high', 'Ārtava vikāra means menstrual disorders, which is the ārtava-vitiation entry.', ''),
 'Drishtiroga': ('accept', 'AYD-01760', 'high', 'Dṛṣṭiroga means eyesight disorders, which is this category.', ''),
 'Garbhasraava Vyadhi': ('accept', 'AYD-01402', 'high', 'Garbhasrāva is early miscarriage, the same term.', 'AYD-01403 (garbhapāta, later miscarriage)'),
 'Hikkaroga': ('accept', 'AYD-00471', 'high', 'Hikkā; same target as Hikka.', ''),
 'Kashta-shartava': ('accept', 'AYD-01360', 'high', 'Misspelt kaṣṭārtava (dysmenorrhoea); NAMASTE files it as udāvartinī.', ''),
 'Keshya Vikara': ('accept', 'AYD-00829', 'high', 'Disorders of hair, which is this category.', ''),
 'Naktandhya': ('accept', 'AYD-01803', 'high', 'Naktāndhya is night blindness; this entry lists rātryāndhya.', 'AYD-01802 (doṣāndha)'),
 'Shiroga': ('accept', 'AYD-01522', 'high', 'Misspelt śiroroga; same target as Shirashoola.', ''),
 'Sthoulya': ('accept', 'AYD-01161', 'high', 'Sthaulya is obesity; medoroga is the general obesity disorder.', 'AYD-00326 (kapha-only listing, no definition)'),
 'Yonidosha': ('accept', 'AYD-01350', 'medium', 'Yoni-doṣa means gynaecological disorders, which is the yoniroga/yonivyāpad category.', ''),
 'Garbhashaya Roga': ('accept', 'AYD-01350', 'medium', 'Uterine disorders fall under the yoniroga/yonivyāpad category; NAMASTE has no separate uterus entry.', ''),
 'Kshata Kshaya': ('accept', 'AYD-00511', 'medium', 'Kṣatakṣaya is wasting after chest injury, named in this entry as kṣatakṣīṇa; consistent with Kshata.', ''),
 'Kshata-kshaya': ('accept', 'AYD-00511', 'medium', 'Kṣatakṣaya is wasting after chest injury, named in this entry as kṣatakṣīṇa; consistent with Kshata.', ''),
 'Pitta Roga': ('accept', 'AYD-00254', 'medium', 'Disorders of pitta, which is this category; consistent with the kapha and vāta groups.', ''),
 'Hrillasa': ('accept', 'AYD-02311', 'medium', "Hṛllāsa is nausea; NAMASTE's nausea disorder is filed as utkleśa.", ''),
 'Kampavata': ('accept', 'AYD-00178', 'medium', 'Kampavāta is tremor; this is the general tremor disorder.', 'AYD-00040 (vāta-only listing)'),
 'Manasavikara': ('accept', 'AYD-01421', 'medium', 'Mental disorders; same target as Manasa Roga.', ''),
 'Manasa Vikara': ('accept', 'AYD-01421', 'medium', 'Mental disorders; same target as Manasa Roga.', ''),
 'Raktavikara': ('accept', 'AYD-00387', 'medium', 'Rakta vikāra means vitiation of blood; same target as Raktadosha.', ''),
 'Vandhyatva': ('accept', 'AYD-01374', 'medium', 'Vandhyatva usually means female infertility; putrañjīvaka is given to aid conception.', ''),
 'Visha Roga': ('accept', 'AYD-02314', 'medium', "Disorders from poison, which is NAMASTE's poisoning category.", ''),
 'Visha Vyadhi': ('accept', 'AYD-02314', 'medium', "Disorders from poison, which is NAMASTE's poisoning category.", ''),
 'Asthi Daurbalya': ('accept', 'AYD-00401', 'medium', 'Weakness of bone tissue corresponds to the asthi-depletion pattern.', ''),
 'Bhagna-sandhana': ('accept', 'AYD-01971', 'medium', 'Sandhāna is the healing action; the condition treated is fracture (bhagna).', ''),
 'Bhutavesha': ('accept', 'AYD-01452', 'medium', 'Bhūtāveśa is possession by bhūta, the bhūtonmāda entry.', 'AYD-02140 (bālagraha)'),
 'Dantaphuyya': ('accept', 'AYD-01568', 'medium', 'Danta-pūya (pus from the teeth and gums) is pyorrhoea.', 'AYD-01577 (pyorrhoea alveolaris)'),
 'Dantashoola': ('accept', 'AYD-01584', 'medium', 'Dantaśūla is toothache; this is the odontalgia disorder.', 'AYD-00064 (vāta-only listing)'),
 'Dhanurvata': ('accept', 'AYD-00149', 'medium', 'Dhanurvāta is the bow-shaped spasm; this entry names dhanu and opisthotonos.', 'AYD-00134 (apatānaka)'),
 'Dristidaurbalya': ('accept', 'AYD-01760', 'medium', 'Weak eyesight falls under the eyesight-disorders category.', ''),
 'Garbhasanga': ('accept', 'AYD-01412', 'medium', 'Garbhasaṅga, obstructed delivery of the foetus, is covered by mūḍhagarbha.', ''),
 'Keshapata': ('accept', 'AYD-01543', 'medium', 'Keśapāta is hair fall; khālitya is the hair-loss disorder.', 'AYD-02284 (patchy alopecia)'),
 'Malaria': ('accept', 'AYD-00761', 'medium', 'A modern term; classical texts describe malaria as viṣamajvara (intermittent fever).', ''),
 'Shukra Alpata': ('needs_expert', 'AYD-00114', 'low', 'Alpatā means low quantity, which fits oligospermia better than dhātu depletion. Decide together with the three śukrakṣaya spellings.', 'AYD-00407 (śukra-dhātu depletion)'),
 'Sandhishoola': ('needs_expert', 'AYD-00248', 'low', 'NAMASTE has no joint-pain disorder. Sandhigatavāta is the closest, but it is narrower than pain in the joints.', ''),
 'Yakrit-pliha Roga': ('needs_expert', 'AYD-01017', 'low', 'Liver and spleen disorders; NAMASTE covers only the spleen part. Linking it drops the liver sense.', ''),
 'Amashaya Shotha': ('needs_expert', 'AYD-00641', 'low', 'Inflammation of the stomach is gastritis, which NAMASTE files as a type of śūla.', ''),
 'Graha': ('needs_expert', 'AYD-02140', 'low', 'Graha as an indication means possession by grahas. Bālagraha is the paediatric form; the intended sense is unclear.', 'AYD-01452 (bhūtonmāda)'),
 'Kati Shoola': ('needs_expert', 'AYD-00652', 'low', 'Kaṭiśūla is low-back pain. NAMASTE has no exact entry; trikaśūla (sacral pain) is the closest.', 'AYD-00078 (lumbar spondylosis)'),
 'Katishoola': ('needs_expert', 'AYD-00652', 'low', 'Kaṭiśūla is low-back pain. NAMASTE has no exact entry; trikaśūla (sacral pain) is the closest.', 'AYD-00078 (lumbar spondylosis)'),
 'Pakwashaya Shoola': ('needs_expert', 'AYD-00633', 'low', 'Pain in the colon. NAMASTE has no exact entry; the general abdominal-pain disorder is the closest.', 'AYD-00639 (abdominal colic)'),
 'Meha': ('no_target', '', 'medium', 'Probably a misspelling of medhya (intellect-promoting): both herbs, brāhmī and maṇḍūkaparṇī, are classic medhya drugs. Linking it to prameha would be wrong.', 'AYD-01110 (prameha: rejected)'),
 'Smritidaurbalya': ('no_target', '', 'medium', 'NAMASTE has no memory disorder.', ''),
 'Smritinasha': ('no_target', '', 'medium', 'NAMASTE has no memory disorder.', ''),
 'Yakrit Vikara': ('no_target', '', 'high', 'NAMASTE has no liver-disorder entry. Keep unmatched.', ''),
 'Raktachapa': ('no_target', '', 'high', 'A modern term for hypertension; NAMASTE has no entry.', ''),
 'Raktachapa Vyadhi': ('no_target', '', 'high', 'A modern term for hypertension; NAMASTE has no entry.', ''),
 'Vedana': ('no_target', '', 'medium', 'Pain in general; NAMASTE has no general pain disorder.', ''),
 'Vedana Vyadhi': ('no_target', '', 'medium', 'Pain in general; NAMASTE has no general pain disorder.', ''),
 'Vibhandha': ('no_target', '', 'medium', 'Constipation has no general NAMASTE entry; consistent with Vibandha.', ''),
 'Kleda': ('no_target', '', 'medium', 'Kleda is a body constituent (moisture), not a disorder.', ''),
 'Grahi Roga': ('no_target', '', 'medium', 'Unclear term; grāhī is an absorbent action. Cannot be identified safely.', ''),
 'Mukhabodham': ('no_target', '', 'medium', 'Unclear term; it matches no recognisable disorder name.', ''),
 'Rasayana': ('no_target', '', 'high', 'Names a therapeutic action or class of herb, not a disorder; there is nothing to link.', ''),
 'Vrishya': ('no_target', '', 'high', 'Names a therapeutic action or class of herb, not a disorder; there is nothing to link.', ''),
 'Varnya': ('no_target', '', 'high', 'Names a therapeutic action or class of herb, not a disorder; there is nothing to link.', ''),
 'Keshya': ('no_target', '', 'high', 'Names a therapeutic action or class of herb, not a disorder; there is nothing to link.', ''),
 'Pachana': ('no_target', '', 'high', 'Names a therapeutic action or class of herb, not a disorder; there is nothing to link.', ''),
 'Artava Janana': ('no_target', '', 'high', 'Names a therapeutic action or class of herb, not a disorder; there is nothing to link.', ''),
 'Garbhashaya Shodhana': ('no_target', '', 'high', 'Names a therapeutic action or class of herb, not a disorder; there is nothing to link.', ''),
}

state = hi.groupby("indication_raw").agg(rows=("herb_id", "size"), status=("mapping_status", lambda s: ";".join(sorted(set(s)))),
                                          original=("original_disease_id", lambda s: ";".join(sorted(set(s) - {""}))))
out = []
for raw, (sug, did, conf, why, alt) in S.items():
    if raw not in state.index:
        raise SystemExit("raw term not in herb_indication: " + raw)
    st = state.loc[raw]
    if did and did not in d.index:
        raise SystemExit("unknown disease id " + did)
    out.append(dict(indication_raw=raw, affected_rows=int(st.rows), current_status=st.status,
                    original_disease_id=st.original, original_name_en="; ".join(d.loc[x, "name_en"] for x in st.original.split(";") if x),
                    suggestion=sug, suggested_disease_id=did,
                    suggested_term_iast=d.loc[did, "term_iast"] if did else "", suggested_name_en=d.loc[did, "name_en"] if did else "",
                    relation="equivalent" if did else "", confidence=conf, rationale=why, alternatives_considered=alt,
                    drafted_by="AI pre-review (Claude), 8 November 2026; not an expert decision",
                    reviewer_verdict="", reviewer_disease_id="", reviewer="", reference="", reviewer_comment=""))
df = pd.DataFrame(out)
order = {"accept": 0, "accept_replacement": 1, "needs_expert": 2, "no_target": 3}
df = df.sort_values(["suggestion", "affected_rows"], key=lambda s: s.map(order) if s.name == "suggestion" else -s.astype(int)).reset_index(drop=True)
dest = ROOT / "reports/indication_review/ai_prereview.csv"
if dest.exists():
    previous = pd.read_csv(dest, keep_default_na=False, dtype=str)
    if any(previous[c].ne("").any() for c in ("reviewer_verdict", "reviewer_disease_id", "reviewer_comment") if c in previous):
        raise SystemExit(f"Refusing to overwrite reviewer verdicts in {dest.relative_to(ROOT).as_posix()}")
write_review_csv(df, dest)   # also refuses when reviewer or reference is filled
print(df.groupby("suggestion").agg(groups=("indication_raw", "size"), rows=("affected_rows", "sum")).to_string())
print("confidence:", df.confidence.value_counts().to_dict())
