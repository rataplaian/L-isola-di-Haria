"""Modelli puri e immutabili per la validazione deterministica del mondo."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias


class SeveritaProblema(str, Enum):
    ERRORE = "errore"
    AVVERTIMENTO = "avvertimento"
    INFORMAZIONE = "informazione"


class AmbitoValidazione(str, Enum):
    INTEGRITA = "integrità"
    SPAZIO = "spazio"
    TEMPO = "tempo"
    INVENTARIO = "inventario"
    EPISTEMICA = "epistemica"


@dataclass(frozen=True, slots=True, order=True)
class RiferimentoEntita:
    entity_id: str
    nome: str


@dataclass(frozen=True, slots=True)
class EntitaValidazione:
    world_id: str
    entity_id: str
    entity_type: str
    canonical_name: str
    status: str
    location_id: str | None
    holder_id: str | None
    accessibility: bool
    condition: str | None
    version: int
    updated_at: str


@dataclass(frozen=True, slots=True)
class EventoValidazione:
    event_id: str
    world_id: str
    event_type: str
    occurred_at: str
    actor_id: str | None
    target_id: str | None
    location_id: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class MemoriaValidazione:
    memory_id: str
    world_id: str
    character_id: str
    event_id: str | None
    knowledge_type: str
    source_type: str
    source_entity_id: str | None
    learned_at: str
    status: str
    supersedes_memory_id: str | None
    is_current: bool
    effective_status: str
    entity_ids: tuple[str, ...]
    source_memory_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FotografiaValidazioneMondo:
    world_id: str
    entita: tuple[EntitaValidazione, ...]
    eventi: tuple[EventoValidazione, ...]
    memorie: tuple[MemoriaValidazione, ...]


@dataclass(frozen=True, slots=True)
class PropostaSpostamento:
    entity_id: str
    location_id: str
    actor_id: str | None = None
    occurred_at: str | None = None
    reason: str = ""
    memory_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PropostaTrasferimento:
    object_id: str
    holder_id: str
    actor_id: str | None = None
    occurred_at: str | None = None
    reason: str = ""
    memory_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PropostaCambioStato:
    target_id: str
    status: str | None = None
    condition: str | None = None
    accessibility: bool | None = None
    actor_id: str | None = None
    occurred_at: str | None = None
    reason: str = ""
    memory_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PropostaEventoDescrittivo:
    event_type: str
    actor_id: str | None = None
    target_id: str | None = None
    location_id: str | None = None
    occurred_at: str | None = None
    reason: str = ""
    memory_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PropostaEpistemica:
    actor_id: str
    target_id: str | None = None
    location_id: str | None = None
    occurred_at: str | None = None
    reason: str = ""
    memory_ids: tuple[str, ...] = ()


PropostaValidazione: TypeAlias = (
    PropostaSpostamento
    | PropostaTrasferimento
    | PropostaCambioStato
    | PropostaEventoDescrittivo
    | PropostaEpistemica
)


@dataclass(frozen=True, slots=True)
class ProblemaValidazione:
    codice: str
    severita: SeveritaProblema
    ambito: AmbitoValidazione
    messaggio: str
    indice_proposta: int | None = None
    entita: tuple[RiferimentoEntita, ...] = ()


@dataclass(frozen=True, slots=True)
class RapportoValidazione:
    problemi: tuple[ProblemaValidazione, ...]

    @property
    def errori(self) -> tuple[ProblemaValidazione, ...]:
        return tuple(
            problema
            for problema in self.problemi
            if problema.severita is SeveritaProblema.ERRORE
        )

    @property
    def avvertimenti(self) -> tuple[ProblemaValidazione, ...]:
        return tuple(
            problema
            for problema in self.problemi
            if problema.severita is SeveritaProblema.AVVERTIMENTO
        )

    @property
    def informazioni(self) -> tuple[ProblemaValidazione, ...]:
        return tuple(
            problema
            for problema in self.problemi
            if problema.severita is SeveritaProblema.INFORMAZIONE
        )

    @property
    def superata(self) -> bool:
        return not self.errori


@dataclass(frozen=True, slots=True)
class EsitoProposta:
    indice: int
    proposta: PropostaValidazione
    rapporto: RapportoValidazione
    fotografia: FotografiaValidazioneMondo

    @property
    def valida(self) -> bool:
        return self.rapporto.superata


@dataclass(frozen=True, slots=True)
class EsitoSequenza:
    esiti: tuple[EsitoProposta, ...]
    rapporto: RapportoValidazione
    fotografia_finale: FotografiaValidazioneMondo

    @property
    def superata(self) -> bool:
        return self.rapporto.superata
