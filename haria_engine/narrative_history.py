"""Modelli tipizzati della cronologia narrativa persistente."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessioneNarrativa:
    session_id: str
    world_id: str
    current_time: str
    next_turn_number: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class TurnoNarrativoPersistito:
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
class PartitaNarrativa:
    sessione: SessioneNarrativa
    turni: tuple[TurnoNarrativoPersistito, ...]
