"""Parser rigoroso dell'output JSON prodotto dal motore narrativo."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Final

from .errors import ErroreTurnoNarrativo
from .memories import KNOWLEDGE_TYPES, MEMORY_ROLES, SOURCE_TYPES
from .narrative_models import (
    AssociazioneMemoriaCandidata,
    MemoriaCandidata,
    TurnoNarrativoProposto,
)
from .narrative_output_schema import (
    MAX_ELAPSED_MINUTES,
    MAX_MEMORIES,
    MAX_MEMORY_CONTENT_CHARS,
    MAX_NARRATIVE_CHARS,
    MAX_OPERATIONS,
)
from .validation_models import (
    PropostaCambioStato,
    PropostaEpistemica,
    PropostaEventoDescrittivo,
    PropostaSpostamento,
    PropostaTrasferimento,
    PropostaValidazione,
)


MAX_OUTPUT_CHARS: Final = 100_000

TOP_LEVEL_KEYS: Final = frozenset(
    {"narrative", "elapsed_minutes", "operations", "memories"}
)


class ErroreOutputNarrativo(ErroreTurnoNarrativo, ValueError):
    """La risposta del modello non rispetta il contratto narrativo."""


class ErroreOutputNarrativoNonRiparabile(ErroreOutputNarrativo):
    """L'output non è un singolo oggetto JSON riparabile automaticamente."""


class ErroreStrutturaOutputNarrativo(ErroreOutputNarrativo):
    """Un oggetto JSON leggibile non rispetta la struttura richiesta."""


def parse_output_narrativo(raw: str) -> TurnoNarrativoProposto:
    """Converte un singolo oggetto JSON in modelli tipizzati e immutabili."""

    if not isinstance(raw, str):
        raise ErroreOutputNarrativoNonRiparabile(
            "La risposta narrativa deve essere testuale."
        )
    if len(raw) > MAX_OUTPUT_CHARS:
        raise ErroreOutputNarrativoNonRiparabile(
            "La risposta narrativa supera il limite consentito."
        )
    if not raw.strip():
        raise ErroreOutputNarrativoNonRiparabile("La risposta narrativa è vuota.")
    try:
        dati = json.loads(raw)
    except json.JSONDecodeError as errore:
        raise ErroreOutputNarrativoNonRiparabile(
            "Il modello non ha restituito un singolo oggetto JSON valido."
        ) from errore
    if not isinstance(dati, dict):
        raise ErroreOutputNarrativoNonRiparabile(
            "La risposta narrativa deve essere un oggetto JSON."
        )
    try:
        return _parse_oggetto_narrativo(dati)
    except ErroreStrutturaOutputNarrativo:
        raise
    except ErroreOutputNarrativo as errore:
        raise ErroreStrutturaOutputNarrativo(str(errore)) from errore


def _parse_oggetto_narrativo(
    dati: dict[str, object],
) -> TurnoNarrativoProposto:
    """Valida la struttura dopo che sintassi e oggetto radice sono certi."""

    _richiedi_chiavi_esatte(dati, TOP_LEVEL_KEYS, "risposta narrativa")

    narrative = _testo_obbligatorio(
        dati["narrative"], "testo narrativo", MAX_NARRATIVE_CHARS
    )
    elapsed_minutes = _intero_nell_intervallo(
        dati["elapsed_minutes"],
        "tempo trascorso",
        minimo=0,
        massimo=MAX_ELAPSED_MINUTES,
    )
    operations_raw = _lista(dati["operations"], "operazioni")
    memories_raw = _lista(dati["memories"], "memorie")
    if len(operations_raw) > MAX_OPERATIONS:
        raise ErroreOutputNarrativo(
            f"Il modello ha proposto più di {MAX_OPERATIONS} operazioni."
        )
    if len(memories_raw) > MAX_MEMORIES:
        raise ErroreOutputNarrativo(
            f"Il modello ha proposto più di {MAX_MEMORIES} memorie."
        )

    operations = tuple(
        _parse_operazione(voce, indice)
        for indice, voce in enumerate(operations_raw)
    )
    memories = tuple(
        _parse_memoria(voce, indice)
        for indice, voce in enumerate(memories_raw)
    )
    return TurnoNarrativoProposto(
        narrative=narrative,
        elapsed_minutes=elapsed_minutes,
        operations=operations,
        memories=memories,
    )


