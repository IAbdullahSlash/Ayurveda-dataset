#!/usr/bin/env python3
"""
Stage 16 - Three linking layers for the expert system.

1. therapy_disease      disorder -> procedure links (WHO/SAT therapy records) from explicit classical rules:
                          * site-specific procedures (eye -> kriyākalpa, nose -> nasya, ear -> karṇapūraṇa, mouth ->
                            kavala/gaṇḍūṣa, head -> mūrdhataila, ulcers -> ṣaṣṭi upakrama, anorectal -> kṣāra/agni ...)
                          * disorder-specific protocols (kuṣṭha, vātarakta, jvara, medoroga, kārśya, manas ...)
                          * iatrogenic disorders -> the procedure they are complications of
                          * the doṣa principle of Caraka Sūtrasthāna 25.40 (basti / virecana / vamana) - generic
                          * procedures observed in published case reports for that diagnosis (stage 14)
2. multiscript_names    every Devanagari name (disorders, symptoms, herbs, formulations, terminology, therapies)
                        transliterated into 8 regional scripts (Bengali, Gujarati, Gurmukhi, Kannada, Malayalam,
                        Odia, Tamil, Telugu) - Ayurveda texts are widely printed in regional scripts.
3. headword_concepts    records of all sources that share a Sanskrit headword (skeleton key) - WHO term, SAT term,
   + concept_members    NAMASTE disorder, symptom, therapy, herb, formulation - a cross-source navigation index.
"""
import re, sys
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd
from indic_transliteration import sanscript

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.keys import skeleton

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)

SODHANA_CAUTION = ("Śodhana needs assessment of strength (bala), age, season and contraindications "
                   "(e.g. pregnancy, debility, children, elderly); practitioner decision.")

def therapy_resolver(T):
    T = T.assign(sk=T.term_sa_iast_primary.map(skeleton))
    order = {"S3": 0, "S2": 1}
    T = T.sort_values(by=["source_id", "therapy_id"], key=lambda s: s.map(order) if s.name == "source_id" else s)
    idx = {}
    for tid, sk, t in zip(T.therapy_id, T.sk, T.term_sa_iast_primary):
        if "(" in t:                      # context-specific variants such as 'virecanakarma (vraṇacikitsā'
            continue
        idx.setdefault(sk, (tid, t))
    by_id = dict(zip(T.therapy_id, T.term_sa_iast_primary))
    def get(name):
        if name.startswith("THE-"):       # explicit record where a headword is ambiguous (pācanam: cautery vs digestion)
            return name, by_id[name]
        r = idx.get(skeleton(name))
        if r is None:
            raise KeyError(f"therapy not found: {name}")
        return r
    return get

