#!/usr/bin/env python3
"""
Stage 14 - Real-world validation layer: published Ayurveda case reports (Europe PMC).

The knowledge base is built from terminology standards and classical/pharmacological sources.  This stage checks
it against how Ayurveda is actually practised and reported:

 1. search Europe PMC (REST API, cursor paging) for Ayurveda case reports / case series (peer-reviewed sources);
 2. keep bibliographic metadata, licence, MeSH headings and author keywords; for open-access articles download the
    JATS full text (text mining of the Europe PMC open-access subset is permitted).  Everything is cached;
 3. extract, with the knowledge-base lexicons only, the Ayurvedic diagnosis (NAMASTE disorder), presenting symptoms
    (SAT lexicon), herbs, classical formulations, procedures (Pañcakarma etc.) and modern assessments
    (laboratory tests, imaging, validated scales) - plus formulation names that are NOT yet in the KB;
 4. evaluate (experiment E6): (a) the KB symptom->disorder matcher on real presentations, (b) how much of the
    medicine actually used in practice the KB covers.

No abstract or full-text passage is redistributed: the tables hold identifiers, titles (bibliographic metadata) and
KB-vocabulary entities.  Outputs: data/processed/case_reports.csv, case_report_entities.csv,
case_report_links.csv, curation/candidates_formulations_from_cases.csv, reports/ml/E6_case_reports.json
"""
import argparse, json, math, re, sys, time, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.keys import skeleton
from lib.indic import fix_text, ascii_fold

try:                                    # downloaded XML is untrusted -> hardened parser when available
    import defusedxml.ElementTree as ET
except ImportError:                     # pragma: no cover
    import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
CACHE = ROOT / "data/interim/cache"
FT = CACHE / "epmc_fulltext"
FT.mkdir(parents=True, exist_ok=True)
REP = ROOT / "reports/ml"
rd = lambda n: pd.read_csv(P / f"{n}.csv", keep_default_na=False, low_memory=False)

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
QUERY = ('(TITLE:ayurved* OR ABSTRACT:ayurved* OR KW:ayurved* OR TITLE:panchakarma OR ABSTRACT:panchakarma) AND '
         '(PUB_TYPE:"Case Reports" OR TITLE:"case report" OR TITLE:"case study" OR TITLE:"case series" OR '
         'KW:"case report") AND (SRC:MED OR SRC:PMC)')
UA = {"User-Agent": "AyurKB-research-pipeline/1.0 (dataset build; contact via repository)"}

# ---------------------------------------------------------------------------------------------------------------
# 1-2. fetch
# ---------------------------------------------------------------------------------------------------------------
def _get(url, params=None, tries=4, as_json=True):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=60)
            if r.status_code == 200:
                return r.json() if as_json else r.content
            if r.status_code in (404, 400):
                return None
        except requests.RequestException:
            pass
        time.sleep(2 ** (i + 1))
    return None

def fetch():
    cache = CACHE / "epmc_case_reports.json"
    if cache.exists():
        recs = json.loads(cache.read_text())
    else:
        recs, cursor = [], "*"
        while True:
            d = _get(f"{EPMC}/search", {"query": QUERY, "format": "json", "resultType": "core", "pageSize": 1000,
                                        "cursorMark": cursor})
            if not d:
                raise SystemExit("Europe PMC search failed")
            page = d["resultList"]["result"]
            recs += page
            nxt = d.get("nextCursorMark")
            print(f"  search: {len(recs)}/{d['hitCount']}", flush=True)
            if not page or not nxt or nxt == cursor:
                break
            cursor = nxt
        cache.write_text(json.dumps(recs))
    n_new = 0
    for r in recs:
        pmc = r.get("pmcid")
        if not pmc or r.get("isOpenAccess") != "Y" or r.get("inEPMC") != "Y":
            continue
        f = FT / f"{pmc}.xml"
        if f.exists():
            continue
        x = _get(f"{EPMC}/{pmc}/fullTextXML", as_json=False)
        f.write_bytes(x or b"")
        n_new += 1
        time.sleep(0.15)
    print(f"  records {len(recs)}; full texts cached {sum(1 for _ in FT.glob('*.xml'))} (+{n_new})", flush=True)
    return recs

# ---------------------------------------------------------------------------------------------------------------
# JATS -> sections
# ---------------------------------------------------------------------------------------------------------------
def _text(el):
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip() if el is not None else ""

PRESENT = re.compile(r"case|patient|present|histor|complaint|clinical (finding|feature|examination|picture)|examination|"
                     r"diagnos|chief|symptom|finding", re.I)
TREAT = re.compile(r"treat|intervention|management|therap|medic|drug|protocol|plan|prescri|panchakarma|pañcakarma|"
                   r"procedure|timeline|follow|regimen|administ", re.I)
SKIP = re.compile(r"introduc|discussion|review|background|conclusion|referenc|acknowledg|limitation|mode of action|"
                  r"probable|samprapti|sampr[aā]pti|pathogenesis|literature|aim|objective|funding|conflict|consent|"
                  r"author|abbreviation|supplementary|ethic", re.I)

def sections(xml_bytes):
    """-> dict(presentation, treatment, body, tables, abstract_struct) of plain text"""
    out = {"presentation": [], "treatment": [], "body": [], "tables": []}
    if not xml_bytes:
        return None
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return None
    body = root.find(".//body")
    for tw in root.iter("table-wrap"):
        out["tables"].append(_text(tw))
    def walk(sec, path):
        title = _text(sec.find("title"))
        p = path + [title]
        pstr = " > ".join(t for t in p if t)
        own = " ".join(_text(c) for c in sec if c.tag in ("p", "list", "disp-quote", "boxed-text"))
        if own:
            out["body"].append(own)
            if not SKIP.search(pstr):
                if TREAT.search(title or pstr):
                    out["treatment"].append(own)
                elif PRESENT.search(pstr):
                    out["presentation"].append(own)
        for c in sec.findall("sec"):
            walk(c, p)
    if body is not None:
        for s in body.findall("sec"):
            walk(s, [])
        if not out["body"]:
            out["body"].append(_text(body))
    abs_struct = {}
    for ab in root.findall(".//article-meta/abstract"):
        for s in ab.findall("sec"):
            abs_struct[_text(s.find("title")).lower()] = " ".join(_text(c) for c in s if c.tag == "p")
    out = {k: " ".join(v) for k, v in out.items()}
    out["abstract_struct"] = abs_struct
    return out

