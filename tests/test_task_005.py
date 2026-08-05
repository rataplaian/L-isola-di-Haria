from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from haria_engine.app import (
    ApplicazioneHaria,
    UI_TEXT,
    etichetta_ambito_validazione,
    etichetta_severita_validazione,
)
from haria_engine.errors import ErroreValidazione
from haria_engine.service import ServizioMondi
from haria_engine.validation import ServizioValidazione
from haria_engine.validation_models import (
    AmbitoValidazione,
    EntitaValidazione,
    EventoValidazione,
    FotografiaValidazioneMondo,
    MemoriaValidazione,
    ProblemaValidazione,
    PropostaCambioStato,
    PropostaEpistemica,
    PropostaEventoDescrittivo,
    PropostaSpostamento,
    PropostaTrasferimento,
    RapportoValidazione,
    SeveritaProblema,
)
from haria_engine.validation_rules import (
    controlla_integrita,
    crea_rapporto,
    valida_sequenza_pura,
)


RADICE = Path(__file__).resolve().parents[1]
MINI_MONDO = RADICE / "sample_world"
MONDO_ID = "haria_minimal_test"
RIFERIMENTO = datetime(2030, 1, 2, 12, 0, tzinfo=timezone.utc)


class _AlberoFinto:
    def __init__(self) -> None:
        self.righe: list[tuple[object, ...]] = []

    def get_children(self) -> tuple[str, ...]:
        return ()

    def delete(self, _elemento: object) -> None:
        raise AssertionError("Non erano previste righe da eliminare.")

    def insert(self, _parent: str, _position: str, *, values: tuple[object, ...]):
        self.righe.append(values)


class _EtichettaFinta:
    def __init__(self) -> None:
        self.testo = ""

    def configure(self, *, text: str) -> None:
        self.testo = text


class _PulsanteFinto:
    def __init__(self) -> None:
        self.stato: object = None

    def configure(self, *, state: object) -> None:
        self.stato = state


