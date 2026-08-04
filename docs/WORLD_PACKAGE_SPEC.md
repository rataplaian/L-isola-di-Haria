# Formato pacchetto Bibbia

Un mondo importabile è una cartella o ZIP con:

- `world.yaml` oppure `world.json`
- `scenario.md`
- `rules.md`
- `style.md`
- `characters/`
- `locations/`
- `lore/`
- `timeline/`
- `media/`
- `manifest.json`

## Regola di usabilità
L'utente può modificare i file Markdown in italiano.
Il software converte internamente i dati tecnici.

## Identificatori
Ogni entità deve avere un ID stabile.
I nomi visibili possono cambiare senza rompere riferimenti.

## Importazione
L'importatore deve:
- validare schema;
- rilevare duplicati;
- mostrare errori leggibili;
- non modificare gli originali;
- creare una copia versionata.
