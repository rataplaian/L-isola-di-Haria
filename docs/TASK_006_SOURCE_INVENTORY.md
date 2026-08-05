# Inventario sorgenti locali Task 006

## Ambito controllato

È stata ispezionata esclusivamente la cartella dedicata
`Haria_Scenario_Personaggi_Immagini_Backup/Haria_Scenario_Personaggi_Immagini`
e il repository. I file originali non sono stati modificati.

Sono disponibili scenario iniziale JSON/Markdown, profili iniziali di nove
personaggi, un indice di riferimenti, un manifest storico e 16 immagini PNG
rinominate. Non sono disponibili sorgenti complete e verificabili per luoghi,
oggetti, lore o timeline; tali contenuti non vengono inventati.

Il pacchetto risultante è stato creato in `local_worlds/haria/` con una copia
ZIP in `local_worlds/haria.zip`; entrambi sono ignorati da Git. Il rapporto
completo con dimensioni e SHA-256 resta esclusivamente dentro `local_worlds/`
e non viene pubblicato nel repository.

## Immagini associate con certezza

| File | Personaggio |
| --- | --- |
| `Ahri (Silvia).png` | Silvia detta Ahri |
| `Akari Mori.png` | Akari Mori |
| `Elise Moreau.png` | Élise Moreau |
| `Katarina Volkov.png` | Katarina Volkov |
| `Mara Voss.png` | Mara Voss |
| `Mara Voss 2.png` | Mara Voss |
| `Natsumi Kuroda.png` | Natsumi Kuroda |
| `Sofia Alvarez.png` | Sofia Álvarez |
| `Yumi Takeda.png` | Yumi Takeda |

Gli ID media dipendono deterministicamente soltanto dal prefisso, dal mondo e
dal percorso relativo normalizzato senza distinzione tra maiuscole e minuscole.
Le due immagini di Mara sono media distinti collegati allo stesso personaggio.

## Immagine di mondo senza personaggio

- `copertina Isola di Haria.png`, classificata come copertina del mondo.

## Immagini escluse dalle associazioni automatiche

| File | Motivo |
| --- | --- |
| `protagonista icona chat.png` | “protagonista” non identifica univocamente Luca |
| `protagonista tipo 1.png` | variante generica |
| `protagonista tipo 2.png` | variante generica |
| `protagonista tipo 3.png` | variante generica |
| `protagonista tipo 4.png` | variante generica |
| `ritratto_al_tramonto_nella_veranda_tropicale.png` | nessun nome di personaggio |

## Personaggi senza immagine certa

- Luca.

## Duplicati o ambiguità

- Mara Voss possiede due immagini distinte e chiaramente nominate; entrambe
  vengono conservate e collegate. Il riferimento principale usa
  deterministicamente `Mara Voss.png`, mentre `Mara Voss 2.png` resta un
  secondo media associato;
- le cinque varianti “protagonista” non vengono collegate a Luca;
- il ritratto della veranda resta non associato;
- la copertina è classificata come media del mondo, non come ritratto.

Tutte le immagini incluse nel pacchetto locale sono copie byte-per-byte degli
originali. Nessun file sorgente è stato rinominato, convertito, ricompresso,
ridimensionato o cancellato.
