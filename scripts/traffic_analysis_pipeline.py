"""
Analisi degli incidenti stradali nei comuni italiani 2015-2023.

"""

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import requests
import matplotlib.pyplot as plt

try:
    from scipy import stats
except ImportError as exc:
    raise ImportError("Per eseguire i test statistici serve scipy: pip install scipy") from exc


# Cartelle e file usati nel progetto
DATA_DIR = Path("data")
VIZ_DIR = Path("visualizations")
OUTPUT_DIR = Path("output")

SITUAS_FILE = DATA_DIR / "situas_comuni.csv"
ISTAT_RAW_FILE = DATA_DIR / "istat_raw.csv"
FINAL_DATASET_FILE = DATA_DIR / "traffic_analysis_final.csv"
POWERBI_DATASET_FILE = DATA_DIR / "traffic_analysis_powerbi.csv"
TEST_RESULTS_FILE = OUTPUT_DIR / "statistical_tests_summary.csv"

# Endpoint ISTAT usato per scaricare i dati sugli incidenti
ISTAT_URL = "https://esploradati.istat.it/SDMXWS/rest/data/41_983"
ISTAT_HEADERS = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}

# Periodo scelto per l'analisi
START_YEAR = 2015
END_YEAR = 2023

pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 140)
warnings.filterwarnings("ignore", category=RuntimeWarning)


