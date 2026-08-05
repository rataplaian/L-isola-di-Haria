"""Modelli e validazione dei dati canonici e dello stato corrente."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .errors import ErroreImportazione, ErroreStatoMondo
from .models import FileSorgente

if TYPE_CHECKING:
    from .storage import ArchivioSQLite


TIPO_PERSONAGGIO = "personaggio"
TIPO_LUOGO = "luogo"
TIPO_OGGETTO = "oggetto"
TIPI_ENTITA = frozenset({TIPO_PERSONAGGIO, TIPO_LUOGO, TIPO_OGGETTO})


@dataclass(frozen=True, slots=True)
class EntitaImportata:
    entity_id: str
    entity_type: str
    canonical_name: str
    canonical_data: dict[str, object]
    status: str
    location_id: str | None
    holder_id: str | None
    accessibility: bool
    condition: str | None
    state_data: dict[str, object]


@dataclass(frozen=True, slots=True)
class EntitaMondo:
    world_id: str
    entity_id: str
    entity_type: str
    canonical_name: str
    canonical_data: dict[str, object]
    status: str
    location_id: str | None
    holder_id: str | None
    accessibility: bool
    condition: str | None
    state_data: dict[str, object]
    version: int
    updated_at: str


@dataclass(frozen=True, slots=True)
class EventoMondo:
    event_id: str
    world_id: str
    event_type: str
    occurred_at: str
    actor_id: str | None
    target_id: str | None
    location_id: str | None
    payload: dict[str, object]
    reason: str
    created_at: str


@dataclass(frozen=True, slots=True)
class AggiornamentoStato:
    entity_id: str
    expected_version: int
    status: str
    location_id: str | None
    holder_id: str | None
    accessibility: bool
    condition: str | None
    state_data: dict[str, object]


class ServizioStatoMondo:
    """Operazioni strutturate validate, indipendenti dall'interfaccia grafica."""

    def __init__(self, archivio: ArchivioSQLite) -> None:
        self.archivio = archivio

    def elenca_entita(
        self, mondo_id: str, entity_type: str | None = None
    ) -> list[EntitaMondo]:
        return self.archivio.elenca_entita(mondo_id, entity_type)

    def carica_entita(self, mondo_id: str, entity_id: str) -> EntitaMondo:
        return self.archivio.carica_entita(mondo_id, entity_id)

    def eventi_per_entita(
        self, mondo_id: str, entity_id: str
    ) -> list[EventoMondo]:
        return self.archivio.eventi_per_entita(mondo_id, entity_id)

    def elenca_eventi(self, mondo_id: str) -> list[EventoMondo]:
        return self.archivio.elenca_eventi(mondo_id)

    def sposta_entita(
        self,
        mondo_id: str,
        entity_id: str,
        location_id: str,
        *,
        reason: str,
        actor_id: str | None = None,
    ) -> EventoMondo:
        self.archivio.carica_mondo(mondo_id)
        entita = self.archivio.carica_entita(mondo_id, entity_id)
        if entita.entity_type not in {TIPO_PERSONAGGIO, TIPO_OGGETTO}:
            raise ErroreStatoMondo(
                "Solo un personaggio o un oggetto può essere spostato."
            )
        luogo = self._richiedi_tipo(mondo_id, location_id, TIPO_LUOGO)
        self._valida_riferimento_opzionale(mondo_id, actor_id)
        if entita.entity_type == TIPO_OGGETTO and entita.holder_id is not None:
            raise ErroreStatoMondo(
                "Un oggetto posseduto deve essere trasferito, non spostato direttamente."
            )

        aggiornamenti = [
            self._aggiornamento(entita, location_id=luogo.entity_id)
        ]
        if entita.entity_type == TIPO_PERSONAGGIO:
            for oggetto in self.archivio.entita_possedute(mondo_id, entita.entity_id):
                aggiornamenti.append(
                    self._aggiornamento(oggetto, location_id=luogo.entity_id)
                )

        evento = self._nuovo_evento(
            mondo_id=mondo_id,
            event_type="spostamento_entita",
            actor_id=actor_id,
            target_id=entita.entity_id,
            location_id=luogo.entity_id,
            payload={
                "location_id_precedente": entita.location_id,
                "location_id_nuova": luogo.entity_id,
            },
            reason=reason,
        )
        self.archivio.applica_evento_e_stati(evento, aggiornamenti)
        return evento

    def trasferisci_oggetto(
        self,
        mondo_id: str,
        object_id: str,
        holder_id: str,
        *,
        reason: str,
        actor_id: str | None = None,
    ) -> EventoMondo:
        self.archivio.carica_mondo(mondo_id)
        oggetto = self._richiedi_tipo(mondo_id, object_id, TIPO_OGGETTO)
        possessore = self._richiedi_tipo(mondo_id, holder_id, TIPO_PERSONAGGIO)
        if possessore.location_id is None:
            raise ErroreStatoMondo(
                "Il possessore non ha una posizione corrente valida."
            )
        self._richiedi_tipo(mondo_id, possessore.location_id, TIPO_LUOGO)
        if (
            oggetto.holder_id == possessore.entity_id
            and oggetto.location_id == possessore.location_id
        ):
            raise ErroreStatoMondo(
                "L'oggetto è già assegnato al possessore selezionato."
            )
        attore = actor_id or possessore.entity_id
        self._valida_riferimento_opzionale(mondo_id, attore)

        aggiornamento = self._aggiornamento(
            oggetto,
            location_id=possessore.location_id,
            holder_id=possessore.entity_id,
        )
        evento = self._nuovo_evento(
            mondo_id=mondo_id,
            event_type="trasferimento_oggetto",
            actor_id=attore,
            target_id=oggetto.entity_id,
            location_id=possessore.location_id,
            payload={
                "holder_id_precedente": oggetto.holder_id,
                "holder_id_nuovo": possessore.entity_id,
                "location_id": possessore.location_id,
            },
            reason=reason,
        )
        self.archivio.applica_evento_e_stati(evento, [aggiornamento])
        return evento

    def cambia_stato(
        self,
        mondo_id: str,
        entity_id: str,
        *,
        reason: str,
        status: str | None = None,
        condition: str | None = None,
        accessibility: bool | None = None,
        actor_id: str | None = None,
    ) -> EventoMondo:
        self.archivio.carica_mondo(mondo_id)
        entita = self.archivio.carica_entita(mondo_id, entity_id)
        self._valida_riferimento_opzionale(mondo_id, actor_id)
        if status is None and condition is None and accessibility is None:
            raise ErroreStatoMondo(
                "Indica almeno uno stato, una condizione o un'accessibilità da modificare."
            )
        if accessibility is not None and not isinstance(accessibility, bool):
            raise ErroreStatoMondo("Il valore di accessibilità deve essere vero o falso.")
        stato_nuovo = (
            self._testo_non_vuoto(status, "stato")
            if status is not None
            else entita.status
        )
        condizione_nuova = (
            self._testo_non_vuoto(condition, "condizione")
            if condition is not None
            else entita.condition
        )
        aggiornamento = self._aggiornamento(
            entita,
            status=stato_nuovo,
            condition=condizione_nuova,
            accessibility=(
                entita.accessibility if accessibility is None else accessibility
            ),
        )
        evento = self._nuovo_evento(
            mondo_id=mondo_id,
            event_type="cambio_stato",
            actor_id=actor_id,
            target_id=entita.entity_id,
            location_id=entita.location_id,
            payload={
                "status": stato_nuovo,
                "condition": condizione_nuova,
                "accessibility": aggiornamento.accessibility,
            },
            reason=reason,
        )
        self.archivio.applica_evento_e_stati(evento, [aggiornamento])
        return evento

    def registra_evento_descrittivo(
        self,
        mondo_id: str,
        event_type: str,
        *,
        reason: str,
        actor_id: str | None = None,
        target_id: str | None = None,
        location_id: str | None = None,
        payload: Mapping[str, object] | None = None,
    ) -> EventoMondo:
        self.archivio.carica_mondo(mondo_id)
        self._valida_riferimento_opzionale(mondo_id, actor_id)
        self._valida_riferimento_opzionale(mondo_id, target_id)
        if location_id is not None:
            self._richiedi_tipo(mondo_id, location_id, TIPO_LUOGO)
        evento = self._nuovo_evento(
            mondo_id=mondo_id,
            event_type=self._testo_non_vuoto(event_type, "tipo evento"),
            actor_id=actor_id,
            target_id=target_id,
            location_id=location_id,
            payload=dict(payload or {}),
            reason=reason,
        )
        self.archivio.registra_evento(evento)
        return evento

    def _richiedi_tipo(
        self, mondo_id: str, entity_id: str, tipo_atteso: str
    ) -> EntitaMondo:
        entita = self.archivio.carica_entita(mondo_id, entity_id)
        if entita.entity_type != tipo_atteso:
            raise ErroreStatoMondo(
                f"L'entità “{entita.canonical_name}” non è di tipo {tipo_atteso}."
            )
        return entita

    def _valida_riferimento_opzionale(
        self, mondo_id: str, entity_id: str | None
    ) -> None:
        if entity_id is not None:
            self.archivio.carica_entita(mondo_id, entity_id)

    @staticmethod
    def _aggiornamento(
        entita: EntitaMondo,
        *,
        status: str | None = None,
        location_id: str | None = None,
        holder_id: str | None = None,
        accessibility: bool | None = None,
        condition: str | None = None,
    ) -> AggiornamentoStato:
        return AggiornamentoStato(
            entity_id=entita.entity_id,
            expected_version=entita.version,
            status=entita.status if status is None else status,
            location_id=entita.location_id if location_id is None else location_id,
            holder_id=entita.holder_id if holder_id is None else holder_id,
            accessibility=(
                entita.accessibility if accessibility is None else accessibility
            ),
            condition=entita.condition if condition is None else condition,
            state_data=dict(entita.state_data),
        )

    @classmethod
    def _nuovo_evento(
        cls,
        *,
        mondo_id: str,
        event_type: str,
        actor_id: str | None,
        target_id: str | None,
        location_id: str | None,
        payload: dict[str, object],
        reason: str,
    ) -> EventoMondo:
        try:
            json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError) as errore:
            raise ErroreStatoMondo(
                "I dettagli strutturati dell'evento non sono validi."
            ) from errore
        istante = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        return EventoMondo(
            event_id=uuid.uuid4().hex,
            world_id=mondo_id,
            event_type=cls._testo_non_vuoto(event_type, "tipo evento"),
            occurred_at=istante,
            actor_id=actor_id,
            target_id=target_id,
            location_id=location_id,
            payload=payload,
            reason=cls._testo_non_vuoto(reason, "motivo"),
            created_at=istante,
        )

    @staticmethod
    def _testo_non_vuoto(valore: str, descrizione: str) -> str:
        if not isinstance(valore, str) or not valore.strip():
            raise ErroreStatoMondo(f"Il campo {descrizione} è obbligatorio.")
        return valore.strip()


