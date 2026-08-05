# Formato pacchetto Bibbia

## Compatibilità legacy

Resta valido il formato tecnico originale:

```text
world.json
scenario.md
characters.json
locations.json
items.json
```

`sample_world/` continua a essere importabile senza conversioni.

## Formato completo Task 006

Un pacchetto completo è una cartella o un archivio `.zip` con questa struttura:

```text
world.json
manifest.json
scenario.md
rules.md
style.md
characters/<personaggio>.json
locations/<luogo>.json
items/<oggetto>.json
lore/<documento>.md
timeline/<voce>.json oppure <documento>.md
media/...
```

`world.json` è il solo file master supportato. `world.yaml` è deliberatamente
fuori dal Task 006: il progetto non introduce un parser YAML parziale o una
dipendenza esterna.

`rules.md`, `style.md`, luoghi, oggetti, lore, timeline e media sono indicizzati
quando presenti; non vengono inventati contenuti narrativi mancanti. Un
pacchetto che usa la struttura completa richiede sempre `manifest.json` e
`scenario.md`.

## Manifest

Il manifest contiene:

- `world_id`, uguale all'ID di `world.json`;
- `files`, elenco esatto di tutti i file tranne il manifest con percorso e
  SHA-256;
- `documents`, metadati opzionali per ID, tipo, titolo, ordine e metadati;
- `media`, metadati opzionali per ID, tipo, titolo, testo alternativo, ordine
  ed entità collegata.

Gli ID dichiarati devono essere non vuoti e univoci nella propria categoria.
Quando un ID documento o media non è dichiarato, viene derivato in modo
deterministico da mondo, percorso normalizzato e impronta del file.

## Sicurezza

Sono ammessi JSON, Markdown, testo e media statici PNG, GIF, PPM, PGM, JPEG,
WebP e BMP. I file devono avere percorsi relativi sicuri. Percorsi assoluti,
unità Windows, `..`, file tecnici nascosti, symlink e duplicati ignorando le
maiuscole vengono rifiutati.

Limiti Task 006:

- massimo 2.000 file;
- massimo 32 MiB per file;
- massimo 256 MiB complessivi.

Lo ZIP viene estratto in una directory temporanea rimossa sempre. La
validazione completa precede ogni scrittura SQLite. Originali e archivio non
sono modificati.

## Entità e contenuti

Ogni file sotto `characters/`, `locations/` e `items/` contiene un singolo
oggetto JSON con ID stabile e nome. Tutti gli altri campi canonici vengono
conservati integralmente; i campi narrativi non universali restano opzionali.
Posizioni, possessori, relazioni strutturate, personaggio giocante e immagini
devono riferirsi a entità o media presenti nello stesso mondo.

Una timeline JSON deve contenere almeno un campo testuale `content`; la GUI ne
mostra il contenuto leggibile, non il JSON sorgente. Il file originale resta
comunque nella fotografia `source_files`.

## Esportazione

L'esportazione ricrea la struttura completa in una directory temporanea e la
pubblica atomicamente. Conserva byte dei media, file ammessi non interpretati,
cartelle e ID. Scenario e impostazioni narrative correnti vengono aggiornati;
se presente, il manifest viene rigenerato con gli hash effettivi. Gli altri
file non vengono appiattiti o riscritti.

## Anteprime

Tkinter mostra nativamente PNG, GIF, PPM e PGM. JPEG, WebP, BMP e altri formati
indicizzati ricevono un fallback italiano; i byte restano disponibili per
export anche quando l'anteprima non è supportata.
