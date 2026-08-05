from __future__ import annotations

import json
import shutil
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from haria_engine.ai_models import (
    OLLAMA_URL_PREDEFINITO,
    ConfigurazioneAI,
    valida_configurazione_ai,
)
from haria_engine.app import UI_TEXT
from haria_engine.async_coordinator import CoordinatoreAsincrono
from haria_engine.errors import (
    ErroreConfigurazioneAI,
    ErroreCorpoHTTP,
    ErroreElencoModelli,
    ErroreHTTPProvider,
    ErroreLimiteTesto,
    ErroreMigrazione,
    ErroreModelloNonDisponibile,
    ErroreOllamaNonRaggiungibile,
    ErroreRispostaAssistant,
    ErroreRispostaJSON,
    ErroreStrutturaRisposta,
    ErroreTimeoutOllama,
    ErroreVersioneMancante,
)
from haria_engine.http_transport import (
    LIMITE_CORPO_HTTP,
    RispostaHTTP,
    TrasportoUrllib,
)
from haria_engine.service import ServizioMondi


RADICE_PROGETTO = Path(__file__).resolve().parents[1]
MINI_BIBBIA = RADICE_PROGETTO / "sample_world"


def risposta_json(dati: object, status: int = 200) -> RispostaHTTP:
    return RispostaHTTP(
        status=status,
        corpo=json.dumps(dati, ensure_ascii=False).encode("utf-8"),
    )


