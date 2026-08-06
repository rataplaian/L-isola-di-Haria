# Haria Engine Task 008.1 — Output strutturato e singola correzione

## Base e ambito

- base: `main` al commit `18825bb09bb9d73b911bfbe9eafb6d1974b2f8c4`;
- branch: `fix/task-008-1-structured-output`;
- nessuna migrazione SQLite;
- nessun Task 009;
- nessuna modifica a sorgenti canonici, immagini, `sample_world` o pacchetti locali.

## Problema verificato

Un collaudo reale con Ollama 0.32.6 e `qwen3:4b-instruct` ha prodotto un
oggetto JSON leggibile nel quale campi propri delle memorie erano stati inseriti
dentro una operazione. Il parser rigoroso ha correttamente rifiutato la risposta
e il database non è stato modificato. Il contratto inviato al modello deve però
ridurre questa ambiguità senza rendere permissivi parser o validatore.

## Contratto unico

Il motore deve possedere un solo JSON Schema immutabile e tipizzato, condiviso
da prompt e payload Ollama. L'oggetto radice contiene esattamente:

- `narrative`;
- `elapsed_minutes`;
- `operations`;
- `memories`.

Il livello radice e ogni operazione o memoria usano
`additionalProperties: false`. Le operazioni sono cinque varianti `oneOf`
esplicite (`move`, `transfer`, `state_change`, `event`, `epistemic`) aderenti al
parser corrente. `state_change` richiede almeno una modifica effettiva tra
stato, condizione e accessibilità.

Le memorie pubblicizzano soltanto le combinazioni generabili dal modello:

- `direct_observation` → `observed_fact`, con `operation_index`;
- `told_by_character` → `reported_fact`, con `source_entity_id`;
- `inference` → `inference` o `belief`, con fonti non vuote;
- `self_experience` → `observed_fact` o `belief`.

`canonical_knowledge` e `imported_background` restano supportati dai dati
storici ma non vengono presentati come valori generabili.

## Provider Ollama

Soltanto la generazione narrativa invia a `/api/chat`:

```json
{
  "model": "<modello locale configurato>",
  "stream": false,
  "messages": ["<messaggi tipizzati serializzati>"],
  "format": "<copia JSON del contratto immutabile>"
}
```

La prova tecnica nelle Impostazioni AI non riceve `format`. Non vengono aggiunti
tool, opzioni di temperatura, endpoint cloud o dipendenze esterne.

## Correzione automatica

È ammesso un solo tentativo quando il primo risultato è un oggetto JSON
sintatticamente valido ma il parser segnala una violazione strutturale
tipizzata. La seconda richiesta contiene, nell'ordine:

1. gli stessi messaggi originali;
2. la prima risposta come messaggio `assistant`;
3. un messaggio `user` con l'errore preciso e l'ordine di correggere soltanto la
   struttura.

Non si tenta la correzione per JSON invalido o non-oggetto, errori di rete,
timeout, HTTP, ID inesistenti, impossibilità semantiche, violazioni del mondo o
errori SQLite. Una seconda risposta invalida termina il turno senza un terzo
tentativo.

## Persistenza e thread

Il parsing e la validazione avvengono nel thread principale. Le due eventuali
richieste HTTP avvengono sul worker daemon. SQLite e Tkinter restano nel thread
principale. Nessuna transazione inizia prima che la risposta finale sia valida.

Se il secondo tentativo riesce:

- `prompt_text` contiene esattamente i quattro messaggi della richiesta finale;
- `raw_model_output` contiene soltanto la seconda risposta accettata;
- il primo output non crea righe separate e non modifica stato o tempo.

## Criteri di verifica

- schema immutabile e condiviso;
- cinque contratti di operazione espliciti;
- netta separazione fra operazioni e memorie;
- `format` presente soltanto nel turno narrativo;
- una richiesta per output iniziale valido;
- esattamente due richieste per una correzione riuscita o fallita;
- nessun retry per errori non strutturali;
- prompt e output finali persistiti fedelmente;
- rollback completo e regressione Task 001–008;
- `python -m haria_engine --check` riuscito.

## Fuori ambito

- parser permissivo o spostamento automatico di campi;
- più di un tentativo di correzione;
- modifica del timeout predefinito;
- migrazioni SQLite;
- provider cloud, filtri narrativi o Task 009.
