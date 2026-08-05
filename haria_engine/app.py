"""Interfaccia desktop Tkinter completamente leggibile in italiano."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .ai_models import (
    ConfigurazioneAI,
    ModelloLocale,
    RispostaTestuale,
    RisultatoConnessione,
    valida_configurazione_ai,
)
from .async_coordinator import CoordinatoreAsincrono, EsitoAsincrono
from .editor_state import SceltaModifiche, StatoEditor
from .errors import ErroreConfigurazioneAI, ErroreHaria
from .memories import MemoriaPersonaggio
from .models import Mondo
from .paths import database_predefinito
from .service import ServizioMondi
from .validation_models import AmbitoValidazione, SeveritaProblema
from .world_state import EntitaMondo, TIPO_OGGETTO, TIPO_PERSONAGGIO


UI_TEXT = {
    "titolo_finestra": "Haria Engine — Editor del mondo",
    "importa": "Importa mini-Bibbia",
    "esporta": "Esporta mondo",
    "nessun_mondo": "Nessun mondo importato",
    "istruzione_importa": "Importa una mini-Bibbia da una cartella per iniziare.",
    "scenario": "Scenario",
    "impostazioni": "Impostazioni narrative",
    "cronologia": "Cronologia versioni",
    "salva": "Salva nuova versione",
    "ripristina": "Ripristina versione selezionata",
    "versione": "Versione corrente: {numero}",
    "stato_pronto": "Pronto",
    "errore": "Errore",
    "operazione_completata": "Operazione completata",
    "importazione_completata": "Mini-Bibbia importata correttamente.",
    "salvataggio_completato": "Nuova versione salvata correttamente.",
    "ripristino_completato": "Versione ripristinata creando una nuova versione recuperabile.",
    "esportazione_completata": "Mondo esportato nella cartella:\n{cartella}",
    "conferma_ripristino": "Ripristinare la versione {numero}? La versione corrente resterà nella cronologia.",
    "seleziona_versione": "Seleziona una versione dalla cronologia.",
    "seleziona_sorgente": "Seleziona la cartella della mini-Bibbia",
    "seleziona_destinazione": "Seleziona la cartella di destinazione",
    "numero_versione": "Versione",
    "data_versione": "Data",
    "motivo_versione": "Operazione",
    "nessuna_impostazione": "Il pacchetto non contiene impostazioni narrative.",
    "modifiche_non_salvate": "Modifiche non salvate",
    "titolo_modificato": "* {titolo}",
    "conferma_modifiche_non_salvate": (
        "Sono presenti modifiche non salvate. Vuoi salvarle prima di {azione}?\n\n"
        "Sì: salva le modifiche.\n"
        "No: scarta le modifiche.\n"
        "Annulla: interrompe l'operazione."
    ),
    "stato_mondo": "Stato del mondo",
    "nome_entita": "Entità",
    "tipo_entita": "Tipo",
    "posizione": "Posizione",
    "possessore": "Possessore",
    "stato_entita": "Stato",
    "condizione": "Condizione",
    "accessibilita": "Accessibilità",
    "eventi_entita": "Cronologia eventi dell'entità selezionata",
    "nessun_evento": "Nessun evento registrato per l'entità selezionata.",
    "tipo_evento": "Evento",
    "data_evento": "Data",
    "motivo_evento": "Motivo",
    "oggetto_da_trasferire": "Oggetto",
    "nuovo_possessore": "Nuovo possessore",
    "trasferisci_oggetto": "Trasferisci oggetto",
    "seleziona_trasferimento": "Seleziona un oggetto e un nuovo possessore.",
    "trasferimento_completato": "Oggetto trasferito e stato aggiornato correttamente.",
    "memorie_personaggi": "Memorie dei personaggi",
    "personaggio_memorie": "Personaggio",
    "filtra_entita": "Entità collegata",
    "tutte_entita": "Tutte le entità",
    "cronologia_completa_memorie": "Cronologia completa",
    "contenuto_memoria": "Contenuto",
    "tipo_conoscenza": "Tipo di conoscenza",
    "fonte_memoria": "Fonte",
    "certezza_memoria": "Certezza",
    "data_memoria": "Data appresa",
    "interpretazione_memoria": "Interpretazione",
    "emozione_memoria": "Emozione",
    "stato_memoria": "Stato",
    "nessuna_memoria": "Nessuna memoria disponibile per i filtri selezionati.",
    "impostazioni_ai": "Impostazioni AI",
    "provider_ai": "Provider",
    "url_servizio_ai": "URL del servizio",
    "timeout_ai": "Timeout (secondi)",
    "modello_ai": "Modello locale",
    "salva_impostazioni_ai": "Salva impostazioni",
    "verifica_connessione_ai": "Verifica connessione",
    "aggiorna_modelli_ai": "Aggiorna modelli",
    "prova_modello_ai": "Prova modello",
    "testo_prova_ai": "Testo breve di prova",
    "risposta_ai": "Risposta del modello",
    "versione_ollama": "Versione Ollama: {versione}",
    "versione_ollama_non_verificata": "Versione Ollama: non verificata",
    "stato_ai_pronto": "Impostazioni AI pronte. Nessuna connessione automatica.",
    "stato_ai_salvato": "Impostazioni AI salvate.",
    "stato_ai_connessione": "Connessione a Ollama verificata.",
    "stato_ai_modelli": "Elenco dei modelli locali aggiornato.",
    "stato_ai_prova": "Prova del modello completata.",
    "stato_ai_in_corso": "Operazione AI in corso…",
    "stato_ai_occupato": "Attendi il completamento dell'operazione AI in corso.",
    "errore_ai_generico": "L'operazione AI non è riuscita.",
    "validazione_mondo": "Validazione mondo",
    "controlla_mondo": "Controlla mondo",
    "validazione_non_eseguita": "Controllo non ancora eseguito.",
    "validazione_superata": (
        "Controllo superato — Errori: {errori} — Avvertimenti: {avvertimenti}"
    ),
    "validazione_non_superata": (
        "Controllo non superato — Errori: {errori} — Avvertimenti: {avvertimenti}"
    ),
    "severita_validazione": "Severità",
    "ambito_validazione": "Ambito",
    "problema_validazione": "Problema rilevato",
    "validazione_errore": "Il controllo del mondo non è riuscito.",
}


ETICHETTE_IMPOSTAZIONI = {
    "point_of_view": "Punto di vista",
    "tense": "Tempo verbale",
    "tone": "Tono",
    "language": "Lingua narrativa",
    "language_register": "Registro linguistico",
    "violence": "Violenza",
    "adult_consensual_eroticism": "Erotismo adulto consensuale",
    "descriptive_intensity": "Intensità descrittiva",
    "dark_themes": "Temi oscuri",
    "pace": "Ritmo",
}


def etichetta_impostazione(chiave: str) -> str:
    return ETICHETTE_IMPOSTAZIONI.get(
        chiave, chiave.replace("_", " ").strip().capitalize()
    )


def etichetta_stato_memoria(effective_status: str) -> str:
    etichette = {
        "active": "Attiva",
        "corrected": "Corretta",
        "contradicted": "Contraddetta",
        "superseded": "Superata",
    }
    return etichette.get(effective_status, "Stato non riconosciuto")


def etichetta_ambito_validazione(ambito: AmbitoValidazione) -> str:
    etichette = {
        AmbitoValidazione.INTEGRITA: "Integrità",
        AmbitoValidazione.SPAZIO: "Spazio",
        AmbitoValidazione.TEMPO: "Tempo",
        AmbitoValidazione.INVENTARIO: "Inventario",
        AmbitoValidazione.EPISTEMICA: "Epistemica",
    }
    return etichette[ambito]


def etichetta_severita_validazione(severita: SeveritaProblema) -> str:
    etichette = {
        SeveritaProblema.ERRORE: "Errore",
        SeveritaProblema.AVVERTIMENTO: "Avvertimento",
        SeveritaProblema.INFORMAZIONE: "Informazione",
    }
    return etichette[severita]


class ApplicazioneHaria:
    def __init__(self, radice: tk.Tk, percorso_database: str | Path) -> None:
        self.radice = radice
        self.servizio = ServizioMondi(percorso_database)
        self.mondo_corrente: Mondo | None = None
        self.campi_impostazioni: dict[str, tk.StringVar] = {}
        self.stato_editor = StatoEditor()
        self._caricamento_interfaccia = False
        self._oggetti_trasferibili: list[EntitaMondo] = []
        self._possessori_disponibili: list[EntitaMondo] = []
        self._personaggi_memorie: list[EntitaMondo] = []
        self._entita_memorie: list[EntitaMondo] = []
        self._cronologia_completa_memorie = tk.BooleanVar(value=False)
        self._coordinatore_ai = CoordinatoreAsincrono()
        self._controllo_ai_after: str | None = None
        self._chiusura_in_corso = False
        self._pulsanti_rete_ai: list[ttk.Button] = []

        self.radice.title(UI_TEXT["titolo_finestra"])
        self.radice.geometry("1080x720")
        self.radice.minsize(820, 560)
        self.radice.protocol("WM_DELETE_WINDOW", self.chiudi)
        self._costruisci_interfaccia()
        self._carica_configurazione_ai()
        self._carica_mondo_esistente()
        self._programma_controllo_ai()

    def _costruisci_interfaccia(self) -> None:
        contenitore = ttk.Frame(self.radice, padding=14)
        contenitore.pack(fill=tk.BOTH, expand=True)

        barra = ttk.Frame(contenitore)
        barra.pack(fill=tk.X)
        ttk.Button(
            barra, text=UI_TEXT["importa"], command=self._importa_da_interfaccia
        ).pack(side=tk.LEFT)
        self.pulsante_esporta = ttk.Button(
            barra,
            text=UI_TEXT["esporta"],
            command=self._esporta_da_interfaccia,
            state=tk.DISABLED,
        )
        self.pulsante_esporta.pack(side=tk.LEFT, padx=(8, 0))

        intestazione = ttk.Frame(contenitore)
        intestazione.pack(fill=tk.X, pady=(16, 10))
        self.etichetta_titolo = ttk.Label(
            intestazione, text=UI_TEXT["nessun_mondo"], font=("TkDefaultFont", 16, "bold")
        )
        self.etichetta_titolo.pack(side=tk.LEFT)
        self.etichetta_versione = ttk.Label(intestazione, text="")
        self.etichetta_versione.pack(side=tk.RIGHT)

        self.schede = ttk.Notebook(contenitore)
        self.schede.pack(fill=tk.BOTH, expand=True)

        scheda_scenario = ttk.Frame(self.schede, padding=10)
        self.schede.add(scheda_scenario, text=UI_TEXT["scenario"])
        scheda_scenario.rowconfigure(0, weight=1)
        scheda_scenario.columnconfigure(0, weight=1)
        self.editor_scenario = tk.Text(
            scheda_scenario,
            wrap=tk.WORD,
            undo=True,
            padx=12,
            pady=12,
            font=("TkDefaultFont", 11),
        )
        self.editor_scenario.grid(row=0, column=0, sticky="nsew")
        self.editor_scenario.bind(
            "<<Modified>>", self._rileva_modifica_scenario
        )
        scorrimento = ttk.Scrollbar(
            scheda_scenario, orient=tk.VERTICAL, command=self.editor_scenario.yview
        )
        scorrimento.grid(row=0, column=1, sticky="ns")
        self.editor_scenario.configure(yscrollcommand=scorrimento.set)
        self.pulsante_salva = ttk.Button(
            scheda_scenario,
            text=UI_TEXT["salva"],
            command=self._salva_da_interfaccia,
            state=tk.DISABLED,
        )
        self.pulsante_salva.grid(row=1, column=0, sticky="e", pady=(10, 0))

        self.scheda_impostazioni = ttk.Frame(self.schede, padding=14)
        self.schede.add(
            self.scheda_impostazioni, text=UI_TEXT["impostazioni"]
        )
        self.scheda_impostazioni.columnconfigure(1, weight=1)

        self._costruisci_scheda_stato_mondo()
        self._costruisci_scheda_memorie()
        self._costruisci_scheda_validazione()
        self._costruisci_scheda_ai()

        scheda_cronologia = ttk.Frame(self.schede, padding=10)
        self.schede.add(scheda_cronologia, text=UI_TEXT["cronologia"])
        scheda_cronologia.rowconfigure(0, weight=1)
        scheda_cronologia.columnconfigure(0, weight=1)
        self.albero_versioni = ttk.Treeview(
            scheda_cronologia,
            columns=("versione", "data", "motivo"),
            show="headings",
            selectmode="browse",
        )
        self.albero_versioni.heading(
            "versione", text=UI_TEXT["numero_versione"]
        )
        self.albero_versioni.heading("data", text=UI_TEXT["data_versione"])
        self.albero_versioni.heading("motivo", text=UI_TEXT["motivo_versione"])
        self.albero_versioni.column("versione", width=90, anchor=tk.CENTER)
        self.albero_versioni.column("data", width=210)
        self.albero_versioni.column("motivo", width=320)
        self.albero_versioni.grid(row=0, column=0, sticky="nsew")
        scorrimento_versioni = ttk.Scrollbar(
            scheda_cronologia,
            orient=tk.VERTICAL,
            command=self.albero_versioni.yview,
        )
        scorrimento_versioni.grid(row=0, column=1, sticky="ns")
        self.albero_versioni.configure(yscrollcommand=scorrimento_versioni.set)
        self.pulsante_ripristina = ttk.Button(
            scheda_cronologia,
            text=UI_TEXT["ripristina"],
            command=self._ripristina_da_interfaccia,
            state=tk.DISABLED,
        )
        self.pulsante_ripristina.grid(row=1, column=0, sticky="e", pady=(10, 0))

        self.etichetta_stato = ttk.Label(
            contenitore, text=UI_TEXT["istruzione_importa"], anchor=tk.W
        )
        self.etichetta_stato.pack(fill=tk.X, pady=(10, 0))

    def _costruisci_scheda_ai(self) -> None:
        scheda = ttk.Frame(self.schede, padding=14)
        self.schede.add(scheda, text=UI_TEXT["impostazioni_ai"])
        scheda.columnconfigure(1, weight=1)
        scheda.rowconfigure(7, weight=1)

        self._url_ai = tk.StringVar()
        self._timeout_ai = tk.StringVar()
        self._modello_ai = tk.StringVar()
        self._testo_prova_ai = tk.StringVar()

        ttk.Label(scheda, text=UI_TEXT["provider_ai"]).grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=5
        )
        ttk.Label(scheda, text="Ollama").grid(row=0, column=1, sticky="w", pady=5)

        ttk.Label(scheda, text=UI_TEXT["url_servizio_ai"]).grid(
            row=1, column=0, sticky="w", padx=(0, 12), pady=5
        )
        self.campo_url_ai = ttk.Entry(scheda, textvariable=self._url_ai)
        self.campo_url_ai.grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(scheda, text=UI_TEXT["timeout_ai"]).grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=5
        )
        self.campo_timeout_ai = ttk.Entry(
            scheda, textvariable=self._timeout_ai, width=12
        )
        self.campo_timeout_ai.grid(row=2, column=1, sticky="w", pady=5)

        ttk.Label(scheda, text=UI_TEXT["modello_ai"]).grid(
            row=3, column=0, sticky="w", padx=(0, 12), pady=5
        )
        self.selettore_modello_ai = ttk.Combobox(
            scheda, textvariable=self._modello_ai, state="readonly"
        )
        self.selettore_modello_ai.grid(row=3, column=1, sticky="ew", pady=5)

        pulsanti = ttk.Frame(scheda)
        pulsanti.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 10))
        self.pulsante_salva_ai = ttk.Button(
            pulsanti,
            text=UI_TEXT["salva_impostazioni_ai"],
            command=self._salva_configurazione_ai,
        )
        self.pulsante_salva_ai.pack(side=tk.LEFT)
        self.pulsante_verifica_ai = ttk.Button(
            pulsanti,
            text=UI_TEXT["verifica_connessione_ai"],
            command=self._verifica_connessione_ai,
        )
        self.pulsante_verifica_ai.pack(side=tk.LEFT, padx=(8, 0))
        self.pulsante_modelli_ai = ttk.Button(
            pulsanti,
            text=UI_TEXT["aggiorna_modelli_ai"],
            command=self._aggiorna_modelli_ai,
        )
        self.pulsante_modelli_ai.pack(side=tk.LEFT, padx=(8, 0))
        self.pulsante_prova_ai = ttk.Button(
            pulsanti,
            text=UI_TEXT["prova_modello_ai"],
            command=self._prova_modello_ai,
        )
        self.pulsante_prova_ai.pack(side=tk.LEFT, padx=(8, 0))
        self._pulsanti_rete_ai = [
            self.pulsante_verifica_ai,
            self.pulsante_modelli_ai,
            self.pulsante_prova_ai,
        ]

        ttk.Label(scheda, text=UI_TEXT["testo_prova_ai"]).grid(
            row=5, column=0, sticky="w", padx=(0, 12), pady=5
        )
        self.campo_testo_prova_ai = ttk.Entry(
            scheda, textvariable=self._testo_prova_ai
        )
        self.campo_testo_prova_ai.grid(row=5, column=1, sticky="ew", pady=5)

        ttk.Label(scheda, text=UI_TEXT["risposta_ai"]).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(5, 4)
        )
        self.risposta_ai = tk.Text(
            scheda, height=8, wrap=tk.WORD, state=tk.DISABLED, padx=8, pady=8
        )
        self.risposta_ai.grid(row=7, column=0, columnspan=2, sticky="nsew")

        self.etichetta_versione_ollama = ttk.Label(
            scheda, text=UI_TEXT["versione_ollama_non_verificata"]
        )
        self.etichetta_versione_ollama.grid(
            row=8, column=0, sticky="w", pady=(10, 0)
        )
        self.etichetta_stato_ai = ttk.Label(
            scheda, text=UI_TEXT["stato_ai_pronto"], anchor=tk.W
        )
        self.etichetta_stato_ai.grid(
            row=8, column=1, sticky="ew", pady=(10, 0)
        )

    def _carica_configurazione_ai(self) -> None:
        configurazione = self.servizio.carica_configurazione_ai()
        self._url_ai.set(configurazione.ollama_base_url)
        self._timeout_ai.set(str(configurazione.ollama_timeout_seconds))
        self._modello_ai.set(configurazione.ollama_model)
        self.selettore_modello_ai["values"] = (
            (configurazione.ollama_model,) if configurazione.ollama_model else ()
        )

    def _configurazione_ai_visibile(self) -> ConfigurazioneAI:
        testo_timeout = self._timeout_ai.get().strip()
        try:
            timeout = int(testo_timeout)
        except ValueError as errore:
            raise ErroreConfigurazioneAI(
                "Il timeout deve essere un numero intero tra 1 e 300 secondi."
            ) from errore
        return valida_configurazione_ai(
            "ollama",
            self._url_ai.get(),
            self._modello_ai.get(),
            timeout,
        )

    def _salva_configurazione_ai(self) -> None:
        try:
            configurazione = self._configurazione_ai_visibile()
            salvata = self.servizio.salva_configurazione_ai(configurazione)
            self._url_ai.set(salvata.ollama_base_url)
            self._timeout_ai.set(str(salvata.ollama_timeout_seconds))
            self.etichetta_stato_ai.configure(text=UI_TEXT["stato_ai_salvato"])
        except ErroreHaria as errore:
            messagebox.showerror(UI_TEXT["errore"], str(errore))

    def _verifica_connessione_ai(self) -> None:
        self._avvia_operazione_ai(
            "connessione", self.servizio.ai.verifica_connessione
        )

    def _aggiorna_modelli_ai(self) -> None:
        self._avvia_operazione_ai("modelli", self.servizio.ai.elenca_modelli)

    def _prova_modello_ai(self) -> None:
        self._avvia_operazione_ai(
            "prova",
            self.servizio.ai.genera_testo_di_prova,
            self._testo_prova_ai.get(),
        )

    def _avvia_operazione_ai(
        self,
        operazione: str,
        funzione: Callable[..., object],
        *argomenti: object,
    ) -> None:
        try:
            configurazione = self._configurazione_ai_visibile()
        except ErroreHaria as errore:
            messagebox.showerror(UI_TEXT["errore"], str(errore))
            return
        avviata = self._coordinatore_ai.avvia(
            operazione, funzione, configurazione, *argomenti
        )
        if not avviata:
            self.etichetta_stato_ai.configure(text=UI_TEXT["stato_ai_occupato"])
            return
        self._imposta_controlli_rete_ai(False)
        self.etichetta_stato_ai.configure(text=UI_TEXT["stato_ai_in_corso"])

    def _programma_controllo_ai(self) -> None:
        if self._chiusura_in_corso:
            return
        self._elabora_esiti_ai()
        self._controllo_ai_after = self.radice.after(
            75, self._programma_controllo_ai
        )

    def _elabora_esiti_ai(self) -> None:
        for esito in self._coordinatore_ai.raccogli():
            self._imposta_controlli_rete_ai(True)
            self._mostra_esito_ai(esito)

    def _mostra_esito_ai(self, esito: EsitoAsincrono[object]) -> None:
        if esito.errore is not None:
            messaggio = (
                str(esito.errore)
                if isinstance(esito.errore, ErroreHaria)
                else UI_TEXT["errore_ai_generico"]
            )
            self.etichetta_stato_ai.configure(text=messaggio)
            messagebox.showerror(UI_TEXT["errore"], messaggio)
            return
        if esito.operazione == "connessione" and isinstance(
            esito.risultato, RisultatoConnessione
        ):
            self.etichetta_versione_ollama.configure(
                text=UI_TEXT["versione_ollama"].format(
                    versione=esito.risultato.informazioni.versione
                )
            )
            self.etichetta_stato_ai.configure(text=UI_TEXT["stato_ai_connessione"])
            return
        if esito.operazione == "modelli" and isinstance(esito.risultato, tuple):
            modelli = tuple(
                voce for voce in esito.risultato if isinstance(voce, ModelloLocale)
            )
            nomi = tuple(voce.nome for voce in modelli)
            selezionato = self._modello_ai.get()
            self.selettore_modello_ai["values"] = nomi
            self._modello_ai.set(selezionato if selezionato in nomi else "")
            self.etichetta_stato_ai.configure(text=UI_TEXT["stato_ai_modelli"])
            return
        if esito.operazione == "prova" and isinstance(
            esito.risultato, RispostaTestuale
        ):
            self.risposta_ai.configure(state=tk.NORMAL)
            self.risposta_ai.delete("1.0", tk.END)
            self.risposta_ai.insert("1.0", esito.risultato.contenuto)
            self.risposta_ai.configure(state=tk.DISABLED)
            self.etichetta_stato_ai.configure(text=UI_TEXT["stato_ai_prova"])
            return
        self.etichetta_stato_ai.configure(text=UI_TEXT["errore_ai_generico"])

    def _imposta_controlli_rete_ai(self, abilitati: bool) -> None:
        stato = tk.NORMAL if abilitati else tk.DISABLED
        for pulsante in self._pulsanti_rete_ai:
            pulsante.configure(state=stato)

    def _costruisci_scheda_memorie(self) -> None:
        scheda = ttk.Frame(self.schede, padding=10)
        self.schede.add(scheda, text=UI_TEXT["memorie_personaggi"])
        scheda.rowconfigure(1, weight=1)
        scheda.columnconfigure(0, weight=1)

        filtri = ttk.Frame(scheda)
        filtri.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        filtri.columnconfigure(1, weight=1)
        filtri.columnconfigure(3, weight=1)
        ttk.Label(filtri, text=UI_TEXT["personaggio_memorie"]).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self.selettore_personaggio_memorie = ttk.Combobox(
            filtri, state="readonly", width=28
        )
        self.selettore_personaggio_memorie.grid(
            row=0, column=1, sticky="ew", padx=(0, 16)
        )
        self.selettore_personaggio_memorie.bind(
            "<<ComboboxSelected>>", self._mostra_memorie_selezionate
        )
        ttk.Label(filtri, text=UI_TEXT["filtra_entita"]).grid(
            row=0, column=2, sticky="w", padx=(0, 8)
        )
        self.selettore_entita_memorie = ttk.Combobox(
            filtri, state="readonly", width=28
        )
        self.selettore_entita_memorie.grid(
            row=0, column=3, sticky="ew", padx=(0, 16)
        )
        self.selettore_entita_memorie.bind(
            "<<ComboboxSelected>>", self._mostra_memorie_selezionate
        )
        ttk.Checkbutton(
            filtri,
            text=UI_TEXT["cronologia_completa_memorie"],
            variable=self._cronologia_completa_memorie,
            command=self._mostra_memorie_selezionate,
        ).grid(row=0, column=4, sticky="e")

        colonne = (
            "contenuto",
            "tipo",
            "fonte",
            "certezza",
            "data",
            "interpretazione",
            "emozione",
            "stato",
        )
        self.albero_memorie = ttk.Treeview(
            scheda, columns=colonne, show="headings", selectmode="browse"
        )
        intestazioni = {
            "contenuto": UI_TEXT["contenuto_memoria"],
            "tipo": UI_TEXT["tipo_conoscenza"],
            "fonte": UI_TEXT["fonte_memoria"],
            "certezza": UI_TEXT["certezza_memoria"],
            "data": UI_TEXT["data_memoria"],
            "interpretazione": UI_TEXT["interpretazione_memoria"],
            "emozione": UI_TEXT["emozione_memoria"],
            "stato": UI_TEXT["stato_memoria"],
        }
        for colonna, testo in intestazioni.items():
            self.albero_memorie.heading(colonna, text=testo)
        self.albero_memorie.column("contenuto", width=310)
        self.albero_memorie.column("tipo", width=150)
        self.albero_memorie.column("fonte", width=150)
        self.albero_memorie.column("certezza", width=80, anchor=tk.CENTER)
        self.albero_memorie.column("data", width=190)
        self.albero_memorie.column("interpretazione", width=190)
        self.albero_memorie.column("emozione", width=130)
        self.albero_memorie.column("stato", width=90, anchor=tk.CENTER)
        self.albero_memorie.tag_configure("osservata", background="#eaf5ff")
        self.albero_memorie.tag_configure("riferita", background="#fff3df")
        self.albero_memorie.grid(row=1, column=0, sticky="nsew")
        scorrimento = ttk.Scrollbar(
            scheda, orient=tk.VERTICAL, command=self.albero_memorie.yview
        )
        scorrimento.grid(row=1, column=1, sticky="ns")
        scorrimento_orizzontale = ttk.Scrollbar(
            scheda, orient=tk.HORIZONTAL, command=self.albero_memorie.xview
        )
        scorrimento_orizzontale.grid(row=2, column=0, sticky="ew")
        self.albero_memorie.configure(
            yscrollcommand=scorrimento.set,
            xscrollcommand=scorrimento_orizzontale.set,
        )

    def _costruisci_scheda_stato_mondo(self) -> None:
        scheda = ttk.Frame(self.schede, padding=10)
        self.schede.add(scheda, text=UI_TEXT["stato_mondo"])
        scheda.rowconfigure(0, weight=3)
        scheda.rowconfigure(2, weight=2)
        scheda.columnconfigure(0, weight=1)

        colonne = (
            "nome",
            "tipo",
            "posizione",
            "possessore",
            "stato",
            "condizione",
            "accessibilita",
        )
        self.albero_stato_mondo = ttk.Treeview(
            scheda, columns=colonne, show="headings", selectmode="browse"
        )
        intestazioni = {
            "nome": UI_TEXT["nome_entita"],
            "tipo": UI_TEXT["tipo_entita"],
            "posizione": UI_TEXT["posizione"],
            "possessore": UI_TEXT["possessore"],
            "stato": UI_TEXT["stato_entita"],
            "condizione": UI_TEXT["condizione"],
            "accessibilita": UI_TEXT["accessibilita"],
        }
        for colonna, testo in intestazioni.items():
            self.albero_stato_mondo.heading(colonna, text=testo)
        self.albero_stato_mondo.column("nome", width=190)
        self.albero_stato_mondo.column("tipo", width=100)
        self.albero_stato_mondo.column("posizione", width=170)
        self.albero_stato_mondo.column("possessore", width=150)
        self.albero_stato_mondo.column("stato", width=110)
        self.albero_stato_mondo.column("condizione", width=110)
        self.albero_stato_mondo.column("accessibilita", width=100)
        self.albero_stato_mondo.grid(row=0, column=0, sticky="nsew")
        self.albero_stato_mondo.bind(
            "<<TreeviewSelect>>", self._mostra_eventi_entita_selezionata
        )

        ttk.Label(scheda, text=UI_TEXT["eventi_entita"]).grid(
            row=1, column=0, sticky="w", pady=(10, 4)
        )
        self.albero_eventi_entita = ttk.Treeview(
            scheda,
            columns=("data", "tipo", "motivo"),
            show="headings",
            selectmode="none",
        )
        self.albero_eventi_entita.heading("data", text=UI_TEXT["data_evento"])
        self.albero_eventi_entita.heading("tipo", text=UI_TEXT["tipo_evento"])
        self.albero_eventi_entita.heading("motivo", text=UI_TEXT["motivo_evento"])
        self.albero_eventi_entita.column("data", width=220)
        self.albero_eventi_entita.column("tipo", width=180)
        self.albero_eventi_entita.column("motivo", width=500)
        self.albero_eventi_entita.grid(row=2, column=0, sticky="nsew")

        controlli = ttk.LabelFrame(
            scheda, text=UI_TEXT["trasferisci_oggetto"], padding=10
        )
        controlli.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        controlli.columnconfigure(1, weight=1)
        controlli.columnconfigure(3, weight=1)
        ttk.Label(controlli, text=UI_TEXT["oggetto_da_trasferire"]).grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self.selettore_oggetto = ttk.Combobox(
            controlli, state="readonly", width=28
        )
        self.selettore_oggetto.grid(row=0, column=1, sticky="ew", padx=(0, 16))
        ttk.Label(controlli, text=UI_TEXT["nuovo_possessore"]).grid(
            row=0, column=2, sticky="w", padx=(0, 8)
        )
        self.selettore_possessore = ttk.Combobox(
            controlli, state="readonly", width=28
        )
        self.selettore_possessore.grid(row=0, column=3, sticky="ew", padx=(0, 16))
        self.pulsante_trasferisci = ttk.Button(
            controlli,
            text=UI_TEXT["trasferisci_oggetto"],
            command=self._trasferisci_oggetto_da_interfaccia,
            state=tk.DISABLED,
        )
        self.pulsante_trasferisci.grid(row=0, column=4)

    def _costruisci_scheda_validazione(self) -> None:
        scheda = ttk.Frame(self.schede, padding=10)
        self.schede.add(scheda, text=UI_TEXT["validazione_mondo"])
        scheda.rowconfigure(1, weight=1)
        scheda.columnconfigure(0, weight=1)

        riepilogo = ttk.Frame(scheda)
        riepilogo.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        riepilogo.columnconfigure(0, weight=1)
        self.etichetta_validazione = ttk.Label(
            riepilogo, text=UI_TEXT["validazione_non_eseguita"], anchor=tk.W
        )
        self.etichetta_validazione.grid(row=0, column=0, sticky="ew")
        self.pulsante_controlla_mondo = ttk.Button(
            riepilogo,
            text=UI_TEXT["controlla_mondo"],
            command=self._controlla_mondo,
            state=tk.DISABLED,
        )
        self.pulsante_controlla_mondo.grid(row=0, column=1, padx=(12, 0))

        self.albero_validazione = ttk.Treeview(
            scheda,
            columns=("severita", "ambito", "messaggio"),
            show="headings",
            selectmode="none",
        )
        self.albero_validazione.heading(
            "severita", text=UI_TEXT["severita_validazione"]
        )
        self.albero_validazione.heading(
            "ambito", text=UI_TEXT["ambito_validazione"]
        )
        self.albero_validazione.heading(
            "messaggio", text=UI_TEXT["problema_validazione"]
        )
        self.albero_validazione.column("severita", width=120)
        self.albero_validazione.column("ambito", width=120)
        self.albero_validazione.column("messaggio", width=700)
        self.albero_validazione.grid(row=1, column=0, sticky="nsew")
        scorrimento = ttk.Scrollbar(
            scheda, orient=tk.VERTICAL, command=self.albero_validazione.yview
        )
        scorrimento.grid(row=1, column=1, sticky="ns")
        self.albero_validazione.configure(yscrollcommand=scorrimento.set)

    def _carica_mondo_esistente(self) -> None:
        mondi = self.servizio.elenca_mondi()
        if mondi:
            self._mostra_mondo(mondi[0])

    def _mostra_mondo(self, mondo: Mondo) -> None:
        self._caricamento_interfaccia = True
        try:
            self.mondo_corrente = mondo
            self.etichetta_titolo.configure(text=mondo.titolo)
            self.etichetta_versione.configure(
                text=UI_TEXT["versione"].format(numero=mondo.versione_corrente)
            )
            self.editor_scenario.configure(state=tk.NORMAL)
            self.editor_scenario.delete("1.0", tk.END)
            self.editor_scenario.insert("1.0", mondo.scenario)
            self.editor_scenario.edit_modified(False)
            self._mostra_impostazioni(mondo.impostazioni_narrative)
            self.stato_editor.carica(
                mondo.scenario, mondo.impostazioni_narrative
            )
        finally:
            self._caricamento_interfaccia = False
        self._aggiorna_cronologia()
        self._aggiorna_stato_mondo()
        self._aggiorna_memorie()
        self._azzera_validazione()
        self.pulsante_salva.configure(state=tk.NORMAL)
        self.pulsante_esporta.configure(state=tk.NORMAL)
        self.pulsante_ripristina.configure(state=tk.NORMAL)
        self._aggiorna_indicatore_modifiche()

    def _azzera_validazione(self) -> None:
        for elemento in self.albero_validazione.get_children():
            self.albero_validazione.delete(elemento)
        self.etichetta_validazione.configure(
            text=UI_TEXT["validazione_non_eseguita"]
        )
        stato = tk.NORMAL if self.mondo_corrente is not None else tk.DISABLED
        self.pulsante_controlla_mondo.configure(state=stato)

    def _controlla_mondo(self) -> None:
        if self.mondo_corrente is None:
            return
        try:
            rapporto = self.servizio.validazione.controlla_mondo(
                self.mondo_corrente.id
            )
        except ErroreHaria as errore:
            self.etichetta_validazione.configure(
                text=UI_TEXT["validazione_errore"]
            )
            messagebox.showerror(UI_TEXT["errore"], str(errore))
            return
        for elemento in self.albero_validazione.get_children():
            self.albero_validazione.delete(elemento)
        modello = (
            UI_TEXT["validazione_superata"]
            if rapporto.superata
            else UI_TEXT["validazione_non_superata"]
        )
        self.etichetta_validazione.configure(
            text=modello.format(
                errori=len(rapporto.errori),
                avvertimenti=len(rapporto.avvertimenti),
            )
        )
        for problema in rapporto.problemi:
            self.albero_validazione.insert(
                "",
                tk.END,
                values=(
                    etichetta_severita_validazione(problema.severita),
                    etichetta_ambito_validazione(problema.ambito),
                    problema.messaggio,
                ),
            )

    def _mostra_impostazioni(self, impostazioni: dict[str, str]) -> None:
        for elemento in self.scheda_impostazioni.winfo_children():
            elemento.destroy()
        self.campi_impostazioni.clear()
        if not impostazioni:
            ttk.Label(
                self.scheda_impostazioni, text=UI_TEXT["nessuna_impostazione"]
            ).grid(row=0, column=0, sticky="w")
            return
        for riga, chiave in enumerate(sorted(impostazioni)):
            ttk.Label(
                self.scheda_impostazioni, text=etichetta_impostazione(chiave)
            ).grid(row=riga, column=0, sticky="w", padx=(0, 14), pady=6)
            variabile = tk.StringVar(value=impostazioni[chiave])
            ttk.Entry(
                self.scheda_impostazioni, textvariable=variabile, width=70
            ).grid(row=riga, column=1, sticky="ew", pady=6)
            variabile.trace_add(
                "write",
                lambda *_eventi, chiave=chiave, variabile=variabile: (
                    self._rileva_modifica_impostazione(chiave, variabile)
                ),
            )
            self.campi_impostazioni[chiave] = variabile

    def _rileva_modifica_scenario(self, _evento: object | None = None) -> None:
        if not self.editor_scenario.edit_modified():
            return
        self.editor_scenario.edit_modified(False)
        if self._caricamento_interfaccia or self.mondo_corrente is None:
            return
        self.stato_editor.aggiorna_scenario(
            self.editor_scenario.get("1.0", "end-1c")
        )
        self._aggiorna_indicatore_modifiche()

    def _rileva_modifica_impostazione(
        self, chiave: str, variabile: tk.StringVar
    ) -> None:
        if self._caricamento_interfaccia or self.mondo_corrente is None:
            return
        self.stato_editor.aggiorna_impostazione(chiave, variabile.get())
        self._aggiorna_indicatore_modifiche()

    def _aggiorna_indicatore_modifiche(self) -> None:
        if self.stato_editor.modificato:
            self.radice.title(
                UI_TEXT["titolo_modificato"].format(
                    titolo=UI_TEXT["titolo_finestra"]
                )
            )
            self.etichetta_stato.configure(text=UI_TEXT["modifiche_non_salvate"])
            return
        self.radice.title(UI_TEXT["titolo_finestra"])
        self.etichetta_stato.configure(text=UI_TEXT["stato_pronto"])

    def _aggiorna_stato_mondo(self) -> None:
        for elemento in self.albero_stato_mondo.get_children():
            self.albero_stato_mondo.delete(elemento)
        for elemento in self.albero_eventi_entita.get_children():
            self.albero_eventi_entita.delete(elemento)
        self._oggetti_trasferibili = []
        self._possessori_disponibili = []
        self.selettore_oggetto["values"] = ()
        self.selettore_possessore["values"] = ()
        self.pulsante_trasferisci.configure(state=tk.DISABLED)
        if self.mondo_corrente is None:
            return

        entita = self.servizio.stato_mondo.elenca_entita(self.mondo_corrente.id)
        nomi = {voce.entity_id: voce.canonical_name for voce in entita}
        for voce in entita:
            self.albero_stato_mondo.insert(
                "",
                tk.END,
                iid=voce.entity_id,
                values=(
                    voce.canonical_name,
                    self._etichetta_tecnica(voce.entity_type),
                    self._descrivi_posizione(voce, nomi),
                    nomi.get(voce.holder_id, "—"),
                    self._etichetta_tecnica(voce.status),
                    voce.condition or "—",
                    "Sì" if voce.accessibility else "No",
                ),
            )

        self._oggetti_trasferibili = [
            voce for voce in entita if voce.entity_type == TIPO_OGGETTO
        ]
        self._possessori_disponibili = [
            voce for voce in entita if voce.entity_type == TIPO_PERSONAGGIO
        ]
        self.selettore_oggetto["values"] = tuple(
            voce.canonical_name for voce in self._oggetti_trasferibili
        )
        self.selettore_possessore["values"] = tuple(
            voce.canonical_name for voce in self._possessori_disponibili
        )
        if self._oggetti_trasferibili:
            self.selettore_oggetto.current(0)
        if self._possessori_disponibili:
            self.selettore_possessore.current(0)
        if self._oggetti_trasferibili and self._possessori_disponibili:
            self.pulsante_trasferisci.configure(state=tk.NORMAL)

    def _aggiorna_memorie(self) -> None:
        self._personaggi_memorie = []
        self._entita_memorie = []
        self.selettore_personaggio_memorie["values"] = ()
        self.selettore_entita_memorie["values"] = (UI_TEXT["tutte_entita"],)
        self.selettore_entita_memorie.current(0)
        self._svuota_memorie()
        if self.mondo_corrente is None:
            return

        entita = self.servizio.stato_mondo.elenca_entita(self.mondo_corrente.id)
        self._personaggi_memorie = [
            voce for voce in entita if voce.entity_type == TIPO_PERSONAGGIO
        ]
        self._entita_memorie = entita
        self.selettore_personaggio_memorie["values"] = tuple(
            voce.canonical_name for voce in self._personaggi_memorie
        )
        self.selettore_entita_memorie["values"] = (
            UI_TEXT["tutte_entita"],
            *(voce.canonical_name for voce in self._entita_memorie),
        )
        if self._personaggi_memorie:
            self.selettore_personaggio_memorie.current(0)
            self._mostra_memorie_selezionate()

    def _svuota_memorie(self) -> None:
        for elemento in self.albero_memorie.get_children():
            self.albero_memorie.delete(elemento)

    def _mostra_memorie_selezionate(
        self, _evento: object | None = None
    ) -> None:
        self._svuota_memorie()
        if self.mondo_corrente is None:
            return
        indice_personaggio = self.selettore_personaggio_memorie.current()
        if indice_personaggio < 0:
            return
        personaggio = self._personaggi_memorie[indice_personaggio]
        indice_entita = self.selettore_entita_memorie.current()
        entity_id = None
        if indice_entita > 0:
            entity_id = self._entita_memorie[indice_entita - 1].entity_id
        memorie = self.servizio.memorie.elenca_memorie_personaggio(
            self.mondo_corrente.id,
            personaggio.entity_id,
            entity_id=entity_id,
            solo_correnti=not self._cronologia_completa_memorie.get(),
        )
        if not memorie:
            self.albero_memorie.insert(
                "", tk.END, values=(UI_TEXT["nessuna_memoria"], "", "", "", "", "", "", "")
            )
            return
        for memoria in memorie:
            etichetta = ""
            if memoria.source_type == "direct_observation":
                etichetta = "osservata"
            elif memoria.source_type == "told_by_character":
                etichetta = "riferita"
            self.albero_memorie.insert(
                "",
                tk.END,
                values=(
                    memoria.content,
                    self._tipo_conoscenza_memoria(memoria.knowledge_type),
                    self._fonte_memoria(memoria),
                    f"{memoria.certainty}%",
                    memoria.learned_at,
                    memoria.interpretation or "—",
                    memoria.associated_emotion or "—",
                    etichetta_stato_memoria(memoria.effective_status),
                ),
                tags=(etichetta,) if etichetta else (),
            )

    @staticmethod
    def _tipo_conoscenza_memoria(knowledge_type: str) -> str:
        etichette = {
            "observed_fact": "Fatto osservato",
            "reported_fact": "Fatto riferito",
            "inference": "Inferenza",
            "belief": "Convinzione",
            "canonical_knowledge": "Conoscenza iniziale",
        }
        return etichette.get(knowledge_type, "Conoscenza")

    @staticmethod
    def _fonte_memoria(memoria: MemoriaPersonaggio) -> str:
        if memoria.source_name:
            return memoria.source_name
        etichette = {
            "direct_observation": "Osservazione diretta",
            "told_by_character": "Racconto",
            "inference": "Inferenza personale",
            "imported_background": "Conoscenza iniziale",
            "self_experience": "Esperienza personale",
        }
        return etichette.get(memoria.source_type, "Fonte non specificata")

    def _mostra_eventi_entita_selezionata(
        self, _evento: object | None = None
    ) -> None:
        for elemento in self.albero_eventi_entita.get_children():
            self.albero_eventi_entita.delete(elemento)
        if self.mondo_corrente is None:
            return
        selezione = self.albero_stato_mondo.selection()
        if not selezione:
            return
        entity_id = selezione[0]
        eventi = self.servizio.stato_mondo.eventi_per_entita(
            self.mondo_corrente.id, entity_id
        )
        if not eventi:
            self.albero_eventi_entita.insert(
                "", tk.END, values=("", "", UI_TEXT["nessun_evento"])
            )
        for evento in eventi:
            self.albero_eventi_entita.insert(
                "",
                tk.END,
                values=(
                    evento.occurred_at,
                    self._etichetta_tecnica(evento.event_type),
                    evento.reason,
                ),
            )
        for indice, oggetto in enumerate(self._oggetti_trasferibili):
            if oggetto.entity_id == entity_id:
                self.selettore_oggetto.current(indice)
                break

    def _trasferisci_oggetto_da_interfaccia(self) -> None:
        if self.mondo_corrente is None:
            return
        indice_oggetto = self.selettore_oggetto.current()
        indice_possessore = self.selettore_possessore.current()
        if indice_oggetto < 0 or indice_possessore < 0:
            messagebox.showwarning(
                UI_TEXT["errore"], UI_TEXT["seleziona_trasferimento"]
            )
            return
        oggetto = self._oggetti_trasferibili[indice_oggetto]
        possessore = self._possessori_disponibili[indice_possessore]
        try:
            self.servizio.stato_mondo.trasferisci_oggetto(
                self.mondo_corrente.id,
                oggetto.entity_id,
                possessore.entity_id,
                reason="Trasferimento manuale dall'interfaccia.",
            )
            self._aggiorna_stato_mondo()
            self.albero_stato_mondo.selection_set(oggetto.entity_id)
            self.albero_stato_mondo.focus(oggetto.entity_id)
            self._mostra_eventi_entita_selezionata()
            messagebox.showinfo(
                UI_TEXT["operazione_completata"],
                UI_TEXT["trasferimento_completato"],
            )
        except ErroreHaria as errore:
            messagebox.showerror(UI_TEXT["errore"], str(errore))

    @staticmethod
    def _etichetta_tecnica(valore: str) -> str:
        traduzioni = {
            "personaggio": "Personaggio",
            "luogo": "Luogo",
            "oggetto": "Oggetto",
            "active": "Attivo",
            "inaccessible": "Inaccessibile",
            "spostamento_entita": "Spostamento entità",
            "trasferimento_oggetto": "Trasferimento oggetto",
            "cambio_stato": "Cambio stato",
        }
        return traduzioni.get(valore, valore.replace("_", " ").capitalize())

    @staticmethod
    def _descrivi_posizione(
        entita: EntitaMondo, nomi: dict[str, str]
    ) -> str:
        posizione = nomi.get(entita.location_id, "—")
        dettaglio = entita.state_data.get("position")
        if isinstance(dettaglio, str) and dettaglio.strip():
            return f"{posizione} — {dettaglio.strip()}"
        return posizione

    def _aggiorna_cronologia(self) -> None:
        for elemento in self.albero_versioni.get_children():
            self.albero_versioni.delete(elemento)
        if self.mondo_corrente is None:
            return
        for versione in self.servizio.cronologia(self.mondo_corrente.id):
            self.albero_versioni.insert(
                "",
                tk.END,
                iid=str(versione.numero),
                values=(versione.numero, versione.creata_il, versione.motivo),
            )

    def _importa_da_interfaccia(self) -> None:
        cartella = filedialog.askdirectory(title=UI_TEXT["seleziona_sorgente"])
        if not cartella:
            return
        if not self._puo_proseguire_con_modifiche("importare un altro mondo"):
            return
        try:
            mondo = self.servizio.importa_da_cartella(cartella)
            self._mostra_mondo(mondo)
            messagebox.showinfo(
                UI_TEXT["operazione_completata"], UI_TEXT["importazione_completata"]
            )
        except ErroreHaria as errore:
            messagebox.showerror(UI_TEXT["errore"], str(errore))

    def _salva_da_interfaccia(self) -> None:
        self._salva_senza_dialogo(mostra_conferma=True)

    def _salva_senza_dialogo(self, *, mostra_conferma: bool = False) -> bool:
        if self.mondo_corrente is None:
            return False
        scenario = self.editor_scenario.get("1.0", "end-1c")
        impostazioni = {
            chiave: variabile.get()
            for chiave, variabile in self.campi_impostazioni.items()
        }
        try:
            mondo = self.servizio.salva(
                self.mondo_corrente.id, scenario, impostazioni
            )
            self._mostra_mondo(mondo)
            if mostra_conferma:
                messagebox.showinfo(
                    UI_TEXT["operazione_completata"],
                    UI_TEXT["salvataggio_completato"],
                )
            return True
        except ErroreHaria as errore:
            messagebox.showerror(UI_TEXT["errore"], str(errore))
            return False

    def _puo_proseguire_con_modifiche(self, azione: str) -> bool:
        if not self.stato_editor.modificato:
            return True
        risposta = messagebox.askyesnocancel(
            UI_TEXT["modifiche_non_salvate"],
            UI_TEXT["conferma_modifiche_non_salvate"].format(azione=azione),
        )
        if risposta is True:
            scelta = SceltaModifiche.SALVA
        elif risposta is False:
            scelta = SceltaModifiche.SCARTA
        else:
            scelta = SceltaModifiche.ANNULLA
        return self.stato_editor.consenti_operazione(
            scelta,
            lambda: self._salva_senza_dialogo(mostra_conferma=False),
        )

    def _ripristina_da_interfaccia(self) -> None:
        if self.mondo_corrente is None:
            return
        selezione = self.albero_versioni.selection()
        if not selezione:
            messagebox.showwarning(UI_TEXT["errore"], UI_TEXT["seleziona_versione"])
            return
        numero = int(selezione[0])
        conferma = messagebox.askyesno(
            UI_TEXT["ripristina"],
            UI_TEXT["conferma_ripristino"].format(numero=numero),
        )
        if not conferma:
            return
        if not self._puo_proseguire_con_modifiche(
            "ripristinare la versione selezionata"
        ):
            return
        try:
            mondo = self.servizio.ripristina(self.mondo_corrente.id, numero)
            self._mostra_mondo(mondo)
            messagebox.showinfo(
                UI_TEXT["operazione_completata"], UI_TEXT["ripristino_completato"]
            )
        except ErroreHaria as errore:
            messagebox.showerror(UI_TEXT["errore"], str(errore))

    def _esporta_da_interfaccia(self) -> None:
        if self.mondo_corrente is None:
            return
        cartella = filedialog.askdirectory(title=UI_TEXT["seleziona_destinazione"])
        if not cartella:
            return
        try:
            risultato = self.servizio.esporta(self.mondo_corrente.id, cartella)
            messagebox.showinfo(
                UI_TEXT["operazione_completata"],
                UI_TEXT["esportazione_completata"].format(
                    cartella=risultato.cartella
                ),
            )
        except ErroreHaria as errore:
            messagebox.showerror(UI_TEXT["errore"], str(errore))

    def chiudi(self) -> None:
        if not self._puo_proseguire_con_modifiche("chiudere l'applicazione"):
            return
        self._chiusura_in_corso = True
        self._coordinatore_ai.chiudi()
        if self._controllo_ai_after is not None:
            try:
                self.radice.after_cancel(self._controllo_ai_after)
            except tk.TclError:
                pass
            self._controllo_ai_after = None
        self.servizio.chiudi()
        self.radice.destroy()


def avvia(percorso_database: str | Path | None = None) -> None:
    radice = tk.Tk()
    try:
        ApplicazioneHaria(radice, percorso_database or database_predefinito())
    except ErroreHaria as errore:
        messagebox.showerror(UI_TEXT["errore"], str(errore))
        radice.destroy()
        return
    radice.mainloop()

