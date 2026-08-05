"""Tester för exportens proveniensstämpel.

Bakgrund: `bibliotek/…del2` bar `ENER- GISTRÅLE` och `SMIslaget.` — brytfel
som redan var lagade i `pipeline/export.py` men i en `bok.md` som ingen kört
om. Ingen varning, ingenting i `status`. Testerna nedan mäter båda riktningarna:
en export byggd på HEAD ska vara TYST, och en stämpel backad ett steg ska tända
varningen.

Git-arbetsträdet byggs i tempkatalogen. Att mäta mot repots eget träd hade
gjort utfallet beroende av om det råkar vara smutsigt när sviten körs.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from pipeline import SCHEMA_VERSION
from pipeline.merge import merge
from pipeline.provenance import (STAMP_KEY, check_exports, check_stamp,
                                 code_dirty, code_revision, record, stamp)


def git(root, *args):
    subprocess.run(("git", "-C", str(root)) + args, check=True,
                   capture_output=True, text=True)


def repo_with_two_commits(root):
    """Ett arbetsträd med en historik att backa i."""
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")
    (root / "pipeline").mkdir()
    (root / "pipeline" / "rows.py").write_text("# v1\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "första")
    forra = subprocess.run(("git", "-C", str(root), "rev-parse", "HEAD"),
                           capture_output=True, text=True).stdout.strip()
    (root / "pipeline" / "rows.py").write_text("# v2 — lagad\n",
                                               encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "andra")
    return forra


class TestStamp(unittest.TestCase):
    def test_stamp_reads_revision_and_clean_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_with_two_commits(root)
            mark = stamp(root)
            self.assertEqual(mark["git_revision"], code_revision(root))
            self.assertEqual(mark["schema_version"], SCHEMA_VERSION)
            self.assertFalse(mark["smutsigt"])

    def test_dirty_code_tree_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_with_two_commits(root)
            (root / "pipeline" / "rows.py").write_text("# oincheckat\n",
                                                       encoding="utf-8")
            self.assertTrue(code_dirty(root))
            self.assertTrue(stamp(root)["smutsigt"])

    def test_changes_outside_the_code_dirs_do_not_dirty_the_stamp(self):
        """`arbete/` ändras vid varje körning och säger inget om byggaren."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_with_two_commits(root)
            (root / "arbete").mkdir()
            (root / "arbete" / "bok.json").write_text("{}", encoding="utf-8")
            self.assertFalse(code_dirty(root))

    def test_outside_a_worktree_there_is_no_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(code_revision(Path(tmp) / "finns-inte"))


class TestCheckStamp(unittest.TestCase):
    def test_stamp_built_on_head_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_with_two_commits(root)
            self.assertEqual(check_stamp(stamp(root), "bok.md", root), [])

    def test_stamp_backed_one_commit_raises_the_warning(self):
        """Motprovet till testet ovan: samma stämpel, en revision bakåt."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            forra = repo_with_two_commits(root)
            mark = dict(stamp(root), git_revision=forra)
            varningar = check_stamp(mark, "bok.md", root)
            self.assertEqual(len(varningar), 1)
            self.assertIn("ÄLDRE kod än HEAD", varningar[0])
            self.assertIn(forra[:12], varningar[0])

    def test_missing_stamp_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_with_two_commits(root)
            varningar = check_stamp(None, "bok.json", root)
            self.assertEqual(len(varningar), 1)
            self.assertIn("saknar proveniensstämpel", varningar[0])

    def test_unknown_revision_is_not_called_old(self):
        """En revision utanför HEAD:s historia är okänd, inte gammal."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_with_two_commits(root)
            mark = dict(stamp(root), git_revision="0" * 40)
            varningar = check_stamp(mark, "bok.md", root)
            self.assertEqual(len(varningar), 1)
            self.assertIn("INTE ligger i HEAD:s historia", varningar[0])

    def test_schema_version_drift_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_with_two_commits(root)
            mark = dict(stamp(root), schema_version=SCHEMA_VERSION - 1)
            varningar = check_stamp(mark, "bok.json", root)
            self.assertEqual(len(varningar), 1)
            self.assertIn("schemaversion", varningar[0])


class TestExportStamps(unittest.TestCase):
    """Stämpeln skrivs där artefakten byggs — och läses tillbaka därifrån."""

    def workdir(self, tmp):
        wd = Path(tmp) / "arbete" / "bok"
        (wd / "export").mkdir(parents=True)
        return wd

    def test_merge_stamps_bok_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            wd = self.workdir(tmp)
            (wd / "book.json").write_text(json.dumps({
                "schema_version": SCHEMA_VERSION, "source": {"path": "x.pdf"},
                "pages": {"1": {"class": "text", "state": "final"}},
            }), encoding="utf-8")
            book, _ = merge(wd)
            self.assertIn(STAMP_KEY, book)
            self.assertEqual(book[STAMP_KEY]["schema_version"],
                             SCHEMA_VERSION)

    def test_check_exports_reads_both_places(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            repo_with_two_commits(root)
            wd = self.workdir(tmp)
            (wd / "export" / "bok.json").write_text(
                json.dumps({STAMP_KEY: stamp(root)}), encoding="utf-8")
            (wd / "export" / "bok.md").write_text("# bok", encoding="utf-8")
            record(wd, "bok.md", root)
            self.assertEqual(check_exports(wd, root), [])
            # Backa markdownens stämpel ett steg — bara den ska larma.
            path = wd / "export" / "proveniens.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["bok.md"]["git_revision"] = subprocess.run(
                ("git", "-C", str(root), "rev-parse", "HEAD~1"),
                capture_output=True, text=True).stdout.strip()
            path.write_text(json.dumps(data), encoding="utf-8")
            varningar = check_exports(wd, root)
            self.assertEqual(len(varningar), 1)
            self.assertIn("bok.md", varningar[0])

    def test_an_unbuilt_artifact_is_not_missing_a_stamp(self):
        """Finns ingen bok.md är det inget att varna för."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            repo_with_two_commits(root)
            wd = self.workdir(tmp)
            (wd / "export" / "bok.json").write_text(
                json.dumps({STAMP_KEY: stamp(root)}), encoding="utf-8")
            self.assertEqual(check_exports(wd, root), [])


if __name__ == "__main__":
    unittest.main()
