"""Contratto JSON immutabile condiviso da prompt e provider narrativo."""

from __future__ import annotations

import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, cast


MAX_NARRATIVE_CHARS: Final = 20_000
MAX_OPERATIONS: Final = 50
MAX_MEMORIES: Final = 50
MAX_MEMORY_CONTENT_CHARS: Final = 4_000
MAX_ELAPSED_MINUTES: Final = 10_080


def _testo(max_length: int) -> dict[str, object]:
    return {
        "type": "string",
        "minLength": 1,
        "maxLength": max_length,
    }


def _testo_o_null(max_length: int) -> dict[str, object]:
    return {
        "anyOf": (_testo(max_length), {"type": "null"}),
    }


def _id() -> dict[str, object]:
    return _testo(200)


def _id_o_null() -> dict[str, object]:
    return {"anyOf": (_id(), {"type": "null"})}


def _lista_id(*, min_items: int = 0, max_items: int | None = None) -> dict[str, object]:
    schema: dict[str, object] = {
        "type": "array",
        "items": _id(),
        "minItems": min_items,
        "uniqueItems": True,
    }
    if max_items is not None:
        schema["maxItems"] = max_items
    return schema


def _proprieta_operazione(tipo: str) -> dict[str, object]:
    return {
        "type": {"const": tipo},
        "actor_id": _id_o_null(),
        "occurred_at": _testo_o_null(1_000),
        "memory_ids": _lista_id(),
        "reason": _testo(1_000),
    }


def _operazione(
    tipo: str,
    obbligatorie: tuple[str, ...],
    specifiche: Mapping[str, object],
    *,
    vincoli: tuple[Mapping[str, object], ...] = (),
) -> dict[str, object]:
    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {**_proprieta_operazione(tipo), **specifiche},
        "required": ("type", "reason", *obbligatorie),
    }
    if vincoli:
        schema["allOf"] = vincoli
    return schema


ENTITA_MEMORIA_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "entity_id": _id(),
        "role": {"enum": ("subject", "source", "location", "related")},
    },
    "required": ("entity_id", "role"),
}


def _proprieta_memoria() -> dict[str, object]:
    return {
        "character_id": _id(),
        "knowledge_type": {"type": "string"},
        "source_type": {"type": "string"},
        "source_entity_id": _id_o_null(),
        "certainty": {"type": "integer", "minimum": 0, "maximum": 100},
        "content": _testo(MAX_MEMORY_CONTENT_CHARS),
        "interpretation": _testo_o_null(2_000),
        "associated_emotion": _testo_o_null(500),
        "operation_index": {
            "anyOf": (
                {"type": "integer", "minimum": 0, "maximum": MAX_OPERATIONS - 1},
                {"type": "null"},
            )
        },
        "entities": {
            "type": "array",
            "items": ENTITA_MEMORIA_SCHEMA,
        },
        "source_memory_ids": _lista_id(),
    }


def _memoria(
    source_type: str,
    knowledge_type: Mapping[str, object],
    *,
    obbligatorie: tuple[str, ...] = (),
    specifiche: Mapping[str, object] | None = None,
    escluse: tuple[str, ...] = (),
) -> dict[str, object]:
    proprieta = _proprieta_memoria()
    for chiave in escluse:
        proprieta.pop(chiave)
    proprieta.update(
        {
            "source_type": {"const": source_type},
            "knowledge_type": dict(knowledge_type),
            **dict(specifiche or {}),
        }
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": proprieta,
        "required": (
            "character_id",
            "knowledge_type",
            "source_type",
            "certainty",
            "content",
            *obbligatorie,
        ),
    }