class TrasportoSimulato:
    def __init__(self, *risposte: RispostaHTTP | Exception) -> None:
        self.risposte = list(risposte)
        self.richieste: list[dict[str, object]] = []

    def richiedi(
        self,
        metodo: str,
        url: str,
        *,
        headers=None,
        corpo: bytes | None = None,
        timeout: int,
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
        risposta = self.risposte.pop(0)
        if isinstance(risposta, Exception):
            raise risposta
        return risposta


class RispostaUrllibSimulata:
    def __init__(
        self, corpo: bytes, *, status: int = 200, content_length: str | None = None
    ) -> None:
        self.corpo = corpo
        self.status = status
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length
        self.limite_letto: int | None = None

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def getcode(self) -> int:
        return self.status

    def read(self, limite: int) -> bytes:
        self.limite_letto = limite
        return self.corpo[:limite]


def attendi_esito(
    coordinatore: CoordinatoreAsincrono, timeout: float = 2.0
):
    scadenza = time.monotonic() + timeout
    while time.monotonic() < scadenza:
        esiti = coordinatore.raccogli()
        if esiti:
            return esiti[0]
        time.sleep(0.01)
    raise AssertionError("Il worker asincrono non ha restituito un esito.")


class TestConfigurazioneESchema4(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)

    def tearDown(self) -> None:
        self.temporanea.cleanup()

    def test_database_vuoto_apre_direttamente_schema_4_con_predefiniti(self) -> None:
        database = self.radice / "vuoto.sqlite3"
        with ServizioMondi(database) as servizio:
            configurazione = servizio.carica_configurazione_ai()
            versione = servizio.archivio._connessione.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            self.assertEqual(6, versione)
        self.assertEqual("ollama", configurazione.provider)
        self.assertEqual(OLLAMA_URL_PREDEFINITO, configurazione.ollama_base_url)
        self.assertEqual("", configurazione.ollama_model)
        self.assertEqual(30, configurazione.ollama_timeout_seconds)

    def test_database_vuoto_percorre_gli_schemi_0_1_2_3_4(self) -> None:
        database = self.radice / "sequenza.sqlite3"
        with ServizioMondi(database) as servizio:
            tabelle = {
                riga[0]
                for riga in servizio.archivio._connessione.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertTrue(
            {"worlds", "world_entities", "memories", "ai_settings"}.issubset(
                tabelle
            )
        )

    def test_migrazione_3_a_4_preserva_dati_narrativi(self) -> None:
        database = self.radice / "schema3.sqlite3"
        sorgente = self.radice / "mondo"
        shutil.copytree(MINI_BIBBIA, sorgente)
        with ServizioMondi(database) as servizio:
            mondo = servizio.importa_da_cartella(sorgente)
            servizio.salva(mondo.id, "Scenario preservato", {"tone": "sobrio"})
            prima = self._fotografia_narrativa(servizio.archivio._connessione)
        self._riduci_a_schema_3(database)

        with ServizioMondi(database) as servizio:
            dopo = self._fotografia_narrativa(servizio.archivio._connessione)
            versione = servizio.archivio._connessione.execute(
                "PRAGMA user_version"
            ).fetchone()[0]

        self.assertEqual(6, versione)
        self.assertEqual(prima, dopo)

    def test_migrazione_3_a_4_fallita_esegue_rollback(self) -> None:
        database = self.radice / "rollback.sqlite3"
        with ServizioMondi(database):
            pass
        self._riduci_a_schema_3(database)
        connessione = sqlite3.connect(database)
        connessione.execute("CREATE VIEW ai_settings AS SELECT 1 AS settings_id")
        connessione.commit()
        connessione.close()

        with self.assertRaisesRegex(ErroreMigrazione, "schema 3 senza dati parziali"):
            ServizioMondi(database)

        connessione = sqlite3.connect(database)
        try:
            versione = connessione.execute("PRAGMA user_version").fetchone()[0]
            tabella = connessione.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ai_settings'"
            ).fetchone()
        finally:
            connessione.close()
        self.assertEqual(3, versione)
        self.assertIsNone(tabella)

    def test_riapertura_non_duplica_la_configurazione(self) -> None:
        database = self.radice / "riapertura.sqlite3"
        with ServizioMondi(database):
            pass
        with ServizioMondi(database) as servizio:
            conteggio = servizio.archivio._connessione.execute(
                "SELECT COUNT(*) FROM ai_settings"
            ).fetchone()[0]
        self.assertEqual(1, conteggio)

    def test_singleton_impedisce_id_diverso_e_seconda_riga(self) -> None:
        database = self.radice / "singleton.sqlite3"
        with ServizioMondi(database) as servizio:
            connessione = servizio.archivio._connessione
            parametri = ("ollama", OLLAMA_URL_PREDEFINITO, "", 30, "ora")
            with self.assertRaises(sqlite3.IntegrityError):
                connessione.execute(
                    """
                    INSERT INTO ai_settings VALUES (2, ?, ?, ?, ?, ?)
                    """,
                    parametri,
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connessione.execute(
                    """
                    INSERT INTO ai_settings VALUES (1, ?, ?, ?, ?, ?)
                    """,
                    parametri,
                )
            conteggio = connessione.execute(
                "SELECT COUNT(*) FROM ai_settings"
            ).fetchone()[0]
        self.assertEqual(1, conteggio)

    def test_salvataggio_e_persistenza_aggiornano_solo_il_singleton(self) -> None:
        database = self.radice / "persistenza.sqlite3"
        with ServizioMondi(database) as servizio:
            servizio.salva_configurazione_ai(
                valida_configurazione_ai(
                    "ollama", "http://127.0.0.1:11434/", "gemma3", 45
                )
            )
        with ServizioMondi(database) as servizio:
            caricata = servizio.carica_configurazione_ai()
            conteggio = servizio.archivio._connessione.execute(
                "SELECT COUNT(*) FROM ai_settings"
            ).fetchone()[0]
        self.assertEqual("http://127.0.0.1:11434", caricata.ollama_base_url)
        self.assertEqual("gemma3", caricata.ollama_model)
        self.assertEqual(45, caricata.ollama_timeout_seconds)
        self.assertEqual(1, conteggio)

    def test_configurazione_globale_nello_stesso_database(self) -> None:
        database = self.radice / "globale.sqlite3"
        sorgente_a = self.radice / "mondo_a"
        sorgente_b = self.radice / "mondo_b"
        shutil.copytree(MINI_BIBBIA, sorgente_a)
        shutil.copytree(MINI_BIBBIA, sorgente_b)
        dati = json.loads((sorgente_b / "world.json").read_text(encoding="utf-8"))
        dati["id"] = "secondo_mondo"
        dati["title"] = "Secondo mondo"
        (sorgente_b / "world.json").write_text(
            json.dumps(dati, ensure_ascii=False), encoding="utf-8"
        )
        with ServizioMondi(database) as servizio:
            servizio.importa_da_cartella(sorgente_a)
            servizio.importa_da_cartella(sorgente_b)
            servizio.salva_configurazione_ai(
                valida_configurazione_ai(
                    "ollama", OLLAMA_URL_PREDEFINITO, "modello-comune", 30
                )
            )
            self.assertEqual(2, len(servizio.elenca_mondi()))
            self.assertEqual(
                "modello-comune",
                servizio.carica_configurazione_ai().ollama_model,
            )

    def test_database_distinti_hanno_configurazioni_indipendenti(self) -> None:
        database_a = self.radice / "a.sqlite3"
        database_b = self.radice / "b.sqlite3"
        with ServizioMondi(database_a) as servizio:
            servizio.salva_configurazione_ai(
                valida_configurazione_ai(
                    "ollama", OLLAMA_URL_PREDEFINITO, "modello-a", 30
                )
            )
        with ServizioMondi(database_b) as servizio:
            self.assertEqual("", servizio.carica_configurazione_ai().ollama_model)

    def test_validazione_accetta_solo_loopback_senza_dns(self) -> None:
        casi = {
            "http://localhost:11434/": "http://localhost:11434",
            "https://127.0.0.42": "https://127.0.0.42",
            "http://[::1]:11434/": "http://[::1]:11434",
        }
        with mock.patch("socket.getaddrinfo") as risoluzione:
            for url, atteso in casi.items():
                with self.subTest(url=url):
                    configurazione = valida_configurazione_ai(
                        "ollama", url, "", 30
                    )
                    self.assertEqual(atteso, configurazione.ollama_base_url)
        risoluzione.assert_not_called()

    def test_validazione_rifiuta_url_non_locali_o_ambigui(self) -> None:
        url_non_validi = (
            "",
            "localhost:11434",
            "ftp://localhost:11434",
            "http://example.com:11434",
            "http://192.168.1.10:11434",
            "http://localhost.example:11434",
            "http://utente:segreto@localhost:11434",
            "http://localhost:11434?x=1",
            "http://localhost:11434#parte",
            "http://localhost:11434/api",
        )
        for url in url_non_validi:
            with self.subTest(url=url), self.assertRaises(ErroreConfigurazioneAI):
                valida_configurazione_ai("ollama", url, "", 30)

    def test_validazione_rifiuta_provider_modello_e_timeout_non_validi(self) -> None:
        casi = (
            ("altro", OLLAMA_URL_PREDEFINITO, "", 30),
            ("ollama", OLLAMA_URL_PREDEFINITO, "   ", 30),
            ("ollama", OLLAMA_URL_PREDEFINITO, "m", True),
            ("ollama", OLLAMA_URL_PREDEFINITO, "m", 0),
            ("ollama", OLLAMA_URL_PREDEFINITO, "m", 301),
            ("ollama", OLLAMA_URL_PREDEFINITO, "m", 2.5),
        )
        for caso in casi:
            with self.subTest(caso=caso), self.assertRaises(ErroreConfigurazioneAI):
                valida_configurazione_ai(*caso)

    def test_caricamento_e_validazione_non_effettuano_rete(self) -> None:
        trasporto = TrasportoSimulato()
        with ServizioMondi(self.radice / "senza_rete.sqlite3", trasporto) as servizio:
            servizio.carica_configurazione_ai()
            valida_configurazione_ai("ollama", OLLAMA_URL_PREDEFINITO, "", 30)
        self.assertEqual([], trasporto.richieste)

    @staticmethod
    def _riduci_a_schema_3(database: Path) -> None:
        connessione = sqlite3.connect(database)
        try:
            connessione.execute("PRAGMA foreign_keys = OFF")
            connessione.execute("DROP TABLE narrative_turn_memories")
            connessione.execute("DROP TABLE narrative_turn_events")
            connessione.execute("DROP TABLE narrative_turns")
            connessione.execute("DROP TABLE narrative_sessions")
            connessione.execute("DROP TABLE media_assets")
            connessione.execute("DROP TABLE canonical_documents")
            connessione.execute("DROP TABLE ai_settings")
            connessione.execute("PRAGMA user_version = 3")
            connessione.commit()
        finally:
            connessione.close()

    @staticmethod
    def _fotografia_narrativa(connessione: sqlite3.Connection):
        tabelle = (
            "worlds",
            "world_versions",
            "source_files",
            "world_entities",
            "entity_state",
            "events",
            "event_entities",
            "memories",
            "memory_entities",
            "memory_sources",
        )
        return {
            tabella: tuple(connessione.execute(f"SELECT * FROM {tabella}").fetchall())
            for tabella in tabelle
        }


class TestProviderOllama(unittest.TestCase):
    def configurazione(self, modello: str = "gemma3") -> ConfigurazioneAI:
        return valida_configurazione_ai(
            "ollama", "http://localhost:11434/", modello, 30
        )

    def servizio(self, trasporto: TrasportoSimulato) -> ServizioMondi:
        temporanea = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        temporanea.close()
        self.addCleanup(Path(temporanea.name).unlink, missing_ok=True)
        return ServizioMondi(temporanea.name, trasporto)

    def test_versione_usa_endpoint_nativo_e_restituisce_informazioni(self) -> None:
        trasporto = TrasportoSimulato(risposta_json({"version": "0.11.4"}))
        servizio = self.servizio(trasporto)
        self.addCleanup(servizio.chiudi)
        risultato = servizio.ai.verifica_connessione(self.configurazione())
        self.assertTrue(risultato.raggiungibile)
        self.assertEqual("0.11.4", risultato.informazioni.versione)
        self.assertEqual("GET", trasporto.richieste[0]["metodo"])
        self.assertEqual(
            "http://localhost:11434/api/version",
            trasporto.richieste[0]["url"],
        )

    def test_modelli_sono_validati_deduplicati_e_ordinati(self) -> None:
        trasporto = TrasportoSimulato(
            risposta_json(
                {
                    "models": [
                        {"name": "zeta", "size": 10},
                        {"name": "Alfa", "digest": "x"},
                        {"name": "zeta"},
                        {"name": "beta"},
                    ]
                }
            )
        )
        servizio = self.servizio(trasporto)
        self.addCleanup(servizio.chiudi)
        modelli = servizio.ai.elenca_modelli(self.configurazione())
        self.assertEqual(["Alfa", "beta", "zeta"], [m.nome for m in modelli])
        self.assertEqual("http://localhost:11434/api/tags", trasporto.richieste[0]["url"])

    def test_un_elemento_modello_non_valido_invalida_tutta_la_risposta(self) -> None:
        casi = ({}, {"models": {}}, {"models": ["m"]}, {"models": [{}]})
        for dati in casi:
            with self.subTest(dati=dati):
                trasporto = TrasportoSimulato(risposta_json(dati))
                servizio = self.servizio(trasporto)
                try:
                    with self.assertRaises(ErroreElencoModelli):
                        servizio.ai.elenca_modelli(self.configurazione())
                finally:
                    servizio.chiudi()

    def test_chat_invia_payload_minimo_e_legge_solo_assistant(self) -> None:
        trasporto = TrasportoSimulato(
            risposta_json({"models": [{"name": "gemma3"}]}),
            risposta_json(
                {
                    "message": {
                        "role": "assistant",
                        "content": "Funzionamento confermato.",
                        "thinking": "dato da ignorare",
                    }
                }
            ),
        )
        servizio = self.servizio(trasporto)
        self.addCleanup(servizio.chiudi)
        risposta = servizio.ai.genera_testo_di_prova(
            self.configurazione(), "Rispondi in italiano."
        )
        richiesta = trasporto.richieste[1]
        payload = json.loads(richiesta["corpo"].decode("utf-8"))
        self.assertEqual("Funzionamento confermato.", risposta.contenuto)
        self.assertEqual("POST", richiesta["metodo"])
        self.assertEqual("http://localhost:11434/api/chat", richiesta["url"])
        self.assertEqual("application/json", richiesta["headers"]["Content-Type"])
        self.assertIs(payload["stream"], False)
        self.assertEqual("gemma3", payload["model"])
        self.assertEqual(["system", "user"], [m["role"] for m in payload["messages"]])
        self.assertNotIn("tools", payload)
        self.assertNotIn("format", payload)
        self.assertNotIn("thinking", risposta.contenuto)

    def test_chat_vuota_usa_testo_tecnico_predefinito(self) -> None:
        trasporto = TrasportoSimulato(
            risposta_json({"models": [{"name": "gemma3"}]}),
            risposta_json({"message": {"role": "assistant", "content": "Ok"}}),
        )
        servizio = self.servizio(trasporto)
        self.addCleanup(servizio.chiudi)
        servizio.ai.genera_testo_di_prova(self.configurazione(), "   ")
        payload = json.loads(trasporto.richieste[1]["corpo"].decode("utf-8"))
        self.assertTrue(payload["messages"][1]["content"].strip())

    def test_testo_oltre_limite_viene_rifiutato_prima_della_rete(self) -> None:
        trasporto = TrasportoSimulato()
        servizio = self.servizio(trasporto)
        self.addCleanup(servizio.chiudi)
        with self.assertRaisesRegex(ErroreLimiteTesto, "2.000"):
            servizio.ai.genera_testo_di_prova(self.configurazione(), "à" * 2001)
        self.assertEqual([], trasporto.richieste)

    def test_modello_mancante_o_non_disponibile_viene_rifiutato(self) -> None:
        trasporto_vuoto = TrasportoSimulato()
        servizio_vuoto = self.servizio(trasporto_vuoto)
        self.addCleanup(servizio_vuoto.chiudi)
        with self.assertRaises(ErroreModelloNonDisponibile):
            servizio_vuoto.ai.genera_testo_di_prova(self.configurazione(""), "x")
        self.assertEqual([], trasporto_vuoto.richieste)

        trasporto = TrasportoSimulato(
            risposta_json({"models": [{"name": "altro"}]})
        )
        servizio = self.servizio(trasporto)
        self.addCleanup(servizio.chiudi)
        with self.assertRaises(ErroreModelloNonDisponibile):
            servizio.ai.genera_testo_di_prova(self.configurazione(), "x")
        self.assertEqual(1, len(trasporto.richieste))

    def test_json_non_valido_e_struttura_non_oggetto(self) -> None:
        casi = (
            (RispostaHTTP(200, b"{non-json"), ErroreRispostaJSON),
            (risposta_json([]), ErroreStrutturaRisposta),
        )
        for risposta, errore in casi:
            with self.subTest(errore=errore):
                trasporto = TrasportoSimulato(risposta)
                servizio = self.servizio(trasporto)
                try:
                    with self.assertRaises(errore):
                        servizio.ai.verifica_connessione(self.configurazione())
                finally:
                    servizio.chiudi()

    def test_versione_e_risposta_assistant_incomplete(self) -> None:
        trasporto = TrasportoSimulato(risposta_json({}))
        servizio = self.servizio(trasporto)
        try:
            with self.assertRaises(ErroreVersioneMancante):
                servizio.ai.verifica_connessione(self.configurazione())
        finally:
            servizio.chiudi()

        casi_chat = (
            {},
            {"message": []},
            {"message": {"role": "user", "content": "x"}},
            {"message": {"role": "assistant", "content": "   "}},
        )
        for dati in casi_chat:
            with self.subTest(dati=dati):
                trasporto = TrasportoSimulato(
                    risposta_json({"models": [{"name": "gemma3"}]}),
                    risposta_json(dati),
                )
                servizio = self.servizio(trasporto)
                try:
                    with self.assertRaises(ErroreRispostaAssistant):
                        servizio.ai.genera_testo_di_prova(
                            self.configurazione(), "x"
                        )
                finally:
                    servizio.chiudi()

    def test_status_non_2xx_e_redirect_sono_errori_italiani(self) -> None:
        for status in (302, 404, 500):
            with self.subTest(status=status):
                trasporto = TrasportoSimulato(RispostaHTTP(status, b"<html>segreto"))
                servizio = self.servizio(trasporto)
                try:
                    with self.assertRaises(ErroreHTTPProvider) as contesto:
                        servizio.ai.verifica_connessione(self.configurazione())
                    self.assertNotIn("html", str(contesto.exception).lower())
                    self.assertNotIn("localhost", str(contesto.exception).lower())
                finally:
                    servizio.chiudi()


class TestTrasportoHTTP(unittest.TestCase):
    def test_limite_corpo_interrompe_la_lettura(self) -> None:
        risposta = RispostaUrllibSimulata(b"x" * (LIMITE_CORPO_HTTP + 1))
        trasporto = TrasportoUrllib()
        trasporto._opener = mock.Mock()
        trasporto._opener.open.return_value = risposta
        with self.assertRaisesRegex(ErroreCorpoHTTP, "limite"):
            trasporto.richiedi("GET", "http://localhost/api/version", timeout=1)
        self.assertEqual(LIMITE_CORPO_HTTP + 1, risposta.limite_letto)

    def test_content_length_oltre_limite_non_legge_il_corpo(self) -> None:
        risposta = RispostaUrllibSimulata(
            b"segreto", content_length=str(LIMITE_CORPO_HTTP + 1)
        )
        trasporto = TrasportoUrllib()
        trasporto._opener = mock.Mock()
        trasporto._opener.open.return_value = risposta
        with self.assertRaises(ErroreCorpoHTTP):
            trasporto.richiedi("GET", "http://localhost/api/version", timeout=1)
        self.assertIsNone(risposta.limite_letto)

    def test_timeout_connessione_rifiutata_e_http_conservano_la_causa(self) -> None:
        casi = (
            (
                urllib.error.URLError(socket.timeout("tempo")),
                ErroreTimeoutOllama,
            ),
            (
                urllib.error.URLError(ConnectionRefusedError("rifiutata")),
                ErroreOllamaNonRaggiungibile,
            ),
            (
                urllib.error.HTTPError(
                    "http://localhost", 302, "redirect", {}, None
                ),
                ErroreHTTPProvider,
            ),
        )
        for causa, tipo in casi:
            with self.subTest(tipo=tipo):
                trasporto = TrasportoUrllib()
                trasporto._opener = mock.Mock()
                trasporto._opener.open.side_effect = causa
                with self.assertRaises(tipo) as contesto:
                    trasporto.richiedi(
                        "GET", "http://localhost/api/version", timeout=1
                    )
                self.assertIs(contesto.exception.__cause__, causa)
                self.assertNotIn("rifiutata", str(contesto.exception))
                self.assertNotIn("redirect", str(contesto.exception))


class TestCoordinatoreAI(unittest.TestCase):
    def test_servizio_rete_del_worker_non_contiene_archivio_o_tkinter(self) -> None:
        temporanea = tempfile.TemporaryDirectory()
        self.addCleanup(temporanea.cleanup)
        trasporto = TrasportoSimulato(risposta_json({"version": "1.0"}))
        servizio = ServizioMondi(Path(temporanea.name) / "haria.sqlite3", trasporto)
        self.addCleanup(servizio.chiudi)
        configurazione = servizio.carica_configurazione_ai()
        coordinatore = CoordinatoreAsincrono()
        self.addCleanup(coordinatore.chiudi)

        with mock.patch.object(
            servizio.archivio,
            "carica_configurazione_ai",
            side_effect=AssertionError("SQLite non deve essere usato dal worker"),
        ):
            self.assertTrue(
                coordinatore.avvia(
                    "connessione", servizio.ai.verifica_connessione, configurazione
                )
            )
            esito = attendi_esito(coordinatore)

        self.assertIsNone(esito.errore)
        self.assertFalse(hasattr(servizio.ai, "archivio"))
        self.assertFalse(hasattr(servizio.ai, "radice"))

    def test_worker_daemon_restituisce_esito_senza_sqlite_o_tkinter(self) -> None:
        coordinatore = CoordinatoreAsincrono()
        dati: dict[str, object] = {}

        def operazione(configurazione: ConfigurazioneAI) -> str:
            dati["thread"] = threading.get_ident()
            dati["daemon"] = threading.current_thread().daemon
            dati["configurazione"] = configurazione
            return "ok"

        configurazione = valida_configurazione_ai(
            "ollama", OLLAMA_URL_PREDEFINITO, "", 30
        )
        principale = threading.get_ident()
        self.assertTrue(coordinatore.avvia("prova", operazione, configurazione))
        esito = attendi_esito(coordinatore)
        self.assertEqual("ok", esito.risultato)
        self.assertNotEqual(principale, dati["thread"])
        self.assertIs(dati["daemon"], True)
        self.assertEqual(configurazione, dati["configurazione"])
        coordinatore.chiudi()

    def test_richieste_concorrenti_duplicate_sono_impedite(self) -> None:
        coordinatore = CoordinatoreAsincrono()
        avviata = threading.Event()
        prosegui = threading.Event()

        def operazione() -> str:
            avviata.set()
            prosegui.wait(1)
            return "fine"

        self.assertTrue(coordinatore.avvia("prima", operazione))
        self.assertTrue(avviata.wait(1))
        self.assertFalse(coordinatore.avvia("duplicata", lambda: "no"))
        prosegui.set()
        self.assertEqual("fine", attendi_esito(coordinatore).risultato)
        coordinatore.chiudi()

    def test_risultato_tardivo_viene_ignorato_dopo_chiusura(self) -> None:
        coordinatore = CoordinatoreAsincrono()
        avviata = threading.Event()
        prosegui = threading.Event()

        def operazione() -> str:
            avviata.set()
            prosegui.wait(1)
            return "troppo tardi"

        coordinatore.avvia("tardiva", operazione)
        self.assertTrue(avviata.wait(1))
        coordinatore.chiudi()
        prosegui.set()
        time.sleep(0.05)
        self.assertEqual((), coordinatore.raccogli())


class TestIntegrazioneTask004(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)
        self.sorgente = self.radice / "mondo"
        shutil.copytree(MINI_BIBBIA, self.sorgente)

    def tearDown(self) -> None:
        self.temporanea.cleanup()

    def test_operazioni_ai_non_modificano_dati_narrativi(self) -> None:
        trasporto = TrasportoSimulato(
            risposta_json({"version": "1.0"}),
            risposta_json({"models": [{"name": "gemma3"}]}),
            risposta_json({"models": [{"name": "gemma3"}]}),
            risposta_json({"message": {"role": "assistant", "content": "Ok"}}),
        )
        with ServizioMondi(self.radice / "haria.sqlite3", trasporto) as servizio:
            servizio.importa_da_cartella(self.sorgente)
            prima = TestConfigurazioneESchema4._fotografia_narrativa(
                servizio.archivio._connessione
            )
            configurazione = valida_configurazione_ai(
                "ollama", OLLAMA_URL_PREDEFINITO, "gemma3", 30
            )
            servizio.salva_configurazione_ai(configurazione)
            servizio.ai.verifica_connessione(configurazione)
            servizio.ai.elenca_modelli(configurazione)
            servizio.ai.genera_testo_di_prova(configurazione, "Prova")
            dopo = TestConfigurazioneESchema4._fotografia_narrativa(
                servizio.archivio._connessione
            )
        self.assertEqual(prima, dopo)

    def test_rete_usa_fotografia_visibile_senza_salvarla_implicitamente(self) -> None:
        trasporto = TrasportoSimulato(risposta_json({"version": "1.0"}))
        with ServizioMondi(self.radice / "visibile.sqlite3", trasporto) as servizio:
            persistente = servizio.carica_configurazione_ai()
            visibile = valida_configurazione_ai(
                "ollama", "http://127.0.0.9:11435/", "", 12
            )
            servizio.ai.verifica_connessione(visibile)
            ancora_persistente = servizio.carica_configurazione_ai()
        self.assertEqual(
            "http://127.0.0.9:11435/api/version", trasporto.richieste[0]["url"]
        )
        self.assertEqual(persistente, ancora_persistente)

    def test_testi_gui_ai_sono_italiani_e_non_tecnici(self) -> None:
        self.assertEqual("Impostazioni AI", UI_TEXT["impostazioni_ai"])
        self.assertEqual("Verifica connessione", UI_TEXT["verifica_connessione_ai"])
        self.assertEqual("Aggiorna modelli", UI_TEXT["aggiorna_modelli_ai"])
        self.assertEqual("Prova modello", UI_TEXT["prova_modello_ai"])
        testi = " ".join(UI_TEXT.values()).casefold()
        for tecnico in ("/api/", "payload", "traceback", "socket error", "json grezzo"):
            self.assertNotIn(tecnico, testi)


if __name__ == "__main__":
    unittest.main()
