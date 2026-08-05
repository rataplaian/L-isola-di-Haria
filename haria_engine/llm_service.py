"""Servizio applicativo AI privo di dipendenze da SQLite e Tkinter."""

from __future__ import annotations

from .ai_models import (
    ConfigurazioneAI,
    ModelloLocale,
    RispostaTestuale,
    RisultatoConnessione,
    valida_configurazione_ai,
)
from .http_transport import TrasportoHTTP, TrasportoUrllib
from .ollama_provider import OllamaProvider, ProviderLLM


class ServizioAI:
    """Costruisce provider su fotografie immutabili già validate."""

    def __init__(self, trasporto: TrasportoHTTP | None = None) -> None:
        self._trasporto = trasporto or TrasportoUrllib()

    def verifica_connessione(
        self, configurazione: ConfigurazioneAI
    ) -> RisultatoConnessione:
        return self._provider(configurazione).verifica_connessione()

    def elenca_modelli(
        self, configurazione: ConfigurazioneAI
    ) -> tuple[ModelloLocale, ...]:
        return self._provider(configurazione).elenca_modelli()

    def genera_testo_di_prova(
        self, configurazione: ConfigurazioneAI, testo: str
    ) -> RispostaTestuale:
        return self._provider(configurazione).genera_testo_di_prova(testo)

    def _provider(self, configurazione: ConfigurazioneAI) -> ProviderLLM:
        valida = valida_configurazione_ai(
            configurazione.provider,
            configurazione.ollama_base_url,
            configurazione.ollama_model,
            configurazione.ollama_timeout_seconds,
            updated_at=configurazione.updated_at,
        )
        return OllamaProvider(valida, self._trasporto)
