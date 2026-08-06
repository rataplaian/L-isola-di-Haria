"""Costruzione deterministica dei messaggi del primo turno narrativo."""

from __future__ import annotations

from dataclasses import dataclass

from .ai_models import MessaggioChat
from .narrative_output_schema import serializza_schema_output_narrativo


@dataclass(frozen=True, slots=True)
class ContestoTurnoNarrativo:
    """Contesto già selezionato dal servizio applicativo, senza accesso al DB."""

    world_title: str
    player_name: str
    user_input: str
    scenario: str
    rules: str = ""
    style: str = ""
    author_note: str = ""
    world_state: str = ""
    characters: tuple[str, ...] = ()
    relevant_memories: tuple[str, ...] = ()
    recent_history: tuple[str, ...] = ()
    narrative_time: str = ""


def costruisci_messaggi_turno(
    contesto: ContestoTurnoNarrativo,
) -> tuple[MessaggioChat, MessaggioChat]:
    """Restituisce i due messaggi realmente inviabili al provider."""

    _valida_contesto(contesto)
    sistema = _prompt_sistema(contesto.player_name)
    utente = _prompt_utente(contesto)
    return (
        MessaggioChat("system", sistema),
        MessaggioChat("user", utente),
    )


def formatta_prompt_visibile(
    messaggi: tuple[MessaggioChat, ...],
) -> str:
    """Rende leggibile esattamente il prompt, senza dati nascosti."""

    sezioni: list[str] = []
    for messaggio in messaggi:
        ruolo = messaggio.ruolo.upper()
        sezioni.append(f"===== {ruolo} =====\n{messaggio.contenuto}")
    return "\n\n".join(sezioni)


def _prompt_sistema(player_name: str) -> str:
    schema = serializza_schema_output_narrativo()
    return f"""Sei il motore narrativo locale di un mondo persistente.

SEPARAZIONE DEL CONTROLLO
- L'utente controlla esclusivamente {player_name}.
- Non decidere pensieri, consenso, desideri, intenzioni, parole volontarie o azioni volontarie di {player_name}.
- Non scrivere battute di {player_name} che l'utente non abbia già fornito.
- Puoi descrivere ciò che accade attorno a {player_name}, le azioni autonome delle NPC, conseguenze esterne e reazioni fisiche involontarie senza trasformarle in scelte volontarie.
- Le NPC hanno volontà, obiettivi e relazioni indipendenti. Non provano automaticamente amore, fiducia, desiderio, obbedienza o perdono.

NATURA ADULTA DI HARIA
- Haria è destinato esclusivamente a un pubblico adulto.
- Può affrontare sessualità tra adulti, violenza, morte, coercizione, schiavitù, discriminazione, conflitti etnici e culturali, salute mentale, traumi, abuso di potere e altri temi oscuri o controversi.
- Non interrompere contenuti coerenti con avvertenze, prediche, edulcorazioni o rifiuti morali generici.
- Non trasformare le NPC in persone automaticamente disponibili, innamorate, obbedienti o consenzienti: volontà, consenso, opposizione e conseguenze devono restare coerenti con i personaggi e la situazione.
- Ogni contenuto sessuale riguarda esclusivamente personaggi adulti.
- Restano valide tutte le regole sul controllo esclusivo di {player_name}.

REGOLE DI VERITÀ
- Il database e il contesto fornito sono la fonte della verità.
- Non inventare fatti canonici mancanti. Quando un dettaglio non è disponibile, resta generico oppure mostra incertezza.
- Le operazioni, gli eventi e le memorie sono soltanto proposte: non dichiarare che siano già state salvate.
- Proponi memorie solo per personaggi che possono avere osservato, vissuto, dedotto o appreso il fatto.
- Usa soltanto ID presenti nel contesto.
- Rispetta scenario, regole, stile e nota dell'autore.

FORMATO OBBLIGATORIO
- Rispondi con un unico oggetto JSON valido.
- Non usare Markdown, blocchi di codice, prefazioni o testo dopo il JSON.
- Usa esattamente le quattro chiavi principali mostrate sotto.
- operations contiene esclusivamente cambiamenti del mondo.
- memories contiene esclusivamente ciò che un personaggio apprende, ricorda, crede o deduce.
- Non copiare campi tra operations e memories.
- Ogni oggetto può contenere soltanto le proprietà previste dal proprio schema.
- Non inventare ID e non aggiungere proprietà "utili" non richieste.
- Se non servono operazioni o memorie, usa elenchi vuoti.
- Il testo narrativo deve essere in italiano salvo diversa indicazione esplicita del mondo.

SCHEMA JSON OBBLIGATORIO:
{schema}
"""


