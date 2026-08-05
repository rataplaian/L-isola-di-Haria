# Haria Engine — Task 006

## Obiettivo

Importare, consultare ed esportare pacchetti narrativi completi da cartella o
ZIP, mantenendo compatibilità con la mini-Bibbia legacy e senza generazione
narrativa, simulazione o applicazione di output LLM.

## Formati

Il file principale è `world.json`. Il formato completo supporta
`manifest.json`, `scenario.md`, `rules.md`, `style.md`, file JSON individuali
in `characters/`, `locations/` e `items/`, documenti in `lore/`, voci JSON o
Markdown in `timeline/` e file statici sotto `media/`. `world.yaml` è escluso:
il Task 006 implementa esclusivamente il JSON master senza introdurre YAML.

Il formato legacy con `characters.json`, `locations.json` e `items.json` resta
supportato senza modifiche.

## Sicurezza e determinismo

- i percorsi devono essere relativi, normalizzati e privi di attraversamenti;
- ZIP assoluti, con unità Windows, link simbolici o voci eccessive sono
  rifiutati prima dell'importazione;
- massimo 2.000 file, 32 MiB per file e 256 MiB complessivi estratti;
- nomi duplicati senza distinzione significativa di maiuscole sono rifiutati;
- JSON e Markdown testuali devono essere UTF-8;
- ID e riferimenti devono essere stabili, univoci e interni allo stesso mondo;
- hash SHA-256 dichiarati nel manifest devono coincidere;
- la validazione precede ogni scrittura SQLite;
- cartella, ZIP e file sorgente non vengono mai modificati;
- l'estrazione ZIP è temporanea e viene sempre rimossa.

## Persistenza

Lo schema SQLite 5 aggiunge `canonical_documents` e `media_assets`. I documenti
conservano tipo, titolo, percorso, contenuto, ordine, metadati e hash. I media
conservano identità, percorso, tipo, MIME, hash, testo alternativo, possibile
entità collegata, ordine e metadati. I byte restano nella fotografia
`source_files` e non vengono duplicati.

La migrazione 4→5 è transazionale e idempotente. Non modifica mondi, versioni,
eventi, stato, memorie o configurazione AI. Un errore lascia `user_version` a 4
e nessuna struttura Task 006 parziale.

## Interfaccia

La GUI italiana aggiunge consultazioni in sola lettura per **Personaggi**,
**Lore**, **Regole e stile** e **Media**. Non mostra JSON o ID tecnici. Le
anteprime usano soltanto i formati supportati nativamente da Tkinter; gli altri
file ricevono un messaggio italiano e restano comunque conservati.

## Materiali reali

I materiali locali dedicati possono essere convertiti soltanto sotto una
directory ignorata da Git. Testi e byte vengono copiati senza riscrittura,
ricompressione o conversione. Associazioni ambigue non vengono create.

## Esportazione

L'esportazione ripristina l'intera struttura fotografata, inclusi file non
interpretati ammessi e media byte-identici. Scenario e impostazioni narrative
correnti sostituiscono soltanto le rispettive rappresentazioni previste; gli
altri contenuti non vengono appiattiti o persi.

## Test obbligatori

Copertura di legacy, cartella completa, ZIP, equivalenza deterministica,
manifest e hash, duplicati, riferimenti, percorsi ZIP ostili, limiti, rollback,
migrazione, persistenza invariata, export/reimport, media byte-identici, GUI
italiana, fallback anteprima e validatore. Tutti i test usano risorse
temporanee e nessun contenuto narrativo reale.

## Fuori ambito

YAML, scene narrative, chat, output LLM applicato, simulazione fuori scena,
modifica GUI del canone completo, pubblicazione dei materiali privati e Task
007.
