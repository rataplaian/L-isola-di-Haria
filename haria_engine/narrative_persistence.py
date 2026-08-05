"""Piano puro e deterministico per rendere persistente un turno narrativo."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from .narrative_models import MemoriaCandidata, TurnoNarrativoProposto
from .validation_models import (
    EntitaValidazione,
    EsitoSequenza,
    FotografiaValidazioneMondo,
    PropostaCambioStato,
    PropostaEpistemica,
    PropostaEventoDescrittivo,
    PropostaSpostamento,
    PropostaTrasferimento,
    PropostaValidazione,
)

MAX_TESTO_PERSISTITO: Final = 200_000


class ErrorePianoTurno(ValueError):
    """Il turno validato non può essere convertito in una scrittura atomica."""


@dataclass(frozen=True, slots=True)
class TurnoDaPersistire:
    turn_id: str
    session_id: str
    world_id: str
    sequence_number: int
    user_input: str
    narrative: str
    elapsed_minutes: int
    world_time_before: str
    world_time_after: str
    prompt_text: str
    raw_model_output: str
    created_at: str


@dataclass(frozen=True, slots=True)
class AggiornamentoEntitaTurno:
    entity_id: str
    expected_version: int
    final_version: int
    status: str
    location_id: str | None
    holder_id: str | None
    accessibility: bool
    condition: str | None


@dataclass(frozen=True, slots=True)
class EventoTurno:
    event_id: str
    operation_index: int
    event_type: str
    occurred_at: str
    actor_id: str | None
    target_id: str | None
    location_id: str | None
    payload_json: str
    reason: str
    affected_entity_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MemoriaTurno:
    memory_id: str
    memory_index: int
    character_id: str
    event_id: str | None
    knowledge_type: str
    source_type: str
    source_entity_id: str | None
    learned_at: str
    certainty: int
    content: str
    interpretation: str | None
    associated_emotion: str | None
    entity_roles: tuple[tuple[str, str], ...]
    source_memory_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PianoPersistenzaTurno:
    turno: TurnoDaPersistire
    eventi: tuple[EventoTurno, ...]
    aggiornamenti: tuple[AggiornamentoEntitaTurno, ...]
    memorie: tuple[MemoriaTurno, ...]


def crea_id_sessione(world_id: str) -> str:
    return _id_stabile("session", _testo(world_id, "identificatore mondo"))


def crea_id_turno(session_id: str, sequence_number: int) -> str:
    if isinstance(sequence_number, bool) or not isinstance(sequence_number, int) or sequence_number < 1:
        raise ErrorePianoTurno("Il numero progressivo del turno deve essere positivo.")
    return _id_stabile("turn", _testo(session_id, "identificatore sessione"), str(sequence_number))


def crea_piano_persistenza_turno(
    *,
    session_id: str,
    turn_id: str,
    sequence_number: int,
    world_time_before: datetime,
    user_input: str,
    prompt_text: str,
    raw_model_output: str,
    proposta: TurnoNarrativoProposto,
    fotografia_iniziale: FotografiaValidazioneMondo,
    esito_validazione: EsitoSequenza,
    created_at: datetime,
    memory_operation_indices: tuple[int | None, ...] | None = None,
) -> PianoPersistenzaTurno:
    """Costruisce un piano immutabile; non accede a SQLite e non scrive nulla."""

    sessione = _testo(session_id, "identificatore sessione")
    turno_id = _testo(turn_id, "identificatore turno")
    if isinstance(sequence_number, bool) or not isinstance(sequence_number, int) or sequence_number < 1:
        raise ErrorePianoTurno("Il numero progressivo del turno deve essere positivo.")
    prima = _datetime_consapevole(world_time_before, "tempo iniziale del mondo")
    creato = _datetime_consapevole(created_at, "data di creazione")
    input_utente = _testo_limitato(user_input, "azione dell'utente")
    prompt = _testo_limitato(prompt_text, "prompt effettivo")
    output = _testo_limitato(raw_model_output, "output grezzo del modello")
    narrazione = _testo_limitato(proposta.narrative, "narrazione")
    if isinstance(proposta.elapsed_minutes, bool) or not isinstance(proposta.elapsed_minutes, int):
        raise ErrorePianoTurno("Il tempo trascorso deve essere un numero intero.")
    if not 0 <= proposta.elapsed_minutes <= 10_080:
        raise ErrorePianoTurno("Il tempo trascorso non è compreso tra 0 e 10.080 minuti.")
    dopo = prima + timedelta(minutes=proposta.elapsed_minutes)

    _valida_esito(proposta, fotografia_iniziale, esito_validazione)
    world_id = fotografia_iniziale.world_id
    eventi = _crea_eventi(
        sessione,
        turno_id,
        prima,
        dopo,
        proposta.operations,
        fotografia_iniziale,
        esito_validazione,
    )
    aggiornamenti = _crea_aggiornamenti(
        fotografia_iniziale, esito_validazione.fotografia_finale
    )
    indici = _normalizza_indici_memoria(
        memory_operation_indices, len(proposta.memories), len(eventi)
    )
    memorie = _crea_memorie(
        sessione,
        turno_id,
        dopo,
        proposta.memories,
        eventi,
        indici,
    )
    turno = TurnoDaPersistire(
        turn_id=turno_id,
        session_id=sessione,
        world_id=world_id,
        sequence_number=sequence_number,
        user_input=input_utente,
        narrative=narrazione,
        elapsed_minutes=proposta.elapsed_minutes,
        world_time_before=_iso(prima),
        world_time_after=_iso(dopo),
        prompt_text=prompt,
        raw_model_output=output,
        created_at=_iso(creato),
    )
    return PianoPersistenzaTurno(turno, eventi, aggiornamenti, memorie)


def _valida_esito(
    proposta: TurnoNarrativoProposto,
    iniziale: FotografiaValidazioneMondo,
    esito: EsitoSequenza,
) -> None:
    if not esito.superata:
        raise ErrorePianoTurno("Una proposta non valida non può essere resa persistente.")
    if iniziale.world_id != esito.fotografia_finale.world_id:
        raise ErrorePianoTurno("La fotografia finale appartiene a un altro mondo.")
    if len(esito.esiti) != len(proposta.operations):
        raise ErrorePianoTurno("L'esito non contiene una voce per ogni operazione.")
    for indice, (operazione, voce) in enumerate(zip(proposta.operations, esito.esiti)):
        if voce.indice != indice or voce.proposta != operazione or not voce.valida:
            raise ErrorePianoTurno("L'esito validato non corrisponde alle operazioni proposte.")
        if voce.fotografia.world_id != iniziale.world_id:
            raise ErrorePianoTurno("Una proiezione intermedia appartiene a un altro mondo.")


def _crea_eventi(
    session_id: str,
    turn_id: str,
    world_time_before: datetime,
    world_time_after: datetime,
    operazioni: tuple[PropostaValidazione, ...],
    fotografia_iniziale: FotografiaValidazioneMondo,
    esito: EsitoSequenza,
) -> tuple[EventoTurno, ...]:
    eventi: list[EventoTurno] = []
    precedente = fotografia_iniziale
    ultimo_istante = world_time_before
    for indice, (operazione, voce) in enumerate(zip(operazioni, esito.esiti)):
        istante = _istante_operazione(operazione, world_time_after)
        if istante < world_time_before or istante > world_time_after:
            raise ErrorePianoTurno(
                "L'istante di un'operazione deve rientrare nel turno corrente."
            )
        if istante < ultimo_istante:
            raise ErrorePianoTurno("Gli istanti delle operazioni non sono in ordine.")
        ultimo_istante = istante
        corrente = voce.fotografia
        cambiati = _entita_cambiate(precedente, corrente)
        tipo, attore, bersaglio, luogo, payload, motivo = _descrivi_operazione(
            operazione, precedente, corrente
        )
        eventi.append(
            EventoTurno(
                event_id=_id_stabile("event", session_id, turn_id, str(indice)),
                operation_index=indice,
                event_type=tipo,
                occurred_at=_iso(istante),
                actor_id=attore,
                target_id=bersaglio,
                location_id=luogo,
                payload_json=json.dumps(
                    payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ),
                reason=_testo(motivo, "motivo operazione"),
                affected_entity_ids=cambiati,
            )
        )
        precedente = corrente
    return tuple(eventi)


def _descrivi_operazione(
    proposta: PropostaValidazione,
    prima: FotografiaValidazioneMondo,
    dopo: FotografiaValidazioneMondo,
) -> tuple[str, str | None, str | None, str | None, dict[str, object], str]:
    iniziali = {voce.entity_id: voce for voce in prima.entita}
    finali = {voce.entity_id: voce for voce in dopo.entita}
    if isinstance(proposta, PropostaSpostamento):
        entita = iniziali[proposta.entity_id]
        return (
            "spostamento_entita",
            proposta.actor_id,
            proposta.entity_id,
            proposta.location_id,
            {
                "location_id_precedente": entita.location_id,
                "location_id_nuova": proposta.location_id,
                "memory_ids": list(proposta.memory_ids),
            },
            proposta.reason,
        )
    if isinstance(proposta, PropostaTrasferimento):
        oggetto = iniziali[proposta.object_id]
        possessore = finali[proposta.holder_id]
        return (
            "trasferimento_oggetto",
            proposta.actor_id or proposta.holder_id,
            proposta.object_id,
            possessore.location_id,
            {
                "holder_id_precedente": oggetto.holder_id,
                "holder_id_nuovo": proposta.holder_id,
                "location_id": possessore.location_id,
                "memory_ids": list(proposta.memory_ids),
            },
            proposta.reason,
        )
    if isinstance(proposta, PropostaCambioStato):
        vecchia = iniziali[proposta.target_id]
        nuova = finali[proposta.target_id]
        return (
            "cambio_stato",
            proposta.actor_id,
            proposta.target_id,
            nuova.location_id,
            {
                "status_precedente": vecchia.status,
                "status": nuova.status,
                "condition_precedente": vecchia.condition,
                "condition": nuova.condition,
                "accessibility_precedente": vecchia.accessibility,
                "accessibility": nuova.accessibility,
                "memory_ids": list(proposta.memory_ids),
            },
            proposta.reason,
        )
    if isinstance(proposta, PropostaEventoDescrittivo):
        return (
            proposta.event_type,
            proposta.actor_id,
            proposta.target_id,
            proposta.location_id,
            {"memory_ids": list(proposta.memory_ids)},
            proposta.reason,
        )
    if isinstance(proposta, PropostaEpistemica):
        return (
            "evento_epistemico",
            proposta.actor_id,
            proposta.target_id,
            proposta.location_id,
            {"memory_ids": list(proposta.memory_ids)},
            proposta.reason,
        )
    raise ErrorePianoTurno("Il tipo di operazione non è supportato.")


def _crea_aggiornamenti(
    iniziale: FotografiaValidazioneMondo,
    finale: FotografiaValidazioneMondo,
) -> tuple[AggiornamentoEntitaTurno, ...]:
    prima = {voce.entity_id: voce for voce in iniziale.entita}
    dopo = {voce.entity_id: voce for voce in finale.entita}
    if set(prima) != set(dopo):
        raise ErrorePianoTurno("Le operazioni non possono creare o eliminare entità.")
    risultato: list[AggiornamentoEntitaTurno] = []
    for entity_id in sorted(prima):
        vecchia = prima[entity_id]
        nuova = dopo[entity_id]
        if _stato_entita(vecchia) == _stato_entita(nuova):
            if vecchia.version != nuova.version:
                raise ErrorePianoTurno("Una versione è cambiata senza modificare lo stato.")
            continue
        if nuova.version <= vecchia.version:
            raise ErrorePianoTurno("La versione finale di uno stato non è avanzata.")
        risultato.append(
            AggiornamentoEntitaTurno(
                entity_id=entity_id,
                expected_version=vecchia.version,
                final_version=nuova.version,
                status=nuova.status,
                location_id=nuova.location_id,
                holder_id=nuova.holder_id,
                accessibility=nuova.accessibility,
                condition=nuova.condition,
            )
        )
    return tuple(risultato)


def _crea_memorie(
    session_id: str,
    turn_id: str,
    world_time_after: datetime,
    candidate: tuple[MemoriaCandidata, ...],
    eventi: tuple[EventoTurno, ...],
    operation_indices: tuple[int | None, ...],
) -> tuple[MemoriaTurno, ...]:
    risultato: list[MemoriaTurno] = []
    for indice, (memoria, operation_index) in enumerate(zip(candidate, operation_indices)):
        evento = None if operation_index is None else eventi[operation_index]
        associazioni = tuple(
            sorted((voce.entity_id, voce.role) for voce in memoria.entities)
        )
        risultato.append(
            MemoriaTurno(
                memory_id=_id_stabile("memory", session_id, turn_id, str(indice)),
                memory_index=indice,
                character_id=memoria.character_id,
                event_id=None if evento is None else evento.event_id,
                knowledge_type=memoria.knowledge_type,
                source_type=memoria.source_type,
                source_entity_id=memoria.source_entity_id,
                learned_at=(
                    _iso(world_time_after) if evento is None else evento.occurred_at
                ),
                certainty=memoria.certainty,
                content=memoria.content,
                interpretation=memoria.interpretation,
                associated_emotion=memoria.associated_emotion,
                entity_roles=associazioni,
                source_memory_ids=tuple(memoria.source_memory_ids),
            )
        )
    return tuple(risultato)


def _normalizza_indici_memoria(
    valori: tuple[int | None, ...] | None,
    numero_memorie: int,
    numero_eventi: int,
) -> tuple[int | None, ...]:
    if valori is None:
        return (None,) * numero_memorie
    if len(valori) != numero_memorie:
        raise ErrorePianoTurno("Serve un collegamento evento per ogni memoria candidata.")
    risultato: list[int | None] = []
    for valore in valori:
        if valore is None:
            risultato.append(None)
            continue
        if isinstance(valore, bool) or not isinstance(valore, int):
            raise ErrorePianoTurno("L'indice evento di una memoria deve essere intero.")
        if not 0 <= valore < numero_eventi:
            raise ErrorePianoTurno("Una memoria fa riferimento a un'operazione inesistente.")
        risultato.append(valore)
    return tuple(risultato)


def _entita_cambiate(
    prima: FotografiaValidazioneMondo,
    dopo: FotografiaValidazioneMondo,
) -> tuple[str, ...]:
    iniziali = {voce.entity_id: voce for voce in prima.entita}
    finali = {voce.entity_id: voce for voce in dopo.entita}
    return tuple(
        sorted(
            entity_id
            for entity_id in iniziali.keys() & finali.keys()
            if _stato_entita(iniziali[entity_id]) != _stato_entita(finali[entity_id])
        )
    )


def _stato_entita(voce: EntitaValidazione) -> tuple[object, ...]:
    return (
        voce.status,
        voce.location_id,
        voce.holder_id,
        voce.accessibility,
        voce.condition,
    )


def _istante_operazione(
    proposta: PropostaValidazione, predefinito: datetime
) -> datetime:
    valore = proposta.occurred_at
    if valore is None:
        return predefinito
    try:
        istante = datetime.fromisoformat(valore)
    except ValueError as errore:
        raise ErrorePianoTurno("L'istante di un'operazione non è ISO-8601 valido.") from errore
    return _datetime_consapevole(istante, "istante operazione")


def _datetime_consapevole(valore: datetime, descrizione: str) -> datetime:
    if not isinstance(valore, datetime) or valore.tzinfo is None or valore.utcoffset() is None:
        raise ErrorePianoTurno(f"Il campo {descrizione} deve includere il fuso orario.")
    return valore


def _iso(valore: datetime) -> str:
    return valore.isoformat(timespec="microseconds")


def _testo(valore: str, descrizione: str) -> str:
    if not isinstance(valore, str) or not valore.strip():
        raise ErrorePianoTurno(f"Il campo {descrizione} è obbligatorio.")
    return valore.strip()


def _testo_limitato(valore: str, descrizione: str) -> str:
    testo = _testo(valore, descrizione)
    if len(testo) > MAX_TESTO_PERSISTITO:
        raise ErrorePianoTurno(f"Il campo {descrizione} supera il limite persistibile.")
    return testo


def _id_stabile(prefisso: str, *parti: str) -> str:
    impronta = hashlib.sha256("\x00".join(parti).encode("utf-8")).hexdigest()
    return f"{prefisso}_{impronta}"
