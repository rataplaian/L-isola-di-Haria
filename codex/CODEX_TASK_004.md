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

Haria deve contattare esclusivamente un servizio Ollama sul computer locale.
La radice configurata deve usare un host di loopback valido: `localhost`, un
indirizzo IPv4 nel blocco `127.0.0.0/8` oppure l'indirizzo IPv6 `::1`. Sono
ammessi `http` e `https`, con porta esplicita o predefinita.

Gli URL dei tre endpoint devono essere costruiti esplicitamente a partire
dalla radice validata. Non usare concatenazioni ambigue né `urljoin` con
percorsi forniti dall'utente. Il trasporto non segue redirect: qualunque
risposta `3xx` è un errore HTTP applicativo italiano.

La richiesta a `/api/chat` contiene sempre:

- il modello configurato;
- `stream: false`;
- un messaggio `system` con un breve prompt tecnico fisso;
- un messaggio `user` con il breve testo di prova inserito dall'utente oppure
  con un breve testo tecnico predefinito quando il campo è vuoto.

Il testo utente può contenere al massimo 2.000 caratteri Unicode. Un testo più
lungo viene rifiutato prima della richiesta con un errore italiano. Il payload
usa JSON UTF-8, invia `Content-Type: application/json` e non include `tools`,
`format` o dati del mondo.

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

Il trasporto accetta soltanto risposte HTTP `2xx`, non segue redirect e limita
il corpo di ogni risposta a 1 MiB. La lettura deve interrompersi appena viene
superato il limite e produrre un errore italiano senza mostrare o conservare il
corpo eccedente. Le risposte JSON vengono decodificate come UTF-8.

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

### Confine tra thread, SQLite e Tkinter

La connessione SQLite esistente non deve mai essere usata dal thread di rete.
Il flusso obbligatorio è:

1. il thread principale Tkinter legge e valida la configurazione;
2. crea una fotografia immutabile della configurazione;
3. consegna al worker soltanto tale fotografia e oggetti HTTP indipendenti;
4. il worker esegue esclusivamente HTTP, decodifica e validazione della
   risposta;
5. il risultato tipizzato o l'errore applicativo torna al thread principale;
6. soltanto il thread principale aggiorna widget, stato GUI e configurazione
   persistente.

Nel worker non devono transitare connessioni o cursori SQLite,
`ArchivioSQLite`, widget o variabili Tkinter, né oggetti del mondo narrativo.
Usare `after` o un coordinatore equivalente per consegnare il risultato al
thread principale.

Alla chiusura della finestra, ignorare i risultati tardivi e non programmare
aggiornamenti su widget distrutti. I worker non devono impedire la chiusura
regolare dell'applicazione. Il coordinatore asincrono deve essere isolabile e
testabile senza un display grafico reale.

## Persistenza della configurazione

La configurazione AI è applicativa e globale rispetto al file SQLite aperto:
è condivisa da tutti i mondi contenuti nello stesso file. Non è condivisa
automaticamente tra due file database distinti. Non appartiene a un singolo
mondo, non entra nelle versioni narrative e non modifica mondi, scenari,
versioni, stato, eventi o memorie.

Definire la migrazione SQLite transazionale dallo schema 3 allo schema 4. La
migrazione crea una tabella applicativa singleton `ai_settings` con struttura
equivalente a:

- `settings_id INTEGER PRIMARY KEY`;
- `CHECK (settings_id = 1)`;
- `provider TEXT NOT NULL` con `CHECK (provider = 'ollama')`;
- `ollama_base_url TEXT NOT NULL`;
- `ollama_model TEXT NOT NULL`;
- `ollama_timeout_seconds INTEGER NOT NULL` con un `CHECK` che ne imponga il
  tipo intero e il valore tra 1 e 300;
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

La migrazione inserisce atomicamente la sola riga `settings_id = 1`. I
salvataggi successivi aggiornano esclusivamente quella riga e non possono
creare configurazioni aggiuntive.

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
- host remoti, host della rete locale o hostname diversi da `localhost`;
- percorsi diversi dalla stringa vuota o da `/`;
- modello composto soltanto da spazi;
- timeout booleani, non interi, non positivi o maggiori di 300 secondi.

Sono accettati esclusivamente `localhost`, gli indirizzi IPv4 appartenenti a
`127.0.0.0/8` e `::1`. La porta può essere esplicita o quella predefinita dello
schema. La stringa vuota è ammessa come modello non ancora selezionato; una
chiamata di prova richiede invece un modello non vuoto e disponibile. L'URL
viene normalizzato eliminando soltanto la barra finale ammessa. Non applicare
altre riscritture implicite all'URL.

## Contratto delle risposte Ollama

### Versione

`GET /api/version` deve restituire un oggetto JSON con `version` testuale non
vuota. Una versione assente, non testuale o vuota è una struttura inattesa.

### Modelli

