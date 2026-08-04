"""Percorsi dati multipiattaforma dell'applicazione."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def cartella_dati_predefinita() -> Path:
    personalizzata = os.environ.get("HARIA_ENGINE_DATA_DIR")
    if personalizzata:
        return Path(personalizzata).expanduser().resolve()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "HariaEngine"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "HariaEngine"
    base_linux = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base_linux / "haria-engine"


def database_predefinito() -> Path:
    return cartella_dati_predefinita() / "haria_engine.sqlite3"

