# Piano di test

## Test 1 — Penna e chiavi
Stato iniziale:
- penna sulla scrivania;
- chiavi sul gancio;
- Élise presente;
- Akari assente.

Azione:
- Luca prende la penna.

Risultati:
- penna posseduta da Luca;
- chiavi ancora sul gancio;
- Élise sa dell'azione;
- Akari non acquisisce automaticamente la conoscenza;
- dopo riavvio lo stato resta invariato.

## Test 2 — Distruzione del villaggio
Evento:
- un meteorite distrugge il villaggio.

Risultati:
- villaggio non cancellato;
- stato corrente: distrutto;
- mappa storica preservata;
- accessibilità aggiornata;
- persone valutate individualmente;
- morti e dispersi distinti;
- ricordi preesistenti preservati.

## Test 3 — Modifica manuale scenario
Azione:
- l'utente modifica lo scenario in italiano.

Risultati:
- anteprima disponibile;
- backup creato;
- modifica salvata;
- cronologia versioni aggiornata;
- JSON interno aggiornato automaticamente.

## Test 4 — Controllo di Luca
Il modello non deve:
- scegliere pensieri di Luca;
- farlo parlare senza input;
- stabilire consenso;
- imporre emozioni accettate.

## Test 5 — Persistenza
Chiudere e riaprire il programma.
Tutti gli stati devono essere identici.

## Test 6 — Cambio LLM
Cambiare provider o modello.
La campagna non deve perdere dati.

## Test 7 — Validazione deterministica

Controllare un mondo integro e proposte valide o incoerenti.

Risultati:
- problemi ordinati per severità, ambito e riferimenti stabili;
- riferimenti, posizioni, possessori, tempi e conoscenze incoerenti rilevati;
- una proposta valida produce soltanto una nuova fotografia in memoria;
- una proposta non valida non produce una proiezione;
- database, schema, eventi, stato, memorie e configurazione AI invariati;
- nessuna richiesta HTTP o connessione a Ollama.

## Test 8 — Pacchetto completo

Importare la stessa fixture tecnica da cartella e ZIP.

Risultati:
- identificatori, documenti, entità e media equivalenti;
- manifest e hash validati prima delle scritture;
- archivi ostili, link, duplicati e limiti rifiutati in italiano;
- migrazione 4→5 e importazione atomiche con rollback completo;
- export e reimport conservano struttura, ID, file sconosciuti ammessi e byte media;
- `sample_world/` resta importabile;
- nessuna rete o modifica dei sorgenti;
- GUI italiana senza JSON o identificatori tecnici.

La suite Task 001–006 contiene **206 test automatici** e usa soltanto database,
cartelle, ZIP e media tecnici temporanei. I materiali reali locali non sono
fixture automatiche.
