"""Errori applicativi con messaggi destinati all'interfaccia italiana."""


class ErroreHaria(Exception):
    """Errore previsto e leggibile dall'utente."""


class ErroreImportazione(ErroreHaria):
    """Il pacchetto scelto non può essere importato."""


class ErroreEsportazione(ErroreHaria):
    """Il mondo non può essere esportato."""


class MondoNonTrovato(ErroreHaria):
    """Il mondo richiesto non esiste nell'archivio locale."""

