# Haria Engine — Task 008: turni narrativi persistenti e atomici

## Punto di partenza

Partire esclusivamente da `main` al commit squash del Task 007:

`c55ab8c71f86532028626f4ba100a521c699737a`

Branch richiesto:

`feature/task-008-persistent-turns`

La fondazione preparata aggiunge:

- `haria_engine/narrative_persistence.py`;
- `tests/test_task_008_foundation.py`;
- questo documento.

La fondazione contiene il piano puro e deterministico che converte un turno già
validato in eventi, aggiornamenti finali dello stato, memorie e record del turno.
I suoi 14 test devono passare prima e dopo l'integrazione. Non riscrivere il piano
salvo un errore concreto dimostrato da un test.

## Obiettivo

Trasformare la scheda **Gioca** da anteprima volatile a partita locale persistente.

Dopo una risposta Ollama valida, il programma deve salvare in una singola
transazione SQLite:

1. input dell'utente e narrazione;
2. prompt effettivo e output grezzo del modello;
3. tempo narrativo trascorso;
4. un evento immutabile per ogni operazione proposta;
5. stato finale delle entità coinvolte;
6. memorie candidate validate;
7. collegamenti del turno a eventi e memorie.

Tutto deve essere applicato oppure nulla deve cambiare.

## Principi non negoziabili

- Il database resta la fonte della verità.
- Il testo narrativo non modifica direttamente lo stato.
- L'LLM propone; parser e validatore decidono se il turno è applicabile.
- Nessuna scrittura avviene prima che parsing, validazione e piano siano completi.
- Nessuna operazione parziale deve sopravvivere a un errore.
- Nessun contenuto viene inviato a servizi cloud.
- Non aggiungere moderazione narrativa, classificatori morali, blacklist di parole
  o filtri tematici. Haria è destinato ad adulti e deve poter conservare testo
  italiano profondo, controverso o esplicito senza alterarlo.
- Le regole canoniche e l'autonomia dei personaggi restano obbligatorie. I
  personaggi coinvolti in contenuti sessuali devono essere adulti.

Questa assenza di censura narrativa non modifica i controlli tecnici di coerenza,
integrità e riferimenti.

## 1. Schema SQLite 6

Aggiungere una migrazione atomica da schema 5 a schema 6.

### `narrative_sessions`

Una sola cronologia narrativa per mondo in questo task:

- `session_id TEXT PRIMARY KEY`;
- `world_id TEXT NOT NULL UNIQUE`;
- `current_time TEXT NOT NULL`;
- `next_turn_number INTEGER NOT NULL` con valore minimo 1;
- `created_at TEXT NOT NULL`;
- `updated_at TEXT NOT NULL`;
- `UNIQUE(session_id, world_id)`;
- FK verso `worlds` con `ON DELETE RESTRICT`.

Non implementare ancora slot di salvataggio paralleli o ramificazioni.

### `narrative_turns`

- `turn_id TEXT PRIMARY KEY`;
- `session_id TEXT NOT NULL`;
- `world_id TEXT NOT NULL`;
- `sequence_number INTEGER NOT NULL`;
- `user_input TEXT NOT NULL`;
- `narrative TEXT NOT NULL`;
- `elapsed_minutes INTEGER NOT NULL` tra 0 e 10.080;
- `world_time_before TEXT NOT NULL`;
- `world_time_after TEXT NOT NULL`;
- `prompt_text TEXT NOT NULL`;
- `raw_model_output TEXT NOT NULL`;
- `created_at TEXT NOT NULL`;
- `UNIQUE(session_id, sequence_number)`;
- `UNIQUE(turn_id, world_id)`;
- FK composita `(session_id, world_id)` verso la sessione.

### `narrative_turn_events`

- `turn_id`, `event_id`, `world_id`, `operation_index`;
- PK `(turn_id, event_id)`;
- `UNIQUE(turn_id, operation_index)`;
- FK verso `narrative_turns` ed `events`.

### `narrative_turn_memories`

- `turn_id`, `memory_id`, `world_id`, `memory_index`;
- PK `(turn_id, memory_id)`;
- `UNIQUE(turn_id, memory_index)`;
- FK verso `narrative_turns` e `memories`.

Aggiungere indici per:

- turni della sessione in ordine;
- eventi per turno;
- memorie per turno.

I turni e le tabelle di collegamento sono append-only: bloccare UPDATE e DELETE
con trigger, come già avviene per eventi e memorie. La sessione può aggiornare
soltanto tempo corrente, prossimo numero e `updated_at`; identità, mondo e data
di creazione non devono poter cambiare.

La migrazione deve preservare integralmente tutti i database schema 5.

