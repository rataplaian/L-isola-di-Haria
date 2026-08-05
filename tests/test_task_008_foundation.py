from __future__ import annotations

import json
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

from haria_engine.narrative_models import (
    AssociazioneMemoriaCandidata,
    MemoriaCandidata,
    TurnoNarrativoProposto,
)
from haria_engine.narrative_persistence import (
    ErrorePianoTurno,
    crea_id_sessione,
    crea_id_turno,
    crea_piano_persistenza_turno,
)
from haria_engine.validation_models import (
    EntitaValidazione,
    EsitoProposta,
    EsitoSequenza,
    FotografiaValidazioneMondo,
    PropostaCambioStato,
    PropostaEventoDescrittivo,
    PropostaSpostamento,
    RapportoValidazione,
)

UTC = timezone.utc
BASE_TIME = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)


def entita(
    entity_id: str,
    tipo: str,
    *,
    location_id: str | None = None,
    holder_id: str | None = None,
    status: str = "active",
    condition: str | None = None,
    accessibility: bool = True,
    version: int = 1,
) -> EntitaValidazione:
    return EntitaValidazione(
        world_id="haria",
        entity_id=entity_id,
        entity_type=tipo,
        canonical_name=entity_id.title(),
        status=status,
        location_id=location_id,
        holder_id=holder_id,
        accessibility=accessibility,
        condition=condition,
        version=version,
        updated_at=BASE_TIME.isoformat(),
    )


def foto(*voci: EntitaValidazione) -> FotografiaValidazioneMondo:
    return FotografiaValidazioneMondo("haria", tuple(voci), (), ())


def esito(
    operazioni,
    fotografie,
    *,
    valido: bool = True,
) -> EsitoSequenza:
    rapporto = RapportoValidazione(())
    esiti = tuple(
        EsitoProposta(indice, operazione, rapporto, fotografia)
        for indice, (operazione, fotografia) in enumerate(zip(operazioni, fotografie))
    )
    if valido:
        finale = fotografie[-1] if fotografie else foto()
        return EsitoSequenza(esiti, rapporto, finale)
    from haria_engine.validation_models import (
        AmbitoValidazione,
        ProblemaValidazione,
        SeveritaProblema,
    )
    errore = ProblemaValidazione(
        "errore", SeveritaProblema.ERRORE, AmbitoValidazione.INTEGRITA, "errore"
    )
    return EsitoSequenza(esiti, RapportoValidazione((errore,)), fotografie[-1])


def proposta_base(operations=(), memories=(), elapsed=5):
    return TurnoNarrativoProposto(
        "La scena continua.", elapsed, tuple(operations), tuple(memories)
    )


def crea_piano(proposta, iniziale, risultato, **extra):
    return crea_piano_persistenza_turno(
        session_id=crea_id_sessione("haria"),
        turn_id=crea_id_turno(crea_id_sessione("haria"), 1),
        sequence_number=1,
        world_time_before=BASE_TIME,
        user_input="Osservo il campo.",
        prompt_text="Prompt effettivo",
        raw_model_output='{"narrative":"La scena continua."}',
        proposta=proposta,
        fotografia_iniziale=iniziale,
        esito_validazione=risultato,
        created_at=BASE_TIME,
        **extra,
    )