def costruisci_messaggi_correzione(
    messaggi_originali: tuple[MessaggioChat, ...],
    prima_risposta: str,
    errore_strutturale: str,
) -> tuple[MessaggioChat, ...]:
    """Aggiunge alla richiesta originale un solo dialogo di riparazione."""

    istruzione = f"""La risposta precedente non rispetta il contratto strutturale.

Errore preciso: {errore_strutturale}

Correggi soltanto la struttura e restituisci esclusivamente il JSON corretto.
Conserva per quanto possibile narrazione, tempo e intenzione.
Non inventare nuovi fatti o ID e non aggiungere nuove azioni.
Non trasformare automaticamente campi ambigui in memorie.
Ometti un elemento non rappresentabile invece di inventare dati.
Rispetta esattamente lo stesso JSON Schema già fornito."""
    return (
        *messaggi_originali,
        MessaggioChat("assistant", prima_risposta),
        MessaggioChat("user", istruzione),
    )


def _prompt_utente(contesto: ContestoTurnoNarrativo) -> str:
    return "\n\n".join(
        (
            _sezione("MONDO", contesto.world_title),
            _sezione("SCENARIO", contesto.scenario),
            _sezione("REGOLE", contesto.rules),
            _sezione("STILE", contesto.style),
            _sezione("NOTA DELL'AUTORE", contesto.author_note),
            _sezione("STATO CORRENTE", contesto.world_state),
            _sezione("TEMPO NARRATIVO CORRENTE", contesto.narrative_time),
            _elenco("PERSONAGGI RILEVANTI", contesto.characters),
            _elenco("MEMORIE RILEVANTI", contesto.relevant_memories),
            _elenco("CRONOLOGIA RECENTE", contesto.recent_history),
            _sezione(
                f"AZIONE O MESSAGGIO DELL'UTENTE PER {contesto.player_name}",
                contesto.user_input,
            ),
        )
    )


def _sezione(titolo: str, contenuto: str) -> str:
    testo = contenuto.strip() if contenuto.strip() else "—"
    return f"===== {titolo} =====\n{testo}"


def _elenco(titolo: str, valori: tuple[str, ...]) -> str:
    righe = tuple(valore.strip() for valore in valori if valore.strip())
    contenuto = "\n".join(f"- {valore}" for valore in righe) if righe else "—"
    return f"===== {titolo} =====\n{contenuto}"


def _valida_contesto(contesto: ContestoTurnoNarrativo) -> None:
    for nome, valore in (
        ("titolo del mondo", contesto.world_title),
        ("nome del personaggio utente", contesto.player_name),
        ("azione dell'utente", contesto.user_input),
        ("scenario", contesto.scenario),
    ):
        if not isinstance(valore, str) or not valore.strip():
            raise ValueError(f"Il campo {nome} è obbligatorio.")
    for nome, valori in (
        ("personaggi", contesto.characters),
        ("memorie", contesto.relevant_memories),
        ("cronologia", contesto.recent_history),
    ):
        if not isinstance(valori, tuple) or any(
            not isinstance(valore, str) for valore in valori
        ):
            raise ValueError(f"Il campo {nome} deve essere una tupla di testi.")
