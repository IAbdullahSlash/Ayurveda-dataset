#!/usr/bin/env python3
"""
Stage 02a - Parse 'WHO international standard terminologies on Ayurveda' (2022) into a table.

Method: pdftotext -bbox-layout gives every word with its coordinates.  The term tables have five
columns (Term ID | English term | Description | Sanskrit IAST | Sanskrit Devanagari); words are
assigned to columns by x-position (boundaries learnt per page from the bold header row), and to
rows by the y-position of the 'ITA-x.y.z' identifiers.  Section headings are detected and kept
as metadata.  The parse is then VALIDATED against Annex 2 of the same book (index of every
transliterated term with its ID and Devanagari form).
Output: data/interim/who_terms.csv, data/interim/who_sections.csv, reports/who_parse_validation.json
"""
import html, json, re, subprocess, unicodedata
from collections import defaultdict
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data/raw/who/WHO_international_standard_terminologies_on_ayurveda_2022.pdf"
OUT = ROOT / "data/interim"
ID_RE = re.compile(r"^ITA-\d+(\.\d+)+$")
SEC_RE = re.compile(r"^\d+(\.\d+)*$")
NS = "{http://www.w3.org/1999/xhtml}"

def words_by_page():
    # regex instead of an XML parser: the bbox output is not always well-formed XML
    xml = subprocess.run(["pdftotext", "-bbox-layout", "-enc", "UTF-8", str(PDF), "-"],
                         capture_output=True, check=True).stdout.decode("utf-8", errors="replace")
    word_re = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', re.S)
    pages = []
    for chunk in xml.split("<page ")[1:]:
        ws = [dict(t=html.unescape(m.group(5)), x=float(m.group(1)), y=float(m.group(2)),
                   x2=float(m.group(3)), y2=float(m.group(4))) for m in word_re.finditer(chunk)]
        pages.append(ws)
    return pages

def header_y(ws):
    """y of the bold table-header row (located by its 'Description' cell); None if no table on page."""
    ys = [w["y"] for w in ws if w["t"] == "Description" and w["x"] > 200]
    return min(ys) if ys else None

def col_bounds(ws):
    """Column x-boundaries from the header row ('Term ID','English term','Description','Sanskrit...').
    The header is not always at the top: on a chapter's first page it sits below the chapter title."""
    hy = header_y(ws)
    if hy is None:
        return None
    hdr = [w for w in ws if abs(w["y"] - hy) < 3]
    def x_of(token, nth=0):
        xs = sorted(w["x"] for w in hdr if w["t"] == token)
        return xs[nth] if len(xs) > nth else None
    en, de, s1, s2 = x_of("English"), x_of("Description"), x_of("Sanskrit", 0), x_of("Sanskrit", 1)
    if None in (en, de, s1, s2):
        return None
    return [en - 6, de - 6, s1 - 6, s2 - 6]   # boundaries between the 5 columns

def lines(ws, tol=2.5):
    """group words into visual lines by y."""
    out = []
    for w in sorted(ws, key=lambda w: (w["y"], w["x"])):
        if out and abs(out[-1][0] - w["y"]) <= tol:
            out[-1][1].append(w)
        else:
            out.append([w["y"], [w]])
    return out

def join_col(frags, hyphen_fix=True):
    """join line fragments of a cell; repair soft hyphenation (speciali- ties -> specialities)."""
    txt = ""
    for f in frags:
        f = f.strip()
        if not f:
            continue
        if not txt:
            txt = f
        elif hyphen_fix and re.search(r"[a-z]{3,}-$", txt) and re.match(r"^[a-z]", f):
            txt = txt[:-1] + f
        elif txt.endswith("-") and not hyphen_fix:
            txt = txt + f
        else:
            txt = txt + " " + f
    return re.sub(r"\s+", " ", txt).strip()

