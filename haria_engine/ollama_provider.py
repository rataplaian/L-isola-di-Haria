"""Provider Ollama basato esclusivamente sull'API REST nativa."""

from __future__ import annotations

import json
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from .ai_models import (
    LIMITE_TESTO_PROVA,
    ConfigurazioneAI,
    InformazioniProvider,
    MessaggioChat,
    ModelloLocale,
    RispostaTestuale,
    RisultatoConnessione,
)
from .errors import (
    ErroreElencoModelli,
    ErroreHTTPProvider,
    ErroreLimiteTesto,
    ErroreModelloNonDisponibile,
    ErroreRispostaAssistant,
    ErroreRispostaJSON,
    ErroreStrutturaRisposta,
    ErroreVersioneMancante,
)
from .http_transport import RispostaHTTP, TrasportoHTTP


PROMPT_SISTEMA_PROVA = (
    "Rispondi brevemente per confermare che il modello locale funziona."
)
TESTO_PROVA_PREDEFINITO = "Conferma il funzionamento con una breve risposta."


class ProviderLLM(Protocol):
    def verifica_connessione(self) -> RisultatoConnessione: ...

    def elenca_modelli(self) -> tuple[ModelloLocale, ...]: ...

    def genera_testo_di_prova(self, testo: str) -> RispostaTestuale: ...


class OllamaProvider:
    def __init__(
        self, configurazione: ConfigurazioneAI, trasporto: TrasportoHTTP
    ) -> None:
        self.configurazione = configurazione
        self.trasporto = trasporto

    def verifica_connessione(self) -> RisultatoConnessione:
        dati = self._richiedi_json("GET", "/api/version")
        versione = dati.get("version")
        if not isinstance(versione, str) or not versione.strip():
            raise ErroreVersioneMancante(
                "Ollama non ha restituito una versione valida."
            )
        informazioni = InformazioniProvider(
            provider="Ollama", versione=versione.strip()
        )
        return RisultatoConnessione(True, informazioni)

    def elenca_modelli(self) -> tuple[ModelloLocale, ...]:
        dati = self._richiedi_json("GET", "/api/tags")
        modelli = dati.get("models")
        if not isinstance(modelli, list):
            raise ErroreElencoModelli(
                "Ollama non ha restituito un elenco di modelli valido."
            )
        nomi: dict[str, None] = {}
        for elemento in modelli:
            if not isinstance(elemento, dict):
                raise ErroreElencoModelli(
                    "Ollama non ha restituito un elenco di modelli valido."
                )
            nome = elemento.get("name")
            if not isinstance(nome, str) or not nome.strip():
                raise ErroreElencoModelli(
                    "Ollama non ha restituito un elenco di modelli valido."
                )
            nomi.setdefault(nome, None)
        return tuple(
            ModelloLocale(nome)
            for nome in sorted(nomi, key=lambda voce: (voce.casefold(), voce))
        )

    def genera_testo_di_prova(self, testo: str) -> RispostaTestuale:
        if len(testo) > LIMITE_TESTO_PROVA:
            raise ErroreLimiteTesto(
                "Il testo di prova non può superare 2.000 caratteri."
            )
        modello = self.configurazione.ollama_model
        if not modello:
            raise ErroreModelloNonDisponibile(
                "Seleziona un modello Ollama prima di eseguire la prova."
            )
        disponibili = {voce.nome for voce in self.elenca_modelli()}
        if modello not in disponibili:
            raise ErroreModelloNonDisponibile(
                "Il modello selezionato non è disponibile in Ollama."
            )
        testo_utente = testo if testo.strip() else TESTO_PROVA_PREDEFINITO
        messaggi = (
            MessaggioChat("system", PROMPT_SISTEMA_PROVA),
            MessaggioChat("user", testo_utente),
        )
        payload = {
            "model": modello,
            "stream": False,
            "messages": [
                {"role": messaggio.ruolo, "content": messaggio.contenuto}
                for messaggio in messaggi
            ],
        }
        dati = self._richiedi_json(
            "POST",
            "/api/chat",
            corpo=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        messaggio = dati.get("message")
        if not isinstance(messaggio, dict):
            raise ErroreRispostaAssistant(
                "Ollama non ha restituito una risposta testuale valida."
            )
        ruolo = messaggio.get("role")
        contenuto = messaggio.get("content")
        if (
            ruolo != "assistant"
            or not isinstance(contenuto, str)
            or not contenuto.strip()
        ):
            raise ErroreRispostaAssistant(
                "Ollama non ha restituito una risposta testuale valida."
            )
        return RispostaTestuale(contenuto=contenuto)

    def _richiedi_json(
        self,
        metodo: str,
        percorso: str,
        *,
        corpo: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        risposta = self.trasporto.richiedi(
            metodo,
            _endpoint(self.configurazione.ollama_base_url, percorso),
            headers=headers,
            corpo=corpo,
            timeout=self.configurazione.ollama_timeout_seconds,
        )
        _verifica_status(risposta)
        try:
            decodificato = risposta.corpo.decode("utf-8")
            dati = json.loads(decodificato)
        except (UnicodeDecodeError, json.JSONDecodeError) as errore:
            raise ErroreRispostaJSON(
                "Ollama ha restituito una risposta non valida."
            ) from errore
        if not isinstance(dati, dict):
            raise ErroreStrutturaRisposta(
                "Ollama ha restituito una risposta con struttura inattesa."
            )
        return dict(dati)


def _endpoint(radice: str, percorso: str) -> str:
    parti = urlsplit(radice)
    return urlunsplit((parti.scheme, parti.netloc, percorso, "", ""))


def _verifica_status(risposta: RispostaHTTP) -> None:
    if not 200 <= risposta.status <= 299:
        raise ErroreHTTPProvider(
            "Il servizio Ollama ha restituito un errore HTTP."
        )
