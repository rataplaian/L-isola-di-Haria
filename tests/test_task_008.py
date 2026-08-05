from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from haria_engine.app import UI_TEXT, formatta_tempo_narrativo
from haria_engine.errors import ErroreMigrazione, ErroreTurnoNarrativo
from haria_engine.service import ServizioMondi
from tests.test_task_006 import crea_pacchetto_completo, scrivi_json


def aggiungi_file_al_manifest(pacchetto: Path, relativo: str, dati: object) -> None:
    percorso = pacchetto / relativo
    scrivi_json(percorso, dati)
    manifest_path = pacchetto / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"].append(
        {
            "path": relativo,
            "sha256": hashlib.sha256(percorso.read_bytes()).hexdigest(),
        }
    )
    manifest["files"].sort(key=lambda voce: voce["path"].casefold())
    scrivi_json(manifest_path, manifest)


def sostituisci_world_json(pacchetto: Path, dati: dict[str, object]) -> None:
    percorso = pacchetto / "world.json"
    scrivi_json(percorso, dati)
    manifest_path = pacchetto / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for voce in manifest["files"]:
        if voce["path"] == "world.json":
            voce["sha256"] = hashlib.sha256(percorso.read_bytes()).hexdigest()
    scrivi_json(manifest_path, manifest)


def output_turno(
    *,
    narrative: str = "La scena continua senza perdere memoria.",
    elapsed: int = 5,
    operations: list[dict[str, object]] | None = None,
    memories: list[dict[str, object]] | None = None,
) -> str:
    return json.dumps(
        {
            "narrative": narrative,
            "elapsed_minutes": elapsed,
            "operations": operations or [],
            "memories": memories or [],
        },
        ensure_ascii=False,
    )


def operazione_spostamento() -> dict[str, object]:
    return {
        "type": "move",
        "entity_id": "alba",
        "location_id": "archivio",
        "actor_id": "alba",
        "reason": "Alba raggiunge l'archivio.",
    }


def operazione_evento() -> dict[str, object]:
    return {
        "type": "event",
        "event_type": "scoperta",
        "actor_id": "alba",
        "target_id": "chiave",
        "location_id": "laboratorio",
        "reason": "Alba nota un segno sulla chiave.",
    }


def memoria_osservata(**modifiche: object) -> dict[str, object]:
    memoria: dict[str, object] = {
        "character_id": "alba",
        "knowledge_type": "observed_fact",
        "source_type": "direct_observation",
        "source_entity_id": None,
        "certainty": 95,
        "content": "La chiave porta un segno nuovo.",
        "interpretation": None,
        "associated_emotion": "curiosita",
        "operation_index": 0,
        "entities": [
            {"entity_id": "chiave", "role": "subject"},
            {"entity_id": "laboratorio", "role": "location"},
        ],
        "source_memory_ids": [],
    }
    memoria.update(modifiche)
    return memoria


class BaseTask008(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)
        self.pacchetto = crea_pacchetto_completo(self.radice)
        aggiungi_file_al_manifest(
            self.pacchetto,
            "locations/archivio.json",
            {"id": "archivio", "name": "Archivio", "status": "active"},
        )
        self.database = self.radice / "task008.sqlite3"
        self.servizio = ServizioMondi(self.database)
        self.mondo = self.servizio.importa_da_cartella(self.pacchetto)

    def tearDown(self) -> None:
        self.servizio.chiudi()
        self.temporanea.cleanup()

    def prepara(self, testo: str = "Osservo la stanza."):
        return self.servizio.narrativa.prepara_turno(self.mondo.id, testo)

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
            tuple(riga)
            for riga in connessione.execute(
                "SELECT entity_id, current_status, location_id, holder_id, version "
                "FROM entity_state ORDER BY entity_id"
            )
        )
        sessione = tuple(
            connessione.execute(
                "SELECT narrative_sessions.current_time, next_turn_number "
                "FROM narrative_sessions "
                "WHERE world_id = ?",
                (self.mondo.id,),
            ).fetchone()
            or ()
        )
        return conteggi, stati, sessione


