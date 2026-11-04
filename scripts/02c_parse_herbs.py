#!/usr/bin/env python3
"""
Stage 02c - Parse herb / materia-medica sources.

  SAT-F (NAMASTE)  : official plant list (Sanskrit name, botanical name+author, synonyms, accepted
                     substitutes, English names), animal & mineral drugs, Caraka's 50 mahākaṣāya
                     groups (10 herbs each, with botanical names), karma (pharmacological actions).
  Amidha herb DB   : rasa, guṇa, vīrya, vipāka, karma, doṣa effects, parts used, indications (360 herbs).
  USDA Duke        : taxa, plant->chemical (with plant part), chemical->activity, ethnobotany.
Outputs (data/interim): sat_plants.csv, sat_animal_mineral.csv, mahakashaya_groups.csv,
  mahakashaya_members.csv, sat_karma.csv, amidha_herbs.csv, duke_*.parquet
"""
import json, re, sys, zipfile, io
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.indic import fix_text, iast_to_deva, hindi_usage_form, ascii_fold, iso_to_iast

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"

BOT_RE = re.compile(r"^\s*([A-Z][a-z]+)\s+(×\s*)?([a-z][a-z\-]+)"
                    r"(?:\s+(subsp\.|ssp\.|var\.|f\.)\s+([a-z][a-z\-]+))?\s*(.*)$")

def split_binomial(txt):
    """'Terminalia arjuna (Roxb. ex DC.) Wight & Arn.' -> ('Terminalia arjuna', '(Roxb. ex DC.) Wight & Arn.')"""
    m = BOT_RE.match(txt or "")
    if not m:
        return "", ""
    g, hyb, sp, rank, infra, rest = m.groups()
    name = f"{g} {'× ' if hyb else ''}{sp}" + (f" {rank} {infra}" if rank else "")
    author = re.split(r"\s+synonymous|\s*;|\s+syn\.", rest)[0].strip(" ,")
    return name, author

def split_members(txt):
    """'drākṣā [Vitis vinifera Linn.], prabha, pippalīmūla [root of Piper longum L.]' ->
    [('drākṣā','Vitis vinifera Linn.'), ('prabha',''), ('pippalīmūla','root of Piper longum L.')]"""
    items, depth, cur = [], 0, ""
    txt = re.sub(r"\]\s+(?=[^\s,;\]])", "], ", txt or "")     # source sometimes omits the comma after ']'
    for ch in txt:
        depth += (ch == "[") - (ch == "]")
        if ch in ",;" and depth == 0:
            items.append(cur); cur = ""
        else:
            cur += ch
    items.append(cur)
    out = []
    for it in items:
        it = it.strip(" .")
        if not it:
            continue
        m = re.match(r"^(.*?)\s*\[(.*?)\]?\s*$", it)
        nm, note = (m.group(1), m.group(2)) if m and "[" in it else (it, "")
        nm = re.sub(r"\s+", "", nm.strip(" ,."))          # names are single compounds ('ma jiṣṭha' -> 'mañjiṣṭha'-ish)
        if nm:
            out.append((nm, note.strip()))
    return out

