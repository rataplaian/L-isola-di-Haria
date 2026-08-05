"""Fotografie read-only e regole deterministiche per il mondo corrente."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Protocol

from .errors import ErroreHaria, ErroreValidazione
from .memories import MemoriaPersonaggio
from .models import Mondo
from .validation_models import (
    EntitaValidazione,
    EventoValidazione,
    FotografiaValidazioneMondo,
    MemoriaValidazione,
)
from .world_state import EntitaMondo, EventoMondo, TIPO_PERSONAGGIO


class ArchivioLetturaValidazione(Protocol):
    """Superficie minima di lettura necessaria al validatore."""

    def carica_mondo(self, mondo_id: str) -> Mondo: ...

    def elenca_entita(
        self, mondo_id: str, entity_type: str | None = None
    ) -> list[EntitaMondo]: ...

    def elenca_eventi(self, mondo_id: str) -> list[EventoMondo]: ...

    def elenca_memorie_personaggio(
        self,
        mondo_id: str,
        character_id: str,
        *,
        event_id: str | None = None,
        entity_id: str | None = None,
        source_type: str | None = None,
        solo_correnti: bool = True,
    ) -> list[MemoriaPersonaggio]: ...


class ServizioValidazione:
    """Costruisce fotografie senza esporre SQLite alle regole pure."""

    def __init__(self, archivio: ArchivioLetturaValidazione) -> None:
        self._archivio = archivio

    def costruisci_fotografia(
        self, world_id: str
    ) -> FotografiaValidazioneMondo:
        if not isinstance(world_id, str) or not world_id.strip():
            raise ErroreValidazione("Seleziona un mondo valido da controllare.")
        mondo_id = world_id.strip()
        try:
            mondo = self._archivio.carica_mondo(mondo_id)
            entita_archivio = self._archivio.elenca_entita(mondo.id)
            eventi_archivio = self._archivio.elenca_eventi(mondo.id)
            memorie_archivio: list[MemoriaPersonaggio] = []
            for entita in sorted(
                entita_archivio, key=lambda voce: voce.entity_id
            ):
                if entita.entity_type == TIPO_PERSONAGGIO:
                    memorie_archivio.extend(
                        self._archivio.elenca_memorie_personaggio(
                            mondo.id,
                            entita.entity_id,
                            solo_correnti=False,
                        )
                    )
        except ErroreValidazione:
            raise
        except ErroreHaria as errore:
            raise ErroreValidazione(
                "Non è stato possibile costruire la fotografia del mondo selezionato."
            ) from errore
        except Exception as errore:
            raise ErroreValidazione(
                "La lettura del mondo non è riuscita senza modificare i dati."
            ) from errore

        entita = tuple(
            sorted(
                (self._entita_validazione(voce) for voce in entita_archivio),
                key=lambda voce: (voce.entity_type, voce.canonical_name.casefold(), voce.entity_id),
            )
        )
        eventi = tuple(
            sorted(
                (self._evento_validazione(voce) for voce in eventi_archivio),
                key=self._chiave_evento,
            )
        )
        memorie = tuple(
            sorted(
                (self._memoria_validazione(voce) for voce in memorie_archivio),
                key=lambda voce: (
                    voce.learned_at,
                    voce.character_id,
                    voce.memory_id,
                ),
            )
        )
        return FotografiaValidazioneMondo(
            world_id=mondo.id,
            entita=entita,
            eventi=eventi,
            memorie=memorie,
        )

    @staticmethod
    def _entita_validazione(entita: EntitaMondo) -> EntitaValidazione:
        return EntitaValidazione(
            world_id=entita.world_id,
            entity_id=entita.entity_id,
            entity_type=entita.entity_type,
            canonical_name=entita.canonical_name,
            status=entita.status,
            location_id=entita.location_id,
            holder_id=entita.holder_id,
            accessibility=entita.accessibility,
            condition=entita.condition,
            version=entita.version,
            updated_at=entita.updated_at,
        )

    @staticmethod
    def _evento_validazione(evento: EventoMondo) -> EventoValidazione:
        return EventoValidazione(
            event_id=evento.event_id,
            world_id=evento.world_id,
            event_type=evento.event_type,
            occurred_at=evento.occurred_at,
            actor_id=evento.actor_id,
            target_id=evento.target_id,
            location_id=evento.location_id,
            created_at=evento.created_at,
        )

    @staticmethod
    def _memoria_validazione(memoria: MemoriaPersonaggio) -> MemoriaValidazione:
        return MemoriaValidazione(
            memory_id=memoria.memory_id,
            world_id=memoria.world_id,
            character_id=memoria.character_id,
            event_id=memoria.event_id,
            knowledge_type=memoria.knowledge_type,
            source_type=memoria.source_type,
            source_entity_id=memoria.source_entity_id,
            learned_at=memoria.learned_at,
            status=memoria.status,
            supersedes_memory_id=memoria.supersedes_memory_id,
            is_current=memoria.is_current,
            effective_status=memoria.effective_status,
            entity_ids=tuple(
                sorted(entita.entity_id for entita in memoria.entities)
            ),
            source_memory_ids=tuple(memoria.source_memory_ids),
        )

    @classmethod
    def _chiave_evento(
        cls, evento: EventoValidazione
    ) -> tuple[int, datetime, str, str]:
        istante = cls._istante_utc_opzionale(evento.occurred_at)
        if istante is None:
            return (1, datetime.max.replace(tzinfo=timezone.utc), evento.created_at, evento.event_id)
        return (0, istante, evento.created_at, evento.event_id)

    @staticmethod
    def _istante_utc_opzionale(valore: str) -> datetime | None:
        if not isinstance(valore, str) or not valore.strip():
            return None
        testo = valore.strip()
        if testo.endswith("Z"):
            testo = testo[:-1] + "+00:00"
        try:
            istante = datetime.fromisoformat(testo)
        except ValueError:
            return None
        if istante.tzinfo is None or istante.utcoffset() is None:
            return None
        return istante.astimezone(timezone.utc)


def riferimenti_unici(valori: Sequence[str]) -> tuple[str, ...]:
    """Normalizza riferimenti soltanto per confronti, senza perdere stabilità."""

    return tuple(sorted(set(valori)))
