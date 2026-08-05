"""Trasporto HTTP limitato e iniettabile per provider locali."""

from __future__ import annotations

import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Protocol

from .errors import (
    ErroreCorpoHTTP,
    ErroreHTTPProvider,
    ErroreOllamaNonRaggiungibile,
    ErroreTimeoutOllama,
)


LIMITE_CORPO_HTTP = 1024 * 1024


@dataclass(frozen=True, slots=True)
class RispostaHTTP:
    status: int
    corpo: bytes


class TrasportoHTTP(Protocol):
    def richiedi(
        self,
        metodo: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        corpo: bytes | None = None,
        timeout: int,
    ) -> RispostaHTTP: ...


class _NessunRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


class TrasportoUrllib:
    """Client diretto, senza proxy, redirect o retry automatici."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NessunRedirect()
        )

    def richiedi(
        self,
        metodo: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        corpo: bytes | None = None,
        timeout: int,
    ) -> RispostaHTTP:
        richiesta = urllib.request.Request(
            url,
            data=corpo,
            headers=dict(headers or {}),
            method=metodo,
        )
        try:
            with self._opener.open(richiesta, timeout=timeout) as risposta:
                status = int(risposta.getcode())
                if not 200 <= status <= 299:
                    raise ErroreHTTPProvider(
                        "Il servizio Ollama ha restituito un errore HTTP."
                    )
                lunghezza = risposta.headers.get("Content-Length")
                if lunghezza is not None:
                    try:
                        if int(lunghezza) > LIMITE_CORPO_HTTP:
                            raise ErroreCorpoHTTP(
                                "La risposta di Ollama supera il limite consentito."
                            )
                    except ValueError:
                        pass
                dati = risposta.read(LIMITE_CORPO_HTTP + 1)
        except ErroreCorpoHTTP:
            raise
        except urllib.error.HTTPError as errore:
            raise ErroreHTTPProvider(
                "Il servizio Ollama ha restituito un errore HTTP."
            ) from errore
        except (TimeoutError, socket.timeout) as errore:
            raise ErroreTimeoutOllama(
                "Ollama non ha risposto entro il timeout configurato."
            ) from errore
        except urllib.error.URLError as errore:
            if isinstance(errore.reason, (TimeoutError, socket.timeout)):
                raise ErroreTimeoutOllama(
                    "Ollama non ha risposto entro il timeout configurato."
                ) from errore
            raise ErroreOllamaNonRaggiungibile(
                "Ollama non è raggiungibile sul computer locale."
            ) from errore
        except OSError as errore:
            raise ErroreOllamaNonRaggiungibile(
                "Ollama non è raggiungibile sul computer locale."
            ) from errore
        if len(dati) > LIMITE_CORPO_HTTP:
            raise ErroreCorpoHTTP(
                "La risposta di Ollama supera il limite consentito."
            )
        return RispostaHTTP(status=status, corpo=dati)

