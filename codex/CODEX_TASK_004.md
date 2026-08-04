# Codex Task 004 — Provider LLM locale e collegamento Ollama

## Obiettivo

Creare un'infrastruttura sostituibile per provider LLM e una prima
implementazione locale basata su Ollama. Il Task 004 consente esclusivamente
di configurare il provider, l'URL, il modello e il timeout; verificare il
servizio; leggere la versione di Ollama; elencare e selezionare i modelli
locali; eseguire una chiamata testuale di prova; mostrare il risultato nella
GUI italiana; gestire gli errori in modo leggibile.

Il provider non genera ancora la storia, non riceve dati del mondo e non
modifica il mondo.

## Stack e dipendenze

Mantenere lo stack esistente:

- Python standard library;
- Tkinter;
- SQLite;
- nessuna dipendenza Python esterna.

Usare `urllib` della standard library dietro un trasporto HTTP isolabile e
iniettabile. Non aggiungere il pacchetto Python `ollama`, `requests`, `httpx` o
framework. Non usare l'endpoint di compatibilità OpenAI.

## API Ollama

URL predefinito: `http://localhost:11434`.

L'implementazione usa direttamente l'API REST nativa:

- `GET /api/version`: verifica la raggiungibilità e legge la versione;
- `GET /api/tags`: elenca i modelli locali disponibili;
- `POST /api/chat`: esegue la chiamata testuale di prova.

La richiesta a `/api/chat` contiene sempre:

- il modello configurato;
- `stream: false`;
- un messaggio `system` con un breve prompt tecnico fisso;
- un messaggio `user` con il breve testo di prova inserito dall'utente oppure
  con un breve testo tecnico predefinito quando il campo è vuoto.

Il prompt e il testo di prova non contengono Bibbia, scenario, personaggi,
stato, eventi o memorie. La risposta è valida soltanto se contiene un oggetto
`message` con ruolo `assistant` e un `content` testuale non vuoto. Eventuali
campi `thinking` vengono ignorati e non sono esposti né conservati.

## Architettura richiesta

### Modelli immutabili e tipizzati

Prevedere almeno modelli immutabili e tipizzati equivalenti a:

- `ConfigurazioneAI`: provider, URL base, modello, timeout e data di
  aggiornamento;
- `InformazioniProvider`: nome provider e versione leggibile;
- `ModelloLocale`: nome leggibile del modello disponibile;
- `MessaggioChat`: ruolo e contenuto testuale;
- `RispostaTestuale`: contenuto assistant non vuoto;
- `RisultatoConnessione`: raggiungibilità e informazioni del provider.

I modelli non devono dipendere da Tkinter, SQLite, `urllib` o dalle classi del
mondo narrativo.

### Interfaccia sostituibile del provider

Definire un `Protocol` o una ABC indipendente da Ollama con operazioni
equivalenti a:

- `verifica_connessione`;
- `elenca_modelli`;
- `genera_testo_di_prova`.

La prima e unica implementazione del Task 004 è il provider Ollama. La GUI non
conosce URL di endpoint, payload HTTP o JSON: usa esclusivamente un servizio
applicativo tipizzato. Il provider Ollama resta separato dalla GUI, dalla
persistenza SQLite e dalla logica del mondo.

### Trasporto HTTP

Isolare il trasporto dietro un'interfaccia iniettabile che riceva metodo, URL,
header, corpo e timeout e restituisca stato HTTP e corpo della risposta. La
produzione usa la standard library; i test usano il trasporto iniettabile o un
server HTTP locale della standard library.

Non introdurre retry automatici nascosti. Ogni azione dell'utente produce al
massimo una richiesta per l'endpoint richiesto.

### Servizio applicativo

Il servizio applicativo:

- carica, valida e salva la configurazione tramite un archivio dedicato;
- costruisce il provider configurato;
- verifica la connessione;
- recupera i modelli;
- verifica che il modello scelto sia disponibile prima della prova;
- invia messaggi tipizzati e restituisce una risposta testuale tipizzata;
- traduce gli errori tecnici in errori applicativi italiani distinguibili.

Né la GUI né il provider accedono direttamente alle tabelle del mondo.

## Persistenza della configurazione

