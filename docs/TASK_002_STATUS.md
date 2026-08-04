# Stato Codex Task 002

## Implementato

- migrazione SQLite transazionale e idempotente dallo schema 1 allo schema 2;
- ricostruzione di canone e stato dai soli BLOB archiviati in `source_files`;
- rollback completo con `user_version` invariato se gli archivi sono incompleti
  o non validi;
- tabelle `world_entities`, `entity_state`, `events` ed `event_entities`;
- personaggi, luoghi e oggetti importati con ID stabili;
- separazione tra dati canonici immutabili e stato corrente, con
  `entity_state.current_status` esplicito;
- operazioni tipizzate `sposta_entita`, `trasferisci_oggetto`, `cambia_stato` e
  `registra_evento_descrittivo`;
- validazioni di mondo, entità, tipo, posizione, possessore e coerenza del
  trasferimento;
- transazione unica per inserimento evento, associazioni alle entità e
  aggiornamenti di stato;
- rollback con evento, associazioni e stato invariati in caso di errore;
- eventi append-only senza API di modifica o cancellazione;
- associazioni automatiche `actor`, `target`, `location` e `affected` che
  rendono completa la cronologia di ogni entità senza duplicare eventi;
- trigger SQLite che rifiutano `UPDATE` e `DELETE` su `events` ed
  `event_entities`;
- scheda italiana **Stato del mondo** con elenco entità, stato leggibile,
  cronologia e trasferimento manuale di oggetti;
- messaggi di migrazione leggibili in italiano in GUI e modalità `--check`;
- conservazione integrale dei file sorgente.

## Caso di collaudo

- Akari parte nell'assemblea come nel canone importato;
- `sposta_entita` la porta nell'infermeria e crea un solo evento;
- `trasferisci_oggetto` assegna la penna blu a Luca e crea un solo evento;
- un secondo trasferimento identico viene rifiutato senza evento duplicato;
- le chiavi restano nell'infermeria, non possedute, senza variazioni o eventi;
- stato ed eventi persistono dopo la riapertura del servizio.

## Verifica

```powershell
python -m unittest discover -s tests -v
python -m haria_engine --check
```

Esito suite: **55 test superati su 55**.

Sono verificati anche migrazione riuscita, archivi mancanti o non validi,
riapertura idempotente, immutabilità del canone, persistenza di
`current_status`, oggetti trasportati con il personaggio, identità condivisa
degli eventi, trigger append-only, rollback evento+associazioni+stato,
validazioni italiane e assenza di dati tecnici nei testi GUI.

## Escluso perché fuori ambito

- memorie soggettive e tabella `memories`;
- LLM, Ollama e generazione narrativa;
- simulazione fuori scena;
- Haria Bible completa;
- relazioni sociali avanzate, combattimento e mappe grafiche.

## Limiti e rischi residui

- Un database schema 1 privo di una fotografia valida di `characters.json`,
  `locations.json` o `items.json` non viene migrato: resta integro allo schema 1
  e richiede correzione dei dati archiviati.
- Non è previsto un comando di downgrade dallo schema 2 allo schema 1; la
  migrazione è additiva e protetta da rollback transazionale.
- La GUI Tkinter resta volutamente essenziale e consente manualmente soltanto il
  trasferimento di oggetti; le altre operazioni sono disponibili nel servizio
  applicativo tipizzato.
- La prova grafica è stata eseguita nell'ordine richiesto. `py -3 -m
  haria_engine` non può partire perché il launcher `py` non è installato;
  `python -m haria_engine` richiama soltanto l'alias Microsoft Store e segnala
  che Python non è installato. Il runtime incorporato di Codex non dispone di
  un Tcl utilizzabile. La finestra non ha quindi potuto essere collaudata
  visivamente in questa sessione; l'avvio richiede un Python di sistema con
  Tkinter/Tcl completo, senza cambiamenti allo stack.