# ---------------------------------------------------------------------------------------------------------------
# 3. lexicons
# ---------------------------------------------------------------------------------------------------------------
STOP = {"in", "of", "the", "a", "an", "with", "and", "due", "to", "at", "on", "or", "is", "was", "were", "has", "had"}
SPELL = {"diarrhea": "diarrhoea", "edema": "oedema", "anemia": "anaemia", "dyspnea": "dyspnoea", "color": "colour",
         "hemorrhage": "haemorrhage", "anorexia": "anorexia", "tumor": "tumour", "pruritus": "itching",
         "pruritis": "itching", "joint": "joint"}
CLINICAL = {  # modern clinical phrasing -> SAT gloss (only where the gloss exists in the lexicon)
    "joint pain": "pain in joints", "pain in the joint": "pain in joints", "arthralgia": "pain in joints",
    "shortness of breath": "breathlessness", "decreased appetite": "loss of appetite", "poor appetite": "loss of appetite",
    "generalised weakness": "weakness", "generalized weakness": "weakness", "hair loss": "hair fall",
    "sleeplessness": "insomnia", "lack of sleep": "insomnia", "disturbed sleep": "insomnia", "malaise": "body ache",
    "bodyache": "body ache", "loose stool": "diarrhoea", "loose motion": "diarrhoea", "dizziness": "giddiness",
    "lethargy": "fatigue", "tiredness": "fatigue", "puffiness": "swelling", "nausea": "nausea", "belching": "eructation",
    "heart burn": "heartburn", "sour belching": "sour eructation", "hyperacidity": "heartburn",
}

def norm_words(s):
    toks = [w for w in re.findall(r"[a-z]+", ascii_fold(s.lower())) if w not in STOP]
    out = []
    for w in toks:
        w = SPELL.get(w, w)
        if len(w) > 4 and w.endswith("es") and not w.endswith("sses"):
            w = w[:-2] if w[:-2].endswith(("ch", "sh", "ss", "x")) else w[:-1]
        elif len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out

DOSHA_SK = {"vata", "pita", "kapa", "dosa", "dosas", "rasa", "rakta", "mamsa", "meda", "asti", "maja", "sukra", "agni",
            "ama", "srotas", "mala", "vayu", "slesma", "sles", "tridosa", "prakrti", "prakriti"}
GENERIC_SYM_SK = {"roga", "vyadi", "duka", "pida", "vedana", "kriya", "karma", "sarira", "deha", "kaya", "bala",
                  "jala", "udaka", "anna", "ahara", "vihara", "nidana", "rupa", "linga", "sama", "nirama", "kala",
                  "manas", "atma", "satva", "cikitsa", "ausada", "dravya", "guna", "virya", "vipaka", "prabava",
                  "sadya", "asadya", "yapya", "basti", "vamana", "virecana", "nasya", "sneha", "sveda", "lepa"}

SYMPTOM_WORDS = set("""pain fever swelling itching cough vomiting diarrhoea headache giddiness vertigo insomnia anorexia
stiffness redness discharge breathlessness dyspnoea weakness numbness constipation bleeding heaviness fatigue
tastelessness nausea thirst oedema dryness palpitation flatulence tenderness emaciation indigestion salivation
horripilation lacrimation restlessness exhaustion tremor sweating jaundice pallor hiccup hoarseness ulcer eruption
rash scaling crusting oozing blister discolouration dizziness fainting unconsciousness convulsion delirium anxiety
lethargy drowsiness somnolence polyuria dysuria haematuria amenorrhoea dysmenorrhoea menorrhagia leucorrhoea
infertility impotence obesity distension colic cramp spasm paralysis deformity lameness burning tingling heartburn
eructation belching hyperacidity anaemia fissure pus suppuration wheezing sneezing coryza pruritus alopecia
depression irritability malaise ache soreness tinnitus deafness blurring photophobia lassitude""".split())
COMPLAINT_CUE = re.compile(r"complain|present(ed|ing) with|c/o\b|chief|suffer|history of|symptom|associated with|"
                           r"since \d|for (the )?(last|past) \d|onset|noticed|developed|reported", re.I)

def presenting_text(text, max_chars=2500):
    """sentences that state complaints; falls back to the opening of the presentation"""
    sents = re.split(r"(?<=[.!?;])\s+", text)
    keep = " ".join(s for s in sents if COMPLAINT_CUE.search(s))
    return keep if len(keep) >= 150 else text[:max_chars]