def _parse_operazione(valore: object, indice: int) -> PropostaValidazione:
    dati = _oggetto(valore, f"operazione {indice + 1}")
    tipo = _testo_obbligatorio(dati.get("type"), "tipo operazione", 80)

    if tipo == "move":
        _richiedi_chiavi_esatte(
            dati,
            frozenset({"type", "entity_id", "location_id", "reason"}),
            f"operazione {indice + 1}",
            opzionali=frozenset({"actor_id", "occurred_at", "memory_ids"}),
        )
        return PropostaSpostamento(
            entity_id=_id(dati["entity_id"], "entità da spostare"),
            location_id=_id(dati["location_id"], "luogo di destinazione"),
            actor_id=_id_opzionale(dati.get("actor_id"), "attore"),
            occurred_at=_testo_opzionale(dati.get("occurred_at"), "istante"),
            reason=_testo_obbligatorio(dati["reason"], "motivo", 1_000),
            memory_ids=_lista_id(dati.get("memory_ids", []), "memorie collegate"),
        )

    if tipo == "transfer":
        _richiedi_chiavi_esatte(
            dati,
            frozenset({"type", "object_id", "holder_id", "reason"}),
            f"operazione {indice + 1}",
            opzionali=frozenset({"actor_id", "occurred_at", "memory_ids"}),
        )
        return PropostaTrasferimento(
            object_id=_id(dati["object_id"], "oggetto"),
            holder_id=_id(dati["holder_id"], "possessore"),
            actor_id=_id_opzionale(dati.get("actor_id"), "attore"),
            occurred_at=_testo_opzionale(dati.get("occurred_at"), "istante"),
            reason=_testo_obbligatorio(dati["reason"], "motivo", 1_000),
            memory_ids=_lista_id(dati.get("memory_ids", []), "memorie collegate"),
        )

    if tipo == "state_change":
        _richiedi_chiavi_esatte(
            dati,
            frozenset({"type", "target_id", "reason"}),
            f"operazione {indice + 1}",
            opzionali=frozenset(
                {
                    "status",
                    "condition",
                    "accessibility",
                    "actor_id",
                    "occurred_at",
                    "memory_ids",
                }
            ),
        )
        status = _testo_opzionale(dati.get("status"), "stato")
        condition = _testo_opzionale(dati.get("condition"), "condizione")
        accessibility = _booleano_opzionale(
            dati.get("accessibility"), "accessibilità"
        )
        if status is None and condition is None and accessibility is None:
            raise ErroreOutputNarrativo(
                "Un cambio di stato deve modificare almeno un campo."
            )
        return PropostaCambioStato(
            target_id=_id(dati["target_id"], "bersaglio"),
            status=status,
            condition=condition,
            accessibility=accessibility,
            actor_id=_id_opzionale(dati.get("actor_id"), "attore"),
            occurred_at=_testo_opzionale(dati.get("occurred_at"), "istante"),
            reason=_testo_obbligatorio(dati["reason"], "motivo", 1_000),
            memory_ids=_lista_id(dati.get("memory_ids", []), "memorie collegate"),
        )

    if tipo == "event":
        _richiedi_chiavi_esatte(
            dati,
            frozenset({"type", "event_type", "reason"}),
            f"operazione {indice + 1}",
            opzionali=frozenset(
                {
                    "actor_id",
                    "target_id",
                    "location_id",
                    "occurred_at",
                    "memory_ids",
                }
            ),
        )
        return PropostaEventoDescrittivo(
            event_type=_testo_obbligatorio(
                dati["event_type"], "tipo evento", 120
            ),
            actor_id=_id_opzionale(dati.get("actor_id"), "attore"),
            target_id=_id_opzionale(dati.get("target_id"), "bersaglio"),
            location_id=_id_opzionale(dati.get("location_id"), "luogo"),
            occurred_at=_testo_opzionale(dati.get("occurred_at"), "istante"),
            reason=_testo_obbligatorio(dati["reason"], "motivo", 1_000),
            memory_ids=_lista_id(dati.get("memory_ids", []), "memorie collegate"),
        )

    if tipo == "epistemic":
        _richiedi_chiavi_esatte(
            dati,
            frozenset({"type", "actor_id", "reason"}),
            f"operazione {indice + 1}",
            opzionali=frozenset(
                {"target_id", "location_id", "occurred_at", "memory_ids"}
            ),
        )
        return PropostaEpistemica(
            actor_id=_id(dati["actor_id"], "attore epistemico"),
            target_id=_id_opzionale(dati.get("target_id"), "bersaglio"),
            location_id=_id_opzionale(dati.get("location_id"), "luogo"),
            occurred_at=_testo_opzionale(dati.get("occurred_at"), "istante"),
            reason=_testo_obbligatorio(dati["reason"], "motivo", 1_000),
            memory_ids=_lista_id(dati.get("memory_ids", []), "memorie collegate"),
        )

    raise ErroreOutputNarrativo(
        f"Il tipo di operazione “{tipo}” non è supportato."
    )