def prepare_folders() -> None:
    """Creo le cartelle"""
    for folder in [DATA_DIR, VIZ_DIR, OUTPUT_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def safe_divide(numerator: pd.Series, denominator: pd.Series, multiplier: float = 1.0) -> pd.Series:
    """Divisione usata per evitare errori quando il denominatore è zero."""
    result = numerator / denominator.replace({0: np.nan}) * multiplier
    return result.replace([np.inf, -np.inf], np.nan)


def load_situas_data() -> pd.DataFrame:
    """Carico il file SITUAS con le informazioni dei comuni."""
    if not SITUAS_FILE.exists():
        raise FileNotFoundError(
            f"File non trovato: {SITUAS_FILE}. Il CSV SITUAS deve essere dentro la cartella data."
        )

    df_situas = pd.read_csv(SITUAS_FILE, encoding="latin-1", sep=";")
    print("Dataset SITUAS caricato")
    print(f"Righe: {df_situas.shape[0]:,} | Colonne: {df_situas.shape[1]:,}")
    return df_situas


def fetch_istat_data() -> pd.DataFrame:
    """Scarico il dataset ISTAT in formato CSV."""
    response = requests.get(ISTAT_URL, headers=ISTAT_HEADERS, timeout=120)
    response.raise_for_status()

    ISTAT_RAW_FILE.write_text(response.text, encoding="utf-8")
    df_istat = pd.read_csv(ISTAT_RAW_FILE)

    print("Dataset ISTAT scaricato")
    print(f"Righe: {df_istat.shape[0]:,} | Colonne: {df_istat.shape[1]:,}")
    return df_istat


def clean_istat_data(df_istat: pd.DataFrame) -> pd.DataFrame:
    """Pulisco i dati ISTAT e tengo solo gli anni scelti per l'analisi."""
    required_columns = {"REF_AREA", "OBS_VALUE", "TIME_PERIOD"}
    missing_columns = required_columns.difference(df_istat.columns)
    if missing_columns:
        raise ValueError(f"Colonne mancanti nel dataset ISTAT: {sorted(missing_columns)}")

    df = df_istat.copy()

    # Converto le colonne principali in numerico, così evito problemi nel merge e nei calcoli
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df["TIME_PERIOD"] = pd.to_numeric(df["TIME_PERIOD"], errors="coerce")
    df["REF_AREA"] = pd.to_numeric(df["REF_AREA"], errors="coerce")

    df = df.dropna(subset=["REF_AREA", "OBS_VALUE", "TIME_PERIOD"])
    df = df[(df["TIME_PERIOD"] >= START_YEAR) & (df["TIME_PERIOD"] <= END_YEAR)]

    print(f"Dati ISTAT filtrati sul periodo {START_YEAR}-{END_YEAR}")
    print(f"Righe dopo la pulizia: {df.shape[0]:,}")
    return df


def aggregate_accidents_by_municipality(df_istat: pd.DataFrame) -> pd.DataFrame:
    """Raggruppo gli incidenti per codice comune."""
    df_agg = (
        df_istat.groupby("REF_AREA", as_index=False)
        .agg(
            TOTAL_ACCIDENTS=("OBS_VALUE", "sum"),
            OBSERVATION_COUNT=("OBS_VALUE", "count"),
            FIRST_YEAR=("TIME_PERIOD", "min"),
            LAST_YEAR=("TIME_PERIOD", "max"),
            YEARS_AVAILABLE=("TIME_PERIOD", "nunique"),
        )
        .rename(columns={"REF_AREA": "AREA_CODE"})
    )

    df_agg["AREA_CODE"] = df_agg["AREA_CODE"].astype(int)

    # Oltre al totale, calcolo anche la media annua perché è più facile da leggere nella dashboard
    df_agg["AVG_ACCIDENTS_PER_YEAR"] = safe_divide(
        df_agg["TOTAL_ACCIDENTS"], df_agg["YEARS_AVAILABLE"]
    ).round(2)

    print("Incidenti aggregati per comune")
    print(f"Comuni presenti nei dati ISTAT: {df_agg.shape[0]:,}")
    return df_agg


def merge_and_create_features(df_situas: pd.DataFrame, df_istat_agg: pd.DataFrame) -> pd.DataFrame:
    """Unisco i dati dei comuni con quelli sugli incidenti e creo le metriche finali."""
    required_columns = {"Codice Comune (numerico)", "Popolazione legale", "Superficie (Kmq)", "Comune", "Codice Regione"}
    missing_columns = required_columns.difference(df_situas.columns)
    if missing_columns:
        raise ValueError(f"Colonne mancanti nel dataset SITUAS: {sorted(missing_columns)}")

    df = df_situas.copy()

    # Preparo il codice comune nello stesso formato dei dati ISTAT
    df["AREA_CODE"] = pd.to_numeric(df["Codice Comune (numerico)"], errors="coerce")
    df["Popolazione legale"] = pd.to_numeric(df["Popolazione legale"], errors="coerce")
    df["Superficie (Kmq)"] = pd.to_numeric(df["Superficie (Kmq)"], errors="coerce")
    df = df.dropna(subset=["AREA_CODE"])
    df["AREA_CODE"] = df["AREA_CODE"].astype(int)

    merged = df.merge(df_istat_agg, on="AREA_CODE", how="left")

    # Se un comune non ha incidenti nel dataset ISTAT, imposto i valori a zero
    accident_columns = ["TOTAL_ACCIDENTS", "OBSERVATION_COUNT", "YEARS_AVAILABLE", "AVG_ACCIDENTS_PER_YEAR"]
    for column in accident_columns:
        merged[column] = merged[column].fillna(0)

    merged["FIRST_YEAR"] = merged["FIRST_YEAR"].fillna(START_YEAR)
    merged["LAST_YEAR"] = merged["LAST_YEAR"].fillna(END_YEAR)
    merged["ANALYSIS_PERIOD"] = f"{START_YEAR}-{END_YEAR}"

    # Tasso cumulato: incidenti totali del periodo ogni 100.000 abitanti
    merged["ACCIDENTS_PER_100K_INHABITANTS"] = safe_divide(
        merged["TOTAL_ACCIDENTS"], merged["Popolazione legale"], 100000
    ).round(2)

    # Tasso medio annuo, utile per non leggere solo il totale cumulato
    merged["AVG_ACCIDENTS_PER_YEAR_PER_100K"] = safe_divide(
        merged["AVG_ACCIDENTS_PER_YEAR"], merged["Popolazione legale"], 100000
    ).round(2)

    # Incidenti per kmq, utile per confrontare comuni con superfici diverse
    merged["ACCIDENTS_PER_KM2"] = safe_divide(
        merged["TOTAL_ACCIDENTS"], merged["Superficie (Kmq)"]
    ).round(2)

    # Tengo anche questi nomi perché li avevo già usati nella prima versione della dashboard
    merged["ACCIDENTS_PER_CAPITA"] = merged["ACCIDENTS_PER_100K_INHABITANTS"]
    merged["ACCIDENTS_PER_KMQ"] = merged["ACCIDENTS_PER_KM2"]

    merged = merged.sort_values("ACCIDENTS_PER_100K_INHABITANTS", ascending=False)

    print("Dataset finale creato")
    print(f"Comuni totali: {merged.shape[0]:,}")
    print(f"Comuni con incidenti nel periodo: {(merged['TOTAL_ACCIDENTS'] > 0).sum():,}")
    return merged


def print_main_summaries(df: pd.DataFrame) -> None:
    """Stampo alcune statistiche principali per controllare il risultato finale."""
    df_with_accidents = df[df["TOTAL_ACCIDENTS"] > 0]

    print("\nStatistiche generali")
    print(f"Periodo analizzato: {START_YEAR}-{END_YEAR}")
    print(f"Incidenti totali nel periodo: {df['TOTAL_ACCIDENTS'].sum():,.0f}")
    print(f"Media incidenti per comune: {df['TOTAL_ACCIDENTS'].mean():.2f}")
    print(f"Mediana incidenti per comune: {df['TOTAL_ACCIDENTS'].median():.2f}")

    print("\nTop 10 comuni per incidenti ogni 100.000 abitanti")
    columns = ["Comune", "Popolazione legale", "TOTAL_ACCIDENTS", "ACCIDENTS_PER_100K_INHABITANTS"]
    print(df_with_accidents.nlargest(10, "ACCIDENTS_PER_100K_INHABITANTS")[columns].to_string(index=False))

    print("\nTop 10 comuni per incidenti medi annui ogni 100.000 abitanti")
    columns = ["Comune", "Popolazione legale", "AVG_ACCIDENTS_PER_YEAR", "AVG_ACCIDENTS_PER_YEAR_PER_100K"]
    print(df_with_accidents.nlargest(10, "AVG_ACCIDENTS_PER_YEAR_PER_100K")[columns].to_string(index=False))

    region_summary = (
        df.groupby("Codice Regione", as_index=False)
        .agg(TOTAL_ACCIDENTS=("TOTAL_ACCIDENTS", "sum"), POPULATION=("Popolazione legale", "sum"))
    )
    region_summary["ACCIDENTS_PER_100K_INHABITANTS"] = safe_divide(
        region_summary["TOTAL_ACCIDENTS"], region_summary["POPULATION"], 100000
    ).round(2)

    print("\nPrime regioni per incidenti cumulati ogni 100.000 abitanti")
    print(region_summary.sort_values("ACCIDENTS_PER_100K_INHABITANTS", ascending=False).head(10).to_string(index=False))


def detect_outliers(df: pd.DataFrame) -> pd.DataFrame:
    metric = df["ACCIDENTS_PER_100K_INHABITANTS"].dropna()
    q1 = metric.quantile(0.25)
    q3 = metric.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    outliers = df[
        (df["ACCIDENTS_PER_100K_INHABITANTS"] < lower_bound)
        | (df["ACCIDENTS_PER_100K_INHABITANTS"] > upper_bound)
    ].copy()

    print("\nControllo outlier")
    print(f"Limiti IQR: {lower_bound:.2f} - {upper_bound:.2f}")
    print(f"Outlier trovati: {outliers.shape[0]:,} ({outliers.shape[0] / df.shape[0] * 100:.2f}%)")
    return outliers


def create_visualizations(df: pd.DataFrame) -> None:
    """Creo un grafico riassuntivo per controllare distribuzioni e relazioni principali."""
    df_with_accidents = df[df["TOTAL_ACCIDENTS"] > 0]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    axes[0, 0].hist(df["TOTAL_ACCIDENTS"], bins=50, color="#356891", edgecolor="black")
    axes[0, 0].set_title(f"Incidenti totali per comune ({START_YEAR}-{END_YEAR})")
    axes[0, 0].set_xlabel("Incidenti totali")
    axes[0, 0].set_ylabel("Numero di comuni")
    axes[0, 0].grid(True, alpha=0.3)

    axes[0, 1].boxplot(df_with_accidents["ACCIDENTS_PER_100K_INHABITANTS"].dropna(), vert=True)
    axes[0, 1].set_title("Incidenti ogni 100.000 abitanti")
    axes[0, 1].set_ylabel("Tasso cumulato")
    axes[0, 1].grid(True, alpha=0.3)

    axes[1, 0].scatter(df["Popolazione legale"], df["TOTAL_ACCIDENTS"], alpha=0.45, s=18, color="#356891")
    axes[1, 0].set_title("Popolazione e incidenti totali")
    axes[1, 0].set_xlabel("Popolazione")
    axes[1, 0].set_ylabel("Incidenti totali")
    axes[1, 0].set_xscale("log")
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].hist(
        df_with_accidents["AVG_ACCIDENTS_PER_YEAR_PER_100K"].dropna(),
        bins=50,
        color="#C76E4B",
        edgecolor="black",
    )
    axes[1, 1].set_title("Incidenti medi annui ogni 100.000 abitanti")
    axes[1, 1].set_xlabel("Tasso medio annuo")
    axes[1, 1].set_ylabel("Numero di comuni")
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    chart_path = VIZ_DIR / "01_eda_overview.png"
    plt.savefig(chart_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"\nGrafico EDA salvato in {chart_path}")


