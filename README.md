# Haria Engine — Pacchetto iniziale

Questo pacchetto definisce le fondamenta del progetto **Haria Engine**.

Obiettivo: creare un software desktop locale, modulare e leggibile in italiano, capace di:

- importare Bibbie narrative;
- mostrare scenario, regole, stile e personaggi in italiano;
- permettere modifiche manuali senza toccare JSON;
- usare un LLM locale sostituibile;
- conservare memoria persistente, stato del mondo e cronologia;
- distinguere canone, stato corrente, eventi e ricordi soggettivi;
- evitare limiti editoriali nascosti o hardcoded;
- mantenere completa esportabilità e controllo dell'utente.

La cartella `docs/` contiene le specifiche.
La cartella `sample_world/` contiene una mini-Bibbia tecnica per i test.
La cartella `codex/` contiene il primo incarico operativo per Codex.

## Task 001 — Editor desktop italiano

Questa versione implementa esclusivamente il primo incarico: importa una mini-Bibbia da cartella, mostra e modifica lo scenario, conserva ogni salvataggio in SQLite, permette il ripristino e crea esportazioni senza modificare i file sorgente.

L'interfaccia non mostra JSON o tabelle del database. Le impostazioni narrative presenti nel pacchetto sono campi leggibili e modificabili in italiano.

## Task 002 — Stato corrente ed eventi

Lo schema SQLite 2 aggiunge personaggi, luoghi e oggetti con canone importato e
stato corrente separati. Le operazioni strutturate di spostamento, trasferimento
e cambio di stato registrano un evento immutabile, le entità coinvolte e lo
stato aggiornato nella stessa transazione. Lo status corrente risiede soltanto
nello stato operativo; il canone importato non viene aggiornato. Eventuali
errori annullano tutte le scritture.

La scheda **Stato del mondo** mostra nomi, tipi, posizioni, possessori, stato,
condizione, accessibilità e cronologia degli eventi senza esporre dati tecnici.
Da questa scheda è possibile trasferire manualmente un oggetto a un personaggio.

I database del Task 001 vengono migrati automaticamente usando soltanto le
fotografie già conservate in `source_files`; la cartella originale non viene
riletta. Se le fotografie richieste sono incomplete o non valide, la migrazione
viene annullata e il database resta allo schema 1.

## Task 003 — Memorie soggettive

Lo schema SQLite 3 separa le memorie di ciascun personaggio dal canone, dallo
stato operativo e dagli eventi. Un fatto globale non diventa conoscenza
automatica: osservazioni, racconti, inferenze e correzioni vengono registrati
esplicitamente tramite il servizio applicativo.

Le memorie e le relazioni con entità e memorie sorgente sono append-only. Le
correzioni creano catene lineari senza riscrivere la memoria precedente; la
vista corrente viene calcolata dalle relazioni di sostituzione. Le conoscenze
iniziali di `characters.json` vengono importate con identità deterministiche.

La scheda **Memorie dei personaggi** permette di selezionare un personaggio,
filtrare per entità, passare dalla vista corrente alla cronologia completa e
consultare contenuto, tipo, fonte, certezza, data, interpretazione ed emozione,
senza mostrare identificatori tecnici.

## Task 004 — Provider Ollama locale

Lo schema SQLite 4 aggiunge una configurazione AI singleton per ciascun file
database. La scheda italiana **Impostazioni AI** permette di configurare un
servizio Ollama sul computer locale, verificarne la versione, aggiornare
l'elenco dei modelli e inviare una breve richiesta tecnica non streaming.

L'integrazione usa direttamente le API native `/api/version`, `/api/tags` e
`/api/chat` tramite la libreria standard. Sono accettati soltanto `localhost`,
indirizzi IPv4 `127.0.0.0/8` e IPv6 `::1`; redirect, host remoti, payload troppo
grandi e risposte non valide vengono rifiutati con messaggi italiani.