def _parse_memoria(valore: object, indice: int) -> MemoriaCandidata:
    dati = _oggetto(valore, f"memoria {indice + 1}")
    _richiedi_chiavi_esatte(
        dati,
        frozenset(
            {
                "character_id",
                "knowledge_type",
                "source_type",
                "certainty",
                "content",
            }
        ),
        f"memoria {indice + 1}",
        opzionali=frozenset(
            {
                "source_entity_id",
                "interpretation",
                "associated_emotion",
                "entities",
                "source_memory_ids",
                "operation_index",
            }
        ),
    )
    knowledge_type = _testo_obbligatorio(
        dati["knowledge_type"], "tipo di conoscenza", 80
    )
    if knowledge_type not in KNOWLEDGE_TYPES:
        raise ErroreOutputNarrativo(
            f"Il tipo di conoscenza “{knowledge_type}” non è supportato."
        )
    source_type = _testo_obbligatorio(
        dati["source_type"], "tipo di fonte", 80
    )
    if source_type not in SOURCE_TYPES:
        raise ErroreOutputNarrativo(
            f"Il tipo di fonte “{source_type}” non è supportato."
        )
    entities_raw = _lista(dati.get("entities", []), "entità della memoria")
    entities: list[AssociazioneMemoriaCandidata] = []
    seen_entities: set[tuple[str, str]] = set()
    for posizione, valore_entita in enumerate(entities_raw):
        entita = _oggetto(
            valore_entita,
            f"entità {posizione + 1} della memoria {indice + 1}",
        )
        _richiedi_chiavi_esatte(
            entita,
            frozenset({"entity_id", "role"}),
            f"entità {posizione + 1} della memoria {indice + 1}",
        )
        role = _testo_obbligatorio(entita["role"], "ruolo memoria", 40)
        if role not in MEMORY_ROLES:
            raise ErroreOutputNarrativo(
                f"Il ruolo memoria “{role}” non è supportato."
            )
        associazione = AssociazioneMemoriaCandidata(
            entity_id=_id(entita["entity_id"], "entità della memoria"),
            role=role,
        )
        chiave = (associazione.entity_id, associazione.role)
        if chiave in seen_entities:
            raise ErroreOutputNarrativo(
                "La stessa associazione è duplicata nella memoria."
            )
        seen_entities.add(chiave)
        entities.append(associazione)

    return MemoriaCandidata(
        character_id=_id(dati["character_id"], "personaggio della memoria"),
        knowledge_type=knowledge_type,
        source_type=source_type,
        source_entity_id=_id_opzionale(
            dati.get("source_entity_id"), "fonte della memoria"
        ),
        certainty=_intero_nell_intervallo(
            dati["certainty"], "certezza", minimo=0, massimo=100
        ),
        content=_testo_obbligatorio(
            dati["content"], "contenuto memoria", MAX_MEMORY_CONTENT_CHARS
        ),
        interpretation=_testo_opzionale(
            dati.get("interpretation"), "interpretazione", massimo=2_000
        ),
        associated_emotion=_testo_opzionale(
            dati.get("associated_emotion"), "emozione", massimo=500
        ),
        entities=tuple(entities),
        source_memory_ids=_lista_id(
            dati.get("source_memory_ids", []), "memorie sorgente"
        ),
        operation_index=_intero_opzionale_non_negativo(
            dati.get("operation_index"), "indice operazione"
        ),
    )


