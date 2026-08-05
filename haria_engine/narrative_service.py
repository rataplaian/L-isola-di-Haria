"""Contesto e validazione applicativa dell'anteprima narrativa."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from .ai_models import MessaggioChat
from .errors import ErroreHaria, ErroreTurnoNarrativo
from .memories import MemoriaPersonaggio
from .models import FileSorgente, Mondo
from .narrative_history import (
    PartitaNarrativa,
    SessioneNarrativa,
    TurnoNarrativoPersistito,
)
from .narrative_models import TurnoNarrativoProposto
from .narrative_parser import ErroreOutputNarrativo, parse_output_narrativo
from .narrative_prompt import (
    ContestoTurnoNarrativo,
    costruisci_messaggi_turno,
    formatta_prompt_visibile,
)
from .narrative_persistence import (
    PianoPersistenzaTurno,
    crea_id_turno,
    crea_piano_persistenza_turno,
)
from .package_models import DocumentoCanonico
from .validation import ServizioValidazione
from .validation_models import EsitoSequenza, FotografiaValidazioneMondo
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

    def ottieni_o_crea_sessione_narrativa(
        self, mondo_id: str, tempo_iniziale: str, creata_il: str
    ) -> SessioneNarrativa: ...

    def elenca_turni_narrativi(
        self, mondo_id: str, *, limite: int | None = None
    ) -> list[TurnoNarrativoPersistito]: ...

    def applica_piano_turno_narrativo(
        self, piano: PianoPersistenzaTurno
    ) -> TurnoNarrativoPersistito: ...


@dataclass(frozen=True, slots=True)
class TurnoNarrativoPreparato:
    world_id: str
    user_input: str
    messaggi: tuple[MessaggioChat, ...]
    prompt_visibile: str
    session_id: str = ""
    sequence_number: int = 0
    world_time_before: str = ""
    fotografia_iniziale: FotografiaValidazioneMondo | None = None


class ServizioNarrativo:
    """Prepara e valida un turno senza produrre alcuna scrittura."""

    def __init__(
        self,
        archivio: ArchivioLetturaNarrativa,
        validazione: ServizioValidazione,
    ) -> None:
        self._archivio = archivio
        self._validazione = validazione

    def carica_partita(
        self, world_id: str, *, limite_turni: int | None = None
    ) -> PartitaNarrativa:
        adesso = datetime.now(timezone.utc)
        dati_world = self._dati_world_json(world_id)
        tempo_iniziale = self._tempo_iniziale(dati_world, adesso)
        sessione = self._archivio.ottieni_o_crea_sessione_narrativa(
            world_id,
            tempo_iniziale.isoformat(timespec="microseconds"),
            adesso.isoformat(timespec="microseconds"),
        )
        turni = self._archivio.elenca_turni_narrativi(
            world_id, limite=limite_turni
        )
        return PartitaNarrativa(sessione, tuple(turni))

    def prepara_piano_da_risposta(
        self,
        turno: TurnoNarrativoPreparato,
        risposta: str,
        *,
        created_at: datetime | None = None,
    ) -> PianoPersistenzaTurno:
        if (
            not turno.session_id
            or turno.sequence_number < 1
            or not turno.world_time_before
            or turno.fotografia_iniziale is None
        ):
            raise ErroreTurnoNarrativo(
                "Il turno non contiene una sessione narrativa persistente valida."
            )
        try:
            prima = datetime.fromisoformat(turno.world_time_before)
        except ValueError as errore:
            raise ErroreTurnoNarrativo(
                "Il tempo narrativo corrente non è leggibile."
            ) from errore
        if prima.tzinfo is None or prima.utcoffset() is None:
            raise ErroreTurnoNarrativo(
                "Il tempo narrativo corrente deve includere il fuso orario."
            )
        proposta = self._parse_risposta(risposta)
        tempo_finale = prima + timedelta(minutes=proposta.elapsed_minutes)
        esito = self._valida_operazioni(
            turno.world_id, proposta, tempo_finale
        )
        istante_creazione = created_at or datetime.now(timezone.utc)
        try:
            piano = crea_piano_persistenza_turno(
                session_id=turno.session_id,
                turn_id=crea_id_turno(turno.session_id, turno.sequence_number),
                sequence_number=turno.sequence_number,
                world_time_before=prima,
                user_input=turno.user_input,
                prompt_text=turno.prompt_visibile,
                raw_model_output=risposta,
                proposta=proposta,
                fotografia_iniziale=turno.fotografia_iniziale,
                esito_validazione=esito,
                created_at=istante_creazione,
                memory_operation_indices=tuple(
                    memoria.operation_index for memoria in proposta.memories
                ),
            )
            self._valida_memorie_candidate(
                proposta, piano, esito, turno.fotografia_iniziale
            )
        except ValueError as errore:
            raise ErroreTurnoNarrativo(str(errore)) from errore
        return piano

    def salva_risposta_turno(
        self, turno: TurnoNarrativoPreparato, risposta: str
    ) -> TurnoNarrativoPersistito:
        piano = self.prepara_piano_da_risposta(turno, risposta)
        return self._archivio.applica_piano_turno_narrativo(piano)

    def prepara_turno(
        self,
        world_id: str,
        user_input: str,
        recent_history: Sequence[str] | None = None,
    ) -> TurnoNarrativoPreparato:
        testo_utente = user_input.strip() if isinstance(user_input, str) else ""
        if not testo_utente:
            raise ErroreTurnoNarrativo("Scrivi un'azione prima di inviare il turno.")
        try:
            mondo = self._archivio.carica_mondo(world_id)
            entita = self._archivio.elenca_entita(mondo.id)
            documenti = self._archivio.elenca_documenti(mondo.id)
            player = self._risolvi_player(mondo.id, entita)
            partita = self.carica_partita(mondo.id, limite_turni=10)
            memorie = self._memorie_correnti(mondo.id, entita)
            fotografia = self._validazione.costruisci_fotografia(mondo.id)
        except ErroreTurnoNarrativo:
            raise
        except ErroreHaria as errore:
            raise ErroreTurnoNarrativo(
                "Non è stato possibile preparare il contesto del mondo selezionato."
            ) from errore

        storia = (
            tuple(recent_history)
            if recent_history is not None
            else self._cronologia_prompt(partita.turni)
        )
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
            recent_history=storia[-MAX_CRONOLOGIA_TURNO:],
            narrative_time=self._formatta_tempo_narrativo(
                partita.sessione.current_time
            ),
        )
        messaggi = costruisci_messaggi_turno(contesto)
        return TurnoNarrativoPreparato(
            world_id=mondo.id,
            user_input=testo_utente,
            messaggi=messaggi,
            prompt_visibile=formatta_prompt_visibile(messaggi),
            session_id=partita.sessione.session_id,
            sequence_number=partita.sessione.next_turn_number,
            world_time_before=partita.sessione.current_time,
            fotografia_iniziale=fotografia,
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
        proposta = self._parse_risposta(risposta)
        self._valida_operazioni(
            turno.world_id, proposta, riferimento_temporale
        )
        return proposta

    @staticmethod
    def _parse_risposta(risposta: str) -> TurnoNarrativoProposto:
        try:
            return parse_output_narrativo(risposta)
        except ErroreOutputNarrativo as errore:
            raise ErroreTurnoNarrativo(str(errore)) from errore

    def _valida_operazioni(
        self,
        world_id: str,
        proposta: TurnoNarrativoProposto,
        riferimento_temporale: datetime,
    ) -> EsitoSequenza:
        esito = self._validazione.valida_sequenza(
            world_id, proposta.operations, riferimento_temporale
        )
        if not esito.superata:
            dettagli = "\n".join(
                f"- {problema.messaggio}" for problema in esito.rapporto.errori[:5]
            )
            raise ErroreTurnoNarrativo(
                "La proposta narrativa non supera la validazione del mondo."
                + (f"\n{dettagli}" if dettagli else "")
            )
        return esito

    def _dati_world_json(self, world_id: str) -> dict[str, object]:
        sorgente = next(
            (
                file for file in self._archivio.file_sorgente(world_id)
                if file.percorso_relativo.replace("\\", "/").casefold()
                == "world.json"
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
        if not isinstance(dati, dict):
            raise ErroreTurnoNarrativo(
                "Il file archiviato world.json non descrive un mondo valido."
            )
        return dict(dati)

    @staticmethod
    def _tempo_iniziale(
        dati_world: Mapping[str, object], fallback: datetime
    ) -> datetime:
        valore = dati_world.get("narrative_start_at")
        if valore is None:
            return fallback
        if not isinstance(valore, str) or not valore.strip():
            raise ErroreTurnoNarrativo(
                "Il campo narrative_start_at deve contenere una data ISO-8601."
            )
        testo = valore.strip()
        if testo.endswith("Z"):
            testo = testo[:-1] + "+00:00"
        try:
            istante = datetime.fromisoformat(testo)
        except ValueError as errore:
            raise ErroreTurnoNarrativo(
                "Il campo narrative_start_at non contiene una data ISO-8601 valida."
            ) from errore
        if istante.tzinfo is None or istante.utcoffset() is None:
            raise ErroreTurnoNarrativo(
                "Il campo narrative_start_at deve includere il fuso orario."
            )
        return istante

    @staticmethod
    def _formatta_tempo_narrativo(valore: str) -> str:
        try:
            istante = datetime.fromisoformat(valore)
        except ValueError:
            return valore
        return istante.strftime("%d/%m/%Y alle %H:%M (%z)")

    @staticmethod
    def _cronologia_prompt(
        turni: Sequence[TurnoNarrativoPersistito],
    ) -> tuple[str, ...]:
        messaggi: list[str] = []
        for turno in turni[-10:]:
            messaggi.extend(
                (
                    f"Utente: {turno.user_input}",
                    f"Narratore: {turno.narrative}",
                )
            )
        return tuple(messaggi)

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

    @staticmethod
    def _valida_memorie_candidate(
        proposta: TurnoNarrativoProposto,
        piano: PianoPersistenzaTurno,
        esito: EsitoSequenza,
        fotografia_iniziale: FotografiaValidazioneMondo,
    ) -> None:
        entita = {voce.entity_id: voce for voce in fotografia_iniziale.entita}
        memorie = {
            voce.memory_id: voce for voce in fotografia_iniziale.memorie
        }
        eventi = {voce.operation_index: voce for voce in piano.eventi}
        tipi_conoscenza_ammessi = {
            "direct_observation": {"observed_fact"},
            "told_by_character": {"reported_fact"},
            "inference": {"inference", "belief"},
            "self_experience": {"observed_fact", "belief"},
        }
        for indice, memoria in enumerate(proposta.memories):
            personaggio = entita.get(memoria.character_id)
            if personaggio is None or personaggio.entity_type != TIPO_PERSONAGGIO:
                raise ErroreTurnoNarrativo(
                    f"La memoria {indice + 1} non appartiene a un personaggio esistente."
                )
            if memoria.source_type == "imported_background":
                raise ErroreTurnoNarrativo(
                    "Il modello non può creare memorie di sfondo importate."
                )
            if memoria.knowledge_type == "canonical_knowledge":
                raise ErroreTurnoNarrativo(
                    "Il modello non può creare conoscenze canoniche."
                )
            conoscenze_ammesse = tipi_conoscenza_ammessi.get(memoria.source_type)
            if (
                conoscenze_ammesse is None
                or memoria.knowledge_type not in conoscenze_ammesse
            ):
                raise ErroreTurnoNarrativo(
                    f"Il tipo di conoscenza della memoria {indice + 1} non è coerente con la fonte."
                )
            if memoria.source_type == "told_by_character":
                if memoria.source_entity_id is None:
                    raise ErroreTurnoNarrativo(
                        "Una memoria raccontata richiede un personaggio come fonte."
                    )
            elif memoria.source_entity_id is not None:
                raise ErroreTurnoNarrativo(
                    f"La memoria {indice + 1} non deve indicare un'entità fonte."
                )
            if memoria.source_type == "inference":
                if not memoria.source_memory_ids:
                    raise ErroreTurnoNarrativo(
                        "Una inferenza richiede almeno una memoria sorgente."
                    )
            elif memoria.source_memory_ids:
                raise ErroreTurnoNarrativo(
                    f"La memoria {indice + 1} non inferenziale non può indicare memorie sorgente."
                )
            fonte = (
                None
                if memoria.source_entity_id is None
                else entita.get(memoria.source_entity_id)
            )
            if memoria.source_entity_id is not None and fonte is None:
                raise ErroreTurnoNarrativo(
                    f"La fonte della memoria {indice + 1} non esiste."
                )
            for associazione in memoria.entities:
                if associazione.entity_id not in entita:
                    raise ErroreTurnoNarrativo(
                        f"Un'entità collegata alla memoria {indice + 1} non esiste."
                    )
            for source_memory_id in memoria.source_memory_ids:
                sorgente = memorie.get(source_memory_id)
                if sorgente is None or sorgente.character_id != memoria.character_id:
                    raise ErroreTurnoNarrativo(
                        f"Una memoria sorgente della memoria {indice + 1} non appartiene allo stesso personaggio."
                    )
            if memoria.source_type == "direct_observation":
                operation_index = memoria.operation_index
                if operation_index is None or operation_index not in eventi:
                    raise ErroreTurnoNarrativo(
                        "Una osservazione diretta deve indicare la propria operazione."
                    )
                evento = eventi[operation_index]
                if evento.location_id is None:
                    raise ErroreTurnoNarrativo(
                        "Una osservazione diretta richiede un evento con luogo."
                    )
                proiezione = esito.esiti[operation_index].fotografia
                posizione = next(
                    (
                        voce.location_id
                        for voce in proiezione.entita
                        if voce.entity_id == memoria.character_id
                    ),
                    None,
                )
                if posizione != evento.location_id:
                    raise ErroreTurnoNarrativo(
                        "Il personaggio non si trova nel luogo dell'osservazione diretta."
                    )
            elif memoria.source_type == "told_by_character":
                if fonte is None or fonte.entity_type != TIPO_PERSONAGGIO:
                    raise ErroreTurnoNarrativo(
                        "Una memoria raccontata richiede un personaggio come fonte."
                    )
                if fonte.entity_id == memoria.character_id:
                    raise ErroreTurnoNarrativo(
                        "Fonte e ascoltatore della memoria devono essere distinti."
                    )

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
