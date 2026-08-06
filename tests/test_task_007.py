from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from haria_engine.ai_models import ConfigurazioneAI, MessaggioChat
from haria_engine.app import UI_TEXT, ApplicazioneHaria
from haria_engine.async_coordinator import CoordinatoreAsincrono
from haria_engine.errors import ErroreRispostaAssistant, ErroreTurnoNarrativo
from haria_engine.http_transport import RispostaHTTP
from haria_engine.llm_service import ServizioAI
from haria_engine.narrative_prompt import formatta_prompt_visibile
from haria_engine.narrative_output_schema import schema_output_narrativo
from haria_engine.service import ServizioMondi
from tests.test_task_006 import crea_pacchetto_completo


def risposta_json(dati: object) -> RispostaHTTP:
    return RispostaHTTP(200, json.dumps(dati, ensure_ascii=False).encode("utf-8"))


class TrasportoSimulato:
    def __init__(self, *risposte: RispostaHTTP) -> None:
        self.risposte = list(risposte)
        self.richieste: list[dict[str, object]] = []

    def richiedi(
        self, metodo: str, url: str, *, headers=None, corpo=None, timeout: int
    ) -> RispostaHTTP:
        self.richieste.append(
            {
                "metodo": metodo,
                "url": url,
                "headers": dict(headers or {}),
                "corpo": corpo,
                "timeout": timeout,
                "thread": threading.get_ident(),
            }
        )
        return self.risposte.pop(0)


def configurazione() -> ConfigurazioneAI:
    return ConfigurazioneAI("ollama", "http://localhost:11434", "modello:locale", 12)


def output_narrativo(*, operations: list[dict[str, object]] | None = None) -> str:
    return json.dumps(
        {
            "narrative": "La porta del laboratorio vibra appena.",
            "elapsed_minutes": 1,
            "operations": operations or [],
            "memories": [],
        },
        ensure_ascii=False,
    )


class TestProviderNarrativo(unittest.TestCase):
    def test_payload_chat_esatto_con_stream_false(self) -> None:
        trasporto = TrasportoSimulato(
            risposta_json({"message": {"role": "assistant", "content": "{}"}})
        )
        messaggi = (
            MessaggioChat("system", "Istruzioni"),
            MessaggioChat("user", "Contesto"),
        )
        risposta = ServizioAI(trasporto).genera_turno_narrativo(
            configurazione(), messaggi
        )
        payload = json.loads(trasporto.richieste[0]["corpo"].decode("utf-8"))
        self.assertEqual("{}", risposta.contenuto)
        self.assertEqual("modello:locale", payload["model"])
        self.assertIs(payload["stream"], False)
        self.assertEqual(
            [
                {"role": "system", "content": "Istruzioni"},
                {"role": "user", "content": "Contesto"},
            ],
            payload["messages"],
        )
        self.assertEqual(schema_output_narrativo(), payload["format"])

    def test_turno_non_interroga_api_tags(self) -> None:
        trasporto = TrasportoSimulato(
            risposta_json({"message": {"role": "assistant", "content": "{}"}})
        )
        ServizioAI(trasporto).genera_turno_narrativo(
            configurazione(), (MessaggioChat("user", "azione"),)
        )
        self.assertEqual(1, len(trasporto.richieste))
        self.assertTrue(str(trasporto.richieste[0]["url"]).endswith("/api/chat"))

    def test_risposta_deve_essere_assistant_testuale(self) -> None:
        for risposta in (
            {},
            {"message": {"role": "user", "content": "testo"}},
            {"message": {"role": "assistant", "content": "   "}},
        ):
            with self.subTest(risposta=risposta), self.assertRaises(
                ErroreRispostaAssistant
            ):
                ServizioAI(TrasportoSimulato(risposta_json(risposta))).genera_turno_narrativo(
                    configurazione(), (MessaggioChat("user", "azione"),)
                )

    def test_trasporto_iniettato_e_unica_sorgente_di_rete(self) -> None:
        trasporto = TrasportoSimulato(
            risposta_json({"message": {"role": "assistant", "content": "ok"}})
        )
        ServizioAI(trasporto).genera_turno_narrativo(
            configurazione(), (MessaggioChat("user", "azione"),)
        )
        self.assertEqual("POST", trasporto.richieste[0]["metodo"])
        self.assertEqual(12, trasporto.richieste[0]["timeout"])


