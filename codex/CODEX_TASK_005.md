# Codex Task 005 — Validatore deterministico del mondo

## Obiettivo

Implementare un confine applicativo deterministico e in sola lettura tra le
future proposte strutturate di un LLM e le operazioni transazionali già
esposte da `ServizioStatoMondo`.

Il validatore costruisce una fotografia tipizzata del mondo, ne controlla
l'integrità logica, valida proposte strutturate e può simulare in memoria una
sequenza di proposte. La narrazione non è fonte della verità: la fotografia
derivata dal database è l'unico stato considerato dalle regole.

## Stack e invarianti

- Python standard library, Tkinter e SQLite già presenti nel progetto;
- nessuna dipendenza esterna;
- schema SQLite invariato alla versione 4;
- nessuna chiamata HTTP, Ollama o ad altri provider;
- nessuna connessione o cursore SQLite nei modelli puri;
- nessun accesso a Tkinter nelle regole;
- nessuna scrittura, applicazione di eventi o correzione automatica.

## Modelli immutabili

Definire modelli frozen e tipizzati almeno per:

- fotografia del mondo;
- entità con canone e stato corrente necessari alla validazione;
- eventi ordinati temporalmente;
- memorie correnti e storiche, entità associate e fonti;
- proposte strutturate;
- problemi, rapporti ed esiti di proposta o sequenza.

Le severità sono `errore`, `avvertimento` e `informazione`. Gli ambiti sono
`integrità`, `spazio`, `tempo`, `inventario` ed `epistemica`.

Ogni problema contiene un codice stabile, severità, ambito, messaggio
italiano, eventuale indice della proposta e riferimenti tipizzati alle entità.
I codici sono disponibili alle API e ai test, ma non sono mostrati nella GUI
normale.

Un rapporto è superato quando non contiene problemi di severità `errore`.
Avvertimenti e informazioni non rendono da soli il rapporto non superato.

## Ordinamento deterministico

I problemi sono ordinati tramite una chiave stabile composta da:

1. indice della proposta, con i problemi dell'audit generale prima delle
   proposte;
2. severità nell'ordine errore, avvertimento, informazione;
3. ambito nell'ordine integrità, spazio, tempo, inventario, epistemica;
4. codice tecnico;
5. riferimenti alle entità già ordinati;
6. messaggio.

Nessun risultato dipende dall'ordine di iterazione di set o dizionari, da UUID
casuali o dall'orologio di sistema.

## Fotografia in sola lettura

Un servizio applicativo costruisce la fotografia tramite API tipizzate
dell'archivio. La fotografia contiene quanto necessario per validare:

- identità, tipo e nome canonico delle entità;
- stato, posizione, possessore, accessibilità, condizione e versione corrente;
- eventi, riferimenti alle entità e ordine temporale;
- memorie, appartenenza al personaggio, stato corrente, entità associate e
  fonti ordinate.

La costruzione usa soltanto letture. Non restituisce connessioni, cursori,
righe SQLite o JSON grezzo e non duplica SQL nella GUI.

## Audit di integrità

L'audit rileva deterministicamente almeno:

- riferimenti a entità mancanti;
- posizione che non indica un luogo;
- possessore che non indica un personaggio;
- oggetto posseduto in una posizione diversa dal possessore;
- personaggio con possessore;
- luogo con posizione o possessore;
- riferimenti evento assenti o appartenenti a un altro mondo;
- memoria associata a un personaggio assente o non personaggio;
- fonti di memoria appartenenti a un altro personaggio;
- timestamp assenti di fuso o non confrontabili;
- duplicazioni strutturali rilevabili senza interpretare testo libero.

L'audit non corregge alcuna anomalia.

## Proposte strutturate

Supportare proposte immutabili equivalenti a:

- spostamento di personaggio o oggetto;
- trasferimento di un singolo oggetto;
- cambiamento di status, condizione o accessibilità;
- registrazione di un evento descrittivo;
- affermazione o decisione puramente epistemica di un personaggio.

I campi opzionali includono, quando pertinenti, attore, bersaglio, luogo,
oggetto, possessore, istante, motivo e memorie dichiarate come base. Le regole
usano soltanto questi campi e non interpretano semanticamente testo libero.

## Regole spaziali e inventariali

La validazione controlla:

- esistenza e tipo di tutte le entità coinvolte;
- esistenza, tipo e accessibilità del luogo;
- accessibilità delle entità fisicamente coinvolte;
- compresenza per le interazioni dirette;
- coerenza tra oggetto e possessore;
- divieto di spostare direttamente un oggetto posseduto;
- nuovo possessore necessariamente personaggio con posizione valida;
- trasferimento remoto o verso lo stesso possessore non valido;
- aggiornamento, nel dry-run, soltanto di possessore e posizione dell'oggetto
  trasferito.