## 2. Sessione e tempo narrativo

Aggiungere modelli tipizzati e API applicative per:

- ottenere la sessione del mondo;
- crearla quando manca;
- leggere i turni in ordine;
- leggere gli ultimi turni senza cancellare quelli vecchi.

Usare `crea_id_sessione(world_id)` della fondazione. Esiste una sola sessione per
mondo.

Per il tempo iniziale:

1. leggere dal `world.json` archiviato il campo opzionale `narrative_start_at`;
2. se presente, richiedere ISO-8601 con fuso orario;
3. se assente, usare l'UTC corrente al momento della creazione della sessione.

Una volta creata, la sessione non deve cambiare ancoraggio.

Ogni turno parte da `session.current_time` e termina dopo `elapsed_minutes`.
Il riferimento temporale passato a `ServizioValidazione.valida_sequenza` deve
essere il tempo finale del turno, non `datetime.now()`.

Gli eventuali `occurred_at` espliciti devono rientrare tra inizio e fine turno e
restare in ordine. La fondazione esegue questo controllo una seconda volta.

## 3. Collegamento delle memorie a un'operazione

Estendere in modo retrocompatibile il contratto delle memorie candidate con:

`operation_index: int | None = None`

Aggiornare:

- `MemoriaCandidata`;
- schema mostrato nel prompt;
- parser rigoroso;
- test della fondazione Task 007 interessati.

L'indice è zero-based e deve riferirsi a una voce esistente di `operations`.
Passare alla fondazione:

```python
memory_operation_indices=tuple(
    memoria.operation_index for memoria in proposta.memories
)
```

Regole minime:

- `direct_observation` richiede `operation_index` e un evento con luogo;
- il personaggio che ricorda deve trovarsi nel luogo dell'evento nella proiezione
  corrispondente;
- `told_by_character` richiede `source_entity_id` riferito a un personaggio;
- ascoltatore e fonte devono essere personaggi distinti;
- `inference` può usare solo memorie sorgente dello stesso personaggio;
- `imported_background` non può essere creato dall'LLM;
- ogni entità collegata deve esistere;
- non creare automaticamente una memoria per tutti i presenti.

Gli errori devono impedire l'intero turno.

## 4. Applicazione atomica

Aggiungere in `ArchivioSQLite` una sola API pubblica, con nome chiaro, che riceva
un `PianoPersistenzaTurno` e applichi tutto con `BEGIN IMMEDIATE` o una singola
transazione equivalente.

Non chiamare dentro questa operazione i metodi pubblici esistenti che aprono
transazioni separate.

All'interno della stessa transazione:

1. verificare sessione, `current_time` e `next_turn_number` attesi;
2. inserire il record del turno;
3. inserire ogni evento con `_inserisci_evento`;
4. aggiornare gli stati con controllo `expected_version` e impostare
   `final_version`;
5. inserire le memorie e associazioni/fonti;
6. inserire i collegamenti turno-eventi e turno-memorie;
7. aggiornare tempo e prossimo numero della sessione.

Usare il `created_at` del turno per `created_at` degli eventi e delle memorie.
Usare `learned_at` e `occurred_at` forniti dal piano.

Se qualsiasi INSERT, FK, trigger, versione ottimistica o memoria fallisce:

- rollback completo;
- nessun turno;
- nessun evento;
- nessuna memoria;
- nessuna modifica allo stato;
- nessun avanzamento del tempo.

Tradurre gli errori in un messaggio italiano dedicato, senza mostrare SQL.

## 5. Servizio narrativo

Il flusso applicativo deve diventare:

1. carica o crea sessione;
2. prepara prompt con stato, memorie e cronologia persistente recente;
3. invia a Ollama sul worker;
4. nel thread principale esegue parser;
5. valida operazioni e memorie;
6. costruisce `PianoPersistenzaTurno`;
7. applica il piano atomicamente;
8. ricarica stato e conversazione;
9. mostra il turno solo dopo commit riuscito.

Non mantenere due fonti di verità tra `_cronologia_narrativa` e SQLite.
La cronologia usata dal prompt deve provenire dai turni persistiti.

Per il prompt caricare al massimo gli ultimi 20 messaggi, ma conservare nel DB
tutti i turni senza limite applicativo. “Non caricato nel prompt” non significa
“cancellato”.

Il prompt del turno deve includere il tempo narrativo corrente in italiano.

## 6. Scheda Gioca

Sostituire l'avviso preview-only con:

`Partita locale persistente`

Comportamento minimo:

