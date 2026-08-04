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

## Schema SQLite implementato nel Task 002

Lo schema applicativo corrente è la versione 2. Le tabelle del Task 001
`worlds`, `world_versions` e `source_files` restano invariate.

### `world_entities`

Conserva l'identità stabile e il canone importato di personaggi, luoghi e
oggetti. La coppia `(world_id, entity_id)` è la chiave primaria. Il campo
`canonical_data` non viene modificato dalle operazioni sullo stato.

### `entity_state`

Conserva posizione, possessore, accessibilità, condizione, dati di stato,
versione e data di aggiornamento. È separata dal canone e contiene una sola riga
corrente per entità.

### `events`

Registro append-only con ID evento stabile, tipo, istante, attore, bersaglio,
luogo, dettagli strutturati e motivo leggibile. Non esistono API applicative di
modifica o cancellazione. Due trigger SQLite rifiutano anche `UPDATE` e `DELETE`
diretti.

## Migrazione 1 → 2

La migrazione crea le tre tabelle e ricostruisce canone e stato iniziale usando
esclusivamente i BLOB di `source_files`. Tutto avviene in una transazione:
`PRAGMA user_version` diventa 2 soltanto dopo il completamento. File mancanti o
non validi causano rollback completo, lasciando versione e dati Task 001
invariati.

La riapertura di uno schema 2 non ripete la migrazione e non duplica entità.

## Memorie
Ogni memoria deve indicare:
- personaggio;
- evento collegato;
- tipo di conoscenza;
- certezza;
- fonte;
- data appresa;
- eventuale interpretazione;
- eventuale emozione associata.

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