def parse_terms(pages):
    rows, sections = [], {}
    last_b = None
    for pno, ws in enumerate(pages, start=1):
        n_ids = sum(ID_RE.match(w["t"]) is not None and w["x"] < 120 for w in ws)
        if not n_ids:
            continue
        b = col_bounds(ws)
        hy = header_y(ws)
        if b is None:
            # continuation page without a repeated header row (e.g. chapter 10): reuse previous
            # page's column bounds. Annex index pages never get here: their IDs sit mid-page (x>120).
            if last_b is None:
                continue
            b, hy = last_b, 40.0
        last_b = b
        # drop header row, running footer and the vertical 'Chapter n' tabs in the side margins
        body = [w for w in ws if hy + 8 <= w["y"] < 552 and 40 < w["x"] < 800]
        # --- detect & remove section headings: a line whose first word is a bare section number
        keep = []
        for y, lw in lines(body):
            lw = sorted(lw, key=lambda w: w["x"])
            if SEC_RE.match(lw[0]["t"]) and lw[0]["x"] < b[0] and not ID_RE.match(lw[0]["t"]):
                sections[lw[0]["t"]] = " ".join(w["t"] for w in lw[1:])
                continue
            keep.extend(lw)
        ids = sorted([w for w in keep if ID_RE.match(w["t"]) and w["x"] < b[0]], key=lambda w: w["y"])
        # Two layouts occur: IDs top-aligned with their row (most pages) or vertically CENTRED in a
        # multi-line row (e.g. chapter 6).  Segment both ways and keep the one giving well-formed rows.
        top = [idw["y"] - 3 for idw in ids]
        ctr = [(ids[i - 1]["y2"] + idw["y"]) / 2 if i else min([w["y"] for w in keep] + [idw["y"]]) - 1 for i, idw in enumerate(ids)]
        best_rows, best_score = None, -1e9
        for starts in (top, ctr):
            cand = []
            for i, idw in enumerate(ids):
                y0, y1 = starts[i], (starts[i + 1] if i + 1 < len(ids) else 1e9)
                cell = defaultdict(list)
                for y, lw in lines([w for w in keep if y0 <= w["y"] < y1 and w is not idw]):
                    for c in range(5):
                        lo = -1 if c == 0 else b[c - 1]
                        hi = b[c] if c < 4 else 1e9
                        frag = " ".join(w["t"] for w in sorted(lw, key=lambda w: w["x"]) if lo <= w["x"] < hi)
                        if frag:
                            cell[c].append(frag)
                cand.append(dict(term_id=idw["t"], page=pno, english_term=join_col(cell[1]), description=join_col(cell[2]),
                                 iast=join_col(cell[3], hyphen_fix=False), devanagari=join_col(cell[4], hyphen_fix=False),
                                 stray_id_col=join_col(cell[0])))
            score = sum((r["iast"] != "") + (r["devanagari"] != "") + bool(re.match(r"^[A-Z0-9(“\"']", r["english_term"]))
                        - 2 * bool(re.match(r"^[a-z]", r["english_term"])) for r in cand)
            if score > best_score:
                best_rows, best_score = cand, score
        rows.extend(best_rows)
    return pd.DataFrame(rows), sections

def parse_annex(pages):
    """Annex 2: 'iast  ITA-x.y  देवनागरी' triples, two per line."""
    trip = []
    for ws in pages:
        for y, lw in lines(ws):
            lw = sorted(lw, key=lambda w: w["x"])
            idx = [i for i, w in enumerate(lw) if ID_RE.match(w["t"])]
            if not idx:
                continue
            for k, i in enumerate(idx):
                start = idx[k - 1] + 1 if k else 0
                # words before the id (since previous id's devanagari) -> split iast | deva by script
                prev = lw[start:i]
                iast = " ".join(w["t"] for w in prev if not re.search(r"[ऀ-ॿ]", w["t"]))
                nxt_end = idx[k + 1] if k + 1 < len(idx) else len(lw)
                deva = " ".join(w["t"] for w in lw[i + 1:nxt_end] if re.search(r"[ऀ-ॿ]", w["t"]))
                trip.append((lw[i]["t"], iast.strip(), deva.strip()))
    return pd.DataFrame(trip, columns=["term_id", "iast_annex", "devanagari_annex"])

def nfc(s):
    return unicodedata.normalize("NFC", s or "")

