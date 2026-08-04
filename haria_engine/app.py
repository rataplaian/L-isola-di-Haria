"""Interfaccia desktop Tkinter completamente leggibile in italiano."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .editor_state import SceltaModifiche, StatoEditor
from .errors import ErroreHaria
from .memories import MemoriaPersonaggio
from .models import Mondo
from .paths import database_predefinito
from .service import ServizioMondi
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

        self.radice.title(UI_TEXT["titolo_finestra"])
        self.radice.geometry("1080x720")
        self.radice.minsize(820, 560)
        self.radice.protocol("WM_DELETE_WINDOW", self.chiudi)
        self._costruisci_interfaccia()
        self._carica_mondo_esistente()

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
        self.pulsante_salva.configure(state=tk.NORMAL)
        self.pulsante_esporta.configure(state=tk.NORMAL)
        self.pulsante_ripristina.configure(state=tk.NORMAL)
        self._aggiorna_indicatore_modifiche()

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
                    "Corrente" if memoria.is_current else "Superata",
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

