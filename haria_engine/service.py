"""Importazione, versionamento, ripristino ed esportazione dei mondi."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from .errors import ErroreEsportazione, ErroreImportazione
from .models import FileSorgente, Mondo, RisultatoEsportazione, VersioneMondo
from .storage import ArchivioSQLite


FILE_OBBLIGATORI = ("world.json", "scenario.md")


class ServizioMondi:
    """API applicativa indipendente dall'interfaccia grafica."""

    def __init__(self, percorso_database: str | Path) -> None:
        self.archivio = ArchivioSQLite(percorso_database)

    def importa_da_cartella(self, cartella_sorgente: str | Path) -> Mondo:
        sorgente = Path(cartella_sorgente).expanduser().resolve()
        if not sorgente.is_dir():
            raise ErroreImportazione("La cartella selezionata non esiste o non è leggibile.")

        mancanti = [nome for nome in FILE_OBBLIGATORI if not (sorgente / nome).is_file()]
        if mancanti:
            elenco = ", ".join(mancanti)
            raise ErroreImportazione(
                f"Mancano i file obbligatori per l'importazione: {elenco}."
            )

        dati_mondo = self._leggi_world_json(sorgente / "world.json")
        mondo_id = self._campo_testuale(dati_mondo, "id", "identificatore")
        titolo = self._campo_testuale(dati_mondo, "title", "titolo")
        lingua = str(dati_mondo.get("language") or "it")
        scenario = self._leggi_testo(sorgente / "scenario.md", "scenario.md")
        impostazioni = self._leggi_impostazioni(dati_mondo)
        file_sorgente = self._fotografa_file_sorgente(sorgente)

        return self.archivio.importa_mondo(
            mondo_id=mondo_id,
            titolo=titolo,
            lingua=lingua,
            percorso_sorgente=str(sorgente),
            scenario=scenario,
            impostazioni_narrative=impostazioni,
            file_sorgente=file_sorgente,
        )

    def _leggi_world_json(self, percorso: Path) -> dict[str, object]:
        try:
            dati = json.loads(percorso.read_text(encoding="utf-8"))
        except UnicodeDecodeError as errore:
            raise ErroreImportazione(
                "Il file world.json non usa una codifica UTF-8 valida."
            ) from errore
        except json.JSONDecodeError as errore:
            raise ErroreImportazione(
                f"Il file world.json non è valido (riga {errore.lineno})."
            ) from errore
        except OSError as errore:
            raise ErroreImportazione("Impossibile leggere il file world.json.") from errore
        if not isinstance(dati, dict):
            raise ErroreImportazione("Il file world.json deve descrivere un singolo mondo.")
        return dati

    @staticmethod
    def _campo_testuale(
        dati: Mapping[str, object], chiave: str, nome_italiano: str
    ) -> str:
        valore = dati.get(chiave)
        if not isinstance(valore, str) or not valore.strip():
            raise ErroreImportazione(
                f"Nel file world.json manca il campo {nome_italiano}."
            )
        return valore.strip()

    @staticmethod
    def _leggi_testo(percorso: Path, nome: str) -> str:
        try:
            return percorso.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as errore:
            raise ErroreImportazione(
                f"Impossibile leggere {nome} come testo UTF-8."
            ) from errore

    @staticmethod
    def _leggi_impostazioni(dati: Mapping[str, object]) -> dict[str, str]:
        grezze = dati.get("narrative_style", {})
        if grezze is None:
            return {}
        if not isinstance(grezze, dict):
            raise ErroreImportazione(
                "Le impostazioni narrative in world.json non hanno un formato valido."
            )
        impostazioni: dict[str, str] = {}
        for chiave, valore in grezze.items():
            if not isinstance(chiave, str) or isinstance(valore, (dict, list)):
                raise ErroreImportazione(
                    "Le impostazioni narrative devono contenere campi testuali semplici."
                )
            impostazioni[chiave] = "" if valore is None else str(valore)
        return impostazioni

    @staticmethod
    def _fotografa_file_sorgente(sorgente: Path) -> list[FileSorgente]:
        risultato: list[FileSorgente] = []
        try:
            percorsi = sorted(
                (percorso for percorso in sorgente.rglob("*") if percorso.is_file()),
                key=lambda percorso: percorso.as_posix().casefold(),
            )
            for percorso in percorsi:
                contenuto = percorso.read_bytes()
                risultato.append(
                    FileSorgente(
                        percorso_relativo=percorso.relative_to(sorgente).as_posix(),
                        contenuto=contenuto,
                        sha256=hashlib.sha256(contenuto).hexdigest(),
                    )
                )
        except OSError as errore:
            raise ErroreImportazione(
                "Non è stato possibile leggere tutti i file della mini-Bibbia."
            ) from errore
        return risultato

    def elenca_mondi(self) -> list[Mondo]:
        return self.archivio.elenca_mondi()

    def carica_mondo(self, mondo_id: str) -> Mondo:
        return self.archivio.carica_mondo(mondo_id)

    def salva(
        self,
        mondo_id: str,
        scenario: str,
        impostazioni_narrative: Mapping[str, str],
    ) -> Mondo:
        return self.archivio.salva_versione(
            mondo_id, scenario, impostazioni_narrative, "Salvataggio manuale"
        )

    def cronologia(self, mondo_id: str) -> list[VersioneMondo]:
        return self.archivio.elenca_versioni(mondo_id)

    def ripristina(self, mondo_id: str, numero_versione: int) -> Mondo:
        versione = self.archivio.carica_versione(mondo_id, numero_versione)
        return self.archivio.salva_versione(
            mondo_id,
            versione.scenario,
            versione.impostazioni_narrative,
            f"Ripristino della versione {numero_versione}",
        )

    def esporta(
        self, mondo_id: str, cartella_destinazione: str | Path
    ) -> RisultatoEsportazione:
        mondo = self.archivio.carica_mondo(mondo_id)
        base = Path(cartella_destinazione).expanduser().resolve()
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError as errore:
            raise ErroreEsportazione(
                "Non è possibile creare la cartella di destinazione."
            ) from errore
        if not base.is_dir():
            raise ErroreEsportazione("La destinazione scelta non è una cartella.")

        nome_sicuro = re.sub(r"[^A-Za-z0-9._-]+", "-", mondo.id).strip("-.")
        nome_sicuro = nome_sicuro or "mondo"
        cartella = base / f"{nome_sicuro}_export_v{mondo.versione_corrente}"
        progressivo = 2
        while cartella.exists():
            cartella = base / (
                f"{nome_sicuro}_export_v{mondo.versione_corrente}_{progressivo}"
            )
            progressivo += 1

        cartella_temporanea: Path | None = None
        try:
            cartella_temporanea = Path(
                tempfile.mkdtemp(prefix=".haria_export_", dir=base)
            )
            self._scrivi_esportazione(mondo, cartella_temporanea)
            cartella_temporanea.rename(cartella)
            cartella_temporanea = None
        except ErroreEsportazione:
            self._rimuovi_cartella_temporanea(cartella_temporanea)
            raise
        except (OSError, ValueError, json.JSONDecodeError) as errore:
            self._rimuovi_cartella_temporanea(cartella_temporanea)
            raise ErroreEsportazione(
                "L'esportazione non è riuscita. Nessuna cartella parziale è stata "
                "conservata e nessun file sorgente è stato modificato."
            ) from errore

        return RisultatoEsportazione(
            cartella=cartella, versione=mondo.versione_corrente
        )

    def _scrivi_esportazione(self, mondo: Mondo, cartella: Path) -> None:
        """Prepara l'intero pacchetto in una cartella non ancora pubblicata."""

        for file in self.archivio.file_sorgente(mondo.id):
            relativo = PurePosixPath(file.percorso_relativo)
            if relativo.is_absolute() or ".." in relativo.parts:
                raise ErroreEsportazione(
                    "Il pacchetto importato contiene un percorso non sicuro."
                )
            destinazione = cartella.joinpath(*relativo.parts)
            destinazione.parent.mkdir(parents=True, exist_ok=True)
            destinazione.write_bytes(file.contenuto)

        (cartella / "scenario.md").write_text(mondo.scenario, encoding="utf-8")
        percorso_world = cartella / "world.json"
        dati_world = json.loads(percorso_world.read_text(encoding="utf-8"))
        dati_world["scenario"] = self._scenario_senza_intestazione(mondo.scenario)
        dati_world["narrative_style"] = mondo.impostazioni_narrative
        dati_world["version"] = mondo.versione_corrente
        percorso_world.write_text(
            json.dumps(dati_world, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _rimuovi_cartella_temporanea(cartella: Path | None) -> None:
        if cartella is None or not cartella.exists():
            return
        try:
            shutil.rmtree(cartella)
        except OSError as errore:
            raise ErroreEsportazione(
                "L'esportazione è fallita e non è stato possibile rimuovere la "
                "cartella temporanea incompleta."
            ) from errore

    @staticmethod
    def _scenario_senza_intestazione(scenario: str) -> str:
        righe = scenario.splitlines()
        if righe and righe[0].strip().casefold() == "# scenario":
            righe = righe[1:]
            while righe and not righe[0].strip():
                righe = righe[1:]
        return "\n".join(righe).strip()

    def chiudi(self) -> None:
        self.archivio.chiudi()

    def __enter__(self) -> "ServizioMondi":
        return self

    def __exit__(self, *_: object) -> None:
        self.chiudi()