def parse_sat_f():
    s = pd.read_csv(INT / "namaste_sat.csv", keep_default_na=False)
    f = s[s.section == "F"].copy()
    f["t_id"] = f.t_id.astype(int)
    f["parent_id"] = pd.to_numeric(f.parent_id, errors="coerce").fillna(-1).astype(int)
    # ---- plants: children of 'dravyaguṇa-vijñānam' (t_id 2) whose short definition is a binomial
    pl = f[(f.parent_id == 2) & f.short_definition.str.match(r"^\s*[A-Z][a-z]+ (×\s*)?[a-z]")].copy()
    bn = pl.short_definition.map(split_binomial)
    pl["botanical_name"] = [b[0] for b in bn]
    pl["botanical_author"] = [b[1] for b in bn]
    pl["botanical_synonyms"] = pl.short_definition.str.findall(
        r"synonymous\s*with\s*([A-Z][a-z]+ [a-z\-]+)").map(lambda xs: "; ".join(dict.fromkeys(xs)))
    ld = pl.long_definition
    pl["english_names"] = ld.str.split(r";\s*|\s*can be substituted", regex=True).str[0].str.strip(" ,.")
    pl["substitutes"] = ld.str.extract(r"substituted with\s*(.*)$")[0].fillna("").map(
        lambda t: "; ".join(split_binomial(x)[0] for x in re.split(r"\s*\d+\.\s*", t) if split_binomial(x)[0]))
    pl["formula_synonyms_iast"] = ld.str.extract(r"mentioned in formulae as:-?\s*(.*)$")[0].fillna("")
    plants = pl.rename(columns={"term_iast": "name_sa_iast", "term_deva": "name_sa_deva", "term_hi": "name_hi_usage",
                                "word_phonetic": "name_phonetic"})[
        ["sat_id", "name_phonetic", "name_sa_iast", "name_sa_deva", "name_hi_usage", "botanical_name",
         "botanical_author", "botanical_synonyms", "english_names", "substitutes", "formula_synonyms_iast",
         "short_definition", "long_definition"]]
    # ---- animal / mineral origin drugs (children of t_id 241 'khanija')
    am = f[f.parent_id == 241].rename(columns={"term_iast": "name_sa_iast", "term_deva": "name_sa_deva",
                                               "term_hi": "name_hi_usage"})
    am["source_material_en"] = am.short_definition
    am["english_names"] = am.long_definition.str.split(r";", regex=True).str[0].str.strip()
    am["formula_synonyms_iast"] = am.long_definition.str.extract(r"mentioned in formulae as:-?\s*(.*)$")[0].fillna("")
    am = am[["sat_id", "name_sa_iast", "name_sa_deva", "name_hi_usage", "source_material_en", "english_names",
             "formula_synonyms_iast", "long_definition"]]
    # ---- mahākaṣāya groups (children of t_id 188) and their ten members
    g = f[f.parent_id == 188].copy()
    groups, members = [], []
    for _, r in g.iterrows():
        groups.append(dict(group_id=r.sat_id, group_sa_iast=r.term_iast, group_sa_deva=r.term_deva,
                           group_hi_usage=r.term_hi, action_en=r.short_definition, members_raw=r.long_definition))
        for k, (nm, note) in enumerate(split_members(r.long_definition), 1):
            # 'root of Piper longum L.' / 'white variety of Cynodon dactylon' -> organism name only;
            # 'Wood-fordia fruticosa' (hyphenated line-break in source) -> 'Woodfordia fruticosa'
            nt = re.sub(r"^\s*[A-Za-z ]+?\s+of\s+", "", note or "")
            nt = re.sub(r"\b([A-Z][a-z]+)-\s?([a-z]+)\b", r"\1\2", nt)
            bot = re.match(r"^\s*([A-Z][a-z]{2,})\s+([a-z][a-z\-]{2,})", nt)
            members.append(dict(group_id=r.sat_id, member_rank=k, member_sa_iast=iso_to_iast(nm).lower(),
                                member_botanical=(f"{bot.group(1)} {bot.group(2).strip('-')}" if bot else ""),
                                member_note=note,
                                member_part_or_variety=(re.match(r"^\s*([a-z ]+?)\s+of\s+", note).group(1)
                                                        if re.match(r"^\s*([a-z ]+?)\s+of\s+", note or "") else "")))
    groups, members = pd.DataFrame(groups), pd.DataFrame(members)
    groups["n_members_parsed"] = groups.group_id.map(members.groupby("group_id").size()).fillna(0).astype(int)
    # ---- karma (actions), children of t_id 60
    k = f[f.parent_id == 60].rename(columns={"term_iast": "karma_sa_iast", "term_deva": "karma_sa_deva",
                                             "term_hi": "karma_hi_usage"})[
        ["sat_id", "karma_sa_iast", "karma_sa_deva", "karma_hi_usage", "short_definition", "long_definition"]]
    return plants, am, groups, members, k

# ----------------------------------------------------------------------------- Amidha herb DB
DOSHA = {"vata": "Vata", "pitta": "Pitta", "kapha": "Kapha"}

