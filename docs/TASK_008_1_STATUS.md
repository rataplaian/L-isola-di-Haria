# Stato Task 008.1–008.2

## Risultato

Il contratto dell'output narrativo è un JSON Schema immutabile completo usato
dal prompt, dal parser e dai test applicativi. Le cinque operazioni e le quattro
forme generabili di memoria sono separate tramite varianti esplicite e
rifiutano proprietà estranee.

La richiesta narrativa a `/api/chat` usa `stream: false` e passa nel campo
nativo `format` una proiezione deterministica del contratto completo. La prova
tecnica del modello continua a usare il payload semplice senza schema narrativo.

## Compatibilità reale della grammatica Ollama

La matrice progressiva A–L eseguita con Ollama 0.32.6 e
`qwen3:4b-instruct` ha verificato realmente JSON mode, oggetto minimo,
`additionalProperties`, array di oggetti, `oneOf`, `const`, `enum`, le due forme
nullable, `allOf` con `anyOf`, le quattro varianti di memoria, i limiti e
`$schema`.

Il primo costrutto incompatibile è `maxLength: 20000`; le prove di soglia hanno
confermato che 1.000, 1.023, 1.024 e 1.025 compilano, mentre 2.000, 4.000 e
20.000 restituiscono HTTP 400 con `failed to parse grammar`. Rimuovere dal
contratto completo soltanto 20.000 non basta; rimuovere dalla sola proiezione
Ollama i `maxLength` superiori a 1.000 rende compilabile lo schema e conserva
tutti gli altri vincoli verificati compatibili.

`schema_output_narrativo_ollama()` deriva ogni volta la proiezione dal contratto
completo e non ne mantiene una copia indipendente. Il parser rigoroso resta
l'autorità finale per limiti, proprietà, ID e coerenza semantica.

Il trasporto HTTP conserva ora il codice di stato e, entro il limite di corpo
già previsto, espone soltanto il messaggio JSON locale sicuro. Corpi non JSON,
eccessivi o non leggibili mantengono il messaggio generico e nessun errore HTTP
attiva la correzione strutturale.

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

- test Task 008.1–008.2: 19/19;
- regressione mirata Task 007 + Task 008 + fondazione Task 008: 57/57;
- suite completa: 300/300;
- trasporti Ollama simulati, nessun servizio reale richiesto.

Il controllo con un database temporaneo nuovo è riuscito. Il comando senza
`--database` non è invece riuscito perché il database predefinito locale
preesistente non completa la migrazione dallo schema 4 allo schema 5. Il task
non modifica né ripara quel database e non introduce migrazioni.

## Collaudo reale e limite residuo

Il nuovo collaudo end-to-end usa Ollama 0.32.6, `qwen3:4b-instruct`, timeout 300,
un database temporaneo nuovo e `sample_world`. La grammatica proiettata supera
la compilazione: non compare più `failed to parse grammar`. La richiesta viene
però respinta prima della generazione perché i 6.381 token complessivi superano
il contesto di 4.096 token disponibile nell'istanza provata.

Il nuovo errore viene mostrato come HTTP 400 con dettaglio locale leggibile. Non
viene avviata la correzione, non viene salvato alcun turno e la fotografia del
database resta identica: zero turni ed eventi, quattro memorie importate,
sessione ancora al turno 1, stato invariato. La gestione della dimensione del
contesto non viene ampliata in Task 008.2. Schema SQLite, timeout, prompt adulto,
moderazione e architettura dei turni restano invariati.
