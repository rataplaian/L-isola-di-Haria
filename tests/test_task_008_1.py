from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from haria_engine.ai_models import ConfigurazioneAI, MessaggioChat, RispostaTestuale
from haria_engine.app import ApplicazioneHaria, UI_TEXT
from haria_engine.async_coordinator import EsitoAsincrono
from haria_engine.errors import ErroreHTTPProvider, ErroreTimeoutOllama
from haria_engine.http_transport import RispostaHTTP
from haria_engine.llm_service import ServizioAI
from haria_engine.narrative_output_schema import (
    NARRATIVE_OUTPUT_SCHEMA,
    schema_output_narrativo,
)
from haria_engine.narrative_parser import (
    ErroreOutputNarrativoNonRiparabile,
    ErroreStrutturaOutputNarrativo,
    parse_output_narrativo,
)
from haria_engine.narrative_prompt import (
    ContestoTurnoNarrativo,
    costruisci_messaggi_turno,
)
from haria_engine.service import ServizioMondi
from tests.test_task_006 import crea_pacchetto_completo


def risposta_http_assistant(contenuto: str) -> RispostaHTTP:
    return RispostaHTTP(
        200,
        json.dumps(
            {"message": {"role": "assistant", "content": contenuto}},
            ensure_ascii=False,
        ).encode("utf-8"),
    )


def output_valido(*, operations: list[dict[str, object]] | None = None) -> str:
    return json.dumps(
        {
            "narrative": "La scena prosegue senza alterare il canone.",
            "elapsed_minutes": 1,
            "operations": operations or [],
            "memories": [],
        },
        ensure_ascii=False,
    )


def output_errore_reale() -> str:
    return json.dumps(
        {
            "narrative": "Alba osserva la chiave.",
            "elapsed_minutes": 1,
            "operations": [
                {
                    "type": "event",
                    "event_type": "osservazione",
                    "actor_id": "alba",
                    "target_id": "chiave",
                    "location_id": "laboratorio",
                    "reason": "Alba osserva la chiave.",
                    "associated_emotion": "curiosità",
                    "certainty": 90,
                    "content": "La chiave ha un segno.",
                    "interpretation": None,
                    "operation_index": 0,
                    "source_entity_id": None,
                    "source_type": "direct_observation",
                }
            ],
            "memories": [],
        },
        ensure_ascii=False,
    )


class TrasportoSequenziale:
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


