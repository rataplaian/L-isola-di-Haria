# Stato Codex Task 001

## Implementato

- importazione della mini-Bibbia da cartella;
- visualizzazione di titolo e scenario;
- editor testuale dello scenario;
- impostazioni narrative del pacchetto modificabili con etichette italiane;
- nuova versione SQLite per ogni salvataggio;
- cronologia e ripristino non distruttivo;
- esportazione in una nuova cartella;
- errori applicativi leggibili in italiano;
- conservazione integrale e non modifica dei file sorgente;
- test automatici dei criteri del task.

## Non implementato perché fuori ambito

- integrazione LLM;
- importazione della Haria Bible completa;
- simulazione narrativa, eventi e memorie soggettive;
- modifica diretta del database o visualizzazione del JSON nell'interfaccia;
- funzioni assegnate ai task successivi.

## Verifica

```powershell
python -m unittest discover -s tests -v
python -m haria_engine --check
python -m haria_engine
```

