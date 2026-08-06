# Stato Task 008.1–008.3

## Risultato

Il contratto dell'output narrativo è un JSON Schema immutabile completo usato
dal parser, dalla validazione e dai test applicativi. Le cinque operazioni e le
quattro forme generabili di memoria sono separate tramite varianti esplicite e
rifiutano proprietà estranee. Il prompt non ne mantiene una seconda copia:
rimanda allo schema allegato e conserva soltanto le istruzioni narrative e
strutturali essenziali.

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

## Budget del contesto e collaudo reale

`POST /api/show` su Ollama 0.32.6 ha riportato per `qwen3:4b-instruct` un
`qwen3.context_length` pari a 262.144. Il prompt precedente, con lo schema
duplicato nel messaggio di sistema, non ha completato entro 300 secondi nelle
prove a 8.192, 12.288 e 16.384; `/api/ps` ha confermato i tre contesti allocati
e una quota VRAM decrescente di circa 57,8%, 48,5% e 44,3%.

Il prompt conciso ha ridotto il primo input reale da 6.381 a 2.150 token. Il
budget definitivo `NUM_CTX_NARRATIVO_OLLAMA` è 4.096: è il valore minimo che ha
completato primo turno, secondo turno con cronologia e correzione strutturale.
Sul computer di collaudo `/api/ps` ha indicato circa 2,35 GB in VRAM e 1,18 GB
in CPU, equivalenti al 66,5% e 33,5% del modello caricato.

Il primo turno ha prodotto 290 token in 120,6 secondi; il secondo 489 token in
241,4 secondi. Entrambi hanno richiesto una sola chiamata, sono stati persistiti
con sequenza 1 e 2 e hanno creato una memoria ciascuno senza eventi. Dopo la
chiusura completa, input, narrazioni, `prompt_text`, `raw_model_output`, tempo e
conteggi sono stati riletti dallo stesso database; `PRAGMA quick_check` è `ok`.

Una richiesta reale di correzione con una risposta assistant sintetica
incompleta ha usato 3.204 token di prompt e 22 token di output, concludendo in
29,9 secondi. Il parser ha accettato la risposta corretta e il database è
rimasto invariato a due turni, zero eventi e sei memorie.

`options.num_ctx` viene aggiunto esclusivamente alle generazioni narrative e
alla loro eventuale unica correzione. La prova semplice delle Impostazioni AI
non riceve né `format` né il budget narrativo.

## Test automatici

- test Task 008.1–008.3: 20/20;
- regressione mirata Task 007 + Task 008 + fondazione Task 008: 57/57;
- suite completa: 301/301;
- trasporti Ollama simulati, nessun servizio reale richiesto.

Il controllo con un database temporaneo nuovo è riuscito. Il comando senza
`--database` non è invece riuscito perché il database predefinito locale
preesistente non completa la migrazione dallo schema 4 allo schema 5. Il task
non modifica né ripara quel database e non introduce migrazioni.

## Limiti residui

Le durate dipendono dal modello, dalla lunghezza casuale dell'output e dalla
ripartizione tra CPU e GPU. Una prova diagnostica del secondo turno a 4.096 e
una a 8.192 hanno raggiunto il timeout senza scritture; una successiva prova a
4.096 ha completato correttamente in 241,4 secondi. Il budget non garantisce
quindi prestazioni uniformi, ma è il più basso che ha soddisfatto il collaudo
completo senza ridurre l'output con `num_predict` o alterare il modello.

Schema SQLite, timeout, prompt adulto, moderazione e architettura dei turni
restano invariati.
