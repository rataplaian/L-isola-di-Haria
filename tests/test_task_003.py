from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
import uuid
from dataclasses import replace
from pathlib import Path

from haria_engine.app import UI_TEXT
from haria_engine.errors import ErroreMemoria, ErroreMigrazione
from haria_engine.memories import (
    AssociazioneMemoria,
    FonteMemoria,
    MemoriaDaSalvare,
)
from haria_engine.service import ServizioMondi


RADICE_PROGETTO = Path(__file__).resolve().parents[1]
MINI_BIBBIA = RADICE_PROGETTO / "sample_world"


def impronte_cartella(cartella: Path) -> dict[str, str]:
    return {
        file.relative_to(cartella).as_posix(): hashlib.sha256(
            file.read_bytes()
        ).hexdigest()
        for file in sorted(cartella.rglob("*"))
        if file.is_file()
    }


def riduci_a_schema_2(database: Path) -> None:
    connessione = sqlite3.connect(database)
    try:
        connessione.execute("PRAGMA foreign_keys = OFF")
        for trigger in (
            "memories_character_must_be_character",
            "memories_append_only_update",
            "memories_append_only_delete",
            "memory_entities_append_only_update",
            "memory_entities_append_only_delete",
            "memory_sources_append_only_update",
            "memory_sources_append_only_delete",
        ):
            connessione.execute(f"DROP TRIGGER IF EXISTS {trigger}")
        connessione.execute("DROP TABLE memory_sources")
        connessione.execute("DROP TABLE memory_entities")
        connessione.execute("DROP TABLE memories")
        connessione.execute("PRAGMA user_version = 2")
        connessione.commit()
    finally:
        connessione.close()


