"""Modelli e operazioni validate per le memorie soggettive."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .errors import ErroreImportazione, ErroreMemoria
from .models import FileSorgente
from .world_state import TIPO_PERSONAGGIO

if TYPE_CHECKING:
    from .storage import ArchivioSQLite


KNOWLEDGE_TYPES = frozenset(
    {
        "observed_fact",
        "reported_fact",
        "inference",
        "belief",
        "canonical_knowledge",
    }
)
SOURCE_TYPES = frozenset(
    {
        "direct_observation",
        "told_by_character",
        "inference",
        "imported_background",
        "self_experience",
    }
)
MEMORY_STATUSES = frozenset(
    {"active", "corrected", "contradicted", "superseded"}
)
MEMORY_ROLES = frozenset({"subject", "source", "location", "related"})


def _adesso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True, slots=True)
class MemoriaDaSalvare:
    memory_id: str
    world_id: str
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
    status: str
    supersedes_memory_id: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class EntitaMemoria:
    entity_id: str
    role: str
    canonical_name: str


@dataclass(frozen=True, slots=True)
class MemoriaPersonaggio:
    memory_id: str
    world_id: str
    character_id: str
    event_id: str | None
    knowledge_type: str
    source_type: str
    source_entity_id: str | None
    source_name: str | None
    learned_at: str
    certainty: int
    content: str
    interpretation: str | None
    associated_emotion: str | None
    status: str
    supersedes_memory_id: str | None
    created_at: str
    is_current: bool
    effective_status: str
    entities: tuple[EntitaMemoria, ...]
    source_memory_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssociazioneMemoria:
    entity_id: str
    role: str


@dataclass(frozen=True, slots=True)
class FonteMemoria:
    source_memory_id: str
    position: int


def importa_conoscenze_iniziali(
    file_sorgente: Iterable[FileSorgente], world_id: str
) -> list[MemoriaDaSalvare]:
    """Converte knowledge dalle sole fotografie archiviate con ID deterministici."""

    fotografie = {
        file.percorso_relativo.replace("\\", "/"): file.contenuto
        for file in file_sorgente
    }
    contenuto = fotografie.get("characters.json")
    if contenuto is None:
        raise ErroreImportazione(
            "Manca il file archiviato characters.json necessario per importare le conoscenze."
        )
    try:
        personaggi = json.loads(contenuto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as errore:
        raise ErroreImportazione(
            "Il file archiviato characters.json non contiene dati validi in UTF-8."
        ) from errore
    if not isinstance(personaggi, list) or any(
        not isinstance(personaggio, dict) for personaggio in personaggi
    ):
        raise ErroreImportazione(
            "Il file archiviato characters.json deve contenere un elenco valido."
        )

    istante = _adesso_utc()
    risultato: list[MemoriaDaSalvare] = []
    for personaggio in personaggi:
        character_id = personaggio.get("id")
        if not isinstance(character_id, str) or not character_id.strip():
            raise ErroreImportazione(
                "Un personaggio importato non contiene un identificatore valido."
            )
        conoscenze = personaggio.get("knowledge", [])
        if not isinstance(conoscenze, list):
            raise ErroreImportazione(
                f"Le conoscenze del personaggio “{character_id}” non sono un elenco valido."
            )
        for posizione, voce in enumerate(conoscenze, start=1):
            if not isinstance(voce, str) or not voce.strip():
                raise ErroreImportazione(
                    f"Una conoscenza del personaggio “{character_id}” non è un testo valido."
                )
            impronta = hashlib.sha256(voce.encode("utf-8")).hexdigest()
            identita = "\x00".join(
                (world_id, character_id.strip(), str(posizione), impronta)
            ).encode("utf-8")
            memory_id = "imported_" + hashlib.sha256(identita).hexdigest()
            risultato.append(
                MemoriaDaSalvare(
                    memory_id=memory_id,
                    world_id=world_id,
                    character_id=character_id.strip(),
                    event_id=None,
                    knowledge_type="canonical_knowledge",
                    source_type="imported_background",
                    source_entity_id=None,
                    learned_at=istante,
                    certainty=100,
                    content=voce,
                    interpretation=None,
                    associated_emotion=None,
                    status="active",
                    supersedes_memory_id=None,
                    created_at=istante,
                )
            )
    return risultato


class ServizioMemorie:
    """API soggettiva tipizzata, indipendente da GUI e SQL."""

    def __init__(self, archivio: ArchivioSQLite) -> None:
        self.archivio = archivio

    def registra_osservazione_diretta(
        self,
        world_id: str,
        character_id: str,
        event_id: str,
        content: str,
        certainty: int,
        *,
        interpretation: str | None = None,
        emotion: str | None = None,
        entity_ids: Iterable[str] = (),
    ) -> MemoriaPersonaggio:
        personaggio = self._richiedi_personaggio(world_id, character_id)
        evento = self.archivio.carica_evento(world_id, event_id)
        if evento.location_id is None:
            raise ErroreMemoria(
                "L'evento non possiede un luogo e non può essere osservato direttamente."
            )
        if personaggio.location_id != evento.location_id:
            raise ErroreMemoria(
                "Il personaggio non è presente nel luogo corrente dell'evento."
            )
        testo = self._testo_obbligatorio(content, "contenuto")
        certezza = self._certezza(certainty)
        interpretazione = self._testo_opzionale(interpretation, "interpretazione")
        emozione = self._testo_opzionale(emotion, "emozione")
        for memoria in self.archivio.elenca_memorie_personaggio(
            world_id, character_id, event_id=event_id, solo_correnti=False
        ):
            if (
                memoria.knowledge_type == "observed_fact"
                and memoria.source_type == "direct_observation"
                and memoria.content == testo
                and memoria.certainty == certezza
                and memoria.interpretation == interpretazione
                and memoria.associated_emotion == emozione
            ):
                raise ErroreMemoria(
                    "Esiste già una memoria identica per questo personaggio ed evento."
                )

        associazioni = self._associazioni_correlate(world_id, entity_ids)
        for entity_id in (evento.actor_id, evento.target_id):
            if entity_id is not None:
                associazioni.add((entity_id, "subject"))
        associazioni.add((evento.location_id, "location"))
        memoria = self._nuova_memoria(
            world_id=world_id,
            character_id=character_id,
            event_id=event_id,
            knowledge_type="observed_fact",
            source_type="direct_observation",
            source_entity_id=None,
            content=testo,
            certainty=certezza,
            interpretation=interpretazione,
            emotion=emozione,
        )
        return self._salva(memoria, associazioni, ())

    def registra_racconto(
        self,
        world_id: str,
        listener_id: str,
        speaker_id: str,
        content: str,
        certainty: int,
        *,
        event_id: str | None = None,
        interpretation: str | None = None,
        emotion: str | None = None,
        entity_ids: Iterable[str] = (),
    ) -> MemoriaPersonaggio:
        self._richiedi_personaggio(world_id, listener_id)
        self._richiedi_personaggio(world_id, speaker_id)
        if listener_id == speaker_id:
            raise ErroreMemoria(
                "Ascoltatore e narratore devono essere personaggi diversi."
            )
        evento = (
            self.archivio.carica_evento(world_id, event_id)
            if event_id is not None
            else None
        )
        associazioni = self._associazioni_correlate(world_id, entity_ids)
        associazioni.add((speaker_id, "source"))
        if evento is not None and evento.location_id is not None:
            associazioni.add((evento.location_id, "location"))
        memoria = self._nuova_memoria(
            world_id=world_id,
            character_id=listener_id,
            event_id=event_id,
            knowledge_type="reported_fact",
            source_type="told_by_character",
            source_entity_id=speaker_id,
            content=self._testo_obbligatorio(content, "contenuto"),
            certainty=self._certezza(certainty),
            interpretation=self._testo_opzionale(interpretation, "interpretazione"),
            emotion=self._testo_opzionale(emotion, "emozione"),
        )
        return self._salva(memoria, associazioni, ())

    def registra_inferenza(
        self,
        world_id: str,
        character_id: str,
        content: str,
        certainty: int,
        *,
        source_memory_ids: Sequence[str] = (),
        event_id: str | None = None,
        interpretation: str | None = None,
        emotion: str | None = None,
        entity_ids: Iterable[str] = (),
    ) -> MemoriaPersonaggio:
        self._richiedi_personaggio(world_id, character_id)
        if event_id is not None:
            self.archivio.carica_evento(world_id, event_id)
        fonti: list[FonteMemoria] = []
        viste: set[str] = set()
        for posizione, source_memory_id in enumerate(source_memory_ids, start=1):
            if source_memory_id in viste:
                raise ErroreMemoria("Una memoria origine è stata indicata più volte.")
            viste.add(source_memory_id)
            sorgente = self.archivio.carica_memoria(world_id, source_memory_id)
            if sorgente.character_id != character_id:
                raise ErroreMemoria(
                    "La memoria origine appartiene a un altro personaggio."
                )
            fonti.append(FonteMemoria(source_memory_id, posizione))
        memoria = self._nuova_memoria(
            world_id=world_id,
            character_id=character_id,
            event_id=event_id,
            knowledge_type="inference",
            source_type="inference",
            source_entity_id=None,
            content=self._testo_obbligatorio(content, "contenuto"),
            certainty=self._certezza(certainty),
            interpretation=self._testo_opzionale(interpretation, "interpretazione"),
            emotion=self._testo_opzionale(emotion, "emozione"),
        )
        associazioni = self._associazioni_correlate(world_id, entity_ids)
        return self._salva(memoria, associazioni, fonti)

    def correggi_memoria(
        self,
        world_id: str,
        character_id: str,
        previous_memory_id: str,
        content: str,
        certainty: int,
        *,
        status: str = "corrected",
        interpretation: str | None = None,
        emotion: str | None = None,
        entity_ids: Iterable[str] = (),
    ) -> MemoriaPersonaggio:
        self._richiedi_personaggio(world_id, character_id)
        precedente = self.archivio.carica_memoria(world_id, previous_memory_id)
        if precedente.character_id != character_id:
            raise ErroreMemoria(
                "La memoria da correggere appartiene a un altro personaggio."
            )
        if not precedente.is_current:
            raise ErroreMemoria("La memoria da correggere non è più corrente.")
        if status not in {"corrected", "contradicted"}:
            raise ErroreMemoria(
                "Una correzione deve essere indicata come corretta o contraddetta."
            )
        memoria = self._nuova_memoria(
            world_id=world_id,
            character_id=character_id,
            event_id=precedente.event_id,
            knowledge_type=precedente.knowledge_type,
            source_type=precedente.source_type,
            source_entity_id=precedente.source_entity_id,
            content=self._testo_obbligatorio(content, "contenuto"),
            certainty=self._certezza(certainty),
            interpretation=self._testo_opzionale(interpretation, "interpretazione"),
            emotion=self._testo_opzionale(emotion, "emozione"),
            status=status,
            supersedes_memory_id=previous_memory_id,
        )
        associazioni = self._associazioni_correlate(world_id, entity_ids)
        return self._salva(memoria, associazioni, ())

    def elenca_memorie_personaggio(
        self,
        world_id: str,
        character_id: str,
        *,
        event_id: str | None = None,
        entity_id: str | None = None,
        source_type: str | None = None,
        solo_correnti: bool = True,
    ) -> list[MemoriaPersonaggio]:
        self._richiedi_personaggio(world_id, character_id)
        if entity_id is not None:
            self.archivio.carica_entita(world_id, entity_id)
        if source_type is not None and source_type not in SOURCE_TYPES:
            raise ErroreMemoria("Il tipo di fonte richiesto non è valido.")
        return self.archivio.elenca_memorie_personaggio(
            world_id,
            character_id,
            event_id=event_id,
            entity_id=entity_id,
            source_type=source_type,
            solo_correnti=solo_correnti,
        )

    def _richiedi_personaggio(self, world_id: str, entity_id: str):
        entita = self.archivio.carica_entita(world_id, entity_id)
        if entita.entity_type != TIPO_PERSONAGGIO:
            raise ErroreMemoria(
                f"L'entità “{entita.canonical_name}” non è un personaggio."
            )
        return entita

    def _associazioni_correlate(
        self, world_id: str, entity_ids: Iterable[str]
    ) -> set[tuple[str, str]]:
        associazioni: set[tuple[str, str]] = set()
        for entity_id in entity_ids:
            self.archivio.carica_entita(world_id, entity_id)
            associazioni.add((entity_id, "related"))
        return associazioni

    def _salva(
        self,
        memoria: MemoriaDaSalvare,
        associazioni: Iterable[tuple[str, str]],
        fonti: Iterable[FonteMemoria],
    ) -> MemoriaPersonaggio:
        self.archivio.registra_memoria(
            memoria,
            (AssociazioneMemoria(entity_id, role) for entity_id, role in associazioni),
            fonti,
        )
        return self.archivio.carica_memoria(memoria.world_id, memoria.memory_id)

    @staticmethod
    def _nuova_memoria(
        *,
        world_id: str,
        character_id: str,
        event_id: str | None,
        knowledge_type: str,
        source_type: str,
        source_entity_id: str | None,
        content: str,
        certainty: int,
        interpretation: str | None,
        emotion: str | None,
        status: str = "active",
        supersedes_memory_id: str | None = None,
    ) -> MemoriaDaSalvare:
        istante = _adesso_utc()
        return MemoriaDaSalvare(
            memory_id=uuid.uuid4().hex,
            world_id=world_id,
            character_id=character_id,
            event_id=event_id,
            knowledge_type=knowledge_type,
            source_type=source_type,
            source_entity_id=source_entity_id,
            learned_at=istante,
            certainty=certainty,
            content=content,
            interpretation=interpretation,
            associated_emotion=emotion,
            status=status,
            supersedes_memory_id=supersedes_memory_id,
            created_at=istante,
        )

    @staticmethod
    def _certezza(valore: int) -> int:
        if isinstance(valore, bool) or not isinstance(valore, int) or not 0 <= valore <= 100:
            raise ErroreMemoria("La certezza deve essere un intero tra 0 e 100.")
        return valore

    @staticmethod
    def _testo_obbligatorio(valore: str, nome: str) -> str:
        if not isinstance(valore, str) or not valore.strip():
            raise ErroreMemoria(f"Il campo {nome} è obbligatorio.")
        return valore.strip()

    @classmethod
    def _testo_opzionale(cls, valore: str | None, nome: str) -> str | None:
        if valore is None:
            return None
        return cls._testo_obbligatorio(valore, nome)
