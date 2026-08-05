"""Verifica manuale isolata di importazione, export, reimport e validazione."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from haria_engine.service import ServizioMondi


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="haria_task006_") as temporanea:
        radice = Path(temporanea)
        with ServizioMondi(radice / "prima.sqlite3") as servizio:
            mondo = servizio.importa(args.package)
            documenti = servizio.elenca_documenti(mondo.id)
            media = servizio.elenca_media(mondo.id)
            personaggi = servizio.stato_mondo.elenca_entita(mondo.id, "personaggio")
            rapporto = servizio.validazione.controlla_mondo(mondo.id)
            esportazione = servizio.esporta(mondo.id, radice / "export").cartella
        with ServizioMondi(radice / "seconda.sqlite3") as servizio:
            reimportato = servizio.importa_da_cartella(esportazione)
            rapporto_reimportato = servizio.validazione.controlla_mondo(reimportato.id)
            media_reimportati = servizio.elenca_media(reimportato.id)
        esito = {
            "world": mondo.titolo,
            "characters": len(personaggi),
            "documents": len(documenti),
            "media": len(media),
            "validation_passed": rapporto.superata,
            "validation_errors": len(rapporto.errori),
            "reimport_validation_passed": rapporto_reimportato.superata,
            "reimport_media": len(media_reimportati),
        }
        print(json.dumps(esito, ensure_ascii=False, indent=2))
        return 0 if rapporto.superata and rapporto_reimportato.superata else 1


if __name__ == "__main__":
    raise SystemExit(main())
