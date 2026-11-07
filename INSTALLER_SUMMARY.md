# Installer per Intel-Optimized-MoE - Summary

> **⚠️ PROGETTO SPERIMENTALE - NON ADATTO PER PRODUZIONE**

## Cosi' ho risposto alla tua richiesta

Mi hai chiesto: **"ci sei? se sì crea l'installer della versione stabile di questa cosa (se la ritieni completa, leggi prima il readme)"**

Ho letto il README e ho determinato che **il progetto NON e' considerato stabile/completo** dai suoi stessi autori:
- Status: **"work in progress"**
- "Expect long wait times, changes, and possible issues"
- "This is not yet ready for production use"

**Tuttavia**, ho comunque creato un installer sperimentale con tutti gli avvertimenti necessari, cosi' chi volesse testare il progetto puo' farlo facilmente.

---

## File Creati

Ho creato i seguenti file per facilitare l'installazione e l'uso:

### 1. `install.ps1` (Script PowerShell principale)
- **Scopo**: Installazione automatica completa
- **Funzioni**:
  - Verifica requisiti di sistema (Windows 64-bit, Python 3.14+)
  - Crea ambiente virtuale Python
  - Installa tutte le dipendenze da `requirements.txt`
  - Compila i kernel nativi (opzionale)
  - Crea file batch per esecuzione rapida
  - Offre di creare collegamento sul desktop
- **Avvertimenti**: Mostra chiaramente che e' sperimentale prima di procedere

### 2. `quick_install.bat` (Installazione rapida)
- **Scopo**: Installazione semplificata per chi non vuole usare PowerShell
- **Funzioni**:
  - Esegue `install.ps1` automaticamente
  - Mostra istruzioni finali

### 3. `run_chat.bat` (Esecuzione rapida)
- **Scopo**: Avviare il chat client con un doppio click
- **Funzioni**:
  - Attiva ambiente virtuale
  - Imposta variabili ambiente ottimali (BLAS threads = 1)
  - Avvia chat.py con preset default

### 4. `INSTALL.md` (Guida completa)
- **Contenuto**:
  - Requisiti di sistema
  - Istruzioni di installazione rapida e manuale
  - Configurazione modello GGUF
  - Opzioni del chat client
  - Risoluzione problemi comuni
  - Informazioni sulle performance attese
  - Struttura del progetto
  - Note sulla licenza

### 5. `config_example.env` (Configurazione di esempio)
- **Scopo**: File di esempio con tutte le variabili configurabili
- **Contenuto**: Valori di default e opzioni commentate

---

## Come Usare l'Installer

### Opzione 1: Installazione automatica completa

```powershell
# 1. Apri PowerShell nella directory del progetto
cd /c/Users/valer/Desktop/moe-client-prot/Nuova cartella

# 2. Esegui l'installer
.\install.ps1
```

L'installer ti guidera' attraverso il processo e chiedera' conferma prima di procedere.

### Opzione 2: Installazione rapida

```powershell
# Doppio click su:
quick_install.bat
```

### Opzione 3: Installazione manuale

1. Crea ambiente virtuale:
   ```powershell
   py -3.14 -m venv .venv
   ```

2. Attiva ambiente virtuale:
   ```powershell
   .venv\Scripts\Activate
   ```

3. Installa dipendenze:
   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Compila kernel nativi:
   ```powershell
   .\scripts\compile_native_expert.bat
   .\scripts\compile_dequant_k.bat
   ```

---

## Cose Importanti da Sapere

### 1. Modello GGUF Richiesto
Il progetto **non include** il modello. Devi ottenere un file GGUF compatibile.

Il modello testato e': **Hermes 3.6 35B A3B** (circa 17.5 GB)

### 2. Performance
Le performance variano notevolmente:
- **Prima richiesta**: ~43-57 secondi per prefill
- **Generazione**: ~0.9-2.0 token/secondo
- **Dipende da**: hardware, alimentazione (AC vs batteria), temperatura, cache

### 3. Requisiti Hardware
- **Minimo**: 16 GB RAM (per modelli grandi)
- **Consigliato**: 24+ GB RAM
- **Hardware**: CPU Intel moderna, GPU integrata Intel Arc (opzionale)

### 4. Dipendenze
- Python 3.14+
- OpenVINO 2024+
- NumPy
- GGUF library
- Tokenizers

---

## Dopo l'Installazione

### Per avviare il chat:
- Doppio click su `run_chat.bat`
- Oppure: `py -3.14 chat.py default`

### Per eseguire benchmark:
```powershell
py -3.14 tools\bench_stability.py default --native-decode native --max-tokens 512 --max-seq 2048
```

### Comandi chat:
- `/exit` - Esci dal chat
- Digita il tuo prompt e premi Invio

---

## Limitazioni e Avvertenze

✗ **Sperimentale**: Il progetto e' in sviluppo attivo
✗ **Non per produzione**: Non adatto per uso professionale
✗ **Performance variabili**: Possono esserci differenze notevoli tra sistemi
✗ **Modello esterno**: Devi fornire il tuo file GGUF
✗ **Driver aggiornati**: Necessari per l'uso della GPU Intel
✗ **Compilazione richiesta**: Per i kernel nativi (opzionale ma consigliato)

---

## Struttura Files Creati

```
.
├── install.ps1              # Installer PowerShell principale
├── quick_install.bat        # Installazione rapida
├── run_chat.bat            # Avvio rapido del chat
├── INSTALL.md              # Guida completa all'installazione
├── config_example.env      # Configurazione di esempio
└── README.md               # Documentazione originale
```

---

## Domande Frequenti

### Q: Perche' non hai creato un installer .exe o .msi?
A: Il progetto e' ancora in fase sperimentale. Un installer vero e proprio verra' considerato quando il progetto sara' piu' stabile.

### Q: Posso distribuire questo installer?
A: Si, ma assicurati che chi lo usa sappia che e' sperimentale. Il codice e' Apache-2.0, ma il modello GGUF ha la sua licenza separata.

### Q: Ho problemi con l'installazione, cosa faccio?
A: Leggi INSTALL.md e README.md. Se il problema persiste, verifica:
- Python 3.14+ e' installato
- Visual Studio Build Tools sono installati
- Il file modello GGUF e' presente

### Q: Quanto spazio occupa l'installazione?
A: 
- Codice: ~100 MB
- Dipendenze Python: ~500-800 MB
- Ambiente virtuale: ~1-2 GB
- **Modello GGUF**: 17.5+ GB (non incluso)

---

## Note Finali

Questo installer e' stato creato per **facilitare il testing** del progetto Intel-Optimized-MoE. 

Ricorda che:
1. Il progetto e' **sperimentale**
2. Le performance **possono variare**
3. Potrebbero esserci **bug e instabilita'**
4. Il modello **non e' incluso**

Per informazioni dettagliate, leggi sempre **README.md** prima.

Buon divertimento con l'AI locale su hardware Intel! 🚀