class TestTask008Foundation(unittest.TestCase):
    def test_identificatori_sono_stabili_e_separati(self) -> None:
        sessione = crea_id_sessione("haria")
        self.assertEqual(sessione, crea_id_sessione("haria"))
        self.assertNotEqual(sessione, crea_id_sessione("altro"))
        self.assertEqual(crea_id_turno(sessione, 2), crea_id_turno(sessione, 2))
        self.assertNotEqual(crea_id_turno(sessione, 1), crea_id_turno(sessione, 2))

    def test_turno_senza_operazioni_avanza_il_tempo(self) -> None:
        iniziale = foto(entita("campo", "luogo"))
        proposta = proposta_base(elapsed=17)
        piano = crea_piano(proposta, iniziale, EsitoSequenza((), RapportoValidazione(()), iniziale))
        self.assertEqual(17, piano.turno.elapsed_minutes)
        self.assertEqual(
            (BASE_TIME + timedelta(minutes=17)).isoformat(timespec="microseconds"),
            piano.turno.world_time_after,
        )
        self.assertEqual((), piano.eventi)
        self.assertEqual((), piano.aggiornamenti)

    def test_spostamento_crea_evento_e_aggiornamenti_aggregati(self) -> None:
        luca = entita("luca", "personaggio", location_id="spiaggia")
        zaino = entita("zaino", "oggetto", location_id="spiaggia", holder_id="luca")
        spiaggia = entita("spiaggia", "luogo")
        campo = entita("campo", "luogo")
        iniziale = foto(luca, zaino, spiaggia, campo)
        finale = foto(
            replace(luca, location_id="campo", version=2),
            replace(zaino, location_id="campo", version=2),
            spiaggia,
            campo,
        )
        operazione = PropostaSpostamento("luca", "campo", reason="Luca raggiunge il campo")
        proposta = proposta_base((operazione,))
        piano = crea_piano(proposta, iniziale, esito((operazione,), (finale,)))
        self.assertEqual("spostamento_entita", piano.eventi[0].event_type)
        self.assertEqual(("luca", "zaino"), piano.eventi[0].affected_entity_ids)
        self.assertEqual(("luca", "zaino"), tuple(a.entity_id for a in piano.aggiornamenti))
        self.assertEqual("campo", piano.aggiornamenti[0].location_id)

    def test_due_modifiche_stessa_entita_diventano_un_update_finale(self) -> None:
        luca = entita("luca", "personaggio", location_id="campo")
        campo = entita("campo", "luogo")
        iniziale = foto(luca, campo)
        prima = foto(replace(luca, condition="ferito", version=2), campo)
        finale = foto(replace(luca, condition="ferito", status="stanco", version=3), campo)
        op1 = PropostaCambioStato("luca", condition="ferito", reason="Ferita")
        op2 = PropostaCambioStato("luca", status="stanco", reason="Stanchezza")
        proposta = proposta_base((op1, op2))
        piano = crea_piano(proposta, iniziale, esito((op1, op2), (prima, finale)))
        self.assertEqual(2, len(piano.eventi))
        self.assertEqual(1, len(piano.aggiornamenti))
        self.assertEqual(1, piano.aggiornamenti[0].expected_version)
        self.assertEqual(3, piano.aggiornamenti[0].final_version)

    def test_evento_descrittivo_non_modifica_stato(self) -> None:
        luca = entita("luca", "personaggio", location_id="campo")
        campo = entita("campo", "luogo")
        iniziale = foto(luca, campo)
        op = PropostaEventoDescrittivo(
            "temporale", actor_id="luca", location_id="campo", reason="Inizia a piovere"
        )
        piano = crea_piano(proposta_base((op,)), iniziale, esito((op,), (iniziale,)))
        self.assertEqual("temporale", piano.eventi[0].event_type)
        self.assertEqual((), piano.aggiornamenti)

    def test_memoria_puo_collegarsi_all_evento_generato(self) -> None:
        luca = entita("luca", "personaggio", location_id="campo")
        campo = entita("campo", "luogo")
        iniziale = foto(luca, campo)
        op = PropostaEventoDescrittivo("scoperta", target_id="campo", reason="Segno inciso")
        memoria = MemoriaCandidata(
            "luca",
            "observed_fact",
            "direct_observation",
            None,
            95,
            "Nel campo esiste un segno inciso.",
            None,
            "curiosità",
            (AssociazioneMemoriaCandidata("campo", "location"),),
            (),
        )
        proposta = proposta_base((op,), (memoria,))
        piano = crea_piano(
            proposta,
            iniziale,
            esito((op,), (iniziale,)),
            memory_operation_indices=(0,),
        )
        self.assertEqual(piano.eventi[0].event_id, piano.memorie[0].event_id)
        self.assertEqual((("campo", "location"),), piano.memorie[0].entity_roles)
        self.assertEqual(piano.eventi[0].occurred_at, piano.memorie[0].learned_at)

    def test_memoria_senza_collegamento_resta_valida(self) -> None:
        iniziale = foto(entita("luca", "personaggio", location_id="campo"), entita("campo", "luogo"))
        memoria = MemoriaCandidata(
            "luca", "belief", "self_experience", None, 60, "Il luogo sembra sicuro.", None, None
        )
        proposta = proposta_base(memories=(memoria,))
        piano = crea_piano(
            proposta,
            iniziale,
            EsitoSequenza((), RapportoValidazione(()), iniziale),
        )
        self.assertIsNone(piano.memorie[0].event_id)
        self.assertEqual(piano.turno.world_time_after, piano.memorie[0].learned_at)

    def test_indice_memoria_inesistente_viene_rifiutato(self) -> None:
        iniziale = foto(entita("luca", "personaggio", location_id="campo"), entita("campo", "luogo"))
        memoria = MemoriaCandidata(
            "luca", "belief", "self_experience", None, 60, "Ricordo.", None, None
        )
        proposta = proposta_base(memories=(memoria,))
        risultato = EsitoSequenza((), RapportoValidazione(()), iniziale)
        with self.assertRaisesRegex(ErrorePianoTurno, "inesistente"):
            crea_piano(proposta, iniziale, risultato, memory_operation_indices=(0,))

    def test_istante_esplicito_deve_rientrare_nel_turno(self) -> None:
        iniziale = foto(entita("campo", "luogo"))
        op = PropostaEventoDescrittivo(
            "evento",
            occurred_at=(BASE_TIME + timedelta(minutes=6)).isoformat(),
            reason="Troppo tardi",
        )
        with self.assertRaisesRegex(ErrorePianoTurno, "rientrare"):
            crea_piano(proposta_base((op,), elapsed=5), iniziale, esito((op,), (iniziale,)))

    def test_operazioni_fuori_ordine_temporale_vengono_rifiutate(self) -> None:
        iniziale = foto(entita("campo", "luogo"))
        op1 = PropostaEventoDescrittivo(
            "uno", occurred_at=(BASE_TIME + timedelta(minutes=4)).isoformat(), reason="Uno"
        )
        op2 = PropostaEventoDescrittivo(
            "due", occurred_at=(BASE_TIME + timedelta(minutes=2)).isoformat(), reason="Due"
        )
        with self.assertRaisesRegex(ErrorePianoTurno, "ordine"):
            crea_piano(
                proposta_base((op1, op2), elapsed=5),
                iniziale,
                esito((op1, op2), (iniziale, iniziale)),
            )

    def test_esito_non_valido_non_puo_essere_persistito(self) -> None:
        iniziale = foto(entita("campo", "luogo"))
        op = PropostaEventoDescrittivo("evento", reason="Errore")
        with self.assertRaisesRegex(ErrorePianoTurno, "non valida"):
            crea_piano(proposta_base((op,)), iniziale, esito((op,), (iniziale,), valido=False))

    def test_payload_json_e_deterministico(self) -> None:
        iniziale = foto(entita("campo", "luogo"))
        op = PropostaEventoDescrittivo("evento", reason="Determinismo", memory_ids=("b", "a"))
        proposta = proposta_base((op,))
        primo = crea_piano(proposta, iniziale, esito((op,), (iniziale,)))
        secondo = crea_piano(proposta, iniziale, esito((op,), (iniziale,)))
        self.assertEqual(primo.eventi[0].event_id, secondo.eventi[0].event_id)
        self.assertEqual(primo.eventi[0].payload_json, secondo.eventi[0].payload_json)
        self.assertEqual({"memory_ids": ["b", "a"]}, json.loads(primo.eventi[0].payload_json))

    def test_modelli_del_piano_sono_immutabili(self) -> None:
        iniziale = foto(entita("campo", "luogo"))
        piano = crea_piano(
            proposta_base(), iniziale, EsitoSequenza((), RapportoValidazione(()), iniziale)
        )
        with self.assertRaises(FrozenInstanceError):
            piano.turno.sequence_number = 2

    def test_datetime_senza_fuso_viene_rifiutato(self) -> None:
        iniziale = foto(entita("campo", "luogo"))
        proposta = proposta_base()
        risultato = EsitoSequenza((), RapportoValidazione(()), iniziale)
        with self.assertRaisesRegex(ErrorePianoTurno, "fuso orario"):
            crea_piano_persistenza_turno(
                session_id="sessione",
                turn_id="turno",
                sequence_number=1,
                world_time_before=datetime(2026, 1, 1, 8, 0),
                user_input="Azione",
                prompt_text="Prompt",
                raw_model_output="Output",
                proposta=proposta,
                fotografia_iniziale=iniziale,
                esito_validazione=risultato,
                created_at=BASE_TIME,
            )


if __name__ == "__main__":
    unittest.main()
