# Stato Task 007

## Risultato

Implementata l'anteprima alpha del turno narrativo tramite Ollama locale. La
scheda italiana **Gioca** raccoglie l'azione dell'utente, permette di vedere il
prompt effettivo, genera la proposta sul worker daemon e mostra la prosa
soltanto dopo parsing rigoroso e validazione dry-run.

## Componenti

- `narrative_models.py`, `narrative_parser.py` e `narrative_prompt.py`:
  fondazione immutabile, parser JSON rigoroso e due messaggi deterministici;
- `narrative_service.py`: contesto applicativo, risoluzione del personaggio
  giocante e validazione della proposta senza scritture;
- `ollama_provider.py` e `llm_service.py`: richiesta narrativa `/api/chat`
  sostituibile e testabile, senza interrogare `/api/tags`;
- `app.py`: prima scheda **Gioca**, cronologia volatile di venti messaggi,
  prompt visibile e gestione sicura dei risultati asincroni.

## Invarianti verificate

- schema SQLite fermo alla versione 5;
- nessuna nuova tabella;
- nessuna applicazione di operazioni, eventi, stato o memorie;
- nessun avanzamento temporale;
- nessun salvataggio della conversazione;
- nessun accesso SQLite o Tkinter dal worker;
- nessuna rete reale nei test automatici.

## Verifiche automatiche

- fondazione Task 007: 12/12;
- Task 007 complessivo: 25/25;
- suite completa: 237/237;
- `python -m haria_engine --check`: riuscito su database temporaneo scrivibile.

## Limiti residui dichiarati

Questa versione è un'anteprima non persistente. Applicazione atomica delle
proposte, memorie candidate, avanzamento del tempo, ricerca semantica e
salvataggio della conversazione sono fuori dal Task 007. Il collaudo contro un
modello Ollama reale dipende dalla disponibilità locale del servizio e di un
modello configurato.

Il collaudo visivo con `local_worlds/haria` ha verificato la prima scheda
**Gioca**, Luca come personaggio controllato, il testo di anteprima e il prompt
effettivo leggibile. La generazione end-to-end reale non è stata eseguita:
Ollama non risultava raggiungibile su `localhost:11434`.