def build_lexicons():
    S, D, H, HN, F, T = rd("symptoms"), rd("diseases"), rd("herbs"), rd("herb_names"), rd("formulations"), rd("therapies")
    # symptoms: English gloss phrases (1-4 words) + Sanskrit term skeletons
    sym_en = defaultdict(set)
    for sid, g in zip(S.symptom_id, S.gloss_en):
        for part in re.split(r"[/;]", g):
            w = norm_words(part)
            if (len(w) == 1 and w[0] in SYMPTOM_WORDS) or (2 <= len(w) <= 4 and any(x in SYMPTOM_WORDS for x in w)):
                sym_en[tuple(w)].add(sid)
    for k, v in CLINICAL.items():
        tgt = tuple(norm_words(v))
        if tgt in sym_en:
            sym_en[tuple(norm_words(k))] |= sym_en[tgt]
    sym_sa = defaultdict(set)
    for sid, t in zip(S.symptom_id, S.term_sa_iast):
        for part in re.split(r"[/,;]", t):
            sk = skeleton(part)
            if len(sk) >= 5 and sk not in DOSHA_SK and sk not in GENERIC_SYM_SK:
                sym_sa[sk].add(sid)
    # disorders: each '/'-alternative, plus the stem without -roga/-doṣa/-vikāra; prodromes are not diagnoses
    dis_sk = defaultdict(set)
    keep = D[~D.term_iast.str.contains("pūrvarūp|purvarup", regex=True)]
    for did, t in zip(keep.disease_id, keep.term_iast):
        for part in re.split(r"[/,]", t):
            sk = skeleton(part)
            stem = re.sub(r"(roga|dosa|vikara|vyadi|amaya|gada)$", "", sk)
            for cand in {sk, stem}:
                if cand != sk and (cand in HERB_STOP or cand in SUBSTANCE_STEMS):
                    continue                     # 'kṣīradoṣa' must not match every mention of milk (kṣīra)
                if len(cand) >= 4 and cand not in DOSHA_SK:
                    dis_sk[cand].add(did)
    blocked = {skeleton(x) for x in T.term_sa_iast_primary} | {skeleton(v) for vs in PROCEDURES.values() for v in vs} \
              | {skeleton(c.split("(")[0]) for c in PROCEDURES} | DISEASE_KEY_STOP
    for k in [k for k in dis_sk if k in blocked or len(k) < 5]:
        del dis_sk[k]
    depth = dict(zip(D.disease_id, D.depth))
    # herbs: Sanskrit (IAST/ASCII) by skeleton, Latin binomials and English names as lowercase phrases
    herb_sk, herb_phrase = defaultdict(set), defaultdict(set)
    rows = list(zip(HN.herb_id, HN.name, HN.language_script)) + \
           [(h, n, "la-botanical") for h, n in zip(H.herb_id, H.accepted_name)] + \
           [(h, n, "sa-Latn-IAST") for h, n in zip(H.herb_id, H.name_sa_iast)]
    for hid, name, scr in rows:
        if not name:
            continue
        if scr.startswith("sa-Latn") or scr == "hi-Latn":
            for part in re.split(r"[/,;()]", name):
                sk = skeleton(part)
                if len(sk) >= 5 and sk not in DOSHA_SK and sk not in GENERIC_SYM_SK and sk not in HERB_STOP:
                    herb_sk[sk].add(hid)
        elif scr in ("la-botanical", "en"):
            w = " ".join(re.findall(r"[a-z]+", ascii_fold(name.lower())))
            if scr == "la-botanical":
                w = " ".join(w.split()[:2])
                if len(w.split()) < 2:
                    continue
            if len(w) >= 5 and w not in EN_HERB_STOP:
                herb_phrase[w].add(hid)
    # Sanskrit synonyms (paryāya) are shared by several plants ('amṛtā', 'pippalī'): keep an ambiguous key only for the
    # plant whose PRIMARY name it is, otherwise drop it (precision over recall for text mining)
    primary = defaultdict(set)
    for hid, a, b in zip(H.herb_id, H.name_sa_iast, H.name_ascii):
        for n in (a, b):
            if n:
                primary[skeleton(n)].add(hid)
    for k in [k for k, v in herb_sk.items() if len(v) > 1]:
        own = herb_sk[k] & primary.get(k, set())
        if len(own) == 1:
            herb_sk[k] = own
        else:
            del herb_sk[k]
    # curated formulations: name + search variants
    form_sk = defaultdict(set)
    for fid, n, v in zip(F.form_id, F.name_sa_iast, F.search_variants):
        for part in [n] + re.findall(r'"([^"]+)"', v) + [x for x in re.split(r"[;|]", v) if x and '"' not in x]:
            sk = skeleton(part)
            if len(sk) >= 6:
                form_sk[sk].add(fid)
    # procedures -> WHO/SAT therapy records by skeleton
    th_sk = defaultdict(set)
    for tid, t in zip(T.therapy_id, T.term_sa_iast_primary):
        for part in re.split(r"[/,]", t):
            sk = skeleton(part)
            if len(sk) >= 4:
                th_sk[sk].add(tid)
    return dict(S=S, D=D, H=H, F=F, T=T, sym_en=sym_en, sym_sa=sym_sa, dis_sk=dis_sk, depth=depth,
                herb_sk=herb_sk, herb_phrase=herb_phrase, form_sk=form_sk, th_sk=th_sk)

SUBSTANCE_STEMS = {"ksira", "stanya", "mutra", "purisa", "sveda", "rakta", "mamsa", "meda", "asti", "maja", "sukra",
                   "artava", "kapa", "pita", "vata", "ana", "jala", "udaka", "visa", "agni", "netra", "karna", "nasa",
                   "muka", "danta", "jihva", "kanta", "sira", "hrd", "udara", "guda", "yoni", "sandi", "tvak", "kesa"}
DISEASE_KEY_STOP = {"bina", "binna", "sarvanga", "sarira", "kosta", "abigata", "vyapada", "vyapat", "rogi", "dusti",
                    "kaya", "bala", "mana", "manas", "sadya", "yapya", "asadya", "purvarupa", "upadrava", "arista",
                    "lakṣaṇa", "laksana", "nidana", "virecana", "vamana", "basti", "nasya", "sneha", "sveda"}

# Sanskrit herb names that are also ordinary words in case reports (checked against the corpus)
HERB_STOP = {"madhu", "taila", "ghrta", "dugdha", "ksira", "jala", "takra", "dadhi", "lavana", "saindhava", "guda",
             "sarkara", "tila", "yava", "mudga", "godhuma", "masa", "arka", "kumari", "loha", "svarna", "rajata",
             "tamra", "abraka", "parada", "gandhaka", "vasa", "bala", "vaca", "ela", "jivaka", "rsabaka", "maha",
             "pancakarma", "rasayana", "vajikarana", "patra", "mula", "puspa", "pala", "tvak", "bija", "kanda", "sara",
             "ksara", "basma", "curna", "kvata", "kasaya", "vati", "gutika", "guguluh", "guggulu",
             # tastes, therapy words and homonyms of ordinary words / disease names (checked against the corpus)
             "tikta", "katu", "madura", "amla", "lavana", "kusta", "sarva", "lekana", "patya", "pathya", "sodana",
             "samana", "dipana", "pacana", "vrana", "sota", "jvara", "kasa", "svasa"}