def therapy_disease():
    D, T = rd("diseases"), rd("therapies")
    get = therapy_resolver(T)
    children = defaultdict(set)
    for c, p in zip(D.disease_id, D.parent_disease_id):
        if p:
            children[p].add(c)
    def fam(*roots):
        out, stack = set(), list(roots)
        while stack:
            x = stack.pop()
            if x not in out:
                out.add(x); stack += list(children.get(x, ()))
        return out
    by_sys = lambda *codes: set(D[D.system_code.isin(codes)].disease_id)
    by_cat = lambda *cats: set(D[D.category_name_en.isin(cats)].disease_id)
    eye_cats = ("eye sight disorders", "eyelid disorders", "generalised eye diseases", "sclera diseases", "Corneal disorder",
                "disorders of nētrasandhi", "ophthalmic diseases")
    oral = by_sys("G")
    rakta_family_excl = fam("AYD-00944", "AYD-00295")                 # raktapitta: bleeding - no bloodletting
    R = [  # (disease set, [therapies], relation, reference, note)
        (by_sys("H") | by_cat(*eye_cats), ["netratarpaṇam", "puṭapākaḥ", "sekaḥ", "āścyotanam", "añjanam"],
         "site_specific_procedure", "Suśruta Saṃhitā Uttaratantra 18 (kriyākalpa); Aṣṭāṅgahṛdaya Sūtrasthāna 23-24", ""),
        (by_sys("I"), ["nasyam", "śirovirecanam", "pratimarśaḥ", "dhūmapānam"], "site_specific_procedure",
         "Aṣṭāṅgahṛdaya Sūtrasthāna 20-21; Suśruta Saṃhitā Uttaratantra 22-24", ""),
        (by_sys("J"), ["karṇapūraṇam", "karṇadhūpanam"], "site_specific_procedure", "Suśruta Saṃhitā Uttaratantra 21", ""),
        (oral, ["kavalaḥ", "gaṇḍūṣaḥ", "pratisāraṇam"], "site_specific_procedure", "Aṣṭāṅgahṛdaya Sūtrasthāna 22", ""),
        (by_sys("F") | by_cat("Scalp affliction disorder"), ["mūrdhatailam", "śirobastiḥ", "śiraḥpicuḥ", "nasyam"],
         "site_specific_procedure", "Aṣṭāṅgahṛdaya Sūtrasthāna 22 (mūrdhataila); Caraka Saṃhitā Sūtrasthāna 5 (nasya)", ""),
        (by_sys("K") | fam("AYD-01913"), ["vraṇasyaṣaṣṭi-upakramāḥ"], "disorder_protocol", "Suśruta Saṃhitā Cikitsāsthāna 1", ""),
        (fam("AYD-01074"), ["kṣārakarma", "agnikarma", "aṣṭavidhaśastrakarma"], "disorder_protocol",
         "Suśruta Saṃhitā Cikitsāsthāna 6 (four modalities for arśas: medicine, caustic, cautery, surgery)", ""),
        (fam("AYD-01033"), ["kṣārasūtraḥ", "kṣārakarma", "agnikarma", "aṣṭavidhaśastrakarma"], "disorder_protocol",
         "Suśruta Saṃhitā Cikitsāsthāna 8 (bhagandara); kṣārasūtra validated in ICMR multicentric trial", ""),
        (by_sys("P"), ["viṣagaravairodhikacikitsā"], "disorder_protocol", "Caraka Saṃhitā Cikitsāsthāna 23.35-37 (24 upakrama)",
         "Envenomation and poisoning are medical emergencies: refer for modern emergency care (antivenom etc.)."),
        (fam("AYD-00883"), ["vamanakarma", "virecanakarma", "nasyam", "raktamokṣaṇam"], "disorder_protocol",
         "Caraka Saṃhitā Cikitsāsthāna 7.39-41 (periodic śodhana and bloodletting in kuṣṭha)", SODHANA_CAUTION),
        (fam("AYD-00956"), ["raktamokṣaṇam", "jalaukāvacaraṇam", "bastikarma", "virecanakarma"], "disorder_protocol",
         "Caraka Saṃhitā Cikitsāsthāna 29 (vātarakta)", SODHANA_CAUTION),
        (fam("AYD-00997"), ["raktamokṣaṇam", "jalaukāvacaraṇam", "virecanakarma", "pradehaḥ"], "disorder_protocol",
         "Caraka Saṃhitā Cikitsāsthāna 21 (visarpa)", SODHANA_CAUTION),
        (by_cat("disorders of raktavahasrōtas") - rakta_family_excl, ["virecanakarma", "laṅghanam", "raktamokṣaṇam"],
         "category_principle", "Caraka Saṃhitā Sūtrasthāna 24.18 (purgation, fasting and bloodletting in blood disorders)",
         SODHANA_CAUTION),
        (by_cat("disorders due to vāta") | fam("AYD-00004"), ["snehanam", "svedana", "bastikarma"], "category_principle",
         "Caraka Saṃhitā Cikitsāsthāna 28 (vātavyādhi: oleation, sudation, enema)", SODHANA_CAUTION),
        (by_cat("disorders of manōvahasrōtas") | fam("AYD-01423", "AYD-01457"),
         ["yuktivyapāśrayacikitsā", "satvāvajayacikitsā", "daivavyapāśrayacikitsā"], "category_principle",
         "Caraka Saṃhitā Sūtrasthāna 11.54 (three-fold therapy); Cikitsāsthāna 9-10", ""),
        (fam("AYD-00689"), ["laṅghanam"], "disorder_protocol", "Caraka Saṃhitā Cikitsāsthāna 3.139-142 (laṅghana first in jvara)", ""),
        (fam("AYD-01161") | by_cat("disorders of mēdōvahasrōtas"), ["apatarpaṇam", "udvartanam", "laṅghanam"],
         "disorder_protocol", "Caraka Saṃhitā Sūtrasthāna 21.20-28 (sthaulya); Aṣṭāṅgahṛdaya Sūtrasthāna 2.15 (udvartana)", ""),
        (fam("AYD-00045"), ["bṛṃhaṇam", "santarpaṇam"], "disorder_protocol", "Caraka Saṃhitā Sūtrasthāna 21.29-34 (kārśya)", ""),
        (by_cat("fracture"), ["bandhanakarma"], "disorder_protocol", "Suśruta Saṃhitā Cikitsāsthāna 3 (bhagna)",
         "Fractures need radiological assessment and orthopaedic care."),
        (by_cat("disorders of ārtavavahasrōtas") | fam("AYD-01350"), ["uttarabastiḥ", "yoni picu", "yoni dhūpana"],
         "disorder_protocol", "Caraka Saṃhitā Cikitsāsthāna 30 (yonivyāpad); Kāśyapa Saṃhitā", ""),
        (fam("AYD-01173", "AYD-00407"), ["vājīkaraṇam"], "disorder_protocol", "Caraka Saṃhitā Cikitsāsthāna 2 (vājīkaraṇa)", ""),
        (fam("AYD-00823"), ["laṅghanam", "svedana", "dīpanam", "virecanakarma", "snehanam", "bastikarma"], "disorder_protocol",
         "Cakradatta, Āmavātacikitsā 25.1 (laṅghana, svedana, tikta-kaṭu dīpana, virecana, snehapāna, basti)", SODHANA_CAUTION),
        (fam("AYD-00053", "AYD-00157"), ["sirāvedhaḥ", "bastikarma", "agnikarma"], "disorder_protocol",
         "Caraka Saṃhitā Cikitsāsthāna 28.101 (gṛdhrasī: venesection, enema, thermal cautery)", SODHANA_CAUTION),
        (fam("AYD-00069", "AYD-00163"), ["svedana", "snehanam", "virecanakarma"], "disorder_protocol",
         "Caraka Saṃhitā Cikitsāsthāna 28.100 (pakṣāghāta)", SODHANA_CAUTION),
        (fam("AYD-00022", "AYD-00135"), ["nasyam", "mūrdhatailam", "svedana"], "disorder_protocol",
         "Caraka Saṃhitā Cikitsāsthāna 28.99 (ardita: navana, mūrdhataila, nāḍīsveda)", ""),
        (fam("AYD-00489", "AYD-00471"), ["snehanam", "svedana", "vamanakarma", "virecanakarma"], "disorder_protocol",
         "Caraka Saṃhitā Cikitsāsthāna 17.71-81 (śvāsa-hikkā: oleation and sudation first, then śodhana)", SODHANA_CAUTION),
        (fam("AYD-00558"), ["vamanakarma", "virecanakarma"], "disorder_protocol",
         "Kāśyapa Saṃhitā Khilasthāna 16 (amlapitta)", SODHANA_CAUTION),
        (fam("AYD-01110"), ["vamanakarma", "virecanakarma", "apatarpaṇam", "udvartanam"], "disorder_protocol",
         "Caraka Saṃhitā Cikitsāsthāna 6.15-16 (prameha: śodhana for the strong, apatarpaṇa)", SODHANA_CAUTION),
        (fam("AYD-00812"), ["vamanakarma", "virecanakarma"], "disorder_protocol", "Caraka Saṃhitā Cikitsāsthāna 16.40-41 (pāṇḍu)", SODHANA_CAUTION),
        (fam("AYD-00874", "AYD-00274"), ["virecanakarma"], "disorder_protocol", "Caraka Saṃhitā Cikitsāsthāna 16.40 (kāmalā: purgation)", SODHANA_CAUTION),
        (fam("AYD-01324"), ["virecanakarma"], "disorder_protocol", "Caraka Saṃhitā Cikitsāsthāna 13.61 (udara: repeated purgation)", SODHANA_CAUTION),
        (fam("AYD-00601"), ["dīpanam", "THE-00709", "laṅghanam"], "disorder_protocol", "Caraka Saṃhitā Cikitsāsthāna 15.73-75 (grahaṇī with āma)", ""),
        (fam("AYD-00515"), ["laṅghanam", "THE-00709", "stambhanam"], "disorder_protocol",
         "Caraka Saṃhitā Cikitsāsthāna 19 (atisāra: fasting, digestion of āma, then astringent therapy)", ""),
        (fam("AYD-00944", "AYD-00295"), ["virecanakarma", "vamanakarma", "stambhanam"], "disorder_protocol",
         "Caraka Saṃhitā Cikitsāsthāna 4.24-30 (raktapitta: ūrdhvaga -> purgation, adhoga -> emesis; styptics)",
         "Active bleeding needs urgent medical assessment."),
        (fam("AYD-01304"), ["laṅghanam", "THE-00709", "virecanakarma"], "disorder_protocol", "Caraka Saṃhitā Cikitsāsthāna 12 (śotha)", ""),
        (fam("AYD-01248"), ["aṣṭavidhaśastrakarma"], "disorder_protocol", "Suśruta Saṃhitā Cikitsāsthāna 7 (aśmarī; lithotomy)", ""),
        (fam("AYD-01258"), ["uttarabastiḥ"], "disorder_protocol", "Caraka Saṃhitā Siddhisthāna 9 (mūtrāghāta: uttarabasti)", ""),
        (fam("AYD-00919"), ["virecanakarma", "pracchānam"], "disorder_protocol", "Caraka Saṃhitā Cikitsāsthāna 7.162-164 (śvitra)", SODHANA_CAUTION),
        (fam("AYD-01374"), ["uttarabastiḥ"], "disorder_protocol", "Caraka Saṃhitā Siddhisthāna 9; Kāśyapa Saṃhitā (vandhyā)", ""),
        (fam("AYD-00850", "AYD-02584"), ["abhyaṅgaḥ", "mūrdhatailam"], "disorder_protocol",
         "Caraka Saṃhitā Sūtrasthāna 21.52-54 (nidrānāśa: massage, head oil, comfort measures)", ""),
        (fam("AYD-00326"), ["apatarpaṇam", "udvartanam", "laṅghanam"], "disorder_protocol", "Caraka Saṃhitā Sūtrasthāna 21.20-28 (atisthaulya)", ""),
    ]
    iatro = {  # complications of a procedure -> the procedure (relation: iatrogenic_complication_of)
        "disorders due to improper administration of enema": "bastikarma",
        "complications of purgation therapy": "virecanakarma", "disordered therapeutic-emesis disorders": "vamanakarma",
        "complications of errhine therapy": "nasyam", "complications of collyrium": "añjanam",
        "complications of caustic procedures": "kṣārakarma", "complications of thermal cautery": "agnikarma",
        "complication of improper surgical intervetion": "aṣṭavidhaśastrakarma"}
    rows = []
    for ds, ths, rel, ref, note in R:
        for t in ths:
            tid, tname = get(t)
            for d in sorted(ds):
                rows.append((d, tid, tname, rel, ref, note))
    for cat, t in iatro.items():
        tid, tname = get(t)
        for d in sorted(by_cat(cat)):
            rows.append((d, tid, tname, "iatrogenic_complication_of", "Caraka Saṃhitā Siddhisthāna 6-7; Suśruta Cikitsāsthāna 34-36",
                         "the disorder is a complication of this procedure (not an indication)"))
    # doṣa principle (Caraka Sū 25.40: basti agrya for vāta, virecana for pitta, vamana for kapha)
    principle = {"vata": "bastikarma", "pitta": "virecanakarma", "kapha": "vamanakarma"}
    clinical = D[~D.system_code.isin(["U", "V", "W", "S"])]
    for dz in ("vata", "pitta", "kapha"):
        tid, tname = get(principle[dz])
        for d in clinical[clinical[f"dosha_{dz}"].astype(str) == "True"].disease_id:
            rows.append((d, tid, tname, "dosha_principle_generic", "Caraka Saṃhitā Sūtrasthāna 25.40 (agrya-saṅgraha)",
                         SODHANA_CAUTION))
    # procedures observed in published case reports (stage 14)
    cr = P / "case_reports.csv"
    if cr.exists():
        C = pd.read_csv(cr, keep_default_na=False)
        E = pd.read_csv(P / "case_report_entities.csv", keep_default_na=False)
        E = E[(E.entity_type == "procedure") & (E.kb_ids != "")]
        dx = dict(zip(C.case_id, C.dx_disease_ids.str.split("; ").str[0]))
        kind = dict(zip(C.case_id, C.case_kind))
        cnt, cases = Counter(), defaultdict(list)
        for cid, ids in zip(E.case_id, E.kb_ids):
            d = dx.get(cid, "")
            if d and kind.get(cid) == "therapeutic":
                tid = ids.split(";")[0]
                cnt[(d, tid)] += 1; cases[(d, tid)].append(cid)
        tname = dict(zip(T.therapy_id, T.term_sa_iast_primary))
        for (d, tid), n in cnt.items():
            rows.append((d, tid, tname.get(tid, ""), "observed_in_published_cases",
                         f"{n} case report(s): " + ";".join(cases[(d, tid)][:10]), "text-mined; verify against the article"))
    out = pd.DataFrame(rows, columns=["disease_id", "therapy_id", "therapy_term_iast", "relation", "reference", "note"])
    out = out.drop_duplicates(["disease_id", "therapy_id", "relation"])
    Dn = D.set_index("disease_id")
    out.insert(1, "disease_term_iast", out.disease_id.map(Dn.term_iast))
    Tn = T.set_index("therapy_id")
    out.insert(4, "therapy_term_en", out.therapy_id.map(Tn.term_en))
    out["strength"] = out.relation.map({"site_specific_procedure": "specific", "disorder_protocol": "specific",
                                         "category_principle": "category", "dosha_principle_generic": "generic",
                                         "iatrogenic_complication_of": "n/a", "observed_in_published_cases": "observed"})
    out["source_id"] = out.relation.map(lambda r: "S10" if r == "observed_in_published_cases" else "S0")
    out["data_origin"] = "rule-based from classical references (curated); requires expert verification"
    out.loc[out.relation == "observed_in_published_cases", "data_origin"] = "text-mined from case reports"
    out.to_csv(P / "therapy_disease.csv", index=False)
    return out

