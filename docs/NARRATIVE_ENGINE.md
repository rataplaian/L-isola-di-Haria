# Motore narrativo

## Separazione del controllo
L'utente controlla il personaggio giocante.
Il motore controlla mondo, NPC, eventi esterni e conseguenze.

## Haria
Per il primo mondo:
- l'utente controlla Luca;
- il motore non decide pensieri, consenso, parole volontarie o azioni volontarie di Luca;
- le NPC sono autonome;
- nessun personaggio prova automaticamente amore, fiducia, desiderio, obbedienza o perdono;
- gli eventi possono accadere fuori scena.

## Prompt effettivo
L'interfaccia deve permettere di vedere il prompt realmente inviato al modello.

## Output strutturato
Il modello deve produrre:
- testo narrativo;
- operazioni proposte;
- eventi;
- tempo trascorso;
- cambiamenti di stato;
- memorie candidate.

## Validazione e persistenza
Le operazioni vengono applicate soltanto dopo parsing rigoroso, validazione e
costruzione del piano immutabile. Nel Task 008 una singola transazione salva
turno, eventi, stato, memorie e tempo; un errore annulla ogni parte.

## Recupero memoria
Usare:
- ricerca esatta;
- filtri temporali;
- filtri per personaggio;
- filtri per luogo;
- priorità alla fonte canonica e allo stato corrente.

La ricerca semantica non è ancora implementata.

## Anteprima Task 007

Il contesto usa scenario e impostazioni correnti, regole, stile, eventuale nota
dell'autore, stato deterministico, profili dei personaggi, fino a cento memorie
correnti e gli ultimi venti messaggi della sessione. Il personaggio giocante
viene risolto da `player_character_id` nella fotografia archiviata di
`world.json`; il valore deve indicare un personaggio esistente.

## Partita persistente Task 008

Ogni mondo possiede una sola sessione con tempo corrente e numerazione
progressiva. Il prompt usa gli ultimi venti messaggi persistiti; tutti i turni,
prompt e output grezzi restano nell'archivio locale senza scadenza automatica.
La GUI mostra il turno solo dopo il commit e ricarica conversazione e tempo alla
riapertura.

Il motore non aggiunge moderazione, censura, blacklist o trasformazioni
tematiche. Restano obbligatori i controlli tecnici di coerenza, i vincoli
canonici e l'autonomia dei personaggi. Simulazione fuori scena, embeddings,
riassunti, dimenticanza, slot paralleli e rewind restano fuori ambito.
