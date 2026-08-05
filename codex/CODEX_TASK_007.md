# Haria Engine â€” Task 007: prima alpha narrativa giocabile

## Punto di partenza giÃ  preparato

Questo task deve partire da `main` contenente il merge del Task 006:

`26e555e7679ec19a246926e8a2493e5068e202b2`

Il branch richiesto Ã¨:

`feature/task-007-narrative-alpha`

La fondazione fornita aggiunge giÃ :

- `haria_engine/narrative_models.py`;
- `haria_engine/narrative_parser.py`;
- `haria_engine/narrative_prompt.py`;
- `tests/test_task_007_foundation.py`;
- questo documento.

La fondazione contiene modelli immutabili, parser JSON rigoroso, prompt deterministico
e 12 test puri giÃ  verificati. Non riscriverla e non cambiarne il contratto salvo
errore concreto dimostrato da un test.

## Obiettivo del task

Creare la prima alpha realmente provabile di Haria:

1. l'utente seleziona o importa un mondo;
2. apre la scheda **Gioca**;
3. scrive un'azione o un messaggio per il proprio personaggio;
4. il programma costruisce e mostra il prompt effettivo;
5. Ollama restituisce l'output JSON strutturato;
6. il parser giÃ  fornito lo converte in modelli tipizzati;
7. le operazioni proposte vengono validate in dry-run;
8. se tutto Ã¨ valido, la narrazione appare nella conversazione.

Questa alpha Ã¨ intenzionalmente **solo anteprima**: non applica ancora operazioni,
tempo o memorie al database. La conversazione resta disponibile durante la sessione
dell'app, ma non viene ancora salvata dopo la chiusura.

## Principio di costo e ambito

Applica la modifica piÃ¹ piccola possibile. Riusa provider, coordinatore asincrono,
servizi e widget esistenti.

Non svolgere audit generici, refactoring estesi, redesign della GUI o lavoro
preparatorio per funzionalitÃ  future.

## 1. Provider Ollama

Estendi l'interfaccia esistente senza duplicare il trasporto HTTP.

Aggiungi a `ProviderLLM`, `OllamaProvider` e `ServizioAI` un'operazione narrativa
che accetta una tupla di `MessaggioChat` e restituisce `RispostaTestuale`.

Requisiti:

- usa `POST /api/chat`;
- `stream` deve essere `false`;
- usa il modello giÃ  salvato nella configurazione;
- inoltra esattamente ruolo e contenuto dei messaggi ricevuti;
- non eseguire `GET /api/tags` prima di ogni turno;
- riusa la validazione giÃ  esistente della risposta assistant;
- nessun accesso a SQLite o Tkinter dal provider;
- nessuna rete nei test.

Non rimuovere nÃ© cambiare il comportamento della prova testuale giÃ  esistente.

## 2. Contesto del turno

Aggiungi un piccolo servizio puro o metodi tipizzati nel servizio applicativo.
Non eseguire SQL dalla GUI.

Il contesto passato a `ContestoTurnoNarrativo` deve includere:

- titolo del mondo;
- nome del personaggio giocante;
- input corrente dell'utente;
- scenario corrente;
- `rules.md`, `style.md` e nota autore quando presenti;
- stato corrente delle entitÃ  in righe deterministiche e leggibili;
- personaggi con ID, nome, profilo canonico e stato corrente;
- memorie correnti utili giÃ  disponibili nell'archivio;
- cronologia narrativa recente della sessione.

Usa soltanto dati giÃ  presenti. Non inventare lore o stato.

### Personaggio giocante

Leggi `player_character_id` dal `world.json` archiviato e risolvilo contro le
entitÃ  del mondo. Se il campo manca o non identifica un personaggio, mostra un
errore italiano chiaro e non inviare la richiesta.

Per Haria deve risolversi in Luca.

### Limiti semplici

Per evitare prompt incontrollati:

- massimo 20 elementi di cronologia recente;
- massimo 100 memorie correnti;
- nessuna ricerca semantica in questo task;
- nessun riassunto generato da un secondo passaggio LLM;
- ordine deterministico per ID/nome/tempo.

Se una sezione non esiste, passa stringa vuota o tupla vuota come previsto dai
modelli giÃ  forniti.

## 3. Validazione dry-run

Dopo `parse_output_narrativo`:

- usa `ServizioValidazione.valida_sequenza`;
- il riferimento temporale deve essere un `datetime` UTC consapevole;
- se esistono errori, non aggiungere la risposta assistant alla cronologia;
- mostra un messaggio italiano leggibile con i primi problemi;
- non applicare nessuna proposta;
- non creare eventi;
- non creare memorie;
- non modificare lo scenario;
- non avanzare alcun orologio persistente.

