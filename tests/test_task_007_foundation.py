from __future__ import annotations

import dataclasses
import json
import unittest

from haria_engine.narrative_models import TurnoNarrativoProposto
from haria_engine.narrative_parser import (
    ErroreOutputNarrativo,
    parse_output_narrativo,
)
from haria_engine.narrative_prompt import (
    ContestoTurnoNarrativo,
    costruisci_messaggi_turno,
    formatta_prompt_visibile,
)
from haria_engine.validation_models import (
    PropostaCambioStato,
    PropostaEpistemica,
    PropostaEventoDescrittivo,
    PropostaSpostamento,
    PropostaTrasferimento,
)


def output_valido() -> dict[str, object]:
    return {
        "narrative": "Mara osserva il sentiero e attende la risposta di Luca.",
        "elapsed_minutes": 4,
        "operations": [
            {
                "type": "move",
                "entity_id": "mara",
                "location_id": "baia",
                "actor_id": "mara",
                "reason": "Mara raggiunge la baia.",
                "memory_ids": [],
            },
            {
                "type": "transfer",
                "object_id": "coltello",
                "holder_id": "mara",
                "reason": "Mara raccoglie il coltello.",
            },
            {
                "type": "state_change",
                "target_id": "porta",
                "accessibility": False,
                "reason": "La porta viene chiusa.",
            },
            {
                "type": "event",
                "event_type": "rumore_lontano",
                "location_id": "foresta",
                "reason": "Un ramo si spezza nella foresta.",
            },
            {
                "type": "epistemic",
                "actor_id": "mara",
                "target_id": "foresta",
                "reason": "Mara nota il rumore.",
            },
        ],
        "memories": [
            {
                "character_id": "mara",
                "knowledge_type": "observed_fact",
                "source_type": "direct_observation",
                "source_entity_id": None,
                "certainty": 95,
                "content": "Un rumore Ã¨ arrivato dalla foresta.",
                "interpretation": "Qualcuno potrebbe essere vicino.",
                "associated_emotion": "allerta",
                "entities": [
                    {"entity_id": "foresta", "role": "location"},
                ],
                "source_memory_ids": [],
            }
        ],
    }


class TestParserNarrativo(unittest.TestCase):
    def test_output_completo_diventa_modelli_immutabili(self) -> None:
        turno = parse_output_narrativo(
            json.dumps(output_valido(), ensure_ascii=False)
        )

        self.assertIsInstance(turno, TurnoNarrativoProposto)
        self.assertEqual(4, turno.elapsed_minutes)
        self.assertEqual(
            (
                PropostaSpostamento,
                PropostaTrasferimento,
                PropostaCambioStato,
                PropostaEventoDescrittivo,
                PropostaEpistemica,
            ),
            tuple(type(voce) for voce in turno.operations),
        )
        self.assertEqual("mara", turno.memories[0].character_id)
        self.assertEqual("location", turno.memories[0].entities[0].role)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            turno.elapsed_minutes = 5  # type: ignore[misc]

    def test_rifiuta_markdown_o_testo_fuori_dal_json(self) -> None:
        testo = "```json\n" + json.dumps(output_valido()) + "\n```"
        with self.assertRaisesRegex(
            ErroreOutputNarrativo, "singolo oggetto JSON"
        ):
            parse_output_narrativo(testo)

    def test_rifiuta_chiavi_principali_mancanti_o_sconosciute(self) -> None:
        for modifica in ("mancante", "sconosciuta"):
            dati = output_valido()
            if modifica == "mancante":
                dati.pop("memories")
            else:
                dati["debug"] = True
            with self.subTest(modifica=modifica), self.assertRaises(
                ErroreOutputNarrativo
            ):
                parse_output_narrativo(json.dumps(dati))

    def test_rifiuta_tipo_operazione_sconosciuto(self) -> None:
        dati = output_valido()
        dati["operations"] = [
            {"type": "teleport", "reason": "Operazione non supportata."}
        ]
        with self.assertRaisesRegex(ErroreOutputNarrativo, "non Ã¨ supportato"):
            parse_output_narrativo(json.dumps(dati))

    def test_cambio_stato_deve_modificare_un_campo(self) -> None:
        dati = output_valido()
        dati["operations"] = [
            {
                "type": "state_change",
                "target_id": "mara",
                "reason": "Nessuna modifica.",
            }
        ]
        with self.assertRaisesRegex(
            ErroreOutputNarrativo, "almeno un campo"
        ):
            parse_output_narrativo(json.dumps(dati))

    def test_bool_non_viene_accettato_come_numero(self) -> None:
        dati = output_valido()
        dati["elapsed_minutes"] = True
        with self.assertRaisesRegex(ErroreOutputNarrativo, "numero intero"):
            parse_output_narrativo(json.dumps(dati))

    def test_memoria_usa_vocabolari_esistenti(self) -> None:
        for campo, valore in (
            ("knowledge_type", "telepatia"),
            ("source_type", "sogno_magico"),
        ):
            dati = output_valido()
            assert isinstance(dati["memories"], list)
            dati["memories"][0][campo] = valore
            with self.subTest(campo=campo), self.assertRaisesRegex(
                ErroreOutputNarrativo, "non Ã¨ supportato"
            ):
                parse_output_narrativo(json.dumps(dati))

    def test_rifiuta_associazioni_memoria_duplicate(self) -> None:
        dati = output_valido()
        assert isinstance(dati["memories"], list)
        dati["memories"][0]["entities"] = [
            {"entity_id": "foresta", "role": "location"},
            {"entity_id": "foresta", "role": "location"},
        ]
        with self.assertRaisesRegex(ErroreOutputNarrativo, "duplicata"):
            parse_output_narrativo(json.dumps(dati))


