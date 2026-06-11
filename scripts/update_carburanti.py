import json
import os
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

OUTPUT_DIR = "data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

URL_ANAGRAFICA = "https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv"
URL_PREZZO = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"

def create_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; ConsumoViaggi/1.0)"
    })
    return session

print(f"[{datetime.now()}] Downloading MIMIT data...")
session = create_session()

try:
    resp_ana = session.get(URL_ANAGRAFICA, timeout=120)
    resp_ana.raise_for_status()
    ana_content = resp_ana.text
    print(f"  Anagrafica OK: {len(ana_content)} bytes")
except Exception as e:
    print(f"  Anagrafica failed: {e}")
    ana_content = None

try:
    resp_prezzo = session.get(URL_PREZZO, timeout=120)
    resp_prezzo.raise_for_status()
    prezzo_content = resp_prezzo.text
    print(f"  Prezzo OK: {len(prezzo_content)} bytes")
except Exception as e:
    print(f"  Prezzo failed: {e}")
    prezzo_content = None

if ana_content and prezzo_content:
    try:
        import pandas as pd
        from io import StringIO

        print(f"[{datetime.now()}] Parsing...")
        df_a = pd.read_csv(StringIO(ana_content), sep="|", dtype=str, encoding="utf-8", skiprows=1, on_bad_lines='skip')
        df_p = pd.read_csv(StringIO(prezzo_content), sep="|", dtype=str, encoding="utf-8", skiprows=1, on_bad_lines='skip')
        print(f"  Anagrafica: {len(df_a)} rows")
        print(f"  Prezzo: {len(df_p)} rows")

        df_a.columns = [c.strip() for c in df_a.columns]
        df_p.columns = [c.strip() for c in df_p.columns]
        print(f"  Anagrafica cols: {list(df_a.columns[:10])}")
        print(f"  Prezzo cols: {list(df_p.columns[:10])}")

        # Find the common key column (might be idImpianto or something else)
        common_cols = set(df_a.columns) & set(df_p.columns)
        key_col = None
        for candidate in ["idImpianto", "id_impianto", "ID_IMPIANTO", "CodImpianto"]:
            if candidate in common_cols:
                key_col = candidate
                break
        if not key_col and common_cols:
            # Try to find a column that looks like an ID
            for c in common_cols:
                if "id" in c.lower() or "impianto" in c.lower():
                    key_col = c
                    break
        
        if not key_col:
            raise Exception(f"No common key found. Anagrafica: {list(df_a.columns)}, Prezzo: {list(df_p.columns)}")
        
        print(f"  Using key: {key_col}")
        merged = pd.merge(df_p, df_a, on=key_col, how="inner", suffixes=("_p", "_a"))
        print(f"  Merged: {len(merged)} rows")

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

        print(f"  Cleaned: {len(df)} rows")

        records = []
        for _, r in df.iterrows():
            records.append({
                "id": str(r.get(key_col,"")),
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
        print(f"[{datetime.now()}] Success: {len(records)} records written")

    except Exception as e:
        print(f"Parse error: {e}, using placeholder")
        raise
else:
    print("Download failed, generating placeholder")
    records = [{
        "id": "0", "gestore": "Placeholder", "bandiera": "Test",
        "nome": "Stazione Test - Download MIMIT fallito",
        "comune": "Milano", "provincia": "MI",
        "lat": 45.4642, "lon": 9.1900,
        "carburante": "Benzina", "prezzo": 1.750,
        "self": True, "data": datetime.now().strftime("%Y-%m-%d")
    }]
    with open(os.path.join(OUTPUT_DIR, "prezzi_italia.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)

with open(os.path.join(OUTPUT_DIR, "last_update.json"), "w") as f:
    json.dump({"last_update": datetime.now().isoformat()}, f)
print(f"[{datetime.now()}] Done.")
