"""Small explicit UI catalogue; never translate user messages or model output."""
_language='it'


def set_language(language):
    global _language
    if language not in ('it','en'):raise ValueError('Unsupported language')
    _language=language


def language():return _language


def tr(source,**values):
    text=EN.get(source,source) if _language=='en' else source
    return text.format(**values) if values else text


EN={
'Lingua / Language':'Language',
'Lingua dell’interfaccia':'Interface language',
'La modalità inglese usa l’interfaccia e le nuove risposte in inglese. Le conversazioni salvate restano invariate.':'English mode uses English for the interface and new answers. Saved conversations keep their original text.',
'Nuova chat':'New chat','Nuova conversazione':'New conversation','LE TUE CHAT':'YOUR CHATS',
'Tutto sul tuo PC':'Everything on your PC','Impostazioni':'Settings','Il tuo spazio per pensare':'Your space to think',
'Scegli un modello GGUF nelle impostazioni':'Choose a GGUF model in Settings','Non caricato':'Not loaded',
'Allega testo o immagini locali':'Attach local text or images','Ricerca web':'Web search',
'Facoltativa e disattivata di default. Invia la domanda a DuckDuckGo e legge fino a tre pagine HTTPS pubbliche.':'Optional and off by default. Sends your query to DuckDuckGo and reads up to three public HTTPS pages.',
'Rimuovi immagini':'Remove images','Elaborazione locale':'Local processing','Interrompi':'Stop',
'Invia · Maiusc+Invio per andare a capo':'Send · Shift+Enter for a new line',
'Uno spazio tranquillo per le tue idee.\nScrivi una domanda per iniziare.':'A quiet space for your ideas.\nAsk a question to get started.',
'Elimina conversazione':'Delete conversation','Eliminare questa conversazione salvata?':'Delete this saved conversation?',
'Salvataggio non riuscito: ':'Could not save: ','Caricamento del modello':'Loading model',
'Pronto':'Ready','Interruzione':'Stopping',
'Anteprima grafica: avvia la GUI senza --demo e seleziona un GGUF per chattare.':'Design preview: start the GUI without --demo and select a GGUF to chat.',
'Questa chat contiene immagini: seleziona Vision locale o apri una nuova chat di testo.':'This chat contains images: select local Vision or start a new text chat.',
'La ricerca web è disponibile solo con il modello di testo locale.':'Web search is only available with the local text model.',
'Descrivi questa immagine.':'Describe this image.',
'Seleziona Vision locale per rigenerare questa risposta con immagini.':'Select local Vision to regenerate this answer with images.',
'Elaborazione del prompt':'Processing prompt','Elaborazione del prompt…':'Processing prompt…','Generazione':'Generating',
'Generazione interrotta.':'Generation stopped.','Seleziona un modello GGUF nelle impostazioni':'Choose a GGUF model in Settings',
'Allega file locale':'Attach a local file','Testo e immagini (*.txt *.md *.png *.jpg *.jpeg *.webp)':'Text and images (*.txt *.md *.png *.jpg *.jpeg *.webp)',
"Il file supera 1 MiB; seleziona un estratto piu' breve.":'The file exceeds 1 MiB; select a shorter excerpt.',
'Per le immagini seleziona Vision locale nelle impostazioni e indica llama-server e mmproj.':'For images, select local Vision in Settings and choose llama-server and mmproj.',
'Massimo quattro immagini per messaggio':'Up to four images per message',
'Motore vision':'Vision runtime','Aggiornamenti':'Updates','Aggiornamenti LLocalMind':'LLocalMind updates',
'Installazione motore vision…':'Installing vision runtime…','Controllo aggiornamenti…':'Checking for updates…','Download aggiornamento…':'Downloading update…',
'Annulla':'Cancel','Motore installato, ma configurazione non salvata: ':'Runtime installed, but settings could not be saved: ',
'Motore vision pronto':'Vision runtime ready','Il motore vision è installato e configurato. Seleziona il modello GGUF e il suo mmproj, poi salva.':'The vision runtime is installed and configured. Select the model GGUF and its mmproj, then save.',
'Nessun aggiornamento disponibile (incluse le anteprime).':'No updates available (including previews).','Aggiornamento disponibile':'Update available',
' · anteprima':' · preview','Scarica aggiornamento':'Download update','Non ora':'Not now','Download completato':'Download complete',
'Installa aggiornamento':'Install update',"Salvare la conversazione e chiudere il modello per installare l'aggiornamento?":'Save the conversation and close the model to install the update?',
'Chiusura del modello…':'Closing model…','Installazione aggiornamento':'Update installation',' · Anteprima':' · Preview',
'Anteprima':'Preview','Anteprima · statistiche non misurate':'Preview · statistics not measured',
'Una giornata di studio':'A day of studying','Aiutami a organizzare una giornata di studio.':'Help me plan a day of studying.',
'Ecco un programma semplice, con il giusto spazio per le pause.\n\n09:00 — Ripasso\n10:30 — Pausa\n11:00 — Esercizi':'Here is a simple schedule with time for breaks.\n\n09:00 — Review\n10:30 — Break\n11:00 — Practice',
'Idee per un progetto':'Project ideas','Spiegare un concetto':'Explain a concept',
'Da dove iniziamo?':'Where shall we start?','Copia':'Copy','Rigenera':'Regenerate','Risposta non completata.':'Answer incomplete.',
'Ricerca web · DuckDuckGo\n\n':'Web search · DuckDuckGo\n\n','Immagine non disponibile: ':'Image unavailable: ',
'Media della generazione dopo il primo token; elaborazione del prompt esclusa.':'Average generation speed after the first token; prompt processing excluded.',
'Servono almeno due token e un tempo di generazione valido per misurare i tok/s.':'At least two tokens and valid generation timing are needed to measure tok/s.',
' Generazione interrotta.':' Generation stopped.','; modello linguistico: CPU.':'; language model: CPU.',
'Impostazioni · LLocalMind':'Settings · LLocalMind','Il tuo modello, sul tuo PC':'Your model, on your PC','Seleziona il file GGUF…':'Select the GGUF file…',
'Sfoglia…':'Browse…','Il modello resta nella posizione scelta e non viene incluso negli aggiornamenti.':'The model stays in its selected location and is not included in app updates.',
'Testo · Intel ottimizzato':'Text · Intel optimized','Testo e immagini · llama.cpp locale':'Text and images · local llama.cpp','Motore':'Engine',
'mmproj compatibile':'Compatible mmproj','Eseguibile (llama-server.exe llama-server)':'Executable (llama-server.exe llama-server)',
'Installa / aggiorna motore vision CPU':'Install / update CPU vision runtime',
'Serve una versione di llama.cpp che supporti il modello e il suo mmproj. L’encoder immagini e il modello usano la CPU. Il pulsante scarica e configura il motore; modello e mmproj restano da selezionare.':'A llama.cpp version supporting your model and mmproj is required. The image encoder and model use CPU. The button downloads and configures the runtime; select the model and mmproj separately.',
'Parametri avanzati · configurazione consigliata preimpostata':'Advanced options · recommended defaults',
'Token massimi di risposta':'Maximum response tokens','Contesto massimo':'Maximum context','Cache esperti':'Expert cache','Cache pesi convertiti':'Converted-weight cache',
'Worker esperti CPU':'CPU expert workers','Thread prefill CPU':'CPU prefill threads','Token visivi massimi':'Maximum visual tokens','Thread Vision CPU':'CPU vision threads',
'Batch vision':'Vision batch','Microbatch vision':'Vision microbatch','Cache prompt vision (MiB)':'Vision prompt cache (MiB)',
'Prepara il motore prima di «Pronto»':'Warm up the runtime before showing “Ready”',
'Meno token visivi riducono il lavoro ma possono perdere dettagli e scritte piccole. Disattivare la preparazione iniziale accelera l’avvio ma può rallentare la prima risposta.':'Fewer visual tokens reduce work but may lose detail and small text. Disabling warm-up speeds up startup but may delay the first answer.',
'Temperatura':'Temperature','Controlla aggiornamenti':'Check for updates','Interrompi la risposta prima di cambiare modello o configurazione.':'Stop the answer before changing model or settings.',
'Salva':'Save','Seleziona modello GGUF':'Select a GGUF model','Modelli GGUF (*.gguf)':'GGUF models (*.gguf)',
'Il file del modello selezionato non esiste':'The selected model file does not exist','Seleziona llama-server e il mmproj compatibile':'Select llama-server and the compatible mmproj',
'Il mmproj deve essere un file GGUF':'The mmproj must be a GGUF file','Preparazione del modello':'Preparing model','Preparazione del tokenizer':'Preparing tokenizer','Modello pronto':'Model ready',
'Carica prima un modello':'Load a model first','La conversazione supera il contesto disponibile. Apri una nuova chat o aumenta il contesto nelle impostazioni.':'The conversation exceeds the available context. Start a new chat or increase context in Settings.',
'Ricerca DuckDuckGo':'Searching DuckDuckGo','Analisi locale':'Local analysis','Impostazioni non valide':'Invalid settings','Percorso non valido':'Invalid path',
'Motore non valido':'Invalid engine','Il limite di output deve essere inferiore al contesto':'The output limit must be smaller than the context',
'Impostazione vision non valida: ':'Invalid vision setting: ','Profilo vision non valido':'Invalid vision profile','Dispositivo non valido':'Invalid device','Temperatura non valida':'Invalid temperature',
'Archivio conversazioni non valido':'Invalid conversation archive','Conversazione non valida':'Invalid conversation','Messaggi non validi':'Invalid messages','Messaggio non valido':'Invalid message',
'Impostazione ricerca web non valida':'Invalid web search setting','Identificatori duplicati':'Duplicate identifiers','La conversazione deve terminare con una domanda':'The conversation must end with a question',
'Ordine dei messaggi non valido':'Invalid message order','Riferimento immagine non valido':'Invalid image reference','Immagine troppo grande':'Image too large','Immagine salvata danneggiata':'Stored image is corrupted',
'Seleziona un’immagine locale di massimo 20 MiB':'Select a local image of at most 20 MiB','Usa PNG, JPEG o WebP fino a 32 megapixel':'Use PNG, JPEG or WebP up to 32 megapixels','Immagine convertita troppo grande':'Converted image is too large',
'Connessione vision interrotta':'Vision connection interrupted','Modello e mmproj devono essere file GGUF compatibili':'Model and mmproj must be compatible GGUF files','Profilo prestazioni vision non valido':'Invalid vision performance profile',
'Caricamento vision · encoder e modello CPU':'Loading vision · CPU encoder and model','Vision pronta · encoder CPU':'Vision ready · CPU encoder','Motore vision chiuso: ricarica il modello':'Vision runtime is closed: reload the model',
'Vision: richiesta rifiutata; verifica contesto e mmproj. ':'Vision: request rejected; check context and mmproj. ','Risposta vision interrotta prima della fine':'Vision answer interrupted before completion',
'Manifest del motore non valido':'Invalid runtime manifest','Percorso ZIP non valido':'Invalid ZIP path','Installazione annullata':'Installation cancelled',
'Installazione automatica disponibile su Windows x64':'Automatic installation is available on Windows x64','Eseguibile Windows x64 non valido':'Invalid Windows x64 executable',
'Verifica del motore vision scaduta':'Vision runtime verification timed out','Il motore scaricato non si avvia: ':'The downloaded runtime failed to start: ',
'Dimensione del download non valida':'Invalid download size','Verifica SHA-256 del motore fallita: download incompleto o modificato':'Runtime SHA-256 verification failed: incomplete or modified download',
'Archivio del motore troppo grande':'Runtime archive too large','Archivio ZIP ambiguo o con collegamenti':'Ambiguous ZIP archive or links found','llama-server.exe o DLL mancanti nell’archivio':'llama-server.exe or DLLs missing from archive',
'Installazione motore vision non riuscita: ':'Vision runtime installation failed: ','Redirect del download senza HTTPS':'Non-HTTPS download redirect',
'URL non valido':'Invalid URL','Host locale non consentito':'Local host is not allowed','Host non pubblico non consentito':'Non-public host is not allowed','Host non raggiungibile':'Host is unreachable',
'La domanda per la ricerca web deve contenere da 1 a 500 caratteri':'The web search query must contain 1 to 500 characters','DuckDuckGo non ha restituito risultati HTTPS pubblici utilizzabili':'DuckDuckGo returned no usable public HTTPS results',
'La pagina supera il limite di download':'Page exceeds the download limit','Il risultato non è una pagina HTML o testo':'Result is not an HTML or text page','La pagina non contiene testo leggibile':'Page has no readable text','La ricerca web non contiene risultati':'Web search has no results',
'estratto della pagina':'Page excerpt','snippet DuckDuckGo; pagina non letta':'DuckDuckGo snippet; page not read',
'URL dell’aggiornamento senza HTTPS':'Update URL does not use HTTPS',"URL dell'aggiornamento senza HTTPS":'Update URL does not use HTTPS',
"L'asset non appartiene alla release GitHub prevista":'The asset does not belong to the expected GitHub release',"L'aggiornamento non e' piu' recente":'The update is no longer newer',
'Dimensione installer non valida':'Invalid installer size','Nome installer non valido':'Invalid installer name','Tag e versione della release non corrispondenti':'Release tag and version do not match',
'Release senza installer Windows valido per LLocalMind':'Release has no valid LLocalMind Windows installer','La release non contiene un checksum SHA-256':'Release has no SHA-256 checksum',
'Redirect dell’aggiornamento senza HTTPS':'Non-HTTPS update redirect',"Redirect dell'aggiornamento senza HTTPS":'Non-HTTPS update redirect',
'File checksum troppo grande':'Checksum file too large','Checksum non valido':'Invalid checksum','Checksum non valido o riferito a un altro file':'Invalid checksum or checksum for another file',
"Checksum SHA-256 dell'installer non corrispondente":'Installer SHA-256 checksum mismatch',"Installer piu' grande del previsto":'Installer larger than expected',
"Download dell'aggiornamento fallito":'Update download failed','Installer fuori dalla cartella aggiornamenti':'Installer is outside the update folder',"L'installer e' cambiato dopo il download":'The installer changed after download',
'LLocalMind · chat locale':'LLocalMind · local chat','Anteprima della GUI senza caricare il modello':'Preview the GUI without loading a model',
}

