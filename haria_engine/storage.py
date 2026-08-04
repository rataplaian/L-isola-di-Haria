"""Persistenza SQLite e cronologia immutabile delle versioni."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path

from .errors import ErroreImportazione, MondoNonTrovato
from .models import FileSorgente, Mondo, VersioneMondo


def _adesso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _serializza_impostazioni(impostazioni: Mapping[str, str]) -> str:
    return json.dumps(dict(impostazioni), ensure_ascii=False, sort_keys=True)


def _deserializza_impostazioni(valore: str) -> dict[str, str]:
    dati = json.loads(valore)
    return {str(chiave): str(contenuto) for chiave, contenuto in dati.items()}


class ArchivioSQLite:
    """Archivio locale; ogni modifica crea una riga in ``world_versions``."""

    def __init__(self, percorso_database: str | Path) -> None:
        self.percorso_database = Path(percorso_database).expanduser().resolve()
        self.percorso_database.parent.mkdir(parents=True, exist_ok=True)
        self._connessione = sqlite3.connect(self.percorso_database)
        self._connessione.row_factory = sqlite3.Row
        self._connessione.execute("PRAGMA foreign_keys = ON")
        self._crea_schema()

    def _crea_schema(self) -> None:
        with self._connessione:
            self._connessione.executescript(
                """
                CREATE TABLE IF NOT EXISTS worlds (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    current_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS world_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    world_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    scenario TEXT NOT NULL,
                    narrative_settings TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE RESTRICT,
                    UNIQUE (world_id, version_number)
                );

                CREATE TABLE IF NOT EXISTS source_files (
                    world_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    content BLOB NOT NULL,
                    sha256 TEXT NOT NULL,
                    PRIMARY KEY (world_id, relative_path),
                    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE RESTRICT
                );

                CREATE INDEX IF NOT EXISTS idx_world_versions_world
                    ON world_versions(world_id, version_number DESC);

                PRAGMA user_version = 1;
                """
            )

    def importa_mondo(
        self,
        *,
        mondo_id: str,
        titolo: str,
        lingua: str,
        percorso_sorgente: str,
        scenario: str,
        impostazioni_narrative: Mapping[str, str],
        file_sorgente: Iterable[FileSorgente],
    ) -> Mondo:
        if self._connessione.execute(
            "SELECT 1 FROM worlds WHERE id = ?", (mondo_id,)
        ).fetchone():
            raise ErroreImportazione(
                f"Esiste già un mondo importato con identificatore “{mondo_id}”."
            )

        istante = _adesso_utc()
        with self._connessione:
            self._connessione.execute(
                """
                INSERT INTO worlds (
                    id, title, language, source_path, current_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (mondo_id, titolo, lingua, percorso_sorgente, istante, istante),
            )
            self._connessione.execute(
                """
                INSERT INTO world_versions (
                    world_id, version_number, scenario, narrative_settings,
                    created_at, reason
                ) VALUES (?, 1, ?, ?, ?, ?)
                """,
                (
                    mondo_id,
                    scenario,
                    _serializza_impostazioni(impostazioni_narrative),
                    istante,
                    "Importazione iniziale",
                ),
            )
            self._connessione.executemany(
                """
                INSERT INTO source_files (world_id, relative_path, content, sha256)
                VALUES (?, ?, ?, ?)
                """,
                (
                    (mondo_id, file.percorso_relativo, file.contenuto, file.sha256)
                    for file in file_sorgente
                ),
            )
        return self.carica_mondo(mondo_id)

    def elenca_mondi(self) -> list[Mondo]:
        righe = self._connessione.execute(
            "SELECT id FROM worlds ORDER BY updated_at DESC, title"
        ).fetchall()
        return [self.carica_mondo(riga["id"]) for riga in righe]

    def carica_mondo(self, mondo_id: str) -> Mondo:
        riga = self._connessione.execute(
            """
            SELECT w.id, w.title, w.language, w.source_path,
                   w.current_version, w.updated_at,
                   v.scenario, v.narrative_settings
            FROM worlds AS w
            JOIN world_versions AS v
              ON v.world_id = w.id AND v.version_number = w.current_version
            WHERE w.id = ?
            """,
            (mondo_id,),
        ).fetchone()
        if riga is None:
            raise MondoNonTrovato("Il mondo richiesto non è presente nell'archivio.")
        return Mondo(
            id=riga["id"],
            titolo=riga["title"],
            lingua=riga["language"],
            percorso_sorgente=riga["source_path"],
            versione_corrente=riga["current_version"],
            scenario=riga["scenario"],
            impostazioni_narrative=_deserializza_impostazioni(
                riga["narrative_settings"]
            ),
            aggiornato_il=riga["updated_at"],
        )

    def salva_versione(
        self,
        mondo_id: str,
        scenario: str,
        impostazioni_narrative: Mapping[str, str],
        motivo: str = "Salvataggio manuale",
    ) -> Mondo:
        self.carica_mondo(mondo_id)
        istante = _adesso_utc()
        with self._connessione:
            riga = self._connessione.execute(
                """
                SELECT COALESCE(MAX(version_number), 0) + 1 AS nuova_versione
                FROM world_versions WHERE world_id = ?
                """,
                (mondo_id,),
            ).fetchone()
            nuova_versione = int(riga["nuova_versione"])
            self._connessione.execute(
                """
                INSERT INTO world_versions (
                    world_id, version_number, scenario, narrative_settings,
                    created_at, reason
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    mondo_id,
                    nuova_versione,
                    scenario,
                    _serializza_impostazioni(impostazioni_narrative),
                    istante,
                    motivo,
                ),
            )
            self._connessione.execute(
                """
                UPDATE worlds SET current_version = ?, updated_at = ? WHERE id = ?
                """,
                (nuova_versione, istante, mondo_id),
            )
        return self.carica_mondo(mondo_id)

    def elenca_versioni(self, mondo_id: str) -> list[VersioneMondo]:
        self.carica_mondo(mondo_id)
        righe = self._connessione.execute(
            """
            SELECT version_number, created_at, reason, scenario, narrative_settings
            FROM world_versions
            WHERE world_id = ?
            ORDER BY version_number DESC
            """,
            (mondo_id,),
        ).fetchall()
        return [
            VersioneMondo(
                numero=riga["version_number"],
                creata_il=riga["created_at"],
                motivo=riga["reason"],
                scenario=riga["scenario"],
                impostazioni_narrative=_deserializza_impostazioni(
                    riga["narrative_settings"]
                ),
            )
            for riga in righe
        ]

    def carica_versione(self, mondo_id: str, numero: int) -> VersioneMondo:
        riga = self._connessione.execute(
            """
            SELECT version_number, created_at, reason, scenario, narrative_settings
            FROM world_versions WHERE world_id = ? AND version_number = ?
            """,
            (mondo_id, numero),
        ).fetchone()
        if riga is None:
            raise MondoNonTrovato(
                f"La versione {numero} non è presente nella cronologia."
            )
        return VersioneMondo(
            numero=riga["version_number"],
            creata_il=riga["created_at"],
            motivo=riga["reason"],
            scenario=riga["scenario"],
            impostazioni_narrative=_deserializza_impostazioni(
                riga["narrative_settings"]
            ),
        )

    def file_sorgente(self, mondo_id: str) -> list[FileSorgente]:
        self.carica_mondo(mondo_id)
        righe = self._connessione.execute(
            """
            SELECT relative_path, content, sha256
            FROM source_files WHERE world_id = ? ORDER BY relative_path
            """,
            (mondo_id,),
        ).fetchall()
        return [
            FileSorgente(
                percorso_relativo=riga["relative_path"],
                contenuto=bytes(riga["content"]),
                sha256=riga["sha256"],
            )
            for riga in righe
        ]

    def chiudi(self) -> None:
        self._connessione.close()

    def __enter__(self) -> "ArchivioSQLite":
        return self

    def __exit__(self, *_: object) -> None:
        self.chiudi()