EN_HERB_STOP = {"honey", "sugar", "salt", "water", "milk", "ghee", "rice", "wheat", "barley", "sesame oil", "butter",
                "pepper", "lemon", "orange", "apple", "grape", "banana", "onion", "potato", "tomato", "coconut",
                "linseed", "mustard", "castor", "almond", "date", "datura", "night", "rose", "lotus", "old woman",
                "old man", "black", "white", "red", "yellow", "green", "blue"}

PROCEDURES = {  # canonical name -> spelling variants seen in case reports
    "vamana": ["vamana"], "virecana": ["virechana", "virecana", "virechan"], "basti": ["basti", "vasti", "bastí"],
    "anuvāsana basti": ["anuvasana", "anuvasan", "anuvasana basti"], "nirūha basti": ["niruha", "niruha basti", "asthapana"],
    "mātrā basti": ["matra basti", "matrabasti"], "uttara basti": ["uttara basti", "uttarbasti", "uttar basti"],
    "yoga basti": ["yoga basti"], "kāla basti": ["kala basti"], "karma basti": ["karma basti"],
    "nasya": ["nasya", "nasyam"], "raktamokṣaṇa": ["raktamokshana", "rakta mokshana", "raktamokṣaṇa"],
    "jalaukāvacaraṇa (leech therapy)": ["jalaukavacharana", "jalauka", "leech therapy", "leech application"],
    "sirāvedha": ["siravedha", "siravyadha", "sira vedha"], "snehapāna": ["snehapana", "sneha pana"],
    "abhyaṅga": ["abhyanga", "abhyangam"], "svedana": ["swedana", "svedana", "sudation"],
    "bāṣpa sveda": ["bashpa sweda", "baspa sveda", "steam sudation"], "nāḍī sveda": ["nadi sweda", "nadi sveda"],
    "patra piṇḍa sveda": ["patra pinda sweda", "elakizhi", "ela kizhi", "patrapinda"],
    "ṣaṣṭika śāli piṇḍa sveda": ["shashtika shali", "navarakizhi", "njavarakizhi", "shastika shali"],
    "śirodhārā": ["shirodhara", "sirodhara"], "takradhārā": ["takradhara", "takra dhara"],
    "śirobasti": ["shirobasti", "shiro basti", "sirobasti"], "kaṭibasti": ["kati basti", "katibasti"],
    "jānubasti": ["janu basti", "janubasti"], "grīvābasti": ["greeva basti", "griva basti", "greevabasti"],
    "udvartana": ["udvartana", "udwarthana", "udvarthana"], "pichu": ["pichu"], "lepa": ["lepa", "lepam"],
    "pizhichil": ["pizhichil", "sarvanga dhara"], "netra tarpaṇa": ["netra tarpana", "tarpana", "akshi tarpana"],
    "kṣārasūtra": ["ksharasutra", "kshara sutra", "ksharsutra"], "kṣārakarma": ["kshara karma", "ksharakarma"],
    "agnikarma": ["agnikarma", "agni karma"], "kavala / gaṇḍūṣa": ["kavala", "gandusha", "gandoosha"],
    "karṇapūraṇa": ["karnapurana", "karna purana"], "dīpana-pācana": ["deepana", "dipana", "pachana", "pacana"],
    "saṃsarjana krama": ["samsarjana", "sansarjana"], "rasāyana": ["rasayana"], "yoga / prāṇāyāma": ["pranayama", "yoga therapy"],
    "pathya (diet regimen)": ["pathya", "pathyapathya", "pathya-apathya"],
}