def importa_entita_da_file(
    file_sorgente: Iterable[FileSorgente],
) -> list[EntitaImportata]:
    """Converte le fotografie archiviate senza accedere alla cartella originale."""

    fotografie = {
        file.percorso_relativo.replace("\\", "/"): file.contenuto
        for file in file_sorgente
    }
    formato_legacy = any(
        nome in fotografie
        for nome in ("characters.json", "locations.json", "items.json")
    )
    personaggi = _leggi_entita_archiviate(
        fotografie, "characters.json", "characters/", "personaggi", obbligatorie=True
    )
    luoghi = _leggi_entita_archiviate(
        fotografie, "locations.json", "locations/", "luoghi",
        obbligatorie=formato_legacy,
    )
    oggetti = _leggi_entita_archiviate(
        fotografie, "items.json", "items/", "oggetti",
        obbligatorie=formato_legacy,
    )

    risultato: list[EntitaImportata] = []
    for dati in personaggi:
        risultato.append(
            EntitaImportata(
                entity_id=_testo_obbligatorio(dati, "id", "identificatore"),
                entity_type=TIPO_PERSONAGGIO,
                canonical_name=_testo_obbligatorio(dati, "name", "nome"),
                canonical_data=dict(dati),
                status=_testo_opzionale(dati.get("status")) or "active",
                location_id=_testo_opzionale(dati.get("location_id")),
                holder_id=None,
                accessibility=_booleano(dati.get("accessible", True), "accessibilità"),
                condition=_testo_opzionale(dati.get("condition")),
                state_data={},
            )
        )

    for dati in luoghi:
        risultato.append(
            EntitaImportata(
                entity_id=_testo_obbligatorio(dati, "id", "identificatore"),
                entity_type=TIPO_LUOGO,
                canonical_name=_testo_obbligatorio(dati, "name", "nome"),
                canonical_data=dict(dati),
                status=_testo_opzionale(dati.get("status")) or "active",
                location_id=None,
                holder_id=None,
                accessibility=_booleano(dati.get("accessible", True), "accessibilità"),
                condition=_testo_opzionale(dati.get("condition")),
                state_data={},
            )
        )

    for dati in oggetti:
        dettagli_stato: dict[str, object] = {}
        if "position" in dati:
            dettagli_stato["position"] = dati["position"]
        risultato.append(
            EntitaImportata(
                entity_id=_testo_obbligatorio(dati, "id", "identificatore"),
                entity_type=TIPO_OGGETTO,
                canonical_name=_testo_obbligatorio(dati, "name", "nome"),
                canonical_data=dict(dati),
                status=_testo_opzionale(dati.get("status")) or "active",
                location_id=_testo_opzionale(dati.get("location_id")),
                holder_id=_testo_opzionale(dati.get("owner_id")),
                accessibility=_booleano(dati.get("accessible", True), "accessibilità"),
                condition=_testo_opzionale(dati.get("condition")),
                state_data=dettagli_stato,
            )
        )

    _valida_riferimenti(risultato)
    return risultato


