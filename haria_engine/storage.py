"""Persistenza SQLite e cronologia immutabile delle versioni."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path

from .ai_models import (
    OLLAMA_URL_PREDEFINITO,
    PROVIDER_OLLAMA,
    TIMEOUT_PREDEFINITO,
    ConfigurazioneAI,
    valida_configurazione_ai,
)
from .errors import (
    ErroreConfigurazioneAI,
    ErroreImportazione,
    ErroreMemoria,
    ErroreMigrazione,
    ErroreStatoMondo,
    ErroreTurnoNarrativo,
    MondoNonTrovato,
)
from .memories import (
    AssociazioneMemoria,
    EntitaMemoria,
    FonteMemoria,
    MemoriaDaSalvare,
    MemoriaPersonaggio,
    importa_conoscenze_iniziali,
)
from .models import FileSorgente, Mondo, VersioneMondo
from .narrative_history import SessioneNarrativa, TurnoNarrativoPersistito
from .narrative_persistence import (
    PianoPersistenzaTurno,
    TurnoDaPersistire,
    crea_id_sessione,
)
from .package_models import DocumentoCanonico, MediaCanonico
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
        if versione == 2:
            self._migra_da_2_a_3()
            versione = 3
        if versione == 3:
            self._migra_da_3_a_4()
            versione = 4
        if versione == 4:
            self._migra_da_4_a_5()
            versione = 5
        if versione == 5:
            self._migra_da_5_a_6()
            versione = 6
        if versione != 6:
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
                    current_status TEXT NOT NULL,
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
                    UNIQUE (event_id, world_id),
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
                CREATE TABLE event_entities (
                    event_id TEXT NOT NULL,
                    world_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    PRIMARY KEY (event_id, entity_id, role),
                    FOREIGN KEY (event_id, world_id)
                        REFERENCES events(event_id, world_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (world_id, entity_id)
                        REFERENCES world_entities(world_id, entity_id)
                        ON DELETE RESTRICT,
                    CHECK (role IN ('actor', 'target', 'location', 'affected'))
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
                CREATE INDEX idx_event_entities_entity
                    ON event_entities(world_id, entity_id, event_id)
            """,
            """
                CREATE TRIGGER events_append_only_update
                BEFORE UPDATE ON events
                BEGIN
                    SELECT RAISE(ABORT, 'Il registro eventi è immutabile: aggiornamento vietato.');
                END
            """,
            """
                CREATE TRIGGER event_entities_append_only_update
                BEFORE UPDATE ON event_entities
                BEGIN
                    SELECT RAISE(ABORT, 'Le associazioni degli eventi sono immutabili: aggiornamento vietato.');
                END
            """,
            """
                CREATE TRIGGER event_entities_append_only_delete
                BEFORE DELETE ON event_entities
                BEGIN
                    SELECT RAISE(ABORT, 'Le associazioni degli eventi sono immutabili: cancellazione vietata.');
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

    def _migra_da_3_a_4(self) -> None:
        self._connessione.execute("BEGIN IMMEDIATE")
        try:
            self._connessione.execute(
                """
                CREATE TABLE ai_settings (
                    settings_id INTEGER PRIMARY KEY,
                    provider TEXT NOT NULL,
                    ollama_base_url TEXT NOT NULL,
                    ollama_model TEXT NOT NULL,
                    ollama_timeout_seconds INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    CHECK (settings_id = 1),
                    CHECK (provider = 'ollama'),
                    CHECK (
                        typeof(ollama_timeout_seconds) = 'integer'
                        AND ollama_timeout_seconds BETWEEN 1 AND 300
                    )
                )
                """
            )
            self._connessione.execute(
                """
                INSERT INTO ai_settings (
                    settings_id, provider, ollama_base_url, ollama_model,
                    ollama_timeout_seconds, updated_at
                ) VALUES (1, ?, ?, '', ?, ?)
                """,
                (
                    PROVIDER_OLLAMA,
                    OLLAMA_URL_PREDEFINITO,
                    TIMEOUT_PREDEFINITO,
                    _adesso_utc(),
                ),
            )
            self._connessione.execute("PRAGMA user_version = 4")
            self._connessione.commit()
        except sqlite3.Error as errore:
            self._connessione.rollback()
            raise ErroreMigrazione(
                "La migrazione allo schema 4 non è riuscita; il database è "
                "rimasto allo schema 3 senza dati parziali."
            ) from errore

    def _migra_da_4_a_5(self) -> None:
        """Aggiunge l'indice consultabile senza reinterpretare i mondi esistenti."""

        istruzioni = (
            """
                CREATE TABLE canonical_documents (
                    world_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    metadata TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    PRIMARY KEY (world_id, document_id),
                    UNIQUE (world_id, relative_path),
                    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE RESTRICT,
                    FOREIGN KEY (world_id, relative_path)
                        REFERENCES source_files(world_id, relative_path) ON DELETE RESTRICT,
                    CHECK (length(trim(document_id)) > 0),
                    CHECK (length(trim(document_type)) > 0),
                    CHECK (sort_order >= 0)
                )
            """,
            """
                CREATE TABLE media_assets (
                    world_id TEXT NOT NULL,
                    media_id TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    title TEXT NOT NULL,
                    alt_text TEXT NOT NULL,
                    entity_id TEXT,
                    sort_order INTEGER NOT NULL,
                    metadata TEXT NOT NULL,
                    PRIMARY KEY (world_id, media_id),
                    UNIQUE (world_id, relative_path),
                    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE RESTRICT,
                    FOREIGN KEY (world_id, relative_path)
                        REFERENCES source_files(world_id, relative_path) ON DELETE RESTRICT,
                    FOREIGN KEY (world_id, entity_id)
                        REFERENCES world_entities(world_id, entity_id) ON DELETE RESTRICT,
                    CHECK (length(trim(media_id)) > 0),
                    CHECK (length(trim(media_type)) > 0),
                    CHECK (length(trim(mime_type)) > 0),
                    CHECK (sort_order >= 0)
                )
            """,
            """
                CREATE INDEX idx_canonical_documents_order
                    ON canonical_documents(world_id, document_type, sort_order, title)
            """,
            """
                CREATE INDEX idx_media_assets_order
                    ON media_assets(world_id, sort_order, title)
            """,
        )
        self._connessione.execute("BEGIN IMMEDIATE")
        try:
            for istruzione in istruzioni:
                self._connessione.execute(istruzione)
            self._connessione.execute("PRAGMA user_version = 5")
            self._connessione.commit()
        except sqlite3.Error as errore:
            self._connessione.rollback()
            raise ErroreMigrazione(
                "La migrazione allo schema 5 non è riuscita; il database è "
                "rimasto allo schema 4 senza dati parziali."
            ) from errore

    def _migra_da_5_a_6(self) -> None:
        """Aggiunge cronologia e collegamenti dei turni in una transazione."""

        istruzioni = (
            """
                CREATE TABLE narrative_sessions (
                    session_id TEXT PRIMARY KEY,
                    world_id TEXT NOT NULL UNIQUE,
                    current_time TEXT NOT NULL,
                    next_turn_number INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (session_id, world_id),
                    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE RESTRICT,
                    CHECK (typeof(next_turn_number) = 'integer' AND next_turn_number >= 1)
                )
            """,
            """
                CREATE TABLE narrative_turns (
                    turn_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    world_id TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    user_input TEXT NOT NULL,
                    narrative TEXT NOT NULL,
                    elapsed_minutes INTEGER NOT NULL,
                    world_time_before TEXT NOT NULL,
                    world_time_after TEXT NOT NULL,
                    prompt_text TEXT NOT NULL,
                    raw_model_output TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (session_id, sequence_number),
                    UNIQUE (turn_id, world_id),
                    FOREIGN KEY (session_id, world_id)
                        REFERENCES narrative_sessions(session_id, world_id)
                        ON DELETE RESTRICT,
                    CHECK (typeof(sequence_number) = 'integer' AND sequence_number >= 1),
                    CHECK (
                        typeof(elapsed_minutes) = 'integer'
                        AND elapsed_minutes BETWEEN 0 AND 10080
                    )
                )
            """,
            """
                CREATE TABLE narrative_turn_events (
                    turn_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    world_id TEXT NOT NULL,
                    operation_index INTEGER NOT NULL,
                    PRIMARY KEY (turn_id, event_id),
                    UNIQUE (turn_id, operation_index),
                    FOREIGN KEY (turn_id, world_id)
                        REFERENCES narrative_turns(turn_id, world_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (event_id, world_id)
                        REFERENCES events(event_id, world_id)
                        ON DELETE RESTRICT,
                    CHECK (operation_index >= 0)
                )
            """,
            """
                CREATE TABLE narrative_turn_memories (
                    turn_id TEXT NOT NULL,
                    memory_id TEXT NOT NULL,
                    world_id TEXT NOT NULL,
                    memory_index INTEGER NOT NULL,
                    PRIMARY KEY (turn_id, memory_id),
                    UNIQUE (turn_id, memory_index),
                    FOREIGN KEY (turn_id, world_id)
                        REFERENCES narrative_turns(turn_id, world_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (memory_id, world_id)
                        REFERENCES memories(memory_id, world_id)
                        ON DELETE RESTRICT,
                    CHECK (memory_index >= 0)
                )
            """,
            """
                CREATE INDEX idx_narrative_turns_session
                    ON narrative_turns(session_id, sequence_number)
            """,
            """
                CREATE INDEX idx_narrative_turn_events_turn
                    ON narrative_turn_events(turn_id, operation_index)
            """,
            """
                CREATE INDEX idx_narrative_turn_memories_turn
                    ON narrative_turn_memories(turn_id, memory_index)
            """,
            """
                CREATE TRIGGER narrative_sessions_identity_immutable
                BEFORE UPDATE ON narrative_sessions
                WHEN NEW.session_id <> OLD.session_id
                  OR NEW.world_id <> OLD.world_id
                  OR NEW.created_at <> OLD.created_at
                BEGIN
                    SELECT RAISE(ABORT, 'Identità della sessione narrativa immutabile.');
                END
            """,
            """
                CREATE TRIGGER narrative_turns_append_only_update
                BEFORE UPDATE ON narrative_turns
                BEGIN
                    SELECT RAISE(ABORT, 'Turni narrativi immutabili: aggiornamento vietato.');
                END
            """,
            """
                CREATE TRIGGER narrative_turns_append_only_delete
                BEFORE DELETE ON narrative_turns
                BEGIN
                    SELECT RAISE(ABORT, 'Turni narrativi immutabili: cancellazione vietata.');
                END
            """,
            """
                CREATE TRIGGER narrative_turn_events_append_only_update
                BEFORE UPDATE ON narrative_turn_events
                BEGIN
                    SELECT RAISE(ABORT, 'Collegamenti turno-evento immutabili.');
                END
            """,
            """
                CREATE TRIGGER narrative_turn_events_append_only_delete
                BEFORE DELETE ON narrative_turn_events
                BEGIN
                    SELECT RAISE(ABORT, 'Collegamenti turno-evento non cancellabili.');
                END
            """,
            """
                CREATE TRIGGER narrative_turn_memories_append_only_update
                BEFORE UPDATE ON narrative_turn_memories
                BEGIN
                    SELECT RAISE(ABORT, 'Collegamenti turno-memoria immutabili.');
                END
            """,
            """
                CREATE TRIGGER narrative_turn_memories_append_only_delete
                BEFORE DELETE ON narrative_turn_memories
                BEGIN
                    SELECT RAISE(ABORT, 'Collegamenti turno-memoria non cancellabili.');
                END
            """,
        )
        self._connessione.execute("BEGIN IMMEDIATE")
        try:
            for istruzione in istruzioni:
                self._connessione.execute(istruzione)
            self._connessione.execute("PRAGMA user_version = 6")
            self._connessione.commit()
        except sqlite3.Error as errore:
            self._connessione.rollback()
            raise ErroreMigrazione(
                "La migrazione allo schema 6 non è riuscita; il database è "
                "rimasto allo schema 5 senza dati parziali."
            ) from errore

    def _migra_da_2_a_3(self) -> None:
        istruzioni = (
            """
                CREATE TABLE memories (
                    memory_id TEXT PRIMARY KEY,
                    world_id TEXT NOT NULL,
                    character_id TEXT NOT NULL,
                    event_id TEXT,
                    knowledge_type TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_entity_id TEXT,
                    learned_at TEXT NOT NULL,
                    certainty INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    interpretation TEXT,
                    associated_emotion TEXT,
                    status TEXT NOT NULL,
                    supersedes_memory_id TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (memory_id, world_id),
                    UNIQUE (memory_id, world_id, character_id),
                    FOREIGN KEY (world_id, character_id)
                        REFERENCES world_entities(world_id, entity_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (event_id, world_id)
                        REFERENCES events(event_id, world_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (world_id, source_entity_id)
                        REFERENCES world_entities(world_id, entity_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (supersedes_memory_id, world_id, character_id)
                        REFERENCES memories(memory_id, world_id, character_id)
                        ON DELETE RESTRICT,
                    CHECK (knowledge_type IN (
                        'observed_fact', 'reported_fact', 'inference',
                        'belief', 'canonical_knowledge'
                    )),
                    CHECK (source_type IN (
                        'direct_observation', 'told_by_character', 'inference',
                        'imported_background', 'self_experience'
                    )),
                    CHECK (status IN (
                        'active', 'corrected', 'contradicted', 'superseded'
                    )),
                    CHECK (typeof(certainty) = 'integer' AND certainty BETWEEN 0 AND 100),
                    CHECK (length(trim(content)) > 0),
                    CHECK (
                        supersedes_memory_id IS NULL
                        OR supersedes_memory_id <> memory_id
                    )
                )
            """,
            """
                CREATE TABLE memory_entities (
                    memory_id TEXT NOT NULL,
                    world_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    PRIMARY KEY (memory_id, entity_id, role),
                    FOREIGN KEY (memory_id, world_id)
                        REFERENCES memories(memory_id, world_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (world_id, entity_id)
                        REFERENCES world_entities(world_id, entity_id)
                        ON DELETE RESTRICT,
                    CHECK (role IN ('subject', 'source', 'location', 'related'))
                )
            """,
            """
                CREATE TABLE memory_sources (
                    memory_id TEXT NOT NULL,
                    source_memory_id TEXT NOT NULL,
                    world_id TEXT NOT NULL,
                    character_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY (memory_id, source_memory_id),
                    UNIQUE (memory_id, position),
                    FOREIGN KEY (memory_id, world_id, character_id)
                        REFERENCES memories(memory_id, world_id, character_id)
                        ON DELETE RESTRICT,
                    FOREIGN KEY (source_memory_id, world_id, character_id)
                        REFERENCES memories(memory_id, world_id, character_id)
                        ON DELETE RESTRICT,
                    CHECK (memory_id <> source_memory_id),
                    CHECK (typeof(position) = 'integer' AND position > 0)
                )
            """,
            """
                CREATE INDEX idx_memories_character_time
                    ON memories(world_id, character_id, learned_at, created_at)
            """,
            """
                CREATE INDEX idx_memories_event
                    ON memories(world_id, event_id)
            """,
            """
                CREATE UNIQUE INDEX idx_memories_single_successor
                    ON memories(supersedes_memory_id)
                    WHERE supersedes_memory_id IS NOT NULL
            """,
            """
                CREATE INDEX idx_memory_entities_entity
                    ON memory_entities(world_id, entity_id, memory_id)
            """,
            """
                CREATE INDEX idx_memory_sources_source
                    ON memory_sources(source_memory_id, memory_id)
            """,
            """
                CREATE TRIGGER memories_character_must_be_character
                BEFORE INSERT ON memories
                WHEN NOT EXISTS (
                    SELECT 1 FROM world_entities
                    WHERE world_id = NEW.world_id
                      AND entity_id = NEW.character_id
                      AND entity_type = 'personaggio'
                )
                BEGIN
                    SELECT RAISE(ABORT, 'La memoria deve appartenere a un personaggio valido.');
                END
            """,
            """
                CREATE TRIGGER memories_append_only_update
                BEFORE UPDATE ON memories
                BEGIN
                    SELECT RAISE(ABORT, 'Le memorie sono immutabili: aggiornamento vietato.');
                END
            """,
            """
                CREATE TRIGGER memories_append_only_delete
                BEFORE DELETE ON memories
                BEGIN
                    SELECT RAISE(ABORT, 'Le memorie sono immutabili: cancellazione vietata.');
                END
            """,
            """
                CREATE TRIGGER memory_entities_append_only_update
                BEFORE UPDATE ON memory_entities
                BEGIN
                    SELECT RAISE(ABORT, 'Le associazioni delle memorie sono immutabili: aggiornamento vietato.');
                END
            """,
            """
                CREATE TRIGGER memory_entities_append_only_delete
                BEFORE DELETE ON memory_entities
                BEGIN
                    SELECT RAISE(ABORT, 'Le associazioni delle memorie sono immutabili: cancellazione vietata.');
                END
            """,
            """
                CREATE TRIGGER memory_sources_append_only_update
                BEFORE UPDATE ON memory_sources
                BEGIN
                    SELECT RAISE(ABORT, 'Le fonti delle memorie sono immutabili: aggiornamento vietato.');
                END
            """,
            """
                CREATE TRIGGER memory_sources_append_only_delete
                BEFORE DELETE ON memory_sources
                BEGIN
                    SELECT RAISE(ABORT, 'Le fonti delle memorie sono immutabili: cancellazione vietata.');
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
                memorie = importa_conoscenze_iniziali(
                    self._file_sorgente_senza_validazione(mondo["id"]),
                    mondo["id"],
                )
                self._inserisci_memorie_iniziali(memorie)
            self._connessione.execute("PRAGMA user_version = 3")
            self._connessione.commit()
        except (ErroreImportazione, sqlite3.Error) as errore:
            self._connessione.rollback()
            raise ErroreMigrazione(
                "La migrazione allo schema 3 non è riuscita; il database è rimasto "
                "allo schema 2 senza dati parziali. Dettaglio: " + str(errore)
            ) from errore

    def _inserisci_memorie_iniziali(
        self, memorie: Iterable[MemoriaDaSalvare]
    ) -> None:
        self._connessione.executemany(
            """
            INSERT INTO memories (
                memory_id, world_id, character_id, event_id, knowledge_type,
                source_type, source_entity_id, learned_at, certainty, content,
                interpretation, associated_emotion, status,
                supersedes_memory_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (self._parametri_memoria(memoria) for memoria in memorie),
        )

    def _inserisci_entita(
        self, mondo_id: str, entita: Iterable[EntitaImportata]
    ) -> None:
        istante = _adesso_utc()
        elenco = list(entita)
        self._connessione.executemany(
            """
            INSERT INTO world_entities (
                world_id, entity_id, entity_type, canonical_name,
                canonical_data, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    mondo_id,
                    voce.entity_id,
                    voce.entity_type,
                    voce.canonical_name,
                    json.dumps(voce.canonical_data, ensure_ascii=False, sort_keys=True),
                    istante,
                    istante,
                )
                for voce in elenco
            ),
        )
        self._connessione.executemany(
            """
            INSERT INTO entity_state (
                world_id, entity_id, current_status, location_id, holder_id, accessibility,
                condition, state_data, version, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                (
                    mondo_id,
                    voce.entity_id,
                    voce.status,
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
        documenti: Iterable[DocumentoCanonico] = (),
        media: Iterable[MediaCanonico] = (),
    ) -> Mondo:
        try:
            return self._importa_mondo_transazionale(
                mondo_id=mondo_id,
                titolo=titolo,
                lingua=lingua,
                percorso_sorgente=percorso_sorgente,
                scenario=scenario,
                impostazioni_narrative=impostazioni_narrative,
                file_sorgente=file_sorgente,
                entita=entita,
                documenti=documenti,
                media=media,
            )
        except sqlite3.Error as errore:
            raise ErroreImportazione(
                "L'importazione non è riuscita; nessun dato parziale è stato salvato."
            ) from errore

    def _importa_mondo_transazionale(
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
        documenti: Iterable[DocumentoCanonico] = (),
        media: Iterable[MediaCanonico] = (),
    ) -> Mondo:
        elenco_file_sorgente = list(file_sorgente)
        elenco_entita = list(entita)
        elenco_documenti = list(documenti)
        elenco_media = list(media)
        memorie_iniziali = importa_conoscenze_iniziali(
            elenco_file_sorgente, mondo_id
        )
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
                    for file in elenco_file_sorgente
                ),
            )
            self._inserisci_entita(mondo_id, elenco_entita)
            self._inserisci_memorie_iniziali(memorie_iniziali)
            self._connessione.executemany(
                """
                INSERT INTO canonical_documents (
                    world_id, document_id, document_type, title, relative_path,
                    content, sort_order, metadata, sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        voce.world_id, voce.document_id, voce.document_type,
                        voce.title, voce.relative_path, voce.content,
                        voce.sort_order,
                        json.dumps(dict(voce.metadata), ensure_ascii=False, sort_keys=True),
                        voce.sha256,
                    )
                    for voce in elenco_documenti
                ),
            )
            self._connessione.executemany(
                """
                INSERT INTO media_assets (
                    world_id, media_id, relative_path, media_type, mime_type,
                    sha256, title, alt_text, entity_id, sort_order, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        voce.world_id, voce.media_id, voce.relative_path,
                        voce.media_type, voce.mime_type, voce.sha256, voce.title,
                        voce.alt_text, voce.entity_id, voce.sort_order,
                        json.dumps(dict(voce.metadata), ensure_ascii=False, sort_keys=True),
                    )
                    for voce in elenco_media
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
                   e.canonical_data, s.current_status AS status,
                   s.location_id, s.holder_id,
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
                   e.canonical_data, s.current_status AS status,
                   s.location_id, s.holder_id,
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

    def carica_evento(self, mondo_id: str, event_id: str) -> EventoMondo:
        self.carica_mondo(mondo_id)
        riga = self._connessione.execute(
            """
            SELECT event_id, world_id, event_type, occurred_at, actor_id,
                   target_id, location_id, payload, reason, created_at
            FROM events WHERE world_id = ? AND event_id = ?
            """,
            (mondo_id, event_id),
        ).fetchone()
        if riga is None:
            raise ErroreMemoria(
                "L'evento richiesto non esiste nel mondo selezionato."
            )
        return self._evento_da_riga(riga)

    def eventi_per_entita(
        self, mondo_id: str, entity_id: str
    ) -> list[EventoMondo]:
        self.carica_entita(mondo_id, entity_id)
        righe = self._connessione.execute(
            """
            SELECT e.event_id, e.world_id, e.event_type, e.occurred_at,
                   e.actor_id, e.target_id, e.location_id, e.payload,
                   e.reason, e.created_at
            FROM events AS e
            WHERE e.world_id = ?
              AND EXISTS (
                  SELECT 1
                  FROM event_entities AS ee
                  WHERE ee.event_id = e.event_id
                    AND ee.world_id = e.world_id
                    AND ee.entity_id = ?
              )
            ORDER BY e.occurred_at, e.created_at, e.event_id
            """,
            (mondo_id, entity_id),
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

    def registra_memoria(
        self,
        memoria: MemoriaDaSalvare,
        associazioni: Iterable[AssociazioneMemoria],
        fonti: Iterable[FonteMemoria],
    ) -> None:
        elenco_associazioni = list(associazioni)
        elenco_fonti = list(fonti)
        try:
            with self._connessione:
                self._inserisci_memoria(memoria)
                self._connessione.executemany(
                    """
                    INSERT INTO memory_entities (
                        memory_id, world_id, entity_id, role
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        (
                            memoria.memory_id,
                            memoria.world_id,
                            associazione.entity_id,
                            associazione.role,
                        )
                        for associazione in elenco_associazioni
                    ),
                )
                self._connessione.executemany(
                    """
                    INSERT INTO memory_sources (
                        memory_id, source_memory_id, world_id,
                        character_id, position
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        (
                            memoria.memory_id,
                            fonte.source_memory_id,
                            memoria.world_id,
                            memoria.character_id,
                            fonte.position,
                        )
                        for fonte in elenco_fonti
                    ),
                )
        except sqlite3.Error as errore:
            raise ErroreMemoria(
                "La memoria non è stata salvata: memoria, associazioni e fonti "
                "sono rimaste invariate."
            ) from errore

    def _inserisci_memoria(self, memoria: MemoriaDaSalvare) -> None:
        self._connessione.execute(
            """
            INSERT INTO memories (
                memory_id, world_id, character_id, event_id, knowledge_type,
                source_type, source_entity_id, learned_at, certainty, content,
                interpretation, associated_emotion, status,
                supersedes_memory_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._parametri_memoria(memoria),
        )

    @staticmethod
    def _parametri_memoria(memoria: MemoriaDaSalvare) -> tuple[object, ...]:
        return (
            memoria.memory_id,
            memoria.world_id,
            memoria.character_id,
            memoria.event_id,
            memoria.knowledge_type,
            memoria.source_type,
            memoria.source_entity_id,
            memoria.learned_at,
            memoria.certainty,
            memoria.content,
            memoria.interpretation,
            memoria.associated_emotion,
            memoria.status,
            memoria.supersedes_memory_id,
            memoria.created_at,
        )

    def carica_memoria(
        self, mondo_id: str, memory_id: str
    ) -> MemoriaPersonaggio:
        self.carica_mondo(mondo_id)
        righe = self._seleziona_memorie(
            "m.world_id = ? AND m.memory_id = ?",
            (mondo_id, memory_id),
        )
        if not righe:
            raise ErroreMemoria(
                "La memoria richiesta non esiste nel mondo selezionato."
            )
        return self._completa_memorie(righe)[0]

    def elenca_memorie_personaggio(
        self,
        mondo_id: str,
        character_id: str,
        *,
        event_id: str | None = None,
        entity_id: str | None = None,
        source_type: str | None = None,
        solo_correnti: bool = True,
    ) -> list[MemoriaPersonaggio]:
        condizioni = ["m.world_id = ?", "m.character_id = ?"]
        parametri: list[object] = [mondo_id, character_id]
        if event_id is not None:
            condizioni.append("m.event_id = ?")
            parametri.append(event_id)
        if source_type is not None:
            condizioni.append("m.source_type = ?")
            parametri.append(source_type)
        if entity_id is not None:
            condizioni.append(
                """
                EXISTS (
                    SELECT 1 FROM memory_entities AS me
                    WHERE me.memory_id = m.memory_id
                      AND me.world_id = m.world_id
                      AND me.entity_id = ?
                )
                """
            )
            parametri.append(entity_id)
        if solo_correnti:
            condizioni.append(
                """
                NOT EXISTS (
                    SELECT 1 FROM memories AS successiva
                    WHERE successiva.world_id = m.world_id
                      AND successiva.character_id = m.character_id
                      AND successiva.supersedes_memory_id = m.memory_id
                )
                """
            )
        righe = self._seleziona_memorie(
            " AND ".join(condizioni), tuple(parametri)
        )
        return self._completa_memorie(righe)

    def _seleziona_memorie(
        self, condizione: str, parametri: tuple[object, ...]
    ) -> list[sqlite3.Row]:
        return self._connessione.execute(
            f"""
            SELECT m.memory_id, m.world_id, m.character_id, m.event_id,
                   m.knowledge_type, m.source_type, m.source_entity_id,
                   fonte.canonical_name AS source_name, m.learned_at,
                   m.certainty, m.content, m.interpretation,
                   m.associated_emotion, m.status, m.supersedes_memory_id,
                   m.created_at,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM memories AS successiva
                       WHERE successiva.world_id = m.world_id
                         AND successiva.character_id = m.character_id
                         AND successiva.supersedes_memory_id = m.memory_id
                   ) THEN 0 ELSE 1 END AS is_current,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM memories AS successiva
                       WHERE successiva.world_id = m.world_id
                         AND successiva.character_id = m.character_id
                         AND successiva.supersedes_memory_id = m.memory_id
                   ) THEN 'superseded' ELSE m.status END AS effective_status
            FROM memories AS m
            LEFT JOIN world_entities AS fonte
              ON fonte.world_id = m.world_id
             AND fonte.entity_id = m.source_entity_id
            WHERE {condizione}
            ORDER BY m.learned_at, m.created_at, m.memory_id
            """,
            parametri,
        ).fetchall()

    def _completa_memorie(
        self, righe: list[sqlite3.Row]
    ) -> list[MemoriaPersonaggio]:
        if not righe:
            return []
        memory_ids = [riga["memory_id"] for riga in righe]
        segnaposto = ",".join("?" for _ in memory_ids)
        righe_entita = self._connessione.execute(
            f"""
            SELECT me.memory_id, me.entity_id, me.role, e.canonical_name
            FROM memory_entities AS me
            JOIN world_entities AS e
              ON e.world_id = me.world_id AND e.entity_id = me.entity_id
            WHERE me.memory_id IN ({segnaposto})
            ORDER BY me.memory_id, me.role, e.canonical_name
            """,
            tuple(memory_ids),
        ).fetchall()
        righe_fonti = self._connessione.execute(
            f"""
            SELECT memory_id, source_memory_id
            FROM memory_sources
            WHERE memory_id IN ({segnaposto})
            ORDER BY memory_id, position
            """,
            tuple(memory_ids),
        ).fetchall()
        entita_per_memoria: dict[str, list[EntitaMemoria]] = {
            memory_id: [] for memory_id in memory_ids
        }
        for riga in righe_entita:
            entita_per_memoria[riga["memory_id"]].append(
                EntitaMemoria(
                    entity_id=riga["entity_id"],
                    role=riga["role"],
                    canonical_name=riga["canonical_name"],
                )
            )
        fonti_per_memoria: dict[str, list[str]] = {
            memory_id: [] for memory_id in memory_ids
        }
        for riga in righe_fonti:
            fonti_per_memoria[riga["memory_id"]].append(riga["source_memory_id"])
        return [
            MemoriaPersonaggio(
                memory_id=riga["memory_id"],
                world_id=riga["world_id"],
                character_id=riga["character_id"],
                event_id=riga["event_id"],
                knowledge_type=riga["knowledge_type"],
                source_type=riga["source_type"],
                source_entity_id=riga["source_entity_id"],
                source_name=riga["source_name"],
                learned_at=riga["learned_at"],
                certainty=int(riga["certainty"]),
                content=riga["content"],
                interpretation=riga["interpretation"],
                associated_emotion=riga["associated_emotion"],
                status=riga["status"],
                supersedes_memory_id=riga["supersedes_memory_id"],
                created_at=riga["created_at"],
                is_current=bool(riga["is_current"]),
                effective_status=riga["effective_status"],
                entities=tuple(entita_per_memoria[riga["memory_id"]]),
                source_memory_ids=tuple(fonti_per_memoria[riga["memory_id"]]),
            )
            for riga in righe
        ]

    def applica_evento_e_stati(
        self,
        evento: EventoMondo,
        aggiornamenti: Iterable[AggiornamentoStato],
    ) -> None:
        elenco = list(aggiornamenti)
        try:
            with self._connessione:
                self._inserisci_evento(
                    evento,
                    (aggiornamento.entity_id for aggiornamento in elenco),
                )
                for aggiornamento in elenco:
                    aggiornato_stato = self._connessione.execute(
                        """
                        UPDATE entity_state
                        SET current_status = ?, location_id = ?, holder_id = ?,
                            accessibility = ?, condition = ?, state_data = ?,
                            version = version + 1, updated_at = ?
                        WHERE world_id = ? AND entity_id = ? AND version = ?
                        """,
                        (
                            aggiornamento.status,
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
                    if aggiornato_stato.rowcount != 1:
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
                self._inserisci_evento(evento, ())
        except sqlite3.Error as errore:
            raise ErroreStatoMondo(
                "Non è stato possibile registrare l'evento descrittivo."
            ) from errore

    def _inserisci_evento(
        self,
        evento: EventoMondo,
        entita_interessate: Iterable[str],
    ) -> None:
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
        associazioni: set[tuple[str, str]] = set()
        for entity_id, ruolo in (
            (evento.actor_id, "actor"),
            (evento.target_id, "target"),
            (evento.location_id, "location"),
        ):
            if entity_id is not None:
                associazioni.add((entity_id, ruolo))
        associazioni.update(
            (entity_id, "affected") for entity_id in entita_interessate
        )
        self._connessione.executemany(
            """
            INSERT INTO event_entities (event_id, world_id, entity_id, role)
            VALUES (?, ?, ?, ?)
            """,
            (
                (evento.event_id, evento.world_id, entity_id, ruolo)
                for entity_id, ruolo in sorted(associazioni)
            ),
        )

    def carica_sessione_narrativa(
        self, mondo_id: str
    ) -> SessioneNarrativa | None:
        self.carica_mondo(mondo_id)
        riga = self._connessione.execute(
            """
            SELECT session_id, world_id,
                   narrative_sessions.current_time AS current_time,
                   next_turn_number,
                   created_at, updated_at
            FROM narrative_sessions WHERE world_id = ?
            """,
            (mondo_id,),
        ).fetchone()
        return None if riga is None else self._sessione_narrativa_da_riga(riga)

    def ottieni_o_crea_sessione_narrativa(
        self,
        mondo_id: str,
        tempo_iniziale: str,
        creata_il: str,
    ) -> SessioneNarrativa:
        self.carica_mondo(mondo_id)
        try:
            self._connessione.execute("BEGIN IMMEDIATE")
            riga = self._connessione.execute(
                """
                SELECT session_id, world_id,
                       narrative_sessions.current_time AS current_time,
                       next_turn_number,
                       created_at, updated_at
                FROM narrative_sessions WHERE world_id = ?
                """,
                (mondo_id,),
            ).fetchone()
            if riga is None:
                self._connessione.execute(
                    """
                    INSERT INTO narrative_sessions (
                        session_id, world_id, current_time, next_turn_number,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, 1, ?, ?)
                    """,
                    (
                        crea_id_sessione(mondo_id),
                        mondo_id,
                        tempo_iniziale,
                        creata_il,
                        creata_il,
                    ),
                )
                riga = self._connessione.execute(
                    """
                    SELECT session_id, world_id,
                           narrative_sessions.current_time AS current_time,
                           next_turn_number,
                           created_at, updated_at
                    FROM narrative_sessions WHERE world_id = ?
                    """,
                    (mondo_id,),
                ).fetchone()
            self._connessione.commit()
        except sqlite3.Error as errore:
            self._connessione.rollback()
            raise ErroreTurnoNarrativo(
                "Non è stato possibile aprire la partita locale persistente."
            ) from errore
        assert riga is not None
        return self._sessione_narrativa_da_riga(riga)

    def elenca_turni_narrativi(
        self, mondo_id: str, *, limite: int | None = None
    ) -> list[TurnoNarrativoPersistito]:
        sessione = self.carica_sessione_narrativa(mondo_id)
        if sessione is None:
            return []
        if limite is not None and (
            isinstance(limite, bool) or not isinstance(limite, int) or limite < 1
        ):
            raise ErroreTurnoNarrativo(
                "Il limite della cronologia narrativa deve essere positivo."
            )
        if limite is None:
            righe = self._connessione.execute(
                """
                SELECT * FROM narrative_turns
                WHERE session_id = ?
                ORDER BY sequence_number
                """,
                (sessione.session_id,),
            ).fetchall()
        else:
            righe = self._connessione.execute(
                """
                SELECT * FROM (
                    SELECT * FROM narrative_turns
                    WHERE session_id = ?
                    ORDER BY sequence_number DESC LIMIT ?
                ) ORDER BY sequence_number
                """,
                (sessione.session_id, limite),
            ).fetchall()
        return [self._turno_narrativo_da_riga(riga) for riga in righe]

    def applica_piano_turno_narrativo(
        self, piano: PianoPersistenzaTurno
    ) -> TurnoNarrativoPersistito:
        """Applica turno, eventi, stato e memorie come un'unica unità atomica."""

        turno = piano.turno
        try:
            self._connessione.execute("BEGIN IMMEDIATE")
            sessione = self._connessione.execute(
                """
                SELECT narrative_sessions.current_time AS current_time,
                       next_turn_number FROM narrative_sessions
                WHERE session_id = ? AND world_id = ?
                """,
                (turno.session_id, turno.world_id),
            ).fetchone()
            if sessione is None:
                raise sqlite3.IntegrityError("Sessione narrativa inesistente.")
            if (
                sessione["current_time"] != turno.world_time_before
                or int(sessione["next_turn_number"]) != turno.sequence_number
            ):
                raise sqlite3.IntegrityError("Sessione narrativa non aggiornata.")

            self._connessione.execute(
                """
                INSERT INTO narrative_turns (
                    turn_id, session_id, world_id, sequence_number, user_input,
                    narrative, elapsed_minutes, world_time_before,
                    world_time_after, prompt_text, raw_model_output, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turno.turn_id,
                    turno.session_id,
                    turno.world_id,
                    turno.sequence_number,
                    turno.user_input,
                    turno.narrative,
                    turno.elapsed_minutes,
                    turno.world_time_before,
                    turno.world_time_after,
                    turno.prompt_text,
                    turno.raw_model_output,
                    turno.created_at,
                ),
            )

            for evento in piano.eventi:
                try:
                    payload = _deserializza_oggetto(evento.payload_json)
                except (json.JSONDecodeError, ValueError) as errore:
                    raise sqlite3.IntegrityError(
                        "Il payload dell'evento non è valido."
                    ) from errore
                evento_mondo = EventoMondo(
                    event_id=evento.event_id,
                    world_id=turno.world_id,
                    event_type=evento.event_type,
                    occurred_at=evento.occurred_at,
                    actor_id=evento.actor_id,
                    target_id=evento.target_id,
                    location_id=evento.location_id,
                    payload=payload,
                    reason=evento.reason,
                    created_at=turno.created_at,
                )
                self._inserisci_evento(
                    evento_mondo, evento.affected_entity_ids
                )
                self._connessione.execute(
                    """
                    INSERT INTO narrative_turn_events (
                        turn_id, event_id, world_id, operation_index
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        turno.turn_id,
                        evento.event_id,
                        turno.world_id,
                        evento.operation_index,
                    ),
                )

            for aggiornamento in piano.aggiornamenti:
                risultato = self._connessione.execute(
                    """
                    UPDATE entity_state
                    SET current_status = ?, location_id = ?, holder_id = ?,
                        accessibility = ?, condition = ?, version = ?, updated_at = ?
                    WHERE world_id = ? AND entity_id = ? AND version = ?
                    """,
                    (
                        aggiornamento.status,
                        aggiornamento.location_id,
                        aggiornamento.holder_id,
                        int(aggiornamento.accessibility),
                        aggiornamento.condition,
                        aggiornamento.final_version,
                        turno.created_at,
                        turno.world_id,
                        aggiornamento.entity_id,
                        aggiornamento.expected_version,
                    ),
                )
                if risultato.rowcount != 1:
                    raise sqlite3.IntegrityError(
                        "Lo stato corrente è cambiato durante il turno."
                    )

            for memoria in piano.memorie:
                self._inserisci_memoria(
                    MemoriaDaSalvare(
                        memory_id=memoria.memory_id,
                        world_id=turno.world_id,
                        character_id=memoria.character_id,
                        event_id=memoria.event_id,
                        knowledge_type=memoria.knowledge_type,
                        source_type=memoria.source_type,
                        source_entity_id=memoria.source_entity_id,
                        learned_at=memoria.learned_at,
                        certainty=memoria.certainty,
                        content=memoria.content,
                        interpretation=memoria.interpretation,
                        associated_emotion=memoria.associated_emotion,
                        status="active",
                        supersedes_memory_id=None,
                        created_at=turno.created_at,
                    )
                )
                self._connessione.executemany(
                    """
                    INSERT INTO memory_entities (
                        memory_id, world_id, entity_id, role
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        (memoria.memory_id, turno.world_id, entity_id, ruolo)
                        for entity_id, ruolo in memoria.entity_roles
                    ),
                )
                self._connessione.executemany(
                    """
                    INSERT INTO memory_sources (
                        memory_id, source_memory_id, world_id,
                        character_id, position
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        (
                            memoria.memory_id,
                            source_id,
                            turno.world_id,
                            memoria.character_id,
                            posizione,
                        )
                        for posizione, source_id in enumerate(
                            memoria.source_memory_ids, start=1
                        )
                    ),
                )
                self._connessione.execute(
                    """
                    INSERT INTO narrative_turn_memories (
                        turn_id, memory_id, world_id, memory_index
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        turno.turn_id,
                        memoria.memory_id,
                        turno.world_id,
                        memoria.memory_index,
                    ),
                )

            aggiornata = self._connessione.execute(
                """
                UPDATE narrative_sessions
                SET "current_time" = ?, next_turn_number = ?, updated_at = ?
                WHERE session_id = ? AND world_id = ?
                  AND narrative_sessions.current_time = ?
                  AND next_turn_number = ?
                """,
                (
                    turno.world_time_after,
                    turno.sequence_number + 1,
                    turno.created_at,
                    turno.session_id,
                    turno.world_id,
                    turno.world_time_before,
                    turno.sequence_number,
                ),
            )
            if aggiornata.rowcount != 1:
                raise sqlite3.IntegrityError(
                    "La sessione narrativa è cambiata durante il turno."
                )
            self._connessione.commit()
        except (sqlite3.Error, ValueError) as errore:
            self._connessione.rollback()
            raise ErroreTurnoNarrativo(
                "Il turno non è stato salvato: conversazione, tempo, eventi, "
                "stato e memorie sono rimasti invariati."
            ) from errore
        return self._turno_narrativo_da_valore(turno)

    @staticmethod
    def _sessione_narrativa_da_riga(riga: sqlite3.Row) -> SessioneNarrativa:
        return SessioneNarrativa(
            session_id=riga["session_id"],
            world_id=riga["world_id"],
            current_time=riga["current_time"],
            next_turn_number=int(riga["next_turn_number"]),
            created_at=riga["created_at"],
            updated_at=riga["updated_at"],
        )

    @staticmethod
    def _turno_narrativo_da_riga(riga: sqlite3.Row) -> TurnoNarrativoPersistito:
        return TurnoNarrativoPersistito(
            turn_id=riga["turn_id"],
            session_id=riga["session_id"],
            world_id=riga["world_id"],
            sequence_number=int(riga["sequence_number"]),
            user_input=riga["user_input"],
            narrative=riga["narrative"],
            elapsed_minutes=int(riga["elapsed_minutes"]),
            world_time_before=riga["world_time_before"],
            world_time_after=riga["world_time_after"],
            prompt_text=riga["prompt_text"],
            raw_model_output=riga["raw_model_output"],
            created_at=riga["created_at"],
        )

    @staticmethod
    def _turno_narrativo_da_valore(
        turno: TurnoDaPersistire,
    ) -> TurnoNarrativoPersistito:
        return TurnoNarrativoPersistito(
            turn_id=turno.turn_id,
            session_id=turno.session_id,
            world_id=turno.world_id,
            sequence_number=turno.sequence_number,
            user_input=turno.user_input,
            narrative=turno.narrative,
            elapsed_minutes=turno.elapsed_minutes,
            world_time_before=turno.world_time_before,
            world_time_after=turno.world_time_after,
            prompt_text=turno.prompt_text,
            raw_model_output=turno.raw_model_output,
            created_at=turno.created_at,
        )

    def file_sorgente(self, mondo_id: str) -> list[FileSorgente]:
        self.carica_mondo(mondo_id)
        return self._file_sorgente_senza_validazione(mondo_id)

    def elenca_documenti(
        self, mondo_id: str, document_type: str | None = None
    ) -> list[DocumentoCanonico]:
        self.carica_mondo(mondo_id)
        filtro = ""
        parametri: list[object] = [mondo_id]
        if document_type is not None:
            filtro = " AND document_type = ?"
            parametri.append(document_type)
        righe = self._connessione.execute(
            """
            SELECT world_id, document_id, document_type, title, relative_path,
                   content, sort_order, metadata, sha256
            FROM canonical_documents WHERE world_id = ?
            """ + filtro + " ORDER BY sort_order, title, document_id",
            tuple(parametri),
        ).fetchall()
        return [
            DocumentoCanonico(
                world_id=riga["world_id"],
                document_id=riga["document_id"],
                document_type=riga["document_type"],
                title=riga["title"],
                relative_path=riga["relative_path"],
                content=riga["content"],
                sort_order=int(riga["sort_order"]),
                metadata=_deserializza_oggetto(riga["metadata"]),
                sha256=riga["sha256"],
            )
            for riga in righe
        ]

    def elenca_media(self, mondo_id: str) -> list[MediaCanonico]:
        self.carica_mondo(mondo_id)
        righe = self._connessione.execute(
            """
            SELECT world_id, media_id, relative_path, media_type, mime_type,
                   sha256, title, alt_text, entity_id, sort_order, metadata
            FROM media_assets WHERE world_id = ?
            ORDER BY sort_order, title, media_id
            """,
            (mondo_id,),
        ).fetchall()
        return [
            MediaCanonico(
                world_id=riga["world_id"],
                media_id=riga["media_id"],
                relative_path=riga["relative_path"],
                media_type=riga["media_type"],
                mime_type=riga["mime_type"],
                sha256=riga["sha256"],
                title=riga["title"],
                alt_text=riga["alt_text"],
                entity_id=riga["entity_id"],
                sort_order=int(riga["sort_order"]),
                metadata=_deserializza_oggetto(riga["metadata"]),
            )
            for riga in righe
        ]

    def carica_media_contenuto(self, mondo_id: str, media_id: str) -> bytes:
        riga = self._connessione.execute(
            """
            SELECT s.content
            FROM media_assets AS m
            JOIN source_files AS s
              ON s.world_id = m.world_id AND s.relative_path = m.relative_path
            WHERE m.world_id = ? AND m.media_id = ?
            """,
            (mondo_id, media_id),
        ).fetchone()
        if riga is None:
            raise MondoNonTrovato("Il media richiesto non è presente nel mondo.")
        return bytes(riga["content"])

    def carica_configurazione_ai(self) -> ConfigurazioneAI:
        riga = self._connessione.execute(
            """
            SELECT provider, ollama_base_url, ollama_model,
                   ollama_timeout_seconds, updated_at
            FROM ai_settings WHERE settings_id = 1
            """
        ).fetchone()
        if riga is None:
            raise ErroreConfigurazioneAI(
                "La configurazione AI non è presente nell'archivio."
            )
        return valida_configurazione_ai(
            riga["provider"],
            riga["ollama_base_url"],
            riga["ollama_model"],
            riga["ollama_timeout_seconds"],
            updated_at=riga["updated_at"],
        )

    def salva_configurazione_ai(
        self, configurazione: ConfigurazioneAI
    ) -> ConfigurazioneAI:
        valida = valida_configurazione_ai(
            configurazione.provider,
            configurazione.ollama_base_url,
            configurazione.ollama_model,
            configurazione.ollama_timeout_seconds,
        )
        istante = _adesso_utc()
        try:
            with self._connessione:
                aggiornamento = self._connessione.execute(
                    """
                    UPDATE ai_settings
                    SET provider = ?, ollama_base_url = ?, ollama_model = ?,
                        ollama_timeout_seconds = ?, updated_at = ?
                    WHERE settings_id = 1
                    """,
                    (
                        valida.provider,
                        valida.ollama_base_url,
                        valida.ollama_model,
                        valida.ollama_timeout_seconds,
                        istante,
                    ),
                )
                if aggiornamento.rowcount != 1:
                    raise sqlite3.IntegrityError(
                        "La configurazione singleton non è presente."
                    )
        except sqlite3.Error as errore:
            raise ErroreConfigurazioneAI(
                "Non è stato possibile salvare le impostazioni AI."
            ) from errore
        return self.carica_configurazione_ai()

    def chiudi(self) -> None:
        self._connessione.close()

    def __enter__(self) -> "ArchivioSQLite":
        return self

    def __exit__(self, *_: object) -> None:
        self.chiudi()

