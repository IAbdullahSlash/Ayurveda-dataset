#!/usr/bin/env python3
"""
Stage 18 - Links from KB herbs to openly licensed medicinal-plant IMAGE datasets (plant identification hook).

Three CC BY 4.0 datasets on Mendeley Data are linked at species level, so an image classifier trained on them can
hand its prediction straight to the KB (herb -> properties, indications, safety):
  * MED117 Medicinal Plant Leaf Dataset & Name Table (Sarma & Boruah 2023), 117 species, DOI 10.17632/dtvbwrhznz.4
  * Medicinal Leaf Dataset (30 species), DOI 10.17632/nnytj2v3n5.1
  * Indian Medicinal Leaves Image Datasets (Pushpa & Rani 2023), ~80 leaf / 40 plant classes, DOI 10.17632/748f8jkphb.3
    (class labels are local names - mapped to binomials by a curated table below)
Only the class labels (folder names, via the Mendeley public API) are used; no images are copied.
Species are matched to KB herbs through GBIF accepted taxon keys (synonyms resolved), then exact binomials.
Output: data/processed/herb_image_datasets.csv
"""
import json, re, time
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
P, RAW, CACHE = ROOT / "data/processed", ROOT / "data/raw/image_datasets", ROOT / "data/interim/cache"
RAW.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "ayurveda-open-dataset-builder/1.0 (research)"}
DATASETS = [("MED117", "dtvbwrhznz", 4, "Sarma P, Boruah PA. MED117 Medicinal Plant Leaf Dataset & Name Table. Mendeley Data 2023"),
            ("MedicinalLeaf30", "nnytj2v3n5", 1, "Medicinal Leaf Dataset. Mendeley Data 2020"),
            ("IndianMedicinalLeaves", "748f8jkphb", 3, "Pushpa BR, Rani NS. Indian Medicinal Leaves Image Datasets. Mendeley Data 2023")]
# local/common class labels of the 'Indian Medicinal Leaves' dataset -> binomial (curated; unclear labels left out)
COMMON = {
    "aloevera": "Aloe vera", "amla": "Phyllanthus emblica", "amruthaballi": "Tinospora cordifolia", "amruta_balli": "Tinospora cordifolia",
    "arali": "Nerium oleander", "ashoka": "Saraca asoca", "seethaashoka": "Saraca asoca", "ashwagandha": "Withania somnifera",
    "astma_weed": "Euphorbia hirta", "avacado": "Persea americana", "balloon_vine": "Cardiospermum halicacabum",
    "basale": "Basella alba", "malabar_spinach": "Basella alba", "betel": "Piper betle", "betel_nut": "Areca catechu",
    "bhrami": "Bacopa monnieri", "brahmi": "Bacopa monnieri", "bringaraja": "Eclipta prostrata", "castor": "Ricinus communis",
    "catharanthus": "Catharanthus roseus", "nithyapushpa": "Catharanthus roseus", "chilly": "Capsicum annuum",
    "citron lime (herelikai)": "Citrus medica", "coffee": "Coffea arabica", "common rue(naagdalli)": "Ruta graveolens",
    "nagadali": "Ruta graveolens", "coriender": "Coriandrum sativum", "curry": "Murraya koenigii", "curry_leaf": "Murraya koenigii",
    "doddapatre": "Plectranthus amboinicus", "doddpathre": "Plectranthus amboinicus", "drumstick": "Moringa oleifera",
    "ekka": "Calotropis gigantea", "eucalyptus": "Eucalyptus globulus", "ganike": "Solanum nigrum", "gasagase": "Muntingia calabura",
    "gauva": "Psidium guajava", "guava": "Psidium guajava", "geranium": "Pelargonium graveolens", "ginger": "Zingiber officinale",
    "globe amarnath": "Gomphrena globosa", "henna": "Lawsonia inermis", "hibiscus": "Hibiscus rosa-sinensis",
    "honge": "Pongamia pinnata", "insulin": "Chamaecostus cuspidatus", "jackfruit": "Artocarpus heterophyllus",
    "lantana": "Lantana camara", "lemon": "Citrus limon", "lemon_grass": "Cymbopogon citratus", "lemongrass": "Cymbopogon citratus",
    "malabar_nut": "Justicia adhatoda", "mango": "Mangifera indica", "marigold": "Tagetes erecta", "neem": "Azadirachta indica",
    "nelavembu": "Andrographis paniculata", "nerale": "Syzygium cumini", "nooni": "Morinda citrifolia", "onion": "Allium cepa",
    "padri": "Stereospermum chelonoides", "palak(spinach)": "Spinacia oleracea", "spinach1": "Spinacia oleracea",
    "papaya": "Carica papaya", "pappaya": "Carica papaya", "parijatha": "Nyctanthes arbor-tristis", "pepper": "Piper nigrum",
    "pomegranate": "Punica granatum", "pomoegranate": "Punica granatum", "raddish": "Raphanus sativus",
    "sampige": "Magnolia champaca", "sapota": "Manilkara zapota", "seethapala": "Annona squamosa", "tamarind": "Tamarindus indica",
    "taro": "Colocasia esculenta", "tecoma": "Tecoma stans", "thumbe": "Leucas aspera", "tulasi": "Ocimum tenuiflorum",
    "tulsi": "Ocimum tenuiflorum", "turmeric": "Curcuma longa", "wood_sorel": "Oxalis corniculata",
    "camphor": "Cinnamomum camphora", "kamakasturi": "Ocimum basilicum", "kepala": "Ixora coccinea"}

