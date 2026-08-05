"""Modelli puri per un turno narrativo proposto dal modello locale."""

from __future__ import annotations

from dataclasses import dataclass

from .validation_models import PropostaValidazione


@dataclass(frozen=True, slots=True)
class AssociazioneMemoriaCandidata:
    """Entità citata da una memoria candidata e relativo ruolo."""

    entity_id: str
    role: str


@dataclass(frozen=True, slots=True)
class MemoriaCandidata:
    """Memoria proposta dall'LLM, non ancora applicata al database."""

    character_id: str
    knowledge_type: str
    source_type: str
    source_entity_id: str | None
    certainty: int
    content: str
    interpretation: str | None
    associated_emotion: str | None
    entities: tuple[AssociazioneMemoriaCandidata, ...] = ()
    source_memory_ids: tuple[str, ...] = ()
    operation_index: int | None = None


@dataclass(frozen=True, slots=True)
class TurnoNarrativoProposto:
    """Risposta strutturata completa, ancora priva di effetti persistenti."""

    narrative: str
    elapsed_minutes: int
    operations: tuple[PropostaValidazione, ...]
    memories: tuple[MemoriaCandidata, ...]
