from __future__ import annotations

import unittest

from haria_engine.editor_state import SceltaModifiche, StatoEditor


class TestStatoEditor(unittest.TestCase):
    def setUp(self) -> None:
        self.stato = StatoEditor()
        self.stato.carica("Scenario salvato", {"tone": "sobrio"})

    def test_modifica_scenario_imposta_stato_dirty(self) -> None:
        self.stato.aggiorna_scenario("Scenario modificato")

        self.assertTrue(self.stato.modificato)

    def test_modifica_impostazione_imposta_stato_dirty(self) -> None:
        self.stato.aggiorna_impostazione("tone", "contemplativo")

        self.assertTrue(self.stato.modificato)

    def test_salvataggio_azzera_stato_dirty(self) -> None:
        self.stato.aggiorna_scenario("Scenario modificato")

        self.stato.registra_salvataggio()

        self.assertFalse(self.stato.modificato)

    def test_annulla_impedisce_operazione_e_non_salva(self) -> None:
        self.stato.aggiorna_scenario("Scenario modificato")
        salvataggi = 0

        def salva() -> bool:
            nonlocal salvataggi
            salvataggi += 1
            return True

        consentita = self.stato.consenti_operazione(
            SceltaModifiche.ANNULLA, salva
        )

        self.assertFalse(consentita)
        self.assertEqual(0, salvataggi)
        self.assertTrue(self.stato.modificato)

    def test_scarta_consente_operazione_senza_salvare(self) -> None:
        self.stato.aggiorna_scenario("Scenario modificato")
        salvataggi = 0

        def salva() -> bool:
            nonlocal salvataggi
            salvataggi += 1
            return True

        consentita = self.stato.consenti_operazione(
            SceltaModifiche.SCARTA, salva
        )

        self.assertTrue(consentita)
        self.assertEqual(0, salvataggi)
        self.assertTrue(self.stato.modificato)

    def test_salva_consente_operazione_e_azzera_dirty(self) -> None:
        self.stato.aggiorna_impostazione("tone", "contemplativo")
        salvataggi = 0

        def salva() -> bool:
            nonlocal salvataggi
            salvataggi += 1
            return True

        consentita = self.stato.consenti_operazione(
            SceltaModifiche.SALVA, salva
        )

        self.assertTrue(consentita)
        self.assertEqual(1, salvataggi)
        self.assertFalse(self.stato.modificato)


if __name__ == "__main__":
    unittest.main()
