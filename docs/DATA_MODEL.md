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