def parse_amidha():
    d = json.loads((ROOT / "data/raw/amidha_herb_db/herb.json").read_text(encoding="utf-8"))
    rows = []
    for i, h in enumerate(d, 1):
        def lst(k):
            v = h.get(k) or []
            v = v if isinstance(v, list) else [v]
            return [fix_text(x) for x in v if fix_text(x)]
        pac = lst("pacify")
        if any(p.lower() == "tridosha" for p in pac) or h.get("tridosha"):
            pac = ["Vata", "Pitta", "Kapha"]
        pac = sorted({DOSHA.get(p.lower(), p) for p in pac}, key=["Vata", "Pitta", "Kapha"].index)
        agg = sorted({DOSHA.get(p.lower(), p) for p in lst("aggravate")}, key=["Vata", "Pitta", "Kapha"].index)
        karma = [("Rasayana" if k.lower().startswith("rasayan") else k) for k in lst("prabhav")]
        rows.append(dict(
            amidha_id=f"AMD-{i:03d}", name=fix_text(h["name"]), botanical_name=fix_text(h["botanical_name"]),
            family=fix_text(h["family"]), english_name=fix_text(h["english_name"]),
            sanskrit_synonyms="; ".join(lst("sanskrit_synonyms")), parts_used="; ".join(lst("part_used")),
            indications="; ".join(lst("main_indications")), description_en=fix_text(h.get("preview")),
            rasa="; ".join(lst("rasa")), guna="; ".join(lst("guna")), virya=fix_text(h.get("virya")),
            vipaka=fix_text(h.get("vipaka")), karma_actions="; ".join(dict.fromkeys(karma)),
            dosha_pacify="; ".join(pac), dosha_aggravate="; ".join(agg),
            tridosha_flag=bool(h.get("tridosha")),
            link=("https://www.amidhaayurveda.com" + h["link"]) if str(h.get("link", "")).startswith("/") else h.get("link", ""),
        ))
    a = pd.DataFrame(rows)
    a["conflict_pacify_and_aggravate"] = [bool(set(p.split("; ")) & set(g.split("; ")) - {""})
                                          for p, g in zip(a.dosha_pacify, a.dosha_aggravate)]
    return a

# ----------------------------------------------------------------------------- USDA Duke
def parse_duke():
    z = zipfile.ZipFile(ROOT / "data/raw/usda_duke/Duke-Source-CSV.zip")
    def rd(name):
        with z.open(name) as fh:
            return pd.read_csv(io.BytesIO(fh.read()), dtype=str, encoding="latin-1", keep_default_na=False)
    for name in ["FNFTAX", "FARMACY_NEW", "AGGREGAC", "ETHNOBOT", "COMMON_NAMES", "PARTS", "REFERENCES", "CHEMICALS", "ACTIVITIES"]:
        df = rd(f"{name}.csv")
        for c in df.columns:
            if df[c].dtype == object:
                df[c] = df[c].str.strip()
        df.to_parquet(INT / f"duke_{name.lower()}.parquet", index=False)
        print(f"  duke {name}: {df.shape}")

def main():
    plants, am, groups, members, karma = parse_sat_f()
    plants.to_csv(INT / "sat_plants.csv", index=False)
    am.to_csv(INT / "sat_animal_mineral.csv", index=False)
    groups.to_csv(INT / "mahakashaya_groups.csv", index=False)
    members.to_csv(INT / "mahakashaya_members.csv", index=False)
    karma.to_csv(INT / "sat_karma.csv", index=False)
    a = parse_amidha()
    a.to_csv(INT / "amidha_herbs.csv", index=False)
    parse_duke()
    print(f"SAT plants {len(plants)} (with botanical {int((plants.botanical_name!='').sum())}); animal/mineral {len(am)}; "
          f"mahakashaya groups {len(groups)} members {len(members)} (groups with 10 parsed: {(groups.n_members_parsed==10).sum()}); karma {len(karma)}")
    print(f"Amidha herbs {len(a)}; pacify/aggravate conflicts {int(a.conflict_pacify_and_aggravate.sum())}; "
          f"duplicate botanical names {int(a.botanical_name.duplicated(keep=False).sum())}")

if __name__ == "__main__":
    main()
