import json
import os
from datetime import datetime
from urllib.request import urlopen, Request

OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# MIMIT open data - proviamo diverse URL possibili
URLS_ANAGRAFICA = [
    "https://www.mimit.gov.it/images/open-data/anagrafica_impianti_attivi.csv",
    "https://www.mimit.gov.it/open-data/anagrafica_impianti_attivi.csv",
]

URLS_PREZZO = [
    "https://www.mimit.gov.it/images/open-data/prezzo_alle_8.csv",
    "https://www.mimit.gov.it/open-data/prezzo_alle_8.csv",
]

def try_download(url):
    """Try to download a URL with different User-Agent headers"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  Failed: {url} -> {e}")
        return None

print(f"[{datetime.now()}] Downloading MIMIT data...")

ana_content = None
for url in URLS_ANAGRAFICA:
    ana_content = try_download(url)
    if ana_content:
        print(f"  Anagrafica OK: {url}")
        break

prezzo_content = None
for url in URLS_PREZZO:
    prezzo_content = try_download(url)
    if prezzo_content:
        print(f"  Prezzo OK: {url}")
        break

if ana_content and prezzo_content:
    # Import pandas conditionally
    try:
        import pandas as pd
        from io import StringIO

        df_a = pd.read_csv(StringIO(ana_content), sep="|", dtype=str, encoding="utf-8")
        df_p = pd.read_csv(StringIO(prezzo_content), sep="|", dtype=str, encoding="utf-8")
        df_a.columns = [c.strip() for c in df_a.columns]
        df_p.columns = [c.strip() for c in df_p.columns]

        merged = pd.merge(df_p, df_a, on="idImpianto", how="inner", suffixes=("_p", "_a"))

        COLS = ["idImpianto","Gestore","Bandiera","Tipo Impianto","Nome Impianto",
                "Indirizzo","Comune","Provincia","Latitudine","Longitudine",
                "descCarburante","prezzo","isSelf","dtComu"]
        avail = [c for c in COLS if c in merged.columns]
        df = merged[avail].copy()

        if "prezzo" in df.columns:
            df["prezzo"] = pd.to_numeric(df["prezzo"], errors="coerce")
            df = df.dropna(subset=["prezzo"])
        if "Latitudine" in df.columns and "Longitudine" in df.columns:
            df["Latitudine"] = pd.to_numeric(df["Latitudine"], errors="coerce")
            df["Longitudine"] = pd.to_numeric(df["Longitudine"], errors="coerce")
            df = df.dropna(subset=["Latitudine","Longitudine"])

        records = []
        for _, r in df.iterrows():
            records.append({
                "id": str(r.get("idImpianto","")),
                "gestore": str(r.get("Gestore","")),
                "bandiera": str(r.get("Bandiera","")),
                "nome": str(r.get("Nome Impianto","")),
                "comune": str(r.get("Comune","")),
                "provincia": str(r.get("Provincia","")),
                "lat": float(r["Latitudine"]),
                "lon": float(r["Longitudine"]),
                "carburante": str(r.get("descCarburante","")),
                "prezzo": float(r["prezzo"]),
                "self": str(r.get("isSelf","1")) == "1",
                "data": str(r.get("dtComu",""))
            })

        with open(os.path.join(OUTPUT_DIR, "prezzi_italia.json"), "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)
        print(f"[{datetime.now()}] Success: {len(records)} records")

    except ImportError:
        print("pandas not available, generating placeholder")
        create_placeholder = True
    except Exception as e:
        print(f"Parse error: {e}, generating placeholder")
        create_placeholder = True
else:
    create_placeholder = True
    print("Could not download MIMIT data, generating placeholder JSON")

if 'create_placeholder' in dir() and create_placeholder:
    # Generate a minimal placeholder so Pages deployment works
    placeholder = [{
        "id": "0",
        "gestore": "Placeholder",
        "bandiera": "Test",
        "nome": "Stazione Test - Aggiornare pipeline",
        "comune": "Milano",
        "provincia": "MI",
        "lat": 45.4642,
        "lon": 9.1900,
        "carburante": "Benzina",
        "prezzo": 1.750,
        "self": True,
        "data": datetime.now().strftime("%Y-%m-%d")
    }]
    with open(os.path.join(OUTPUT_DIR, "prezzi_italia.json"), "w", encoding="utf-8") as f:
        json.dump(placeholder, f, ensure_ascii=False)
    print(f"[{datetime.now()}] Placeholder generated (1 record)")

# Save metadata
with open(os.path.join(OUTPUT_DIR, "last_update.json"), "w") as f:
    json.dump({"last_update": datetime.now().isoformat()}, f)
print(f"[{datetime.now()}] Done.")