class TestTask005(unittest.TestCase):
    def setUp(self) -> None:
        self.cartella = tempfile.TemporaryDirectory(prefix="haria_task005_")
        self.database = Path(self.cartella.name) / "haria.sqlite3"
        self.servizio = ServizioMondi(self.database)
        self.servizio.importa_da_cartella(MINI_MONDO)
        self.fotografia = self.servizio.validazione.costruisci_fotografia(MONDO_ID)

    def tearDown(self) -> None:
        self.servizio.chiudi()
        self.cartella.cleanup()

    def entita(
        self, entity_id: str, fotografia: FotografiaValidazioneMondo | None = None
    ) -> EntitaValidazione:
        foto = fotografia or self.fotografia
        return next(voce for voce in foto.entita if voce.entity_id == entity_id)

    def sostituisci_entita(
        self,
        entity_id: str,
        fotografia: FotografiaValidazioneMondo | None = None,
        **modifiche: object,
    ) -> FotografiaValidazioneMondo:
        foto = fotografia or self.fotografia
        return replace(
            foto,
            entita=tuple(
                replace(voce, **modifiche) if voce.entity_id == entity_id else voce
                for voce in foto.entita
            ),
        )

    @staticmethod
    def codici(rapporto: RapportoValidazione) -> set[str]:
        return {problema.codice for problema in rapporto.problemi}

    @staticmethod
    def evento(istante: datetime, **modifiche: object) -> EventoValidazione:
        base = EventoValidazione(
            event_id="evento-base",
            world_id=MONDO_ID,
            event_type="evento_descrittivo",
            occurred_at=istante.isoformat(),
            actor_id="luca",
            target_id="pen_blue",
            location_id="infirmary",
            created_at=istante.isoformat(),
        )
        return replace(base, **modifiche)

    def test_modelli_immutabili(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.fotografia.world_id = "altro"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            self.entita("luca").location_id = "assembly"  # type: ignore[misc]

    def test_ordinamento_problemi_deterministico(self) -> None:
        errore = ProblemaValidazione(
            "z_errore",
            SeveritaProblema.ERRORE,
            AmbitoValidazione.TEMPO,
            "Errore temporale.",
            1,
        )
        avvertimento = ProblemaValidazione(
            "a_avvertimento",
            SeveritaProblema.AVVERTIMENTO,
            AmbitoValidazione.INTEGRITA,
            "Avvertimento.",
            1,
        )
        primo = crea_rapporto([avvertimento, errore])
        secondo = crea_rapporto([errore, avvertimento])
        self.assertEqual(primo, secondo)
        self.assertEqual(primo.problemi, (errore, avvertimento))

    def test_mondo_integro(self) -> None:
        rapporto = controlla_integrita(self.fotografia)
        self.assertTrue(rapporto.superata)
        self.assertEqual(rapporto.problemi, ())

    def test_riferimento_entita_mancante(self) -> None:
        foto = self.sostituisci_entita("luca", location_id="luogo-assente")
        self.assertIn("posizione_inesistente", self.codici(controlla_integrita(foto)))

    def test_tipo_luogo_errato(self) -> None:
        foto = self.sostituisci_entita("luca", location_id="pen_blue")
        self.assertIn("posizione_non_luogo", self.codici(controlla_integrita(foto)))

    def test_posizione_invalida(self) -> None:
        foto = self.sostituisci_entita("pen_blue", location_id="inesistente")
        rapporto = controlla_integrita(foto)
        self.assertFalse(rapporto.superata)
        self.assertIn("posizione_inesistente", self.codici(rapporto))

    def test_possessore_invalido(self) -> None:
        foto = self.sostituisci_entita("pen_blue", holder_id="infirmary")
        self.assertIn(
            "possessore_non_personaggio", self.codici(controlla_integrita(foto))
        )

    def test_oggetto_e_possessore_in_luoghi_diversi(self) -> None:
        foto = self.sostituisci_entita(
            "pen_blue", holder_id="luca", location_id="assembly"
        )
        self.assertIn(
            "oggetto_lontano_possessore", self.codici(controlla_integrita(foto))
        )

    def test_personaggio_con_possessore(self) -> None:
        foto = self.sostituisci_entita("luca", holder_id="elise_moreau")
        self.assertIn(
            "personaggio_con_possessore", self.codici(controlla_integrita(foto))
        )

    def test_luogo_con_posizione(self) -> None:
        foto = self.sostituisci_entita("infirmary", location_id="assembly")
        self.assertIn(
            "luogo_con_riferimenti_non_ammessi",
            self.codici(controlla_integrita(foto)),
        )

    def test_evento_con_riferimento_incoerente(self) -> None:
        foto = replace(
            self.fotografia,
            eventi=(self.evento(RIFERIMENTO, actor_id="assente"),),
        )
        self.assertIn(
            "evento_attore_inesistente", self.codici(controlla_integrita(foto))
        )

    def test_memoria_con_personaggio_inesistente(self) -> None:
        memoria = replace(self.fotografia.memorie[0], character_id="assente")
        foto = replace(self.fotografia, memorie=(memoria,))
        self.assertIn(
            "personaggio_memoria_inesistente",
            self.codici(controlla_integrita(foto)),
        )

    def test_memoria_origine_di_altro_personaggio(self) -> None:
        luca = next(m for m in self.fotografia.memorie if m.character_id == "luca")
        elise = next(
            m for m in self.fotografia.memorie if m.character_id == "elise_moreau"
        )
        inferenza = replace(
            elise,
            memory_id="inferenza-test",
            knowledge_type="inference",
            source_memory_ids=(luca.memory_id,),
        )
        foto = replace(self.fotografia, memorie=(*self.fotografia.memorie, inferenza))
        self.assertIn(
            "fonte_memoria_altro_personaggio",
            self.codici(controlla_integrita(foto)),
        )

    def test_timestamp_evento_non_valido(self) -> None:
        foto = replace(
            self.fotografia,
            eventi=(self.evento(RIFERIMENTO, occurred_at="2030-01-02T10:00:00"),),
        )
        self.assertIn(
            "timestamp_evento_non_valido", self.codici(controlla_integrita(foto))
        )

    def test_duplicazioni_strutturali(self) -> None:
        foto = replace(
            self.fotografia,
            entita=(self.fotografia.entita[0], *self.fotografia.entita),
        )
        self.assertIn("entita_duplicata", self.codici(controlla_integrita(foto)))

    def test_spostamento_valido(self) -> None:
        proposta = PropostaSpostamento(
            "akari_mori", "infirmary", actor_id="akari_mori"
        )
        esito = valida_sequenza_pura(self.fotografia, (proposta,), RIFERIMENTO)
        self.assertTrue(esito.superata)
        self.assertEqual(
            self.entita("akari_mori", esito.fotografia_finale).location_id,
            "infirmary",
        )

    def test_spostamento_oggetto_posseduto_rifiutato(self) -> None:
        foto = self.sostituisci_entita("pen_blue", holder_id="luca")
        proposta = PropostaSpostamento("pen_blue", "assembly", actor_id="luca")
        esito = valida_sequenza_pura(foto, (proposta,), RIFERIMENTO)
        self.assertIn("oggetto_posseduto_spostato_direttamente", self.codici(esito.rapporto))

    def test_destinazione_inaccessibile(self) -> None:
        foto = self.sostituisci_entita("assembly", accessibility=False)
        proposta = PropostaSpostamento("luca", "assembly", actor_id="luca")
        esito = valida_sequenza_pura(foto, (proposta,), RIFERIMENTO)
        self.assertIn("destinazione_inaccessibile", self.codici(esito.rapporto))

    def test_trasferimento_valido(self) -> None:
        proposta = PropostaTrasferimento("pen_blue", "luca", actor_id="luca")
        esito = valida_sequenza_pura(self.fotografia, (proposta,), RIFERIMENTO)
        penna = self.entita("pen_blue", esito.fotografia_finale)
        self.assertTrue(esito.superata)
        self.assertEqual((penna.holder_id, penna.location_id), ("luca", "infirmary"))

    def test_trasferimento_duplicato(self) -> None:
        foto = self.sostituisci_entita("pen_blue", holder_id="luca")
        proposta = PropostaTrasferimento("pen_blue", "luca", actor_id="luca")
        esito = valida_sequenza_pura(foto, (proposta,), RIFERIMENTO)
        self.assertIn("trasferimento_duplicato", self.codici(esito.rapporto))

    def test_trasferimento_remoto(self) -> None:
        proposta = PropostaTrasferimento(
            "pen_blue", "akari_mori", actor_id="akari_mori"
        )
        esito = valida_sequenza_pura(self.fotografia, (proposta,), RIFERIMENTO)
        self.assertIn("trasferimento_remoto", self.codici(esito.rapporto))

    def test_oggetto_inaccessibile(self) -> None:
        foto = self.sostituisci_entita("pen_blue", accessibility=False)
        proposta = PropostaTrasferimento("pen_blue", "luca", actor_id="luca")
        esito = valida_sequenza_pura(foto, (proposta,), RIFERIMENTO)
        self.assertIn("oggetto_inaccessibile", self.codici(esito.rapporto))

    def test_cambio_stato_senza_cambiamenti(self) -> None:
        proposta = PropostaCambioStato("luca", status="active")
        esito = valida_sequenza_pura(self.fotografia, (proposta,), RIFERIMENTO)
        self.assertIn("stato_senza_cambiamenti", self.codici(esito.rapporto))

    def test_cambio_stato_valido_modifica_solo_proiezione(self) -> None:
        proposta = PropostaCambioStato("luca", condition="vigile")
        esito = valida_sequenza_pura(self.fotografia, (proposta,), RIFERIMENTO)
        self.assertTrue(esito.superata)
        self.assertEqual(self.entita("luca", esito.fotografia_finale).condition, "vigile")
        self.assertIsNone(self.entita("luca").condition)

    def test_timestamp_proposta_senza_fuso(self) -> None:
        proposta = PropostaEventoDescrittivo(
            "nota", occurred_at="2030-01-02T10:00:00"
        )
        esito = valida_sequenza_pura(self.fotografia, (proposta,), RIFERIMENTO)
        self.assertIn("timestamp_proposta_senza_fuso", self.codici(esito.rapporto))

    def test_evento_anteriore_all_ultimo_evento(self) -> None:
        ultimo = self.evento(RIFERIMENTO)
        foto = replace(self.fotografia, eventi=(ultimo,))
        proposta = PropostaEventoDescrittivo(
            "nota", occurred_at=(RIFERIMENTO - timedelta(seconds=1)).isoformat()
        )
        esito = valida_sequenza_pura(foto, (proposta,), RIFERIMENTO)
        self.assertIn("proposta_anteriore_ultimo_evento", self.codici(esito.rapporto))

    def test_sequenza_temporale_valida(self) -> None:
        proposte = (
            PropostaSpostamento(
                "akari_mori",
                "infirmary",
                actor_id="akari_mori",
                occurred_at=RIFERIMENTO.isoformat(),
            ),
            PropostaTrasferimento(
                "pen_blue",
                "akari_mori",
                actor_id="akari_mori",
                occurred_at=(RIFERIMENTO + timedelta(minutes=1)).isoformat(),
            ),
        )
        esito = valida_sequenza_pura(self.fotografia, proposte, RIFERIMENTO)
        self.assertTrue(esito.superata)

    def test_sequenza_temporale_non_ordinata(self) -> None:
        proposte = (
            PropostaEventoDescrittivo(
                "prima", occurred_at=(RIFERIMENTO + timedelta(minutes=1)).isoformat()
            ),
            PropostaEventoDescrittivo("seconda", occurred_at=RIFERIMENTO.isoformat()),
        )
        esito = valida_sequenza_pura(self.fotografia, proposte, RIFERIMENTO)
        self.assertIn("sequenza_temporale_non_ordinata", self.codici(esito.rapporto))

    def test_memoria_dell_attore_valida(self) -> None:
        memoria = next(
            m for m in self.fotografia.memorie if m.character_id == "elise_moreau"
        )
        proposta = PropostaEpistemica(
            "elise_moreau", memory_ids=(memoria.memory_id,)
        )
        esito = valida_sequenza_pura(self.fotografia, (proposta,), RIFERIMENTO)
        self.assertTrue(esito.superata)

    def test_memoria_di_altro_personaggio_rifiutata(self) -> None:
        memoria = next(
            m for m in self.fotografia.memorie if m.character_id == "elise_moreau"
        )
        proposta = PropostaEpistemica("akari_mori", memory_ids=(memoria.memory_id,))
        esito = valida_sequenza_pura(self.fotografia, (proposta,), RIFERIMENTO)
        self.assertIn("memoria_altro_personaggio", self.codici(esito.rapporto))

    def test_memoria_non_corrente_rifiutata(self) -> None:
        memoria = next(
            m for m in self.fotografia.memorie if m.character_id == "elise_moreau"
        )
        storica = replace(memoria, is_current=False, effective_status="superseded")
        successiva = replace(
            memoria,
            memory_id="memoria-successiva",
            supersedes_memory_id=memoria.memory_id,
            status="corrected",
        )
        foto = replace(
            self.fotografia,
            memorie=tuple(
                storica if m.memory_id == memoria.memory_id else m
                for m in self.fotografia.memorie
            )
            + (successiva,),
        )
        proposta = PropostaEpistemica(
            "elise_moreau", memory_ids=(memoria.memory_id,)
        )
        esito = valida_sequenza_pura(foto, (proposta,), RIFERIMENTO)
        self.assertIn("memoria_non_corrente", self.codici(esito.rapporto))

    def test_osservazione_diretta_per_compresenza(self) -> None:
        proposta = PropostaEpistemica("luca", target_id="pen_blue")
        esito = valida_sequenza_pura(self.fotografia, (proposta,), RIFERIMENTO)
        self.assertTrue(esito.superata)

    def test_conoscenza_remota_senza_memoria_rifiutata(self) -> None:
        proposta = PropostaEpistemica("akari_mori", target_id="pen_blue")
        esito = valida_sequenza_pura(self.fotografia, (proposta,), RIFERIMENTO)
        self.assertIn("conoscenza_remota_senza_memoria", self.codici(esito.rapporto))

    def test_conoscenza_remota_con_memoria_corrente(self) -> None:
        base = next(m for m in self.fotografia.memorie if m.character_id == "akari_mori")
        memoria = replace(base, memory_id="akari-penna", entity_ids=("pen_blue",))
        foto = replace(self.fotografia, memorie=(*self.fotografia.memorie, memoria))
        proposta = PropostaEpistemica(
            "akari_mori", target_id="pen_blue", memory_ids=(memoria.memory_id,)
        )
        esito = valida_sequenza_pura(foto, (proposta,), RIFERIMENTO)
        self.assertTrue(esito.superata)

    def test_inferenza_con_fonte_altro_personaggio_rifiutata(self) -> None:
        luca = next(m for m in self.fotografia.memorie if m.character_id == "luca")
        elise = next(
            m for m in self.fotografia.memorie if m.character_id == "elise_moreau"
        )
        inferenza = replace(
            elise,
            memory_id="inferenza-incrociata",
            knowledge_type="inference",
            source_memory_ids=(luca.memory_id,),
        )
        foto = replace(self.fotografia, memorie=(*self.fotografia.memorie, inferenza))
        proposta = PropostaEpistemica(
            "elise_moreau", memory_ids=(inferenza.memory_id,)
        )
        esito = valida_sequenza_pura(foto, (proposta,), RIFERIMENTO)
        self.assertIn("inferenza_fonte_altro_personaggio", self.codici(esito.rapporto))

    def test_dry_run_non_modifica_fotografia_originale(self) -> None:
        proposta = PropostaTrasferimento("pen_blue", "luca", actor_id="luca")
        prima = self.fotografia
        esito = valida_sequenza_pura(prima, (proposta,), RIFERIMENTO)
        self.assertEqual(self.entita("pen_blue", prima).holder_id, None)
        self.assertIsNot(esito.fotografia_finale, prima)

    def test_proposta_invalida_non_altera_proiezione(self) -> None:
        proposta = PropostaSpostamento("assente", "infirmary")
        esito = valida_sequenza_pura(self.fotografia, (proposta,), RIFERIMENTO)
        self.assertEqual(esito.fotografia_finale, self.fotografia)

    def test_piu_proposte_valide_in_sequenza(self) -> None:
        proposte = (
            PropostaSpostamento("akari_mori", "infirmary", actor_id="akari_mori"),
            PropostaTrasferimento("pen_blue", "akari_mori", actor_id="akari_mori"),
            PropostaCambioStato("akari_mori", condition="attenta"),
        )
        esito = valida_sequenza_pura(self.fotografia, proposte, RIFERIMENTO)
        self.assertTrue(esito.superata)
        self.assertEqual(self.entita("pen_blue", esito.fotografia_finale).holder_id, "akari_mori")
        self.assertEqual(self.entita("akari_mori", esito.fotografia_finale).condition, "attenta")

    def test_trasferimento_penna_non_sposta_chiavi(self) -> None:
        chiavi_prima = self.entita("infirmary_keys")
        esito = valida_sequenza_pura(
            self.fotografia,
            (PropostaTrasferimento("pen_blue", "luca", actor_id="luca"),),
            RIFERIMENTO,
        )
        self.assertEqual(self.entita("infirmary_keys", esito.fotografia_finale), chiavi_prima)

    def test_servizio_non_chiama_metodi_di_scrittura(self) -> None:
        nomi = (
            "applica_evento_e_stati",
            "registra_evento",
            "registra_memoria",
            "salva_versione",
            "salva_configurazione_ai",
        )
        patcher = [mock.patch.object(self.servizio.archivio, nome) for nome in nomi]
        mocks = [voce.start() for voce in patcher]
        try:
            rapporto = self.servizio.validazione.controlla_mondo(MONDO_ID)
        finally:
            for voce in reversed(patcher):
                voce.stop()
        self.assertTrue(rapporto.superata)
        for metodo in mocks:
            metodo.assert_not_called()

    def fotografia_database(self) -> dict[str, object]:
        with closing(sqlite3.connect(self.database)) as connessione:
            tabelle = [
                riga[0]
                for riga in connessione.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
            ]
            return {
                "user_version": connessione.execute("PRAGMA user_version").fetchone()[0],
                "conteggi": tuple(
                    (nome, connessione.execute(f'SELECT COUNT(*) FROM "{nome}"').fetchone()[0])
                    for nome in tabelle
                ),
                "eventi": tuple(connessione.execute("SELECT * FROM events ORDER BY event_id")),
                "stato": tuple(connessione.execute("SELECT * FROM entity_state ORDER BY entity_id")),
                "memorie": tuple(connessione.execute("SELECT * FROM memories ORDER BY memory_id")),
                "ai": tuple(connessione.execute("SELECT * FROM ai_settings ORDER BY settings_id")),
            }

    def test_validazione_non_modifica_database(self) -> None:
        prima = self.fotografia_database()
        self.servizio.validazione.controlla_mondo(MONDO_ID)
        self.servizio.validazione.valida_sequenza(
            MONDO_ID,
            (PropostaTrasferimento("pen_blue", "luca", actor_id="luca"),),
            RIFERIMENTO,
        )
        dopo = self.fotografia_database()
        self.assertEqual(dopo, prima)

    def test_user_version_resta_quattro(self) -> None:
        self.servizio.validazione.controlla_mondo(MONDO_ID)
        self.assertEqual(self.fotografia_database()["user_version"], 4)

    def test_conteggi_tabelle_invariati(self) -> None:
        prima = self.fotografia_database()["conteggi"]
        self.servizio.validazione.controlla_mondo(MONDO_ID)
        self.assertEqual(self.fotografia_database()["conteggi"], prima)

    def test_eventi_e_stato_invariati(self) -> None:
        prima = self.fotografia_database()
        self.servizio.validazione.valida_proposta(
            MONDO_ID,
            PropostaTrasferimento("pen_blue", "luca", actor_id="luca"),
            RIFERIMENTO,
        )
        dopo = self.fotografia_database()
        self.assertEqual(dopo["eventi"], prima["eventi"])
        self.assertEqual(dopo["stato"], prima["stato"])

    def test_memorie_e_configurazione_ai_invariate(self) -> None:
        prima = self.fotografia_database()
        self.servizio.validazione.controlla_mondo(MONDO_ID)
        dopo = self.fotografia_database()
        self.assertEqual(dopo["memorie"], prima["memorie"])
        self.assertEqual(dopo["ai"], prima["ai"])

    def test_nessuna_richiesta_http_o_connessione_ollama(self) -> None:
        trasporto = mock.Mock()
        altro_database = Path(self.cartella.name) / "senza-rete.sqlite3"
        with ServizioMondi(altro_database, trasporto_ai=trasporto) as servizio:
            servizio.importa_da_cartella(MINI_MONDO)
            servizio.validazione.controlla_mondo(MONDO_ID)
        self.assertEqual(trasporto.mock_calls, [])

    def test_errori_italiani_con_causa_disponibile(self) -> None:
        archivio = mock.Mock()
        archivio.carica_mondo.side_effect = RuntimeError("dettaglio interno")
        servizio = ServizioValidazione(archivio)
        with self.assertRaises(ErroreValidazione) as contesto:
            servizio.costruisci_fotografia(MONDO_ID)
        self.assertIn("lettura del mondo", str(contesto.exception))
        self.assertIsInstance(contesto.exception.__cause__, RuntimeError)
        self.assertNotIn("dettaglio interno", str(contesto.exception))

    def test_gui_mostra_etichette_italiane_senza_codice_tecnico(self) -> None:
        problema = ProblemaValidazione(
            "codice_da_non_mostrare",
            SeveritaProblema.ERRORE,
            AmbitoValidazione.EPISTEMICA,
            "Akari non dispone di una memoria corrente.",
        )
        rapporto = RapportoValidazione((problema,))
        applicazione = ApplicazioneHaria.__new__(ApplicazioneHaria)
        applicazione.mondo_corrente = SimpleNamespace(id=MONDO_ID)
        applicazione.servizio = SimpleNamespace(
            validazione=SimpleNamespace(controlla_mondo=lambda _mondo: rapporto)
        )
        applicazione.albero_validazione = _AlberoFinto()
        applicazione.etichetta_validazione = _EtichettaFinta()
        applicazione._controlla_mondo()
        testo_gui = " ".join(str(valore) for riga in applicazione.albero_validazione.righe for valore in riga)
        self.assertIn("Epistemica", testo_gui)
        self.assertIn("Errore", testo_gui)
        self.assertIn("Akari", testo_gui)
        self.assertNotIn(problema.codice, testo_gui)
        self.assertNotIn("{", testo_gui)

    def test_gui_non_controlla_automaticamente_all_avvio(self) -> None:
        radice = mock.Mock()
        with (
            mock.patch("haria_engine.app.ServizioMondi"),
            mock.patch("haria_engine.app.CoordinatoreAsincrono"),
            mock.patch("haria_engine.app.tk.BooleanVar"),
            mock.patch.object(ApplicazioneHaria, "_costruisci_interfaccia"),
            mock.patch.object(ApplicazioneHaria, "_carica_configurazione_ai"),
            mock.patch.object(ApplicazioneHaria, "_carica_mondo_esistente"),
            mock.patch.object(ApplicazioneHaria, "_programma_controllo_ai"),
            mock.patch.object(ApplicazioneHaria, "_controlla_mondo") as controllo,
        ):
            ApplicazioneHaria(radice, self.database)
        controllo.assert_not_called()

    def test_gui_azzera_risultato_quando_cambia_mondo(self) -> None:
        applicazione = ApplicazioneHaria.__new__(ApplicazioneHaria)
        applicazione.mondo_corrente = SimpleNamespace(id=MONDO_ID)
        applicazione.albero_validazione = _AlberoFinto()
        applicazione.etichetta_validazione = _EtichettaFinta()
        applicazione.pulsante_controlla_mondo = _PulsanteFinto()
        applicazione._azzera_validazione()
        self.assertEqual(
            applicazione.etichetta_validazione.testo,
            UI_TEXT["validazione_non_eseguita"],
        )
        self.assertEqual(
            etichetta_ambito_validazione(AmbitoValidazione.INVENTARIO),
            "Inventario",
        )
        self.assertEqual(
            etichetta_severita_validazione(SeveritaProblema.AVVERTIMENTO),
            "Avvertimento",
        )


if __name__ == "__main__":
    unittest.main()
