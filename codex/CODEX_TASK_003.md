# Codex Task 003 — Memorie soggettive e conoscenza per personaggio

## Obiettivo

Separare rigorosamente verità operativa, eventi globali e conoscenze o
interpretazioni soggettive dei singoli personaggi. Un evento non crea
automaticamente memorie: osservazioni, racconti, inferenze e correzioni sono
operazioni esplicite, validate e persistenti.

## Ambito escluso

Non integrare LLM, Ollama, prompt, generazione narrativa, dialoghi, validatore
epistemico completo, diffusione autonoma delle voci, menzogne automatiche,
relazioni numeriche, simulazione fuori scena, Bibbia completa, riassunti,
oblio, embeddings, database vettoriali o Task 004.

## Separazione vincolante

- `world_entities`: canone importato immutabile;
- `entity_state`: verità operativa corrente;
- `events`: fatti globali immutabili;
- `event_entities`: entità coinvolte nei fatti;
- `memories`: conoscenze e convinzioni di un solo personaggio;
- `memory_entities`: entità a cui una memoria si riferisce;
- `memory_sources`: memorie usate come origine di un'inferenza;
- configurazione narrativa: separata e versionata.

Le memorie non modificano canone, stato o eventi e non dimostrano che il loro
contenuto sia vero. Non vengono condivise automaticamente.

## Schema SQLite 3

La migrazione esplicita 2 → 3 è transazionale e idempotente.

### `memories`

- `memory_id TEXT PRIMARY KEY`;
- `world_id TEXT NOT NULL`;
- `character_id TEXT NOT NULL`;
- `event_id TEXT` opzionale;
- `knowledge_type TEXT NOT NULL`;
- `source_type TEXT NOT NULL`;
- `source_entity_id TEXT` opzionale;
- `learned_at TEXT NOT NULL`;
- `certainty INTEGER NOT NULL`;
- `content TEXT NOT NULL`;
- `interpretation TEXT` opzionale;
- `associated_emotion TEXT` opzionale;
- `status TEXT NOT NULL`;
- `supersedes_memory_id TEXT` opzionale;
- `created_at TEXT NOT NULL`.

Vincoli:

- `character_id` identifica un personaggio dello stesso mondo;
- evento e fonte, se presenti, appartengono allo stesso mondo;
- certezza intera tra 0 e 100 e contenuto non vuoto;
- `knowledge_type`: `observed_fact`, `reported_fact`, `inference`, `belief`,
  `canonical_knowledge`;
- `source_type`: `direct_observation`, `told_by_character`, `inference`,
  `imported_background`, `self_experience`;
- `status`: `active`, `corrected`, `contradicted`, `superseded`;
- `supersedes_memory_id` appartiene allo stesso mondo e personaggio, è diverso
  da `memory_id` e indica una memoria già esistente e corrente;
- indice unico parziale su `supersedes_memory_id`: una memoria ha al massimo un
  successore diretto.

Il servizio normale scrive `active` per una memoria ordinaria, `corrected` per
una correzione e `contradicted` per una contraddizione. Non scrive
`superseded` sulla riga precedente.

Una memoria è corrente quando nessun'altra memoria dello stesso personaggio la
indica come `supersedes_memory_id`. `effective_status` vale `superseded` in
quel caso, altrimenti coincide con lo `status` immutabile. Il modello espone
separatamente `status`, `is_current` ed `effective_status`.

Le catene sono lineari e acicliche: ogni nuova correzione può puntare soltanto
a una memoria esistente e corrente; righe e riferimenti esistenti non sono
modificabili; l'indice unico impedisce ramificazioni e il controllo
anti-autoreferenziale impedisce cicli di lunghezza uno.

### `memory_entities`

- `memory_id`;
- `world_id`;
- `entity_id`;
- `role` in `subject`, `source`, `location`, `related`;
- chiave primaria `(memory_id, entity_id, role)`;
- chiavi esterne coerenti verso memoria ed entità dello stesso mondo.

### `memory_sources`

- `memory_id`;
- `source_memory_id`;
- `world_id`;
- `character_id`;
- `position INTEGER NOT NULL` positiva;
- chiave primaria `(memory_id, source_memory_id)`;
- unicità `(memory_id, position)`.

Memoria risultante e sorgente devono appartenere allo stesso mondo e allo
stesso personaggio; non possono coincidere. Le fonti possono essere correnti o
storiche e conservano l'ordine fornito.

### Append-only e atomicità

Non esistono API di modifica o cancellazione. Trigger SQLite rifiutano
`UPDATE` e `DELETE` su `memories`, `memory_entities` e `memory_sources`.
Memoria, associazioni alle entità e fonti sono inserite nella stessa
transazione. Qualunque errore annulla tutte le scritture senza modificare
canone, stato o eventi.

Indici minimi:

