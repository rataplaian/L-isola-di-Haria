"""Stato testabile delle modifiche dell'editor, indipendente da Tkinter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import Enum


class SceltaModifiche(Enum):
    """Scelte disponibili prima di un'operazione che sostituisce i dati correnti."""

    SALVA = "salva"
    SCARTA = "scarta"
    ANNULLA = "annulla"


class StatoEditor:
    """Confronta i valori correnti con l'ultima versione caricata o salvata."""

    def __init__(self) -> None:
        self._scenario_salvato = ""
        self._impostazioni_salvate: dict[str, str] = {}
        self._scenario_corrente = ""
        self._impostazioni_correnti: dict[str, str] = {}

    @property
    def modificato(self) -> bool:
        return (
            self._scenario_corrente != self._scenario_salvato
            or self._impostazioni_correnti != self._impostazioni_salvate
        )

    def carica(
        self, scenario: str, impostazioni_narrative: Mapping[str, str]
    ) -> None:
        """Imposta una nuova base salvata e azzera lo stato dirty."""

        impostazioni = dict(impostazioni_narrative)
        self._scenario_salvato = scenario
        self._impostazioni_salvate = impostazioni
        self._scenario_corrente = scenario
        self._impostazioni_correnti = dict(impostazioni)

    def aggiorna_scenario(self, scenario: str) -> None:
        self._scenario_corrente = scenario

    def aggiorna_impostazione(self, chiave: str, valore: str) -> None:
        self._impostazioni_correnti[chiave] = valore

    def registra_salvataggio(self) -> None:
        """Rende i valori correnti la nuova base salvata."""

        self._scenario_salvato = self._scenario_corrente
        self._impostazioni_salvate = dict(self._impostazioni_correnti)

    def consenti_operazione(
        self,
        scelta: SceltaModifiche,
        salva: Callable[[], bool],
    ) -> bool:
        """Risolve le modifiche prima di proseguire con un'operazione distruttiva.

        ``SCARTA`` autorizza l'operazione senza alterare lo stato: sarà il caricamento
        riuscito dei nuovi dati a sostituire l'editor. Se l'operazione fallisce, le
        modifiche restano visibili e ancora marcate come non salvate.
        """

        if not self.modificato:
            return True
        if scelta is SceltaModifiche.ANNULLA:
            return False
        if scelta is SceltaModifiche.SCARTA:
            return True
        if scelta is SceltaModifiche.SALVA:
            if not salva():
                return False
            self.registra_salvataggio()
            return True
        raise ValueError("Scelta per le modifiche non riconosciuta.")
