# Architettura

## Moduli

### 1. Interfaccia desktop
Schermata narrativa e editor in italiano.

### 2. Importatore Bibbia
Accetta un pacchetto di mondo e lo converte nel formato interno.

Nel Task 006, `haria_engine/world_package.py` legge cartelle e ZIP, fotografa i
file, applica limiti e controlli sui percorsi, valida manifest, hash, entità,
documenti e media e restituisce soltanto modelli immutabili. Lo ZIP vive in una
directory temporanea. Nessuna connessione SQLite o GUI entra nel parser.

La lettura e validazione avvengono su un worker daemon. Il risultato tipizzato
torna al thread principale, che esegue l'unica transazione di importazione e
aggiorna Tkinter. Il worker non riceve database, widget o provider AI.

### 3. Archivio canonico
Conserva la Bibbia originale, versionata e non distruttiva.

### 4. Stato corrente
Registra posizione, possesso, condizioni, relazioni, accessibilità e stato delle entità.

### 5. Registro eventi
Ogni cambiamento rilevante diventa un evento immutabile.

Nel Task 002, `haria_engine/world_state.py` espone le sole operazioni strutturate
validate. `haria_engine/storage.py` applica evento, associazioni alle entità e
aggiornamenti dello stato nella stessa transazione SQLite. I registri `events`
ed `event_entities` sono protetti anche da trigger contro aggiornamenti e
cancellazioni.

### 6. Memorie soggettive
Ogni personaggio conosce soltanto ciò che ha osservato, dedotto o appreso.

Nel Task 003, `haria_engine/memories.py` contiene modelli e servizio tipizzati.
`haria_engine/storage.py` inserisce memoria, associazioni alle entità e memorie
sorgente nella stessa transazione. `memories`, `memory_entities` e
`memory_sources` sono protette da trigger contro aggiornamenti e cancellazioni.
Una correzione aggiunge una nuova memoria e non riscrive quella storica.

### 7. Motore narrativo
Prepara il contesto e interroga l'LLM locale.

Nel Task 007, `haria_engine/narrative_service.py` risolve il personaggio
giocante dal `world.json` archiviato, raccoglie scenario, documenti, stato,
profili, memorie correnti e gli ultimi venti messaggi e costruisce i modelli
del prompt senza SQL nella GUI. `narrative_prompt.py` produce esattamente i due
messaggi mostrabili e inviabili; `narrative_parser.py` converte la risposta JSON
in proposte immutabili.

Nel Task 008, `narrative_history.py` espone sessioni e turni persistiti come
modelli immutabili, mentre `narrative_persistence.py` costruisce il piano puro
del turno. `storage.py` applica turno, eventi, associazioni, stato, memorie e
avanzamento temporale in una sola transazione SQLite. Esiste una sola
cronologia per mondo; la GUI rilegge la conversazione dal database e non ne
mantiene una seconda fonte di verità.

La GUI prepara il contesto nel thread principale, affida al worker soltanto
`/api/chat` e valida la risposta nel thread principale. Il dry-run usa
`ServizioValidazione.valida_sequenza`; un errore impedisce di mostrare il testo
come turno riuscito. In caso di successo il piano viene applicato dall'unica
API atomica dell'archivio e la GUI rilegge i dati soltanto dopo il commit.

### 8. Motore di simulazione
Fa avanzare processi fuori scena.

### 9. Validatore
Controlla coerenza spaziale, temporale, epistemica e inventariale.

Nel Task 005, `haria_engine/validation_models.py` definisce fotografie,
proposte, problemi ed esiti immutabili; `haria_engine/validation.py` costruisce
la fotografia usando esclusivamente letture tipizzate dell'archivio e offre il
servizio applicativo; `haria_engine/validation_rules.py` contiene regole pure,
ordinamento deterministico e proiezioni dry-run in memoria.

Il validatore non riceve connessioni SQLite, non esegue SQL, non chiama API di
scrittura e non contatta provider AI. La fotografia esclude testo narrativo,
JSON e cursori del database: contiene soltanto i campi strutturati necessari ai
controlli. La simulazione restituisce una nuova fotografia e non crea eventi,
memorie o versioni.

### 10. Provider LLM
Interfaccia sostituibile. Prima implementazione: Ollama.

