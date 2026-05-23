"""
Forecast incidenti stradali 2024-2025

Questo script è separato dalla pipeline principale.
Serve solo per creare un tentativo di forecast, come richiesto dalla traccia del Capstone.

Input principale:
- data/istat_raw.csv, se già presente

Se il file non è presente, lo script prova a scaricare i dati ISTAT dallo stesso endpoint usato nella pipeline.

Output:
- output/accidents_forecast_2024_2025.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"

ISTAT_RAW_FILE = DATA_DIR / "istat_raw.csv"
FINAL_DATASET_FILE = DATA_DIR / "traffic_analysis_final.csv"
POWERBI_DATASET_FILE = DATA_DIR / "traffic_analysis_powerbi.csv"
FORECAST_RESULTS_FILE = OUTPUT_DIR / "accidents_forecast_2024_2025.csv"

ISTAT_URL = "https://esploradati.istat.it/SDMXWS/rest/data/41_983"
ISTAT_HEADERS = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}


def safe_divide(numerator, denominator, multiplier=1):
    """Evita divisioni per zero o valori mancanti."""
    denominator = denominator.replace(0, np.nan)
    return (numerator / denominator) * multiplier


def load_istat_data() -> pd.DataFrame:
    """Carica i dati ISTAT già presenti oppure li scarica se mancano."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if ISTAT_RAW_FILE.exists():
        print(f"Carico dati ISTAT da {ISTAT_RAW_FILE}")
        return pd.read_csv(ISTAT_RAW_FILE)

    print("File istat_raw.csv non trovato. Scarico i dati ISTAT dall'endpoint API...")
    response = requests.get(ISTAT_URL, headers=ISTAT_HEADERS, timeout=60)
    response.raise_for_status()

    ISTAT_RAW_FILE.write_bytes(response.content)
    print(f"Dati ISTAT salvati in {ISTAT_RAW_FILE}")
    return pd.read_csv(ISTAT_RAW_FILE)


def clean_annual_accidents(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara i dati annuali degli incidenti per comune."""
    required_columns = {"REF_AREA", "TIME_PERIOD", "OBS_VALUE"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"Colonne mancanti nel dataset ISTAT: {missing_columns}")

    clean_df = df[["REF_AREA", "TIME_PERIOD", "OBS_VALUE"]].copy()
    clean_df["TIME_PERIOD"] = pd.to_numeric(clean_df["TIME_PERIOD"], errors="coerce")
    clean_df["OBS_VALUE"] = pd.to_numeric(clean_df["OBS_VALUE"], errors="coerce")

    clean_df = clean_df.dropna(subset=["REF_AREA", "TIME_PERIOD", "OBS_VALUE"])
    clean_df = clean_df[(clean_df["TIME_PERIOD"] >= 2015) & (clean_df["TIME_PERIOD"] <= 2023)]

    annual_df = (
        clean_df.groupby(["REF_AREA", "TIME_PERIOD"], as_index=False)
        .agg(ACCIDENTS=("OBS_VALUE", "sum"))
        .sort_values(["REF_AREA", "TIME_PERIOD"])
    )

    return annual_df


def load_municipality_lookup() -> pd.DataFrame:
    """Carica nomi comuni e popolazione, se disponibili nei dataset finali."""
    lookup_file = None

    if FINAL_DATASET_FILE.exists():
        lookup_file = FINAL_DATASET_FILE
    elif POWERBI_DATASET_FILE.exists():
        lookup_file = POWERBI_DATASET_FILE

    if lookup_file is None:
        print("Dataset finale non trovato. Il forecast verrà salvato solo con il codice area ISTAT.")
        return pd.DataFrame()

    print(f"Carico dati comunali da {lookup_file}")
    df = pd.read_csv(lookup_file)

    area_col = None
    for col in ["AREA_CODE", "REF_AREA", "Codice Comune formato alfanumerico"]:
        if col in df.columns:
            area_col = col
            break

    comune_col = None
    for col in ["Comune", "COMUNE", "comune"]:
        if col in df.columns:
            comune_col = col
            break

    population_col = None
    for col in ["Popolazione legale", "POPOLAZIONE_USATA", "POPOLAZIONE", "Popolazione"]:
        if col in df.columns:
            population_col = col
            break

    selected_columns = []
    rename_map = {}

    if area_col:
        selected_columns.append(area_col)
        rename_map[area_col] = "REF_AREA"

    if comune_col:
        selected_columns.append(comune_col)
        rename_map[comune_col] = "Comune"

    if population_col:
        selected_columns.append(population_col)
        rename_map[population_col] = "POPULATION"

    if not area_col:
        print("Colonna codice area non trovata nel dataset finale. Salto l'arricchimento con i nomi dei comuni.")
        return pd.DataFrame()

    lookup = df[selected_columns].drop_duplicates().rename(columns=rename_map)
    lookup["REF_AREA"] = lookup["REF_AREA"].astype(str)

    return lookup


def create_forecast(annual_df: pd.DataFrame, lookup_df: pd.DataFrame) -> pd.DataFrame:
    """Crea forecast 2024-2025 con regressione lineare semplice per ogni comune."""
    forecast_years = [2024, 2025]
    results = []

    annual_df["REF_AREA"] = annual_df["REF_AREA"].astype(str)

    for area_code, group in annual_df.groupby("REF_AREA"):
        group = group.sort_values("TIME_PERIOD")

        if group["TIME_PERIOD"].nunique() < 3:
            continue

        years = group["TIME_PERIOD"].astype(float).values
        accidents = group["ACCIDENTS"].astype(float).values

        slope, intercept = np.polyfit(years, accidents, 1)

        for year in forecast_years:
            predicted_accidents = max(0, slope * year + intercept)
            results.append(
                {
                    "REF_AREA": area_code,
                    "FORECAST_YEAR": year,
                    "PREDICTED_ACCIDENTS": round(predicted_accidents, 2),
                    "MODEL": "Linear regression on annual municipal accidents",
                }
            )

    forecast_df = pd.DataFrame(results)

    if forecast_df.empty:
        raise ValueError("Forecast non creato: non ci sono abbastanza dati annuali.")

    if not lookup_df.empty:
        forecast_df = forecast_df.merge(lookup_df, on="REF_AREA", how="left")

        if "POPULATION" in forecast_df.columns:
            forecast_df["POPULATION"] = pd.to_numeric(forecast_df["POPULATION"], errors="coerce")
            forecast_df["PREDICTED_ACCIDENTS_PER_100K"] = safe_divide(
                forecast_df["PREDICTED_ACCIDENTS"], forecast_df["POPULATION"], 100000
            ).round(2)

    sort_columns = ["FORECAST_YEAR", "PREDICTED_ACCIDENTS"]
    ascending = [True, False]

    if "PREDICTED_ACCIDENTS_PER_100K" in forecast_df.columns:
        sort_columns = ["FORECAST_YEAR", "PREDICTED_ACCIDENTS_PER_100K"]

    forecast_df = forecast_df.sort_values(sort_columns, ascending=ascending)

    return forecast_df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    istat_df = load_istat_data()
    annual_df = clean_annual_accidents(istat_df)
    lookup_df = load_municipality_lookup()
    forecast_df = create_forecast(annual_df, lookup_df)

    forecast_df.to_csv(FORECAST_RESULTS_FILE, index=False)

    print("\nForecast creato correttamente.")
    print(f"File salvato in: {FORECAST_RESULTS_FILE}")
    print("\nPrime righe del forecast:")
    print(forecast_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