Il provider non riceve dati narrativi, non genera ancora la storia e non può
modificare canone, stato, eventi o memorie. Haria non scarica o gestisce
modelli: Ollama e i modelli locali devono essere predisposti separatamente
dall'utente.

## Task 005 — Validatore deterministico del mondo

Il validatore costruisce una fotografia immutabile del mondo tramite le API
tipizzate dell'archivio e controlla coerenza strutturale, spaziale, temporale,
inventariale ed epistemica. Le proposte di spostamento, trasferimento, cambio
di stato, evento descrittivo e acquisizione di conoscenza possono essere
simulate in memoria, singolarmente o in sequenza, senza generare eventi o
memorie e senza scrivere nel database.

La scheda italiana **Validazione mondo** esegue il controllo soltanto su
richiesta esplicita e mostra un riepilogo e problemi ordinati con severità,
ambito e messaggio leggibili. Non espone codici tecnici, identificatori, JSON o
dettagli del database. Il Task 005 non usa il provider Ollama e mantiene lo
schema SQLite allora corrente senza introdurre scritture proprie.

## Task 006 — Pacchetti completi di mondo

Lo schema SQLite 5 indicizza documenti canonici e media senza duplicarne i
byte, che restano nelle fotografie `source_files`. Sono supportati sia il
formato legacy di `sample_world/` sia pacchetti completi da cartella o ZIP con
manifest, personaggi individuali, luoghi, oggetti, lore, timeline e media.

Gli ZIP vengono estratti soltanto in una directory temporanea dopo controlli
su percorsi, link, duplicati e dimensioni. La GUI aggiunge le schede italiane
**Personaggi**, **Lore**, **Regole e stile** e **Media**; ID tecnici e JSON non
sono mostrati. Le importazioni più costose vengono lette e validate da un
worker daemon, mentre SQLite e Tkinter restano nel thread principale.

## Task 007 - Anteprima del turno narrativo

La scheda **Gioca** costruisce un contesto leggibile dal mondo corrente, mostra
il prompt effettivo e invia a Ollama una richiesta strutturata non streaming.
La risposta viene convertita in modelli immutabili e le operazioni proposte
sono sottoposte al validatore deterministico.

Questa prima versione è deliberatamente una sola anteprima: mostra il testo
narrativo soltanto quando il dry-run è valido, ma non applica operazioni, non
crea eventi o memorie, non fa avanzare il tempo e non salva la conversazione.
Le letture SQLite e gli aggiornamenti Tkinter restano nel thread principale;
il worker daemon esegue soltanto la richiesta HTTP locale.

## Task 008 — Turni narrativi persistenti

Lo schema SQLite 6 conserva una cronologia narrativa unica per ogni mondo. Un
turno valido salva insieme input, narrazione, prompt effettivo, output grezzo,
tempo trascorso, eventi, stato e memorie candidate. L'applicazione usa una sola
transazione: un errore in qualsiasi passaggio annulla l'intero turno.

La scheda **Gioca** ricarica dal database gli ultimi cento turni visibili e usa
gli ultimi venti messaggi per il prompt, senza cancellare la cronologia
precedente. La partita resta interamente locale e non aggiunge moderazione,
blacklist o trasformazioni del testo narrativo. Ricerca semantica, simulazione
fuori scena, salvataggi paralleli e rewind non sono ancora attivi.

## Task 008.1 — Output narrativo strutturato

Il turno narrativo invia a Ollama un JSON Schema completo tramite il campo
nativo `format`. Prompt e provider derivano il contratto dalla stessa fonte:
operazioni e memorie hanno varianti esplicite e non possono accettare proprietà
appartenenti all'altro insieme.

Se un primo output è un oggetto JSON leggibile ma strutturalmente errato,
l'applicazione può inviare una sola richiesta automatica di correzione. JSON non
valido, errori di rete, riferimenti inesistenti, incoerenze del mondo ed errori
SQLite non vengono ritentati. Nessun tentativo scartato modifica il database.

## Requisiti