class TestSessioniETurni(BaseTask008):
    def test_prompt_dichiara_natura_adulta_e_autonomia(self) -> None:
        sistema = self.prepara().messaggi[0].contenuto
        for istruzione in (
            "destinato esclusivamente a un pubblico adulto",
            "sessualità tra adulti",
            "coercizione",
            "schiavitù",
            "conflitti etnici e culturali",
            "salute mentale",
            "abuso di potere",
            "rifiuti morali generici",
            "automaticamente disponibili, innamorate, obbedienti o consenzienti",
            "volontà, consenso, opposizione e conseguenze",
            "esclusivamente personaggi adulti",
            "controllo esclusivo di Alba",
        ):
            with self.subTest(istruzione=istruzione):
                self.assertIn(istruzione, sistema)

    def test_schema_finale_e_sei(self) -> None:
        versione = self.servizio.archivio._connessione.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
        self.assertEqual(6, versione)

    def test_sessione_unica_viene_riusata(self) -> None:
        prima = self.servizio.narrativa.carica_partita(self.mondo.id).sessione
        seconda = self.servizio.narrativa.carica_partita(self.mondo.id).sessione
        self.assertEqual(prima, seconda)
        conteggio = self.servizio.archivio._connessione.execute(
            "SELECT COUNT(*) FROM narrative_sessions WHERE world_id = ?",
            (self.mondo.id,),
        ).fetchone()[0]
        self.assertEqual(1, conteggio)

    def test_fallback_temporale_e_utc_consapevole(self) -> None:
        sessione = self.servizio.narrativa.carica_partita(self.mondo.id).sessione
        istante = datetime.fromisoformat(sessione.current_time)
        self.assertIsNotNone(istante.utcoffset())
        self.assertLess(abs(datetime.now(timezone.utc) - istante), timedelta(minutes=1))

    def test_turno_senza_operazioni_salva_audit_e_avanza_tempo(self) -> None:
        preparato = self.prepara()
        raw = output_turno(elapsed=17)
        salvato = self.servizio.narrativa.salva_risposta_turno(preparato, raw)
        sessione = self.servizio.narrativa.carica_partita(self.mondo.id).sessione
        self.assertEqual(raw, salvato.raw_model_output)
        self.assertEqual(preparato.prompt_visibile, salvato.prompt_text)
        self.assertEqual(17, salvato.elapsed_minutes)
        self.assertEqual(salvato.world_time_after, sessione.current_time)
        self.assertEqual(2, sessione.next_turn_number)
        self.assertEqual(0, len(self.servizio.archivio.elenca_eventi(self.mondo.id)))

    def test_spostamento_salva_turno_evento_e_stato(self) -> None:
        preparato = self.prepara()
        self.servizio.narrativa.salva_risposta_turno(
            preparato, output_turno(operations=[operazione_spostamento()])
        )
        alba = self.servizio.archivio.carica_entita(self.mondo.id, "alba")
        eventi = self.servizio.archivio.eventi_per_entita(self.mondo.id, "alba")
        self.assertEqual("archivio", alba.location_id)
        self.assertEqual(2, alba.version)
        self.assertEqual(1, len(eventi))
        self.assertEqual("spostamento_entita", eventi[0].event_type)

    def test_due_operazioni_stessa_entita_persistono_versione_finale(self) -> None:
        operazioni = [
            {
                "type": "state_change",
                "target_id": "alba",
                "condition": "vigile",
                "reason": "Alba presta attenzione.",
            },
            {
                "type": "state_change",
                "target_id": "alba",
                "status": "allerta",
                "reason": "Il rumore la mette in allerta.",
            },
        ]
        self.servizio.narrativa.salva_risposta_turno(
            self.prepara(), output_turno(operations=operazioni)
        )
        alba = self.servizio.archivio.carica_entita(self.mondo.id, "alba")
        self.assertEqual(3, alba.version)
        self.assertEqual("vigile", alba.condition)
        self.assertEqual("allerta", alba.status)
        self.assertEqual(2, len(self.servizio.archivio.elenca_eventi(self.mondo.id)))

    def test_eventi_del_turno_rispettano_indice_operazione(self) -> None:
        operazioni = [
            {
                "type": "event",
                "event_type": "primo_evento",
                "actor_id": "alba",
                "location_id": "laboratorio",
                "reason": "Primo motivo.",
            },
            {
                "type": "event",
                "event_type": "secondo_evento",
                "actor_id": "alba",
                "location_id": "laboratorio",
                "reason": "Secondo motivo.",
            },
        ]
        self.servizio.narrativa.salva_risposta_turno(
            self.prepara(), output_turno(operations=operazioni)
        )
        attesi = ["Primo motivo.", "Secondo motivo."]
        self.assertEqual(
            attesi,
            [
                evento.reason
                for evento in self.servizio.archivio.elenca_eventi(self.mondo.id)
            ],
        )
        self.assertEqual(
            attesi,
            [
                evento.reason
                for evento in self.servizio.archivio.eventi_per_entita(
                    self.mondo.id, "alba"
                )
            ],
        )

    def test_memorie_del_turno_rispettano_indice_memoria(self) -> None:
        memorie = [
            memoria_osservata(
                source_type="self_experience",
                operation_index=None,
                content="Prima memoria del turno.",
            ),
            memoria_osservata(
                source_type="self_experience",
                operation_index=None,
                content="Seconda memoria del turno.",
            ),
        ]
        self.servizio.narrativa.salva_risposta_turno(
            self.prepara(), output_turno(memories=memorie)
        )
        rilette = self.servizio.archivio.elenca_memorie_personaggio(
            self.mondo.id, "alba"
        )
        self.assertEqual(
            ["Prima memoria del turno.", "Seconda memoria del turno."],
            [memoria.content for memoria in rilette[-2:]],
        )

    def test_memoria_candidata_collegata_all_evento(self) -> None:
        self.servizio.narrativa.salva_risposta_turno(
            self.prepara(),
            output_turno(
                operations=[operazione_evento()], memories=[memoria_osservata()]
            ),
        )
        memoria = self.servizio.archivio.elenca_memorie_personaggio(
            self.mondo.id, "alba"
        )[-1]
        evento = self.servizio.archivio.elenca_eventi(self.mondo.id)[0]
        self.assertEqual(evento.event_id, memoria.event_id)
        collegamento = self.servizio.archivio._connessione.execute(
            "SELECT memory_index FROM narrative_turn_memories WHERE memory_id = ?",
            (memoria.memory_id,),
        ).fetchone()
        self.assertEqual(0, collegamento[0])

    def test_riapertura_ricarica_conversazione_e_tempo(self) -> None:
        self.servizio.narrativa.salva_risposta_turno(
            self.prepara("Entro nel laboratorio."), output_turno(elapsed=9)
        )
        attesa = self.servizio.narrativa.carica_partita(self.mondo.id)
        self.servizio.chiudi()
        self.servizio = ServizioMondi(self.database)
        ricaricata = self.servizio.narrativa.carica_partita(self.mondo.id)
        self.assertEqual(attesa.sessione, ricaricata.sessione)
        self.assertEqual(attesa.turni, ricaricata.turni)

    def test_prompt_usa_ultimi_venti_messaggi_ma_archivio_resta_completo(self) -> None:
        for indice in range(12):
            preparato = self.prepara(f"Azione {indice}")
            self.servizio.narrativa.salva_risposta_turno(
                preparato,
                output_turno(narrative=f"Risposta {indice}", elapsed=0),
            )
        self.assertEqual(
            12, len(self.servizio.archivio.elenca_turni_narrativi(self.mondo.id))
        )
        prompt = self.prepara("Azione finale").messaggi[1].contenuto
        self.assertNotIn("Azione 1\n", prompt)
        self.assertIn("Azione 2", prompt)
        self.assertIn("Risposta 11", prompt)

    def test_testo_utf8_adulto_e_controverso_non_viene_trasformato(self) -> None:
        testo = "Due adulti discutono di sesso, violenza e libertà senza censura automatica."
        salvato = self.servizio.narrativa.salva_risposta_turno(
            self.prepara(testo), output_turno(narrative=testo)
        )
        self.assertEqual(testo, salvato.user_input)
        self.assertEqual(testo, salvato.narrative)