def _leggi_lista(
    fotografie: Mapping[str, bytes], nome_file: str, descrizione: str
) -> list[dict[str, object]]:
    contenuto = fotografie.get(nome_file)
    if contenuto is None:
        raise ErroreImportazione(
            f"Manca il file archiviato {nome_file} necessario per importare {descrizione}."
        )
    try:
        dati = json.loads(contenuto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as errore:
        raise ErroreImportazione(
            f"Il file archiviato {nome_file} non contiene dati validi in UTF-8."
        ) from errore
    if not isinstance(dati, list) or any(not isinstance(voce, dict) for voce in dati):
        raise ErroreImportazione(
            f"Il file archiviato {nome_file} deve contenere un elenco valido."
        )
    return [dict(voce) for voce in dati]


def _leggi_entita_archiviate(
    fotografie: Mapping[str, bytes],
    nome_aggregato: str,
    prefisso: str,
    descrizione: str,
    *,
    obbligatorie: bool = False,
) -> list[dict[str, object]]:
    """Legge il formato legacy aggregato o i file individuali del formato completo."""

    if nome_aggregato in fotografie:
        return _leggi_lista(fotografie, nome_aggregato, descrizione)
    percorsi = sorted(
        (
            percorso
            for percorso in fotografie
            if percorso.startswith(prefisso) and percorso.casefold().endswith(".json")
        ),
        key=str.casefold,
    )
    if obbligatorie and not percorsi:
        raise ErroreImportazione(
            f"Il pacchetto non contiene file individuali per {descrizione}."
        )
    risultato: list[dict[str, object]] = []
    for percorso in percorsi:
        try:
            dati = json.loads(fotografie[percorso].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as errore:
            raise ErroreImportazione(
                f"Il file archiviato {percorso} non contiene JSON UTF-8 valido."
            ) from errore
        if not isinstance(dati, dict):
            raise ErroreImportazione(
                f"Il file archiviato {percorso} deve contenere una singola entità."
            )
        risultato.append(dict(dati))
    return risultato


def _testo_obbligatorio(
    dati: Mapping[str, object], chiave: str, descrizione: str
) -> str:
    valore = dati.get(chiave)
    if not isinstance(valore, str) or not valore.strip():
        raise ErroreImportazione(
            f"Un'entità importata non contiene un {descrizione} valido."
        )
    return valore.strip()


def _testo_opzionale(valore: object) -> str | None:
    if valore is None:
        return None
    if not isinstance(valore, str) or not valore.strip():
        raise ErroreImportazione("Un riferimento testuale del mini-mondo non è valido.")
    return valore.strip()


def _booleano(valore: object, descrizione: str) -> bool:
    if not isinstance(valore, bool):
        raise ErroreImportazione(
            f"Il valore di {descrizione} di un'entità non è valido."
        )
    return valore


def _valida_riferimenti(entita: list[EntitaImportata]) -> None:
    per_id: dict[str, EntitaImportata] = {}
    for voce in entita:
        if voce.entity_id in per_id:
            raise ErroreImportazione(
                f"L'identificatore entità “{voce.entity_id}” è duplicato."
            )
        per_id[voce.entity_id] = voce

    for voce in entita:
        if voce.location_id is not None:
            luogo = per_id.get(voce.location_id)
            if luogo is None or luogo.entity_type != TIPO_LUOGO:
                raise ErroreImportazione(
                    f"La posizione “{voce.location_id}” non identifica un luogo valido."
                )
        if voce.holder_id is not None:
            possessore = per_id.get(voce.holder_id)
            if possessore is None or possessore.entity_type != TIPO_PERSONAGGIO:
                raise ErroreImportazione(
                    f"Il possessore “{voce.holder_id}” non identifica un personaggio valido."
                )
            if (
                voce.location_id is not None
                and possessore.location_id != voce.location_id
            ):
                raise ErroreImportazione(
                    f"La posizione dell'oggetto “{voce.entity_id}” non è coerente "
                    "con il possessore."
                )
