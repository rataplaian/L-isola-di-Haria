# AGENTS.md — Regole vincolanti per Codex

## Ruolo
Codex è lo sviluppatore operativo del progetto. Non deve ridefinire autonomamente il prodotto.

## Regole obbligatorie
1. Leggere sempre `PRODUCT_SPEC.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`, `EDITOR_REQUIREMENTS.md` e `TEST_PLAN.md` prima di modifiche strutturali.
2. Non inventare lore, personaggi, regole o limiti editoriali.
3. Non hardcodare contenuti narrativi, limiti NSFW, tono, violenza o restrizioni editoriali nel codice.
4. Tutte le impostazioni narrative devono essere visibili e modificabili dall'utente in italiano.
5. JSON, database e schemi tecnici devono restare dietro le quinte salvo modalità avanzata volontaria.
6. Separare sempre:
   - canone;
   - stato corrente;
   - eventi;
   - ricordi soggettivi;
   - configurazione narrativa.
7. Non modificare o cancellare file sorgente della Bibbia importata.
8. Qualunque migrazione dati deve essere reversibile e testata.
9. Non lasciare mock, TODO critici o funzioni finte senza dichiararlo.
10. Ogni task deve includere test automatici.
11. Non fare refactoring non richiesti.
12. Non cambiare dipendenze principali senza motivazione documentata.
13. Dichiarare apertamente:
   - cosa è stato completato;
   - cosa non è stato completato;
   - quali test sono stati eseguiti;
   - quali rischi restano.
14. Preferire codice semplice, leggibile, tipizzato e modulare.
15. Il branch `main` non deve ricevere lavoro sperimentale direttamente.

## Priorità
Correttezza dei dati > coerenza narrativa > facilità d'uso > prestazioni > estetica.

## Divieto fondamentale
L'LLM non deve avere accesso libero alla riscrittura diretta del database o della Bibbia.
Può soltanto proporre operazioni strutturate validate dal motore.