- all'apertura del mondo caricare la sessione e la conversazione esistente;
- mostrare almeno gli ultimi 100 turni nella vista, senza cancellare i precedenti;
- dopo il commit aggiungere il nuovo turno e svuotare l'input;
- dopo il commit aggiornare schede Stato, Eventi e Memorie;
- se il commit fallisce, non aggiungere la narrazione alla conversazione;
- **Mostra prompt** continua a mostrare quello realmente inviato;
- riaprendo l'app, la conversazione e il tempo devono tornare disponibili;
- durante una richiesta disabilitare le azioni che potrebbero cambiare il mondo;
- nessun JSON o UUID nella conversazione normale.

Non aggiungere ancora editor di salvataggi, rewind, cancellazione turni o branching.

## 7. Memoria a lungo termine

Questo task deve garantire l'archivio persistente, non ancora la ricerca semantica.

Persistono senza scadenza automatica:

- tutti i turni;
- eventi;
- persone, luoghi e oggetti nello stato;
- memorie candidate accettate;
- prompt e output grezzo per audit locale.

Non implementare ancora:

- embeddings;
- database vettoriale;
- riassunti automatici;
- dimenticanza o decadimento;
- compressione delle scene.

Queste funzioni useranno in seguito l'archivio costruito ora e non dovranno
cancellare gli originali.

## 8. Test obbligatori

Mantenere tutti i 238 test esistenti e i 14 test della fondazione Task 008.

Aggiungere test mirati per almeno:

1. migrazione schema 5 → 6 senza perdita di dati;
2. creazione e riuso della singola sessione per mondo;
3. `narrative_start_at` valido e fallback UTC;
4. turno senza operazioni che salva testo e avanza il tempo;
5. spostamento che salva turno, evento e stato;
6. due operazioni sulla stessa entità con versione finale corretta;
7. memoria candidata collegata al relativo evento;
8. memoria con riferimento invalido che causa rollback totale;
9. errore inserito intenzionalmente a metà transazione che lascia tutto invariato;
10. versione stato obsoleta che causa rollback totale;
11. sessione con tempo o numero turno obsoleto che causa rollback;
12. riavvio del servizio che ricarica conversazione e tempo;
13. cronologia prompt limitata agli ultimi 20 messaggi ma archivio completo;
14. testo UTF-8 adulto/controverso conservato senza blacklist o trasformazioni;
15. output/parser/validazione falliti senza alcuna scrittura;
16. nessuna rete reale nei test;
17. GUI italiana con nuova dicitura persistente;
18. schema finale uguale a 6.

Non testare tramite pixel o screenshot.

## 9. Documentazione

Aggiornare soltanto il necessario:

- `README.md`;
- `docs/ARCHITECTURE.md`;
- `docs/NARRATIVE_ENGINE.md`;
- `docs/TEST_PLAN.md`;
- nuovo `docs/TASK_008_STATUS.md`.

Documentare esplicitamente:

- una cronologia per mondo;
- persistenza completa e locale;
- atomicità;
- nessuna moderazione narrativa aggiunta dal motore;
- nessuna ricerca semantica o simulazione fuori scena ancora attiva.

## 10. Verifica manuale

Con Ollama disponibile e Haria importata:

1. inviare un turno con almeno un evento o cambiamento di stato;
2. verificare narrazione, stato, evento e memoria;
3. chiudere completamente l'app;
4. riaprirla;
5. verificare conversazione, stato e tempo;
6. inviare un secondo turno;
7. verificare numerazione e continuità.

Se Ollama non è disponibile, non dichiarare il collaudo end-to-end. Eseguire i
test con trasporto simulato e dichiarare il blocco.

## Fuori ambito assoluto

- simulazione fuori scena;
- eventi autonomi non collegati a un turno;
- ricerca semantica o embeddings;
- riassunti e dimenticanza;
- più slot o linee temporali parallele;
- rewind e cancellazione della storia;
- streaming token;
- retry automatico LLM;
- provider cloud;
- moderazione o censura narrativa;
- redesign generale;
- Task 009.

## Git

Prima di lavorare:

```powershell
git branch --show-current
git status --short
git log -3 --oneline
```

Al termine:

- working tree pulito;
- pochi commit chiari;
- push su `feature/task-008-persistent-turns`;
- crea una sola PR draft verso `main`;
- titolo: `feat: persist narrative turns atomically`;
- nessun merge;
- non iniziare Task 009.

## Resoconto finale

Comunicare soltanto:

- branch, head e commit;
- file modificati;
- schema e migrazione;
- test fondazione, Task 008 e suite completa;
- risultato `python -m haria_engine --check`;
- esito collaudo reale o blocco Ollama;
- prova del rollback atomico;
- stato PR draft;
- conferma nessun merge e nessun Task 009.