Nel Task 004, `haria_engine/ai_models.py` contiene configurazione e risultati
immutabili; `haria_engine/http_transport.py` isola `urllib` con limiti e senza
redirect; `haria_engine/ollama_provider.py` implementa le API REST native;
`haria_engine/llm_service.py` espone il servizio applicativo privo di accesso a
SQLite e Tkinter. `haria_engine/async_coordinator.py` esegue una sola richiesta
per volta su worker daemon e consegna gli esiti al thread principale tramite
coda.

La GUI crea una fotografia validata dei campi visibili. Per il turno narrativo
il worker riceve soltanto configurazione e messaggi immutabili e non esegue
`/api/tags` prima di `/api/chat`. Il worker riceve
soltanto tale fotografia e il servizio HTTP: connessioni SQLite, widget,
variabili Tkinter e oggetti narrativi restano nel thread principale. Il polling
con `after` avviene esclusivamente nel thread Tkinter; chiusura e risultati
tardivi sono gestiti senza aggiornare widget distrutti.

## Flusso di un turno
1. ricezione azione utente;
2. analisi dell'azione;
3. recupero di stato e ricordi rilevanti;
4. avanzamento dei processi;
5. generazione narrativa;
6. proposta di operazioni strutturate;
7. validazione;
8. applicazione atomica;
9. salvataggio scena;
10. risposta all'utente.

## Regola fondamentale
La narrazione non è la fonte della verità.
Il database è la fonte della verità.

## Confini implementati fino al Task 008

- Il canone originale resta immutabile in `world_entities.canonical_data` e
  nelle fotografie sorgente.
- Lo stato operativo corrente, incluso `current_status`, resta in
  `entity_state`.
- Gli eventi sono righe immutabili in `events`; `event_entities` ne registra le
  entità coinvolte e permette una cronologia completa senza creare duplicati.
- Le memorie appartengono a un solo personaggio e restano separate da canone,
  stato ed eventi. La presenza a un evento non crea automaticamente memoria.
- `memory_entities` rende filtrabili soggetti, fonti, luoghi ed entità correlate
  senza interpretare il testo; `memory_sources` conserva l'ordine delle memorie
  usate per un'inferenza.
- Le correzioni formano catene lineari append-only. `status` conserva la natura
  immutabile della nuova memoria; `is_current` ed `effective_status` sono
  calcolati verificando l'esistenza di un successore.
- La configurazione narrativa continua a essere versionata separatamente.
- La configurazione AI è globale per file SQLite, separata dai mondi e dalle
  versioni narrative. Il provider contatta soltanto un URL di loopback
  validato e non può leggere o modificare dati narrativi.
- Il provider Ollama supporta verifica, elenco modelli, prova testuale e una
  richiesta narrativa non streaming. La generazione narrativa non applica
  ancora alcun cambiamento persistente.
- Il validatore legge canone, stato, eventi e memorie attraverso il servizio
  applicativo, produce problemi ordinati e può simulare proposte soltanto in
  memoria.
- L'audit dalla GUI è manuale: non parte all'avvio e il risultato viene
  azzerato quando cambia il mondo selezionato.
- Lo schema 5 indicizza documenti e media completi; i byte dei media restano
  soltanto in `source_files` e vengono recuperati tramite chiavi esterne.
- Il parser supporta `world.json` ma non YAML, conserva campi canonici non
  interpretati e rifiuta l'intero pacchetto prima di scrivere se manifest,
  hash, riferimenti o percorsi non sono coerenti.
- Le schede Personaggi, Lore, Regole e stile e Media leggono modelli tipizzati,
  non mostrano JSON o ID e usano un fallback italiano per anteprime non native.
- La scheda Gioca mostra soltanto input utente e prosa validata. Il prompt
  effettivo è ispezionabile separatamente; la vista carica al massimo cento
  turni e il prompt gli ultimi venti messaggi, mentre l'archivio conserva tutto.
- Il motore non aggiunge moderazione narrativa, blacklist o filtri tematici.
  Non sono ancora attive ricerca semantica o simulazione fuori scena.

La GUI legge modelli tipizzati e non accede direttamente a SQL o dati tecnici.
La vista delle memorie usa query aggregate per fonti ed entità collegate.
