"""Persistenza SQLite e cronologia immutabile delle versioni."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path

from .errors import (
    ErroreImportazione,
    ErroreMigrazione,
    ErroreStatoMondo,
    MondoNonTrovato,
)
from .models import FileSorgente, Mondo, VersioneMondo
from .world_state import (
    AggiornamentoStato,
    EntitaImportata,
    EntitaMondo,
    EventoMondo,
    importa_entita_da_file,
)


def _adesso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _serializza_impostazioni(impostazioni: Mapping[str, str]) -> str:
    return json.dumps(dict(impostazioni), ensure_ascii=False, sort_keys=True)


def _deserializza_impostazioni(valore: str) -> dict[str, str]:
    dati = json.loads(valore)
    return {str(chiave): str(contenuto) for chiave, contenuto in dati.items()}


def _deserializza_oggetto(valore: str) -> dict[str, object]:
    dati = json.loads(valore)
    if not isinstance(dati, dict):
        raise ValueError("Il dato JSON interno non descrive un oggetto.")
    return dict(dati)


class ArchivioSQLite:
    """Archivio locale; ogni modifica crea una riga in ``world_versions``."""

    def __init__(self, percorso_database: str | Path) -> None:
        self.percorso_database = Path(percorso_database).expanduser().resolve()
        self.percorso_database.parent.mkdir(parents=True, exist_ok=True)
        self._connessione = sqlite3.connect(self.percorso_database)
        self._connessione.row_factory = sqlite3.Row
        self._connessione.execute("PRAGMA foreign_keys = ON")
        try:
            self._inizializza_schema()
        except Exception:
            self._connessione.close()
            raise

    def _inizializza_schema(self) -> None:
        versione = int(self._connessione.execute("PRAGMA user_version").fetchone()[0])
        if versione == 0:
            self._crea_schema_1()
            versione = 1
        if versione == 1:
            self._migra_da_1_a_2()
            versione = 2
        if versione != 2:
            raise ErroreMigrazione(
                f"La versione schema {versione} del database non è supportata."
            )

    def _crea_schema_1(self) -> None:
        istruzioni = (
            """
                CREATE TABLE IF NOT EXISTS worlds (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    current_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """,
            """
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
                )
            """,
            """
                CREATE TABLE IF NOT EXISTS source_files (
                    world_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    content BLOB NOT NULL,
                    sha256 TEXT NOT NULL,
                    PRIMARY KEY (world_id, relative_path),
                    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE RESTRICT
                )
            """,
            """
                CREATE INDEX IF NOT EXISTS idx_world_versions_world
                    ON world_versions(world_id, version_number DESC)
            """,
        )
        self._connessione.execute("BEGIN IMMEDIATE")
        try:
            for istruzione in istruzioni:
                self._connessione.execute(istruzione)
            self._connessione.execute("PRAGMA user_version = 1")
            self._connessione.commit()
        except sqlite3.Error:
            self._connessione.rollback()
            raise

    def _migra_da_1_a_2(self) -> None:
        istruzioni = (
            """
                CREATE TABLE world_entities (
                    world_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    canonical_data TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (world_id, entity_id),
                    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE RESTRICT,
                    CHECK (entity_type IN ('personaggio', 'luogo', 'oggetto'))
                )
            """,
            """
                CREATE TABLE entity_state (
                    world_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    location_id TEXT,
                    holder_id TEXT,
                    accessibility INTEGER NOT NULL,
                    condition TEXT,
                    state_data TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (world_id, entity_id),
                    FOREIGN KEY (world_id, entity_id)
                        REFERENCES world_entities(world_id, entity_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (world_id, location_id)
                        REFERENCES world_entities(world_id, entity_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (world_id, holder_id)
                        REFERENCES world_entities(world_id, entity_id)
                        ON DELETE RESTRICT,
                    CHECK (accessibility IN (0, 1)),
                    CHECK (version >= 1)
                )
            """,
            """
                CREATE TABLE events (
                    event_id TEXT PRIMARY KEY,
                    world_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    actor_id TEXT,
                    target_id TEXT,
                    location_id TEXT,
                    payload TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE RESTRICT,
                    FOREIGN KEY (world_id, actor_id)
                        REFERENCES world_entities(world_id, entity_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (world_id, target_id)
                        REFERENCES world_entities(world_id, entity_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (world_id, location_id)
                        REFERENCES world_entities(world_id, entity_id)
                        ON DELETE RESTRICT
                )
            """,
            """
                CREATE INDEX idx_world_entities_type
                    ON world_entities(world_id, entity_type, canonical_name)
            """,
            """
                CREATE INDEX idx_events_world_time
                    ON events(world_id, occurred_at, created_at)
            """,
            """
                CREATE INDEX idx_events_target
                    ON events(world_id, target_id, occurred_at)
            """,
            """
                CREATE TRIGGER events_append_only_update
                BEFORE UPDATE ON events
                BEGIN
                    SELECT RAISE(ABORT, 'Il registro eventi è immutabile: aggiornamento vietato.');
                END
            """,
            """
                CREATE TRIGGER events_append_only_delete
                BEFORE DELETE ON events
                BEGIN
                    SELECT RAISE(ABORT, 'Il registro eventi è immutabile: cancellazione vietata.');
                END
            """,
        )
        self._connessione.execute("BEGIN IMMEDIATE")
        try:
            for istruzione in istruzioni:
                self._connessione.execute(istruzione)
            mondi = self._connessione.execute(
                "SELECT id FROM worlds ORDER BY id"
            ).fetchall()
            for mondo in mondi:
                file_sorgente = self._file_sorgente_senza_validazione(mondo["id"])
                entita = importa_entita_da_file(file_sorgente)
                self._inserisci_entita(mondo["id"], entita)
            self._connessione.execute("PRAGMA user_version = 2")
            self._connessione.commit()
        except (ErroreImportazione, sqlite3.Error) as errore:
            self._connessione.rollback()
            raise ErroreMigrazione(
                "La migrazione allo schema 2 non è riuscita; il database è rimasto "
                "allo schema 1 senza dati parziali. Dettaglio: " + str(errore)
            ) from errore

    def _inserisci_entita(
        self, mondo_id: str, entita: Iterable[EntitaImportata]
    ) -> None:
        istante = _adesso_utc()
        elenco = list(entita)
        self._connessione.executemany(
            """
            INSERT INTO world_entities (
                world_id, entity_id, entity_type, canonical_name,
                canonical_data, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    mondo_id,
                    voce.entity_id,
                    voce.entity_type,
                    voce.canonical_name,
                    json.dumps(voce.canonical_data, ensure_ascii=False, sort_keys=True),
                    voce.status,
                    istante,
                    istante,
                )
                for voce in elenco
            ),
        )
        self._connessione.executemany(
            """
            INSERT INTO entity_state (
                world_id, entity_id, location_id, holder_id, accessibility,
                condition, state_data, version, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                (
                    mondo_id,
                    voce.entity_id,
                    voce.location_id,
                    voce.holder_id,
                    int(voce.accessibility),
                    voce.condition,
                    json.dumps(voce.state_data, ensure_ascii=False, sort_keys=True),
                    istante,
                )
                for voce in elenco
            ),
        )

    def _file_sorgente_senza_validazione(self, mondo_id: str) -> list[FileSorgente]:
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
        entita: Iterable[EntitaImportata],
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
            self._inserisci_entita(mondo_id, entita)
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

    def elenca_entita(
        self, mondo_id: str, entity_type: str | None = None
    ) -> list[EntitaMondo]:
        self.carica_mondo(mondo_id)
        parametri: list[object] = [mondo_id]
        filtro = ""
        if entity_type is not None:
            filtro = " AND e.entity_type = ?"
            parametri.append(entity_type)
        righe = self._connessione.execute(
            """
            SELECT e.world_id, e.entity_id, e.entity_type, e.canonical_name,
                   e.canonical_data, e.status, s.location_id, s.holder_id,
                   s.accessibility, s.condition, s.state_data, s.version,
                   s.updated_at
            FROM world_entities AS e
            JOIN entity_state AS s
              ON s.world_id = e.world_id AND s.entity_id = e.entity_id
            WHERE e.world_id = ?
            """
            + filtro
            + " ORDER BY e.entity_type, e.canonical_name",
            tuple(parametri),
        ).fetchall()
        return [self._entita_da_riga(riga) for riga in righe]

    def carica_entita(self, mondo_id: str, entity_id: str) -> EntitaMondo:
        self.carica_mondo(mondo_id)
        riga = self._connessione.execute(
            """
            SELECT e.world_id, e.entity_id, e.entity_type, e.canonical_name,
                   e.canonical_data, e.status, s.location_id, s.holder_id,
                   s.accessibility, s.condition, s.state_data, s.version,
                   s.updated_at
            FROM world_entities AS e
            JOIN entity_state AS s
              ON s.world_id = e.world_id AND s.entity_id = e.entity_id
            WHERE e.world_id = ? AND e.entity_id = ?
            """,
            (mondo_id, entity_id),
        ).fetchone()
        if riga is None:
            raise ErroreStatoMondo(
                f"L'entità richiesta “{entity_id}” non esiste o non possiede uno stato corrente."
            )
        return self._entita_da_riga(riga)

    def entita_possedute(
        self, mondo_id: str, holder_id: str
    ) -> list[EntitaMondo]:
        return [
            entita
            for entita in self.elenca_entita(mondo_id)
            if entita.holder_id == holder_id
        ]

    @staticmethod
    def _entita_da_riga(riga: sqlite3.Row) -> EntitaMondo:
        return EntitaMondo(
            world_id=riga["world_id"],
            entity_id=riga["entity_id"],
            entity_type=riga["entity_type"],
            canonical_name=riga["canonical_name"],
            canonical_data=_deserializza_oggetto(riga["canonical_data"]),
            status=riga["status"],
            location_id=riga["location_id"],
            holder_id=riga["holder_id"],
            accessibility=bool(riga["accessibility"]),
            condition=riga["condition"],
            state_data=_deserializza_oggetto(riga["state_data"]),
            version=int(riga["version"]),
            updated_at=riga["updated_at"],
        )

    def elenca_eventi(self, mondo_id: str) -> list[EventoMondo]:
        self.carica_mondo(mondo_id)
        righe = self._connessione.execute(
            """
            SELECT event_id, world_id, event_type, occurred_at, actor_id,
                   target_id, location_id, payload, reason, created_at
            FROM events WHERE world_id = ?
            ORDER BY occurred_at, created_at, event_id
            """,
            (mondo_id,),
        ).fetchall()
        return [self._evento_da_riga(riga) for riga in righe]

    def eventi_per_entita(
        self, mondo_id: str, entity_id: str
    ) -> list[EventoMondo]:
        self.carica_entita(mondo_id, entity_id)
        righe = self._connessione.execute(
            """
            SELECT event_id, world_id, event_type, occurred_at, actor_id,
                   target_id, location_id, payload, reason, created_at
            FROM events
            WHERE world_id = ?
              AND (actor_id = ? OR target_id = ? OR location_id = ?)
            ORDER BY occurred_at, created_at, event_id
            """,
            (mondo_id, entity_id, entity_id, entity_id),
        ).fetchall()
        return [self._evento_da_riga(riga) for riga in righe]

    @staticmethod
    def _evento_da_riga(riga: sqlite3.Row) -> EventoMondo:
        return EventoMondo(
            event_id=riga["event_id"],
            world_id=riga["world_id"],
            event_type=riga["event_type"],
            occurred_at=riga["occurred_at"],
            actor_id=riga["actor_id"],
            target_id=riga["target_id"],
            location_id=riga["location_id"],
            payload=_deserializza_oggetto(riga["payload"]),
            reason=riga["reason"],
            created_at=riga["created_at"],
        )

    def applica_evento_e_stati(
        self,
        evento: EventoMondo,
        aggiornamenti: Iterable[AggiornamentoStato],
    ) -> None:
        elenco = list(aggiornamenti)
        try:
            with self._connessione:
                self._inserisci_evento(evento)
                for aggiornamento in elenco:
                    aggiornato_canone = self._connessione.execute(
                        """
                        UPDATE world_entities
                        SET status = ?, updated_at = ?
                        WHERE world_id = ? AND entity_id = ?
                        """,
                        (
                            aggiornamento.status,
                            evento.created_at,
                            evento.world_id,
                            aggiornamento.entity_id,
                        ),
                    )
                    aggiornato_stato = self._connessione.execute(
                        """
                        UPDATE entity_state
                        SET location_id = ?, holder_id = ?, accessibility = ?,
                            condition = ?, state_data = ?, version = version + 1,
                            updated_at = ?
                        WHERE world_id = ? AND entity_id = ? AND version = ?
                        """,
                        (
                            aggiornamento.location_id,
                            aggiornamento.holder_id,
                            int(aggiornamento.accessibility),
                            aggiornamento.condition,
                            json.dumps(
                                aggiornamento.state_data,
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                            evento.created_at,
                            evento.world_id,
                            aggiornamento.entity_id,
                            aggiornamento.expected_version,
                        ),
                    )
                    if aggiornato_canone.rowcount != 1 or aggiornato_stato.rowcount != 1:
                        raise sqlite3.IntegrityError(
                            "Lo stato corrente è cambiato durante l'operazione."
                        )
        except sqlite3.Error as errore:
            raise ErroreStatoMondo(
                "L'operazione sullo stato non è riuscita: evento e stato sono "
                "rimasti invariati."
            ) from errore

    def registra_evento(self, evento: EventoMondo) -> None:
        try:
            with self._connessione:
                self._inserisci_evento(evento)
        except sqlite3.Error as errore:
            raise ErroreStatoMondo(
                "Non è stato possibile registrare l'evento descrittivo."
            ) from errore

    def _inserisci_evento(self, evento: EventoMondo) -> None:
        self._connessione.execute(
            """
            INSERT INTO events (
                event_id, world_id, event_type, occurred_at, actor_id,
                target_id, location_id, payload, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evento.event_id,
                evento.world_id,
                evento.event_type,
                evento.occurred_at,
                evento.actor_id,
                evento.target_id,
                evento.location_id,
                json.dumps(evento.payload, ensure_ascii=False, sort_keys=True),
                evento.reason,
                evento.created_at,
            ),
        )

    def file_sorgente(self, mondo_id: str) -> list[FileSorgente]:
        self.carica_mondo(mondo_id)
        return self._file_sorgente_senza_validazione(mondo_id)

    def chiudi(self) -> None:
        self._connessione.close()

    def __enter__(self) -> "ArchivioSQLite":
        return self

    def __exit__(self, *_: object) -> None:
        self.chiudi()

