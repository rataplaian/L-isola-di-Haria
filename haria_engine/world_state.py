"""Modelli e validazione dei dati canonici e dello stato corrente."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .errors import ErroreImportazione
from .models import FileSorgente


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


def importa_entita_da_file(
    file_sorgente: Iterable[FileSorgente],
) -> list[EntitaImportata]:
    """Converte le fotografie archiviate senza accedere alla cartella originale."""

    fotografie = {
        file.percorso_relativo.replace("\\", "/"): file.contenuto
        for file in file_sorgente
    }
    personaggi = _leggi_lista(fotografie, "characters.json", "personaggi")
    luoghi = _leggi_lista(fotografie, "locations.json", "luoghi")
    oggetti = _leggi_lista(fotografie, "items.json", "oggetti")

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
