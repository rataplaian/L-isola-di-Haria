"""Contesto e validazione applicativa dell'anteprima narrativa."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .ai_models import MessaggioChat
from .errors import ErroreHaria, ErroreTurnoNarrativo
from .memories import MemoriaPersonaggio
from .models import FileSorgente, Mondo
from .narrative_models import TurnoNarrativoProposto
from .narrative_parser import ErroreOutputNarrativo, parse_output_narrativo
from .narrative_prompt import (
    ContestoTurnoNarrativo,
    costruisci_messaggi_turno,
    formatta_prompt_visibile,
)
from .package_models import DocumentoCanonico
from .validation import ServizioValidazione
from .world_state import EntitaMondo, TIPO_PERSONAGGIO


MAX_CRONOLOGIA_TURNO = 20
MAX_MEMORIE_TURNO = 100


class ArchivioLetturaNarrativa(Protocol):
    def carica_mondo(self, mondo_id: str) -> Mondo: ...

    def file_sorgente(self, mondo_id: str) -> list[FileSorgente]: ...

    def elenca_entita(
        self, mondo_id: str, entity_type: str | None = None
    ) -> list[EntitaMondo]: ...

    def elenca_documenti(
        self, mondo_id: str, document_type: str | None = None
    ) -> list[DocumentoCanonico]: ...

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


@dataclass(frozen=True, slots=True)
class TurnoNarrativoPreparato:
    world_id: str
    user_input: str
    messaggi: tuple[MessaggioChat, ...]
    prompt_visibile: str


class ServizioNarrativo:
    """Prepara e valida un turno senza produrre alcuna scrittura."""

    def __init__(
        self,
        archivio: ArchivioLetturaNarrativa,
        validazione: ServizioValidazione,
    ) -> None:
        self._archivio = archivio
        self._validazione = validazione

    def prepara_turno(
        self,
        world_id: str,
        user_input: str,
        recent_history: Sequence[str] = (),
    ) -> TurnoNarrativoPreparato:
        testo_utente = user_input.strip() if isinstance(user_input, str) else ""
        if not testo_utente:
            raise ErroreTurnoNarrativo("Scrivi un'azione prima di inviare il turno.")
        try:
            mondo = self._archivio.carica_mondo(world_id)
            entita = self._archivio.elenca_entita(mondo.id)
            documenti = self._archivio.elenca_documenti(mondo.id)
            player = self._risolvi_player(mondo.id, entita)
            memorie = self._memorie_correnti(mondo.id, entita)
        except ErroreTurnoNarrativo:
            raise
        except ErroreHaria as errore:
            raise ErroreTurnoNarrativo(
                "Non è stato possibile preparare il contesto del mondo selezionato."
            ) from errore

        contesto = ContestoTurnoNarrativo(
            world_title=mondo.titolo,
            player_name=player.canonical_name,
            user_input=testo_utente,
            scenario=mondo.scenario,
            rules=self._contenuto_documenti(documenti, "regole"),
            style=self._unisci_testi(
                self._formatta_impostazioni(mondo.impostazioni_narrative),
                self._contenuto_documenti(documenti, "stile"),
            ),
            author_note=self._nota_autore(documenti),
            world_state=self._formatta_stato(entita),
            characters=tuple(
                self._formatta_personaggio(voce)
                for voce in self._ordina_entita(entita)
                if voce.entity_type == TIPO_PERSONAGGIO
            ),
            relevant_memories=tuple(
                self._formatta_memoria(memoria, entita) for memoria in memorie
            ),
            recent_history=tuple(recent_history)[-MAX_CRONOLOGIA_TURNO:],
        )
        messaggi = costruisci_messaggi_turno(contesto)
        return TurnoNarrativoPreparato(
            world_id=mondo.id,
            user_input=testo_utente,
            messaggi=messaggi,
            prompt_visibile=formatta_prompt_visibile(messaggi),
        )

    def valida_risposta(
        self,
        turno: TurnoNarrativoPreparato,
        risposta: str,
        riferimento_temporale: datetime,
    ) -> TurnoNarrativoProposto:
        if riferimento_temporale.tzinfo is None or riferimento_temporale.utcoffset() is None:
            raise ErroreTurnoNarrativo(
                "Il riferimento temporale del turno deve includere il fuso orario."
            )
        try:
            proposta = parse_output_narrativo(risposta)
        except ErroreOutputNarrativo as errore:
            raise ErroreTurnoNarrativo(str(errore)) from errore
        esito = self._validazione.valida_sequenza(
            turno.world_id, proposta.operations, riferimento_temporale
        )
        if not esito.superata:
            dettagli = "\n".join(
                f"- {problema.messaggio}" for problema in esito.rapporto.errori[:5]
            )
            raise ErroreTurnoNarrativo(
                "La proposta narrativa non supera la validazione del mondo."
                + (f"\n{dettagli}" if dettagli else "")
            )
        return proposta

    def _risolvi_player(
        self, world_id: str, entita: Sequence[EntitaMondo]
    ) -> EntitaMondo:
        sorgente = next(
            (
                file for file in self._archivio.file_sorgente(world_id)
                if file.percorso_relativo.replace("\\", "/").casefold() == "world.json"
            ),
            None,
        )
        if sorgente is None:
            raise ErroreTurnoNarrativo(
                "Il mondo non contiene il file archiviato world.json."
            )
        try:
            dati = json.loads(sorgente.contenuto.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as errore:
            raise ErroreTurnoNarrativo(
                "Il file archiviato world.json non è leggibile."
            ) from errore
        player_id = dati.get("player_character_id") if isinstance(dati, dict) else None
        if not isinstance(player_id, str) or not player_id.strip():
            raise ErroreTurnoNarrativo(
                "Nel mondo manca il personaggio controllato dal giocatore."
            )
        player = next(
            (voce for voce in entita if voce.entity_id == player_id.strip()), None
        )
        if player is None or player.entity_type != TIPO_PERSONAGGIO:
            raise ErroreTurnoNarrativo(
                "Il personaggio controllato dal giocatore non è valido."
            )
        return player

    def _memorie_correnti(
        self, world_id: str, entita: Sequence[EntitaMondo]
    ) -> tuple[MemoriaPersonaggio, ...]:
        risultato: list[MemoriaPersonaggio] = []
        for personaggio in self._ordina_entita(entita):
            if personaggio.entity_type == TIPO_PERSONAGGIO:
                risultato.extend(
                    self._archivio.elenca_memorie_personaggio(
                        world_id, personaggio.entity_id, solo_correnti=True
                    )
                )
        ordinate = sorted(
            risultato,
            key=lambda voce: (voce.learned_at, voce.character_id, voce.memory_id),
        )
        return tuple(ordinate[-MAX_MEMORIE_TURNO:])

    @staticmethod
    def _ordina_entita(entita: Sequence[EntitaMondo]) -> tuple[EntitaMondo, ...]:
        return tuple(sorted(
            entita,
            key=lambda voce: (
                voce.entity_type, voce.canonical_name.casefold(), voce.entity_id
            ),
        ))

    @staticmethod
    def _contenuto_documenti(
        documenti: Sequence[DocumentoCanonico], tipo: str
    ) -> str:
        return "\n\n".join(
            documento.content for documento in documenti
            if documento.document_type == tipo
        )

    @staticmethod
    def _formatta_impostazioni(impostazioni: Mapping[str, str]) -> str:
        return "\n".join(
            f"{chiave.replace('_', ' ').capitalize()}: {impostazioni[chiave]}"
            for chiave in sorted(
                impostazioni, key=lambda voce: (voce.casefold(), voce)
            )
            if impostazioni[chiave]
        )

    @staticmethod
    def _unisci_testi(*testi: str) -> str:
        return "\n\n".join(testo for testo in testi if testo)

    @staticmethod
    def _nota_autore(documenti: Sequence[DocumentoCanonico]) -> str:
        tipi = {"nota_autore", "note_autore", "author_note", "author_notes"}
        nomi = {"author_note.md", "author_notes.md", "nota_autore.md"}
        return "\n\n".join(
            documento.content for documento in documenti
            if documento.document_type.casefold() in tipi
            or documento.relative_path.rsplit("/", 1)[-1].casefold() in nomi
        )

    @classmethod
    def _formatta_stato(cls, entita: Sequence[EntitaMondo]) -> str:
        return "\n".join(
            " | ".join((
                f"ID: {voce.entity_id}",
                f"tipo: {voce.entity_type}",
                f"nome: {voce.canonical_name}",
                f"stato: {voce.status}",
                f"posizione: {voce.location_id or 'nessuna'}",
                f"possessore: {voce.holder_id or 'nessuno'}",
                f"accessibile: {'sì' if voce.accessibility else 'no'}",
                f"condizione: {voce.condition or 'nessuna'}",
            ))
            for voce in cls._ordina_entita(entita)
        )

    @classmethod
    def _formatta_personaggio(cls, entita: EntitaMondo) -> str:
        profilo = cls._formatta_canone(entita.canonical_data)
        return (
            f"ID: {entita.entity_id}; nome: {entita.canonical_name}; "
            f"profilo: {profilo or 'non specificato'}; stato corrente: "
            f"stato {entita.status}; posizione {entita.location_id or 'nessuna'}; "
            f"condizione {entita.condition or 'nessuna'}"
        )

    @staticmethod
    def _formatta_canone(dati: Mapping[str, object]) -> str:
        escluse = {
            "id", "name", "status", "location_id", "owner_id", "image",
            "accessible", "condition", "relationships",
        }
        parti: list[str] = []
        for chiave in sorted(dati, key=lambda voce: (voce.casefold(), voce)):
            valore = dati[chiave]
            if chiave in escluse or chiave.endswith("_id") or valore in (None, "", [], {}):
                continue
            etichetta = "Profilo" if chiave == "text" else chiave.replace("_", " ").capitalize()
            if isinstance(valore, list):
                testo = ", ".join(
                    str(voce) for voce in valore
                    if isinstance(voce, (str, int, float))
                )
            elif isinstance(valore, Mapping):
                testo = ", ".join(
                    f"{str(sotto).replace('_', ' ')}: {contenuto}"
                    for sotto, contenuto in sorted(
                        valore.items(), key=lambda voce: str(voce[0]).casefold()
                    )
                    if not str(sotto).endswith("_id")
                    and isinstance(contenuto, (str, int, float, bool))
                )
            elif isinstance(valore, bool):
                testo = "sì" if valore else "no"
            elif isinstance(valore, (str, int, float)):
                testo = str(valore)
            else:
                continue
            if testo:
                parti.append(f"{etichetta}: {testo}")
        return "; ".join(parti)

    @staticmethod
    def _formatta_memoria(
        memoria: MemoriaPersonaggio, entita: Sequence[EntitaMondo]
    ) -> str:
        nomi = {voce.entity_id: voce.canonical_name for voce in entita}
        return (
            f"ID: {memoria.memory_id}; personaggio: "
            f"{nomi.get(memoria.character_id, memoria.character_id)} "
            f"({memoria.character_id}); contenuto: {memoria.content}; "
            f"fonte: {memoria.source_type}; certezza: {memoria.certainty}; "
            f"appresa: {memoria.learned_at}"
        )
