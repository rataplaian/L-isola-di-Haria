"""Lettura e validazione deterministica di pacchetti da cartella o ZIP."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath

from .errors import (
    ErroreArchivioNonSicuro,
    ErroreImportazione,
    ErroreManifest,
    ErrorePacchettoCompleto,
    ErroreZipNonValido,
)
from .models import FileSorgente
from .package_models import DocumentoCanonico, MediaCanonico, PacchettoMondo
from .world_state import importa_entita_da_file


MAX_FILE_COUNT = 2_000
MAX_FILE_SIZE = 32 * 1024 * 1024
MAX_TOTAL_SIZE = 256 * 1024 * 1024
LEGACY_REQUIRED = frozenset(
    {"world.json", "scenario.md", "characters.json", "locations.json", "items.json"}
)
TEXT_EXTENSIONS = frozenset({".json", ".md", ".txt"})
MEDIA_MIME = {
    ".png": "image/png",
    ".gif": "image/gif",
    ".ppm": "image/x-portable-pixmap",
    ".pgm": "image/x-portable-graymap",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}
ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | frozenset(MEDIA_MIME)


def importa_pacchetto_da_cartella(cartella: str | Path) -> PacchettoMondo:
    sorgente = Path(cartella).expanduser().resolve()
    if not sorgente.is_dir():
        raise ErroreImportazione(
            "La cartella selezionata non esiste o non è leggibile."
        )
    file_sorgente = _fotografa_cartella(sorgente)
    return _costruisci_pacchetto(file_sorgente)


def importa_pacchetto_da_zip(percorso: str | Path) -> PacchettoMondo:
    archivio_path = Path(percorso).expanduser().resolve()
    if not archivio_path.is_file() or archivio_path.suffix.casefold() != ".zip":
        raise ErroreZipNonValido("Seleziona un archivio ZIP valido e leggibile.")
    try:
        with tempfile.TemporaryDirectory(prefix="haria_import_zip_") as temporanea:
            radice = Path(temporanea)
            _estrai_zip_sicuro(archivio_path, radice)
            sorgente = _trova_radice_pacchetto(radice)
            return importa_pacchetto_da_cartella(sorgente)
    except (ErroreImportazione, ErroreArchivioNonSicuro, ErroreZipNonValido):
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as errore:
        raise ErroreZipNonValido(
            "L'archivio ZIP non è valido o non può essere letto."
        ) from errore


def _estrai_zip_sicuro(archivio_path: Path, destinazione: Path) -> None:
    try:
        archivio = zipfile.ZipFile(archivio_path)
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as errore:
        raise ErroreZipNonValido("L'archivio ZIP è corrotto o non valido.") from errore
    with archivio:
        voci = archivio.infolist()
        if len(voci) > MAX_FILE_COUNT:
            raise ErroreArchivioNonSicuro(
                f"L'archivio contiene più di {MAX_FILE_COUNT} voci."
            )
        totale = 0
        visti: set[str] = set()
        for voce in voci:
            relativo = _percorso_sicuro(voce.filename)
            chiave = relativo.casefold()
            if chiave in visti:
                raise ErroreArchivioNonSicuro(
                    "L'archivio contiene percorsi duplicati senza distinzione sicura."
                )
            visti.add(chiave)
            tipo_unix = (voce.external_attr >> 16) & 0o170000
            if tipo_unix == stat.S_IFLNK:
                raise ErroreArchivioNonSicuro(
                    "L'archivio contiene un collegamento simbolico non ammesso."
                )
            if voce.is_dir():
                continue
            if voce.file_size > MAX_FILE_SIZE:
                raise ErroreArchivioNonSicuro(
                    "L'archivio contiene un file più grande del limite consentito."
                )
            totale += voce.file_size
            if totale > MAX_TOTAL_SIZE:
                raise ErroreArchivioNonSicuro(
                    "La dimensione complessiva dell'archivio supera il limite consentito."
                )
            destinazione_file = destinazione.joinpath(*PurePosixPath(relativo).parts)
            destinazione_file.parent.mkdir(parents=True, exist_ok=True)
            with archivio.open(voce, "r") as origine, destinazione_file.open("wb") as uscita:
                shutil.copyfileobj(origine, uscita, length=1024 * 1024)


def _trova_radice_pacchetto(radice: Path) -> Path:
    if (radice / "world.json").is_file():
        return radice
    candidate = sorted(
        {percorso.parent for percorso in radice.rglob("world.json")},
        key=lambda percorso: percorso.as_posix().casefold(),
    )
    if len(candidate) != 1:
        raise ErrorePacchettoCompleto(
            "Lo ZIP deve contenere un solo pacchetto con world.json."
        )
    scelta = candidate[0]
    estranei = [
        percorso for percorso in radice.rglob("*")
        if percorso.is_file() and scelta not in percorso.parents
    ]
    if estranei:
        raise ErrorePacchettoCompleto(
            "Lo ZIP contiene file esterni alla radice del pacchetto."
        )
    return scelta


def _fotografa_cartella(sorgente: Path) -> tuple[FileSorgente, ...]:
    percorsi = sorted(
        (percorso for percorso in sorgente.rglob("*") if percorso.is_file()),
        key=lambda percorso: percorso.relative_to(sorgente).as_posix().casefold(),
    )
    if len(percorsi) > MAX_FILE_COUNT:
        raise ErroreImportazione(
            f"Il pacchetto contiene più di {MAX_FILE_COUNT} file."
        )
    risultato: list[FileSorgente] = []
    visti: set[str] = set()
    totale = 0
    try:
        for percorso in percorsi:
            relativo = _percorso_sicuro(percorso.relative_to(sorgente).as_posix())
            chiave = relativo.casefold()
            if chiave in visti:
                raise ErroreImportazione(
                    "Il pacchetto contiene percorsi duplicati ignorando le maiuscole."
                )
            visti.add(chiave)
            if percorso.is_symlink():
                raise ErroreImportazione(
                    "Il pacchetto contiene un collegamento simbolico non ammesso."
                )
            dimensione = percorso.stat().st_size
            if dimensione > MAX_FILE_SIZE:
                raise ErroreImportazione(
                    f"Il file {relativo} supera il limite di dimensione consentito."
                )
            totale += dimensione
            if totale > MAX_TOTAL_SIZE:
                raise ErroreImportazione(
                    "La dimensione complessiva del pacchetto supera il limite consentito."
                )
            estensione = PurePosixPath(relativo).suffix.casefold()
            if estensione not in ALLOWED_EXTENSIONS:
                raise ErroreImportazione(
                    f"Il tipo di file {estensione or '(senza estensione)'} non è ammesso."
                )
            contenuto = percorso.read_bytes()
            risultato.append(
                FileSorgente(
                    percorso_relativo=relativo,
                    contenuto=contenuto,
                    sha256=hashlib.sha256(contenuto).hexdigest(),
                )
            )
    except OSError as errore:
        raise ErroreImportazione(
            "Non è stato possibile leggere integralmente il pacchetto."
        ) from errore
    return tuple(risultato)


def _percorso_sicuro(valore: str) -> str:
    if not isinstance(valore, str) or not valore or "\x00" in valore:
        raise ErroreArchivioNonSicuro("Il pacchetto contiene un percorso non valido.")
    testo = valore.replace("\\", "/")
    posix = PurePosixPath(testo)
    windows = PureWindowsPath(valore)
    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ErroreArchivioNonSicuro("Il pacchetto contiene un percorso assoluto.")
    if any(parte in {"", ".", ".."} for parte in posix.parts):
        raise ErroreArchivioNonSicuro(
            "Il pacchetto contiene un percorso con attraversamento non sicuro."
        )
    if any(parte.startswith(".") or parte.casefold() == "__macosx" for parte in posix.parts):
        raise ErroreImportazione(
            "Il pacchetto contiene file tecnici nascosti non ammessi."
        )
    return posix.as_posix()


def _valida_rappresentazioni_entita(
    file_percorso: Mapping[str, FileSorgente],
) -> None:
    for aggregato, prefisso, descrizione in (
        ("characters.json", "characters/", "personaggi"),
        ("locations.json", "locations/", "luoghi"),
        ("items.json", "items/", "oggetti"),
    ):
        individuali = any(
            percorso.startswith(prefisso) and percorso.casefold().endswith(".json")
            for percorso in file_percorso
        )
        if aggregato in file_percorso and individuali:
            raise ErroreImportazione(
                f"Il pacchetto contiene sia {aggregato} sia file individuali per {descrizione}."
            )


def _costruisci_pacchetto(file_sorgente: tuple[FileSorgente, ...]) -> PacchettoMondo:
    file_percorso = {file.percorso_relativo: file for file in file_sorgente}
    _valida_rappresentazioni_entita(file_percorso)
    if "world.json" not in file_percorso:
        raise ErrorePacchettoCompleto("Nel pacchetto manca il file world.json.")
    world = _leggi_json_oggetto(file_percorso["world.json"], "world.json")
    world_id = _testo(world, "id", "identificatore del mondo")
    title = _testo(world, "title", "titolo del mondo")
    language = str(world.get("language") or "it")
    complete = "manifest.json" in file_percorso or any(
        percorso.startswith(("characters/", "locations/", "items/", "lore/", "timeline/", "media/"))
        for percorso in file_percorso
    )
    if not complete:
        mancanti = sorted(LEGACY_REQUIRED - set(file_percorso))
        if mancanti:
            raise ErroreImportazione(
                "Mancano i file obbligatori per l'importazione: " + ", ".join(mancanti) + "."
            )
        scenario = _testo_utf8(file_percorso["scenario.md"], "scenario.md")
        impostazioni = _impostazioni(world)
        entita = tuple(importa_entita_da_file(file_sorgente))
        return PacchettoMondo(
            world_id, title, language, scenario, impostazioni, file_sorgente,
            entita, (), (), False
        )

    manifest_file = file_percorso.get("manifest.json")
    if manifest_file is None:
        raise ErroreManifest("Il pacchetto completo richiede manifest.json.")
    manifest = _leggi_json_oggetto(manifest_file, "manifest.json")
    if manifest.get("world_id") != world_id:
        raise ErroreManifest("Il manifest non corrisponde al mondo dichiarato.")
    _valida_manifest(manifest, file_percorso)
    scenario_file = file_percorso.get("scenario.md")
    if scenario_file is None:
        raise ErrorePacchettoCompleto("Il pacchetto completo richiede scenario.md.")
    scenario = _testo_utf8(scenario_file, "scenario.md")
    entita = tuple(importa_entita_da_file(file_sorgente))
    _valida_player_character(world, entita)
    documenti = _documenti(world_id, manifest, file_percorso)
    media = _media(world_id, manifest, file_percorso, entita)
    _valida_immagini_entita(
        entita, {voce.relative_path: voce for voce in media}
    )
    return PacchettoMondo(
        world_id, title, language, scenario, _impostazioni(world), file_sorgente,
        entita, documenti, media, True
    )


def _valida_manifest(
    manifest: Mapping[str, object], file_percorso: Mapping[str, FileSorgente]
) -> None:
    voci = manifest.get("files")
    if not isinstance(voci, list) or any(not isinstance(voce, dict) for voce in voci):
        raise ErroreManifest("Il manifest deve contenere un elenco files valido.")
    dichiarati: dict[str, str] = {}
    chiavi_percorso: set[str] = set()
    for voce in voci:
        percorso = _percorso_sicuro(str(voce.get("path") or ""))
        sha256 = str(voce.get("sha256") or "").casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ErroreManifest(f"L'hash dichiarato per {percorso} non è valido.")
        if percorso.casefold() in chiavi_percorso:
            raise ErroreManifest("Il manifest contiene un percorso duplicato.")
        chiavi_percorso.add(percorso.casefold())
        dichiarati[percorso] = sha256
    attesi = set(file_percorso) - {"manifest.json"}
    if set(dichiarati) != attesi:
        raise ErroreManifest(
            "Il manifest non elenca esattamente tutti i file del pacchetto."
        )
    for percorso, sha256 in dichiarati.items():
        if file_percorso[percorso].sha256 != sha256:
            raise ErroreManifest(f"L'hash SHA-256 di {percorso} non corrisponde.")


def _documenti(
    world_id: str,
    manifest: Mapping[str, object],
    file_percorso: Mapping[str, FileSorgente],
) -> tuple[DocumentoCanonico, ...]:
    dichiarazioni = manifest.get("documents", [])
    if not isinstance(dichiarazioni, list) or any(not isinstance(v, dict) for v in dichiarazioni):
        raise ErroreManifest("La sezione documents del manifest non è valida.")
    per_percorso = _dichiarazioni_per_percorso(dichiarazioni, "documento")
    percorsi = [
        percorso for percorso in file_percorso
        if percorso in {"scenario.md", "rules.md", "style.md"}
        or percorso.startswith("lore/")
        or percorso.startswith("timeline/")
    ]
    estranei = set(per_percorso) - set(percorsi)
    if estranei:
        raise ErroreManifest(
            "Il manifest dichiara un documento inesistente o fuori dalle cartelle previste."
        )
    risultato: list[DocumentoCanonico] = []
    ids: set[str] = set()
    for ordine, percorso in enumerate(sorted(percorsi, key=str.casefold), start=1):
        file = file_percorso[percorso]
        contenuto = _contenuto_documento(file, percorso)
        dichiarazione = per_percorso.get(percorso, {})
        tipo = str(dichiarazione.get("type") or _tipo_documento(percorso))
        titolo = str(dichiarazione.get("title") or _titolo_percorso(percorso))
        document_id = str(
            dichiarazione.get("id")
            or _id_deterministico("doc", world_id, percorso)
        )
        if not document_id.strip() or document_id in ids:
            raise ErroreImportazione("Un identificatore documento è vuoto o duplicato.")
        ids.add(document_id)
        metadata = dichiarazione.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ErroreManifest("I metadati di un documento non sono validi.")
        risultato.append(
            DocumentoCanonico(
                world_id, document_id, tipo, titolo, percorso, contenuto,
                _ordine(dichiarazione.get("order", ordine), percorso),
                dict(metadata), file.sha256
            )
        )
    return tuple(sorted(risultato, key=lambda v: (v.sort_order, v.document_id)))


def _media(
    world_id: str,
    manifest: Mapping[str, object],
    file_percorso: Mapping[str, FileSorgente],
    entita: tuple[object, ...],
) -> tuple[MediaCanonico, ...]:
    dichiarazioni = manifest.get("media", [])
    if not isinstance(dichiarazioni, list) or any(not isinstance(v, dict) for v in dichiarazioni):
        raise ErroreManifest("La sezione media del manifest non è valida.")
    per_percorso = _dichiarazioni_per_percorso(dichiarazioni, "media")
    percorsi = sorted(
        (percorso for percorso in file_percorso if percorso.startswith("media/")),
        key=str.casefold,
    )
    estranei = set(per_percorso) - set(percorsi)
    if estranei:
        raise ErroreManifest("Il manifest dichiara un media inesistente.")
    entity_ids = {getattr(voce, "entity_id") for voce in entita}
    risultato: list[MediaCanonico] = []
    ids: set[str] = set()
    for ordine, percorso in enumerate(percorsi, start=1):
        file = file_percorso[percorso]
        estensione = PurePosixPath(percorso).suffix.casefold()
        mime = MEDIA_MIME.get(estensione)
        if mime is None:
            raise ErroreImportazione(
                f"Il file {percorso} usa un formato non ammesso nella cartella media."
            )
        dichiarazione = per_percorso.get(percorso, {})
        entity_id = dichiarazione.get("entity_id")
        if entity_id is not None and entity_id not in entity_ids:
            raise ErroreImportazione(
                f"Il media {percorso} fa riferimento a un'entità inesistente."
            )
        media_id = str(
            dichiarazione.get("id")
            or _id_deterministico("media", world_id, percorso)
        )
        if not media_id.strip() or media_id in ids:
            raise ErroreImportazione("Un identificatore media è vuoto o duplicato.")
        ids.add(media_id)
        metadata = dichiarazione.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ErroreManifest("I metadati di un media non sono validi.")
        risultato.append(
            MediaCanonico(
                world_id, media_id, percorso,
                str(dichiarazione.get("type") or "immagine"), mime, file.sha256,
                str(dichiarazione.get("title") or _titolo_percorso(percorso)),
                str(dichiarazione.get("alt_text") or ""),
                str(entity_id) if entity_id is not None else None,
                _ordine(dichiarazione.get("order", ordine), percorso), dict(metadata)
            )
        )
    return tuple(sorted(risultato, key=lambda v: (v.sort_order, v.media_id)))


def _valida_player_character(world: Mapping[str, object], entita: tuple[object, ...]) -> None:
    player = world.get("player_character_id")
    if player is None:
        return
    personaggi = {
        getattr(voce, "entity_id") for voce in entita
        if getattr(voce, "entity_type") == "personaggio"
    }
    if player not in personaggi:
        raise ErroreImportazione(
            "Il personaggio giocante indicato in world.json non esiste."
        )


def _valida_immagini_entita(
    entita: tuple[object, ...], media_percorso: Mapping[str, MediaCanonico]
) -> None:
    ids = {getattr(voce, "entity_id") for voce in entita}
    for voce in entita:
        immagine = getattr(voce, "canonical_data").get("image")
        if immagine is not None and immagine not in media_percorso:
            raise ErroreImportazione(
                f"L'immagine indicata per {getattr(voce, 'canonical_name')} non esiste."
            )
        if (
            immagine is not None
            and getattr(voce, "entity_type") == "personaggio"
            and media_percorso[immagine].entity_id != getattr(voce, "entity_id")
        ):
            raise ErroreImportazione(
                f"L'immagine indicata per {getattr(voce, 'canonical_name')} "
                "non è associata a quel personaggio."
            )
        relazioni = getattr(voce, "canonical_data").get("relationships", [])
        if relazioni is None:
            continue
        if not isinstance(relazioni, list):
            raise ErroreImportazione("Le relazioni di un personaggio non sono valide.")
        for relazione in relazioni:
            if not isinstance(relazione, dict):
                raise ErroreImportazione("Una relazione tra entità non è valida.")
            riferimento = relazione.get("entity_id")
            if riferimento is not None and riferimento not in ids:
                raise ErroreImportazione(
                    "Una relazione del pacchetto fa riferimento a un'entità inesistente."
                )


def _dichiarazioni_per_percorso(
    dichiarazioni: list[object], descrizione: str
) -> dict[str, Mapping[str, object]]:
    risultato: dict[str, Mapping[str, object]] = {}
    chiavi: set[str] = set()
    for dichiarazione in dichiarazioni:
        assert isinstance(dichiarazione, dict)
        percorso = _percorso_sicuro(str(dichiarazione.get("path") or ""))
        chiave = percorso.casefold()
        if chiave in chiavi:
            raise ErroreManifest(
                f"Il manifest dichiara due volte lo stesso {descrizione}."
            )
        chiavi.add(chiave)
        risultato[percorso] = dichiarazione
    return risultato


def _contenuto_documento(file: FileSorgente, percorso: str) -> str:
    testo = _testo_utf8(file, percorso)
    if not percorso.startswith("timeline/") or not percorso.casefold().endswith(".json"):
        return testo
    try:
        dati = json.loads(testo)
    except json.JSONDecodeError as errore:
        raise ErroreImportazione(
            f"Il documento timeline {percorso} non contiene JSON valido."
        ) from errore
    if not isinstance(dati, dict):
        raise ErroreImportazione(
            f"Il documento timeline {percorso} deve contenere un oggetto."
        )
    contenuto = dati.get("content")
    if not isinstance(contenuto, str) or not contenuto.strip():
        raise ErroreImportazione(
            f"Il documento timeline {percorso} non contiene testo leggibile."
        )
    return contenuto


def _ordine(valore: object, percorso: str) -> int:
    if isinstance(valore, bool) or not isinstance(valore, int) or valore < 0:
        raise ErroreManifest(f"L'ordine dichiarato per {percorso} non è valido.")
    return valore


def _leggi_json_oggetto(file: FileSorgente, nome: str) -> dict[str, object]:
    try:
        dati = json.loads(file.contenuto.decode("utf-8"))
    except UnicodeDecodeError as errore:
        raise ErroreImportazione(f"Il file {nome} non usa UTF-8 valido.") from errore
    except json.JSONDecodeError as errore:
        raise ErroreImportazione(f"Il file {nome} non contiene JSON valido.") from errore
    if not isinstance(dati, dict):
        raise ErroreImportazione(f"Il file {nome} deve contenere un oggetto.")
    return dict(dati)


def _testo_utf8(file: FileSorgente, nome: str) -> str:
    try:
        return file.contenuto.decode("utf-8")
    except UnicodeDecodeError as errore:
        raise ErroreImportazione(f"Il file {nome} non usa UTF-8 valido.") from errore


def _testo(dati: Mapping[str, object], chiave: str, descrizione: str) -> str:
    valore = dati.get(chiave)
    if not isinstance(valore, str) or not valore.strip():
        raise ErroreImportazione(f"Nel file world.json manca {descrizione}.")
    return valore.strip()


def _impostazioni(world: Mapping[str, object]) -> dict[str, str]:
    grezze = world.get("narrative_style", {})
    if not isinstance(grezze, dict):
        raise ErroreImportazione("Le impostazioni narrative non sono valide.")
    risultato: dict[str, str] = {}
    for chiave, valore in grezze.items():
        if not isinstance(chiave, str) or isinstance(valore, (dict, list)):
            raise ErroreImportazione("Le impostazioni narrative devono essere semplici.")
        risultato[chiave] = "" if valore is None else str(valore)
    return risultato


def _id_deterministico(prefisso: str, world_id: str, percorso: str) -> str:
    percorso_normalizzato = _percorso_sicuro(percorso).casefold()
    impronta = hashlib.sha256(
        "\x00".join((prefisso, world_id, percorso_normalizzato)).encode("utf-8")
    ).hexdigest()
    return f"{prefisso}_{impronta}"


def _tipo_documento(percorso: str) -> str:
    if percorso == "scenario.md":
        return "scenario"
    if percorso == "rules.md":
        return "regole"
    if percorso == "style.md":
        return "stile"
    if percorso.startswith("timeline/"):
        return "timeline"
    return "lore"


def _titolo_percorso(percorso: str) -> str:
    return PurePosixPath(percorso).stem.replace("_", " ").replace("-", " ").strip().capitalize()
