"""Modelli immutabili e validazione della configurazione AI."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit

from .errors import ErroreConfigurazioneAI


PROVIDER_OLLAMA = "ollama"
OLLAMA_URL_PREDEFINITO = "http://localhost:11434"
TIMEOUT_PREDEFINITO = 30
TIMEOUT_MASSIMO = 300
LIMITE_TESTO_PROVA = 2_000


@dataclass(frozen=True, slots=True)
class ConfigurazioneAI:
    provider: str
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: int
    updated_at: str = ""


@dataclass(frozen=True, slots=True)
class InformazioniProvider:
    provider: str
    versione: str


@dataclass(frozen=True, slots=True)
class ModelloLocale:
    nome: str


@dataclass(frozen=True, slots=True)
class MessaggioChat:
    ruolo: str
    contenuto: str


@dataclass(frozen=True, slots=True)
class RispostaTestuale:
    contenuto: str


@dataclass(frozen=True, slots=True)
class RisultatoConnessione:
    raggiungibile: bool
    informazioni: InformazioniProvider


def valida_configurazione_ai(
    provider: object,
    ollama_base_url: object,
    ollama_model: object,
    ollama_timeout_seconds: object,
    *,
    updated_at: str = "",
) -> ConfigurazioneAI:
    """Valida senza rete e restituisce una fotografia immutabile."""

    if provider != PROVIDER_OLLAMA:
        raise ErroreConfigurazioneAI(
            "Il provider AI selezionato non è supportato."
        )
    if not isinstance(ollama_base_url, str) or not ollama_base_url.strip():
        raise ErroreConfigurazioneAI("L'URL del servizio Ollama è obbligatorio.")
    url_normalizzato = _valida_url_loopback(ollama_base_url)
    if not isinstance(ollama_model, str):
        raise ErroreConfigurazioneAI("Il modello Ollama deve essere testuale.")
    if ollama_model and not ollama_model.strip():
        raise ErroreConfigurazioneAI(
            "Il modello Ollama non può contenere soltanto spazi."
        )
    if (
        isinstance(ollama_timeout_seconds, bool)
        or not isinstance(ollama_timeout_seconds, int)
        or not 1 <= ollama_timeout_seconds <= TIMEOUT_MASSIMO
    ):
        raise ErroreConfigurazioneAI(
            "Il timeout deve essere un numero intero tra 1 e 300 secondi."
        )
    return ConfigurazioneAI(
        provider=PROVIDER_OLLAMA,
        ollama_base_url=url_normalizzato,
        ollama_model=ollama_model,
        ollama_timeout_seconds=ollama_timeout_seconds,
        updated_at=updated_at,
    )


def _valida_url_loopback(url: str) -> str:
    try:
        parti = urlsplit(url)
        porta = parti.port
    except ValueError as errore:
        raise ErroreConfigurazioneAI(
            "L'URL del servizio Ollama non è valido."
        ) from errore

    if parti.scheme.casefold() not in {"http", "https"}:
        raise ErroreConfigurazioneAI(
            "L'URL del servizio Ollama deve usare http oppure https."
        )
    if not parti.netloc or parti.hostname is None:
        raise ErroreConfigurazioneAI(
            "L'URL del servizio Ollama deve essere assoluto e completo."
        )
    if parti.username is not None or parti.password is not None:
        raise ErroreConfigurazioneAI(
            "L'URL del servizio Ollama non può contenere credenziali."
        )
    if parti.query or parti.fragment:
        raise ErroreConfigurazioneAI(
            "L'URL del servizio Ollama non può contenere query o frammenti."
        )
    if parti.path not in {"", "/"}:
        raise ErroreConfigurazioneAI(
            "L'URL del servizio Ollama deve indicare la sola radice del servizio."
        )
    if porta is not None and not 1 <= porta <= 65_535:
        raise ErroreConfigurazioneAI(
            "La porta del servizio Ollama non è valida."
        )
    if not _host_loopback_valido(parti.hostname):
        raise ErroreConfigurazioneAI(
            "Ollama deve essere configurato sul computer locale."
        )
    return url[:-1] if parti.path == "/" else url


def _host_loopback_valido(host: str) -> bool:
    if host.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
