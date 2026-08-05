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

## Validazione
Le operazioni vengono applicate soltanto dopo validazione.

Nel Task 007 le operazioni vengono esclusivamente simulate dal validatore.
Anche una proposta valida non viene applicata: eventi, stato, memorie, tempo e
conversazione persistente restano invariati.

## Recupero memoria
Usare:
- ricerca esatta;
- filtri temporali;
- filtri per personaggio;
- filtri per luogo;
- ricerca semantica;
- priorità alla fonte canonica e allo stato corrente.

## Anteprima Task 007

Il contesto usa scenario e impostazioni correnti, regole, stile, eventuale nota
dell'autore, stato deterministico, profili dei personaggi, fino a cento memorie
correnti e gli ultimi venti messaggi della sessione. Il personaggio giocante
viene risolto da `player_character_id` nella fotografia archiviata di
`world.json`; il valore deve indicare un personaggio esistente.

La ricerca semantica, il secondo passaggio LLM, l'avanzamento del tempo,
l'applicazione atomica e il salvataggio della conversazione restano obiettivi
futuri e non fanno parte di questa anteprima.
