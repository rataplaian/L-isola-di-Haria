"""Regole pure per audit, proposte e dry-run deterministici."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from .validation_models import (
    AmbitoValidazione,
    EntitaValidazione,
    EsitoProposta,
    EsitoSequenza,
    EventoValidazione,
    FotografiaValidazioneMondo,
    MemoriaValidazione,
    ProblemaValidazione,
    PropostaCambioStato,
    PropostaEpistemica,
    PropostaEventoDescrittivo,
    PropostaSpostamento,
    PropostaTrasferimento,
    PropostaValidazione,
    RapportoValidazione,
    RiferimentoEntita,
    SeveritaProblema,
)
from .world_state import TIPO_LUOGO, TIPO_OGGETTO, TIPO_PERSONAGGIO, TIPI_ENTITA


_ORDINE_SEVERITA = {
    SeveritaProblema.ERRORE: 0,
    SeveritaProblema.AVVERTIMENTO: 1,
    SeveritaProblema.INFORMAZIONE: 2,
}
_ORDINE_AMBITO = {
    AmbitoValidazione.INTEGRITA: 0,
    AmbitoValidazione.SPAZIO: 1,
    AmbitoValidazione.TEMPO: 2,
    AmbitoValidazione.INVENTARIO: 3,
    AmbitoValidazione.EPISTEMICA: 4,
}


def crea_rapporto(
    problemi: list[ProblemaValidazione] | tuple[ProblemaValidazione, ...],
) -> RapportoValidazione:
    return RapportoValidazione(
        problemi=tuple(sorted(problemi, key=chiave_problema))
    )


def chiave_problema(
    problema: ProblemaValidazione,
) -> tuple[int, int, int, str, tuple[tuple[str, str], ...], str]:
    indice = -1 if problema.indice_proposta is None else problema.indice_proposta
    riferimenti = tuple(
        (riferimento.entity_id, riferimento.nome)
        for riferimento in problema.entita
    )
    return (
        indice,
        _ORDINE_SEVERITA[problema.severita],
        _ORDINE_AMBITO[problema.ambito],
        problema.codice,
        riferimenti,
        problema.messaggio,
    )


def controlla_integrita(
    fotografia: FotografiaValidazioneMondo,
) -> RapportoValidazione:
    problemi: list[ProblemaValidazione] = []
    entita, duplicati_entita = _indicizza_entita(fotografia.entita)
    eventi, duplicati_eventi = _indicizza_eventi(fotografia)
    memorie, duplicati_memorie = _indicizza_memorie(fotografia)

    for entity_id in duplicati_entita:
        problemi.append(
            _problema(
                fotografia,
                "entita_duplicata",
                AmbitoValidazione.INTEGRITA,
                "La fotografia contiene più entità con la stessa identità.",
                entity_ids=(entity_id,),
            )
        )
    for event_id in duplicati_eventi:
        problemi.append(
            _problema(
                fotografia,
                "evento_duplicato",
                AmbitoValidazione.INTEGRITA,
                "La fotografia contiene lo stesso evento più di una volta.",
            )
        )
    for memory_id in duplicati_memorie:
        problemi.append(
            _problema(
                fotografia,
                "memoria_duplicata",
                AmbitoValidazione.INTEGRITA,
                "La fotografia contiene la stessa memoria più di una volta.",
            )
        )

    for voce in sorted(fotografia.entita, key=lambda elemento: elemento.entity_id):
        problemi.extend(_audit_entita(fotografia, voce, entita))
    problemi.extend(_audit_eventi(fotografia, entita))
    problemi.extend(_audit_memorie(fotografia, entita, eventi, memorie))
    return crea_rapporto(problemi)


def valida_proposta_pura(
    fotografia: FotografiaValidazioneMondo,
    proposta: PropostaValidazione,
    riferimento_temporale: datetime,
    *,
    indice_proposta: int = 0,
    istante_precedente: datetime | None = None,
) -> tuple[RapportoValidazione, datetime | None]:
    problemi: list[ProblemaValidazione] = []
    entita, _ = _indicizza_entita(fotografia.entita)
    memorie, _ = _indicizza_memorie(fotografia)
    istante = _valida_tempo_proposta(
        fotografia,
        proposta,
        riferimento_temporale,
        indice_proposta,
        istante_precedente,
        problemi,
    )
    problemi.extend(
        _valida_basi_epistemiche(
            fotografia,
            proposta,
            entita,
            memorie,
            indice_proposta,
        )
    )

    if isinstance(proposta, PropostaSpostamento):
        problemi.extend(
            _valida_spostamento(fotografia, proposta, entita, indice_proposta)
        )
    elif isinstance(proposta, PropostaTrasferimento):
        problemi.extend(
            _valida_trasferimento(fotografia, proposta, entita, indice_proposta)
        )
    elif isinstance(proposta, PropostaCambioStato):
        problemi.extend(
            _valida_cambio_stato(fotografia, proposta, entita, indice_proposta)
        )
    elif isinstance(proposta, PropostaEventoDescrittivo):
        problemi.extend(
            _valida_evento_descrittivo(
                fotografia, proposta, entita, indice_proposta
            )
        )
    elif isinstance(proposta, PropostaEpistemica):
        problemi.extend(
            _valida_proposta_epistemica(
                fotografia,
                proposta,
                entita,
                memorie,
                indice_proposta,
            )
        )
    else:
        problemi.append(
            _problema(
                fotografia,
                "tipo_proposta_non_supportato",
                AmbitoValidazione.INTEGRITA,
                "Il tipo di proposta non è supportato dal validatore.",
                indice_proposta,
            )
        )
    return crea_rapporto(problemi), istante


def valida_sequenza_pura(
    fotografia: FotografiaValidazioneMondo,
    proposte: tuple[PropostaValidazione, ...],
    riferimento_temporale: datetime,
) -> EsitoSequenza:
    audit = controlla_integrita(fotografia)
    proiezione = fotografia
    esiti: list[EsitoProposta] = []
    problemi_completi = list(audit.problemi)
    ultimo_istante: datetime | None = None
    integrita_bloccante = bool(audit.errori)

    for indice, proposta in enumerate(proposte):
        rapporto, istante = valida_proposta_pura(
            proiezione,
            proposta,
            riferimento_temporale,
            indice_proposta=indice,
            istante_precedente=ultimo_istante,
        )
        problemi_proposta = list(rapporto.problemi)
        if integrita_bloccante:
            problemi_proposta.append(
                _problema(
                    fotografia,
                    "mondo_non_integro",
                    AmbitoValidazione.INTEGRITA,
                    "La proposta non può essere simulata finché il mondo contiene errori di integrità.",
                    indice,
                )
            )
        rapporto_proposta = crea_rapporto(problemi_proposta)
        if rapporto_proposta.superata:
            proiezione = applica_in_memoria(proiezione, proposta)
            if istante is not None:
                ultimo_istante = istante
        esiti.append(
            EsitoProposta(
                indice=indice,
                proposta=proposta,
                rapporto=rapporto_proposta,
                fotografia=proiezione,
            )
        )
        problemi_completi.extend(rapporto_proposta.problemi)

    return EsitoSequenza(
        esiti=tuple(esiti),
        rapporto=crea_rapporto(problemi_completi),
        fotografia_finale=proiezione,
    )


def applica_in_memoria(
    fotografia: FotografiaValidazioneMondo,
    proposta: PropostaValidazione,
) -> FotografiaValidazioneMondo:
    sostituzioni: dict[str, EntitaValidazione] = {}
    entita, _ = _indicizza_entita(fotografia.entita)
    if isinstance(proposta, PropostaSpostamento):
        bersaglio = entita.get(proposta.entity_id)
        if bersaglio is not None:
            sostituzioni[bersaglio.entity_id] = replace(
                bersaglio,
                location_id=proposta.location_id,
                version=bersaglio.version + 1,
            )
            if bersaglio.entity_type == TIPO_PERSONAGGIO:
                for oggetto in fotografia.entita:
                    if oggetto.holder_id == bersaglio.entity_id:
                        sostituzioni[oggetto.entity_id] = replace(
                            oggetto,
                            location_id=proposta.location_id,
                            version=oggetto.version + 1,
                        )
    elif isinstance(proposta, PropostaTrasferimento):
        oggetto = entita.get(proposta.object_id)
        possessore = entita.get(proposta.holder_id)
        if oggetto is not None and possessore is not None:
            sostituzioni[oggetto.entity_id] = replace(
                oggetto,
                holder_id=possessore.entity_id,
                location_id=possessore.location_id,
                version=oggetto.version + 1,
            )
    elif isinstance(proposta, PropostaCambioStato):
        bersaglio = entita.get(proposta.target_id)
        if bersaglio is not None:
            sostituzioni[bersaglio.entity_id] = replace(
                bersaglio,
                status=(bersaglio.status if proposta.status is None else proposta.status.strip()),
                condition=(bersaglio.condition if proposta.condition is None else proposta.condition.strip()),
                accessibility=(
                    bersaglio.accessibility
                    if proposta.accessibility is None
                    else proposta.accessibility
                ),
                version=bersaglio.version + 1,
            )
    if not sostituzioni:
        return fotografia
    return replace(
        fotografia,
        entita=tuple(
            sostituzioni.get(voce.entity_id, voce) for voce in fotografia.entita
        ),
    )


def _audit_entita(
    fotografia: FotografiaValidazioneMondo,
    voce: EntitaValidazione,
    entita: dict[str, EntitaValidazione],
) -> list[ProblemaValidazione]:
    problemi: list[ProblemaValidazione] = []
    if voce.world_id != fotografia.world_id:
        problemi.append(
            _problema(
                fotografia,
                "entita_altro_mondo",
                AmbitoValidazione.INTEGRITA,
                f"L’entità «{voce.canonical_name}» appartiene a un altro mondo.",
                entity_ids=(voce.entity_id,),
            )
        )
    if voce.entity_type not in TIPI_ENTITA:
        problemi.append(
            _problema(
                fotografia,
                "tipo_entita_non_valido",
                AmbitoValidazione.INTEGRITA,
                f"Il tipo dell’entità «{voce.canonical_name}» non è riconosciuto.",
                entity_ids=(voce.entity_id,),
            )
        )
    if voce.version < 1:
        problemi.append(
            _problema(
                fotografia,
                "versione_stato_non_valida",
                AmbitoValidazione.INTEGRITA,
                f"Lo stato corrente di «{voce.canonical_name}» ha una versione non valida.",
                entity_ids=(voce.entity_id,),
            )
        )
    problemi.extend(
        _controlla_riferimento_luogo(
            fotografia, voce.location_id, entita, None, voce.entity_id
        )
    )
    if voce.holder_id is not None:
        possessore = entita.get(voce.holder_id)
        if possessore is None:
            problemi.append(
                _problema(
                    fotografia,
                    "possessore_inesistente",
                    AmbitoValidazione.INVENTARIO,
                    f"Il possessore di «{voce.canonical_name}» non esiste.",
                    entity_ids=(voce.entity_id, voce.holder_id),
                )
            )
        elif possessore.entity_type != TIPO_PERSONAGGIO:
            problemi.append(
                _problema(
                    fotografia,
                    "possessore_non_personaggio",
                    AmbitoValidazione.INVENTARIO,
                    f"Il possessore indicato per «{voce.canonical_name}» non è un personaggio.",
                    entity_ids=(voce.entity_id, possessore.entity_id),
                )
            )
        elif voce.entity_type == TIPO_OGGETTO and voce.location_id != possessore.location_id:
            problemi.append(
                _problema(
                    fotografia,
                    "oggetto_lontano_possessore",
                    AmbitoValidazione.INVENTARIO,
                    f"«{voce.canonical_name}» non si trova insieme al proprio possessore.",
                    entity_ids=(voce.entity_id, possessore.entity_id),
                )
            )
    if voce.entity_type == TIPO_PERSONAGGIO and voce.holder_id is not None:
        problemi.append(
            _problema(
                fotografia,
                "personaggio_con_possessore",
                AmbitoValidazione.INTEGRITA,
                f"Il personaggio «{voce.canonical_name}» non può avere un possessore.",
                entity_ids=(voce.entity_id, voce.holder_id),
            )
        )
    if voce.entity_type == TIPO_LUOGO and (
        voce.location_id is not None or voce.holder_id is not None
    ):
        problemi.append(
            _problema(
                fotografia,
                "luogo_con_riferimenti_non_ammessi",
                AmbitoValidazione.INTEGRITA,
                f"Il luogo «{voce.canonical_name}» non può avere posizione o possessore.",
                entity_ids=(voce.entity_id,),
            )
        )
    return problemi


def _audit_eventi(
    fotografia: FotografiaValidazioneMondo,
    entita: dict[str, EntitaValidazione],
) -> list[ProblemaValidazione]:
    problemi: list[ProblemaValidazione] = []
    precedente: datetime | None = None
    for evento in fotografia.eventi:
        if evento.world_id != fotografia.world_id:
            problemi.append(
                _problema(
                    fotografia,
                    "evento_altro_mondo",
                    AmbitoValidazione.INTEGRITA,
                    "Un evento appartiene a un mondo diverso da quello controllato.",
                )
            )
        for riferimento, ruolo in (
            (evento.actor_id, "attore"),
            (evento.target_id, "bersaglio"),
        ):
            if riferimento is not None and riferimento not in entita:
                problemi.append(
                    _problema(
                        fotografia,
                        f"evento_{ruolo}_inesistente",
                        AmbitoValidazione.INTEGRITA,
                        f"L’{ruolo} indicato da un evento non esiste nel mondo.",
                        entity_ids=(riferimento,),
                    )
                )
        problemi.extend(
            _controlla_riferimento_luogo(
                fotografia, evento.location_id, entita, None, None
            )
        )
        istante = _istante_utc(evento.occurred_at)
        if istante is None:
            problemi.append(
                _problema(
                    fotografia,
                    "timestamp_evento_non_valido",
                    AmbitoValidazione.TEMPO,
                    "Un evento contiene un istante privo di fuso orario o non valido.",
                )
            )
        elif precedente is not None and istante < precedente:
            problemi.append(
                _problema(
                    fotografia,
                    "eventi_non_ordinati",
                    AmbitoValidazione.TEMPO,
                    "Gli eventi della fotografia non sono in ordine temporale non decrescente.",
                )
            )
        if istante is not None:
            precedente = istante
    return problemi


def _audit_memorie(
    fotografia: FotografiaValidazioneMondo,
    entita: dict[str, EntitaValidazione],
    eventi: dict[str, EventoValidazione],
    memorie: dict[str, MemoriaValidazione],
) -> list[ProblemaValidazione]:
    problemi: list[ProblemaValidazione] = []
    successori: dict[str, list[MemoriaValidazione]] = {}
    for memoria in fotografia.memorie:
        if memoria.supersedes_memory_id is not None:
            successori.setdefault(memoria.supersedes_memory_id, []).append(memoria)
    for precedente_id, elenco in sorted(successori.items()):
        if len(elenco) > 1:
            problemi.append(
                _problema(
                    fotografia,
                    "memoria_con_piu_successori",
                    AmbitoValidazione.EPISTEMICA,
                    "Una memoria possiede più di un successore diretto.",
                )
            )
    for memoria in fotografia.memorie:
        personaggio = entita.get(memoria.character_id)
        if memoria.world_id != fotografia.world_id:
            problemi.append(
                _problema(
                    fotografia,
                    "memoria_altro_mondo",
                    AmbitoValidazione.INTEGRITA,
                    "Una memoria appartiene a un mondo diverso da quello controllato.",
                )
            )
        if personaggio is None:
            problemi.append(
                _problema(
                    fotografia,
                    "personaggio_memoria_inesistente",
                    AmbitoValidazione.EPISTEMICA,
                    "Il personaggio proprietario di una memoria non esiste.",
                    entity_ids=(memoria.character_id,),
                )
            )
        elif personaggio.entity_type != TIPO_PERSONAGGIO:
            problemi.append(
                _problema(
                    fotografia,
                    "proprietario_memoria_non_personaggio",
                    AmbitoValidazione.EPISTEMICA,
                    "Il proprietario di una memoria non è un personaggio.",
                    entity_ids=(personaggio.entity_id,),
                )
            )
        if memoria.event_id is not None and memoria.event_id not in eventi:
            problemi.append(
                _problema(
                    fotografia,
                    "evento_memoria_inesistente",
                    AmbitoValidazione.INTEGRITA,
                    "Una memoria fa riferimento a un evento inesistente.",
                )
            )
        for entity_id in memoria.entity_ids:
            if entity_id not in entita:
                problemi.append(
                    _problema(
                        fotografia,
                        "entita_memoria_inesistente",
                        AmbitoValidazione.EPISTEMICA,
                        "Una memoria è collegata a un’entità inesistente.",
                        entity_ids=(entity_id,),
                    )
                )
        if memoria.source_entity_id is not None and memoria.source_entity_id not in entita:
            problemi.append(
                _problema(
                    fotografia,
                    "fonte_entita_inesistente",
                    AmbitoValidazione.EPISTEMICA,
                    "L’entità indicata come fonte di una memoria non esiste.",
                    entity_ids=(memoria.source_entity_id,),
                )
            )
        if _istante_utc(memoria.learned_at) is None:
            problemi.append(
                _problema(
                    fotografia,
                    "timestamp_memoria_non_valido",
                    AmbitoValidazione.TEMPO,
                    "Una memoria contiene un istante privo di fuso orario o non valido.",
                )
            )
        if memoria.supersedes_memory_id == memoria.memory_id:
            problemi.append(
                _problema(
                    fotografia,
                    "memoria_autoreferenziale",
                    AmbitoValidazione.EPISTEMICA,
                    "Una memoria non può sostituire sé stessa.",
                )
            )
        elif memoria.supersedes_memory_id is not None:
            precedente = memorie.get(memoria.supersedes_memory_id)
            if precedente is None:
                problemi.append(
                    _problema(
                        fotografia,
                        "memoria_precedente_inesistente",
                        AmbitoValidazione.EPISTEMICA,
                        "La memoria precedente indicata non esiste.",
                    )
                )
            elif precedente.character_id != memoria.character_id:
                problemi.append(
                    _problema(
                        fotografia,
                        "correzione_altro_personaggio",
                        AmbitoValidazione.EPISTEMICA,
                        "Una correzione collega memorie di personaggi diversi.",
                    )
                )
        ha_successore = memoria.memory_id in successori
        if memoria.is_current == ha_successore or (
            ha_successore and memoria.effective_status != "superseded"
        ):
            problemi.append(
                _problema(
                    fotografia,
                    "stato_corrente_memoria_incoerente",
                    AmbitoValidazione.EPISTEMICA,
                    "Lo stato corrente di una memoria non coincide con la catena di correzione.",
                )
            )
        viste: set[str] = set()
        for source_memory_id in memoria.source_memory_ids:
            if source_memory_id in viste:
                problemi.append(
                    _problema(
                        fotografia,
                        "fonte_memoria_duplicata",
                        AmbitoValidazione.EPISTEMICA,
                        "Una memoria origine è indicata più di una volta.",
                    )
                )
            viste.add(source_memory_id)
            fonte = memorie.get(source_memory_id)
            if fonte is None:
                problemi.append(
                    _problema(
                        fotografia,
                        "fonte_memoria_inesistente",
                        AmbitoValidazione.EPISTEMICA,
                        "Una memoria origine non esiste.",
                    )
                )
            elif fonte.character_id != memoria.character_id:
                problemi.append(
                    _problema(
                        fotografia,
                        "fonte_memoria_altro_personaggio",
                        AmbitoValidazione.EPISTEMICA,
                        "Una memoria origine appartiene a un altro personaggio.",
                    )
                )
    return problemi


def _valida_spostamento(
    fotografia: FotografiaValidazioneMondo,
    proposta: PropostaSpostamento,
    entita: dict[str, EntitaValidazione],
    indice: int,
) -> list[ProblemaValidazione]:
    problemi: list[ProblemaValidazione] = []
    bersaglio = entita.get(proposta.entity_id)
    if bersaglio is None:
        return [
            _problema(
                fotografia,
                "bersaglio_spostamento_inesistente",
                AmbitoValidazione.SPAZIO,
                "L’entità da spostare non esiste.",
                indice,
                (proposta.entity_id,),
            )
        ]
    if bersaglio.entity_type not in {TIPO_PERSONAGGIO, TIPO_OGGETTO}:
        problemi.append(
            _problema(
                fotografia,
                "tipo_spostamento_non_valido",
                AmbitoValidazione.SPAZIO,
                f"«{bersaglio.canonical_name}» non può essere spostata direttamente.",
                indice,
                (bersaglio.entity_id,),
            )
        )
    destinazione = _richiedi_luogo_accessibile(
        fotografia, proposta.location_id, entita, indice, problemi
    )
    if bersaglio.entity_type == TIPO_OGGETTO:
        if bersaglio.holder_id is not None:
            problemi.append(
                _problema(
                    fotografia,
                    "oggetto_posseduto_spostato_direttamente",
                    AmbitoValidazione.INVENTARIO,
                    f"«{bersaglio.canonical_name}» è posseduta e deve essere trasferita.",
                    indice,
                    (bersaglio.entity_id, bersaglio.holder_id),
                )
            )
        if not bersaglio.accessibility:
            problemi.append(
                _problema(
                    fotografia,
                    "oggetto_inaccessibile",
                    AmbitoValidazione.SPAZIO,
                    f"«{bersaglio.canonical_name}» non è accessibile.",
                    indice,
                    (bersaglio.entity_id,),
                )
            )
    if destinazione is not None and bersaglio.location_id == destinazione.entity_id:
        problemi.append(
            _problema(
                fotografia,
                "spostamento_senza_cambiamenti",
                AmbitoValidazione.SPAZIO,
                f"«{bersaglio.canonical_name}» si trova già nella destinazione proposta.",
                indice,
                (bersaglio.entity_id, destinazione.entity_id),
            )
        )
    if proposta.actor_id is not None:
        attore = _richiedi_personaggio(
            fotografia, proposta.actor_id, entita, indice, problemi
        )
        if (
            attore is not None
            and attore.entity_id != bersaglio.entity_id
            and attore.location_id != bersaglio.location_id
        ):
            problemi.append(
                _problema(
                    fotografia,
                    "interazione_spostamento_remota",
                    AmbitoValidazione.SPAZIO,
                    "Attore ed entità da spostare non sono compresenti.",
                    indice,
                    (attore.entity_id, bersaglio.entity_id),
                )
            )
    return problemi


def _valida_trasferimento(
    fotografia: FotografiaValidazioneMondo,
    proposta: PropostaTrasferimento,
    entita: dict[str, EntitaValidazione],
    indice: int,
) -> list[ProblemaValidazione]:
    problemi: list[ProblemaValidazione] = []
    oggetto = entita.get(proposta.object_id)
    if oggetto is None:
        problemi.append(
            _problema(
                fotografia,
                "oggetto_trasferimento_inesistente",
                AmbitoValidazione.INVENTARIO,
                "L’oggetto da trasferire non esiste.",
                indice,
                (proposta.object_id,),
            )
        )
    elif oggetto.entity_type != TIPO_OGGETTO:
        problemi.append(
            _problema(
                fotografia,
                "trasferimento_richiede_oggetto",
                AmbitoValidazione.INVENTARIO,
                f"«{oggetto.canonical_name}» non è un oggetto trasferibile.",
                indice,
                (oggetto.entity_id,),
            )
        )
    possessore = _richiedi_personaggio(
        fotografia, proposta.holder_id, entita, indice, problemi
    )
    attore_id = proposta.actor_id or proposta.holder_id
    attore = (
        possessore
        if attore_id == proposta.holder_id
        else _richiedi_personaggio(
            fotografia, attore_id, entita, indice, problemi
        )
    )
    if possessore is not None:
        if possessore.location_id is None:
            problemi.append(
                _problema(
                    fotografia,
                    "possessore_senza_posizione",
                    AmbitoValidazione.INVENTARIO,
                    f"«{possessore.canonical_name}» non possiede una posizione valida.",
                    indice,
                    (possessore.entity_id,),
                )
            )
        else:
            _richiedi_luogo_accessibile(
                fotografia, possessore.location_id, entita, indice, problemi
            )
    if oggetto is not None and oggetto.entity_type == TIPO_OGGETTO:
        if not oggetto.accessibility:
            problemi.append(
                _problema(
                    fotografia,
                    "oggetto_inaccessibile",
                    AmbitoValidazione.INVENTARIO,
                    f"«{oggetto.canonical_name}» non è accessibile.",
                    indice,
                    (oggetto.entity_id,),
                )
            )
        if (
            possessore is not None
            and oggetto.holder_id == possessore.entity_id
            and oggetto.location_id == possessore.location_id
        ):
            problemi.append(
                _problema(
                    fotografia,
                    "trasferimento_duplicato",
                    AmbitoValidazione.INVENTARIO,
                    f"«{oggetto.canonical_name}» appartiene già al possessore indicato.",
                    indice,
                    (oggetto.entity_id, possessore.entity_id),
                )
            )
        if (
            possessore is not None
            and possessore.location_id is not None
            and oggetto.location_id != possessore.location_id
        ):
            problemi.append(
                _problema(
                    fotografia,
                    "trasferimento_remoto",
                    AmbitoValidazione.SPAZIO,
                    "Oggetto e nuovo possessore non sono compresenti.",
                    indice,
                    (oggetto.entity_id, possessore.entity_id),
                )
            )
        if (
            attore is not None
            and attore.location_id != oggetto.location_id
        ):
            problemi.append(
                _problema(
                    fotografia,
                    "attore_trasferimento_remoto",
                    AmbitoValidazione.SPAZIO,
                    "L’attore non è presente insieme all’oggetto da trasferire.",
                    indice,
                    (attore.entity_id, oggetto.entity_id),
                )
            )
    return problemi


def _valida_cambio_stato(
    fotografia: FotografiaValidazioneMondo,
    proposta: PropostaCambioStato,
    entita: dict[str, EntitaValidazione],
    indice: int,
) -> list[ProblemaValidazione]:
    problemi: list[ProblemaValidazione] = []
    bersaglio = entita.get(proposta.target_id)
    if bersaglio is None:
        problemi.append(
            _problema(
                fotografia,
                "bersaglio_stato_inesistente",
                AmbitoValidazione.INTEGRITA,
                "L’entità da aggiornare non esiste.",
                indice,
                (proposta.target_id,),
            )
        )
        return problemi
    if proposta.actor_id is not None:
        _richiedi_personaggio(
            fotografia, proposta.actor_id, entita, indice, problemi
        )
    status_valido = proposta.status is None or (
        isinstance(proposta.status, str) and bool(proposta.status.strip())
    )
    condizione_valida = proposta.condition is None or (
        isinstance(proposta.condition, str) and bool(proposta.condition.strip())
    )
    if not status_valido:
        problemi.append(
            _problema(
                fotografia,
                "status_non_valido",
                AmbitoValidazione.INTEGRITA,
                "Lo stato proposto deve contenere un testo leggibile.",
                indice,
                (bersaglio.entity_id,),
            )
        )
    if not condizione_valida:
        problemi.append(
            _problema(
                fotografia,
                "condizione_non_valida",
                AmbitoValidazione.INTEGRITA,
                "La condizione proposta deve contenere un testo leggibile.",
                indice,
                (bersaglio.entity_id,),
            )
        )
    if proposta.accessibility is not None and not isinstance(
        proposta.accessibility, bool
    ):
        problemi.append(
            _problema(
                fotografia,
                "accessibilita_non_valida",
                AmbitoValidazione.INTEGRITA,
                "L’accessibilità proposta deve essere vera o falsa.",
                indice,
                (bersaglio.entity_id,),
            )
        )
    nessun_campo = (
        proposta.status is None
        and proposta.condition is None
        and proposta.accessibility is None
    )
    invariata = status_valido and condizione_valida and (
        (proposta.status is None or proposta.status.strip() == bersaglio.status)
        and (
            proposta.condition is None
            or proposta.condition.strip() == (bersaglio.condition or "")
        )
        and (
            proposta.accessibility is None
            or proposta.accessibility == bersaglio.accessibility
        )
    )
    if nessun_campo or invariata:
        problemi.append(
            _problema(
                fotografia,
                "stato_senza_cambiamenti",
                AmbitoValidazione.INTEGRITA,
                f"La proposta non cambia lo stato corrente di «{bersaglio.canonical_name}».",
                indice,
                (bersaglio.entity_id,),
            )
        )
    return problemi


def _valida_evento_descrittivo(
    fotografia: FotografiaValidazioneMondo,
    proposta: PropostaEventoDescrittivo,
    entita: dict[str, EntitaValidazione],
    indice: int,
) -> list[ProblemaValidazione]:
    problemi: list[ProblemaValidazione] = []
    if not isinstance(proposta.event_type, str) or not proposta.event_type.strip():
        problemi.append(
            _problema(
                fotografia,
                "tipo_evento_vuoto",
                AmbitoValidazione.INTEGRITA,
                "Il tipo dell’evento descrittivo è obbligatorio.",
                indice,
            )
        )
    for entity_id, ruolo, messaggio in (
        (proposta.actor_id, "attore", "L’attore dell’evento descrittivo non esiste."),
        (proposta.target_id, "bersaglio", "Il bersaglio dell’evento descrittivo non esiste."),
    ):
        if entity_id is not None and entity_id not in entita:
            problemi.append(
                _problema(
                    fotografia,
                    f"{ruolo}_evento_inesistente",
                    AmbitoValidazione.INTEGRITA,
                    messaggio,
                    indice,
                    (entity_id,),
                )
            )
    problemi.extend(
        _controlla_riferimento_luogo(
            fotografia, proposta.location_id, entita, indice, None
        )
    )
    return problemi


def _valida_proposta_epistemica(
    fotografia: FotografiaValidazioneMondo,
    proposta: PropostaEpistemica,
    entita: dict[str, EntitaValidazione],
    memorie: dict[str, MemoriaValidazione],
    indice: int,
) -> list[ProblemaValidazione]:
    problemi: list[ProblemaValidazione] = []
    attore = _richiedi_personaggio(
        fotografia, proposta.actor_id, entita, indice, problemi
    )
    bersaglio = None
    if proposta.target_id is not None:
        bersaglio = entita.get(proposta.target_id)
        if bersaglio is None:
            problemi.append(
                _problema(
                    fotografia,
                    "bersaglio_epistemico_inesistente",
                    AmbitoValidazione.EPISTEMICA,
                    "L’entità oggetto dell’affermazione non esiste.",
                    indice,
                    (proposta.target_id,),
                )
            )
    if proposta.location_id is not None:
        _richiedi_luogo_accessibile(
            fotografia, proposta.location_id, entita, indice, problemi
        )
    if attore is None or bersaglio is None:
        return problemi
    percepibile = (
        attore.location_id is not None
        and bersaglio.location_id == attore.location_id
        and bersaglio.accessibility
    )
    if not percepibile:
        basi = [memorie.get(memory_id) for memory_id in proposta.memory_ids]
        conosciuta = any(
            memoria is not None
            and memoria.character_id == attore.entity_id
            and memoria.is_current
            and memoria.effective_status != "superseded"
            and bersaglio.entity_id in memoria.entity_ids
            for memoria in basi
        )
        if not conosciuta:
            problemi.append(
                _problema(
                    fotografia,
                    "conoscenza_remota_senza_memoria",
                    AmbitoValidazione.EPISTEMICA,
                    f"«{attore.canonical_name}» non dispone di una memoria corrente sull’entità remota.",
                    indice,
                    (attore.entity_id, bersaglio.entity_id),
                )
            )
    return problemi


def _valida_basi_epistemiche(
    fotografia: FotografiaValidazioneMondo,
    proposta: PropostaValidazione,
    entita: dict[str, EntitaValidazione],
    memorie: dict[str, MemoriaValidazione],
    indice: int,
) -> list[ProblemaValidazione]:
    problemi: list[ProblemaValidazione] = []
    memory_ids = proposta.memory_ids
    if len(set(memory_ids)) != len(memory_ids):
        problemi.append(
            _problema(
                fotografia,
                "base_epistemica_duplicata",
                AmbitoValidazione.EPISTEMICA,
                "La stessa memoria è stata indicata più di una volta.",
                indice,
            )
        )
    actor_id = proposta.actor_id
    if memory_ids and actor_id is None:
        problemi.append(
            _problema(
                fotografia,
                "base_epistemica_senza_attore",
                AmbitoValidazione.EPISTEMICA,
                "Le memorie dichiarate richiedono un personaggio attore.",
                indice,
            )
        )
        return problemi
    for memory_id in memory_ids:
        memoria = memorie.get(memory_id)
        if memoria is None:
            problemi.append(
                _problema(
                    fotografia,
                    "memoria_dichiarata_inesistente",
                    AmbitoValidazione.EPISTEMICA,
                    "Una memoria dichiarata come base non esiste nel mondo.",
                    indice,
                )
            )
            continue
        if memoria.world_id != fotografia.world_id:
            problemi.append(
                _problema(
                    fotografia,
                    "memoria_dichiarata_altro_mondo",
                    AmbitoValidazione.EPISTEMICA,
                    "Una memoria dichiarata appartiene a un altro mondo.",
                    indice,
                )
            )
        if memoria.character_id != actor_id:
            problemi.append(
                _problema(
                    fotografia,
                    "memoria_altro_personaggio",
                    AmbitoValidazione.EPISTEMICA,
                    "Una memoria dichiarata appartiene a un altro personaggio.",
                    indice,
                    tuple(
                        valore
                        for valore in (actor_id, memoria.character_id)
                        if valore is not None
                    ),
                )
            )
        if not memoria.is_current or memoria.effective_status == "superseded":
            problemi.append(
                _problema(
                    fotografia,
                    "memoria_non_corrente",
                    AmbitoValidazione.EPISTEMICA,
                    "Una memoria dichiarata non è più corrente.",
                    indice,
                )
            )
        if memoria.knowledge_type == "inference":
            for source_memory_id in memoria.source_memory_ids:
                fonte = memorie.get(source_memory_id)
                if fonte is not None and fonte.character_id != memoria.character_id:
                    problemi.append(
                        _problema(
                            fotografia,
                            "inferenza_fonte_altro_personaggio",
                            AmbitoValidazione.EPISTEMICA,
                            "Una fonte dell’inferenza appartiene a un altro personaggio.",
                            indice,
                        )
                    )
    return problemi


def _valida_tempo_proposta(
    fotografia: FotografiaValidazioneMondo,
    proposta: PropostaValidazione,
    riferimento: datetime,
    indice: int,
    istante_precedente: datetime | None,
    problemi: list[ProblemaValidazione],
) -> datetime | None:
    if not isinstance(riferimento, datetime) or riferimento.tzinfo is None or riferimento.utcoffset() is None:
        problemi.append(
            _problema(
                fotografia,
                "riferimento_temporale_senza_fuso",
                AmbitoValidazione.TEMPO,
                "L’istante di riferimento deve includere il fuso orario.",
                indice,
            )
        )
        riferimento_utc = None
    else:
        riferimento_utc = riferimento.astimezone(timezone.utc)
    if proposta.occurred_at is None:
        istante = riferimento_utc
    else:
        istante = _istante_utc(proposta.occurred_at)
        if istante is None:
            problemi.append(
                _problema(
                    fotografia,
                    "timestamp_proposta_senza_fuso",
                    AmbitoValidazione.TEMPO,
                    "L’istante proposto deve essere valido e includere il fuso orario.",
                    indice,
                )
            )
    if istante is None:
        return None
    ultimi_eventi = [
        valore
        for valore in (_istante_utc(evento.occurred_at) for evento in fotografia.eventi)
        if valore is not None
    ]
    if ultimi_eventi and istante < max(ultimi_eventi):
        problemi.append(
            _problema(
                fotografia,
                "proposta_anteriore_ultimo_evento",
                AmbitoValidazione.TEMPO,
                "La proposta è anteriore all’ultimo evento registrato.",
                indice,
            )
        )
    if istante_precedente is not None and istante < istante_precedente:
        problemi.append(
            _problema(
                fotografia,
                "sequenza_temporale_non_ordinata",
                AmbitoValidazione.TEMPO,
                "La sequenza contiene istanti non ordinati.",
                indice,
            )
        )
    return istante


def _richiedi_personaggio(
    fotografia: FotografiaValidazioneMondo,
    entity_id: str,
    entita: dict[str, EntitaValidazione],
    indice: int,
    problemi: list[ProblemaValidazione],
) -> EntitaValidazione | None:
    voce = entita.get(entity_id)
    if voce is None:
        problemi.append(
            _problema(
                fotografia,
                "personaggio_inesistente",
                AmbitoValidazione.INTEGRITA,
                "Il personaggio indicato non esiste.",
                indice,
                (entity_id,),
            )
        )
        return None
    if voce.entity_type != TIPO_PERSONAGGIO:
        problemi.append(
            _problema(
                fotografia,
                "entita_non_personaggio",
                AmbitoValidazione.INTEGRITA,
                f"«{voce.canonical_name}» non è un personaggio.",
                indice,
                (voce.entity_id,),
            )
        )
        return None
    return voce


def _richiedi_luogo_accessibile(
    fotografia: FotografiaValidazioneMondo,
    location_id: str,
    entita: dict[str, EntitaValidazione],
    indice: int,
    problemi: list[ProblemaValidazione],
) -> EntitaValidazione | None:
    luogo = entita.get(location_id)
    if luogo is None:
        problemi.append(
            _problema(
                fotografia,
                "luogo_inesistente",
                AmbitoValidazione.SPAZIO,
                "Il luogo indicato non esiste.",
                indice,
                (location_id,),
            )
        )
        return None
    if luogo.entity_type != TIPO_LUOGO:
        problemi.append(
            _problema(
                fotografia,
                "destinazione_non_luogo",
                AmbitoValidazione.SPAZIO,
                f"«{luogo.canonical_name}» non è un luogo.",
                indice,
                (luogo.entity_id,),
            )
        )
        return None
    if not luogo.accessibility:
        problemi.append(
            _problema(
                fotografia,
                "destinazione_inaccessibile",
                AmbitoValidazione.SPAZIO,
                f"Il luogo «{luogo.canonical_name}» non è accessibile.",
                indice,
                (luogo.entity_id,),
            )
        )
    return luogo


def _controlla_riferimento_luogo(
    fotografia: FotografiaValidazioneMondo,
    location_id: str | None,
    entita: dict[str, EntitaValidazione],
    indice: int | None,
    owner_id: str | None,
) -> list[ProblemaValidazione]:
    if location_id is None:
        return []
    luogo = entita.get(location_id)
    riferimenti = tuple(
        valore for valore in (owner_id, location_id) if valore is not None
    )
    if luogo is None:
        return [
            _problema(
                fotografia,
                "posizione_inesistente",
                AmbitoValidazione.SPAZIO,
                "Una posizione indicata non esiste nel mondo.",
                indice,
                riferimenti,
            )
        ]
    if luogo.entity_type != TIPO_LUOGO:
        return [
            _problema(
                fotografia,
                "posizione_non_luogo",
                AmbitoValidazione.SPAZIO,
                f"«{luogo.canonical_name}» è usata come posizione ma non è un luogo.",
                indice,
                riferimenti,
            )
        ]
    return []


def _problema(
    fotografia: FotografiaValidazioneMondo,
    codice: str,
    ambito: AmbitoValidazione,
    messaggio: str,
    indice_proposta: int | None = None,
    entity_ids: tuple[str, ...] = (),
    severita: SeveritaProblema = SeveritaProblema.ERRORE,
) -> ProblemaValidazione:
    nomi = {
        entita.entity_id: entita.canonical_name for entita in fotografia.entita
    }
    riferimenti = tuple(
        sorted(
            {
                RiferimentoEntita(entity_id=entity_id, nome=nomi.get(entity_id, "Entità non disponibile"))
                for entity_id in entity_ids
            }
        )
    )
    return ProblemaValidazione(
        codice=codice,
        severita=severita,
        ambito=ambito,
        messaggio=messaggio,
        indice_proposta=indice_proposta,
        entita=riferimenti,
    )


def _istante_utc(valore: str) -> datetime | None:
    if not isinstance(valore, str) or not valore.strip():
        return None
    testo = valore.strip()
    if testo.endswith("Z"):
        testo = testo[:-1] + "+00:00"
    try:
        istante = datetime.fromisoformat(testo)
    except ValueError:
        return None
    if istante.tzinfo is None or istante.utcoffset() is None:
        return None
    return istante.astimezone(timezone.utc)


def _indicizza_entita(
    entita: tuple[EntitaValidazione, ...],
) -> tuple[dict[str, EntitaValidazione], tuple[str, ...]]:
    risultato: dict[str, EntitaValidazione] = {}
    duplicati: set[str] = set()
    for voce in entita:
        if voce.entity_id in risultato:
            duplicati.add(voce.entity_id)
        else:
            risultato[voce.entity_id] = voce
    return risultato, tuple(sorted(duplicati))


def _indicizza_eventi(
    fotografia: FotografiaValidazioneMondo,
) -> tuple[dict[str, EventoValidazione], tuple[str, ...]]:
    risultato: dict[str, EventoValidazione] = {}
    duplicati: set[str] = set()
    for evento in fotografia.eventi:
        if evento.event_id in risultato:
            duplicati.add(evento.event_id)
        else:
            risultato[evento.event_id] = evento
    return risultato, tuple(sorted(duplicati))


def _indicizza_memorie(
    fotografia: FotografiaValidazioneMondo,
) -> tuple[dict[str, MemoriaValidazione], tuple[str, ...]]:
    risultato: dict[str, MemoriaValidazione] = {}
    duplicati: set[str] = set()
    for memoria in fotografia.memorie:
        if memoria.memory_id in risultato:
            duplicati.add(memoria.memory_id)
        else:
            risultato[memoria.memory_id] = memoria
    return risultato, tuple(sorted(duplicati))
