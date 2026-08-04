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
validate. `haria_engine/storage.py` applica evento e aggiornamenti dello stato
nella stessa transazione SQLite. Il registro è protetto anche da trigger contro
aggiornamenti e cancellazioni.

### 6. Memorie soggettive
Ogni personaggio conosce soltanto ciò che ha osservato, dedotto o appreso.

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

## Confini implementati nel Task 002

- Il canone originale resta in `canonical_data` e nelle fotografie sorgente.
- Lo stato operativo corrente resta in `entity_state`.
- Gli eventi sono righe immutabili in `events`.
- La configurazione narrativa continua a essere versionata separatamente.
- Memorie soggettive, simulazione e provider LLM non sono implementati.

La GUI legge modelli tipizzati e non accede direttamente a SQL o dati tecnici.
