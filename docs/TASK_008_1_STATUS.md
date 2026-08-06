# Stato Task 008.1

## Risultato

Il contratto dell'output narrativo è ora un JSON Schema immutabile condiviso da
prompt e provider Ollama. Le cinque operazioni e le quattro forme generabili di
memoria sono separate tramite varianti esplicite e rifiutano proprietà estranee.

La richiesta narrativa a `/api/chat` usa `stream: false` e passa lo schema nel
campo nativo `format`. La prova tecnica del modello continua a usare il payload
semplice senza schema narrativo.

## Singola correzione

Il parser distingue con eccezioni tipizzate:

- output non riparabile: JSON invalido, vuoto, troppo grande o non-oggetto;
- oggetto JSON strutturalmente non conforme.

Soltanto il secondo caso avvia una richiesta aggiuntiva. La richiesta conserva i
messaggi originali, aggiunge la prima risposta come `assistant` e una istruzione
di correzione con l'errore preciso. Il flag applicativo e il nome distinto
dell'operazione asincrona impediscono un terzo tentativo.

Nessun errore di rete, timeout, HTTP, validazione semantica, riferimento, stato o
persistenza attiva la correzione.

## Atomicità e audit

Il primo output scartato non produce scritture. Solo dopo il parsing, la
validazione e il piano finali viene invocata la transazione Task 008. Se la
correzione riesce, `prompt_text` conserva la richiesta finale completa e
`raw_model_output` conserva esclusivamente la seconda risposta accettata.

## Test automatici

- test Task 008.1: 14/14;
- regressione mirata Task 007 + Task 008 + fondazione Task 008: 57/57;
- suite completa: 295/295;
- trasporti Ollama simulati, nessun servizio reale richiesto.

Il controllo con un database temporaneo nuovo è riuscito. Il comando senza
`--database` non è invece riuscito perché il database predefinito locale
preesistente non completa la migrazione dallo schema 4 allo schema 5. Il task
non modifica né ripara quel database e non introduce migrazioni.

## Limiti

Non è stato eseguito un nuovo collaudo end-to-end contro Ollama reale: questa
sessione non disponeva della conferma di un'istanza e del modello locale attivi e
non modifica o installa servizi esterni. Il caso reale che ha motivato il task è
riprodotto byte per byte nella struttura dei campi errati dai test automatici.
Schema SQLite, timeout predefinito, moderazione narrativa e architettura dei
turni restano invariati.
