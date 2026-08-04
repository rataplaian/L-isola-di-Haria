# Codex Task 001 — Scheletro applicazione e editor italiano

## Modello consigliato
Codex High.

## Obiettivo
Creare una prima applicazione desktop locale che importi `sample_world/`, mostri lo scenario in italiano e permetta modifica, salvataggio e ripristino delle versioni.

## Vincoli
- Non integrare ancora un LLM.
- Non implementare funzionalità non richieste.
- Non hardcodare Haria nel motore.
- Non esporre JSON all'utente normale.
- Usare SQLite per dati e versioni.
- Interfaccia in italiano.
- Preferire stack semplice e multipiattaforma.
- Proporre lo stack prima di implementare se manca una decisione critica.

## Funzioni obbligatorie
1. Importa mini-Bibbia da cartella.
2. Mostra titolo e scenario.
3. Modifica scenario in un editor testuale.
4. Salva creando una nuova versione.
5. Visualizza cronologia versioni.
6. Ripristina una versione precedente.
7. Esporta il mondo aggiornato.
8. Mostra errori leggibili in italiano.
9. Nessuna modifica distruttiva ai file sorgente.

## Test obbligatori
- import valido;
- import file mancante;
- modifica scenario;
- creazione versione;
- ripristino;
- persistenza dopo riavvio;
- esportazione;
- protezione file sorgente.

## Consegna
- codice;
- README di avvio;
- test automatici;
- elenco decisioni;
- elenco parti incomplete;
- comandi esatti per eseguire e testare.

## Divieto
Non dichiarare il task completato se i test non passano.