class TestMigrazioneSchema3(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)
        self.sorgente = self.radice / "mini_bibbia"
        shutil.copytree(MINI_BIBBIA, self.sorgente)
        self.database = self.radice / "haria_v2.sqlite3"
        with ServizioMondi(self.database) as servizio:
            servizio.importa_da_cartella(self.sorgente)
            servizio.salva(
                "haria_minimal_test", "Scenario conservato", {"tone": "sobrio"}
            )
        riduci_a_schema_2(self.database)

    def tearDown(self) -> None:
        self.temporanea.cleanup()

    def test_migrazione_2_a_3_usa_solo_fotografie_e_preserva_mondo(self) -> None:
        shutil.rmtree(self.sorgente)
        with ServizioMondi(self.database) as servizio:
            mondo = servizio.carica_mondo("haria_minimal_test")
            memorie = servizio.archivio._connessione.execute(
                "SELECT content FROM memories ORDER BY content"
            ).fetchall()
            versione = servizio.archivio._connessione.execute(
                "PRAGMA user_version"
            ).fetchone()[0]

        self.assertEqual(3, versione)
        self.assertEqual("Scenario conservato", mondo.scenario)
        self.assertEqual(4, len(memorie))

    def test_riapertura_schema_3_non_duplica_memorie_importate(self) -> None:
        with ServizioMondi(self.database):
            pass
        with ServizioMondi(self.database) as servizio:
            prima = servizio.archivio._connessione.execute(
                "SELECT memory_id FROM memories ORDER BY memory_id"
            ).fetchall()
        with ServizioMondi(self.database) as servizio:
            dopo = servizio.archivio._connessione.execute(
                "SELECT memory_id FROM memories ORDER BY memory_id"
            ).fetchall()
        self.assertEqual(prima, dopo)
        self.assertEqual(4, len(dopo))

    def test_importazione_conoscenze_preserva_testo_e_non_inventa_entita(self) -> None:
        sorgenti_prima = impronte_cartella(self.sorgente)
        with ServizioMondi(self.database) as servizio:
            righe = servizio.archivio._connessione.execute(
                """
                SELECT character_id, content, knowledge_type, source_type,
                       certainty, event_id
                FROM memories ORDER BY character_id, content
                """
            ).fetchall()
            associazioni = servizio.archivio._connessione.execute(
                "SELECT COUNT(*) FROM memory_entities"
            ).fetchone()[0]
        self.assertEqual(4, len(righe))
        self.assertIn(
            "Ricorda soltanto il proprio nome.",
            {riga["content"] for riga in righe},
        )
        self.assertTrue(
            all(riga["knowledge_type"] == "canonical_knowledge" for riga in righe)
        )
        self.assertTrue(
            all(riga["source_type"] == "imported_background" for riga in righe)
        )
        self.assertTrue(all(riga["certainty"] == 100 for riga in righe))
        self.assertTrue(all(riga["event_id"] is None for riga in righe))
        self.assertEqual(0, associazioni)
        self.assertEqual(sorgenti_prima, impronte_cartella(self.sorgente))

    def test_migrazione_senza_characters_esegue_rollback_integrale(self) -> None:
        connessione = sqlite3.connect(self.database)
        connessione.execute(
            "DELETE FROM source_files WHERE relative_path = 'characters.json'"
        )
        connessione.commit()
        connessione.close()

        with self.assertRaisesRegex(ErroreMigrazione, "schema 2 senza dati parziali"):
            ServizioMondi(self.database)
        versione, tabelle = self._versione_e_tabelle()
        self.assertEqual(2, versione)
        self.assertNotIn("memories", tabelle)
        self.assertNotIn("memory_entities", tabelle)
        self.assertNotIn("memory_sources", tabelle)

    def test_migrazione_con_characters_non_valido_esegue_rollback(self) -> None:
        connessione = sqlite3.connect(self.database)
        connessione.execute(
            "UPDATE source_files SET content = ? WHERE relative_path = 'characters.json'",
            (b"{non valido",),
        )
        connessione.commit()
        connessione.close()

        with self.assertRaisesRegex(ErroreMigrazione, "UTF-8"):
            ServizioMondi(self.database)
        versione, tabelle = self._versione_e_tabelle()
        self.assertEqual(2, versione)
        self.assertNotIn("memories", tabelle)
        self.assertNotIn("memory_entities", tabelle)
        self.assertNotIn("memory_sources", tabelle)

    def _versione_e_tabelle(self) -> tuple[int, set[str]]:
        connessione = sqlite3.connect(self.database)
        try:
            versione = connessione.execute("PRAGMA user_version").fetchone()[0]
            tabelle = {
                riga[0]
                for riga in connessione.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            return versione, tabelle
        finally:
            connessione.close()


class TestMemorieSoggettive(unittest.TestCase):
    def setUp(self) -> None:
        self.temporanea = tempfile.TemporaryDirectory()
        self.radice = Path(self.temporanea.name)
        self.sorgente = self.radice / "mini_bibbia"
        shutil.copytree(MINI_BIBBIA, self.sorgente)
        self.database = self.radice / "haria.sqlite3"
        self.servizio = ServizioMondi(self.database)
        self.mondo = self.servizio.importa_da_cartella(self.sorgente)

    def tearDown(self) -> None:
        self.servizio.chiudi()
        self.temporanea.cleanup()

    def _trasferimento_penna(self):
        return self.servizio.stato_mondo.trasferisci_oggetto(
            self.mondo.id,
            "pen_blue",
            "luca",
            reason="Luca prende la penna blu.",
        )

    def _osservazione_elise(self):
        evento = self._trasferimento_penna()
        memoria = self.servizio.memorie.registra_osservazione_diretta(
            self.mondo.id,
            "elise_moreau",
            evento.event_id,
            "Élise vede Luca prendere la penna blu.",
            95,
            interpretation="Un gesto deliberato.",
            emotion="curiosità",
            entity_ids=("luca", "pen_blue"),
        )
        return evento, memoria

    def _memoria_grezza(
        self,
        *,
        character_id: str = "akari_mori",
        world_id: str | None = None,
        **modifiche,
    ) -> MemoriaDaSalvare:
        memoria = MemoriaDaSalvare(
            memory_id=uuid.uuid4().hex,
            world_id=world_id or self.mondo.id,
            character_id=character_id,
            event_id=None,
            knowledge_type="belief",
            source_type="self_experience",
            source_entity_id=None,
            learned_at="2026-01-01T00:00:00+00:00",
            certainty=50,
            content="Una convinzione soggettiva.",
            interpretation=None,
            associated_emotion=None,
            status="active",
            supersedes_memory_id=None,
            created_at="2026-01-01T00:00:00+00:00",
        )
        return replace(memoria, **modifiche)

    def test_evento_non_crea_memorie_automatiche(self) -> None:
        prima = self._numero_memorie()
        self._trasferimento_penna()
        self.assertEqual(prima, self._numero_memorie())

    def test_osservazione_elise_collega_evento_e_entita_richieste(self) -> None:
        evento, memoria = self._osservazione_elise()
        self.assertEqual(evento.event_id, memoria.event_id)
        self.assertEqual("observed_fact", memoria.knowledge_type)
        self.assertEqual("direct_observation", memoria.source_type)
        self.assertEqual(
            {"luca", "pen_blue", "infirmary"},
            {entita.entity_id for entita in memoria.entities},
        )
        self.assertEqual(1, len(self.servizio.stato_mondo.elenca_eventi(self.mondo.id)))

    def test_akari_assente_non_puo_osservare_e_non_riceve_memoria(self) -> None:
        evento = self._trasferimento_penna()
        prima = len(
            self.servizio.memorie.elenca_memorie_personaggio(
                self.mondo.id, "akari_mori", solo_correnti=False
            )
        )
        with self.assertRaisesRegex(ErroreMemoria, "non è presente"):
            self.servizio.memorie.registra_osservazione_diretta(
                self.mondo.id, "akari_mori", evento.event_id, "Akari vede.", 80
            )
        dopo = len(
            self.servizio.memorie.elenca_memorie_personaggio(
                self.mondo.id, "akari_mori", solo_correnti=False
            )
        )
        self.assertEqual(prima, dopo)

    def test_osservazione_duplicata_viene_rifiutata(self) -> None:
        evento, memoria = self._osservazione_elise()
        with self.assertRaisesRegex(ErroreMemoria, "identica"):
            self.servizio.memorie.registra_osservazione_diretta(
                self.mondo.id,
                "elise_moreau",
                evento.event_id,
                memoria.content,
                memoria.certainty,
                interpretation=memoria.interpretation,
                emotion=memoria.associated_emotion,
                entity_ids=("luca", "pen_blue"),
            )

    def test_racconto_elise_akari_resta_memoria_distinta(self) -> None:
        evento, osservazione = self._osservazione_elise()
        racconto = self.servizio.memorie.registra_racconto(
            self.mondo.id,
            "akari_mori",
            "elise_moreau",
            "Luca ha preso la penna.",
            62,
            event_id=evento.event_id,
            entity_ids=("luca", "pen_blue"),
        )
        self.assertNotEqual(osservazione.memory_id, racconto.memory_id)
        self.assertEqual("reported_fact", racconto.knowledge_type)
        self.assertEqual("told_by_character", racconto.source_type)
        self.assertEqual("Élise Moreau", racconto.source_name)
        self.assertNotEqual(osservazione.certainty, racconto.certainty)

    def test_contenuto_soggettivo_non_inventa_evento_o_modifica_stato(self) -> None:
        evento = self._trasferimento_penna()
        racconto = self.servizio.memorie.registra_racconto(
            self.mondo.id,
            "akari_mori",
            "elise_moreau",
            "Luca ha rubato la penna.",
            70,
            event_id=evento.event_id,
            entity_ids=("luca", "pen_blue"),
        )
        penna = self.servizio.stato_mondo.carica_entita(self.mondo.id, "pen_blue")
        eventi = self.servizio.stato_mondo.elenca_eventi(self.mondo.id)
        self.assertIn("rubato", racconto.content)
        self.assertEqual("trasferimento_oggetto", eventi[0].event_type)
        self.assertEqual(1, len(eventi))
        self.assertEqual("luca", penna.holder_id)

    def test_inferenza_errata_con_fonti_ordinate_e_ammessa(self) -> None:
        _, osservazione = self._osservazione_elise()
        seconda = self.servizio.memorie.registra_inferenza(
            self.mondo.id,
            "elise_moreau",
            "La penna controlla il tempo.",
            15,
            source_memory_ids=(
                osservazione.memory_id,
                self._memoria_importata("elise_moreau").memory_id,
            ),
        )
        self.assertEqual("La penna controlla il tempo.", seconda.content)
        self.assertEqual(
            (
                osservazione.memory_id,
                self._memoria_importata("elise_moreau").memory_id,
            ),
            seconda.source_memory_ids,
        )

    def test_filtri_per_evento_entita_e_fonte(self) -> None:
        evento, memoria = self._osservazione_elise()
        per_evento = self.servizio.memorie.elenca_memorie_personaggio(
            self.mondo.id, "elise_moreau", event_id=evento.event_id
        )
        per_entita = self.servizio.memorie.elenca_memorie_personaggio(
            self.mondo.id, "elise_moreau", entity_id="pen_blue"
        )
        per_fonte = self.servizio.memorie.elenca_memorie_personaggio(
            self.mondo.id, "elise_moreau", source_type="direct_observation"
        )
        self.assertEqual([memoria.memory_id], [voce.memory_id for voce in per_evento])
        self.assertEqual([memoria.memory_id], [voce.memory_id for voce in per_entita])
        self.assertEqual([memoria.memory_id], [voce.memory_id for voce in per_fonte])

    def test_correzione_append_only_espone_status_corrente_ed_effettivo(self) -> None:
        evento = self._trasferimento_penna()
        vecchia = self.servizio.memorie.registra_racconto(
            self.mondo.id,
            "akari_mori",
            "elise_moreau",
            "Luca ha rubato la penna.",
            70,
            event_id=evento.event_id,
        )
        nuova = self.servizio.memorie.correggi_memoria(
            self.mondo.id,
            "akari_mori",
            vecchia.memory_id,
            "Luca ha preso la penna con il permesso di Élise.",
            92,
        )
        vecchia_ricaricata = self.servizio.archivio.carica_memoria(
            self.mondo.id, vecchia.memory_id
        )
        self.assertEqual("active", vecchia_ricaricata.status)
        self.assertFalse(vecchia_ricaricata.is_current)
        self.assertEqual("superseded", vecchia_ricaricata.effective_status)
        self.assertEqual("corrected", nuova.status)
        self.assertTrue(nuova.is_current)
        self.assertEqual("corrected", nuova.effective_status)
        self.assertEqual(
            {(entita.entity_id, entita.role) for entita in vecchia.entities},
            {(entita.entity_id, entita.role) for entita in nuova.entities},
        )

    def test_vista_corrente_e_cronologia_completa(self) -> None:
        _, vecchia = self._osservazione_elise()
        nuova = self.servizio.memorie.correggi_memoria(
            self.mondo.id,
            "elise_moreau",
            vecchia.memory_id,
            "Élise precisa ciò che ha visto.",
            99,
        )
        correnti = self.servizio.memorie.elenca_memorie_personaggio(
            self.mondo.id, "elise_moreau"
        )
        cronologia = self.servizio.memorie.elenca_memorie_personaggio(
            self.mondo.id, "elise_moreau", solo_correnti=False
        )
        self.assertIn(nuova.memory_id, {m.memory_id for m in correnti})
        self.assertNotIn(vecchia.memory_id, {m.memory_id for m in correnti})
        self.assertTrue({vecchia.memory_id, nuova.memory_id}.issubset({m.memory_id for m in cronologia}))

    def test_catena_lineare_valida_con_piu_correzioni(self) -> None:
        iniziale = self._memoria_importata("akari_mori")
        seconda = self.servizio.memorie.correggi_memoria(
            self.mondo.id, "akari_mori", iniziale.memory_id, "Prima correzione.", 80
        )
        terza = self.servizio.memorie.correggi_memoria(
            self.mondo.id,
            "akari_mori",
            seconda.memory_id,
            "Seconda correzione.",
            90,
            status="contradicted",
        )
        self.assertEqual(iniziale.memory_id, seconda.supersedes_memory_id)
        self.assertEqual(seconda.memory_id, terza.supersedes_memory_id)
        self.assertTrue(terza.is_current)

    def test_correzione_di_memoria_non_corrente_viene_rifiutata(self) -> None:
        iniziale = self._memoria_importata("akari_mori")
        self.servizio.memorie.correggi_memoria(
            self.mondo.id, "akari_mori", iniziale.memory_id, "Correzione.", 80
        )
        with self.assertRaisesRegex(ErroreMemoria, "non è più corrente"):
            self.servizio.memorie.correggi_memoria(
                self.mondo.id, "akari_mori", iniziale.memory_id, "Ramo.", 70
            )

    def test_indice_impedisce_secondo_successore_diretto(self) -> None:
        iniziale = self._memoria_importata("akari_mori")
        self.servizio.memorie.correggi_memoria(
            self.mondo.id, "akari_mori", iniziale.memory_id, "Correzione.", 80
        )
        ramo = self._memoria_grezza(
            supersedes_memory_id=iniziale.memory_id, status="corrected"
        )
        with self.assertRaises(ErroreMemoria):
            self.servizio.archivio.registra_memoria(ramo, (), ())
        with self.assertRaises(ErroreMemoria):
            self.servizio.archivio.carica_memoria(self.mondo.id, ramo.memory_id)

    def test_autoreferenzialita_memoria_viene_rifiutata(self) -> None:
        memoria = self._memoria_grezza()
        memoria = replace(memoria, supersedes_memory_id=memoria.memory_id)
        with self.assertRaises(ErroreMemoria):
            self.servizio.archivio.registra_memoria(memoria, (), ())

    def test_memory_sources_rifiuta_altra_persona_e_altro_mondo(self) -> None:
        fonte_akari = self._memoria_importata("akari_mori")
        memoria_elise = self._memoria_grezza(character_id="elise_moreau")
        with self.assertRaises(ErroreMemoria):
            self.servizio.archivio.registra_memoria(
                memoria_elise, (), (FonteMemoria(fonte_akari.memory_id, 1),)
            )

        altro = self._importa_altro_mondo()
        fonte_altro = self.servizio.memorie.elenca_memorie_personaggio(
            altro.id, "akari_mori"
        )[0]
        memoria = self._memoria_grezza()
        with self.assertRaises(ErroreMemoria):
            self.servizio.archivio.registra_memoria(
                memoria, (), (FonteMemoria(fonte_altro.memory_id, 1),)
            )

    def test_memory_sources_rifiuta_propria_sorgente(self) -> None:
        memoria = self._memoria_grezza()
        with self.assertRaises(ErroreMemoria):
            self.servizio.archivio.registra_memoria(
                memoria, (), (FonteMemoria(memoria.memory_id, 1),)
            )

    def test_memory_sources_rifiuta_posizione_duplicata_con_rollback(self) -> None:
        fonti = self.servizio.memorie.elenca_memorie_personaggio(
            self.mondo.id, "elise_moreau"
        )
        memoria = self._memoria_grezza(character_id="elise_moreau")
        with self.assertRaises(ErroreMemoria):
            self.servizio.archivio.registra_memoria(
                memoria,
                (),
                (
                    FonteMemoria(fonti[0].memory_id, 1),
                    FonteMemoria(fonti[1].memory_id, 1),
                ),
            )
        with self.assertRaises(ErroreMemoria):
            self.servizio.archivio.carica_memoria(self.mondo.id, memoria.memory_id)

    def test_memory_sources_rifiuta_posizione_non_positiva(self) -> None:
        fonte = self._memoria_importata("akari_mori")
        memoria = self._memoria_grezza()
        with self.assertRaises(ErroreMemoria):
            self.servizio.archivio.registra_memoria(
                memoria, (), (FonteMemoria(fonte.memory_id, 0),)
            )
        self.assertEqual(0, self._conta("memories", memoria.memory_id))

    def test_sorgente_inesistente_esegue_rollback_totale(self) -> None:
        memoria = self._memoria_grezza()
        with self.assertRaisesRegex(ErroreMemoria, "rimaste invariate"):
            self.servizio.archivio.registra_memoria(
                memoria,
                (AssociazioneMemoria("akari_mori", "subject"),),
                (FonteMemoria("memoria_inesistente", 1),),
            )
        self.assertEqual(0, self._conta("memories", memoria.memory_id))
        self.assertEqual(0, self._conta("memory_entities", memoria.memory_id))
        self.assertEqual(0, self._conta("memory_sources", memoria.memory_id))

    def test_rollback_totale_se_associazione_non_valida(self) -> None:
        memoria = self._memoria_grezza()
        with self.assertRaisesRegex(ErroreMemoria, "rimaste invariate"):
            self.servizio.archivio.registra_memoria(
                memoria,
                (
                    AssociazioneMemoria("akari_mori", "subject"),
                    AssociazioneMemoria("inesistente", "related"),
                ),
                (),
            )
        self.assertEqual(0, self._conta("memories", memoria.memory_id))
        self.assertEqual(0, self._conta("memory_entities", memoria.memory_id))

    def test_trigger_append_only_memories_e_memory_entities(self) -> None:
        _, memoria = self._osservazione_elise()
        connessione = self.servizio.archivio._connessione
        with self.assertRaises(sqlite3.IntegrityError):
            connessione.execute(
                "UPDATE memories SET content = 'alterata' WHERE memory_id = ?",
                (memoria.memory_id,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            connessione.execute(
                "DELETE FROM memories WHERE memory_id = ?", (memoria.memory_id,)
            )
        with self.assertRaises(sqlite3.IntegrityError):
            connessione.execute(
                "UPDATE memory_entities SET role = 'related' WHERE memory_id = ?",
                (memoria.memory_id,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            connessione.execute(
                "DELETE FROM memory_entities WHERE memory_id = ?",
                (memoria.memory_id,),
            )

    def test_trigger_append_only_memory_sources(self) -> None:
        fonte = self._memoria_importata("akari_mori")
        inferenza = self.servizio.memorie.registra_inferenza(
            self.mondo.id,
            "akari_mori",
            "Inferenza da proteggere.",
            55,
            source_memory_ids=(fonte.memory_id,),
        )
        connessione = self.servizio.archivio._connessione
        with self.assertRaises(sqlite3.IntegrityError):
            connessione.execute(
                "UPDATE memory_sources SET position = 2 WHERE memory_id = ?",
                (inferenza.memory_id,),
            )
        with self.assertRaises(sqlite3.IntegrityError):
            connessione.execute(
                "DELETE FROM memory_sources WHERE memory_id = ?",
                (inferenza.memory_id,),
            )

    def test_validazioni_restituiscono_errori_italiani(self) -> None:
        with self.assertRaisesRegex(ErroreMemoria, "contenuto.*obbligatorio"):
            self.servizio.memorie.registra_inferenza(
                self.mondo.id, "akari_mori", "  ", 50
            )
        with self.assertRaisesRegex(ErroreMemoria, "intero tra 0 e 100"):
            self.servizio.memorie.registra_inferenza(
                self.mondo.id, "akari_mori", "Test", 101
            )
        with self.assertRaisesRegex(ErroreMemoria, "non è un personaggio"):
            self.servizio.memorie.registra_inferenza(
                self.mondo.id, "pen_blue", "Test", 50
            )

    def test_personaggio_evento_e_memoria_fonte_inesistenti(self) -> None:
        with self.assertRaisesRegex(ErroreMemoria, "entità collegata non esiste"):
            self.servizio.memorie.registra_inferenza(
                self.mondo.id, "personaggio_inesistente", "Test", 50
            )
        with self.assertRaisesRegex(ErroreMemoria, "evento richiesto non esiste"):
            self.servizio.memorie.registra_racconto(
                self.mondo.id,
                "akari_mori",
                "elise_moreau",
                "Test",
                50,
                event_id="evento_inesistente",
            )
        with self.assertRaisesRegex(ErroreMemoria, "memoria richiesta non esiste"):
            self.servizio.memorie.registra_inferenza(
                self.mondo.id,
                "akari_mori",
                "Test",
                50,
                source_memory_ids=("memoria_inesistente",),
            )

    def test_racconto_rifiuta_narratore_uguale_all_ascoltatore(self) -> None:
        with self.assertRaisesRegex(ErroreMemoria, "personaggi diversi"):
            self.servizio.memorie.registra_racconto(
                self.mondo.id,
                "akari_mori",
                "akari_mori",
                "Monologo improprio.",
                50,
            )

    def test_elenco_memorie_usa_query_aggregate(self) -> None:
        self._osservazione_elise()
        query: list[str] = []
        connessione = self.servizio.archivio._connessione
        connessione.set_trace_callback(query.append)
        try:
            memorie = self.servizio.memorie.elenca_memorie_personaggio(
                self.mondo.id, "elise_moreau", solo_correnti=False
            )
        finally:
            connessione.set_trace_callback(None)
        selezioni = [
            istruzione
            for istruzione in query
            if istruzione.lstrip().upper().startswith("SELECT")
        ]
        self.assertGreaterEqual(len(memorie), 3)
        self.assertLessEqual(len(selezioni), 5)

    def test_riferimenti_di_altro_mondo_vengono_rifiutati(self) -> None:
        altro = self._importa_altro_mondo()
        evento = self.servizio.stato_mondo.trasferisci_oggetto(
            altro.id, "pen_blue", "luca", reason="Altro mondo"
        )
        with self.assertRaisesRegex(ErroreMemoria, "evento.*non esiste"):
            self.servizio.memorie.registra_racconto(
                self.mondo.id,
                "akari_mori",
                "elise_moreau",
                "Racconto",
                50,
                event_id=evento.event_id,
            )
        with self.assertRaisesRegex(ErroreMemoria, "entità.*non esiste"):
            self.servizio.memorie.registra_inferenza(
                self.mondo.id,
                "akari_mori",
                "Inferenza",
                50,
                entity_ids=("entita_altro_mondo",),
            )

    def test_persistenza_evento_memoria_e_ignoranza_di_akari(self) -> None:
        evento, memoria = self._osservazione_elise()
        self.servizio.chiudi()
        self.servizio = ServizioMondi(self.database)
        eventi = self.servizio.stato_mondo.elenca_eventi(self.mondo.id)
        elise = self.servizio.memorie.elenca_memorie_personaggio(
            self.mondo.id, "elise_moreau", event_id=evento.event_id
        )
        akari = self.servizio.memorie.elenca_memorie_personaggio(
            self.mondo.id, "akari_mori", event_id=evento.event_id
        )
        self.assertEqual([evento.event_id], [voce.event_id for voce in eventi])
        self.assertEqual([memoria.memory_id], [voce.memory_id for voce in elise])
        self.assertEqual([], akari)

    def _memoria_importata(self, character_id: str):
        return self.servizio.memorie.elenca_memorie_personaggio(
            self.mondo.id,
            character_id,
            source_type="imported_background",
        )[0]

    def _numero_memorie(self) -> int:
        return self.servizio.archivio._connessione.execute(
            "SELECT COUNT(*) FROM memories"
        ).fetchone()[0]

    def _conta(self, tabella: str, memory_id: str) -> int:
        return self.servizio.archivio._connessione.execute(
            f"SELECT COUNT(*) FROM {tabella} WHERE memory_id = ?", (memory_id,)
        ).fetchone()[0]

    def _importa_altro_mondo(self):
        altra_sorgente = self.radice / "altro_mondo"
        if altra_sorgente.exists():
            return self.servizio.carica_mondo("altro_mondo")
        shutil.copytree(MINI_BIBBIA, altra_sorgente)
        percorso_mondo = altra_sorgente / "world.json"
        dati = json.loads(percorso_mondo.read_text(encoding="utf-8"))
        dati["id"] = "altro_mondo"
        dati["title"] = "Altro mondo"
        percorso_mondo.write_text(
            json.dumps(dati, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        percorso_oggetti = altra_sorgente / "items.json"
        oggetti = json.loads(percorso_oggetti.read_text(encoding="utf-8"))
        oggetti.append(
            {
                "id": "entita_altro_mondo",
                "name": "Oggetto dell'altro mondo",
                "location_id": "assembly",
                "position": "tavolo",
                "owner_id": None,
                "condition": "intatto",
            }
        )
        percorso_oggetti.write_text(
            json.dumps(oggetti, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return self.servizio.importa_da_cartella(altra_sorgente)


class TestInterfacciaMemorie(unittest.TestCase):
    def test_testi_gui_memorie_sono_italiani(self) -> None:
        self.assertEqual("Memorie dei personaggi", UI_TEXT["memorie_personaggi"])
        self.assertEqual(
            "Cronologia completa", UI_TEXT["cronologia_completa_memorie"]
        )
        self.assertIn("Entità", UI_TEXT["filtra_entita"])

    def test_gui_non_espone_identificatori_o_payload_tecnici(self) -> None:
        sorgente = (RADICE_PROGETTO / "haria_engine" / "app.py").read_text(
            encoding="utf-8"
        )
        intestazioni = {valore.lower() for valore in UI_TEXT.values()}
        self.assertNotIn("memory_id", intestazioni)
        self.assertNotIn("world_id", intestazioni)
        self.assertNotIn("payload", intestazioni)
        self.assertNotIn("memoria.memory_id", sorgente)