MODERN = [  # (label, category, regex)
    ("ESR", "lab", r"\besr\b|erythrocyte sedimentation"), ("CRP", "lab", r"\bcrp\b|c-reactive protein"),
    ("RA factor", "lab", r"\bra factor\b|rheumatoid factor|\brf\b"), ("anti-CCP", "lab", r"anti-?ccp"),
    ("serum uric acid", "lab", r"uric acid"), ("HbA1c", "lab", r"hba1c|glycated ha?emoglobin|glycosylated"),
    ("blood glucose (FBS/PPBS/RBS)", "lab", r"\bfbs\b|\bppbs\b|\brbs\b|fasting blood (sugar|glucose)|blood sugar|blood glucose"),
    ("lipid profile", "lab", r"lipid profile|cholesterol|triglyceride|\bldl\b|\bhdl\b"),
    ("renal function (creatinine/urea)", "lab", r"creatinine|blood urea|\bbun\b|\begfr\b|renal function"),
    ("liver function (LFT)", "lab", r"\blft\b|sgot|sgpt|\balt\b|\bast\b|bilirubin|liver function|alkaline phosphatase"),
    ("thyroid profile (TSH/T3/T4)", "lab", r"\btsh\b|\bt3\b|\bt4\b|thyroid (profile|function)"),
    ("haemoglobin / CBC", "lab", r"ha?emoglobin|\bhb\b|complete blood count|\bcbc\b|platelet"),
    ("vitamin D / B12", "lab", r"vitamin d|vitamin b12|cobalamin"), ("semen analysis", "lab", r"semen analysis|sperm count|sperm motility"),
    ("hormones (FSH/LH/AMH/prolactin)", "lab", r"\bfsh\b|\blh\b|\bamh\b|prolactin|testosterone|estradiol"),
    ("urine routine / culture", "lab", r"urine (routine|analysis|culture|examination)|urinalysis"),
    ("stool examination", "lab", r"stool (examination|routine|test)|faecal|fecal calprotectin"),
    ("serum heavy metals", "lab", r"blood lead|lead level|serum mercury|arsenic level|heavy metal"),
    ("X-ray", "imaging", r"x-?ray|radiograph"), ("MRI", "imaging", r"\bmri\b|magnetic resonance"),
    ("CT scan", "imaging", r"\bct\b|computed tomography|\bhrct\b"), ("ultrasonography", "imaging", r"\busg\b|ultraso|sonograph"),
    ("ECG / echocardiography", "imaging", r"\becg\b|electrocardiogra|echocardiogra|\b2d echo"),
    ("EEG", "imaging", r"\beeg\b|electroencephalogra"), ("nerve conduction / EMG", "imaging", r"nerve conduction|\bncv\b|\bemg\b|electromyogra"),
    ("DEXA (bone density)", "imaging", r"dexa|bone mineral density"), ("endoscopy / colonoscopy", "imaging", r"endoscop|colonoscop|sigmoidoscop"),
    ("biopsy / histopathology", "lab", r"biopsy|histopatholog"), ("spirometry / PEFR", "physiological", r"spirometr|\bpefr\b|peak expiratory|\bfev1\b"),
    ("visual acuity / IOP", "physiological", r"visual acuity|snellen|intraocular pressure|\biop\b"),
    ("BMI / anthropometry", "physiological", r"\bbmi\b|body mass index|waist circumference"),
    ("blood pressure", "physiological", r"blood pressure|\bmmhg\b"),
    ("VAS (pain)", "scale", r"\bvas\b|visual analog(ue)? scale"), ("PASI (psoriasis)", "scale", r"\bpasi\b"),
    ("DAS28 / ACR (RA)", "scale", r"das-?28|disease activity score|\bacr\b criteria|\bcdai\b|\bhaq\b"),
    ("WOMAC / KOOS (knee)", "scale", r"womac|\bkoos\b|lequesne"), ("Oswestry Disability Index", "scale", r"oswestry|\bodi\b"),
    ("neck/shoulder disability (NDI/SPADI)", "scale", r"neck disability|\bndi\b|spadi"),
    ("SF-36 / QoL", "scale", r"sf-?36|quality of life|\bwhoqol"), ("DLQI / SCORAD / EASI (skin)", "scale", r"dlqi|scorad|\beasi\b"),
    ("HAM-A / HAM-D / BDI (mental health)", "scale", r"hamilton|ham-a|ham-d|beck depression|\bbdi\b|\bgad-7|\bphq-9"),
    ("PSQI / ISI (sleep)", "scale", r"psqi|pittsburgh sleep|insomnia severity index"),
    ("NIHSS / mRS / Barthel (stroke)", "scale", r"nihss|modified rankin|\bmrs\b|barthel"),
    ("MMSE / cognitive tests", "scale", r"\bmmse\b|mini-mental|moca\b"), ("IPSS (prostate)", "scale", r"\bipss\b"),
    ("IBS-SSS", "scale", r"ibs-?sss|ibs severity"), ("Glasgow Coma Scale", "scale", r"glasgow coma|\bgcs\b"),
]
MODERN_RX = [(l, c, re.compile(rx, re.I)) for l, c, rx in MODERN]
ADVERSE = re.compile(r"poison|toxicit|toxic\b|hepatotox|nephrotox|neurotox|\blead\b|plumbism|mercury|arsenic|"
                     r"induced|adverse|injury|intoxication|contaminat|encephalopath|overdose|herb-drug|interaction", re.I)
METALS = {"lead": r"\blead\b|plumbism", "mercury": r"mercury|mercurial|\bparada\b", "arsenic": r"arsenic|arsenical",
          "cadmium": r"cadmium", "copper": r"\bcopper\b"}
FORM_SUFFIX = (r"(?:churna|choorna|curna|kwatha|kwath|kashaya|kashayam|kasaya|vati|vatika|gutika|guggulu|guggul|ghrita|"
               r"ghritam|ghrta|taila|tailam|thailam|asava|arishta|arista|rasa|ras|bhasma|lepa|avaleha|leha|lehya|rasayana|"
               r"pishti|sindura|sindoor|parpati|kshara|arka|phanta|hima|swarasa|kalka|modaka|panaka|anjana|varti|malahara|"
               r"capsule|tablet|syrup)")
FORM_NAME_STOP = {"one", "two", "three", "four", "each", "the", "this", "that", "and", "with", "of", "a", "an", "in", "per",
                  "daily", "twice", "thrice", "oral", "local", "external", "internal", "after", "before", "then", "all"}
TASTES = {"tikta", "katu", "madhura", "amla", "lavana", "kashaya", "kasaya", "madura"}
FORM_RX = re.compile(r"\b((?:[A-Z][a-zāīūṛṅñṭḍṇśṣṃḥ]+[- ]){0,3})(" + FORM_SUFFIX + r")\b")

# ---------------------------------------------------------------------------------------------------------------
# extraction helpers
# ---------------------------------------------------------------------------------------------------------------
def tokens(text):
    return re.findall(r"[A-Za-zÀ-ɏḀ-ỿ]+", unicodedata.normalize("NFC", text))

def find_sk(text, table, max_n=3):
    """n-gram (1..max_n tokens, joined without spaces) skeleton lookup -> {key: ids}"""
    toks = [skeleton(t) for t in tokens(text)]
    hits = {}
    for n in range(max_n, 0, -1):
        for i in range(len(toks) - n + 1):
            key = "".join(toks[i:i + n])
            if key in table:
                hits[key] = table[key]
    return hits

def find_en(text, table, max_n=4):
    w = norm_words(text)
    hits = {}
    for n in range(max_n, 0, -1):
        for i in range(len(w) - n + 1):
            key = tuple(w[i:i + n])
            if key in table:
                hits[" ".join(key)] = table[key]
    return hits

def find_phrase(text, table):
    t = " " + " ".join(re.findall(r"[a-z]+", ascii_fold(text.lower()))) + " "
    return {p: ids for p, ids in table.items() if f" {p} " in t}

