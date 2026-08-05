# Milestone

## M0 — Fondamenta
- repository;
- documentazione;
- struttura cartelle;
- test runner;
- logging.

## M1 — Editor italiano e mini-Bibbia
- import mini-Bibbia;
- visualizzazione scenario;
- modifica e salvataggio;
- versionamento;
- nessun LLM necessario.

## M2 — Stato ed eventi
- personaggi;
- luoghi;
- oggetti;
- eventi;
- persistenza SQLite.

## M3 — Memorie soggettive — implementato
- conoscenze separate per personaggio;
- osservazioni, racconti, inferenze e correzioni append-only;
- cronologia e vista corrente;
- test di presenza, soggettività, persistenza e rollback.

## M4 — Ollama — collegamento tecnico implementato
- provider locale sostituibile e configurazione persistente;
- verifica versione, elenco modelli e prova testuale non streaming;
- nessun prompt narrativo, output strutturato o modifica del mondo nel Task 004.

## M5 — Validatore — implementato
- audit deterministico di integrità, spazio, tempo, inventario ed epistemica;
- proposte tipizzate e dry-run immutabile, anche in sequenza;
- interfaccia italiana in sola lettura;
- nessuna scrittura, migrazione SQLite o dipendenza da Ollama.

## M6 — Import Haria completo — infrastruttura implementata
- JSON master `world.json` e manifest con SHA-256;
- cartelle e ZIP sicuri, deterministici e compatibili con il formato legacy;
- scenario, regole, stile, personaggi individuali, luoghi, oggetti, lore e timeline;
- media conservati byte-identici e indicizzati senza duplicazione;
- consultazione italiana di personaggi, lore, regole, stile e media;
- pacchetto Haria locale parziale costruito dai soli materiali realmente disponibili.

## M7 — Simulazione fuori scena
- processi;
- avanzamento tempo;
- eventi autonomi.