def main():
    pages = words_by_page()
    print("pages", len(pages))
    terms, sections = parse_terms(pages)
    # Annex 2 starts after 'References'; find pages whose text has many ITA ids but no column header
    annex_pages = [ws for ws in pages if sum(ID_RE.match(w["t"]) is not None for w in ws) > 20 and col_bounds(ws) is None]
    annex = parse_annex(annex_pages)
    for c in ["english_term", "description", "iast", "devanagari"]:
        terms[c] = terms[c].map(nfc)
    terms["section_id"] = terms.term_id.str.replace("ITA-", "", regex=False).str.rsplit(".", n=1).str[0]
    terms["chapter"] = terms.term_id.str.extract(r"ITA-(\d+)")[0].astype(int)
    terms = terms.drop_duplicates("term_id", keep="first")
    sec = pd.DataFrame(sorted(sections.items(), key=lambda kv: [int(p) for p in kv[0].split(".")]),
                       columns=["section_id", "section_title"])
    terms = terms.merge(sec, on="section_id", how="left")
    # cross-references occasionally printed inside the IAST cell ("... ITA.3.11.45")
    xref = re.compile(r"\s*\(?\b(?:see\s+)?ITA[.-]\d+(?:\.\d+)+\)?")
    terms["cross_ref"] = terms.iast.str.findall(r"ITA[.-]\d+(?:\.\d+)+").str.join(";")
    terms["iast"] = terms.iast.str.replace(xref, "", regex=True).str.strip()

    # ---- validation against Annex 2 (one annex line per synonym -> membership test)
    def toks(s):
        s = nfc(s).lower().replace("[", ",").replace("]", ",")
        return {t.strip(" .()") for t in re.split(r"[,;/]|\band\b", s) if t.strip(" .()")}
    syn_iast = terms.set_index("term_id").iast.map(toks).to_dict()
    syn_deva = terms.set_index("term_id").devanagari.map(toks).to_dict()
    def nospace(s):
        return re.sub(r"[\s\-]", "", s)
    def member(tid, val, syn):
        if tid not in syn:
            return None
        v = nfc(val).lower().strip(" .")
        return v in syn[tid] or nospace(v) in {nospace(x) for x in syn[tid]}
    annex["iast_found"] = [member(t, v, syn_iast) for t, v in zip(annex.term_id, annex.iast_annex)]
    annex["deva_found"] = [member(t, v, syn_deva) for t, v in zip(annex.term_id, annex.devanagari_annex)]
    known = annex[annex.iast_found.notna()]
    id_cov = annex.term_id.isin(terms.term_id)
    report = dict(
        n_terms=int(len(terms)), n_sections=int(len(sec)), n_annex_entries=int(len(annex)),
        annex_ids_found_in_parse=round(float(id_cov.mean()), 4),
        parsed_ids_found_in_annex=round(float(terms.term_id.isin(annex.term_id).mean()), 4),
        annex_iast_synonym_recovered=round(float(known.iast_found.astype(bool).mean()), 4),
        annex_devanagari_synonym_recovered=round(float(known.deva_found.astype(bool).mean()), 4),
        empty_english=int((terms.english_term == "").sum()),
        empty_description=int((terms.description == "").sum()),
        empty_iast=int((terms.iast == "").sum()),
        rows_with_stray_id_col_text=int((terms.stray_id_col != "").sum()),
        terms_per_chapter=terms.chapter.value_counts().sort_index().to_dict(),
    )
    ok = known.groupby("term_id").iast_found.all().rename("iast_annex_ok")
    terms = terms.merge(ok, on="term_id", how="left")
    # rows whose Sanskrit cell slid into the neighbouring row (mixed alignment on a page): take the
    # term from Annex 2 of the same publication and remove it from the neighbour
    first_annex = annex.drop_duplicates("term_id").set_index("term_id")
    terms["sanskrit_from_annex"] = False
    for i in terms.index[(terms.iast == "") & terms.term_id.isin(first_annex.index)]:
        a = first_annex.loc[terms.at[i, "term_id"]]
        terms.at[i, "iast"], terms.at[i, "devanagari"], terms.at[i, "sanskrit_from_annex"] = a.iast_annex, a.devanagari_annex, True
        for j in (i - 1, i + 1):
            if j in terms.index and a.iast_annex and a.iast_annex in terms.at[j, "iast"] and terms.at[j, "iast"] != a.iast_annex:
                terms.at[j, "iast"] = re.sub(r"\s*,?\s*" + re.escape(a.iast_annex) + r"\s*,?", " ", terms.at[j, "iast"]).strip(" ,")
                terms.at[j, "devanagari"] = re.sub(r"\s*,?\s*" + re.escape(a.devanagari_annex) + r"\s*,?", " ", terms.at[j, "devanagari"]).strip(" ,")
    report["sanskrit_filled_from_annex"] = int(terms.sanskrit_from_annex.sum())
    annex.to_csv(OUT / "who_annex_index.csv", index=False)
    missing = annex[~id_cov].drop_duplicates("term_id")
    missing.to_csv(OUT / "who_annex_ids_missing_in_parse.csv", index=False)
    terms.to_csv(OUT / "who_terms.csv", index=False)
    sec.to_csv(OUT / "who_sections.csv", index=False)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/who_parse_validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