La configurazione AI è applicativa e globale: non appartiene a un mondo, non
entra nelle versioni narrative e non modifica mondi, scenari, versioni, stato,
eventi o memorie.

Definire la migrazione SQLite transazionale dallo schema 3 allo schema 4. La
migrazione crea una tabella applicativa a riga singola, per esempio
`ai_settings`, con almeno:

- una chiave stabile che identifichi l'unica configurazione applicativa;
- `provider TEXT NOT NULL`;
- `ollama_base_url TEXT NOT NULL`;
- `ollama_model TEXT NOT NULL`;
- `ollama_timeout_seconds INTEGER NOT NULL`;
- `updated_at TEXT NOT NULL`.

Valori predefiniti:

- provider: `ollama`;
- URL: `http://localhost:11434`;
- modello: stringa vuota finché l'utente non ne sceglie uno;
- timeout: 30 secondi;
- timeout massimo accettato: 300 secondi.

La migrazione deve essere:

- atomica e transazionale;
- idempotente alla riapertura;
- compatibile con ogni database valido dello schema 3;
- priva di scritture nelle tabelle di mondi, versioni, stato, eventi e memorie.

`PRAGMA user_version` diventa 4 soltanto al termine della transazione. Un
errore esegue il rollback completo: `user_version` resta 3, la tabella Task 004
non resta parzialmente creata o popolata e tutti i dati precedenti restano
invariati.

Il salvataggio della configurazione è esplicito tramite **Salva impostazioni**.
La semplice validazione o il caricamento non effettua richieste HTTP.

## Validazione e normalizzazione

La configurazione rifiuta con messaggi italiani:

- provider diversi da `ollama`;
- URL vuoti o composti soltanto da spazi;
- URL non assoluti;
- schemi diversi da `http` e `https`;
- URL con nome utente o password incorporati;
- URL con query o frammento;
- modello composto soltanto da spazi;
- timeout booleani, non interi, non positivi o maggiori di 300 secondi.

La stringa vuota è ammessa come modello non ancora selezionato; una chiamata di
prova richiede invece un modello non vuoto e disponibile. L'URL viene
normalizzato eliminando soltanto le barre finali superflue. Non applicare altre
riscritture implicite all'URL.

## Contratto delle risposte Ollama

### Versione

`GET /api/version` deve restituire un oggetto JSON con `version` testuale non
vuota. Una versione assente, non testuale o vuota è una struttura inattesa.

### Modelli

`GET /api/tags` deve restituire un oggetto JSON con `models` come lista. Ogni
modello esposto all'applicazione deve possedere un nome testuale non vuoto. Il
servizio restituisce modelli tipizzati e non espone il JSON originale.

### Chat di prova

`POST /api/chat` invia JSON UTF-8 e dichiara il tipo di contenuto appropriato.
Accetta soltanto `message.role = "assistant"` e `message.content` testuale non
vuoto dopo la verifica degli spazi. La GUI mostra soltanto il testo della
risposta.

## Sicurezza e separazione

Il provider LLM:

- non legge direttamente il database;
- non modifica canone, stato, eventi o memorie;
- non applica operazioni al mondo;
- non salva automaticamente le risposte;
- non riceve Bibbia, scenario o dati dei personaggi;
- non accede a Internet per conto dell'applicazione;
- comunica soltanto con l'URL configurato dall'utente;
- non scarica, crea, copia o elimina modelli;
- non esegue tool calling;
- non usa embeddings;
- non usa output strutturati;
- non espone o conserva campi `thinking`;
- non implementa streaming;
- non implementa retry automatici nascosti.

## Errori applicativi

Definire errori tipizzati e distinguibili con messaggi italiani almeno per:

- Ollama non raggiungibile;
- timeout;
- risposta HTTP non riuscita;
- JSON non valido;
- struttura JSON inattesa;
- versione mancante;
- elenco modelli non valido;
- modello configurato non disponibile;
- risposta assistant mancante o vuota.

Gli errori di basso livello conservano la causa originale tramite exception
chaining. La GUI normale non mostra traceback, eccezioni socket, HTML, JSON
grezzo, endpoint completi, payload o altri dettagli tecnici.

## Interfaccia italiana

Aggiungere nel futuro Task 004 una scheda separata **Impostazioni AI** con:

- provider mostrato come Ollama e non modificabile;
- campo **URL del servizio**;
- campo **Timeout (secondi)**;
- selettore del modello;
- pulsante **Salva impostazioni**;
- pulsante **Verifica connessione**;
- pulsante **Aggiorna modelli**;
- pulsante **Prova modello**;
- campo breve per il testo di prova;
- area della risposta in sola lettura;
- indicazione leggibile della versione di Ollama;
- messaggi di stato e di errore in italiano.

Non mostrare identificatori tecnici, endpoint, payload, JSON, nomi inglesi
degli stati o stack trace.

Le operazioni di rete e la generazione non devono bloccare il thread Tkinter.
Eseguirle in modo controllato in background e applicare ogni aggiornamento dei
widget esclusivamente dal thread principale. Mentre una richiesta è in corso,
impedire richieste concorrenti duplicate e disabilitare temporaneamente i
controlli interessati; ripristinarli sia dopo il successo sia dopo l'errore.

## Test obbligatori

I test non richiedono Ollama installato e non effettuano richieste verso un
servizio reale. Usare un server HTTP locale simulato della standard library o
un trasporto HTTP iniettabile.

Coprire almeno:

- migrazione schema 3 → 4;
- riapertura senza duplicazioni;
- rollback completo della migrazione;
- valori predefiniti;
- salvataggio e persistenza della configurazione;
- validazione del provider, dell'URL, del modello e del timeout;
- assenza di richieste durante validazione e caricamento;
- `GET /api/version` e lettura della versione;
- `GET /api/tags` ed elenco dei modelli;
- `POST /api/chat`;
- presenza di `stream: false`;
- presenza e ordine dei ruoli `system` e `user`;
- corretta lettura del contenuto assistant;
- timeout e connessione rifiutata;
- risposte HTTP non riuscite;
- JSON non valido e strutture incomplete;
- versione mancante;
- elenco modelli non valido;
- modello configurato non disponibile;
- risposta assistant mancante o vuota;
- messaggi di errore italiani e conservazione della causa;
- testi italiani della GUI;
- assenza di payload e dettagli tecnici nella GUI;
- esecuzione di rete fuori dal thread Tkinter e aggiornamenti GUI sul thread
  principale;
- blocco delle richieste concorrenti duplicate e ripristino dei controlli;
- nessuna modifica a mondi, versioni, eventi, stato o memorie;
- compatibilità con tutti i 94 test precedenti.

## Criteri di accettazione

Il Task 004 sarà completo soltanto quando:

1. una configurazione valida può essere salvata e riletta dopo il riavvio;
2. la migrazione 3 → 4 è atomica, idempotente e non altera dati narrativi;
3. Ollama può essere verificato tramite `/api/version`;
4. i modelli locali possono essere elencati tramite `/api/tags` e selezionati;
5. la prova usa `/api/chat`, ruoli `system` e `user` e `stream: false`;
6. soltanto una risposta assistant testuale non vuota raggiunge la GUI;
7. operazioni di rete e generazione non bloccano Tkinter;
8. gli errori previsti sono leggibili in italiano e non espongono dati
   tecnici;
9. nessuna risposta viene salvata e nessun dato del mondo viene letto o
   modificato;
10. l'intera suite, inclusi i 94 test precedenti, supera tutti i test;
11. il programma si avvia e `python -m haria_engine --check` riesce.

## Fuori ambito

Escludere esplicitamente:

- generazione narrativa;
- costruzione del prompt effettivo di Haria;
- invio del canone o dello stato del mondo al modello;
- interpretazione delle risposte come azioni;
- validazione epistemica;
- tool calling;
- output JSON strutturato;
- streaming;
- memoria della conversazione;
- relazioni con NPC;
- simulazione fuori scena;
- download o gestione dei modelli;
- supporto cloud;
- autenticazione remota;
- provider diversi da Ollama;
- Task 005.

## Consegna prevista per l'implementazione futura

Quando il Task 004 verrà implementato, usare il branch
`feature/task-004-ollama-provider`, creare commit piccoli e descrittivi,
eseguire l'intera suite e `python -m haria_engine --check`, quindi pubblicare
una pull request verso `main` senza eseguire il merge. Non iniziare Task 005.
