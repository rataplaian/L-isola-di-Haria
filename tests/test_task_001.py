from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from haria_engine.app import ETICHETTE_IMPOSTAZIONI, UI_TEXT
from haria_engine.errors import ErroreEsportazione, ErroreImportazione
from haria_engine.service import ServizioMondi


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


class TestCodexTask001(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)
        self.sorgente = self.radice / "mini_bibbia"
        shutil.copytree(MINI_BIBBIA, self.sorgente)
        self.database = self.radice / "dati" / "haria.sqlite3"
        self.servizio: ServizioMondi | None = ServizioMondi(self.database)

    def tearDown(self) -> None:
        if self.servizio is not None:
            self.servizio.chiudi()
        self.temporanea.cleanup()

    def importa(self):
        assert self.servizio is not None
        return self.servizio.importa_da_cartella(self.sorgente)

    def esporta_con_errore_simulato(self, mondo_id: str, destinazione: Path) -> None:
        assert self.servizio is not None

        def scrittura_parziale(_mondo, cartella_temporanea: Path) -> None:
            (cartella_temporanea / "file_parziale.txt").write_text(
                "contenuto incompleto", encoding="utf-8"
            )
            raise OSError("Errore di scrittura simulato")

        with mock.patch.object(
            self.servizio,
            "_scrivi_esportazione",
            side_effect=scrittura_parziale,
        ):
            self.servizio.esporta(mondo_id, destinazione)

    def test_import_valido_mostra_titolo_scenario_e_impostazioni(self) -> None:
        mondo = self.importa()

        self.assertEqual("Haria — Mini mondo di collaudo", mondo.titolo)
        self.assertIn("# Scenario", mondo.scenario)
        self.assertIn("Élise è presente", mondo.scenario)
        self.assertEqual("seconda persona", mondo.impostazioni_narrative["point_of_view"])
        self.assertEqual(1, mondo.versione_corrente)

    def test_import_file_mancante_restituisce_errore_italiano(self) -> None:
        (self.sorgente / "scenario.md").unlink()

        with self.assertRaisesRegex(
            ErroreImportazione, "Mancano i file obbligatori.*scenario.md"
        ):
            self.importa()

    def test_modifica_scenario_e_creazione_di_ogni_versione(self) -> None:
        mondo = self.importa()
        assert self.servizio is not None

        seconda = self.servizio.salva(
            mondo.id, "Scenario modificato in italiano.", mondo.impostazioni_narrative
        )
        terza = self.servizio.salva(
            mondo.id, "Scenario modificato in italiano.", mondo.impostazioni_narrative
        )

        self.assertEqual("Scenario modificato in italiano.", terza.scenario)
        self.assertEqual(2, seconda.versione_corrente)
        self.assertEqual(3, terza.versione_corrente)
        self.assertEqual([3, 2, 1], [v.numero for v in self.servizio.cronologia(mondo.id)])

    def test_impostazioni_narrative_modificabili_e_versionate(self) -> None:
        mondo = self.importa()
        assert self.servizio is not None
        impostazioni = dict(mondo.impostazioni_narrative)
        impostazioni["tone"] = "misurato e contemplativo"

        aggiornato = self.servizio.salva(mondo.id, mondo.scenario, impostazioni)

        self.assertEqual(
            "misurato e contemplativo", aggiornato.impostazioni_narrative["tone"]
        )

    def test_ripristino_crea_una_nuova_versione_recuperabile(self) -> None:
        originale = self.importa()
        assert self.servizio is not None
        modificato = self.servizio.salva(
            originale.id,
            "Secondo scenario",
            originale.impostazioni_narrative,
        )

        ripristinato = self.servizio.ripristina(modificato.id, 1)

        self.assertEqual(originale.scenario, ripristinato.scenario)
        self.assertEqual(3, ripristinato.versione_corrente)
        versioni = self.servizio.cronologia(originale.id)
        self.assertEqual("Ripristino della versione 1", versioni[0].motivo)
        self.assertEqual("Secondo scenario", versioni[1].scenario)

    def test_persistenza_dopo_chiusura_e_riapertura(self) -> None:
        mondo = self.importa()
        assert self.servizio is not None
        salvato = self.servizio.salva(
            mondo.id,
            "Scenario persistente dopo il riavvio",
            mondo.impostazioni_narrative,
        )
        self.servizio.chiudi()
        self.servizio = ServizioMondi(self.database)

        ricaricato = self.servizio.carica_mondo(salvato.id)

        self.assertEqual(salvato.scenario, ricaricato.scenario)
        self.assertEqual(salvato.versione_corrente, ricaricato.versione_corrente)
        self.assertEqual(2, len(self.servizio.cronologia(salvato.id)))

    def test_database_e_realmente_sqlite(self) -> None:
        self.importa()
        self.assertEqual(b"SQLite format 3\x00", self.database.read_bytes()[:16])

    def test_esportazione_contiene_mondo_aggiornato_senza_esporlo_nella_ui(self) -> None:
        mondo = self.importa()
        assert self.servizio is not None
        impostazioni = dict(mondo.impostazioni_narrative)
        impostazioni["tone"] = "sobrio"
        aggiornato = self.servizio.salva(
            mondo.id, "# Scenario\n\nScenario esportato.", impostazioni
        )

        risultato = self.servizio.esporta(aggiornato.id, self.radice / "esportazioni")
        world_esportato = json.loads(
            (risultato.cartella / "world.json").read_text(encoding="utf-8")
        )

        self.assertEqual("# Scenario\n\nScenario esportato.", (risultato.cartella / "scenario.md").read_text(encoding="utf-8"))
        self.assertEqual("Scenario esportato.", world_esportato["scenario"])
        self.assertEqual("sobrio", world_esportato["narrative_style"]["tone"])
        self.assertEqual(2, world_esportato["version"])
        self.assertTrue((risultato.cartella / "characters.json").is_file())
        self.assertNotIn("JSON", " ".join(UI_TEXT.values()).upper())

    def test_file_sorgente_non_vengono_mai_modificati(self) -> None:
        prima = impronte_cartella(self.sorgente)
        mondo = self.importa()
        assert self.servizio is not None
        self.servizio.salva(
            mondo.id, "Scenario interno modificato", mondo.impostazioni_narrative
        )
        self.servizio.ripristina(mondo.id, 1)
        self.servizio.esporta(mondo.id, self.radice / "esportazioni")
        dopo = impronte_cartella(self.sorgente)

        self.assertEqual(prima, dopo)

    def test_errore_durante_esportazione_restituisce_messaggio_italiano(self) -> None:
        mondo = self.importa()

        with self.assertRaisesRegex(
            ErroreEsportazione, "Nessuna cartella parziale.*nessun file sorgente"
        ):
            self.esporta_con_errore_simulato(
                mondo.id, self.radice / "esportazione_fallita"
            )

    def test_errore_esportazione_non_lascia_cartelle_parziali(self) -> None:
        mondo = self.importa()
        destinazione = self.radice / "esportazione_fallita"

        with self.assertRaises(ErroreEsportazione):
            self.esporta_con_errore_simulato(mondo.id, destinazione)

        self.assertTrue(destinazione.is_dir())
        self.assertEqual([], list(destinazione.iterdir()))

    def test_errore_esportazione_mantiene_integri_i_file_sorgente(self) -> None:
        prima = impronte_cartella(self.sorgente)
        mondo = self.importa()

        with self.assertRaises(ErroreEsportazione):
            self.esporta_con_errore_simulato(
                mondo.id, self.radice / "esportazione_fallita"
            )

        self.assertEqual(prima, impronte_cartella(self.sorgente))

    def test_interfaccia_dichiara_funzioni_e_impostazioni_in_italiano(self) -> None:
        testi_richiesti = {
            "Importa mini-Bibbia",
            "Scenario",
            "Salva nuova versione",
            "Cronologia versioni",
            "Ripristina versione selezionata",
            "Esporta mondo",
            "Impostazioni narrative",
        }
        self.assertTrue(testi_richiesti.issubset(set(UI_TEXT.values())))
        self.assertEqual("Punto di vista", ETICHETTE_IMPOSTAZIONI["point_of_view"])
        self.assertEqual("Tempo verbale", ETICHETTE_IMPOSTAZIONI["tense"])
        self.assertEqual("Tono", ETICHETTE_IMPOSTAZIONI["tone"])

    def test_verifica_avvio_da_riga_di_comando(self) -> None:
        database_check = self.radice / "verifica" / "avvio.sqlite3"
        processo = subprocess.run(
            [
                sys.executable,
                "-m",
                "haria_engine",
                "--check",
                "--database",
                str(database_check),
            ],
            cwd=RADICE_PROGETTO,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(0, processo.returncode, processo.stderr)
        self.assertIn("Verifica di avvio completata", processo.stdout)
        self.assertTrue(database_check.is_file())


if __name__ == "__main__":
    unittest.main()