def calculate_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Calcolo la matrice di correlazione tra le variabili numeriche principali."""
    selected_columns = [
        "Popolazione legale",
        "Superficie (Kmq)",
        "TOTAL_ACCIDENTS",
        "AVG_ACCIDENTS_PER_YEAR",
        "ACCIDENTS_PER_100K_INHABITANTS",
        "AVG_ACCIDENTS_PER_YEAR_PER_100K",
    ]
    correlations = df[selected_columns].corr().round(3)

    print("\nMatrice di correlazione")
    print(correlations)
    return correlations


def run_statistical_tests(df: pd.DataFrame) -> pd.DataFrame:
    """Eseguo alcuni test statistici semplici sui tassi di incidentalità."""
    results = []
    metric = "AVG_ACCIDENTS_PER_YEAR_PER_100K"

    # Test 1: confronto tra comuni sopra e sotto la popolazione mediana
    median_population = df["Popolazione legale"].median()
    large_municipalities = df[df["Popolazione legale"] > median_population][metric].dropna()
    small_municipalities = df[df["Popolazione legale"] <= median_population][metric].dropna()

    t_stat, p_value = stats.ttest_ind(large_municipalities, small_municipalities, equal_var=False, nan_policy="omit")
    results.append(
        {
            "test": "Welch t-test",
            "comparison": "Large vs small municipalities",
            "metric": metric,
            "group_1_mean": large_municipalities.mean(),
            "group_2_mean": small_municipalities.mean(),
            "statistic": t_stat,
            "p_value": p_value,
            "significant_at_0_05": p_value < 0.05,
        }
    )

    # Test 2: confronto semplice tra Nord e Sud usando i codici regione
    northern_regions = [1, 2, 3, 4, 5, 6]
    southern_regions = [14, 15, 16, 17, 18]
    north = df[df["Codice Regione"].isin(northern_regions)][metric].dropna()
    south = df[df["Codice Regione"].isin(southern_regions)][metric].dropna()

    t_stat, p_value = stats.ttest_ind(north, south, equal_var=False, nan_policy="omit")
    results.append(
        {
            "test": "Welch t-test",
            "comparison": "North vs South",
            "metric": metric,
            "group_1_mean": north.mean(),
            "group_2_mean": south.mean(),
            "statistic": t_stat,
            "p_value": p_value,
            "significant_at_0_05": p_value < 0.05,
        }
    )

    # Test 3: ANOVA sulle 5 regioni più popolose
    top_regions = df.groupby("Codice Regione")["Popolazione legale"].sum().nlargest(5).index.tolist()
    region_groups = [df[df["Codice Regione"] == region][metric].dropna().values for region in top_regions]
    region_groups = [group for group in region_groups if len(group) > 1]

    f_stat, p_value = stats.f_oneway(*region_groups)
    results.append(
        {
            "test": "One-way ANOVA",
            "comparison": "Top 5 regions by population",
            "metric": metric,
            "group_1_mean": np.nan,
            "group_2_mean": np.nan,
            "statistic": f_stat,
            "p_value": p_value,
            "significant_at_0_05": p_value < 0.05,
        }
    )

    results_df = pd.DataFrame(results)
    results_df.to_csv(TEST_RESULTS_FILE, index=False)

    print("\nRisultati dei test statistici")
    print(results_df.to_string(index=False))
    print(f"\nRiepilogo test salvato in {TEST_RESULTS_FILE}")
    return results_df


def save_final_outputs(df: pd.DataFrame) -> None:
    """Salvo il dataset completo e una versione più comoda per Power BI."""
    df.to_csv(FINAL_DATASET_FILE, index=False)

    powerbi_columns = [
        "ANALYSIS_PERIOD",
        "AREA_CODE",
        "Comune",
        "Codice Regione",
        "Popolazione legale",
        "Superficie (Kmq)",
        "TOTAL_ACCIDENTS",
        "AVG_ACCIDENTS_PER_YEAR",
        "ACCIDENTS_PER_100K_INHABITANTS",
        "AVG_ACCIDENTS_PER_YEAR_PER_100K",
        "ACCIDENTS_PER_KM2",
        "OBSERVATION_COUNT",
        "YEARS_AVAILABLE",
        "FIRST_YEAR",
        "LAST_YEAR",
    ]
    available_columns = [column for column in powerbi_columns if column in df.columns]
    df[available_columns].to_csv(POWERBI_DATASET_FILE, index=False)

    print(f"\nDataset finale salvato in {FINAL_DATASET_FILE}")
    print(f"Dataset per Power BI salvato in {POWERBI_DATASET_FILE}")


def main() -> None:
    prepare_folders()

    print("Analisi incidenti stradali")
    print(f"Periodo analizzato: {START_YEAR}-{END_YEAR}\n")

    df_situas = load_situas_data()
    df_istat_raw = fetch_istat_data()
    df_istat_clean = clean_istat_data(df_istat_raw)
    df_istat_agg = aggregate_accidents_by_municipality(df_istat_clean)
    df_final = merge_and_create_features(df_situas, df_istat_agg)

    save_final_outputs(df_final)
    print_main_summaries(df_final)
    detect_outliers(df_final)
    calculate_correlations(df_final)
    create_visualizations(df_final)
    run_statistical_tests(df_final)

    print("\nPipeline completata.")


if __name__ == "__main__":
    main()