class TestPromptNarrativo(unittest.TestCase):
    def contesto(self) -> ContestoTurnoNarrativo:
        return ContestoTurnoNarrativo(
            world_title="L'isola di Haria",
            player_name="Luca",
            user_input="Guardo Mara senza parlare.",
            scenario="Una comunitÃ  sopravvive su un'isola.",
            rules="Le NPC sono autonome.",
            style="Prima persona, ritmo quotidiano.",
            author_note="Non accelerare le relazioni.",
            world_state="Mara Ã¨ alla baia. Luca Ã¨ vicino alla riva.",
            characters=("mara â€” Mara Voss â€” baia",),
            relevant_memories=("mara ricorda l'arrivo di Luca",),
            recent_history=("Mara ha chiesto il nome di Luca.",),
        )

    def test_prompt_impedisce_di_controllare_luca(self) -> None:
        messaggi = costruisci_messaggi_turno(self.contesto())
        sistema = messaggi[0].contenuto

        self.assertIn("Non decidere pensieri, consenso", sistema)
        self.assertIn("Non scrivere battute di Luca", sistema)
        self.assertIn("Le NPC hanno volontÃ ", sistema)
        self.assertIn("un unico oggetto JSON", sistema)

    def test_prompt_mostra_esattamente_messaggi_e_input(self) -> None:
        messaggi = costruisci_messaggi_turno(self.contesto())
        visibile = formatta_prompt_visibile(messaggi)

        self.assertIn("===== SYSTEM =====", visibile)
        self.assertIn("===== USER =====", visibile)
        self.assertIn("Guardo Mara senza parlare.", visibile)
        self.assertIn("Mara Ã¨ alla baia.", visibile)

    def test_prompt_e_deterministico(self) -> None:
        prima = costruisci_messaggi_turno(self.contesto())
        seconda = costruisci_messaggi_turno(self.contesto())
        self.assertEqual(prima, seconda)

    def test_contesto_obbligatorio_viene_validato(self) -> None:
        with self.assertRaisesRegex(ValueError, "azione dell'utente"):
            costruisci_messaggi_turno(
                ContestoTurnoNarrativo(
                    world_title="Haria",
                    player_name="Luca",
                    user_input=" ",
                    scenario="Scenario",
                )
            )


if __name__ == "__main__":
    unittest.main()