class TestRollbackAtomico(BaseTask008):
    def test_conoscenza_canonica_generata_non_scrive_nulla(self) -> None:
        preparato = self.prepara()
        prima = self.fotografia()
        memoria = memoria_osservata(knowledge_type="canonical_knowledge")
        with self.assertRaisesRegex(ErroreTurnoNarrativo, "conoscenze canoniche"):
            self.servizio.narrativa.salva_risposta_turno(
                preparato,
                output_turno(
                    operations=[operazione_evento()], memories=[memoria]
                ),
            )
        self.assertEqual(prima, self.fotografia())

    def test_belief_da_osservazione_diretta_non_scrive_nulla(self) -> None:
        preparato = self.prepara()
        prima = self.fotografia()
        memoria = memoria_osservata(knowledge_type="belief")
        with self.assertRaisesRegex(ErroreTurnoNarrativo, "non è coerente"):
            self.servizio.narrativa.salva_risposta_turno(
                preparato,
                output_turno(
                    operations=[operazione_evento()], memories=[memoria]
                ),
            )
        self.assertEqual(prima, self.fotografia())

    def test_memoria_non_inferenziale_con_fonti_non_scrive_nulla(self) -> None:
        memoria_esistente = self.servizio.archivio.elenca_memorie_personaggio(
            self.mondo.id, "alba"
        )[0]
        preparato = self.prepara()
        prima = self.fotografia()
        memoria = memoria_osservata(
            source_type="self_experience",
            operation_index=None,
            source_memory_ids=[memoria_esistente.memory_id],
        )
        with self.assertRaisesRegex(ErroreTurnoNarrativo, "non inferenziale"):
            self.servizio.narrativa.salva_risposta_turno(
                preparato, output_turno(memories=[memoria])
            )
        self.assertEqual(prima, self.fotografia())

    def test_osservazione_diretta_senza_operazione_non_scrive_nulla(self) -> None:
        preparato = self.prepara()
        prima = self.fotografia()
        memoria = memoria_osservata(operation_index=None)
        with self.assertRaisesRegex(ErroreTurnoNarrativo, "osservazione diretta"):
            self.servizio.narrativa.salva_risposta_turno(
                preparato, output_turno(memories=[memoria])
            )
        self.assertEqual(prima, self.fotografia())

    def test_memoria_importata_non_puo_essere_creata_dal_modello(self) -> None:
        preparato = self.prepara()
        prima = self.fotografia()
        memoria = memoria_osservata(
            source_type="imported_background", operation_index=None
        )
        with self.assertRaisesRegex(ErroreTurnoNarrativo, "sfondo importate"):
            self.servizio.narrativa.salva_risposta_turno(
                preparato, output_turno(memories=[memoria])
            )
        self.assertEqual(prima, self.fotografia())

    def test_racconto_richiede_fonte_personaggio_distinta(self) -> None:
        preparato = self.prepara()
        prima = self.fotografia()
        memoria = memoria_osservata(
            knowledge_type="reported_fact",
            source_type="told_by_character",
            source_entity_id="alba",
            operation_index=None,
        )
        with self.assertRaisesRegex(ErroreTurnoNarrativo, "distinti"):
            self.servizio.narrativa.salva_risposta_turno(
                preparato, output_turno(memories=[memoria])
            )
        self.assertEqual(prima, self.fotografia())

    def test_memoria_con_riferimento_invalido_non_scrive_nulla(self) -> None:
        preparato = self.prepara()
        prima = self.fotografia()
        memoria = memoria_osservata(
            entities=[{"entity_id": "inesistente", "role": "subject"}]
        )
        with self.assertRaises(ErroreTurnoNarrativo):
            self.servizio.narrativa.salva_risposta_turno(
                preparato,
                output_turno(
                    operations=[operazione_evento()], memories=[memoria]
                ),
            )
        self.assertEqual(prima, self.fotografia())

    def test_errore_a_meta_transazione_annulla_tutto(self) -> None:
        preparato = self.prepara()
        connessione = self.servizio.archivio._connessione
        connessione.execute(
            """
            CREATE TRIGGER test_blocca_link_memoria
            BEFORE INSERT ON narrative_turn_memories
            BEGIN SELECT RAISE(ABORT, 'errore iniettato'); END
            """
        )
        connessione.commit()
        prima = self.fotografia()
        with self.assertRaisesRegex(ErroreTurnoNarrativo, "rimasti invariati"):
            self.servizio.narrativa.salva_risposta_turno(
                preparato,
                output_turno(
                    operations=[operazione_evento()],
                    memories=[memoria_osservata()],
                ),
            )
        self.assertEqual(prima, self.fotografia())

    def test_versione_stato_obsoleta_esegue_rollback(self) -> None:
        preparato = self.prepara()
        connessione = self.servizio.archivio._connessione
        connessione.execute(
            "UPDATE entity_state SET version = version + 1 WHERE world_id = ? AND entity_id = 'alba'",
            (self.mondo.id,),
        )
        connessione.commit()
        prima = self.fotografia()
        with self.assertRaises(ErroreTurnoNarrativo):
            self.servizio.narrativa.salva_risposta_turno(
                preparato, output_turno(operations=[operazione_spostamento()])
            )
        self.assertEqual(prima, self.fotografia())

    def test_sessione_obsoleta_esegue_rollback(self) -> None:
        preparato = self.prepara()
        connessione = self.servizio.archivio._connessione
        connessione.execute(
            "UPDATE narrative_sessions SET next_turn_number = 2 WHERE world_id = ?",
            (self.mondo.id,),
        )
        connessione.commit()
        prima = self.fotografia()
        with self.assertRaises(ErroreTurnoNarrativo):
            self.servizio.narrativa.salva_risposta_turno(
                preparato, output_turno()
            )
        self.assertEqual(prima, self.fotografia())

    def test_output_non_valido_non_scrive_turno(self) -> None:
        preparato = self.prepara()
        prima = self.fotografia()
        with self.assertRaises(ErroreTurnoNarrativo):
            self.servizio.narrativa.salva_risposta_turno(
                preparato, "non e json"
            )
        self.assertEqual(prima, self.fotografia())


