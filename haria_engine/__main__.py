"""Punto di avvio da ``python -m haria_engine``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .app import avvia
from .errors import ErroreHaria
from .paths import database_predefinito
from .service import ServizioMondi


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Haria Engine — editor locale e versionato di mondi narrativi"
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=database_predefinito(),
        help="percorso del database SQLite locale",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verifica l'avvio senza aprire la finestra",
    )
    argomenti = parser.parse_args()
    if argomenti.check:
        try:
            with ServizioMondi(argomenti.database):
                pass
        except ErroreHaria as errore:
            print(f"Errore: {errore}", file=sys.stderr)
            raise SystemExit(1) from errore
        print("Verifica di avvio completata: archivio SQLite disponibile.")
        return
    avvia(argomenti.database)


if __name__ == "__main__":
    main()