def folders(did, ver):
    f = RAW / f"mendeley_folders_{did}_v{ver}.json"
    if not f.exists():
        r = requests.get(f"https://data.mendeley.com/public-api/datasets/{did}/folders/{ver}", headers=UA, timeout=60)
        r.raise_for_status()
        f.write_bytes(r.content)
    return [x["name"].strip() for x in json.loads(f.read_text())]

def binomial(label):
    m = re.match(r"^\s*([A-Z][a-z]+)\s+([a-z][a-z\-]+)", label.strip().replace("Rosa-sinensis", "rosa-sinensis"), re.I)
    if not m or m.group(2).lower() in ("var", "sp", "spp"):
        return ""
    return f"{m.group(1).capitalize()} {m.group(2).lower()}"

GB_F = CACHE / "gbif_match_images.json"
GB = json.loads(GB_F.read_text()) if GB_F.exists() else {}

def gbif_key(name):
    if name not in GB:
        try:
            r = requests.get("https://api.gbif.org/v1/species/match", params={"name": name, "kingdom": "Plantae"},
                             headers=UA, timeout=30).json()
            GB[name] = r.get("acceptedUsageKey") or r.get("usageKey") if r.get("matchType") in ("EXACT", "FUZZY") else None
        except Exception:
            return None
        time.sleep(0.1)
    return GB[name]

def main():
    H = pd.read_csv(P / "herbs.csv", keep_default_na=False, low_memory=False)
    HN = pd.read_csv(P / "herb_names.csv", keep_default_na=False)
    key2herb = {str(k).split(".")[0]: h for h, k in zip(H.herb_id, H.gbif_key) if k != ""}
    bin2herb = {}
    for h, n in list(zip(H.herb_id, H.accepted_name)) + list(zip(HN.herb_id, HN.name)):
        b = binomial(n)
        if b:
            bin2herb.setdefault(b, h)
    rows = []
    for short, did, ver, cite in DATASETS:
        labels = sorted(set(folders(did, ver)))
        for lab in labels:
            low = lab.lower()
            if any(w in low for w in ("dataset", "segmented", "raw leaf", "med 117", "leaf species")):
                continue
            b, how = binomial(lab), "binomial_in_label"
            if short == "IndianMedicinalLeaves":
                b, how = COMMON.get(low, ""), "curated_common_name"
            if not b:
                continue
            k = gbif_key(b)
            h, method = (key2herb.get(str(k)), "gbif_accepted_key") if k else (None, "")
            if not h and b in bin2herb:
                h, method = bin2herb[b], "exact_binomial"
            rows.append(dict(dataset=short, dataset_doi=f"10.17632/{did}.{ver}", class_label=lab, species=b,
                             label_mapping=how, gbif_key=k or "", herb_id=h or "", match_method=method if h else "not_in_kb",
                             licence="CC BY 4.0", citation=cite, source_id="S12"))
    GB_F.write_text(json.dumps(GB))
    df = pd.DataFrame(rows).drop_duplicates(["dataset", "species", "herb_id"])
    df.to_csv(P / "herb_image_datasets.csv", index=False)
    inkb = df[df.herb_id != ""]
    print(f"image-dataset species: {df.species.nunique()} ; linked to KB herbs: {inkb.herb_id.nunique()} "
          f"({len(inkb)} dataset-species links)")
    print(inkb.groupby("dataset").herb_id.nunique().to_dict())

if __name__ == "__main__":
    main()