`GET /api/tags` deve restituire un oggetto JSON con `models` come lista. Ogni
elemento deve essere un oggetto con `name` testuale non vuoto; un solo elemento
invalido rende invalida l'intera risposta. I nomi duplicati vengono esposti una
sola volta e l'elenco finale viene ordinato senza distinzione tra maiuscole e
minuscole. Il servizio restituisce modelli tipizzati: il JSON originale e gli
altri metadati non raggiungono la GUI.

### Chat di prova

`POST /api/chat` invia JSON UTF-8 con `Content-Type: application/json`.
Accetta soltanto `message.role = "assistant"` e `message.content` testuale non
vuoto dopo la verifica degli spazi. La GUI mostra soltanto il testo della
risposta. Il payload non contiene `tools`, `format` o dati del mondo.

## Sicurezza e separazione

Il provider LLM:

- non legge direttamente il database;
- non modifica canone, stato, eventi o memorie;
- non applica operazioni al mondo;
- non salva automaticamente le risposte;
- non riceve Bibbia, scenario o dati dei personaggi;
- contatta soltanto il servizio di loopback configurato;
- non configura autenticazione cloud e non contatta direttamente servizi
  cloud;
- non scarica, crea, copia o elimina modelli;
- non esegue tool calling;
- non usa embeddings;
- non usa output strutturati;
- non espone o conserva campi `thinking`;
- non implementa streaming;
- non implementa retry automatici nascosti.

Ollama può essere configurato esternamente per usare funzionalità o modelli
cloud. Haria non può determinare in modo affidabile se il processo Ollama
effettuerà connessioni esterne e non deve introdurre euristiche basate soltanto
sul nome del modello. L'uso di modelli cloud resta fuori ambito; quando è
richiesto isolamento completo, l'utente deve configurare Ollama in modalità
locale.

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
- risposta assistant mancante o vuota;
- testo di prova oltre il limite;
- corpo HTTP oltre il limite.

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
La configurazione viene letta e salvata soltanto dal thread principale; il
worker riceve una fotografia immutabile e non accede a SQLite o Tkinter.

## Test obbligatori

I test non richiedono Ollama installato e non effettuano richieste verso un
servizio reale. Usare un server HTTP locale simulato della standard library o
un trasporto HTTP iniettabile.

Coprire almeno:

- migrazione schema 3 → 4;
- apertura di un database vuoto direttamente allo schema 4;
- migrazione sequenziale 0 → 1 → 2 → 3 → 4;
- riapertura senza duplicazioni;
- rollback completo della migrazione;
- valori predefiniti;
- salvataggio e persistenza della configurazione;
- esistenza di una sola riga `ai_settings`;
- rifiuto di `settings_id` diverso da 1 e di una seconda configurazione;
- configurazione condivisa dai mondi dello stesso file SQLite;
- configurazioni indipendenti in due file SQLite differenti;
- validazione del provider, dell'URL, del modello e del timeout;
- accettazione di `localhost`, `127.0.0.1` e `::1`;
- rifiuto di host non loopback e di percorsi diversi da `/`;
- assenza di richieste durante validazione e caricamento;
- `GET /api/version` e lettura della versione;
- `GET /api/tags` ed elenco dei modelli;
- `POST /api/chat`;
- presenza di `stream: false`;
- presenza e ordine dei ruoli `system` e `user`;
- corretta lettura del contenuto assistant;
- timeout e connessione rifiutata;
- risposte HTTP non riuscite;
- rifiuto dei redirect HTTP;
- limite di 2.000 caratteri Unicode per il testo di prova;
- limite di 1 MiB per il corpo HTTP e interruzione della lettura;
- JSON non valido e strutture incomplete;
- versione mancante;
- elenco modelli non valido;
- elenco modelli ordinato senza distinzione tra maiuscole e minuscole e privo
  di duplicati;
- modello configurato non disponibile;
- risposta assistant mancante o vuota;
- messaggi di errore italiani e conservazione della causa;
- testi italiani della GUI;
- assenza di payload e dettagli tecnici nella GUI;
- esecuzione di rete fuori dal thread Tkinter e aggiornamenti GUI sul thread
  principale;
- nessun utilizzo di SQLite o Tkinter dal worker;
- risultato tardivo ignorato dopo la chiusura;
- blocco delle richieste concorrenti duplicate e ripristino dei controlli;
- nessuna modifica a mondi, versioni, eventi, stato o memorie;
- compatibilità con tutti i 94 test precedenti.

## Criteri di accettazione

Il Task 004 sarà completo soltanto quando:

1. una configurazione valida può essere salvata e riletta dopo il riavvio;
2. la migrazione 3 → 4 è atomica, idempotente e non altera dati narrativi;
3. soltanto un servizio Ollama di loopback può essere verificato tramite
   `/api/version`, senza seguire redirect;
4. i modelli locali possono essere elencati tramite `/api/tags` e selezionati;
5. la prova usa `/api/chat`, ruoli `system` e `user` e `stream: false`;
6. soltanto una risposta assistant testuale non vuota raggiunge la GUI;
7. operazioni di rete e generazione non bloccano Tkinter, non usano SQLite dal
   worker e ignorano risultati tardivi dopo la chiusura;
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
