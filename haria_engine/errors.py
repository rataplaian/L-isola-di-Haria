"""Errori applicativi con messaggi destinati all'interfaccia italiana."""


class ErroreHaria(Exception):
    """Errore previsto e leggibile dall'utente."""


class ErroreImportazione(ErroreHaria):
    """Il pacchetto scelto non può essere importato."""


class ErroreZipNonValido(ErroreImportazione):
    """L'archivio ZIP non è leggibile o non è un archivio valido."""


class ErroreArchivioNonSicuro(ErroreImportazione):
    """Il pacchetto contiene percorsi, link o dimensioni non sicuri."""


class ErroreManifest(ErroreImportazione):
    """Il manifest non descrive fedelmente il pacchetto."""


class ErrorePacchettoCompleto(ErroreImportazione):
    """Un pacchetto completo non contiene tutti i file strutturali richiesti."""


class ErroreAnteprimaMedia(ErroreHaria):
    """Il media è conservato ma non visualizzabile nativamente."""


class ErroreEsportazione(ErroreHaria):
    """Il mondo non può essere esportato."""


class MondoNonTrovato(ErroreHaria):
    """Il mondo richiesto non esiste nell'archivio locale."""


class ErroreMigrazione(ErroreHaria):
    """Il database non può essere migrato senza rischiare dati parziali."""


class ErroreStatoMondo(ErroreHaria):
    """Un'operazione strutturata sullo stato del mondo non è valida."""


class ErroreMemoria(ErroreHaria):
    """Una conoscenza soggettiva o una sua relazione non è valida."""


class ErroreConfigurazioneAI(ErroreHaria):
    """La configurazione del provider AI non è valida o persistibile."""


class ErroreProviderAI(ErroreHaria):
    """Il provider AI non ha completato l'operazione richiesta."""


class ErroreOllamaNonRaggiungibile(ErroreProviderAI):
    """Il servizio Ollama locale non è raggiungibile."""


class ErroreTimeoutOllama(ErroreProviderAI):
    """Il servizio Ollama non ha risposto entro il timeout."""


class ErroreHTTPProvider(ErroreProviderAI):
    """Il servizio Ollama ha restituito uno stato HTTP non riuscito."""


class ErroreRispostaJSON(ErroreProviderAI):
    """La risposta del provider non contiene JSON UTF-8 valido."""


class ErroreStrutturaRisposta(ErroreProviderAI):
    """La risposta del provider non rispetta il contratto previsto."""


class ErroreVersioneMancante(ErroreStrutturaRisposta):
    """La risposta non contiene una versione Ollama valida."""


class ErroreElencoModelli(ErroreStrutturaRisposta):
    """La risposta non contiene un elenco modelli valido."""


class ErroreModelloNonDisponibile(ErroreProviderAI):
    """Il modello configurato non è disponibile nel servizio locale."""


class ErroreRispostaAssistant(ErroreStrutturaRisposta):
    """La risposta non contiene testo assistant valido."""


class ErroreLimiteTesto(ErroreProviderAI):
    """Il testo di prova supera il limite applicativo."""


class ErroreCorpoHTTP(ErroreProviderAI):
    """Il corpo della risposta supera il limite applicativo."""


class ErroreValidazione(ErroreHaria):
    """La fotografia o la richiesta di validazione non può essere elaborata."""