Un output con `operations: []` Ã¨ valido e deve essere mostrato normalmente.

## 4. Scheda Gioca

Aggiungi **Gioca** come prima scheda principale, senza ridisegnare le altre.

Elementi minimi:

- conversazione in sola lettura;
- campo di testo multilinea per l'utente;
- pulsante **Invia**;
- pulsante **Mostra prompt**;
- indicazione visibile: `Anteprima narrativa: nessuna modifica viene ancora salvata`;
- stato di attivitÃ  durante la richiesta;
- errori in italiano.

Comportamento:

- disabilita **Invia** durante una richiesta;
- non permettere invio senza mondo, modello Ollama o testo utente;
- usa il coordinatore asincrono esistente;
- SQLite e Tkinter restano nel thread principale;
- risultati tardivi dopo la chiusura non devono aggiornare widget distrutti;
- al successo aggiungi input utente e sola `narrative` alla conversazione;
- conserva in memoria al massimo 20 messaggi recenti;
- **Mostra prompt** visualizza esattamente `formatta_prompt_visibile(...)`;
- cambiando mondo, azzera conversazione, prompt e richiesta narrativa corrente.

Non mostrare automaticamente JSON, operazioni o UUID nella conversazione.
Per il debug, gli errori strutturati possono restare nei log.

## 5. Nessuna persistenza narrativa in questo task

Non aggiungere tabelle SQLite per:

- sessioni;
- messaggi;
- scene;
- orologio narrativo;
- proposte LLM.

Non applicare operazioni o memorie. Questo sarÃ  il task successivo, dopo la prova
manuale dell'alpha.

Lo schema deve restare **5**.

## 6. Test obbligatori

Mantieni i 212 test esistenti e i 12 test della fondazione.

Aggiungi soltanto test mirati per:

1. payload `/api/chat` con messaggi esatti e `stream: false`;
2. nessuna chiamata preventiva a `/api/tags`;
3. risposta assistant valida e principali errori giÃ  supportati;
4. costruzione del contesto dal mondo senza SQL nella GUI;
5. risoluzione del personaggio giocante;
6. prompt visibile uguale al prompt inviato;
7. output valido con operazioni vuote;
8. output con proposta non valida rifiutato senza modificare il database;
9. successo narrativo senza modificare database, eventi, memorie o schema;
10. coordinatore asincrono e chiusura sicura;
11. testi italiani essenziali della scheda Gioca;
12. nessuna rete reale.

Non creare test fragili basati su coordinate pixel o screenshot.

## 7. Verifica manuale minima

Con il pacchetto locale `local_worlds/haria`:

- avvia l'app;
- importa o seleziona Haria;
- configura un modello Ollama disponibile;
- apri **Gioca**;
- invia un messaggio semplice;
- verifica che la risposta narrativa appaia;
- verifica **Mostra prompt**;
- verifica che, riaprendo stato/eventi/memorie, nulla sia cambiato.

Se Ollama o il modello non sono disponibili, non inventare il collaudo reale:
esegui tutti i test simulati e segnala il blocco.

## 8. Documentazione minima

Aggiorna soltanto:

- `README.md`;
- `docs/ARCHITECTURE.md`;
- `docs/NARRATIVE_ENGINE.md`;
- `docs/TEST_PLAN.md`;
- nuovo `docs/TASK_007_STATUS.md`.

Documenta chiaramente che Ã¨ un'alpha preview-only e che nulla viene persistito.

## 9. Git

Prima di lavorare:

```powershell
git branch --show-current
git status --short
git log -3 --oneline
```

Non lavorare su `main`.

Al termine:

- working tree pulito;
- commit chiari e pochi;
- push sul branch `feature/task-007-narrative-alpha`;
- tenta una sola PR draft verso `main`;
- titolo PR: `feat: add narrative turn alpha`;
- nessun merge;
- non iniziare Task 008.

## Fuori ambito assoluto

- applicazione delle operazioni;
- salvataggio conversazioni o scene;
- avanzamento persistente del tempo;
- simulazione fuori scena;
- eventi autonomi;
- ricerca semantica;
- streaming token;
- retry automatici dell'LLM;
- piÃ¹ provider;
- immagini nella chat;
- redesign;
- voce;
- multiplayer;
- Task 008.

## Resoconto finale richiesto

Comunica soltanto:

- branch e head;
- commit creati;
- file modificati;
- test fondazione, Task 007 e suite completa;
- risultato `python -m haria_engine --check`;
- esito del collaudo manuale o blocco Ollama;
- conferma che schema e database non vengono modificati dai turni;
- stato PR draft;
- conferma nessun merge e nessun Task 008.