EN.update({
    'Caricamento {percent}%':'Loading {percent}%',
    ' · {seconds} s al primo token':' · {seconds} s to first token',
    'LLocalMind {version}{channel} è disponibile.':'LLocalMind {version}{channel} is available.',
    'Installer verificato:\n{path}\n\nDai sorgenti continua a usare git pull.':'Installer verified:\n{path}\n\nFor source checkouts, continue using git pull.',
    '\nElaborazione prompt: {seconds:.2f} s.':'\nPrompt processing: {seconds:.2f} s.',
    '\nPrompt: {count} token; cache: {cached}.':'\nPrompt: {count} tokens; cached: {cached}.',
    '\nEncoder immagini: ':'\nImage encoder: ',
    '\nLimite per immagine: {count} token visivi.':'\nPer-image limit: {count} visual tokens.',
    '{count} token · tok/s non misurabili':'{count} token(s) · tok/s unavailable',
    '{rate} tok/s · {count} token':'{rate} tok/s · {count} token(s)',
})

EN.update({
    'Ricerca DuckDuckGo non riuscita: {error}':'DuckDuckGo search failed: {error}',
    'Lettura di {count} risultati web':'Reading {count} web results',
    'Pagina non disponibile ({error}).':'Page unavailable ({error}).',
})

EN.update({
    'Impostazione non valida: {key}':'Invalid setting: {key}',
    'Archivio locale non leggibile: {error}. I file originali non saranno sovrascritti.':'Local archive cannot be read: {error}. Original files will not be overwritten.',
    'Versione non valida: {version}':'Invalid version: {version}',
    'Controllo GitHub fallito (HTTP {code})':'GitHub update check failed (HTTP {code})',
    'File {label} non trovato: {path}':'{label} file not found: {path}',
    'Avvio vision fallito: verifica versione di llama.cpp e compatibilità modello/mmproj. Log: {path}':'Vision startup failed: check llama.cpp version and model/mmproj compatibility. Log: {path}',
    'Tempo di caricamento vision superato. Log: {path}':'Vision loading timed out. Log: {path}',
    'Contesto insufficiente: richiesta {count} token, limite {limit}. Riduci i token visivi o la cronologia, oppure aumenta il contesto nelle impostazioni se la RAM lo consente.':'Insufficient context: request has {count} tokens, limit is {limit}. Reduce visual tokens or history, or increase context in Settings if RAM permits.',
})
