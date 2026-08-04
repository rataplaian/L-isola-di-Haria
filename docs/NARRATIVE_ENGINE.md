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

## Recupero memoria
Usare:
- ricerca esatta;
- filtri temporali;
- filtri per personaggio;
- filtri per luogo;
- ricerca semantica;
- priorità alla fonte canonica e allo stato corrente.
