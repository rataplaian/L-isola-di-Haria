# Haria Engine — Pacchetto iniziale

Questo pacchetto definisce le fondamenta del progetto **Haria Engine**.

Obiettivo: creare un software desktop locale, modulare e leggibile in italiano, capace di:

- importare Bibbie narrative;
- mostrare scenario, regole, stile e personaggi in italiano;
- permettere modifiche manuali senza toccare JSON;
- usare un LLM locale sostituibile;
- conservare memoria persistente, stato del mondo e cronologia;
- distinguere canone, stato corrente, eventi e ricordi soggettivi;
- evitare limiti editoriali nascosti o hardcoded;
- mantenere completa esportabilità e controllo dell'utente.

La cartella `docs/` contiene le specifiche.
La cartella `sample_world/` contiene una mini-Bibbia tecnica per i test.
La cartella `codex/` contiene il primo incarico operativo per Codex.

## Task 001 — Editor desktop italiano

Questa versione implementa esclusivamente il primo incarico: importa una mini-Bibbia da cartella, mostra e modifica lo scenario, conserva ogni salvataggio in SQLite, permette il ripristino e crea esportazioni senza modificare i file sorgente.

L'interfaccia non mostra JSON o tabelle del database. Le impostazioni narrative presenti nel pacchetto sono campi leggibili e modificabili in italiano.

## Requisiti

- Python 3.11 o successivo;
- Tkinter, incluso nell'installazione standard di Python per Windows e macOS;
- su Linux, se necessario, il pacchetto di sistema `python3-tk`.

Non sono richieste dipendenze Python esterne, servizi o account.

## Installazione

1. Installare Python 3.11 o successivo includendo Tkinter.
2. Aprire un terminale nella cartella del repository.
3. Non è necessario eseguire `pip install`.

## Avvio

Windows:

```powershell
py -3 -m haria_engine
```

In alternativa, se `python` è disponibile nel percorso di sistema:

```powershell
python -m haria_engine
```

macOS e Linux:

```bash
python3 -m haria_engine
```

Al primo avvio il database viene creato nella cartella dati locale dell'utente. È possibile indicare un database diverso:

```powershell
py -3 -m haria_engine --database C:\percorso\haria.sqlite3
```

## Uso

1. Selezionare **Importa mini-Bibbia** e scegliere `sample_world/` o un pacchetto compatibile.
2. Modificare lo scenario e, se presenti, le impostazioni narrative.
3. Selezionare **Salva nuova versione**: ogni salvataggio resta recuperabile.
4. Usare **Cronologia versioni** per ripristinare una versione; anche il ripristino crea una nuova versione.
5. Selezionare **Esporta mondo** e scegliere una cartella di destinazione.

## Test e verifica di avvio

Windows:

```powershell
py -3 -m unittest discover -s tests -v
py -3 -m haria_engine --check
```

macOS e Linux:

```bash
python3 -m unittest discover -s tests -v
python3 -m haria_engine --check
```

## Dati e sicurezza dei sorgenti

La mini-Bibbia selezionata viene soltanto letta. I suoi file non vengono modificati o cancellati. Lo stato corrente, le fotografie dei sorgenti e la cronologia sono conservati nel database SQLite; l'esportazione viene sempre creata in una nuova cartella.

Le motivazioni dello stack e i confini architetturali sono descritti in `docs/TECHNICAL_DECISIONS.md`. Lo stato puntuale del primo incarico è in `docs/TASK_001_STATUS.md`.
