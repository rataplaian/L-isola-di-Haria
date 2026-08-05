# Modello dati iniziale

## Entità principali
- worlds
- world_versions
- canon_entries
- scenarios
- narrative_settings
- characters
- locations
- items
- relationships
- events
- memories
- processes
- sessions
- scenes
- saves
- media_assets

## Campi essenziali comuni
- id stabile
- world_id
- created_at
- updated_at
- version
- source
- status
- metadata

## Canone
Il canone è versionato e non viene sovrascritto distruttivamente.

## Stato corrente
Ogni entità conserva uno stato attuale separato dal profilo canonico.

## Eventi
Gli eventi sono immutabili e descrivono la causa dei cambiamenti.

## Schema SQLite implementato fino al Task 004

Lo schema applicativo corrente è la versione 4. Le tabelle dei Task precedenti
restano disponibili senza modifiche distruttive.

### `world_entities`

Conserva l'identità stabile e il canone importato di personaggi, luoghi e
oggetti. La coppia `(world_id, entity_id)` è la chiave primaria. Il campo
`canonical_data` non viene modificato dalle operazioni sullo stato e conserva
l'eventuale status originale. La tabella non contiene uno status operativo e
nessuna operazione runtime aggiorna le sue righe.

### `entity_state`

Conserva `current_status`, posizione, possessore, accessibilità, condizione,
dati di stato, versione e data di aggiornamento. È separata dal canone e
contiene una sola riga corrente per entità. `EntitaMondo.status` legge
`current_status` da questa tabella.

### `events`

Registro append-only con ID evento stabile, tipo, istante, attore, bersaglio,
luogo, dettagli strutturati e motivo leggibile. Non esistono API applicative di
modifica o cancellazione. Due trigger SQLite rifiutano anche `UPDATE` e `DELETE`
diretti.

### `event_entities`

Collega esplicitamente ogni evento alle entità coinvolte con ruolo `actor`,
`target`, `location` o `affected`. La chiave primaria è
`(event_id, entity_id, role)`; le chiavi esterne collegano l'associazione sia
all'evento sia all'entità dello stesso mondo.

Le operazioni registrano come `affected` ogni entità il cui stato viene
aggiornato. In questo modo, quando un personaggio si sposta con un oggetto
posseduto, la cronologia di entrambi mostra lo stesso evento senza duplicarlo.
Due trigger SQLite impediscono `UPDATE` e `DELETE` anche su questa tabella.

## Migrazione 1 → 2

La migrazione crea le quattro tabelle e ricostruisce canone e stato iniziale usando
esclusivamente i BLOB di `source_files`. Tutto avviene in una transazione:
`PRAGMA user_version` diventa 2 soltanto dopo il completamento. File mancanti o
non validi causano rollback completo, lasciando versione e dati Task 001
invariati.

La riapertura di uno schema 2 non ripete la migrazione e non duplica entità.

### `memories`

Conserva conoscenze e convinzioni di un singolo personaggio. Ogni riga include
tipo di conoscenza, tipo e possibile entità fonte, certezza, contenuto, data,
interpretazione ed emozione opzionali, possibile evento e possibile memoria
precedente.

Il campo `status` è immutabile: `active` indica una memoria ordinaria,
`corrected` o `contradicted` descrivono la nuova memoria che sostituisce quella
indicata da `supersedes_memory_id`; `superseded` è supportato dal modello ma il
servizio normale non lo scrive sulla vecchia riga. Una memoria è corrente se
non possiede un successore. `effective_status` vale `superseded` quando un
successore esiste, altrimenti coincide con `status`.

Un indice unico parziale su `supersedes_memory_id` consente un solo successore
diretto. Il riferimento può puntare soltanto a una memoria già esistente dello
stesso mondo e personaggio; poiché le righe non sono aggiornabili o eliminabili,
non sono costruibili né ramificazioni né cicli più lunghi.

### `memory_entities`

Collega una memoria alle entità dello stesso mondo con ruolo `subject`,
`source`, `location` o `related`. Permette filtri strutturati senza dedurre
informazioni dal testo libero.

### `memory_sources`

Registra in ordine positivo le memorie da cui nasce un'inferenza. Memoria
risultante e sorgente devono appartenere allo stesso mondo e personaggio, non
possono coincidere e ogni posizione è unica nella memoria risultante. Una
memoria sorgente può essere corrente o storica.

Le tre tabelle sono append-only: non esistono API applicative di modifica o
cancellazione e trigger SQLite rifiutano `UPDATE` e `DELETE`. Memoria,
`memory_entities` e `memory_sources` vengono inserite nella stessa transazione.

## Migrazione 2 → 3

La migrazione ricostruisce una memoria per ogni voce `knowledge` usando soltanto
le fotografie `characters.json` conservate in `source_files`. Gli ID importati
sono deterministici e includono mondo, personaggio, posizione e impronta del
contenuto. Un archivio mancante o non valido provoca rollback completo:
`PRAGMA user_version` resta 2 e nessuna tabella Task 003 rimane parziale.

### `ai_settings`

Conserva una sola configurazione AI applicativa per file SQLite. La riga ha
`settings_id = 1`, provider `ollama`, URL base, modello, timeout intero tra 1 e
300 secondi e data di aggiornamento. Vincoli SQLite impediscono identificatori
diversi, provider sconosciuti, timeout non interi o fuori intervallo e una
seconda configurazione.

La configurazione è condivisa da tutti i mondi nello stesso database ma non da
database distinti. Non appartiene alle versioni narrative e il salvataggio
aggiorna esclusivamente la riga singleton.

## Migrazione 3 → 4

La migrazione crea `ai_settings` e inserisce atomicamente i valori predefiniti:
provider `ollama`, URL `http://localhost:11434`, modello vuoto e timeout 30
secondi. `PRAGMA user_version` diventa 4 soltanto al termine. Un errore annulla
creazione e inserimento, lascia lo schema 3 e non modifica mondi, versioni,
stato, eventi o memorie. La riapertura non duplica la configurazione.

## Limite temporale delle osservazioni

Nel Task 003 l'osservazione diretta viene registrata immediatamente rispetto
all'evento e verifica la posizione corrente del personaggio. Non sono supportate
osservazioni retroattive: richiederanno snapshot temporali in un task futuro.

## Luoghi
Possibili stati:
- attivo;
- danneggiato;
- distrutto;
- inaccessibile;
- abbandonato;
- sconosciuto;
- storico.

## Personaggi
Possibili stati:
- attivo;
- ferito;
- disperso;
- prigioniero;
- espulso;
- morto;
- incerto.

## Oggetti
Devono avere:
- posizione;
- possessore;
- integrità;
- accessibilità;
- storia degli eventi.
