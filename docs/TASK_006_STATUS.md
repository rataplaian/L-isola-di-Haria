# Stato Haria Engine Task 006

## Infrastruttura completata

- importazione deterministica da cartella e ZIP;
- compatibilità invariata con `sample_world/`;
- `world.json`, manifest, scenario, regole, stile, personaggi individuali,
  luoghi, oggetti, lore, timeline e media;
- validazione preventiva di UTF-8, ID, riferimenti, percorsi e SHA-256;
- limiti ZIP, rifiuto di link, percorsi assoluti, attraversamenti, file nascosti
  e duplicati senza distinzione di maiuscole;
- schema SQLite 5 con `canonical_documents` e `media_assets`;
- importazione e migrazione atomiche;
- export completo e atomico con rigenerazione del manifest;
- schede italiane Personaggi, Lore, Regole e stile e Media;
- lettura e validazione in worker daemon, con SQLite e Tkinter nel thread principale.

## Formati

Testi: JSON UTF-8, Markdown e TXT. Media conservati e indicizzati: PNG, GIF,
PPM, PGM, JPEG, WebP e BMP. Le anteprime native coprono PNG, GIF, PPM e PGM;
gli altri formati mostrano un fallback italiano senza perdere i byte.

`world.yaml` non è supportato. Scene generate, chat, applicazione di output LLM
e simulazione fuori scena restano fuori dal Task 006.

## Materiali reali locali

È stato costruito un pacchetto locale ignorato da Git in:

```text
local_worlds/haria/
local_worlds/haria.zip
```

Contiene 9 profili reali disponibili, lo scenario disponibile, 9 immagini
associate con certezza e una copertina. I byte originali sono stati copiati
senza conversione, ridimensionamento o ricompressione. Il pacchetto conserva
anche i profili e gli scenari sorgente originali sotto `source/` e include
`LOCAL_IMPORT_REPORT.json` con inventario e SHA-256.

Non sono stati trovati materiali verificati sufficienti per creare luoghi,
oggetti, lore, timeline, regole e stile come documenti canonici separati. Tali
contenuti non sono stati inventati. Sei immagini generiche non sono state
associate; Luca resta senza immagine certa. Le associazioni e l'inventario
pubblico sono documentati in `TASK_006_SOURCE_INVENTORY.md`; il rapporto
completo resta soltanto nel pacchetto locale ignorato da Git.

Il pacchetto locale, sia cartella sia ZIP, supera importazione, apertura,
consultazione, validazione, export e reimport. Registra 9 personaggi, un
documento scenario e 10 media. Non viene pubblicato dal branch.

## Persistenza

La versione SQLite corrente è **5**. La migrazione 4→5 non reinterpreta
mondi precedenti e non modifica eventi, stato, memorie o configurazione AI.
I byte dei media risiedono soltanto in `source_files`.

## Verifiche

La suite completa contiene **212 test automatici**. Le fixture Task 006 sono
tecniche e temporanee e non includono i contenuti reali di Haria. Sono coperti
cartella/ZIP, equivalenza, sicurezza, manifest, hash, ID e riferimenti,
migrazione e rollback, preservazione, export/reimport, validatore, GUI e
assenza di rete.

Il collaudo grafico reale ha verificato elenco personaggi, dettaglio canonico e
stato corrente senza ID o JSON, elenco media con associazione leggibile e
anteprima PNG. Lo Scenario locale viene derivato meccanicamente dal JSON
sorgente in Markdown italiano; il JSON originale resta soltanto in `source/`.

## Limiti residui

- nessun test usa file narrativi privati;
- JPEG, WebP e BMP non hanno anteprima Tk nativa;
- non esiste ancora modifica GUI del canone completo;
- il pacchetto reale locale è parziale perché i materiali mancanti non sono
  disponibili in forma verificabile;
- Task 007 non è iniziato.