_SCHEMA_MUTABILE: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "narrative": _testo(MAX_NARRATIVE_CHARS),
        "elapsed_minutes": {
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_ELAPSED_MINUTES,
        },
        "operations": {
            "type": "array",
            "maxItems": MAX_OPERATIONS,
            "items": {
                "oneOf": (
                    _operazione(
                        "move",
                        ("entity_id", "location_id"),
                        {"entity_id": _id(), "location_id": _id()},
                    ),
                    _operazione(
                        "transfer",
                        ("object_id", "holder_id"),
                        {"object_id": _id(), "holder_id": _id()},
                    ),
                    _operazione(
                        "state_change",
                        ("target_id",),
                        {
                            "target_id": _id(),
                            "status": _testo_o_null(1_000),
                            "condition": _testo_o_null(1_000),
                            "accessibility": {
                                "type": ("boolean", "null"),
                            },
                        },
                        vincoli=(
                            {
                                "anyOf": (
                                    {
                                        "required": ("status",),
                                        "properties": {"status": _testo(1_000)},
                                    },
                                    {
                                        "required": ("condition",),
                                        "properties": {"condition": _testo(1_000)},
                                    },
                                    {
                                        "required": ("accessibility",),
                                        "properties": {
                                            "accessibility": {"type": "boolean"}
                                        },
                                    },
                                )
                            },
                        ),
                    ),
                    _operazione(
                        "event",
                        ("event_type",),
                        {
                            "event_type": _testo(120),
                            "target_id": _id_o_null(),
                            "location_id": _id_o_null(),
                        },
                    ),
                    _operazione(
                        "epistemic",
                        ("actor_id",),
                        {
                            "actor_id": _id(),
                            "target_id": _id_o_null(),
                            "location_id": _id_o_null(),
                        },
                    ),
                )
            },
        },
        "memories": {
            "type": "array",
            "maxItems": MAX_MEMORIES,
            "items": {
                "oneOf": (
                    _memoria(
                        "direct_observation",
                        {"const": "observed_fact"},
                        obbligatorie=("operation_index",),
                        specifiche={
                            "operation_index": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": MAX_OPERATIONS - 1,
                            },
                            "source_entity_id": {"type": "null"},
                        },
                        escluse=("source_memory_ids",),
                    ),
                    _memoria(
                        "told_by_character",
                        {"const": "reported_fact"},
                        obbligatorie=("source_entity_id",),
                        specifiche={
                            "source_entity_id": _id(),
                        },
                        escluse=("source_memory_ids",),
                    ),
                    _memoria(
                        "inference",
                        {"enum": ("inference", "belief")},
                        obbligatorie=("source_memory_ids",),
                        specifiche={
                            "source_entity_id": {"type": "null"},
                            "source_memory_ids": _lista_id(min_items=1),
                        },
                    ),
                    _memoria(
                        "self_experience",
                        {"enum": ("observed_fact", "belief")},
                        specifiche={
                            "source_entity_id": {"type": "null"},
                        },
                        escluse=("source_memory_ids",),
                    ),
                )
            },
        },
    },
    "required": ("narrative", "elapsed_minutes", "operations", "memories"),
}


def _congela(valore: object) -> object:
    if isinstance(valore, dict):
        return MappingProxyType({chiave: _congela(voce) for chiave, voce in valore.items()})
    if isinstance(valore, (list, tuple)):
        return tuple(_congela(voce) for voce in valore)
    return valore


def _copia_json(valore: object) -> object:
    if isinstance(valore, Mapping):
        return {chiave: _copia_json(voce) for chiave, voce in valore.items()}
    if isinstance(valore, tuple):
        return [_copia_json(voce) for voce in valore]
    return valore


NARRATIVE_OUTPUT_SCHEMA: Final[Mapping[str, object]] = cast(
    Mapping[str, object], _congela(_SCHEMA_MUTABILE)
)


def schema_output_narrativo() -> dict[str, object]:
    """Restituisce una copia JSON serializzabile del contratto immutabile."""

    return cast(dict[str, object], _copia_json(NARRATIVE_OUTPUT_SCHEMA))


def serializza_schema_output_narrativo() -> str:
    """Serializza la stessa fonte usata dal campo Ollama ``format``."""

    return json.dumps(schema_output_narrativo(), ensure_ascii=False, indent=2)
