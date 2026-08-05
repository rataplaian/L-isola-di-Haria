from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import sqlite3
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from haria_engine.app import (
    UI_TEXT,
    anteprima_media_supportata,
    formatta_canone_personaggio,
)
from haria_engine.errors import (
    ErroreArchivioNonSicuro,
    ErroreImportazione,
    ErroreManifest,
    ErroreMigrazione,
    ErroreZipNonValido,
)
from haria_engine.service import ServizioMondi
from haria_engine.world_package import (
    MAX_FILE_SIZE,
    importa_pacchetto_da_cartella,
    importa_pacchetto_da_zip,
)
from tools.build_local_haria_package import costruisci


RADICE_PROGETTO = Path(__file__).resolve().parents[1]
SAMPLE_WORLD = RADICE_PROGETTO / "sample_world"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUB"
    "AScY42YAAAAASUVORK5CYII="
)


def scrivi_json(percorso: Path, dati: object) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(
        json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def crea_pacchetto_completo(radice: Path, *, world_id: str = "mondo_tecnico") -> Path:
    pacchetto = radice / world_id
    scrivi_json(
        pacchetto / "world.json",
        {
            "id": world_id,
            "title": "Mondo tecnico",
            "language": "it",
            "player_character_id": "alba",
            "narrative_style": {"tone": "chiaro"},
        },
    )
    (pacchetto / "scenario.md").write_text("# Scenario\n\nScenario tecnico.\n", encoding="utf-8")
    (pacchetto / "rules.md").write_text("# Regole\n\nUna regola tecnica.\n", encoding="utf-8")
    (pacchetto / "style.md").write_text("# Stile\n\nStile tecnico.\n", encoding="utf-8")
    scrivi_json(
        pacchetto / "characters" / "alba.json",
        {
            "id": "alba",
            "name": "Alba",
            "role": "Verificatrice",
            "location_id": "laboratorio",
            "status": "active",
            "knowledge": ["Il laboratorio esiste."],
            "image": "media/characters/alba.png",
            "relationships": [{"entity_id": "bruno", "type": "collaborazione"}],
        },
    )
    scrivi_json(
        pacchetto / "characters" / "bruno.json",
        {
            "id": "bruno",
            "name": "Bruno",
            "location_id": "laboratorio",
            "status": "active",
            "knowledge": [],
        },
    )
    scrivi_json(
        pacchetto / "locations" / "laboratorio.json",
        {"id": "laboratorio", "name": "Laboratorio", "status": "active"},
    )
    scrivi_json(
        pacchetto / "items" / "chiave.json",
        {
            "id": "chiave",
            "name": "Chiave",
            "location_id": "laboratorio",
            "accessible": True,
        },
    )
    (pacchetto / "lore" / "fondazione.md").parent.mkdir(parents=True, exist_ok=True)
    (pacchetto / "lore" / "fondazione.md").write_text(
        "# Fondazione\n\nDocumento tecnico.\n", encoding="utf-8"
    )
    scrivi_json(
        pacchetto / "timeline" / "inizio.json",
        {
            "id": "inizio",
            "title": "Inizio",
            "content": "Il collaudo ha inizio.",
            "order": 6,
        },
    )
    media = pacchetto / "media" / "characters" / "alba.png"
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(PNG_1X1)
    file_manifest = []
    for file in sorted(pacchetto.rglob("*")):
        if file.is_file() and file.name != "manifest.json":
            contenuto = file.read_bytes()
            file_manifest.append(
                {
                    "path": file.relative_to(pacchetto).as_posix(),
                    "sha256": hashlib.sha256(contenuto).hexdigest(),
                }
            )
    scrivi_json(
        pacchetto / "manifest.json",
        {
            "world_id": world_id,
            "files": file_manifest,
            "documents": [
                {"path": "rules.md", "id": "regole", "type": "regole", "title": "Regole", "order": 2},
                {"path": "style.md", "id": "stile", "type": "stile", "title": "Stile", "order": 3},
                {"path": "lore/fondazione.md", "id": "fondazione", "type": "lore", "title": "Fondazione", "order": 5},
                {"path": "timeline/inizio.json", "id": "inizio", "type": "timeline", "title": "Inizio", "order": 6},
            ],
            "media": [
                {
                    "path": "media/characters/alba.png",
                    "id": "ritratto_alba",
                    "type": "immagine_personaggio",
                    "title": "Ritratto di Alba",
                    "alt_text": "Ritratto tecnico di Alba",
                    "entity_id": "alba",
                    "order": 1,
                }
            ],
        },
    )
    return pacchetto


def aggiorna_manifest(pacchetto: Path) -> None:
    manifest = json.loads((pacchetto / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"] = [
        {
            "path": file.relative_to(pacchetto).as_posix(),
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        }
        for file in sorted(pacchetto.rglob("*"))
        if file.is_file() and file.name != "manifest.json"
    ]
    scrivi_json(pacchetto / "manifest.json", manifest)


def crea_zip(pacchetto: Path, destinazione: Path, *, contenitore: bool = True) -> None:
    with zipfile.ZipFile(destinazione, "w", zipfile.ZIP_DEFLATED) as archivio:
        for file in sorted(pacchetto.rglob("*")):
            if file.is_file():
                relativo = file.relative_to(pacchetto).as_posix()
                nome = f"pacchetto/{relativo}" if contenitore else relativo
                archivio.write(file, nome)


class TestTask006(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)
        self.pacchetto = crea_pacchetto_completo(self.radice)
        self.database = self.radice / "haria.sqlite3"

    def tearDown(self) -> None:
        self.temporanea.cleanup()

    def test_sample_world_legacy_resta_importabile(self) -> None:
        with ServizioMondi(self.database) as servizio:
            mondo = servizio.importa_da_cartella(SAMPLE_WORLD)
            self.assertEqual("haria_minimal_test", mondo.id)
            self.assertEqual([], servizio.elenca_documenti(mondo.id))

    def test_cartella_completa_importa_entita_documenti_media_e_memorie(self) -> None:
        with ServizioMondi(self.database) as servizio:
            mondo = servizio.importa_da_cartella(self.pacchetto)
            entita = servizio.stato_mondo.elenca_entita(mondo.id)
            documenti = servizio.elenca_documenti(mondo.id)
            media = servizio.elenca_media(mondo.id)
            memorie = servizio.memorie.elenca_memorie_personaggio(mondo.id, "alba")
        self.assertEqual(4, len(entita))
        self.assertEqual({"scenario", "regole", "stile", "lore", "timeline"}, {d.document_type for d in documenti})
        self.assertEqual("Il collaudo ha inizio.", [d.content for d in documenti if d.document_type == "timeline"][0])
        self.assertEqual("alba", media[0].entity_id)
        self.assertEqual("Il laboratorio esiste.", memorie[0].content)

    def test_zip_e_cartella_producono_pacchetti_deterministicamente_equivalenti(self) -> None:
        archivio = self.radice / "mondo.zip"
        crea_zip(self.pacchetto, archivio)
        cartella = importa_pacchetto_da_cartella(self.pacchetto)
        compresso = importa_pacchetto_da_zip(archivio)
        self.assertEqual(cartella, compresso)

    def test_id_automatici_restano_stabili_se_cambiano_i_contenuti(self) -> None:
        manifest = json.loads(
            (self.pacchetto / "manifest.json").read_text(encoding="utf-8")
        )
        manifest["media"][0].pop("id")
        scrivi_json(self.pacchetto / "manifest.json", manifest)
        prima = importa_pacchetto_da_cartella(self.pacchetto)
        documento_prima = next(
            voce for voce in prima.documents if voce.relative_path == "scenario.md"
        )
        media_prima = prima.media[0]

        (self.pacchetto / "scenario.md").write_text(
            "# Scenario\n\nContenuto sostituito.\n", encoding="utf-8"
        )
        (self.pacchetto / "media" / "characters" / "alba.png").write_bytes(
            PNG_1X1 + b"byte-sostituiti"
        )
        aggiorna_manifest(self.pacchetto)
        dopo = importa_pacchetto_da_cartella(self.pacchetto)
        documento_dopo = next(
            voce for voce in dopo.documents if voce.relative_path == "scenario.md"
        )
        media_dopo = dopo.media[0]

        self.assertEqual(documento_prima.document_id, documento_dopo.document_id)
        self.assertNotEqual(documento_prima.sha256, documento_dopo.sha256)
        self.assertEqual(media_prima.media_id, media_dopo.media_id)
        self.assertNotEqual(media_prima.sha256, media_dopo.sha256)

    def test_export_e_reimport_conservano_gli_id_automatici(self) -> None:
        manifest = json.loads(
            (self.pacchetto / "manifest.json").read_text(encoding="utf-8")
        )
        for documento in manifest["documents"]:
            documento.pop("id", None)
        manifest["media"][0].pop("id")
        scrivi_json(self.pacchetto / "manifest.json", manifest)
        with ServizioMondi(self.database) as servizio:
            mondo = servizio.importa_da_cartella(self.pacchetto)
            documenti_prima = {
                voce.relative_path: voce.document_id
                for voce in servizio.elenca_documenti(mondo.id)
            }
            media_prima = {
                voce.relative_path: voce.media_id
                for voce in servizio.elenca_media(mondo.id)
            }
            esportato = servizio.esporta(mondo.id, self.radice / "export_id").cartella
        with ServizioMondi(self.radice / "reimport_id.sqlite3") as servizio:
            reimportato = servizio.importa_da_cartella(esportato)
            documenti_dopo = {
                voce.relative_path: voce.document_id
                for voce in servizio.elenca_documenti(reimportato.id)
            }
            media_dopo = {
                voce.relative_path: voce.media_id
                for voce in servizio.elenca_media(reimportato.id)
            }
        self.assertEqual(documenti_prima, documenti_dopo)
        self.assertEqual(media_prima, media_dopo)

    def test_rappresentazioni_aggregate_e_individuali_non_possono_coesistere(self) -> None:
        casi = (
            ("characters.json", "characters", "personaggi"),
            ("locations.json", "locations", "luoghi"),
            ("items.json", "items", "oggetti"),
        )
        for indice, (aggregato, _cartella, descrizione) in enumerate(casi):
            with self.subTest(categoria=descrizione):
                pacchetto = crea_pacchetto_completo(
                    self.radice, world_id=f"misto_{indice}"
                )
                scrivi_json(pacchetto / aggregato, [])
                aggiorna_manifest(pacchetto)
                with self.assertRaisesRegex(
                    ErroreImportazione, rf"sia {re.escape(aggregato)}.*{descrizione}"
                ):
                    importa_pacchetto_da_cartella(pacchetto)

    def test_file_testuale_nella_cartella_media_viene_rifiutato(self) -> None:
        nota = self.pacchetto / "media" / "nota.txt"
        nota.write_text("Non è un media.", encoding="utf-8")
        aggiorna_manifest(self.pacchetto)
        with self.assertRaisesRegex(ErroreImportazione, "non ammesso.*media"):
            importa_pacchetto_da_cartella(self.pacchetto)

    def test_immagine_del_personaggio_deve_avere_la_stessa_associazione(self) -> None:
        manifest = json.loads(
            (self.pacchetto / "manifest.json").read_text(encoding="utf-8")
        )
        manifest["media"][0]["entity_id"] = "bruno"
        scrivi_json(self.pacchetto / "manifest.json", manifest)
        with self.assertRaisesRegex(
            ErroreImportazione, "non è associata a quel personaggio"
        ):
            importa_pacchetto_da_cartella(self.pacchetto)

    def test_builder_preserva_scenario_e_campi_integrali_dei_profili(self) -> None:
        sorgente = self.radice / "materiali_builder"
        scenario_md = b"# Scenario originale\r\n\r\nTesto gi\xc3\xa0 leggibile.\r\n"
        scenario_json = b'{"origine":"integrale"}\r\n'
        (sorgente / "scenario").mkdir(parents=True)
        (sorgente / "scenario" / "scenario_iniziale.md").write_bytes(scenario_md)
        (sorgente / "scenario" / "scenario_iniziale.json").write_bytes(
            scenario_json
        )
        scrivi_json(
            sorgente / "personaggi" / "profili_cast_iniziale.json",
            {
                "Luca": {"text": "Profilo di Luca", "campo_luca": 1},
                "Alba": {
                    "id": "id_sorgente",
                    "name": "Nome sorgente",
                    "text": "Profilo sorgente integrale",
                    "campo_sconosciuto": {"preservato": True},
                },
            },
        )
        immagini = sorgente / "immagini"
        immagini.mkdir()
        (immagini / "Alba.png").write_bytes(PNG_1X1)
        destinazione = self.radice / "pacchetto_builder"

        costruisci(sorgente, destinazione)

        self.assertEqual(scenario_md, (destinazione / "scenario.md").read_bytes())
        self.assertEqual(
            scenario_json,
            (destinazione / "source" / "scenario_iniziale.json").read_bytes(),
        )
        alba = json.loads(
            (destinazione / "characters" / "alba.json").read_text(encoding="utf-8")
        )
        self.assertEqual("alba", alba["id"])
        self.assertEqual("Alba", alba["name"])
        self.assertEqual({"preservato": True}, alba["campo_sconosciuto"])
        self.assertEqual("Profilo sorgente integrale", alba["text"])
        self.assertNotIn("profile", alba)
        self.assertEqual("media/characters/Alba.png", alba["image"])
        testo_gui = formatta_canone_personaggio(alba)
        self.assertIn("Profilo", testo_gui)
        self.assertEqual(1, testo_gui.count("Profilo sorgente integrale"))

    def test_modelli_pacchetto_hanno_mappature_immutabili(self) -> None:
        pacchetto = importa_pacchetto_da_cartella(self.pacchetto)
        with self.assertRaises(TypeError):
            pacchetto.narrative_settings["tone"] = "mutato"  # type: ignore[index]
        with self.assertRaises(TypeError):
            pacchetto.media[0].metadata["chiave"] = "mutata"  # type: ignore[index]

    def test_importazione_zip_persiste_il_mondo(self) -> None:
        archivio = self.radice / "mondo.zip"
        crea_zip(self.pacchetto, archivio)
        with ServizioMondi(self.database) as servizio:
            mondo = servizio.importa_da_zip(archivio)
            self.assertEqual(1, len(servizio.elenca_media(mondo.id)))

    def test_hash_errato_interrompe_prima_di_scrivere(self) -> None:
        manifest = json.loads((self.pacchetto / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"][0]["sha256"] = "0" * 64
        scrivi_json(self.pacchetto / "manifest.json", manifest)
        with self.assertRaisesRegex(ErroreManifest, "non corrisponde"):
            importa_pacchetto_da_cartella(self.pacchetto)
        with ServizioMondi(self.database) as servizio:
            self.assertEqual([], servizio.elenca_mondi())

    def test_manifest_assente_o_non_valido(self) -> None:
        (self.pacchetto / "manifest.json").unlink()
        with self.assertRaises(ErroreManifest):
            importa_pacchetto_da_cartella(self.pacchetto)
        (self.pacchetto / "manifest.json").write_text("[]", encoding="utf-8")
        with self.assertRaises(ErroreImportazione):
            importa_pacchetto_da_cartella(self.pacchetto)

    def test_id_entita_duplicato_viene_rifiutato(self) -> None:
        dati = json.loads((self.pacchetto / "characters" / "bruno.json").read_text(encoding="utf-8"))
        dati["id"] = "alba"
        scrivi_json(self.pacchetto / "characters" / "bruno.json", dati)
        aggiorna_manifest(self.pacchetto)
        with self.assertRaisesRegex(ErroreImportazione, "duplicato"):
            importa_pacchetto_da_cartella(self.pacchetto)

    def test_riferimento_relazione_e_media_inesistente_viene_rifiutato(self) -> None:
        dati = json.loads((self.pacchetto / "characters" / "alba.json").read_text(encoding="utf-8"))
        dati["relationships"][0]["entity_id"] = "assente"
        scrivi_json(self.pacchetto / "characters" / "alba.json", dati)
        aggiorna_manifest(self.pacchetto)
        with self.assertRaisesRegex(ErroreImportazione, "inesistente"):
            importa_pacchetto_da_cartella(self.pacchetto)

    def test_zip_path_traversal_e_assoluto_sono_rifiutati(self) -> None:
        for nome in ("../fuga.txt", "C:/fuga.txt", "/fuga.txt"):
            archivio = self.radice / (hashlib.sha256(nome.encode()).hexdigest() + ".zip")
            with zipfile.ZipFile(archivio, "w") as zip_file:
                zip_file.writestr(nome, b"x")
            with self.subTest(nome=nome), self.assertRaises(ErroreArchivioNonSicuro):
                importa_pacchetto_da_zip(archivio)

    def test_zip_rifiuta_link_simbolici_e_duplicati_case_insensitive(self) -> None:
        archivio_link = self.radice / "link.zip"
        with zipfile.ZipFile(archivio_link, "w") as zip_file:
            voce = zipfile.ZipInfo("collegamento")
            voce.create_system = 3
            voce.external_attr = (stat.S_IFLNK | 0o777) << 16
            zip_file.writestr(voce, "world.json")
        with self.assertRaises(ErroreArchivioNonSicuro):
            importa_pacchetto_da_zip(archivio_link)

        archivio_duplicato = self.radice / "duplicato.zip"
        with zipfile.ZipFile(archivio_duplicato, "w") as zip_file:
            zip_file.writestr("world.json", b"{}")
            zip_file.writestr("WORLD.JSON", b"{}")
        with self.assertRaises(ErroreArchivioNonSicuro):
            importa_pacchetto_da_zip(archivio_duplicato)

    def test_zip_con_separatori_windows_resta_compatibile(self) -> None:
        archivio = self.radice / "windows.zip"
        with zipfile.ZipFile(archivio, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file in sorted(self.pacchetto.rglob("*")):
                if file.is_file():
                    nome = file.relative_to(self.pacchetto).as_posix().replace("/", "\\")
                    zip_file.writestr(nome, file.read_bytes())
        pacchetto = importa_pacchetto_da_zip(archivio)
        self.assertEqual("mondo_tecnico", pacchetto.world_id)

    def test_file_nascosto_e_pacchetto_completo_incompleto_sono_rifiutati(self) -> None:
        (self.pacchetto / ".DS_Store").write_bytes(b"x")
        with self.assertRaises(ErroreImportazione):
            importa_pacchetto_da_cartella(self.pacchetto)
        (self.pacchetto / ".DS_Store").unlink()
        (self.pacchetto / "scenario.md").unlink()
        aggiorna_manifest(self.pacchetto)
        with self.assertRaisesRegex(ErroreImportazione, "scenario.md"):
            importa_pacchetto_da_cartella(self.pacchetto)

    def test_archivio_corrotto_restituisce_errore_specifico(self) -> None:
        archivio = self.radice / "corrotto.zip"
        archivio.write_bytes(b"non zip")
        with self.assertRaises(ErroreZipNonValido):
            importa_pacchetto_da_zip(archivio)

    def test_limite_dimensione_file_cartella(self) -> None:
        grande = self.pacchetto / "media" / "lore" / "grande.png"
        grande.parent.mkdir(parents=True, exist_ok=True)
        with grande.open("wb") as stream:
            stream.truncate(MAX_FILE_SIZE + 1)
        with self.assertRaisesRegex(ErroreImportazione, "limite"):
            importa_pacchetto_da_cartella(self.pacchetto)

    def test_sorgenti_e_media_restano_invariati(self) -> None:
        impronte_prima = {f.relative_to(self.pacchetto).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in self.pacchetto.rglob("*") if f.is_file()}
        with ServizioMondi(self.database) as servizio:
            mondo = servizio.importa_da_cartella(self.pacchetto)
            self.assertEqual(PNG_1X1, servizio.carica_media_contenuto(mondo.id, "ritratto_alba"))
        impronte_dopo = {f.relative_to(self.pacchetto).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in self.pacchetto.rglob("*") if f.is_file()}
        self.assertEqual(impronte_prima, impronte_dopo)

    def test_media_con_entita_inesistente_e_id_duplicato_viene_rifiutato(self) -> None:
        manifest = json.loads((self.pacchetto / "manifest.json").read_text(encoding="utf-8"))
        manifest["media"][0]["entity_id"] = "assente"
        scrivi_json(self.pacchetto / "manifest.json", manifest)
        with self.assertRaisesRegex(ErroreImportazione, "inesistente"):
            importa_pacchetto_da_cartella(self.pacchetto)

        manifest["media"][0]["entity_id"] = "alba"
        secondo = self.pacchetto / "media" / "characters" / "bruno.png"
        secondo.write_bytes(PNG_1X1)
        manifest["media"].append(
            {
                **manifest["media"][0],
                "path": "media/characters/bruno.png",
                "entity_id": "bruno",
            }
        )
        scrivi_json(self.pacchetto / "manifest.json", manifest)
        aggiorna_manifest(self.pacchetto)
        with self.assertRaisesRegex(ErroreImportazione, "duplicato"):
            importa_pacchetto_da_cartella(self.pacchetto)

    def test_file_sconosciuto_ammesso_viene_preservato_nell_export(self) -> None:
        nota = self.pacchetto / "source" / "nota.txt"
        nota.parent.mkdir()
        nota.write_bytes(b"byte tecnici invariati\r\n")
        aggiorna_manifest(self.pacchetto)
        with ServizioMondi(self.database) as servizio:
            mondo = servizio.importa_da_cartella(self.pacchetto)
            esportato = servizio.esporta(mondo.id, self.radice / "uscita").cartella
        self.assertEqual(nota.read_bytes(), (esportato / "source" / "nota.txt").read_bytes())

    def test_rollback_completo_se_inserimento_media_fallisce(self) -> None:
        pacchetto = importa_pacchetto_da_cartella(self.pacchetto)
        with ServizioMondi(self.database) as servizio:
            servizio.archivio._connessione.execute(
                """
                CREATE TRIGGER errore_media_task006 BEFORE INSERT ON media_assets
                BEGIN SELECT RAISE(ABORT, 'errore simulato'); END
                """
            )
            with self.assertRaisesRegex(ErroreImportazione, "nessun dato parziale"):
                servizio.importa_pacchetto_validato(pacchetto, str(self.pacchetto))
            for tabella in (
                "worlds", "source_files", "world_entities", "entity_state",
                "memories", "canonical_documents", "media_assets",
            ):
                conteggio = servizio.archivio._connessione.execute(
                    f"SELECT COUNT(*) FROM {tabella}"
                ).fetchone()[0]
                self.assertEqual(0, conteggio, tabella)

    def test_validatore_accetta_il_mondo_completo_importato(self) -> None:
        with ServizioMondi(self.database) as servizio:
            mondo = servizio.importa_da_cartella(self.pacchetto)
            rapporto = servizio.validazione.controlla_mondo(mondo.id)
        self.assertTrue(rapporto.superata)
        self.assertEqual((), rapporto.errori)

    def test_export_completo_reimportabile_e_media_byte_identici(self) -> None:
        destinazione = self.radice / "export"
        with ServizioMondi(self.database) as servizio:
            mondo = servizio.importa_da_cartella(self.pacchetto)
            servizio.salva(mondo.id, "Scenario modificato", {"tone": "misurato"})
            esportato = servizio.esporta(mondo.id, destinazione).cartella
        self.assertEqual(PNG_1X1, (esportato / "media" / "characters" / "alba.png").read_bytes())
        self.assertTrue((esportato / "characters" / "alba.json").is_file())
        with ServizioMondi(self.radice / "reimport.sqlite3") as servizio:
            reimportato = servizio.importa_da_cartella(esportato)
            self.assertEqual("Scenario modificato", reimportato.scenario)

    def test_migrazione_4_a_5_preserva_configurazione_e_dati(self) -> None:
        with ServizioMondi(self.database) as servizio:
            mondo = servizio.importa_da_cartella(SAMPLE_WORLD)
            prima_ai = servizio.carica_configurazione_ai()
            connessione = servizio.archivio._connessione
            connessione.execute("PRAGMA foreign_keys = OFF")
            connessione.execute("DROP TABLE narrative_turn_memories")
            connessione.execute("DROP TABLE narrative_turn_events")
            connessione.execute("DROP TABLE narrative_turns")
            connessione.execute("DROP TABLE narrative_sessions")
            connessione.execute("DROP TABLE media_assets")
            connessione.execute("DROP TABLE canonical_documents")
            connessione.execute("PRAGMA user_version = 4")
            connessione.commit()
        with ServizioMondi(self.database) as servizio:
            self.assertEqual(6, servizio.archivio._connessione.execute("PRAGMA user_version").fetchone()[0])
            self.assertEqual(mondo.id, servizio.carica_mondo(mondo.id).id)
            self.assertEqual(prima_ai, servizio.carica_configurazione_ai())

    def test_rollback_migrazione_4_a_5(self) -> None:
        with ServizioMondi(self.database) as servizio:
            connessione = servizio.archivio._connessione
            connessione.execute("DROP TABLE media_assets")
            connessione.execute("DROP TABLE canonical_documents")
            connessione.execute("CREATE VIEW canonical_documents AS SELECT 1 AS world_id")
            connessione.execute("PRAGMA user_version = 4")
            connessione.commit()
        with self.assertRaises(ErroreMigrazione):
            ServizioMondi(self.database)
        connessione = sqlite3.connect(self.database)
        try:
            self.assertEqual(4, connessione.execute("PRAGMA user_version").fetchone()[0])
            self.assertIsNone(connessione.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='media_assets'").fetchone())
        finally:
            connessione.close()

    def test_riapertura_schema_6_idempotente(self) -> None:
        with ServizioMondi(self.database):
            pass
        with ServizioMondi(self.database) as servizio:
            self.assertEqual(6, servizio.archivio._connessione.execute("PRAGMA user_version").fetchone()[0])

    def test_importazione_non_chiama_ollama(self) -> None:
        class TrasportoVietato:
            def invia(self, *args: object, **kwargs: object) -> object:
                raise AssertionError("La rete non deve essere usata")
        with ServizioMondi(self.database, TrasportoVietato()) as servizio:  # type: ignore[arg-type]
            servizio.importa_da_cartella(self.pacchetto)

    def test_gui_italiana_dichiara_sezioni_del_pacchetto(self) -> None:
        self.assertEqual("Personaggi", UI_TEXT["personaggi"])
        self.assertEqual("Lore", UI_TEXT["lore"])
        self.assertEqual("Regole e stile", UI_TEXT["regole_stile"])
        self.assertEqual("Media", UI_TEXT["media"])
        self.assertIn("ZIP", UI_TEXT["importa_zip"])

    def test_canone_personaggio_non_mostra_json_o_id_tecnici(self) -> None:
        testo = formatta_canone_personaggio(
            {
                "id": "uuid-segreto",
                "name": "Alba",
                "role": "Verificatrice",
                "location_id": "luogo_tecnico",
                "knowledge": ["Dato leggibile"],
                "relationships": [{"entity_id": "altro_uuid"}],
            }
        )
        self.assertIn("Alba", testo)
        self.assertIn("Dato leggibile", testo)
        self.assertNotIn("uuid", testo)
        self.assertNotIn("{", testo)
        self.assertNotIn('"', testo)

    def test_anteprima_nativa_e_fallback_media_sono_deterministici(self) -> None:
        self.assertTrue(anteprima_media_supportata("image/png"))
        self.assertTrue(anteprima_media_supportata("image/gif"))
        self.assertFalse(anteprima_media_supportata("image/jpeg"))
        self.assertIn("Anteprima non disponibile", UI_TEXT["anteprima_non_disponibile"])


if __name__ == "__main__":
    unittest.main()