- memorie per personaggio e data;
- memorie per evento;
- `memory_entities` per entità;
- `supersedes_memory_id` unico quando non nullo;
- `memory_sources` per memoria sorgente.

## Migrazione e conoscenze importate

Per ogni mondo schema 2, leggere esclusivamente `characters.json` dai BLOB di
`source_files`. File mancante, UTF-8 o JSON non valido causa rollback completo:
`PRAGMA user_version` resta 2 e nessuna tabella Task 003 resta parziale.

Ogni voce `knowledge` crea una memoria distinta con:

- `knowledge_type = canonical_knowledge`;
- `source_type = imported_background`;
- evento nullo, certezza 100, status `active`;
- contenuto identico, senza interpretazione o entità dedotte dal testo;
- ID deterministico costruito da mondo, personaggio, posizione della voce e
  impronta del contenuto, non dal solo testo visibile.

Nuove importazioni usano la stessa conversione dalle fotografie già acquisite.
Riaperture e migrazioni ritentate non duplicano memorie.

## Servizio tipizzato

### `registra_osservazione_diretta`

Richiede personaggio, evento con luogo nello stesso mondo, contenuto, certezza
ed eventuali interpretazione, emozione ed entità correlate. Il personaggio
deve trovarsi attualmente nel luogo dell'evento. La registrazione è immediata,
esplicita e non retroattiva; la presenza non crea automaticamente memoria.
Rifiutare duplicati identici per personaggio ed evento. Impostare
`observed_fact` e `direct_observation`.

### `registra_racconto`

Ascoltatore e narratore sono personaggi distinti dello stesso mondo. Impostare
`reported_fact`, `told_by_character` e il narratore come fonte. Il contenuto può
divergere dall'evento e non crea nuovi fatti globali.

### `registra_inferenza`

Crea una conclusione soggettiva, anche errata, con `knowledge_type` e
`source_type` uguali a `inference`. Le memorie sorgente opzionali devono
appartenere allo stesso personaggio e mondo e vengono salvate in ordine in
`memory_sources`. Nessun evento o stato viene modificato.

### `correggi_memoria`

Crea atomicamente una nuova memoria `corrected` o `contradicted` che sostituisce
una memoria corrente dello stesso personaggio e mondo. Conserva integralmente
la precedente e rifiuta autoreferenzialità, ramificazioni o correzioni di
memorie non correnti.

### `elenca_memorie_personaggio`

Supporta filtri per evento, entità e `source_type`, vista corrente e cronologia
completa. Recupera in modo aggregato fonti, entità collegate e stato logico,
evitando query N+1.

## Caso di collaudo

1. Importare un mondo nuovo da `sample_world`.
2. Luca prende la penna tramite `trasferisci_oggetto`: un solo evento, nessuna
   memoria automatica.
3. Élise, presente nell'infermeria, registra esplicitamente l'osservazione e
   collega Luca, penna e infermeria.
4. Akari, nell'assemblea, non può osservare e non possiede la memoria.
5. Dopo riavvio evento e memoria di Élise persistono, Akari resta ignara.
6. Élise racconta l'evento ad Akari: nasce una memoria `reported_fact` distinta,
   con certezza indipendente e Élise come fonte.

## Soggettività e correzione

Akari può ricordare “Luca ha rubato la penna” senza creare un evento di furto o
modificare la penna. Una successiva memoria “Luca ha preso la penna con il
permesso di Élise” corregge la precedente: entrambe restano nella cronologia,
ma soltanto la seconda è corrente.

## Interfaccia italiana

Aggiungere la scheda in sola lettura **Memorie dei personaggi** con:

- selezione personaggio;
- memorie correnti o **Cronologia completa**;
- contenuto, tipo, fonte leggibile, certezza, data, interpretazione ed emozione;
- filtro per entità collegata;
- distinzione visiva tra osservata e riferita;
- nessun JSON, SQL, UUID completo o payload tecnico.

## Test obbligatori

Coprire migrazione 2 → 3, riapertura, rollback per `characters.json` mancante o
non valido, importazione deterministica delle conoscenze, integrità sorgenti,
assenza di memorie automatiche, osservazione valida e rifiutata, racconto,
certezze indipendenti, contenuto soggettivo, inferenza errata, filtri, vista
corrente e cronologia, correzione append-only, catene lineari, autoreferenza,
ramificazioni, trigger sulle tre tabelle, fonti ordinate e invalide, rollback
atomico, persistenza, errori italiani, testi GUI e assenza di dati tecnici.
Tutti i 55 test precedenti devono continuare a passare.

## Consegna

- branch `feature/task-003-subjective-memories`;
- primo commit `docs: define Haria Engine Task 003`;
- commit piccoli per migrazione, servizio, GUI, test e documentazione;
- aggiornare solo README, architettura, modello dati, M3 e stato Task 003;
- pubblicare il branch e aprire una PR verso `main`;
- non eseguire merge e non iniziare Task 004.