def find_procedures(text, lex):
    t = " " + " ".join(re.findall(r"[a-z]+", ascii_fold(text.lower()))) + " "
    out = {}
    for canon, variants in PROCEDURES.items():
        if any(f" {ascii_fold(v.lower())} " in t for v in variants):
            out[canon] = sorted(lex["th_sk"].get(skeleton(canon.split("(")[0].split("/")[0]), set()))[:3]
    return out

def diagnosis(title, kw, abstract, lex):
    """NAMASTE disorders named in the title (preferred), keywords, then abstract; most general match wins ties"""
    for src, text in (("title", title), ("keywords", kw), ("abstract", abstract)):
        hits = find_sk(text, lex["dis_sk"])
        if hits:
            # prefer the longest name (most specific), keep all its disease ids, break ties by shallow depth
            best = max(hits, key=len)
            ids = sorted(hits[best], key=lambda d: lex["depth"].get(d, 9))
            others = [k for k in hits if k != best]
            return src, best, ids, others
    return "", "", [], []

# ---------------------------------------------------------------------------------------------------------------
# 4. evaluation: KB matcher (same IDF-cosine as E3 / the demo) on real presentations
# ---------------------------------------------------------------------------------------------------------------
def kb_matcher():
    ds, D = rd("disease_symptom"), rd("diseases")
    prof = ds.groupby("disease_id").symptom_id.apply(set).to_dict()
    df = Counter(s for v in prof.values() for s in v)
    n = len(prof)
    idf = {s: math.log(n / c) + 1 for s, c in df.items()}
    norm = {d: math.sqrt(sum(idf[s] ** 2 for s in ss)) for d, ss in prof.items()}
    inv = defaultdict(set)
    for d, ss in prof.items():
        for s in ss:
            inv[s].add(d)
    parent = dict(zip(D.disease_id, D.parent_disease_id))
    depth = dict(zip(D.disease_id, D.depth))
    children = defaultdict(set)
    for c, p in parent.items():
        if p:
            children[p].add(c)
    def rank(sids):
        sc = Counter()
        for s in sids:
            for d in inv.get(s, ()):
                sc[d] += idf[s]
        return [d for d, v in sorted(((d, v / norm[d]) for d, v in sc.items()), key=lambda t: -t[1])]
    def family(d):
        fam, stack = {d}, [d]
        while stack:                                   # descendants (subtypes)
            for c in children.get(stack.pop(), ()):
                if c not in fam:
                    fam.add(c); stack.append(c)
        cur = parent.get(d, "")                        # ancestors that are still disorders (depth >= 3)
        while cur and depth.get(cur, 0) >= 3 and cur not in fam:
            fam.add(cur)
            fam |= {s for s in children.get(cur, ())}  # siblings, e.g. vātaja/pittaja subtypes
            cur = parent.get(cur, "")
        return fam
    return rank, family, prof, set(prof)

def evaluate(cases, lex):
    rank, family, prof, with_profile = kb_matcher()
    res = []
    for c in cases:
        if c["case_kind"] != "therapeutic" or not c["dx_ids"]:
            continue
        gold = [d for d in c["dx_ids"] if d in with_profile]
        if not gold:
            continue
        sids = set(c["presentation_symptom_ids"])
        dx_keys = {c["dx_term_key"]} | set(c["dx_other_keys"])
        sids = {s for s in sids if not (lex["sym_key"].get(s, "") in dx_keys)}
        if len(c["presentation_phrases"]) < 2:
            continue
        r = rank(sids)
        fam = set().union(*(family(g) for g in gold))
        pos_exact = next((i for i, d in enumerate(r) if d in gold), None)
        pos_fam = next((i for i, d in enumerate(r) if d in fam), None)
        res.append(dict(case_id=c["case_id"], gold=";".join(gold), n_phrases=len(c["presentation_phrases"]),
                        n_symptom_ids=len(sids), rank_exact=pos_exact, rank_family=pos_fam, top1=r[0] if r else ""))
    if not res:
        return {}, pd.DataFrame()
    R = pd.DataFrame(res)
    n_dis = len(with_profile)
    def hit(col, k):
        return float((R[col].notna() & (R[col] < k)).mean())
    # popularity baseline: disorders ordered by profile size (most-described first)
    pop = [d for d, _ in sorted(prof.items(), key=lambda t: -len(t[1]))]
    pop_pos = {d: i for i, d in enumerate(pop)}
    def pop_hit(k, use_family):
        hits = []
        for g in R.gold:
            gs = g.split(";")
            tgt = set().union(*(family(x) for x in gs)) if use_family else set(gs)
            hits.append(min(pop_pos.get(d, 10 ** 6) for d in tgt) < k)
        return float(pd.Series(hits).mean())
    m = {"n_cases_evaluated": int(len(R)), "n_candidate_disorders": n_dis,
         "median_presenting_phrases": float(R.n_phrases.median())}
    for k in (1, 3, 10, 30):
        m[f"exact_hit@{k}"] = round(hit("rank_exact", k), 3)
        m[f"family_hit@{k}"] = round(hit("rank_family", k), 3)
        m[f"baseline_popularity_family_hit@{k}"] = round(pop_hit(k, True), 3)
        m[f"baseline_random_exact_hit@{k}"] = round(k / n_dis, 4)
    mrr = lambda col: float((1 / (R[col].dropna() + 1)).sum() / len(R))
    m["exact_MRR"], m["family_MRR"] = round(mrr("rank_exact"), 3), round(mrr("rank_family"), 3)
    return m, R