def _richiedi_chiavi_esatte(
    dati: Mapping[str, object],
    obbligatorie: frozenset[str],
    descrizione: str,
    *,
    opzionali: frozenset[str] = frozenset(),
) -> None:
    presenti = set(dati)
    mancanti = obbligatorie - presenti
    sconosciute = presenti - obbligatorie - opzionali
    if mancanti:
        raise ErroreOutputNarrativo(
            f"Nella {descrizione} mancano: {', '.join(sorted(mancanti))}."
        )
    if sconosciute:
        raise ErroreOutputNarrativo(
            f"Nella {descrizione} sono presenti campi non ammessi: "
            f"{', '.join(sorted(sconosciute))}."
        )


def _oggetto(valore: object, descrizione: str) -> dict[str, object]:
    if not isinstance(valore, dict):
        raise ErroreOutputNarrativo(f"{descrizione.capitalize()} non è un oggetto.")
    if any(not isinstance(chiave, str) for chiave in valore):
        raise ErroreOutputNarrativo(
            f"{descrizione.capitalize()} contiene una chiave non testuale."
        )
    return dict(valore)


def _lista(valore: object, descrizione: str) -> list[object]:
    if not isinstance(valore, list):
        raise ErroreOutputNarrativo(
            f"Il campo {descrizione} deve essere un elenco."
        )
    return list(valore)


def _testo_obbligatorio(
    valore: object, descrizione: str, massimo: int
) -> str:
    if not isinstance(valore, str) or not valore.strip():
        raise ErroreOutputNarrativo(
            f"Il campo {descrizione} deve contenere testo."
        )
    testo = valore.strip()
    if len(testo) > massimo:
        raise ErroreOutputNarrativo(
            f"Il campo {descrizione} supera il limite di {massimo} caratteri."
        )
    return testo


def _testo_opzionale(
    valore: object, descrizione: str, massimo: int = 1_000
) -> str | None:
    if valore is None:
        return None
    return _testo_obbligatorio(valore, descrizione, massimo)


def _id(valore: object, descrizione: str) -> str:
    return _testo_obbligatorio(valore, descrizione, 200)


def _id_opzionale(valore: object, descrizione: str) -> str | None:
    if valore is None:
        return None
    return _id(valore, descrizione)


def _lista_id(valore: object, descrizione: str) -> tuple[str, ...]:
    valori = _lista(valore, descrizione)
    risultato = tuple(_id(voce, descrizione) for voce in valori)
    if len(set(risultato)) != len(risultato):
        raise ErroreOutputNarrativo(
            f"Il campo {descrizione} contiene riferimenti duplicati."
        )
    return risultato


def _booleano_opzionale(valore: object, descrizione: str) -> bool | None:
    if valore is None:
        return None
    if not isinstance(valore, bool):
        raise ErroreOutputNarrativo(
            f"Il campo {descrizione} deve essere vero, falso oppure nullo."
        )
    return valore


def _intero_opzionale_non_negativo(
    valore: object, descrizione: str
) -> int | None:
    if valore is None:
        return None
    return _intero_nell_intervallo(
        valore, descrizione, minimo=0, massimo=MAX_OPERATIONS - 1
    )


def _intero_nell_intervallo(
    valore: object,
    descrizione: str,
    *,
    minimo: int,
    massimo: int,
) -> int:
    if isinstance(valore, bool) or not isinstance(valore, int):
        raise ErroreOutputNarrativo(
            f"Il campo {descrizione} deve essere un numero intero."
        )
    if not minimo <= valore <= massimo:
        raise ErroreOutputNarrativo(
            f"Il campo {descrizione} deve essere compreso tra {minimo} e {massimo}."
        )
    return valore
