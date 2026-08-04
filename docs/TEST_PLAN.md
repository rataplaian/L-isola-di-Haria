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