Non vengono inventate distanze, collegamenti fra luoghi o topologie non
presenti nei dati.

## Regole temporali

Le regole ricevono sempre un istante di riferimento esplicito. Non usano
`datetime.now`.

- ogni timestamp fornito deve includere il fuso orario;
- i confronti sono normalizzati in UTC;
- una proposta non storica non può precedere l'ultimo evento;
- una sequenza deve avere istanti non decrescenti;
- operazioni storiche e calendari narrativi complessi restano fuori ambito.

## Regole epistemiche

Una memoria dichiarata come base deve:

- esistere nello stesso mondo;
- appartenere all'attore;
- essere corrente e non superata;
- avere fonti, per un'inferenza, appartenenti allo stesso personaggio.

Un'entità accessibile presente nello stesso luogo dell'attore può essere
percepita direttamente. Un'entità remota richiede invece una memoria corrente
dell'attore associata a quell'entità. La memoria di un altro personaggio non
diventa automaticamente conoscenza dell'attore.

Il validatore controlla soltanto provenienza e disponibilità strutturale delle
informazioni. Non stabilisce se una frase sia vera, semanticamente deducibile
o linguisticamente coerente con il contenuto delle memorie.

## Dry-run

Per una sequenza ordinata:

1. ogni proposta è validata contro la proiezione corrente;
2. una proposta valida aggiorna soltanto una nuova proiezione in memoria;
3. una proposta non valida non modifica la proiezione;
4. gli esiti precedenti sono conservati;
5. la diagnosi continua quando le informazioni restano sufficienti;
6. ogni problema conserva l'indice della proposta;
7. entità non coinvolte restano identiche;
8. non vengono creati eventi, memorie, UUID o righe SQLite.

La stessa fotografia e la stessa sequenza producono lo stesso rapporto e la
stessa proiezione.

## Servizio applicativo

`ServizioValidazione` espone almeno:

- `costruisci_fotografia(world_id)`;
- `controlla_mondo(world_id)`;
- `valida_proposta(world_id, proposta, riferimento_temporale)`;
- `valida_sequenza(world_id, proposte, riferimento_temporale)`.

Il servizio può leggere dall'archivio soltanto per creare la fotografia. Le
regole operano su modelli puri. Nessun metodo richiama API di scrittura di
stato, eventi, memorie, versioni o configurazione AI.

## Interfaccia italiana

Aggiungere una scheda **Validazione mondo** in sola lettura con:

- selezione coerente del mondo corrente;
- pulsante esplicito **Controlla mondo**;
- riepilogo di esito, errori e avvertimenti;
- elenco leggibile con ambito e nomi delle entità;
- nessun JSON, traceback, SQL, percorso privato o codice tecnico;
- nessuna correzione automatica;
- nessun audit automatico all'avvio;
- azzeramento coerente della vista quando cambia il mondo.

La GUI esegue soltanto l'audit; non include un editor di proposte.

## Errori

Esporre `ErroreValidazione` con messaggi italiani. Le cause tecniche restano
disponibili tramite exception chaining per test e diagnosi, ma non sono
mostrate nella GUI normale.

## Verifica dell'assenza di scritture

I test devono usare soltanto database temporanei e confrontare prima e dopo:

- `PRAGMA user_version`, sempre pari a 4;
- conteggi delle tabelle;
- eventi e associazioni;
- stato corrente;
- memorie, entità e fonti;
- configurazione AI.

Devono inoltre verificare che nessun metodo di scrittura dell'archivio sia
invocato e che non avvengano richieste HTTP o connessioni Ollama.

## Criteri di accettazione

Il Task 005 è completo quando:

1. la fotografia tipizzata è costruita con sole letture;
2. l'audit copre le incoerenze strutturali richieste;
3. le proposte sono validate nelle quattro dimensioni previste;
4. il dry-run è deterministico e modifica soltanto la proiezione;
5. errori e avvertimenti sono ordinati e leggibili in italiano;
6. la GUI esegue soltanto un audit esplicito e non mostra dati tecnici;
7. lo schema resta alla versione 4 e nessuna tabella cambia durante la
   validazione;
8. la suite completa supera tutti i test e `--check` riesce su un database
   temporaneo esplicitamente indicato.

## Fuori ambito

- generazione narrativa e prompt per Ollama;
- chiamate LLM, HTTP, tool calling o interpretazione di testo libero;
- applicazione di eventi o stato;
- creazione o correzione di memorie;
- modifica di canone, scenario o impostazioni narrative;
- simulazione fuori scena e calendari narrativi complessi;
- topologie o distanze inventate;
- importazione della Bibbia completa;
- migrazioni oltre lo schema 4;
- Task 006.
