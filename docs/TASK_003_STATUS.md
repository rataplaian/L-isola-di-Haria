# Stato Codex Task 003

## Implementato

- migrazione SQLite transazionale e idempotente dallo schema 2 allo schema 3;
- ricostruzione delle conoscenze iniziali dai soli BLOB `characters.json`
  archiviati in `source_files`, con ID deterministici;
- rollback completo con `user_version` invariato e nessuna tabella parziale;
- tabelle append-only `memories`, `memory_entities` e `memory_sources`;
- trigger SQLite che impediscono `UPDATE` e `DELETE` sulle tre tabelle;
- inserimento atomico di memoria, entità collegate e memorie sorgente;
- servizio tipizzato per osservazione diretta, racconto, inferenza, correzione ed
  elenco filtrato;
- separazione rigorosa tra memoria soggettiva, canone, stato corrente ed eventi;
- catene di correzione lineari, senza autoreferenze o ramificazioni;
- esposizione distinta di `status`, `is_current` ed `effective_status`;
- memorie sorgente ordinate e vincolate allo stesso mondo e personaggio;
- query aggregate per fonti leggibili, entità collegate e stato logico;
- scheda italiana in sola lettura **Memorie dei personaggi**, con vista corrente,
  cronologia completa, filtro per entità e distinzione visiva delle fonti;
- nessuna esposizione di JSON, SQL, UUID o payload tecnici nella GUI.

## Caso di collaudo

- Luca prende la penna blu tramite un solo evento `trasferimento_oggetto`;
- non viene creata alcuna memoria automatica;
- Élise, presente nell'infermeria, registra esplicitamente un'osservazione
  collegata a Luca, penna e infermeria;
- Akari, ancora nell'assemblea, non può registrare l'osservazione diretta;
- evento e memoria di Élise persistono dopo il riavvio, mentre Akari resta
  ignara;
- il successivo racconto di Élise crea per Akari una memoria distinta con fonte
  e certezza proprie;
- il contenuto soggettivo «Luca ha rubato la penna» non inventa un evento di
  furto e non modifica lo stato della penna;
- una correzione conserva la vecchia memoria nella cronologia e rende corrente
  soltanto la nuova.

## Verifica

```powershell
python -m unittest discover -s tests -v
python -m haria_engine --check
```

Esito suite: **90 test superati su 90**, inclusi tutti i 55 test precedenti.

`python -m haria_engine --check` ha completato correttamente la verifica
dell'archivio SQLite usando il runtime disponibile nella sessione.

La GUI è stata avviata con il runtime incorporato, ispezionata visivamente e
chiusa regolarmente. La scheda **Memorie dei personaggi**, i filtri, la vista
cronologica e le intestazioni italiane risultano leggibili; una barra
orizzontale mantiene accessibili tutte le colonne. Non sono state installate
dipendenze. Le installazioni di sistema non sono utilizzabili su questa
macchina: il comando `py` non è presente e `python` è soltanto l'alias del
Microsoft Store.

## Escluso perché fuori ambito

- Task 004, LLM, Ollama, prompt e generazione narrativa;
- validatore epistemico completo;
- osservazioni retroattive e snapshot temporali;
- diffusione autonoma di informazioni o voci;
- menzogne automatiche, oblio, riassunti, embeddings e database vettoriali;
- editor GUI per creare o correggere memorie.

## Limiti e rischi residui

- L'osservazione diretta verifica la posizione corrente ed è intenzionalmente
  immediata rispetto all'evento; registrazioni retroattive richiederebbero
  snapshot temporali futuri.
- La GUI Task 003 è volutamente in sola lettura; le operazioni di scrittura sono
  disponibili nel servizio tipizzato e coperte dai test.
- Un database schema 2 con fotografia `characters.json` mancante o non valida
  resta integro allo schema 2 e richiede la correzione dei dati archiviati.
- Non esiste un comando di downgrade dallo schema 3 allo schema 2.
- L'avvio tramite Python di sistema non è verificabile su questa macchina finché
  non è disponibile un'installazione Python con Tkinter; il runtime incorporato
  ha comunque consentito il collaudo grafico effettivo.

Task 004 non è stato iniziato.
