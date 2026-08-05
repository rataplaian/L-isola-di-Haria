"""Costruisce il pacchetto Haria locale senza alterare o pubblicare le sorgenti."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import unicodedata
from pathlib import Path


def _sha256(percorso: Path) -> str:
    return hashlib.sha256(percorso.read_bytes()).hexdigest()


def _normalizza(nome: str) -> str:
    base = unicodedata.normalize("NFKD", nome.casefold())
    senza_accenti = "".join(carattere for carattere in base if not unicodedata.combining(carattere))
    return re.sub(r"[\s_-]+", "", senza_accenti)


def _id_personaggio(nome: str) -> str:
    base = unicodedata.normalize("NFKD", nome.casefold())
    base = "".join(carattere for carattere in base if not unicodedata.combining(carattere))
    return re.sub(r"[^a-z0-9]+", "_", base).strip("_")


def _id_deterministico(prefisso: str, world_id: str, percorso: str) -> str:
    normalizzato = Path(percorso.replace("\\", "/")).as_posix().casefold()
    impronta = hashlib.sha256(
        "\0".join((prefisso, world_id, normalizzato)).encode("utf-8")
    ).hexdigest()
    return f"{prefisso}_{impronta}"


def _scrivi_json(percorso: Path, dati: object) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(
        json.dumps(dati, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def costruisci(sorgente: Path, destinazione: Path) -> dict[str, object]:
    profili_path = sorgente / "personaggi" / "profili_cast_iniziale.json"
    scenario_md = sorgente / "scenario" / "scenario_iniziale.md"
    scenario_json = sorgente / "scenario" / "scenario_iniziale.json"
    immagini = sorgente / "immagini"
    if not all(percorso.is_file() for percorso in (profili_path, scenario_md, scenario_json)):
        raise ValueError("I testi sorgente dedicati di Haria sono incompleti.")
    if not immagini.is_dir():
        raise ValueError("La cartella delle immagini di Haria non è leggibile.")
    if destinazione.exists():
        raise ValueError("La destinazione locale esiste già; non viene sovrascritta.")

    profili_grezzi = json.loads(profili_path.read_text(encoding="utf-8"))
    if not isinstance(profili_grezzi, dict):
        raise ValueError("Il file dei profili non contiene un oggetto valido.")
    profili = {
        nome: dati for nome, dati in profili_grezzi.items()
        if nome != "Galleria visiva del cast iniziale" and isinstance(dati, dict)
    }
    id_per_nome = {nome: _id_personaggio(nome) for nome in profili}
    nomi_normalizzati = {_normalizza(nome): nome for nome in profili}
    associazioni: dict[str, str] = {}
    ambigui: list[str] = []
    senza_personaggio: list[str] = []

    # Alias verificato dai nomi espliciti presenti nei due materiali locali.
    alias_verificati = {
        "Ahri (Silvia).png": "Silvia detta Ahri",
    }
    copertina = "copertina Isola di Haria.png"
    for file in sorted(immagini.iterdir(), key=lambda voce: voce.name.casefold()):
        if not file.is_file():
            continue
        if file.name == copertina:
            continue
        nome = alias_verificati.get(file.name)
        if nome is None:
            normalizzato = _normalizza(file.stem)
            candidati = [
                nome_profilo for chiave, nome_profilo in nomi_normalizzati.items()
                if normalizzato == chiave
            ]
            if not candidati:
                senza_numero = re.sub(r"\d+$", "", normalizzato)
                candidati = [
                    nome_profilo for chiave, nome_profilo in nomi_normalizzati.items()
                    if senza_numero == chiave
                ]
            if len(candidati) == 1:
                nome = candidati[0]
            elif len(candidati) > 1:
                ambigui.append(file.name)
                continue
        if nome is None:
            senza_personaggio.append(file.name)
        else:
            associazioni[file.name] = nome

    destinazione.mkdir(parents=True)
    _scrivi_json(
        destinazione / "world.json",
        {
            "id": "haria_local_complete",
            "title": "L'isola di Haria",
            "language": "it",
            "player_character_id": id_per_nome["Luca"],
        },
    )
    shutil.copyfile(scenario_md, destinazione / "scenario.md")
    (destinazione / "source").mkdir()
    shutil.copyfile(profili_path, destinazione / "source" / profili_path.name)
    shutil.copyfile(scenario_json, destinazione / "source" / scenario_json.name)
    shutil.copyfile(scenario_md, destinazione / "source" / scenario_md.name)

    media_manifest: list[dict[str, object]] = []
    immagini_per_personaggio: dict[str, list[str]] = {nome: [] for nome in profili}
    for nome_file, nome_personaggio in associazioni.items():
        sorgente_file = immagini / nome_file
        relativo = f"media/characters/{nome_file}"
        destinazione_file = destinazione.joinpath(*relativo.split("/"))
        destinazione_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sorgente_file, destinazione_file)
        immagini_per_personaggio[nome_personaggio].append(relativo)
        media_manifest.append(
            {
                "path": relativo,
                "id": _id_deterministico(
                    "media", "haria_local_complete", relativo
                ),
                "type": "immagine_personaggio",
                "title": f"Immagine di {nome_personaggio}",
                "alt_text": f"Riferimento visivo di {nome_personaggio}",
                "entity_id": id_per_nome[nome_personaggio],
            }
        )
    percorso_copertina = immagini / copertina
    if percorso_copertina.is_file():
        relativo = f"media/{copertina}"
        (destinazione / "media").mkdir(exist_ok=True)
        shutil.copyfile(percorso_copertina, destinazione / relativo)
        media_manifest.append(
            {
                "path": relativo,
                "id": _id_deterministico(
                    "media", "haria_local_complete", relativo
                ),
                "type": "copertina",
                "title": "Copertina di Haria",
                "alt_text": "Copertina del mondo di Haria",
            }
        )

    for nome, dati in profili.items():
        personaggio = dict(dati)
        personaggio["id"] = id_per_nome[nome]
        personaggio["name"] = nome
        immagini_personaggio = sorted(immagini_per_personaggio[nome], key=str.casefold)
        if immagini_personaggio:
            preferita = next(
                (voce for voce in immagini_personaggio if not re.search(r"\s2\.png$", voce, re.IGNORECASE)),
                immagini_personaggio[0],
            )
            personaggio["image"] = preferita
        _scrivi_json(
            destinazione / "characters" / f"{id_per_nome[nome]}.json",
            personaggio,
        )

    inventario = [
        {
            "file": file.name,
            "extension": file.suffix.casefold(),
            "size": file.stat().st_size,
            "sha256": _sha256(file),
            "character": associazioni.get(file.name),
        }
        for file in sorted(immagini.iterdir(), key=lambda voce: voce.name.casefold())
        if file.is_file()
    ]
    personaggi_senza_immagine = sorted(
        (nome for nome, percorsi in immagini_per_personaggio.items() if not percorsi),
        key=str.casefold,
    )
    rapporto = {
        "inventory": inventario,
        "certain_associations": [
            {"file": nome_file, "character": nome}
            for nome_file, nome in sorted(associazioni.items(), key=lambda voce: voce[0].casefold())
        ],
        "unmatched_images": sorted(senza_personaggio, key=str.casefold),
        "characters_without_image": personaggi_senza_immagine,
        "ambiguous_or_duplicate_names": sorted(ambigui, key=str.casefold),
    }
    _scrivi_json(destinazione / "LOCAL_IMPORT_REPORT.json", rapporto)

    file_manifest = [
        {
            "path": file.relative_to(destinazione).as_posix(),
            "sha256": _sha256(file),
        }
        for file in sorted(destinazione.rglob("*"))
        if file.is_file() and file.name != "manifest.json"
    ]
    _scrivi_json(
        destinazione / "manifest.json",
        {
            "world_id": "haria_local_complete",
            "files": file_manifest,
            "documents": [],
            "media": [
                {**voce, "order": ordine}
                for ordine, voce in enumerate(
                    sorted(media_manifest, key=lambda dato: str(dato["path"]).casefold()),
                    start=1,
                )
            ],
        },
    )
    return rapporto


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    rapporto = costruisci(args.source.resolve(), args.destination.resolve())
    print(json.dumps(rapporto, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
