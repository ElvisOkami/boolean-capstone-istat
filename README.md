# Analisi degli incidenti stradali in Italia

Progetto finale del corso Data Analyst.

L’obiettivo di questo progetto è analizzare gli incidenti stradali nei comuni italiani usando dati ISTAT e dati territoriali/demografici SITUAS. Il lavoro parte da dati grezzi, li pulisce, li unisce e li trasforma in un dataset finale usato poi per creare una dashboard in Power BI.

Il periodo analizzato è **2015-2023**.

## Obiettivo del progetto

L’idea del progetto è capire quali comuni italiani presentano i valori più alti di incidenti stradali, sia in termini assoluti sia rapportati alla popolazione.

In particolare, l’analisi prova a rispondere a queste domande:

- quali comuni hanno avuto più incidenti nel periodo 2015-2023;
- quali comuni hanno il tasso più alto di incidenti ogni 100.000 abitanti;
- quali province risultano più rilevanti nell’analisi territoriale;
- se ci sono differenze statistiche tra gruppi di comuni o aree geografiche;
- come visualizzare i risultati in modo chiaro tramite Power BI.

## Fonti dati

I dati usati nel progetto arrivano da due fonti principali.

| Fonte | Uso nel progetto |
|---|---|
| ISTAT | Dati sugli incidenti stradali per area territoriale |
| SITUAS ISTAT | Informazioni sui comuni, popolazione e dati territoriali |

Il dataset ISTAT viene scaricato automaticamente nello script Python tramite endpoint API. Il file SITUAS viene invece caricato da CSV nella cartella `data/`.

Link principali:

- ISTAT traffic accidents endpoint: https://esploradati.istat.it/SDMXWS/rest/data/41_983
- SITUAS ISTAT: https://situas.istat.it/web/#/territorio/body?id=74&dateFrom=2020-12-31

## Struttura del progetto

La struttura consigliata del repository è questa:

```text
.
├── data/
│   ├── situas_comuni.csv
│   ├── istat_raw.csv
│   ├── traffic_analysis_final.csv
│   └── traffic_analysis_powerbi.csv
├── output/
│   └── statistical_tests_summary.csv
├── visualizations/
│   └── 01_eda_overview.png
├── traffic_analysis_pipeline.py
├── ISTAT_Traffic_Analysis.pptx
├── dashboard_powerbi.pbix
└── README.md
```

Il nome del file Power BI può essere diverso, ma nel repository deve essere presente il file `.pbix` finale della dashboard.

## Processo seguito

Il lavoro è stato diviso in più passaggi. Prima ho recuperato i dati ISTAT tramite API e ho caricato il file SITUAS con le informazioni dei comuni. Dopo il caricamento, ho pulito i dati principali convertendo le colonne numeriche, filtrando il periodo 2015-2023 e gestendo i valori mancanti.

Successivamente ho aggregato gli incidenti per comune e ho unito il risultato con i dati demografici. In questo modo ho potuto calcolare nuove metriche, tra cui il numero totale di incidenti, la media annua, il tasso di incidenti ogni 100.000 abitanti e gli incidenti per km².

Lo script produce anche un dataset finale da usare per Power BI e alcuni output utili per controllare l’analisi.

## Analisi svolte nello script Python

Lo script principale è `traffic_analysis_pipeline.py`.

Le parti principali dello script sono:

| Parte | Descrizione |
|---|---|
| Data fetching | Scarica i dati ISTAT tramite API |
| Data loading | Carica il CSV SITUAS dalla cartella `data/` |
| Data cleaning | Pulisce e filtra i dati sul periodo 2015-2023 |
| Feature engineering | Crea nuove colonne utili per l’analisi |
| EDA | Stampa statistiche principali e salva grafici esplorativi |
| Outlier check | Controlla gli outlier usando il metodo IQR |
| Test statistici | Esegue Welch t-test e ANOVA |
| Export finale | Salva i dataset finali per analisi e Power BI |

## Metriche principali

Le metriche principali create nel progetto sono:

| Metrica | Significato |
|---|---|
| `TOTAL_ACCIDENTS` | Numero totale di incidenti nel periodo 2015-2023 |
| `AVG_ACCIDENTS_PER_YEAR` | Media annua degli incidenti |
| `ACCIDENTS_PER_100K_INHABITANTS` | Incidenti totali ogni 100.000 abitanti |
| `AVG_ACCIDENTS_PER_YEAR_PER_100K` | Incidenti medi annui ogni 100.000 abitanti |
| `ACCIDENTS_PER_KM2` | Incidenti per km² |

Per la dashboard Power BI sono stati usati anche nomi più leggibili, in modo da rendere le visualizzazioni più chiare.

## Analisi statistica

Per soddisfare la parte di analisi statistica richiesta dal progetto, nello script sono stati inseriti alcuni test:

- Welch t-test tra comuni sopra e sotto la popolazione mediana;
- Welch t-test tra comuni del Nord e comuni del Sud;
- ANOVA sulle regioni più popolose.

I risultati vengono salvati nel file:

```text
output/statistical_tests_summary.csv
```

Questi test sono stati usati come supporto all’analisi, non come conclusione definitiva. L’obiettivo era verificare se esistono differenze statisticamente rilevanti tra alcuni gruppi di comuni.

## Dashboard Power BI

La dashboard Power BI è composta da tre pagine:

| Pagina | Contenuto |
|---|---|
| Panoramica | KPI nazionali e top comuni per incidenti totali e tasso ogni 100.000 abitanti |
| Analisi territoriale | Confronto tra province e tabella comunale |
| Focus comunale | Analisi più dettagliata dei comuni con filtri per provincia e comune |

La dashboard permette di esplorare i dati tramite filtri e confrontare comuni e province in modo più immediato rispetto al solo file CSV.

## Presentazione

Il progetto include anche una presentazione PowerPoint di massimo 5 slide, come richiesto dalla consegna.

Il file è:

```text
ISTAT_Traffic_Analysis.pptx
```

La presentazione riassume il problema, il processo seguito, gli strumenti usati e i risultati principali.

## Forecast

Il forecast è stato considerato come possibile estensione futura del progetto, ma non è stato implementato nella versione finale. L’analisi si concentra sui dati consolidati disponibili per il periodo 2015-2023.

Questa scelta è stata fatta per mantenere il progetto più solido sui dati effettivamente disponibili e già puliti. In una versione successiva si potrebbe aggiungere una previsione semplice, ad esempio usando una regressione sui valori annuali o un modello di serie storica.

## Come eseguire lo script

Per eseguire lo script, dalla cartella principale del progetto:

```bash
python traffic_analysis_pipeline.py
```

Prima dell’esecuzione, il file `situas_comuni.csv` deve essere presente nella cartella `data/`.

Le librerie principali usate sono:

```text
pandas
numpy
requests
matplotlib
scipy
```

## Output prodotti

Dopo l’esecuzione dello script vengono prodotti diversi file:

| File | Descrizione |
|---|---|
| `data/istat_raw.csv` | Dati ISTAT scaricati tramite API |
| `data/traffic_analysis_final.csv` | Dataset finale completo |
| `data/traffic_analysis_powerbi.csv` | Dataset preparato per Power BI |
| `visualizations/01_eda_overview.png` | Grafico esplorativo riassuntivo |
| `output/statistical_tests_summary.csv` | Risultati dei test statistici |

## Strumenti usati

Per il progetto ho usato:

- Python;
- pandas e numpy per la preparazione dei dati;
- requests per scaricare i dati da API;
- matplotlib per i grafici esplorativi;
- scipy per i test statistici;
- Power BI per la dashboard finale;
- Git/GitHub per versionare e consegnare il progetto.

## Conclusioni

Il progetto mostra un flusso completo di lavoro data analytics: recupero dati, pulizia, unione di fonti diverse, creazione di nuove metriche, analisi esplorativa, test statistici e visualizzazione finale in Power BI.

La dashboard finale permette di vedere sia i comuni con più incidenti totali, sia quelli con i tassi più alti rispetto alla popolazione. Questo aiuta a leggere il fenomeno da due punti di vista diversi: il volume assoluto degli incidenti e il rischio relativo rispetto alla dimensione del comune.

Una possibile evoluzione del progetto sarebbe aggiungere un modulo di forecast e aggiornare automaticamente il dataset quando ISTAT pubblica nuovi dati.
