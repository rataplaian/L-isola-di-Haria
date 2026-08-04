# Decisioni tecniche — Task 001

## Confronto dello stack

| Opzione | Vantaggi | Svantaggi per il Task 001 |
| --- | --- | --- |
| Python + Tkinter + SQLite | Libreria standard, nessuna dipendenza applicativa, avvio semplice, test rapidi, supporto Windows/macOS/Linux | Aspetto grafico essenziale; su alcune distribuzioni Linux Tkinter va installato dal gestore di sistema |
| Electron + TypeScript | Ecosistema web maturo e interfacce ricche | Runtime pesante, molte dipendenze e maggiore superficie di manutenzione per un editor locale iniziale |
| Tauri + interfaccia web | Pacchetti più piccoli di Electron e buona portabilità | Richiede Rust, toolchain native e più livelli tecnici del necessario per il primo incarico |

## Decisione

Per il Task 001 viene scelto **Python 3.11+ con Tkinter, SQLite e `unittest`**, usando soltanto la libreria standard.

La scelta privilegia:

- semplicità di installazione e diagnosi;
- stabilità delle API utilizzate;
- persistenza SQLite disponibile senza servizi esterni;
- separazione testabile tra interfaccia, servizio applicativo e archivio;
- portabilità futura senza vincolare i dati a un framework grafico.

## Struttura

- `haria_engine/app.py`: interfaccia italiana; non mostra dati tecnici o JSON;
- `haria_engine/service.py`: importazione non distruttiva, salvataggio, ripristino ed esportazione;
- `haria_engine/storage.py`: schema SQLite e versioni immutabili;
- `haria_engine/models.py`: modelli tipizzati;
- `tests/test_task_001.py`: criteri automatici del primo incarico.

## Persistenza e non distruttività

All'importazione ogni file sorgente viene letto e conservato come fotografia nell'archivio SQLite. Le successive modifiche riguardano esclusivamente nuove righe di versione. L'esportazione crea una nuova cartella e non scrive mai nella mini-Bibbia sorgente.

Il ripristino non sposta un puntatore verso il passato: crea una nuova versione con il contenuto scelto, mantenendo recuperabili sia la versione precedente sia quella ripristinata.

## Confini intenzionali

Non sono inclusi LLM, simulazione, memorie dei personaggi, eventi di gioco, importazione della Bibbia completa o funzioni previste dai task successivi.

