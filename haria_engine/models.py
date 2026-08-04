"""Modelli tipizzati usati dal servizio e dall'interfaccia."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Mondo:
    id: str
    titolo: str
    lingua: str
    percorso_sorgente: str
    versione_corrente: int
    scenario: str
    impostazioni_narrative: dict[str, str]
    aggiornato_il: str


@dataclass(frozen=True, slots=True)
class VersioneMondo:
    numero: int
    creata_il: str
    motivo: str
    scenario: str
    impostazioni_narrative: dict[str, str]


@dataclass(frozen=True, slots=True)
class FileSorgente:
    percorso_relativo: str
    contenuto: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class RisultatoEsportazione:
    cartella: Path
    versione: int