class TestMigrazioneTask008(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)
        self.database = self.radice / "migrazione.sqlite3"
        pacchetto = crea_pacchetto_completo(self.radice)
        servizio = ServizioMondi(self.database)
        self.mondo = servizio.importa_da_cartella(pacchetto)
        servizio.chiudi()
        self._retrocedi_a_schema_5()

    def tearDown(self) -> None:
        self.temporanea.cleanup()

    def _retrocedi_a_schema_5(self) -> None:
        connessione = sqlite3.connect(self.database)
        connessione.execute("PRAGMA foreign_keys = OFF")
        for tabella in (
            "narrative_turn_memories",
            "narrative_turn_events",
            "narrative_turns",
            "narrative_sessions",
        ):
            connessione.execute(f"DROP TABLE {tabella}")
        connessione.execute("PRAGMA user_version = 5")
        connessione.commit()
        connessione.close()

    def test_migrazione_cinque_a_sei_preserva_tutti_i_dati(self) -> None:
        lettura = sqlite3.connect(self.database)
        prima = lettura.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        lettura.close()
        servizio = ServizioMondi(self.database)
        try:
            connessione = servizio.archivio._connessione
            self.assertEqual(6, connessione.execute("PRAGMA user_version").fetchone()[0])
            self.assertEqual(prima, connessione.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
            self.assertEqual(1, connessione.execute("SELECT COUNT(*) FROM worlds").fetchone()[0])
        finally:
            servizio.chiudi()

    def test_migrazione_fallita_torna_interamente_a_schema_cinque(self) -> None:
        connessione = sqlite3.connect(self.database)
        connessione.execute("CREATE VIEW narrative_sessions AS SELECT id FROM worlds")
        connessione.commit()
        connessione.close()
        with self.assertRaises(ErroreMigrazione):
            ServizioMondi(self.database)
        verifica = sqlite3.connect(self.database)
        try:
            self.assertEqual(5, verifica.execute("PRAGMA user_version").fetchone()[0])
            oggetti = dict(
                verifica.execute(
                    "SELECT name, type FROM sqlite_master WHERE name LIKE 'narrative_%'"
                )
            )
            self.assertEqual({"narrative_sessions": "view"}, oggetti)
            self.assertEqual("ok", verifica.execute("PRAGMA quick_check").fetchone()[0])
        finally:
            verifica.close()


class TestTempoCanonicoTask008(unittest.TestCase):
    def test_narrative_start_at_valido_ancora_la_sessione(self) -> None:
        with tempfile.TemporaryDirectory() as temporanea:
            radice = Path(temporanea)
            pacchetto = crea_pacchetto_completo(radice)
            world = json.loads((pacchetto / "world.json").read_text(encoding="utf-8"))
            world["narrative_start_at"] = "2026-03-14T09:30:00+01:00"
            sostituisci_world_json(pacchetto, world)
            servizio = ServizioMondi(radice / "tempo.sqlite3")
            try:
                mondo = servizio.importa_da_cartella(pacchetto)
                sessione = servizio.narrativa.carica_partita(mondo.id).sessione
                self.assertEqual(
                    "2026-03-14T09:30:00.000000+01:00", sessione.current_time
                )
            finally:
                servizio.chiudi()


class TestInterfacciaTask008(unittest.TestCase):
    def test_gui_dichiara_partita_locale_persistente(self) -> None:
        self.assertEqual("Partita locale persistente", UI_TEXT["anteprima_narrativa"])
        self.assertEqual(
            "14/03/2026 alle 09:30 (+0100)",
            formatta_tempo_narrativo("2026-03-14T09:30:00+01:00"),
        )


class TestProtezioneCronologiaTask008(BaseTask008):
    def setUp(self) -> None:
        super().setUp()
        self.servizio.narrativa.salva_risposta_turno(
            self.prepara(),
            output_turno(
                operations=[operazione_evento()], memories=[memoria_osservata()]
            ),
        )

    def test_turni_e_collegamenti_sono_append_only(self) -> None:
        connessione = self.servizio.archivio._connessione
        for tabella in (
            "narrative_turns",
            "narrative_turn_events",
            "narrative_turn_memories",
        ):
            with self.subTest(tabella=tabella, operazione="update"):
                with self.assertRaises(sqlite3.IntegrityError):
                    connessione.execute(f"UPDATE {tabella} SET world_id = world_id")
                connessione.rollback()
            with self.subTest(tabella=tabella, operazione="delete"):
                with self.assertRaises(sqlite3.IntegrityError):
                    connessione.execute(f"DELETE FROM {tabella}")
                connessione.rollback()


if __name__ == "__main__":
    unittest.main()