SCRIPTS = {"bengali": sanscript.BENGALI, "gujarati": sanscript.GUJARATI, "gurmukhi": sanscript.GURMUKHI,
           "kannada": sanscript.KANNADA, "malayalam": sanscript.MALAYALAM, "odia": sanscript.ORIYA,
           "tamil": sanscript.TAMIL, "telugu": sanscript.TELUGU}

def multiscript():
    src = [("disease", "diseases", "disease_id", "term_deva"), ("symptom", "symptoms", "symptom_id", "term_sa_deva"),
           ("herb", "herbs", "herb_id", "name_sa_deva"), ("formulation", "formulations", "form_id", "name_sa_deva"),
           ("terminology", "terminology", "term_uid", "term_sa_deva_primary"),
           ("therapy", "therapies", "therapy_id", "term_sa_deva_primary")]
    rows = []
    for et, tab, idc, col in src:
        df = rd(tab)
        for i, deva in zip(df[idc], df[col]):
            if not deva:
                continue
            r = {"entity_type": et, "entity_id": i, "devanagari": deva}
            for k, s in SCRIPTS.items():
                r[k] = sanscript.transliterate(deva, sanscript.DEVANAGARI, s)
            rows.append(r)
    out = pd.DataFrame(rows)
    out["method"] = "rule-based transliteration (indic_transliteration); Tamil script is lossy for aspirates/voicing"
    out.to_csv(P / "multiscript_names.csv", index=False)
    return out