class TestContrattoOutputNarrativo(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = schema_output_narrativo()

    def test_schema_radice_e_immutabile_con_quattro_chiavi(self) -> None:
        self.assertIs(self.schema["additionalProperties"], False)
        self.assertEqual(
            {"narrative", "elapsed_minutes", "operations", "memories"},
            set(self.schema["properties"]),
        )
        self.assertEqual(
            {"narrative", "elapsed_minutes", "operations", "memories"},
            set(self.schema["required"]),
        )
        with self.assertRaises(TypeError):
            NARRATIVE_OUTPUT_SCHEMA["type"] = "array"  # type: ignore[index]

    def test_cinque_operazioni_hanno_contratti_espliciti(self) -> None:
        varianti = self.schema["properties"]["operations"]["items"]["oneOf"]
        per_tipo = {
            voce["properties"]["type"]["const"]: voce for voce in varianti
        }
        self.assertEqual(
            {"move", "transfer", "state_change", "event", "epistemic"},
            set(per_tipo),
        )
        obbligatorie = {
            "move": {"type", "entity_id", "location_id", "reason"},
            "transfer": {"type", "object_id", "holder_id", "reason"},
            "state_change": {"type", "target_id", "reason"},
            "event": {"type", "event_type", "reason"},
            "epistemic": {"type", "actor_id", "reason"},
        }
        campi_memoria = {
            "associated_emotion",
            "certainty",
            "content",
            "interpretation",
            "operation_index",
            "source_entity_id",
            "source_type",
        }
        for tipo, variante in per_tipo.items():
            with self.subTest(tipo=tipo):
                self.assertIs(variante["additionalProperties"], False)
                self.assertEqual(obbligatorie[tipo], set(variante["required"]))
                self.assertFalse(campi_memoria & set(variante["properties"]))
        self.assertIn("allOf", per_tipo["state_change"])

    def test_epistemic_richiede_actor_id_stringa_non_nulla(self) -> None:
        varianti = self.schema["properties"]["operations"]["items"]["oneOf"]
        epistemic = next(
            voce
            for voce in varianti
            if voce["properties"]["type"]["const"] == "epistemic"
        )
        self.assertIn("actor_id", epistemic["required"])
        actor_id = epistemic["properties"]["actor_id"]
        self.assertEqual("string", actor_id["type"])
        self.assertEqual(1, actor_id["minLength"])
        self.assertNotIn("anyOf", actor_id)

    def test_schema_serializzato_non_contiene_pattern(self) -> None:
        def verifica(valore: object) -> None:
            if isinstance(valore, dict):
                self.assertNotIn("pattern", valore)
                for elemento in valore.values():
                    verifica(elemento)
            elif isinstance(valore, list):
                for elemento in valore:
                    verifica(elemento)

        verifica(json.loads(json.dumps(self.schema, ensure_ascii=False)))

    def test_parser_rifiuta_testo_obbligatorio_composto_da_spazi(self) -> None:
        dati = json.loads(
            output_valido(
                operations=[
                    {
                        "type": "epistemic",
                        "actor_id": "   ",
                        "reason": "Il personaggio apprende un fatto.",
                    }
                ]
            )
        )
        with self.assertRaises(ErroreStrutturaOutputNarrativo):
            parse_output_narrativo(json.dumps(dati, ensure_ascii=False))

    def test_memorie_pubblicizzano_solo_combinazioni_generabili(self) -> None:
        testo = json.dumps(self.schema, ensure_ascii=False)
        self.assertNotIn("canonical_knowledge", testo)
        self.assertNotIn("imported_background", testo)
        varianti = self.schema["properties"]["memories"]["items"]["oneOf"]
        per_fonte = {
            voce["properties"]["source_type"]["const"]: voce
            for voce in varianti
        }
        self.assertEqual(
            {
                "direct_observation",
                "told_by_character",
                "inference",
                "self_experience",
            },
            set(per_fonte),
        )
        self.assertIn("operation_index", per_fonte["direct_observation"]["required"])
        self.assertIn("source_entity_id", per_fonte["told_by_character"]["required"])
        self.assertIn("source_memory_ids", per_fonte["inference"]["required"])
        for fonte in (
            "direct_observation",
            "told_by_character",
            "self_experience",
        ):
            self.assertNotIn("source_memory_ids", per_fonte[fonte]["properties"])

    def test_prompt_serializza_la_stessa_fonte_del_provider(self) -> None:
        contesto = ContestoTurnoNarrativo(
            world_title="Mondo",
            player_name="Luca",
            user_input="Osservo.",
            scenario="Scenario",
        )
        sistema = costruisci_messaggi_turno(contesto)[0].contenuto
        dopo_marcatore = sistema.split("SCHEMA JSON OBBLIGATORIO:\n", 1)[1]
        schema_prompt, indice = json.JSONDecoder().raw_decode(dopo_marcatore)
        self.assertFalse(dopo_marcatore[indice:].strip())
        self.assertEqual(self.schema, schema_prompt)
        self.assertIn("operations contiene esclusivamente cambiamenti", sistema)
        self.assertIn("Non copiare campi", sistema)

    def test_errore_reale_e_strutturale_e_preciso(self) -> None:
        with self.assertRaises(ErroreStrutturaOutputNarrativo) as contesto:
            parse_output_narrativo(output_errore_reale())
        messaggio = str(contesto.exception)
        for campo in (
            "associated_emotion",
            "certainty",
            "content",
            "interpretation",
            "operation_index",
            "source_entity_id",
            "source_type",
        ):
            self.assertIn(campo, messaggio)
        with self.assertRaises(ErroreOutputNarrativoNonRiparabile):
            parse_output_narrativo("{json non valido")
        with self.assertRaises(ErroreOutputNarrativoNonRiparabile):
            parse_output_narrativo("[]")


class TestPayloadOllamaStrutturato(unittest.TestCase):
    def configurazione(self) -> ConfigurazioneAI:
        return ConfigurazioneAI(
            "ollama", "http://localhost:11434", "qwen3:4b-instruct", 300
        )

    def test_turno_invia_format_schema_e_stream_false(self) -> None:
        trasporto = TrasportoSequenziale(risposta_http_assistant(output_valido()))
        ServizioAI(trasporto).genera_turno_narrativo(
            self.configurazione(),
            (MessaggioChat("system", "Sistema"), MessaggioChat("user", "Azione")),
        )
        payload = json.loads(trasporto.richieste[0]["corpo"].decode("utf-8"))
        self.assertIs(payload["stream"], False)
        self.assertEqual(schema_output_narrativo(), payload["format"])
        self.assertNotIn("tools", payload)
        self.assertNotIn("options", payload)

    def test_prova_semplice_non_invia_schema_narrativo(self) -> None:
        trasporto = TrasportoSequenziale(
            RispostaHTTP(200, b'{"models":[{"name":"qwen3:4b-instruct"}]}'),
            risposta_http_assistant("Funzionamento confermato."),
        )
        ServizioAI(trasporto).genera_testo_di_prova(
            self.configurazione(), "Conferma il funzionamento."
        )
        payload = json.loads(trasporto.richieste[1]["corpo"].decode("utf-8"))
        self.assertNotIn("format", payload)


class BaseRiparazioneTurno(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)
        self.database = self.radice / "task008_1.sqlite3"
        self.servizio = ServizioMondi(self.database)
        self.mondo = self.servizio.importa_da_cartella(
            crea_pacchetto_completo(self.radice)
        )
        self.turno = self.servizio.narrativa.prepara_turno(
            self.mondo.id, "Osservo la chiave."
        )
        self.configurazione = ConfigurazioneAI(
            "ollama", "http://localhost:11434", "qwen3:4b-instruct", 300
        )

    def tearDown(self) -> None:
        self.servizio.chiudi()
        self.temporanea.cleanup()

    def fotografia(self) -> tuple[object, ...]:
        connessione = self.servizio.archivio._connessione
        tabelle = (
            "narrative_turns",
            "events",
            "event_entities",
            "memories",
            "memory_entities",
            "memory_sources",
            "narrative_turn_events",
            "narrative_turn_memories",
        )
        conteggi = tuple(
            connessione.execute(f"SELECT COUNT(*) FROM {tabella}").fetchone()[0]
            for tabella in tabelle
        )
        stati = tuple(
            connessione.execute(
                "SELECT entity_id, current_status, location_id, holder_id, version "
                "FROM entity_state ORDER BY entity_id"
            )
        )
        sessione = tuple(
            connessione.execute(
                "SELECT current_time, next_turn_number FROM narrative_sessions "
                "WHERE world_id = ?",
                (self.mondo.id,),
            ).fetchone()
        )
        return conteggi, stati, sessione

    def applicazione(self, trasporto: TrasportoSequenziale) -> ApplicazioneHaria:
        self.servizio.ai = ServizioAI(trasporto)
        applicazione = object.__new__(ApplicazioneHaria)
        applicazione.servizio = self.servizio
        applicazione.mondo_corrente = self.mondo
        applicazione._turno_corrente = self.turno
        applicazione._configurazione_turno_corrente = self.configurazione
        applicazione._correzione_turno_in_corso = False
        applicazione._prompt_narrativo_corrente = self.turno.prompt_visibile
        applicazione._coordinatore_ai = mock.Mock()
        applicazione._coordinatore_ai.avvia.return_value = True
        applicazione.etichetta_stato_gioco = mock.Mock()
        applicazione.input_narrativo = mock.Mock()
        applicazione._carica_conversazione_narrativa = mock.Mock()
        applicazione._aggiorna_stato_mondo = mock.Mock()
        applicazione._aggiorna_memorie = mock.Mock()
        return applicazione

    def esegui_richiesta(
        self,
        trasporto: TrasportoSequenziale,
        messaggi: tuple[MessaggioChat, ...],
    ) -> RispostaTestuale:
        return self.servizio.ai.genera_turno_narrativo(
            self.configurazione, messaggi
        )


class TestRiparazioneSingola(BaseRiparazioneTurno):
    def test_prima_risposta_valida_una_richiesta_e_un_salvataggio(self) -> None:
        trasporto = TrasportoSequenziale(risposta_http_assistant(output_valido()))
        app = self.applicazione(trasporto)
        risposta = self.esegui_richiesta(trasporto, self.turno.messaggi)
        with mock.patch("haria_engine.app.messagebox.showerror") as errore:
            app._mostra_esito_turno_narrativo(
                EsitoAsincrono("turno_narrativo", risultato=risposta)
            )
        self.assertEqual(1, len(trasporto.richieste))
        app._coordinatore_ai.avvia.assert_not_called()
        errore.assert_not_called()
        turni = self.servizio.archivio.elenca_turni_narrativi(self.mondo.id)
        self.assertEqual(1, len(turni))
        self.assertEqual(self.turno.prompt_visibile, turni[0].prompt_text)
        self.assertEqual(output_valido(), turni[0].raw_model_output)

    def test_errore_reale_viene_riparato_con_due_richieste_e_un_turno(self) -> None:
        prima_raw = output_errore_reale()
        seconda_raw = output_valido()
        trasporto = TrasportoSequenziale(
            risposta_http_assistant(prima_raw),
            risposta_http_assistant(seconda_raw),
        )
        app = self.applicazione(trasporto)
        prima = self.esegui_richiesta(trasporto, self.turno.messaggi)
        fotografia_iniziale = self.fotografia()
        with mock.patch("haria_engine.app.messagebox.showerror") as errore:
            app._mostra_esito_turno_narrativo(
                EsitoAsincrono("turno_narrativo", risultato=prima)
            )
            self.assertEqual(fotografia_iniziale, self.fotografia())
            errore.assert_not_called()
            app.etichetta_stato_gioco.configure.assert_called_with(
                text=UI_TEXT["correzione_formato_in_corso"]
            )
            turno_corretto = app._turno_corrente
            chiamata = app._coordinatore_ai.avvia.call_args.args
            self.assertEqual("correzione_turno_narrativo", chiamata[0])
            seconda = chiamata[1](*chiamata[2:])
            app._mostra_esito_turno_narrativo(
                EsitoAsincrono("correzione_turno_narrativo", risultato=seconda)
            )

        self.assertEqual(2, len(trasporto.richieste))
        self.assertEqual(1, app._coordinatore_ai.avvia.call_count)
        payload_iniziale, payload_correzione = (
            json.loads(richiesta["corpo"].decode("utf-8"))
            for richiesta in trasporto.richieste
        )
        self.assertEqual(payload_iniziale["format"], payload_correzione["format"])
        self.assertEqual(
            payload_iniziale["messages"], payload_correzione["messages"][:2]
        )
        self.assertEqual(
            ["system", "user", "assistant", "user"],
            [messaggio["role"] for messaggio in payload_correzione["messages"]],
        )
        self.assertEqual(prima_raw, payload_correzione["messages"][2]["content"])
        self.assertIn(
            "campi non ammessi", payload_correzione["messages"][3]["content"]
        )
        turni = self.servizio.archivio.elenca_turni_narrativi(self.mondo.id)
        self.assertEqual(1, len(turni))
        self.assertIsNotNone(turno_corretto)
        self.assertEqual(turno_corretto.prompt_visibile, turni[0].prompt_text)
        self.assertIn(prima_raw, turni[0].prompt_text)
        self.assertIn("Correggi soltanto la struttura", turni[0].prompt_text)
        self.assertEqual(seconda_raw, turni[0].raw_model_output)

    def test_secondo_output_errato_non_avvia_un_terzo_tentativo(self) -> None:
        prima_raw = output_errore_reale()
        seconda_raw = json.dumps(
            {"narrative": "Ancora incompleto", "operations": [], "memories": []}
        )
        trasporto = TrasportoSequenziale(
            risposta_http_assistant(prima_raw),
            risposta_http_assistant(seconda_raw),
        )
        app = self.applicazione(trasporto)
        prima = self.esegui_richiesta(trasporto, self.turno.messaggi)
        iniziale = self.fotografia()
        with mock.patch("haria_engine.app.messagebox.showerror") as errore:
            app._mostra_esito_turno_narrativo(
                EsitoAsincrono("turno_narrativo", risultato=prima)
            )
            chiamata = app._coordinatore_ai.avvia.call_args.args
            seconda = chiamata[1](*chiamata[2:])
            app._mostra_esito_turno_narrativo(
                EsitoAsincrono("correzione_turno_narrativo", risultato=seconda)
            )
            errore.assert_called_once_with(
                UI_TEXT["errore"], UI_TEXT["correzione_formato_fallita"]
            )
        self.assertEqual(2, len(trasporto.richieste))
        self.assertEqual(1, app._coordinatore_ai.avvia.call_count)
        self.assertEqual(iniziale, self.fotografia())

    def test_nessun_retry_per_errori_non_strutturali(self) -> None:
        casi = (
            (RispostaTestuale("{json non valido"), None),
            (RispostaTestuale("[]"), None),
            (
                RispostaTestuale(
                    output_valido(
                        operations=[
                            {
                                "type": "move",
                                "entity_id": "alba",
                                "location_id": "inesistente",
                                "reason": "Spostamento impossibile",
                            }
                        ]
                    )
                ),
                None,
            ),
            (None, ErroreTimeoutOllama("Ollama non ha risposto in tempo.")),
            (None, ErroreHTTPProvider("Ollama ha restituito un errore HTTP.")),
        )
        for risultato, errore_risposta in casi:
            with self.subTest(risultato=risultato, errore=errore_risposta):
                trasporto = TrasportoSequenziale()
                app = self.applicazione(trasporto)
                iniziale = self.fotografia()
                with mock.patch("haria_engine.app.messagebox.showerror"):
                    app._mostra_esito_turno_narrativo(
                        EsitoAsincrono(
                            "turno_narrativo",
                            risultato=risultato,
                            errore=errore_risposta,
                        )
                    )
                app._coordinatore_ai.avvia.assert_not_called()
                self.assertEqual(iniziale, self.fotografia())


if __name__ == "__main__":
    unittest.main()