- Python 3.11 o successivo;
- Tkinter, incluso nell'installazione standard di Python per Windows e macOS;
- su Linux, se necessario, il pacchetto di sistema `python3-tk`.

Non sono richieste dipendenze Python esterne o account. Ollama è necessario
soltanto per usare le funzioni della scheda **Impostazioni AI**; editor, dati e
test automatici non richiedono un servizio Ollama reale.

## Installazione

1. Installare Python 3.11 o successivo includendo Tkinter.
2. Aprire un terminale nella cartella del repository.
3. Non è necessario eseguire `pip install`.

## Avvio

Windows:

```powershell
py -3 -m haria_engine
```

In alternativa, se `python` è disponibile nel percorso di sistema:

```powershell
python -m haria_engine
```

macOS e Linux:

```bash
python3 -m haria_engine
```

Al primo avvio il database viene creato nella cartella dati locale dell'utente. È possibile indicare un database diverso:

```powershell
py -3 -m haria_engine --database C:\percorso\haria.sqlite3
```

## Uso

1. Selezionare **Importa da cartella** oppure **Importa da ZIP** e scegliere
   `sample_world/` o un pacchetto compatibile.
2. Modificare lo scenario e, se presenti, le impostazioni narrative.
3. Selezionare **Salva nuova versione**: ogni salvataggio resta recuperabile.
4. Usare **Cronologia versioni** per ripristinare una versione; anche il ripristino crea una nuova versione.
5. Selezionare **Esporta mondo** e scegliere una cartella di destinazione.
6. Aprire **Stato del mondo** per consultare entità ed eventi o trasferire un
   oggetto tramite i controlli italiani.
7. Aprire **Memorie dei personaggi** per consultare conoscenze correnti e
   cronologia soggettiva in sola lettura.
8. Aprire **Impostazioni AI**, verificare il servizio Ollama locale, aggiornare
   i modelli, selezionarne uno e usare **Prova modello**. Solo **Salva
   impostazioni** rende persistenti URL, modello e timeout.
9. Aprire **Validazione mondo** e selezionare **Controlla mondo** per eseguire
   un audit deterministico in sola lettura del mondo corrente.
10. Usare **Personaggi**, **Lore**, **Regole e stile** e **Media** per consultare
    il pacchetto completo senza vedere dati tecnici.
11. Aprire **Gioca**, scrivere un'azione, usare **Mostra prompt** per ispezionare
    il contesto effettivo e selezionare **Invia**. Il turno viene mostrato solo
    dopo il salvataggio atomico e torna disponibile alla riapertura.

## Test e verifica di avvio

Windows:

```powershell
py -3 -m unittest discover -s tests -v
py -3 -m haria_engine --check
```

macOS e Linux:

```bash
python3 -m unittest discover -s tests -v
python3 -m haria_engine --check
```

La suite corrente contiene **295 test automatici** per Task 001–008.1. I test
Ollama usano trasporti simulati e non
effettuano richieste verso servizi reali; i test del validatore verificano
anche che database e configurazione AI rimangano invariati.

## Dati e sicurezza dei sorgenti

La mini-Bibbia selezionata viene soltanto letta. I suoi file non vengono
modificati o cancellati. Il canone importato, lo stato corrente, il registro
eventi, le memorie soggettive, le fotografie dei sorgenti e la cronologia sono
conservati separatamente nel database SQLite; l'esportazione viene sempre
creata in una nuova cartella.

Le motivazioni dello stack e i confini architetturali sono descritti in
`docs/TECHNICAL_DECISIONS.md`. Gli stati puntuali degli incarichi sono in
`docs/TASK_001_STATUS.md`, `docs/TASK_002_STATUS.md`,
`docs/TASK_003_STATUS.md`, `docs/TASK_004_STATUS.md`,
`docs/TASK_005_STATUS.md`, `docs/TASK_006_STATUS.md`,
`docs/TASK_007_STATUS.md`, `docs/TASK_008_STATUS.md` e
`docs/TASK_008_1_STATUS.md`.
