# Codex Task 002 — Stato corrente del mondo e registro eventi immutabile

## Obiettivo

Estendere Haria Engine con uno stato corrente persistente per personaggi, luoghi
e oggetti e con un registro di eventi immutabile. Lo stato corrente è la verità
operativa: ogni sua modifica deriva da un'operazione strutturata validata e da
un evento salvato atomicamente nella stessa transazione SQLite.

## Ambito escluso

Non integrare in questo task:

- LLM o Ollama;
- generazione narrativa;
- memorie soggettive dei personaggi;
- simulazione fuori scena;
- Haria Bible completa;
- relazioni sociali avanzate;
- combattimento;
- mappe grafiche.

Non creare la tabella `memories` e non preparare implementazioni speculative
per i task futuri.

## Vincoli architetturali

Mantenere separati:

1. canone importato;
2. stato corrente;
3. registro eventi;
4. future memorie soggettive;
5. configurazione narrativa.

Il canone non viene sovrascritto. La descrizione narrativa non è fonte di
verità. JSON, SQL, UUID completi e payload tecnici non sono mostrati
nell'interfaccia normale.

Riusare Python, Tkinter, SQLite e `unittest` senza introdurre dipendenze esterne,
framework o refactoring non richiesti.

## Schema SQLite 2

Introdurre con una migrazione esplicita da schema 1 a schema 2 le tabelle
seguenti.

### `world_entities`

- `world_id`;
- `entity_id` stabile e non derivato dal nome visibile;
- `entity_type`;
- `canonical_name`;
- `canonical_data`;
- `created_at`;
- `updated_at`.

La tabella conserva soltanto identità e canone importato e non viene aggiornata
dalle operazioni runtime. L'eventuale `status` originale resta esclusivamente
dentro `canonical_data`.

### `entity_state`

- `world_id`;
- `entity_id`;
- `current_status`;
- `location_id` opzionale;
- `holder_id` opzionale;
- `accessibility`;
- `condition`;
- `state_data`;
- `version`;
- `updated_at`.

### `events`

- `event_id` stabile;
- `world_id`;
- `event_type`;
- `occurred_at`;
- `actor_id` opzionale;
- `target_id` opzionale;
- `location_id` opzionale;
- `payload`;
- `reason`;
- `created_at`.

### `event_entities`

- `event_id`;
- `world_id`;
- `entity_id`;
- `role`, con valori `actor`, `target`, `location` o `affected`;
- chiave primaria `(event_id, entity_id, role)`;
- chiave esterna verso `events`;
- chiave esterna composta verso `world_entities`.

Ogni evento associa automaticamente attore, bersaglio e luogo quando presenti,
oltre a tutte le entità il cui stato viene aggiornato. Il registro `events` e le
associazioni `event_entities` sono append-only:

- nessuna API applicativa di modifica o cancellazione;
- trigger SQLite che rifiutano `UPDATE` e `DELETE`;
- test diretti di entrambi i tentativi.

## Migrazione dei database Task 001

La migrazione deve essere transazionale, idempotente e non distruttiva.

- Conservare mondi, scenari, versioni e file sorgente archiviati.
- Ricostruire canone e stato iniziale usando esclusivamente le fotografie nella
  tabella `source_files`.
- Non leggere nuovamente la cartella originale dell'utente.
- Se i file archiviati richiesti sono incompleti o non validi, annullare
  interamente la migrazione.
- In caso di fallimento, `PRAGMA user_version` resta `1` e nessuna tabella Task
  002 resta popolata parzialmente.
- Aggiornare `PRAGMA user_version` a `2` soltanto al termine della migrazione
  riuscita.
- Restituire un errore italiano leggibile.
- La riapertura di un database già migrato non deve duplicare dati né eventi.

## Importazione del mini-mondo

Durante una nuova importazione leggere dalle copie già acquisite in memoria:

- `characters.json`;
- `locations.json`;
- `items.json`.

Importare personaggi, luoghi e oggetti come canone separato e creare il loro
stato iniziale. Non modificare i file sorgente.

Entità minime attese:

- personaggi: Luca, Élise e Akari;
- luoghi: infermeria e assemblea;
- oggetti: penna blu, piccolo quaderno e chiavi dell'infermeria.

Preservare la posizione canonica iniziale di Akari nell'assemblea, come definita
in `sample_world/characters.json`.

## Servizio applicativo e operazioni

Esporre un servizio tipizzato che accetta soltanto operazioni validate.

### `sposta_entita`

Cambia la posizione di un personaggio o di un oggetto e crea un evento
immutabile.

### `trasferisci_oggetto`

Assegna un oggetto a un possessore e aggiorna coerentemente posizione e
possessore, creando un singolo evento immutabile.

### `cambia_stato`

Modifica uno o più valori tra `status`, `condition` e `accessibility`, creando un
evento immutabile. `status` modifica soltanto `entity_state.current_status` e
non il canone.

### `registra_evento_descrittivo`

Aggiunge un evento senza modificare lo stato corrente.

## Transazioni e validazioni

Ogni operazione che modifica lo stato deve:

1. validare il mondo;
2. validare tutte le entità coinvolte;
3. validare il tipo delle entità;
4. aprire una transazione SQLite;
5. inserire l'evento;
6. inserire tutte le associazioni in `event_entities`;
7. aggiornare lo stato;
8. completare tutte le scritture oppure annullarle tutte.

Validazioni minime:

- un oggetto non può avere contemporaneamente `holder_id` e `location_id`
  incoerenti;
- il possessore deve esistere ed essere un personaggio;
- la posizione deve esistere ed essere un luogo;
- un oggetto trasferito a un personaggio deve risultare localizzato presso quel
  personaggio o avere una posizione derivata coerente;
- un'entità con stato inesistente non può essere modificata;
- non inventare entità mancanti;
- errori leggibili in italiano.

Un errore in qualsiasi passaggio deve lasciare invariati `events`,
`event_entities` ed `entity_state`.

## Caso di collaudo obbligatorio

1. Luca ed Élise partono nell'infermeria.
2. Akari parte nell'assemblea.
3. La penna blu è nell'infermeria e non posseduta.
4. Le chiavi dell'infermeria sono nell'infermeria e non possedute.
5. Eseguire `sposta_entita` per portare Akari nell'infermeria.
6. Creare esattamente un evento immutabile per lo spostamento di Akari.
7. Eseguire `trasferisci_oggetto` per assegnare la penna blu a Luca.
8. Creare esattamente un evento immutabile per il trasferimento della penna,
   senza duplicati.
9. La penna risulta posseduta da Luca e localizzata coerentemente.
10. Le chiavi restano nell'infermeria, non possedute e senza nuovi eventi.
11. Chiudere e riaprire il servizio.
12. Stato ed eventi devono persistere.

Non implementare conoscenze o memorie di Élise e Akari: appartengono al Task
003.

## Interfaccia italiana

Aggiungere la sezione `Stato del mondo`, che permette almeno di:

- vedere personaggi, luoghi e oggetti;
- vedere posizione, possessore, stato e accessibilità;
- selezionare un'entità;
- vedere la relativa cronologia eventi;
- trasferire manualmente un oggetto con controlli leggibili;
- aggiornare la schermata dopo ogni operazione.

Non trasformare la GUI in un editor generico del database.

## Criteri di accettazione

- Schema 2 creato tramite migrazione esplicita e idempotente.
- Database schema 1 migrato senza perdita dei dati Task 001.
- Rollback integrale della migrazione se gli archivi sorgente sono incompleti o
  non validi.
- Canone, stato corrente, eventi e configurazione narrativa restano separati.
- Importate tutte le entità minime con ID stabili.
- Canone e file sorgente non vengono modificati dalle operazioni.
- Lo stato corrente, incluso `current_status`, risiede soltanto in
  `entity_state`.
- Tutte le modifiche di stato derivano da eventi immutabili.
- Evento, associazioni alle entità e stato sono scritti nella stessa
  transazione.
- Trigger SQLite impediscono aggiornamento e cancellazione di eventi e relative
  associazioni.
- Le quattro operazioni obbligatorie sono tipizzate e validate.
- Il caso penna, chiavi e spostamento di Akari persiste dopo riavvio.
- Interfaccia `Stato del mondo` completamente leggibile in italiano.
- Nessuna esposizione di JSON, SQL, UUID completi o payload tecnici.
- Tutti i test Task 001 continuano a passare.

## Test obbligatori

Aggiungere test automatici per:

- migrazione schema 1 → schema 2;
- rollback di una migrazione fallita e `user_version` ancora a 1;
- riapertura di database già migrato;
- importazione entità dal mini-mondo;
- separazione canone/stato;
- immutabilità di `canonical_data` e della riga `world_entities` dopo
  `cambia_stato`;
- aggiornamento e persistenza di `entity_state.current_status`;
- posizione iniziale di Akari nell'assemblea;
- spostamento valido di Akari nell'infermeria e singolo evento associato;
- trasferimento valido della penna a Luca;
- persistenza dopo riavvio;
- chiavi rimaste in posizione, non possedute e senza eventi;
- evento della penna creato una sola volta;
- eventi append-only tramite tentativi di `UPDATE` e `DELETE`;
- oggetti posseduti che seguono il personaggio con lo stesso evento, senza
  duplicati;
- associazioni `actor`, `target`, `location` e `affected`;
- trigger append-only su `event_entities`;
- rollback completo se l'inserimento di un'associazione fallisce;
- rollback completo se l'aggiornamento dello stato fallisce;
- possessore inesistente;
- posizione inesistente;
- tipo entità errato;
- operazione su entità inesistente;
- errori italiani;
- sorgenti non modificati;
- visualizzazione italiana dello stato;
- nessuna esposizione JSON nella GUI normale.

Eseguire l'intera suite esistente e nuova.

## Consegna Git

- Branch: `feature/task-002-world-state-events`.
- Primo commit: `docs: define Haria Engine Task 002`.
- Commit successivi piccoli per migrazione, servizi, interfaccia, test e
  documentazione finale.
- Aggiornare `README.md`, `docs/DATA_MODEL.md`, `docs/ARCHITECTURE.md` soltanto
  dove necessario e creare `docs/TASK_002_STATUS.md`.
- Pubblicare il branch e aprire una pull request verso `main`.
- Non eseguire il merge.