# ---------------------------------------------------------------------------------------------------------------
def extract(recs, lex, keep_text=False):
    """keep_text=True keeps each case's presentation text IN MEMORY for downstream matching; it is never written out"""
    S = lex["S"]
    lex["sym_key"] = {sid: skeleton(t) for sid, t in zip(S.symptom_id, S.term_sa_iast)}
    rows, ents, unknown_forms = [], [], Counter()
    form_known_sk = lex["form_sk"]
    for r in recs:
        pmc, pmid = r.get("pmcid", ""), r.get("pmid", "")
        cid = f"CASE-{pmc or 'PMID' + str(pmid)}"
        title = fix_text(r.get("title", "") or "")
        abstract = fix_text(re.sub(r"<[^>]+>", " ", r.get("abstractText", "") or ""))
        kws = "; ".join((r.get("keywordList") or {}).get("keyword", []))
        mesh = [m.get("descriptorName", "") for m in (r.get("meshHeadingList") or {}).get("meshHeading", [])]
        mesh_major = [m.get("descriptorName", "") for m in (r.get("meshHeadingList") or {}).get("meshHeading", [])
                      if m.get("majorTopic_YN") == "Y"]
        sec = None
        if pmc and (FT / f"{pmc}.xml").exists():
            sec = sections((FT / f"{pmc}.xml").read_bytes())
        has_ft = bool(sec and sec["body"])
        kind = "adverse_event" if ADVERSE.search(title) else "therapeutic"
        src, key, dx_ids, other_keys = diagnosis(title, kws, abstract, lex)
        # presentation text: case/presentation sections of the full text, else the abstract's case part
        if has_ft and len(sec["presentation"]) > 200:
            pres, pres_src = sec["presentation"], "fulltext_case_sections"
        else:
            ab = (sec or {}).get("abstract_struct") or {}
            pres = " ".join(v for k, v in ab.items() if re.search(r"case|present|patient|clinical|finding", k)) or abstract
            pres_src = "abstract"
        treat = (sec["treatment"] + " " + sec["tables"]) if has_ft and len(sec["treatment"]) > 100 else \
                ((sec["body"] + " " + sec["tables"]) if has_ft else abstract)
        alltext = " ".join([title, abstract, (sec or {}).get("body", ""), (sec or {}).get("tables", "")])
        # symptoms (presentation only)
        pres = presenting_text(pres)
        sym_hits = find_en(pres, lex["sym_en"])
        sym_hits.update({f"sa:{k}": v for k, v in find_sk(pres, lex["sym_sa"], 2).items()})
        sym_ids = sorted(set().union(*sym_hits.values())) if sym_hits else []
        # herbs and formulations (treatment text)
        herb_hits = find_sk(treat, lex["herb_sk"], 2)
        herb_hits.update(find_phrase(treat, lex["herb_phrase"]))
        herb_ids = sorted(set().union(*herb_hits.values())) if herb_hits else []
        f_hits = find_sk(treat, form_known_sk, 4)
        form_ids = sorted(set().union(*f_hits.values())) if f_hits else []
        names = set()
        for m in FORM_RX.finditer(treat):
            nm = (m.group(1) + m.group(2)).strip(" -")
            first = nm.split()[0].lower()
            if first in FORM_NAME_STOP or (m.group(2).lower() in ("rasa", "ras") and first in TASTES):
                continue
            if len(nm.split()) >= 2 and len(nm) <= 60:
                names.add(re.sub(r"\s+", " ", nm))
        for nm in names:
            if not any(k in form_known_sk for k in [skeleton(nm), skeleton(nm.rsplit(" ", 1)[0])]):
                unknown_forms[nm.title()] += 1
        procs = find_procedures(treat + " " + abstract, lex)
        modern = sorted({l for l, c, rx in MODERN_RX if rx.search(alltext)})
        metals = sorted({k for k, rx in METALS.items() if re.search(rx, title + " " + abstract, re.I)}) if kind == "adverse_event" else []
        c = dict(case_id=cid, pmcid=pmc, pmid=pmid, doi=r.get("doi", ""), journal=(r.get("journalInfo") or {}).get("journal", {}).get("title", ""),
                 year=r.get("pubYear", ""), title=title, licence=r.get("license", "") or "not open access (metadata only)",
                 open_access=r.get("isOpenAccess", "N"), fulltext_mined=has_ft, case_kind=kind,
                 dx_source=src, dx_term_key=key, dx_other_keys=other_keys, dx_ids=dx_ids,
                 mesh_major=mesh_major, mesh=mesh, keywords=kws, presentation_source=pres_src,
                 presentation_phrases=sorted(sym_hits), presentation_symptom_ids=sym_ids, herb_ids=herb_ids,
                 form_ids=form_ids, other_formulation_names=sorted(names), procedures=sorted(procs), modern=modern, metals=metals,
                 _pres=pres if keep_text else None, _kws=kws if keep_text else None)
        rows.append(c)
        for k, v in sym_hits.items():
            ents.append((cid, "symptom", k, ";".join(sorted(v)[:20])))
        for k, v in herb_hits.items():
            ents.append((cid, "herb", k, ";".join(sorted(v))))
        for k, v in f_hits.items():
            ents.append((cid, "formulation", k, ";".join(sorted(v))))
        for nm in sorted(names):
            ents.append((cid, "formulation_name", nm, ""))
        for k, v in procs.items():
            ents.append((cid, "procedure", k, ";".join(v)))
        for l in modern:
            ents.append((cid, "modern_assessment", l, ""))
        for m_ in metals:
            ents.append((cid, "metal_implicated", m_, ""))
    return rows, ents, unknown_forms

