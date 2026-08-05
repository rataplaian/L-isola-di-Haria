# Stato Codex Task 005

## Implementato

- modelli immutabili e tipizzati per fotografia, proposte, problemi ed esiti;
- fotografia del mondo costruita soltanto tramite letture tipizzate
  dell'archivio;
- audit di integrità referenziale e coerenza spaziale, temporale,
  inventariale ed epistemica;
- ordinamento deterministico dei problemi;
- validazione di spostamento, trasferimento, cambio di stato, evento
  descrittivo e acquisizione epistemica;
- dry-run puro in memoria per proposta singola e sequenze ordinate;
- proiezione degli oggetti trasportati insieme al personaggio;
- verifica delle memorie correnti dell'attore senza dedurre conoscenze dal
  testo libero;
- servizio applicativo indipendente da Tkinter, SQLite diretto e provider AI;
- scheda italiana **Validazione mondo** con esecuzione manuale e risultati in
  sola lettura;
- errori italiani con cause tecniche conservate per la diagnostica interna.

## Persistenza e sicurezza

Il Task 005 non introduce migrazioni o nuove tabelle: lo schema resta alla
versione 4. Audit e dry-run non chiamano API applicative di scrittura, non
creano eventi, memorie o versioni e non modificano la configurazione AI. La
fotografia usata dalle regole è un valore immutabile separato dal database.

## Verifica

```powershell
python -m unittest discover -s tests -v
python -m haria_engine --check --database C:\percorso\temporaneo\haria.sqlite3
```

La suite comprende **177 test**: 127 test precedenti e 50 test Task 005. Le
prove del validatore includono mondo integro, riferimenti mancanti, luoghi e
possessori incoerenti, accessibilità, tempi, memorie dell'attore, sequenze,
immutabilità, assenza di scritture e assenza di rete.

## Escluso perché fuori ambito

- applicazione persistente delle proposte validate;
- generazione narrativa, prompt o interpretazione di risposte LLM;
- correzione automatica delle incoerenze;
- snapshot storici o osservazioni retroattive;
- modifica delle regole dall'interfaccia;
- importazione della Bibbia completa;
- Task 006.

## Limiti e rischi residui

- La fotografia rappresenta lo stato letto al momento dell'audit; non è uno
  snapshot storico persistente.
- La validazione epistemica usa relazioni strutturate e memorie correnti, non
  interpreta semanticamente il testo libero.
- Il dry-run dimostra la coerenza della proiezione ma, per scelta di ambito,
  non offre ancora un comando per applicarla al database.
