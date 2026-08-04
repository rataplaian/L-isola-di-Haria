# Architettura

## Moduli

### 1. Interfaccia desktop
Schermata narrativa e editor in italiano.

### 2. Importatore Bibbia
Accetta un pacchetto di mondo e lo converte nel formato interno.

### 3. Archivio canonico
Conserva la Bibbia originale, versionata e non distruttiva.

### 4. Stato corrente
Registra posizione, possesso, condizioni, relazioni, accessibilità e stato delle entità.

### 5. Registro eventi
Ogni cambiamento rilevante diventa un evento immutabile.

Nel Task 002, `haria_engine/world_state.py` espone le sole operazioni strutturate
validate. `haria_engine/storage.py` applica evento, associazioni alle entità e
aggiornamenti dello stato nella stessa transazione SQLite. I registri `events`
ed `event_entities` sono protetti anche da trigger contro aggiornamenti e
cancellazioni.

### 6. Memorie soggettive
Ogni personaggio conosce soltanto ciò che ha osservato, dedotto o appreso.

Nel Task 003, `haria_engine/memories.py` contiene modelli e servizio tipizzati.
`haria_engine/storage.py` inserisce memoria, associazioni alle entità e memorie
sorgente nella stessa transazione. `memories`, `memory_entities` e
`memory_sources` sono protette da trigger contro aggiornamenti e cancellazioni.
Una correzione aggiunge una nuova memoria e non riscrive quella storica.

### 7. Motore narrativo
Prepara il contesto e interroga l'LLM locale.

### 8. Motore di simulazione
Fa avanzare processi fuori scena.

### 9. Validatore
Controlla coerenza spaziale, temporale, epistemica e inventariale.

### 10. Provider LLM
Interfaccia sostituibile. Prima implementazione: Ollama.

## Flusso di un turno
1. ricezione azione utente;
2. analisi dell'azione;
3. recupero di stato e ricordi rilevanti;
4. avanzamento dei processi;
5. generazione narrativa;
6. proposta di operazioni strutturate;
7. validazione;
8. applicazione atomica;
9. salvataggio scena;
10. risposta all'utente.

## Regola fondamentale
La narrazione non è la fonte della verità.
Il database è la fonte della verità.

## Confini implementati fino al Task 003

- Il canone originale resta immutabile in `world_entities.canonical_data` e
  nelle fotografie sorgente.
- Lo stato operativo corrente, incluso `current_status`, resta in
  `entity_state`.
- Gli eventi sono righe immutabili in `events`; `event_entities` ne registra le
  entità coinvolte e permette una cronologia completa senza creare duplicati.
- Le memorie appartengono a un solo personaggio e restano separate da canone,
  stato ed eventi. La presenza a un evento non crea automaticamente memoria.
- `memory_entities` rende filtrabili soggetti, fonti, luoghi ed entità correlate
  senza interpretare il testo; `memory_sources` conserva l'ordine delle memorie
  usate per un'inferenza.
- Le correzioni formano catene lineari append-only. `status` conserva la natura
  immutabile della nuova memoria; `is_current` ed `effective_status` sono
  calcolati verificando l'esistenza di un successore.
- La configurazione narrativa continua a essere versionata separatamente.
- Simulazione, generazione narrativa e provider LLM non sono implementati.

La GUI legge modelli tipizzati e non accede direttamente a SQL o dati tecnici.
La vista delle memorie usa query aggregate per fonti ed entità collegate.
