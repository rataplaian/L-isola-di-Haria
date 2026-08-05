# Stato Task 008

## Risultato

La scheda **Gioca** è una partita locale persistente. Dopo una risposta Ollama
valida, Haria Engine conserva testo, audit, tempo, eventi, stato e memorie in
una sola transazione e ricarica conversazione e tempo alla riapertura.

## Schema 6

- `narrative_sessions`: una sessione e una cronologia per mondo;
- `narrative_turns`: input, narrazione, tempo, prompt e output grezzo;
- `narrative_turn_events`: eventi ordinati del turno;
- `narrative_turn_memories`: memorie ordinate del turno.

Turni e collegamenti sono append-only. La migrazione 5→6 è transazionale e
preserva mondi, versioni, configurazione AI, documenti, media, eventi, stato e
memorie già presenti.

## Atomicità verificata

La singola API di scrittura usa `BEGIN IMMEDIATE`, controlla sessione e versioni
dello stato, inserisce tutte le parti e aggiorna il tempo soltanto alla fine.
Un trigger di test che blocca il collegamento della memoria dopo gli inserimenti
precedenti dimostra il rollback completo: turno, eventi, stato, memorie e tempo
restano invariati.

## Verifiche automatiche

- fondazione Task 008: 14/14;
- Task 008: 23/23;
- suite completa: 275/275;
- nessuna rete reale richiesta dai test.

## Limiti residui

Non sono implementati ricerca semantica, embeddings, simulazione fuori scena,
riassunti, dimenticanza, slot paralleli, rewind o provider cloud. Il motore non
aggiunge moderazione narrativa, blacklist o censura. Il collaudo end-to-end
reale richiede un'istanza Ollama locale e un modello configurato.
