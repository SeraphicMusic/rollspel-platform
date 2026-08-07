"""`--efter-dom`: en exportkodsburen förlust passerar BARA via en grön frysning.

Omexporten 2026-08-07 tog bort ord ur läsexporten som ingen korrektionspost
kan bära — statblockens dubblerade namnrader och listavskiljaren `—` är
exportörens egna, inte bokens. Domen bor i `beslut.md` och i den omtagna
frysningen. Undantaget får aldrig bli en bakdörr: är frysningen INTE ordlik
exporten finns ingen dömd övergång att luta sig mot, och spärren står kvar.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.uppdatera_bibliotek import buren_av_frysningen


class EfterDom(unittest.TestCase):
    def setUp(self):
        self.wd = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.wd, ignore_errors=True)
        (self.wd / "export").mkdir()

    def skriv(self, frysning, bok):
        if frysning is not None:
            (self.wd / "export" / "bok.frysning.md").write_text(
                frysning, encoding="utf-8")
        (self.wd / "export" / "bok.md").write_text(bok, encoding="utf-8")

    def test_gron_frysning_bar_forlusten(self):
        # Namndubbletten är borta ur BÅDE frysning och export: dömd övergång.
        self.skriv("Grym är stark. Han slåss.", "Grym är stark. Han slåss.")
        self.assertTrue(buren_av_frysningen(self.wd))

    def test_ur_takt_frysning_bar_ingenting(self):
        # Exporten har tappat ord som frysningen ännu bär — ingen dom finns,
        # det är precis den drift grinden ska fälla.
        self.skriv("Grym Grym är stark.", "Grym är stark.")
        self.assertFalse(buren_av_frysningen(self.wd))

    def test_saknad_frysning_bar_ingenting(self):
        self.skriv(None, "Grym är stark.")
        self.assertFalse(buren_av_frysningen(self.wd))

    def test_formen_far_andras(self):
        # Ordlikhet, inte byteslikhet: en omflödning ändrar rader, inte ord.
        self.skriv("Grym är stark.\nHan slåss.", "Grym är stark. Han slåss.")
        self.assertTrue(buren_av_frysningen(self.wd))


if __name__ == "__main__":
    unittest.main()
