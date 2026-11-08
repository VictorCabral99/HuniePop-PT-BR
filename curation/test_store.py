"""Tests for the curation store and its HTTP desk."""
from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from store import Store, flags_for
from fold_ascii_pt import export_game_csv
from locale_csv import read_locale_rows, write_locale_rows

ROOT = Path(__file__).resolve().parents[1]


class FlagTests(unittest.TestCase):
    def test_european_and_empty_and_name(self):
        self.assertIn("eu", flags_for("Your turn.", "É a tua vez!"))
        self.assertIn("vazio", flags_for("Normal", ""))
        self.assertIn("nome", flags_for("Kyanna", ""))
        self.assertNotIn("vazio", flags_for("Kyanna", ""))
        self.assertIn("chave", flags_for("success", "sucesso"))
        self.assertIn("chave-ok", flags_for("success", "success"))
        self.assertIn("pausa", flags_for("Oh...····· hey.", "Olá."))
        self.assertNotIn("igual", flags_for("Ahhh!", "Ahhh!"))
        self.assertNotIn("igual", flags_for("Awwwww!", "Awwwww!"))
        self.assertIn("igual", flags_for("Hiii daddy...", "Hiii daddy..."))
        self.assertIn("igual", flags_for("I hope to see you again soon.", "I hope to see you again soon."))

    def test_game_preview_folds(self):
        flags = flags_for("What am I gonna do with you?", "O que vou fazer contigo?")
        self.assertIn("eu", flags)
        self.assertIn("reescrito", flags)


class RoundtripTests(unittest.TestCase):
    def test_locale_writer_matches_committed_files(self):
        locale = ROOT / "locale" / "pt-BR" / "unique_texts.csv"
        rows, fields = read_locale_rows(locale)
        target = ROOT / "build" / "locale-roundtrip.csv"
        target.parent.mkdir(parents=True, exist_ok=True)
        write_locale_rows(target, rows, fields)
        self.assertEqual(target.read_bytes(), locale.read_bytes())
        target.unlink()

    def test_export_matches_game_file(self):
        src = ROOT / "locale" / "pt-BR" / "unique_texts.csv"
        out = ROOT / "build" / "ascii-roundtrip.csv"
        export_game_csv(src, out)
        expected = ROOT / "locale" / "pt-BR" / "unique_texts_ascii.csv"
        self.assertEqual(out.read_bytes(), expected.read_bytes())
        out.unlink()


def make_fixture(tmp: Path) -> Store:
    if tmp.exists():
        for child in sorted(tmp.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
    locale_dir = tmp / "locale" / "pt-BR"
    export_dir = tmp / "export" / "en"
    locale_dir.mkdir(parents=True, exist_ok=True)
    export_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "sample_id": "aaaaaaaaaaaa",
            "category": "dialogue",
            "occurrences": "1",
            "text": "Yeah, okay! I'd love to go out with you.",
            "pt_BR": "Sim, está bem.",
            "char_diff": "",
        },
        {
            "sample_id": "bbbbbbbbbbbb",
            "category": "ui",
            "occurrences": "1",
            "text": "Normal",
            "pt_BR": "",
            "char_diff": "",
        },
    ]
    write_locale_rows(locale_dir / "unique_texts.csv", rows, list(rows[0].keys()))
    groups = [
        {
            "group_id": "IntroAiko",
            "object_name": "IntroAiko",
            "girl": "Aiko",
            "kind": "Intro",
            "n_lines": 1,
            "lines": [
                {
                    "id": "aaaaaaaaaaaa",
                    "path_id": 1,
                    "field_path": "steps[0].sceneLine.dialogLine.text",
                    "text": rows[0]["text"],
                }
            ],
        }
    ]
    (export_dir / "dialogue_groups.json").write_text(json.dumps(groups), encoding="utf-8")
    return Store.open(tmp)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = ROOT / "build" / "curation-test"
        self.store = make_fixture(self.tmp)

    def test_update_rewrites_both_csvs_and_review(self):
        saved = self.store.update("aaaaaaaaaaaa", "Beleza! Quero sair com você.", "ok", "tom")
        self.assertEqual(saved["pt"], "Beleza! Quero sair com você.")
        self.assertEqual(saved["status"], "ok")
        self.assertEqual(saved["game"], "Beleza! Quero sair com voce.")
        self.assertIn("IntroAiko", saved["where"])
        locale = read_locale_rows(self.tmp / "locale" / "pt-BR" / "unique_texts.csv")[0]
        ascii_rows = read_locale_rows(self.tmp / "locale" / "pt-BR" / "unique_texts_ascii.csv")[0]
        self.assertEqual(locale[0]["pt_BR"], "Beleza! Quero sair com você.")
        self.assertEqual(ascii_rows[0]["pt_BR"], "Beleza! Quero sair com voce.")
        review = json.loads((self.tmp / "locale" / "pt-BR" / "review.json").read_text(encoding="utf-8"))
        self.assertEqual(review["lines"]["aaaaaaaaaaaa"]["status"], "ok")
        scene = self.store.scene("IntroAiko")
        self.assertEqual(scene["lines"][0]["role"], "fala")
        self.assertEqual(scene["lines"][0]["pt"], "Beleza! Quero sair com você.")

    def test_rejects_newlines_and_unknown_ids(self):
        with self.assertRaises(ValueError):
            self.store.update("aaaaaaaaaaaa", "linha\nnova", "", "")
        with self.assertRaises(ValueError):
            self.store.update("zzzzzzzzzzzz", "oi", "", "")
        self.assertIsNone(self.store.scene("../etc/passwd"))
        self.assertIsNone(self.store.preview("nope", "oi"))


class ApiTests(unittest.TestCase):
    def test_http_roundtrip(self):
        from server import serve

        store = make_fixture(ROOT / "build" / "curation-test-api")
        httpd = serve(store, "127.0.0.1", 0)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}"
            with urllib.request.urlopen(base + "/api/health") as response:
                self.assertEqual(json.load(response)["ok"], True)
            with urllib.request.urlopen(base + "/") as response:
                html = response.read().decode("utf-8")
            self.assertIn("Curadoria PT-BR", html)
            body = json.dumps({"id": "bbbbbbbbbbbb", "pt": "Normal", "status": "fix", "note": ""}).encode()
            request = urllib.request.Request(base + "/api/line", data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request) as response:
                payload = json.load(response)
            self.assertEqual(payload["status"], "fix")
            self.assertNotIn("vazio", payload["flags"])
            bad = urllib.request.Request(
                base + "/api/line",
                data=b'{"id":"aaaaaaaaaaaa","pt":"a\\nb"}',
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(bad)
            self.assertEqual(caught.exception.code, 400)
        finally:
            httpd.shutdown()


if __name__ == "__main__":
    unittest.main()
