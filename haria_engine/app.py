"""Interfaccia desktop Tkinter completamente leggibile in italiano."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .editor_state import SceltaModifiche, StatoEditor
from .errors import ErroreHaria
from .models import Mondo
from .paths import database_predefinito
from .service import ServizioMondi


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
    ApplicazioneHaria(radice, percorso_database or database_predefinito())
    radice.mainloop()

