from __future__ import annotations

import hashlib
import locale
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from haria_engine.app import UI_TEXT
from haria_engine.errors import ErroreMigrazione, ErroreStatoMondo
from haria_engine.service import ServizioMondi
from haria_engine.world_state import (
    TIPO_LUOGO,
    TIPO_OGGETTO,
    TIPO_PERSONAGGIO,
)


RADICE_PROGETTO = Path(__file__).resolve().parents[1]
MINI_BIBBIA = RADICE_PROGETTO / "sample_world"


def impronte_cartella(cartella: Path) -> dict[str, str]:
    return {
        percorso.relative_to(cartella).as_posix(): hashlib.sha256(
            percorso.read_bytes()
        ).hexdigest()
        for percorso in sorted(cartella.rglob("*"))
        if percorso.is_file()
    }


def crea_database_schema_1(
    percorso: Path,
    sorgente: Path,
    *,
    ometti_file: str | None = None,
    corrompi_file: str | None = None,
) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    connessione = sqlite3.connect(percorso)
    try:
        connessione.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE worlds (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                language TEXT NOT NULL,
                source_path TEXT NOT NULL,
                current_version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE world_versions (
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
            CREATE TABLE source_files (
                world_id TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                content BLOB NOT NULL,
                sha256 TEXT NOT NULL,
                PRIMARY KEY (world_id, relative_path),
                FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE RESTRICT
            );
            CREATE INDEX idx_world_versions_world
                ON world_versions(world_id, version_number DESC);
            PRAGMA user_version = 1;
            """
        )
        istante = "2026-01-01T00:00:00+00:00"
        connessione.execute(
            """
            INSERT INTO worlds (
                id, title, language, source_path, current_version,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 2, ?, ?)
            """,
            (
                "haria_minimal_test",
                "Haria — Mini mondo di collaudo",
                "it",
                str(sorgente),
                istante,
                istante,
            ),
        )
        connessione.executemany(
            """
            INSERT INTO world_versions (
                world_id, version_number, scenario, narrative_settings,
                created_at, reason
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    "haria_minimal_test",
                    1,
                    "Scenario iniziale",
                    "{}",
                    istante,
                    "Importazione iniziale",
                ),
                (
                    "haria_minimal_test",
                    2,
                    "Scenario salvato Task 001",
                    '{"tone": "sobrio"}',
                    istante,
                    "Salvataggio manuale",
                ),
            ),
        )
        for file in sorted(sorgente.rglob("*")):
            if not file.is_file():
                continue
            relativo = file.relative_to(sorgente).as_posix()
            if relativo == ometti_file:
                continue
            contenuto = file.read_bytes()
            if relativo == corrompi_file:
                contenuto = b"{contenuto non valido"
            connessione.execute(
                """
                INSERT INTO source_files (
                    world_id, relative_path, content, sha256
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    "haria_minimal_test",
                    relativo,
                    contenuto,
                    hashlib.sha256(contenuto).hexdigest(),
                ),
            )
        connessione.commit()
    finally:
        connessione.close()


class TestMigrazioneSchema2(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)
        self.sorgente = self.radice / "mini_bibbia"
        shutil.copytree(MINI_BIBBIA, self.sorgente)
        self.database = self.radice / "haria_v1.sqlite3"

    def tearDown(self) -> None:
        self.temporanea.cleanup()

    def test_migrazione_1_a_2_usa_solo_file_archiviati_e_preserva_versioni(self) -> None:
        crea_database_schema_1(self.database, self.sorgente)
        shutil.rmtree(self.sorgente)

        with ServizioMondi(self.database) as servizio:
            mondo = servizio.carica_mondo("haria_minimal_test")
            entita = servizio.stato_mondo.elenca_entita(mondo.id)
            versioni = servizio.cronologia(mondo.id)
            versione_schema = servizio.archivio._connessione.execute(
                "PRAGMA user_version"
            ).fetchone()[0]

        self.assertEqual(5, versione_schema)
        self.assertEqual("Scenario salvato Task 001", mondo.scenario)
        self.assertEqual([2, 1], [versione.numero for versione in versioni])
        self.assertEqual(8, len(entita))

    def test_migrazione_fallita_esegue_rollback_integrale(self) -> None:
        crea_database_schema_1(
            self.database, self.sorgente, ometti_file="items.json"
        )

        with self.assertRaisesRegex(ErroreMigrazione, "schema 1 senza dati parziali"):
            ServizioMondi(self.database)

        connessione = sqlite3.connect(self.database)
        try:
            versione = connessione.execute("PRAGMA user_version").fetchone()[0]
            tabelle = {
                riga[0]
                for riga in connessione.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        finally:
            connessione.close()
        self.assertEqual(1, versione)
        self.assertNotIn("world_entities", tabelle)
        self.assertNotIn("entity_state", tabelle)
        self.assertNotIn("events", tabelle)
        self.assertNotIn("event_entities", tabelle)

    def test_migrazione_file_archiviato_non_valido_esegue_rollback(self) -> None:
        crea_database_schema_1(
            self.database, self.sorgente, corrompi_file="characters.json"
        )

        with self.assertRaisesRegex(ErroreMigrazione, "dati validi"):
            ServizioMondi(self.database)

        connessione = sqlite3.connect(self.database)
        try:
            versione = connessione.execute("PRAGMA user_version").fetchone()[0]
            entita_presente = connessione.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'world_entities'
                """
            ).fetchone()
        finally:
            connessione.close()
        self.assertEqual(1, versione)
        self.assertIsNone(entita_presente)

    def test_riapertura_schema_2_non_duplica_entita(self) -> None:
        crea_database_schema_1(self.database, self.sorgente)
        with ServizioMondi(self.database):
            pass

        with ServizioMondi(self.database) as servizio:
            entita = servizio.stato_mondo.elenca_entita("haria_minimal_test")
            versione = servizio.archivio._connessione.execute(
                "PRAGMA user_version"
            ).fetchone()[0]

        self.assertEqual(5, versione)
        self.assertEqual(8, len(entita))

    def test_verifica_cli_mostra_errore_migrazione_in_italiano(self) -> None:
        crea_database_schema_1(
            self.database, self.sorgente, ometti_file="locations.json"
        )

        processo = subprocess.run(
            [
                sys.executable,
                "-m",
                "haria_engine",
                "--check",
                "--database",
                str(self.database),
            ],
            cwd=RADICE_PROGETTO,
            check=False,
            capture_output=True,
            text=True,
            encoding=locale.getpreferredencoding(False),
        )

        self.assertEqual(1, processo.returncode)
        self.assertIn("Errore: La migrazione allo schema 2 non è riuscita", processo.stderr)
        self.assertNotIn("Traceback", processo.stderr)


