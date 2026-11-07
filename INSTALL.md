# Intel-Optimized-MoE - Guida all'Installazione

> **⚠️ AVVERTENZA: Questo e' un progetto SPERIMENTALE (work in progress)**
> 
> Non e' adatto per uso in produzione. Le performance possono variare notevolmente tra sistemi diversi. Leggi README.md per dettagli e limitazioni.

## Requisiti di Sistema

- **Windows 10/11 a 64-bit**
- **Python 3.14+** (testato con Python 3.14.7)
- **Hardware Intel** con supporto OpenVINO (CPU Intel moderna, GPU integrata Intel Arc)
- **Driver Intel aggiornati** (per l'uso della GPU integrata)
- **Visual Studio Build Tools** (per la compilazione dei kernel nativi)
- **Almeno 16 GB di RAM** (24+ GB consigliati per modelli grandi)

## Installazione Rapida

### Passo 1: Esegui l'installer

```powershell
# Apri PowerShell nella directory del progetto e esegui:
.\install.ps1
```

L'installer:
- Verifica i requisiti di sistema
- Crea un ambiente virtuale Python
- Installa tutte le dipendenze necessarie
- Compila i kernel nativi (richiede Visual Studio Build Tools)
- Crea file batch per l'esecuzione semplice

### Passo 2: Configura il modello

Il progetto **non include** il modello. Devi ottenere un file modello in formato **GGUF** compatibile.

Il modello testato e' **Hermes 3.6 35B A3B** (basato su Qwen3.6-MoE).

#### Opzione A: Posiziona il file nella directory
```
Copia il file .gguf nella directory del progetto:
  Hermes3.6-35B-A3B-Uncensored-Genesis-Final-APEX-Compact.gguf
```

#### Opzione B: Imposta variabile ambiente
```powershell
# In PowerShell, prima di avviare il chat:
$env:FLASH_MOE_GGUF = "D:\percorso\al\tuo\modello.gguf"
```

### Passo 3: Avvia il chat

```powershell
# Doppio click su:
run_chat.bat

# Oppure da PowerShell:
.\run_chat.bat
```

## Installazione Manuale

Se preferisci non usare l'installer automatico:

### 1. Installa dipendenze Python

```powershell
py -3.14 -m pip install -r requirements.txt
```

I pacchetti richiesti:
- numpy>=1.24.0
- openvino>=2024.0.0
- gguf>=0.6.0
- tokenizers>=0.15.0

### 2. Compila kernel nativi

Installa **Visual Studio Build Tools** con:
- C++ build tools
- MSVC v143 - VS 2022 C++ x64/x86 build tools

Poi esegui:

```powershell
# Compila kernel per dequantizzazione
.\scripts\compile_dequant_k.bat

# Compila kernel nativo per esperti
.\scripts\compile_native_expert.bat
```

### 3. Imposta variabili ambiente (opzionale)

Per prestazioni ottimali, imposta queste variabili:

```powershell
$env:OPENBLAS_NUM_THREADS = 1
$env:MKL_NUM_THREADS = 1
$env:BLIS_NUM_THREADS = 1
```

Questo e' particolarmente importante per il modulo attention.

## Opzioni del Chat Client

### Avvio base
```powershell
py -3.14 chat.py default
```

### Opzioni comuni

| Opzione | Descrizione | Default |
|---------|-------------|---------|
| `--max-tokens N` | Numero massimo di token generati | 128 |
| `--max-seq N` | Dimensione massima del contesto | 128 |
| `--temp F` | Temperatura per sampling | 0 |
| `--cache N` | Dimensione cache esperti quantizzati | 320 |
| `--weight-cache N` | Dimensione cache pesi convertiti | 1 |
| `--device DEV` | Dispositivo OpenVINO (CPU, GPU, NPU) | CPU |
| `--native-decode MODE` | Modalita' decode nativo (auto, native, openvino) | auto |
| `--expert-workers N` | Numero di worker per esperti | 4 |
| `--prefill-threads N` | Thread per prefill | 4 |

### Esempi

```powershell
# Generazione piu' lunga
py -3.14 chat.py default --max-tokens 512 --max-seq 2048

# Con temperatura
py -3.14 chat.py default --temp 0.7

# Usa solo CPU (nessuna GPU)
py -3.14 chat.py default --device CPU --ssm-device CPU --attention-device CPU

# Modalita' nativa esplicita
py -3.14 chat.py default --native-decode native
```

## Risoluzione Problemi

### Errore: Python 3.14 non trovato

Installa Python 3.14 da: https://www.python.org/downloads/

Assicurati che `py -3.14` punti alla versione corretta. Se usi Python Launchers, dovrebbe funzionare automaticamente.

### Errore: Visual Studio Build Tools non trovato

Installa da: https://visualstudio.microsoft.com/visual-cpp-build-tools/

Seleziona:
- "C++ build tools"
- "MSVC v143 - VS 2022 C++ x64/x86 build tools"

### Errore: OpenVINO non installato

L'installazione di OpenVINO tramite pip dovrebbe funzionare automaticamente. Se fallisce:

```powershell
py -3.14 -m pip install openvino>=2024.0.0
```

### Errore: Modello non trovato

Assicurati che:
1. Il file GGUF sia nella directory del progetto, OR
2. Abbia impostato la variabile ambiente `FLASH_MOE_GGUF`

### Prestazioni lente

Prova:
- Collega l'alimentatore (AC adapter) - migliore performance
- Assicurati che le variabili BLAS siano impostate a 1 thread
- Usa `--cache 320 --weight-cache 1` per i valori consigliati
- Usa `--expert-workers 4 --prefill-threads 4`

### Errore: Kernel nativo non trovato

Se vedi messaggi che il kernel nativo non e' disponibile, il chat usera' il fallback OpenVINO (piu' lento).

Per risolvere, assicurati di aver compilato i kernel:
```powershell
.\scripts\compile_native_expert.bat
```

E che il file `src\flash_moe\moe_quant_dot.dll` esista.

## Struttura del Progetto

```
.
├── chat.py                    # Chat client principale
├── requirements.txt           # Dipendenze Python
├── install.ps1               # Installer automatico
├── run_chat.bat              # Script per avvio rapido
├── README.md                 # Documentazione principale
├── LICENSE                   # Licenza Apache-2.0
├── scripts/                  # Script di compilazione
│   ├── compile_dequant_k.bat
│   └── compile_native_expert.bat
├── src/                      # Codice sorgente
│   └── flash_moe/            # Modulo principale
│       ├── backend_ov.py     # Backend OpenVINO
│       ├── native_expert.py  # Kernel nativo
│       └── ...
├── tools/                    # Strumenti di test/benchmark
└── cpp/                      # Codice C++ per kernel
```

## Comandi Chat

Dopo aver avviato il chat, puoi usare questi comandi:

| Comando | Descrizione |
|---------|-------------|
| `/exit` | Esci dal chat |
| `/help` | Mostra aiuto (se implementato) |

## Benchmark

Per eseguire un benchmark di stabilita':

```powershell
py -3.14 tools\bench_stability.py --prompt-file .\input.txt default --native-decode native --max-tokens 512 --max-seq 2048
```

Dove `input.txt` contiene il prompt di test.

## Disinstallazione

1. Elimina la directory del progetto
2. L'ambiente virtuale `.venv` puo' essere eliminato
3. I file generati (DLL) sono nella directory `build/` e `src/flash_moe/`

## Licenza

Il codice e' distribuito sotto licenza Apache-2.0. Vedi LICENSE per dettagli.

**Nota**: La licenza del codice e' separata dalla licenza del modello. Il modello GGUF e' separato e soggetto ai termini del suo autore.

## Supporto

Questo e' un progetto sperimentale. Non e' previsto supporto ufficiale.

Per problemi:
1. Controlla README.md per limitazioni note
2. Verifica di aver seguito correttamente la procedura di installazione
3. Leggi i messaggi di errore attentamente

## Performance Attese

Basato sui test sul sistema di riferimento (Intel Core Ultra 5 226V, Arc 130V, 16 GB RAM):

| Configurazione | Prefill (88 token) | Generazione (95 token) | Speed |
|---------------|---------------------|------------------------|-------|
| Prima richiesta (batteria) | 57.0 s | 101.7 s | 0.934 tok/s |
| Prima richiesta (AC) | 43.1 s | 82.8 s | 1.148 tok/s |
| Richiesta ripetuta (AC) | 22.8 s | 55.8 s | 1.702 tok/s |

**Nota**: Questi sono risultati manuali su un sistema specifico. Le performance possono variare notevolmente.

Con le ottimizzazioni piu' recenti (Q3_K, DeltaNet):
- Prefill: ~32 s per 100 token
- Generazione: ~1.8-2.0 tok/s (obbiettivo, non ancora stabilmente dimostrato)

## Note Finali

- Il progetto e' ancora in sviluppo attivo
- Nuove funzionalita' e ottimizzazioni vengono aggiunte regolarmente
- I risultati possono cambiare tra versioni
- Non tutte le funzionalita' sono state testate estensivamente

Grazie per provare Intel-Optimized-MoE!