def concepts():
    members = []
    add = lambda et, i, src, iast, en, deva: members.append((et, i, src, iast, en, deva))
    for r in rd("terminology").itertuples():
        add("terminology", r.term_uid, r.source_id, r.term_sa_iast_primary, r.term_en, r.term_sa_deva_primary)
    for r in rd("diseases").itertuples():
        for part in re.split(r"/", r.term_iast):
            add("disease", r.disease_id, r.source_id, part.strip(), r.name_en, r.term_deva)
    for r in rd("symptoms").itertuples():
        add("symptom", r.symptom_id, r.source_id, r.term_sa_iast, r.gloss_en, r.term_sa_deva)
    for r in rd("therapies").itertuples():
        add("therapy", r.therapy_id, r.source_id, r.term_sa_iast_primary, r.term_en, r.term_sa_deva_primary)
    for r in rd("herbs").itertuples():
        add("herb", r.herb_id, "S2/S5", r.name_sa_iast, f"{r.accepted_name} ({r.name_en})" if r.name_en else r.accepted_name, r.name_sa_deva)
    for r in rd("formulations").itertuples():
        add("formulation", r.form_id, "S0", r.name_sa_iast, r.name_en, r.name_sa_deva)
    M = pd.DataFrame(members, columns=["entity_type", "entity_id", "source_id", "term_iast", "term_en", "term_deva"])
    M = M[M.term_iast != ""]
    M["key"] = M.term_iast.map(skeleton)
    M = M[M.key.str.len() >= 3].drop_duplicates(["entity_type", "entity_id", "key"])
    grp = M.groupby("key")
    keep = grp.filter(lambda g: g.entity_type.nunique() >= 2 or g.source_id.nunique() >= 2).key.unique()
    keys = sorted(keep)
    cid = {k: f"AYC-{i:05d}" for i, k in enumerate(keys, 1)}
    M = M[M.key.isin(cid)].copy()
    M.insert(0, "concept_id", M.key.map(cid))
    rows = []
    for k, g in M.groupby("key"):
        rows.append(dict(concept_id=cid[k], headword_iast=Counter(g.term_iast).most_common(1)[0][0],
                         headword_deva=next((d for d in g.term_deva if d), ""), n_members=len(g),
                         entity_types="; ".join(sorted(g.entity_type.unique())),
                         sources="; ".join(sorted(set(";".join(g.source_id).replace("/", ";").split(";")))),
                         english_glosses=" | ".join(list(dict.fromkeys(e for e in g.term_en if e))[:4]),
                         match_key=k))
    C = pd.DataFrame(rows).sort_values("concept_id")
    C["note"] = "lexical concept: records sharing a Sanskrit headword; homonyms possible - check entity_types/glosses"
    C.to_csv(P / "headword_concepts.csv", index=False)
    M.drop(columns=["key"]).to_csv(P / "concept_members.csv", index=False)
    return C, M

def main():
    td = therapy_disease()
    print("therapy_disease", td.shape, td.relation.value_counts().to_dict())
    ms = multiscript()
    print("multiscript_names", ms.shape, ms.entity_type.value_counts().to_dict())
    C, M = concepts()
    print("headword_concepts", C.shape, "members", M.shape)
    print(C.entity_types.value_counts().head(8).to_dict())

if __name__ == "__main__":
    main()