class TestStatoCorrenteEventi(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)
        self.sorgente = self.radice / "mini_bibbia"
        shutil.copytree(MINI_BIBBIA, self.sorgente)
        self.database = self.radice / "haria.sqlite3"
        self.servizio: ServizioMondi | None = ServizioMondi(self.database)
        self.mondo = self.servizio.importa_da_cartella(self.sorgente)

    def tearDown(self) -> None:
        if self.servizio is not None:
            self.servizio.chiudi()
        self.temporanea.cleanup()

    @property
    def stato(self):
        assert self.servizio is not None
        return self.servizio.stato_mondo

    def test_importa_personaggi_luoghi_e_oggetti_con_id_stabili(self) -> None:
        entita = {voce.entity_id: voce for voce in self.stato.elenca_entita(self.mondo.id)}

        self.assertEqual(8, len(entita))
        self.assertEqual(TIPO_PERSONAGGIO, entita["luca"].entity_type)
        self.assertEqual(TIPO_PERSONAGGIO, entita["elise_moreau"].entity_type)
        self.assertEqual(TIPO_PERSONAGGIO, entita["akari_mori"].entity_type)
        self.assertEqual(TIPO_LUOGO, entita["infirmary"].entity_type)
        self.assertEqual(TIPO_LUOGO, entita["assembly"].entity_type)
        self.assertEqual(TIPO_OGGETTO, entita["pen_blue"].entity_type)
        self.assertEqual(TIPO_OGGETTO, entita["notebook_small"].entity_type)
        self.assertEqual(TIPO_OGGETTO, entita["infirmary_keys"].entity_type)

    def test_stato_iniziale_preserva_posizioni_canoniche(self) -> None:
        self.assertEqual("infirmary", self.stato.carica_entita(self.mondo.id, "luca").location_id)
        self.assertEqual("infirmary", self.stato.carica_entita(self.mondo.id, "elise_moreau").location_id)
        self.assertEqual("assembly", self.stato.carica_entita(self.mondo.id, "akari_mori").location_id)
        self.assertIsNone(self.stato.carica_entita(self.mondo.id, "pen_blue").holder_id)
        self.assertIsNone(self.stato.carica_entita(self.mondo.id, "infirmary_keys").holder_id)

    def test_canone_e_stato_restano_separati(self) -> None:
        prima = self.stato.carica_entita(self.mondo.id, "pen_blue")

        self.stato.trasferisci_oggetto(
            self.mondo.id,
            "pen_blue",
            "luca",
            reason="Luca prende la penna blu.",
        )
        dopo = self.stato.carica_entita(self.mondo.id, "pen_blue")

        self.assertIsNone(prima.canonical_data["owner_id"])
        self.assertIsNone(dopo.canonical_data["owner_id"])
        self.assertEqual("luca", dopo.holder_id)

    def test_cambia_stato_modifica_solo_current_status(self) -> None:
        assert self.servizio is not None
        connessione = self.servizio.archivio._connessione
        entita_prima = self.stato.carica_entita(self.mondo.id, "infirmary")
        riga_canonica_prima = tuple(
            connessione.execute(
                "SELECT * FROM world_entities WHERE world_id = ? AND entity_id = ?",
                (self.mondo.id, "infirmary"),
            ).fetchone()
        )

        self.stato.cambia_stato(
            self.mondo.id,
            "infirmary",
            status="inaccessible",
            reason="L'infermeria viene chiusa temporaneamente.",
        )

        entita_dopo = self.stato.carica_entita(self.mondo.id, "infirmary")
        riga_canonica_dopo = tuple(
            connessione.execute(
                "SELECT * FROM world_entities WHERE world_id = ? AND entity_id = ?",
                (self.mondo.id, "infirmary"),
            ).fetchone()
        )
        current_status = connessione.execute(
            "SELECT current_status FROM entity_state WHERE world_id = ? AND entity_id = ?",
            (self.mondo.id, "infirmary"),
        ).fetchone()[0]
        colonne_canoniche = {
            riga["name"]
            for riga in connessione.execute("PRAGMA table_info(world_entities)")
        }

        self.assertEqual(riga_canonica_prima, riga_canonica_dopo)
        self.assertNotIn("status", colonne_canoniche)
        self.assertEqual(entita_prima.canonical_data, entita_dopo.canonical_data)
        self.assertEqual("active", entita_dopo.canonical_data["status"])
        self.assertEqual("inaccessible", current_status)
        self.assertEqual("inaccessible", entita_dopo.status)

    def test_current_status_persiste_dopo_riavvio(self) -> None:
        self.stato.cambia_stato(
            self.mondo.id,
            "infirmary",
            status="inaccessible",
            reason="L'infermeria viene chiusa temporaneamente.",
        )
        assert self.servizio is not None
        self.servizio.chiudi()
        self.servizio = ServizioMondi(self.database)

        entita = self.stato.carica_entita(self.mondo.id, "infirmary")
        current_status = self.servizio.archivio._connessione.execute(
            "SELECT current_status FROM entity_state WHERE world_id = ? AND entity_id = ?",
            (self.mondo.id, "infirmary"),
        ).fetchone()[0]

        self.assertEqual("inaccessible", entita.status)
        self.assertEqual("inaccessible", current_status)

    def test_sposta_akari_crea_un_solo_evento(self) -> None:
        evento = self.stato.sposta_entita(
            self.mondo.id,
            "akari_mori",
            "infirmary",
            reason="Akari raggiunge l'infermeria.",
        )

        akari = self.stato.carica_entita(self.mondo.id, "akari_mori")
        eventi = self.stato.elenca_eventi(self.mondo.id)
        self.assertEqual("infirmary", akari.location_id)
        self.assertEqual("spostamento_entita", evento.event_type)
        self.assertEqual([evento.event_id], [voce.event_id for voce in eventi])

    def test_trasferimento_penna_a_luca_e_coerente(self) -> None:
        evento = self.stato.trasferisci_oggetto(
            self.mondo.id,
            "pen_blue",
            "luca",
            reason="Luca prende la penna blu.",
        )

        penna = self.stato.carica_entita(self.mondo.id, "pen_blue")
        self.assertEqual("luca", penna.holder_id)
        self.assertEqual("infirmary", penna.location_id)
        self.assertEqual("trasferimento_oggetto", evento.event_type)
        self.assertEqual("luca", evento.actor_id)

    def test_oggetto_posseduto_segue_personaggio_con_un_solo_evento(self) -> None:
        self.stato.trasferisci_oggetto(
            self.mondo.id,
            "pen_blue",
            "luca",
            reason="Luca prende la penna blu.",
        )
        spostamento = self.stato.sposta_entita(
            self.mondo.id,
            "luca",
            "assembly",
            actor_id="elise_moreau",
            reason="Élise accompagna Luca all'assemblea.",
        )

        luca = self.stato.carica_entita(self.mondo.id, "luca")
        penna = self.stato.carica_entita(self.mondo.id, "pen_blue")
        eventi_luca = [
            evento
            for evento in self.stato.eventi_per_entita(self.mondo.id, "luca")
            if evento.event_type == "spostamento_entita"
        ]
        eventi_penna = [
            evento
            for evento in self.stato.eventi_per_entita(self.mondo.id, "pen_blue")
            if evento.event_type == "spostamento_entita"
        ]
        eventi_spostamento = [
            evento
            for evento in self.stato.elenca_eventi(self.mondo.id)
            if evento.event_type == "spostamento_entita"
        ]

        self.assertEqual("assembly", luca.location_id)
        self.assertEqual("assembly", penna.location_id)
        self.assertEqual("luca", penna.holder_id)
        self.assertEqual([spostamento.event_id], [evento.event_id for evento in eventi_luca])
        self.assertEqual([spostamento.event_id], [evento.event_id for evento in eventi_penna])
        self.assertEqual([spostamento.event_id], [evento.event_id for evento in eventi_spostamento])

    def test_spostamento_registra_tutte_le_associazioni_evento(self) -> None:
        self.stato.trasferisci_oggetto(
            self.mondo.id,
            "pen_blue",
            "luca",
            reason="Luca prende la penna blu.",
        )
        evento = self.stato.sposta_entita(
            self.mondo.id,
            "luca",
            "assembly",
            actor_id="elise_moreau",
            reason="Élise accompagna Luca all'assemblea.",
        )
        assert self.servizio is not None

        associazioni = {
            (riga["entity_id"], riga["role"])
            for riga in self.servizio.archivio._connessione.execute(
                "SELECT entity_id, role FROM event_entities WHERE event_id = ?",
                (evento.event_id,),
            )
        }

        self.assertEqual(
            {
                ("elise_moreau", "actor"),
                ("luca", "target"),
                ("assembly", "location"),
                ("luca", "affected"),
                ("pen_blue", "affected"),
            },
            associazioni,
        )

    def test_evento_descrittivo_registra_actor_target_e_location(self) -> None:
        evento = self.stato.registra_evento_descrittivo(
            self.mondo.id,
            "osservazione",
            actor_id="elise_moreau",
            target_id="akari_mori",
            location_id="assembly",
            reason="Élise osserva Akari nell'assemblea.",
        )
        assert self.servizio is not None

        associazioni = {
            (riga["entity_id"], riga["role"])
            for riga in self.servizio.archivio._connessione.execute(
                "SELECT entity_id, role FROM event_entities WHERE event_id = ?",
                (evento.event_id,),
            )
        }

        self.assertEqual(
            {
                ("elise_moreau", "actor"),
                ("akari_mori", "target"),
                ("assembly", "location"),
            },
            associazioni,
        )

    def test_sequenza_persiste_e_non_modifica_le_chiavi(self) -> None:
        chiavi_prima = self.stato.carica_entita(self.mondo.id, "infirmary_keys")
        self.stato.sposta_entita(
            self.mondo.id,
            "akari_mori",
            "infirmary",
            reason="Akari raggiunge l'infermeria.",
        )
        self.stato.trasferisci_oggetto(
            self.mondo.id,
            "pen_blue",
            "luca",
            reason="Luca prende la penna blu.",
        )
        assert self.servizio is not None
        self.servizio.chiudi()
        self.servizio = ServizioMondi(self.database)

        akari = self.stato.carica_entita(self.mondo.id, "akari_mori")
        penna = self.stato.carica_entita(self.mondo.id, "pen_blue")
        chiavi = self.stato.carica_entita(self.mondo.id, "infirmary_keys")
        eventi = self.stato.elenca_eventi(self.mondo.id)

        self.assertEqual("infirmary", akari.location_id)
        self.assertEqual("luca", penna.holder_id)
        self.assertEqual(chiavi_prima.location_id, chiavi.location_id)
        self.assertIsNone(chiavi.holder_id)
        self.assertEqual(chiavi_prima.version, chiavi.version)
        self.assertEqual([], self.stato.eventi_per_entita(self.mondo.id, "infirmary_keys"))
        self.assertEqual(
            ["spostamento_entita", "trasferimento_oggetto"],
            [evento.event_type for evento in eventi],
        )

    def test_evento_trasferimento_penna_creato_una_sola_volta(self) -> None:
        self.stato.trasferisci_oggetto(
            self.mondo.id,
            "pen_blue",
            "luca",
            reason="Luca prende la penna blu.",
        )
        with self.assertRaisesRegex(ErroreStatoMondo, "già assegnato"):
            self.stato.trasferisci_oggetto(
                self.mondo.id,
                "pen_blue",
                "luca",
                reason="Tentativo duplicato.",
            )

        eventi_penna = [
            evento
            for evento in self.stato.eventi_per_entita(self.mondo.id, "pen_blue")
            if evento.event_type == "trasferimento_oggetto"
        ]
        self.assertEqual(1, len(eventi_penna))

    def test_accessibilita_non_booleana_viene_rifiutata(self) -> None:
        with self.assertRaisesRegex(ErroreStatoMondo, "vero o falso"):
            self.stato.cambia_stato(
                self.mondo.id,
                "infirmary",
                accessibility="no",  # type: ignore[arg-type]
                reason="Tentativo non valido.",
            )

    def test_payload_non_valido_restituisce_errore_italiano(self) -> None:
        with self.assertRaisesRegex(ErroreStatoMondo, "dettagli strutturati"):
            self.stato.registra_evento_descrittivo(
                self.mondo.id,
                "nota",
                reason="Tentativo non valido.",
                payload={"valore": object()},
            )

    def test_trigger_impedisce_update_eventi(self) -> None:
        evento = self.stato.registra_evento_descrittivo(
            self.mondo.id,
            "nota",
            reason="Evento descrittivo di collaudo.",
        )
        assert self.servizio is not None

        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutabile"):
            self.servizio.archivio._connessione.execute(
                "UPDATE events SET reason = ? WHERE event_id = ?",
                ("Tentativo vietato", evento.event_id),
            )
        self.servizio.archivio._connessione.rollback()

    def test_trigger_impedisce_delete_eventi(self) -> None:
        evento = self.stato.registra_evento_descrittivo(
            self.mondo.id,
            "nota",
            reason="Evento descrittivo di collaudo.",
        )
        assert self.servizio is not None

        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutabile"):
            self.servizio.archivio._connessione.execute(
                "DELETE FROM events WHERE event_id = ?", (evento.event_id,)
            )
        self.servizio.archivio._connessione.rollback()

    def test_trigger_impedisce_update_associazioni_eventi(self) -> None:
        evento = self.stato.registra_evento_descrittivo(
            self.mondo.id,
            "nota",
            target_id="luca",
            reason="Evento descrittivo di collaudo.",
        )
        assert self.servizio is not None

        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutabili"):
            self.servizio.archivio._connessione.execute(
                """
                UPDATE event_entities SET role = 'affected'
                WHERE event_id = ? AND entity_id = ? AND role = 'target'
                """,
                (evento.event_id, "luca"),
            )
        self.servizio.archivio._connessione.rollback()

    def test_trigger_impedisce_delete_associazioni_eventi(self) -> None:
        evento = self.stato.registra_evento_descrittivo(
            self.mondo.id,
            "nota",
            target_id="luca",
            reason="Evento descrittivo di collaudo.",
        )
        assert self.servizio is not None

        with self.assertRaisesRegex(sqlite3.IntegrityError, "immutabili"):
            self.servizio.archivio._connessione.execute(
                "DELETE FROM event_entities WHERE event_id = ?",
                (evento.event_id,),
            )
        self.servizio.archivio._connessione.rollback()

    def test_rollback_evento_e_stato_se_aggiornamento_fallisce(self) -> None:
        assert self.servizio is not None
        connessione = self.servizio.archivio._connessione
        connessione.execute(
            """
            CREATE TRIGGER collaudo_blocca_stato
            BEFORE UPDATE ON entity_state
            WHEN NEW.entity_id = 'pen_blue'
            BEGIN
                SELECT RAISE(ABORT, 'Errore simulato sullo stato');
            END
            """
        )
        connessione.commit()
        penna_prima = self.stato.carica_entita(self.mondo.id, "pen_blue")

        with self.assertRaisesRegex(ErroreStatoMondo, "evento e stato.*invariati"):
            self.stato.trasferisci_oggetto(
                self.mondo.id,
                "pen_blue",
                "luca",
                reason="Luca prende la penna blu.",
            )

        penna_dopo = self.stato.carica_entita(self.mondo.id, "pen_blue")
        self.assertEqual(penna_prima, penna_dopo)
        self.assertEqual([], self.stato.elenca_eventi(self.mondo.id))
        self.assertEqual(
            0,
            connessione.execute("SELECT COUNT(*) FROM event_entities").fetchone()[0],
        )

    def test_rollback_totale_se_associazione_evento_fallisce(self) -> None:
        assert self.servizio is not None
        connessione = self.servizio.archivio._connessione
        connessione.execute(
            """
            CREATE TRIGGER collaudo_blocca_associazione
            BEFORE INSERT ON event_entities
            WHEN NEW.entity_id = 'pen_blue' AND NEW.role = 'affected'
            BEGIN
                SELECT RAISE(ABORT, 'Errore simulato sull''associazione');
            END
            """
        )
        connessione.commit()
        penna_prima = self.stato.carica_entita(self.mondo.id, "pen_blue")

        with self.assertRaisesRegex(ErroreStatoMondo, "evento e stato.*invariati"):
            self.stato.trasferisci_oggetto(
                self.mondo.id,
                "pen_blue",
                "luca",
                reason="Luca prende la penna blu.",
            )

        self.assertEqual(
            penna_prima,
            self.stato.carica_entita(self.mondo.id, "pen_blue"),
        )
        self.assertEqual([], self.stato.elenca_eventi(self.mondo.id))
        self.assertEqual(
            0,
            connessione.execute("SELECT COUNT(*) FROM event_entities").fetchone()[0],
        )

    def test_possessore_inesistente_restituisce_errore_italiano(self) -> None:
        with self.assertRaisesRegex(ErroreStatoMondo, "non esiste"):
            self.stato.trasferisci_oggetto(
                self.mondo.id,
                "pen_blue",
                "personaggio_assente",
                reason="Tentativo non valido.",
            )

    def test_posizione_inesistente_restituisce_errore_italiano(self) -> None:
        with self.assertRaisesRegex(ErroreStatoMondo, "non esiste"):
            self.stato.sposta_entita(
                self.mondo.id,
                "akari_mori",
                "luogo_assente",
                reason="Tentativo non valido.",
            )

    def test_tipo_entita_errato_viene_rifiutato(self) -> None:
        with self.assertRaisesRegex(ErroreStatoMondo, "non è di tipo oggetto"):
            self.stato.trasferisci_oggetto(
                self.mondo.id,
                "akari_mori",
                "luca",
                reason="Tentativo non valido.",
            )

    def test_entita_inesistente_non_puo_essere_modificata(self) -> None:
        with self.assertRaisesRegex(ErroreStatoMondo, "non esiste"):
            self.stato.cambia_stato(
                self.mondo.id,
                "entita_assente",
                status="active",
                reason="Tentativo non valido.",
            )

    def test_sorgenti_restano_integri_dopo_operazioni(self) -> None:
        prima = impronte_cartella(self.sorgente)

        self.stato.sposta_entita(
            self.mondo.id,
            "akari_mori",
            "infirmary",
            reason="Akari raggiunge l'infermeria.",
        )
        self.stato.trasferisci_oggetto(
            self.mondo.id,
            "pen_blue",
            "luca",
            reason="Luca prende la penna blu.",
        )

        self.assertEqual(prima, impronte_cartella(self.sorgente))

    def test_evento_descrittivo_non_modifica_lo_stato(self) -> None:
        akari_prima = self.stato.carica_entita(self.mondo.id, "akari_mori")

        evento = self.stato.registra_evento_descrittivo(
            self.mondo.id,
            "osservazione",
            target_id="akari_mori",
            location_id="assembly",
            reason="Akari è nell'edificio dell'assemblea.",
        )

        self.assertEqual(
            akari_prima, self.stato.carica_entita(self.mondo.id, "akari_mori")
        )
        self.assertEqual(evento.event_id, self.stato.elenca_eventi(self.mondo.id)[0].event_id)

    def test_cambia_stato_aggiorna_versione_e_crea_evento(self) -> None:
        prima = self.stato.carica_entita(self.mondo.id, "infirmary")

        evento = self.stato.cambia_stato(
            self.mondo.id,
            "infirmary",
            status="inaccessible",
            accessibility=False,
            reason="L'infermeria viene chiusa temporaneamente.",
        )

        dopo = self.stato.carica_entita(self.mondo.id, "infirmary")
        self.assertEqual("inaccessible", dopo.status)
        self.assertFalse(dopo.accessibility)
        self.assertEqual(prima.version + 1, dopo.version)
        self.assertEqual("cambio_stato", evento.event_type)

    def test_event_id_stabile_non_deriva_dai_nomi_visibili(self) -> None:
        evento = self.stato.registra_evento_descrittivo(
            self.mondo.id,
            "nota",
            target_id="luca",
            reason="Evento di collaudo.",
        )

        self.assertEqual(32, len(evento.event_id))
        self.assertNotIn("luca", evento.event_id)
        int(evento.event_id, 16)

    def test_interfaccia_stato_del_mondo_usa_testi_italiani(self) -> None:
        testi_richiesti = {
            "Stato del mondo",
            "Entità",
            "Tipo",
            "Posizione",
            "Possessore",
            "Stato",
            "Accessibilità",
            "Cronologia eventi dell'entità selezionata",
            "Trasferisci oggetto",
            "Nuovo possessore",
        }

        self.assertTrue(testi_richiesti.issubset(set(UI_TEXT.values())))

    def test_interfaccia_normale_non_espone_dati_tecnici(self) -> None:
        testi = " ".join(UI_TEXT.values()).upper()

        for termine in ("JSON", "SQL", "UUID", "PAYLOAD"):
            self.assertNotIn(termine, testi)


if __name__ == "__main__":
    unittest.main()
