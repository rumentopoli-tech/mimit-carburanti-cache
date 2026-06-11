import pandas as pd
import json
import os
from datetime import datetime
from urllib.request import urlretrieve
import glob

# --- CONFIG ---
# MIMIT open data URLs (aggiornare se cambiano)
URL_ANAGRAFICA = "https://www.mimit.gov.it/images/open-data/anagrafica_impianti_attivi.csv"
URL_PREZZO = "https://www.mimit.gov.it/images/open-data/prezzo_alle_8.csv"

OUTPUT_DIR = "data"
REGIONI = {
    "Abruzzo": "Abruzzo", "Basilicata": "Basilicata", "Calabria": "Calabria",
    "Campania": "Campania", "Emilia Romagna": "Emilia Romagna",
    "Friuli Venezia Giulia": "Friuli Venezia Giulia", "Lazio": "Lazio",
    "Liguria": "Liguria", "Lombardia": "Lombardia", "Marche": "Marche",
    "Molise": "Molise", "Piemonte": "Piemonte", "Puglia": "Puglia",
    "Sardegna": "Sardegna", "Sicilia": "Sicilia", "Toscana": "Toscana",
    "Trentino Alto Adige": "Trentino Alto Adige", "Umbria": "Umbria",
    "Valle d'Aosta": "Valle d'Aosta", "Veneto": "Veneto"
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 1. Download CSV ---
print(f"[{datetime.now()}] Downloading anagrafica...")
urlretrieve(URL_ANAGRAFICA, "anagrafica_impianti_attivi.csv")
print(f"[{datetime.now()}] Downloading prezzi...")
urlretrieve(URL_PREZZO, "prezzo_alle_8.csv")

# --- 2. Parse CSV ---
print(f"[{datetime.now()}] Parsing...")
# Il separatore dei CSV MIMIT è "|" (dal 10 febbraio 2026)
df_anagrafica = pd.read_csv("anagrafica_impianti_attivi.csv", sep="|", dtype=str, encoding="utf-8")
df_prezzo = pd.read_csv("prezzo_alle_8.csv", sep="|", dtype=str, encoding="utf-8")

# Normalizza i nomi delle colonne
df_anagrafica.columns = [c.strip() for c in df_anagrafica.columns]
df_prezzo.columns = [c.strip() for c in df_prezzo.columns]

# --- 3. Join ---
print(f"[{datetime.now()}] Joining datasets...")
merged = pd.merge(
    df_prezzo,
    df_anagrafica,
    on="idImpianto",
    how="inner",
    suffixes=("_prezzo", "_anag")
)

# --- 4. Filter & clean ---
COLS_TO_KEEP = [
    "idImpianto", "Gestore", "Bandiera", "Tipo Impianto",
    "Nome Impianto", "Indirizzo", "Comune", "Provincia",
    "Latitudine", "Longitudine", "descCarburante", "prezzo", "isSelf",
    "dtComu"
]

available_cols = [c for c in COLS_TO_KEEP if c in merged.columns]
print(f"Available columns: {available_cols}")

df = merged[available_cols].copy()

# Rimuovi prezzi non validi
if "prezzo" in df.columns:
    df["prezzo"] = pd.to_numeric(df["prezzo"], errors="coerce")
    df = df.dropna(subset=["prezzo"])

if "Latitudine" in df.columns and "Longitudine" in df.columns:
    df["Latitudine"] = pd.to_numeric(df["Latitudine"], errors="coerce")
    df["Longitudine"] = pd.to_numeric(df["Longitudine"], errors="coerce")
    df = df.dropna(subset=["Latitudine", "Longitudine"])

print(f"Total records after cleaning: {len(df)}")

# --- 5. Generate output files ---

# Full Italy JSON (lightweight: only essential fields)
print(f"[{datetime.now()}] Generating JSON...")
records = []
for _, row in df.iterrows():
    rec = {
        "id": str(row.get("idImpianto", "")),
        "gestore": str(row.get("Gestore", "")),
        "bandiera": str(row.get("Bandiera", "")),
        "nome": str(row.get("Nome Impianto", "")),
        "comune": str(row.get("Comune", "")),
        "provincia": str(row.get("Provincia", "")),
        "lat": float(row["Latitudine"]),
        "lon": float(row["Longitudine"]),
        "carburante": str(row.get("descCarburante", "")),
        "prezzo": float(row["prezzo"]),
        "self": str(row.get("isSelf", "1")) == "1",
        "data": str(row.get("dtComu", "")),
    }
    records.append(rec)

# Full file
with open(os.path.join(OUTPUT_DIR, "prezzi_italia.json"), "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False)

# Per regione
if "Regione" in df.columns:
    for regione_nome in REGIONI.values():
        regione_df = df[df["Regione"].str.lower() == regione_nome.lower()]
        if len(regione_df) > 0:
            reg_records = []
            for _, row in regione_df.iterrows():
                reg_records.append({
                    "id": str(row.get("idImpianto", "")),
                    "gestore": str(row.get("Gestore", "")),
                    "bandiera": str(row.get("Bandiera", "")),
                    "nome": str(row.get("Nome Impianto", "")),
                    "comune": str(row.get("Comune", "")),
                    "provincia": str(row.get("Provincia", "")),
                    "lat": float(row["Latitudine"]),
                    "lon": float(row["Longitudine"]),
                    "carburante": str(row.get("descCarburante", "")),
                    "prezzo": float(row["prezzo"]),
                    "self": str(row.get("isSelf", "1")) == "1",
                    "data": str(row.get("dtComu", "")),
                })
            safe_name = regione_nome.lower().replace(" ", "_").replace("'", "")
            with open(os.path.join(OUTPUT_DIR, f"prezzi_{safe_name}.json"), "w", encoding="utf-8") as f:
                json.dump(reg_records, f, ensure_ascii=False)

# Save last update timestamp
with open(os.path.join(OUTPUT_DIR, "last_update.json"), "w") as f:
    json.dump({"last_update": datetime.now().isoformat(), "record_count": len(records)}, f)

# Cleanup
for f in glob.glob("*.csv"):
    os.remove(f)

print(f"[{datetime.now()}] Done. {len(records)} records written.")