class TestServizioNarrativo(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)
        self.pacchetto = crea_pacchetto_completo(self.radice)
        self.servizio = ServizioMondi(self.radice / "task007.sqlite3")
        self.mondo = self.servizio.importa_da_cartella(self.pacchetto)

    def tearDown(self) -> None:
        self.servizio.chiudi()
        self.temporanea.cleanup()

    def prepara(self, storia: tuple[str, ...] = ()):
        return self.servizio.narrativa.prepara_turno(
            self.mondo.id, "Osservo la porta.", storia
        )

    def fotografia_database(self) -> tuple[object, ...]:
        connessione = self.servizio.archivio._connessione
        return (
            connessione.execute("PRAGMA user_version").fetchone()[0],
            connessione.execute("SELECT COUNT(*) FROM worlds").fetchone()[0],
            connessione.execute("SELECT COUNT(*) FROM world_versions").fetchone()[0],
            connessione.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            connessione.execute("SELECT COUNT(*) FROM entity_state").fetchone()[0],
            connessione.execute("SELECT COUNT(*) FROM memories").fetchone()[0],
            tuple(connessione.execute(
                "SELECT entity_id, current_status, location_id, holder_id, version "
                "FROM entity_state ORDER BY entity_id"
            )),
        )

    def test_contesto_usa_solo_servizi_applicativi_e_dati_correnti(self) -> None:
        turno = self.prepara()
        contenuto = turno.messaggi[1].contenuto
        self.assertIn("Mondo tecnico", contenuto)
        self.assertIn("Alba", contenuto)
        self.assertIn("Scenario tecnico", contenuto)
        self.assertIn("Una regola tecnica", contenuto)
        self.assertIn("Stile tecnico", contenuto)
        self.assertIn("Tone: chiaro", contenuto)
        self.assertIn("laboratorio", contenuto)
        self.assertIn("Il laboratorio esiste.", contenuto)

    def test_player_character_id_archiviato_deve_indicare_personaggio(self) -> None:
        connessione = self.servizio.archivio._connessione
        mondo_senza_player = json.dumps(
            {"id": self.mondo.id, "title": "Mondo tecnico", "language": "it"}
        ).encode("utf-8")
        connessione.execute(
            "UPDATE source_files SET content = ? WHERE world_id = ? AND relative_path = 'world.json'",
            (mondo_senza_player, self.mondo.id),
        )
        with self.assertRaisesRegex(ErroreTurnoNarrativo, "personaggio controllato"):
            self.prepara()

    def test_prompt_visibile_coincide_con_i_messaggi_inviabili(self) -> None:
        turno = self.prepara()
        self.assertEqual(
            formatta_prompt_visibile(turno.messaggi), turno.prompt_visibile
        )
        self.assertEqual(("system", "user"), tuple(m.ruolo for m in turno.messaggi))
        self.assertNotIn("Ã", turno.prompt_visibile)
        self.assertNotIn("â€", turno.prompt_visibile)
        self.assertIn("verità", turno.prompt_visibile)

    def test_operazioni_vuote_superano_il_dry_run(self) -> None:
        proposta = self.servizio.narrativa.valida_risposta(
            self.prepara(), output_narrativo(), datetime.now(timezone.utc)
        )
        self.assertEqual((), proposta.operations)
        self.assertEqual("La porta del laboratorio vibra appena.", proposta.narrative)

    def test_operazione_non_valida_e_rifiutata_senza_scritture(self) -> None:
        prima = self.fotografia_database()
        operazione = {
            "type": "move",
            "entity_id": "alba",
            "location_id": "luogo_inesistente",
            "reason": "Tentativo non valido",
        }
        with self.assertRaisesRegex(ErroreTurnoNarrativo, "non supera"):
            self.servizio.narrativa.valida_risposta(
                self.prepara(),
                output_narrativo(operations=[operazione]),
                datetime.now(timezone.utc),
            )
        self.assertEqual(prima, self.fotografia_database())

    def test_successo_non_modifica_schema_eventi_memorie_o_stato(self) -> None:
        prima = self.fotografia_database()
        self.servizio.narrativa.valida_risposta(
            self.prepara(), output_narrativo(), datetime.now(timezone.utc)
        )
        self.assertEqual(prima, self.fotografia_database())
        self.assertEqual(6, prima[0])

    def test_contesto_limita_cronologia_a_venti_voci(self) -> None:
        storia = tuple(f"Messaggio {indice}" for indice in range(25))
        contenuto = self.prepara(storia).messaggi[1].contenuto
        self.assertNotIn("Messaggio 4\n", contenuto)
        self.assertIn("Messaggio 5", contenuto)
        self.assertIn("Messaggio 24", contenuto)


class TestIntegrazioneInterfacciaNarrativa(unittest.TestCase):
    def test_turno_in_corso_mostra_il_prompt_inviato_non_input_modificato(self) -> None:
        applicazione = object.__new__(ApplicazioneHaria)
        applicazione._turno_corrente = object()
        applicazione._prompt_narrativo_corrente = "PROMPT REALMENTE INVIATO"
        applicazione.input_narrativo = mock.Mock()
        applicazione.input_narrativo.get.return_value = "Azione modificata dopo l'invio"
        applicazione._prepara_turno_narrativo = mock.Mock(
            side_effect=AssertionError("Il prompt non deve essere rigenerato")
        )
        applicazione.radice = object()
        finestra = mock.Mock()
        testo = mock.Mock()

        with mock.patch("haria_engine.app.tk.Toplevel", return_value=finestra), mock.patch(
            "haria_engine.app.tk.Text", return_value=testo
        ):
            applicazione._mostra_prompt_narrativo()

        applicazione._prepara_turno_narrativo.assert_not_called()
        testo.insert.assert_called_once_with("1.0", "PROMPT REALMENTE INVIATO")

    def test_coordinatore_ignora_risposta_tardiva_dopo_chiusura(self) -> None:
        coordinatore = CoordinatoreAsincrono()
        via = threading.Event()

        def risposta_tardiva() -> str:
            via.wait(1)
            return "non deve essere consegnata"

        self.assertTrue(coordinatore.avvia("turno_narrativo", risposta_tardiva))
        coordinatore.chiudi()
        via.set()
        time.sleep(0.03)
        self.assertEqual((), coordinatore.raccogli())

    def test_testi_gioca_sono_italiani_e_dichiarano_partita_persistente(self) -> None:
        self.assertEqual("Gioca", UI_TEXT["gioca"])
        self.assertEqual("Invia", UI_TEXT["invia_turno"])
        self.assertEqual("Mostra prompt", UI_TEXT["mostra_prompt"])
        self.assertEqual(
            "Partita locale persistente",
            UI_TEXT["anteprima_narrativa"],
        )


if __name__ == "__main__":
    unittest.main()