def main(no_fetch=False):
    recs = json.loads((CACHE / "epmc_case_reports.json").read_text()) if no_fetch else fetch()
    # de-duplicate (MED and PMC records of the same article)
    seen, uniq = set(), []
    for r in recs:
        k = r.get("pmcid") or r.get("pmid") or r.get("id")
        if k not in seen:
            seen.add(k); uniq.append(r)
    lex = build_lexicons()
    rows, ents, unknown = extract(uniq, lex)
    metrics, R = evaluate(rows, lex)
    D = lex["D"].set_index("disease_id")
    j = lambda xs: "; ".join(xs)
    out = pd.DataFrame([dict(
        case_id=c["case_id"], pmcid=c["pmcid"], pmid=c["pmid"], doi=c["doi"], journal=c["journal"], year=c["year"],
        title=c["title"], article_licence=c["licence"], open_access=c["open_access"], fulltext_mined=c["fulltext_mined"],
        case_kind=c["case_kind"], dx_disease_ids=j(c["dx_ids"]),
        dx_term_iast=j(dict.fromkeys(D.loc[d].term_iast for d in c["dx_ids"])), dx_name_en=j(dict.fromkeys(D.loc[d].name_en for d in c["dx_ids"])),
        dx_found_in=c["dx_source"], mesh_major_topics=j(c["mesh_major"]), presentation_source=c["presentation_source"],
        n_presenting_symptom_phrases=len(c["presentation_phrases"]), presenting_symptom_phrases=j(c["presentation_phrases"]),
        herb_ids=j(c["herb_ids"]), form_ids=j(c["form_ids"]), formulation_names_observed=j(c["other_formulation_names"]),
        procedures=j(c["procedures"]), modern_assessments=j(c["modern"]), metals_implicated=j(c["metals"]),
        source_id="S10", data_origin="text-mined (KB lexicons) from Europe PMC; verify against the article",
        licence="bibliographic metadata, extracted identifiers and short source-derived phrases; full article caches excluded; per-article terms require review")
        for c in rows])
    out.to_csv(P / "case_reports.csv", index=False)
    E = pd.DataFrame(ents, columns=["case_id", "entity_type", "mention_key", "kb_ids"])
    E.to_csv(P / "case_report_entities.csv", index=False)
    # diagnosis x herb / formulation co-occurrence across real cases (curation queue, not merged into the KB)
    hi = rd("herb_indication"); fi = rd("formulation_indications")
    kb_h = set(zip(hi.disease_id, hi.herb_id)); kb_f = set(zip(fi.disease_id, fi.form_id))
    _, family, _, _ = kb_matcher()
    link = Counter(); link_cases = defaultdict(list)
    for c in rows:
        if c["case_kind"] != "therapeutic" or not c["dx_ids"]:
            continue
        d0 = c["dx_ids"][0]
        for h in c["herb_ids"]:
            link[(d0, "herb", h)] += 1; link_cases[(d0, "herb", h)].append(c["case_id"])
        for f in c["form_ids"]:
            link[(d0, "formulation", f)] += 1; link_cases[(d0, "formulation", f)].append(c["case_id"])
    H = lex["H"].set_index("herb_id"); F = lex["F"].set_index("form_id")
    L = []
    for (d, t, e), n in link.most_common():
        fam = family(d)
        in_kb = any((x, e) in (kb_h if t == "herb" else kb_f) for x in fam)
        L.append(dict(disease_id=d, disease_term_iast=D.loc[d].term_iast, entity_type=t, entity_id=e,
                      entity_name=(H.loc[e].name_sa_iast or H.loc[e].accepted_name) if t == "herb" else F.loc[e].name_sa_iast,
                      n_cases=n, case_ids=";".join(link_cases[(d, t, e)][:20]), in_kb_for_disorder_family=in_kb,
                      source_id="S10", data_origin="co-occurrence in published case reports (not curated)"))
    L = pd.DataFrame(L)
    L.to_csv(P / "case_report_links.csv", index=False)
    cand = pd.DataFrame([(n, k) for n, k in unknown.most_common() if k >= 2], columns=["formulation_name_observed", "n_case_reports"])
    cand.to_csv(ROOT / "curation/candidates_formulations_from_cases.csv", index=False)
    # summary
    th = out[out.case_kind == "therapeutic"]
    used_h = E[E.entity_type == "herb"].case_id.nunique()
    summ = {
        "query": QUERY, "n_records": len(out), "n_fulltext_mined": int(out.fulltext_mined.sum()),
        "n_therapeutic": int((out.case_kind == "therapeutic").sum()), "n_adverse_event": int((out.case_kind == "adverse_event").sum()),
        "dx_mapped_to_namaste": round(float((th.dx_disease_ids != "").mean()), 3),
        "cases_with_>=2_presenting_symptoms": int((th.n_presenting_symptom_phrases >= 2).sum()),
        "cases_with_kb_herbs": int(used_h), "cases_with_curated_formulation": int((out.form_ids != "").sum()),
        "distinct_formulation_names_not_in_kb_(>=2 reports)": int(len(cand)),
        "top_diagnoses": Counter(t for t in th.dx_term_iast if t).most_common(25),
        "top_herbs": Counter(h for hs in out.herb_ids for h in hs.split("; ") if h).most_common(25),
        "top_procedures": Counter(p for ps in out.procedures for p in ps.split("; ") if p).most_common(25),
        "top_modern_assessments": Counter(p for ps in out.modern_assessments for p in ps.split("; ") if p).most_common(30),
        "metals_in_adverse_event_reports": Counter(p for ps in out.metals_implicated for p in ps.split("; ") if p).most_common(),
        "kb_link_concordance": {
            "observed_disorder_herb_pairs": int((L.entity_type == "herb").sum()) if len(L) else 0,
            "share_recorded_in_kb": round(float(L[L.entity_type == "herb"].in_kb_for_disorder_family.mean()), 3) if len(L) else None,
            "observed_disorder_formulation_pairs": int((L.entity_type == "formulation").sum()) if len(L) else 0,
            "share_formulation_pairs_recorded_in_kb": round(float(L[L.entity_type == "formulation"].in_kb_for_disorder_family.mean()), 3)
                if len(L) and (L.entity_type == "formulation").any() else None},
        "E6_matcher_on_real_presentations": metrics,
    }
    REP.mkdir(parents=True, exist_ok=True)
    (REP / "E6_case_reports.json").write_text(json.dumps(summ, indent=2, ensure_ascii=False))
    if len(R):
        R.to_csv(REP / "E6_case_reports_ranks.csv", index=False)
    print(json.dumps({k: v for k, v in summ.items() if not k.startswith("top_")}, indent=1, ensure_ascii=False)[:3000])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true", help="use the cached Europe PMC search results")
    main(ap.parse_args().no_fetch)
