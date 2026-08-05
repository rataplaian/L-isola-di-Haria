"""Coordinamento di worker daemon senza dipendenze da Tkinter o SQLite."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class EsitoAsincrono(Generic[T]):
    operazione: str
    risultato: T | None = None
    errore: Exception | None = None


class CoordinatoreAsincrono:
    """Esegue una sola operazione per volta e consegna esiti tramite coda."""

    def __init__(self) -> None:
        self._coda: queue.Queue[EsitoAsincrono[object]] = queue.Queue()
        self._blocco = threading.Lock()
        self._in_corso = False
        self._chiuso = False
        self._generazione = 0

    @property
    def in_corso(self) -> bool:
        with self._blocco:
            return self._in_corso

    def avvia(
        self,
        operazione: str,
        funzione: Callable[..., object],
        *argomenti: object,
    ) -> bool:
        with self._blocco:
            if self._chiuso or self._in_corso:
                return False
            self._in_corso = True
            generazione = self._generazione
        threading.Thread(
            target=self._esegui,
            args=(generazione, operazione, funzione, argomenti),
            name=f"haria-ai-{operazione}",
            daemon=True,
        ).start()
        return True

    def _esegui(
        self,
        generazione: int,
        operazione: str,
        funzione: Callable[..., object],
        argomenti: tuple[object, ...],
    ) -> None:
        try:
            risultato = funzione(*argomenti)
            esito = EsitoAsincrono(operazione, risultato=risultato)
        except Exception as errore:  # l'errore viene interpretato dal thread principale
            esito = EsitoAsincrono(operazione, errore=errore)
        with self._blocco:
            self._in_corso = False
            if self._chiuso or generazione != self._generazione:
                return
            self._coda.put(esito)

    def raccogli(self) -> tuple[EsitoAsincrono[object], ...]:
        with self._blocco:
            if self._chiuso:
                return ()
        risultati: list[EsitoAsincrono[object]] = []
        while True:
            try:
                risultati.append(self._coda.get_nowait())
            except queue.Empty:
                return tuple(risultati)

    def chiudi(self) -> None:
        with self._blocco:
            self._chiuso = True
            self._generazione += 1
            self._in_corso = False
        while True:
            try:
                self._coda.get_nowait()
            except queue.Empty:
                return

