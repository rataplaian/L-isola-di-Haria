# Stato Codex Task 004

## Implementato

- schema SQLite 4 con tabella singleton `ai_settings` globale per file database;
- migrazione 3 → 4 atomica, idempotente e priva di modifiche narrative;
- apertura di database vuoti attraverso la sequenza 0 → 1 → 2 → 3 → 4;
- modelli AI immutabili e validazione senza rete;
- URL limitati a `localhost`, IPv4 `127.0.0.0/8` e IPv6 `::1` senza DNS;
- trasporto `urllib` iniettabile, diretto, senza proxy, redirect o retry;
- sole risposte `2xx`, limite corpo di 1 MiB e JSON UTF-8;
- provider Ollama sostituibile tramite protocollo;
- API native `GET /api/version`, `GET /api/tags` e `POST /api/chat`;
- elenco modelli validato, deduplicato e ordinato con `casefold`;
- prova con `stream: false`, ruoli `system` e `user` e massimo 2.000 caratteri;
- verifica preventiva della disponibilità del modello;
- errori applicativi italiani senza corpi HTTP, JSON o dettagli socket;
- servizio di rete separato da SQLite, Tkinter e oggetti narrativi;
- coordinatore asincrono testabile con un solo worker daemon e coda risultati;
- rifiuto delle richieste concorrenti e scarto dei risultati dopo la chiusura;
- scheda Tkinter italiana **Impostazioni AI** senza richieste automatiche;
- salvataggio esplicito e uso delle impostazioni visibili non ancora salvate per
  le azioni di rete;
- area di risposta in sola lettura e versione Ollama leggibile.

## Confini di sicurezza

Haria contatta direttamente soltanto il servizio di loopback configurato e non
invia Bibbia, scenario, personaggi, stato, eventi o memorie. Il provider non
legge il database, non salva risposte e non applica operazioni al mondo.

Ollama può essere configurato esternamente per usare funzionalità cloud; Haria
non può determinarlo dal nome del modello. Per isolamento completo, l'utente
deve configurare Ollama in modalità locale.

## Verifica

```powershell
python -m unittest discover -s tests -v
python -m haria_engine --check
```

La suite comprende **127 test**: 94 test precedenti e 33 test Task 004. I test
del provider usano trasporti simulati e non richiedono Ollama installato né
servizi reali.

## Escluso perché fuori ambito

- generazione narrativa e prompt effettivo di Haria;
- invio del canone o dello stato al modello;
- interpretazione della risposta come azione;
- tool calling, output strutturato, streaming ed embeddings;
- memoria della conversazione e simulazione fuori scena;
- download o gestione dei modelli;
- autenticazione remota, provider cloud o provider diversi da Ollama;
- Task 005.

## Limiti e rischi residui

- La prova richiede un processo Ollama e un modello già disponibili sul
  computer dell'utente; Haria non li installa o scarica.
- La risposta è intenzionalmente effimera e non viene salvata.
- HTTPS su loopback è accettato, ma certificati e configurazione TLS restano a
  carico dell'utente e del servizio Ollama.
- Il Task 004 non valuta la qualità o l'idoneità narrativa del modello.
