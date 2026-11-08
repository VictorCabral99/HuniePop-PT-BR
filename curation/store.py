"""In-memory locale used by the curation desk.

The accented working copy is ``locale/pt-BR/unique_texts.csv``.
The file the game patch actually reads is ``unique_texts_ascii.csv``,
rebuilt with ``fold_ascii_pt.export_game_csv`` on every save.
Review status lives beside them in ``review.json`` and never enters the patch.
"""
from __future__ import annotations

import json
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from fold_ascii_pt import colloquialize, export_game_csv, fold_ascii, transform  # noqa: E402
from locale_csv import read_locale_rows, write_locale_rows  # noqa: E402

LOCALE_FIELDS = ["sample_id", "category", "occurrences", "text", "pt_BR", "char_diff"]
REVIEW_STATUSES = {"", "ok", "fix"}
PROBLEM_FLAGS = {"vazio", "igual", "eu", "chave"}
WARNING_FLAGS = {"pausa", "longo", "curto", "reescrito"}

NAMES = {
    "kyanna",
    "audrey",
    "aiko",
    "jessie",
    "nikki",
    "lola",
    "tiffany",
    "beli",
    "celeste",
    "momo",
    "venus",
    "kyu",
    "suzume",
}
LOGIC_KEYS = {
    "success",
    "failure",
    "sex",
    "loves",
    "hates",
    "likes",
    "morning",
    "afternoon",
    "evening",
    "night",
    "drunk",
    "hungry",
    "early",
    "accept",
    "full",
    "unique",
}

PAUSE_RE = re.compile(r"(?:\u00b7{2,}|\.{3,}|…+)")
EU_RE = re.compile(
    r"\b("
    r"tu|tens|vais|queres|podes|tenhas|sejas|contigo|convosco|"
    r"rapariga|raparigas|miúda|miúdas|miuda|miudas|"
    r"telemóvel|telemovel|estás|estas|teu|tua|teus|tuas|"
    r"vosso|vossa|vossos|vossas|autocarro|facto|equipa|equipas"
    r")\b|est[aá]s?\s+a\s+\w|actualmente|pequeno[- ]almo[cç]o",
    re.IGNORECASE,
)
GIFT_KEY_RE = re.compile(r"likes gift type \d+$", re.IGNORECASE)
LAUGH_CORE_RE = re.compile(r"[haeiouxz]+", re.IGNORECASE)
ID_RE = re.compile(r"^[0-9a-f]{12}$")
GROUP_RE = re.compile(r"^[A-Za-z0-9_]+$")


def is_name(text: str) -> bool:
    return text.strip().lower() in NAMES


def is_logic_key(text: str) -> bool:
    raw = text.strip().lower()
    return raw in LOGIC_KEYS or bool(GIFT_KEY_RE.fullmatch(raw))


def is_kept_english(text: str) -> bool:
    """Names, sizes, weights and laughter that are fine left in English."""
    raw = text.strip()
    if is_name(raw):
        return True
    if re.fullmatch(r"[\W\d_]+", raw or " "):
        return True
    if re.fullmatch(r"[A-D]{1,2} Cup", raw):
        return True
    if re.fullmatch(r"\d+ lbs", raw):
        return True
    if re.fullmatch(r"\d+ Feet \d+ Inches", raw):
        return True
    core = re.sub(r"[\s.!*?·…\-_'']", "", raw)
    if core and LAUGH_CORE_RE.fullmatch(core) and " " not in raw.strip(" *"):
        return True
    # "Ahhh!" / "Hahahahaha!" / "*aaaaaacc*Hehehehe"
    letters = re.sub(r"[^A-Za-z]", "", raw)
    if letters and LAUGH_CORE_RE.fullmatch(letters) and len(raw) < 40:
        return True
    # "Awwwww!" / "Hmmmm..." / "Byyyyyeee." — one stretched token, not a sentence.
    if " " not in raw and letters:
        squashed = re.sub(r"(.)\1+", r"\1", letters.lower())
        if squashed in {
            "a", "aw", "ah", "ha", "haha", "he", "hehe", "hi", "hey", "hmm", "hm",
            "oh", "oo", "bye", "and", "ew", "yo", "ya", "wow", "ow", "ugh", "uh", "um", "eh",
        }:
            return True
    return False


def pause_count(text: str) -> int:
    return len(PAUSE_RE.findall(text or ""))


def flags_for(en: str, pt: str) -> list[str]:
    en = en or ""
    pt = (pt or "").strip()
    flags: list[str] = []
    if is_logic_key(en):
        flags.append("chave" if pt and pt != en.strip() else "chave-ok")
    if not pt:
        if is_name(en):
            flags.append("nome")
        elif not is_kept_english(en) and not is_logic_key(en):
            flags.append("vazio")
    elif pt == en:
        if is_name(en) or is_kept_english(en) or is_logic_key(en):
            flags.append("mantido")
        else:
            flags.append("igual")
    else:
        if EU_RE.search(pt):
            flags.append("eu")
        if transform(pt) != pt and _colloquial_changed(pt):
            flags.append("reescrito")
    if pause_count(en) > pause_count(pt):
        flags.append("pausa")
    if len(en) > 20 and len(pt) > max(40, int(len(en) * 1.8)):
        flags.append("longo")
    if pt and len(en) > 40 and len(pt) < int(len(en) * 0.45):
        flags.append("curto")
    return flags


def _colloquial_changed(pt: str) -> bool:
    """True when the game export rewrites words, not only strips accents."""
    return fold_ascii(colloquialize(pt)) != fold_ascii(pt)


def role_of(field_path: str, has_pair: bool) -> str:
    fp = field_path or ""
    if "secondaryText" in fp:
        return "jogadora"
    if "responseOptions" in fp:
        return "escolha"
    if fp.endswith(".label") or ".label" in fp:
        return "rotulo"
    if has_pair:
        return "jogador"
    return "fala"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Store:
    def __init__(
        self,
        rows: list[dict],
        groups: list[dict],
        review: dict,
        locale_path: Path,
        ascii_path: Path,
        review_path: Path,
    ) -> None:
        self.rows = rows
        self.groups = groups
        self.review = review
        self.locale_path = locale_path
        self.ascii_path = ascii_path
        self.review_path = review_path
        self.lock = threading.Lock()
        self._catalog: dict | None = None
        self._index()

    def _index(self) -> None:
        self.by_id = {r["sample_id"]: r for r in self.rows}
        self.by_text: dict[str, dict] = {}
        for row in self.rows:
            self.by_text.setdefault(row.get("text") or "", row)
        self._catalog = None

    @classmethod
    def open(cls, root: Path | None = None) -> "Store":
        root = root or ROOT
        locale = root / "locale" / "pt-BR" / "unique_texts.csv"
        ascii_path = root / "locale" / "pt-BR" / "unique_texts_ascii.csv"
        review_path = root / "locale" / "pt-BR" / "review.json"
        groups_path = root / "export" / "en" / "dialogue_groups.json"
        rows, _ = read_locale_rows(locale)
        groups = json.loads(groups_path.read_text(encoding="utf-8"))
        review = {"version": 1, "lines": {}}
        if review_path.exists():
            loaded = json.loads(review_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("lines"), dict):
                review = loaded
        return cls(rows, groups, review, locale, ascii_path, review_path)

    def line_view(self, row: dict, where: list[str] | None = None) -> dict:
        en = row.get("text") or ""
        pt = row.get("pt_BR") or ""
        meta = self.review.get("lines", {}).get(row["sample_id"], {})
        return {
            "id": row["sample_id"],
            "cat": row.get("category") or "other",
            "n": int(row.get("occurrences") or 0),
            "en": en,
            "pt": pt,
            "game": transform(pt),
            "flags": flags_for(en, pt),
            "status": meta.get("status") or "",
            "note": meta.get("note") or "",
            "updated": meta.get("updated") or "",
            "where": where or [],
        }

    def _where_index(self) -> dict[str, list[str]]:
        where: dict[str, list[str]] = {}
        for group in self.groups:
            gid = group.get("group_id") or ""
            for line in group.get("lines") or []:
                row = self._row_for_line(line)
                if not row:
                    continue
                bucket = where.setdefault(row["sample_id"], [])
                if gid not in bucket:
                    bucket.append(gid)
        return where

    def _row_for_line(self, line: dict) -> dict | None:
        row = self.by_id.get(line.get("id") or "")
        if row:
            return row
        return self.by_text.get(line.get("text") or "")

    def catalog(self) -> dict:
        with self.lock:
            if self._catalog is not None:
                return self._catalog
            where = self._where_index()
            strings = [self.line_view(row, where.get(row["sample_id"], [])) for row in self.rows]
            by_id = {item["id"]: item for item in strings}
            scenes = []
            for group in self.groups:
                alerts = 0
                ids: list[str] = []
                for line in group.get("lines") or []:
                    row = self._row_for_line(line)
                    if not row:
                        continue
                    ids.append(row["sample_id"])
                    item = by_id[row["sample_id"]]
                    if _needs_review(item):
                        alerts += 1
                scenes.append(
                    {
                        "id": group.get("group_id") or "",
                        "girl": group.get("girl") or "",
                        "kind": group.get("kind") or "",
                        "n": group.get("n_lines") or 0,
                        "alerts": alerts,
                        "ids": ids,
                    }
                )
            self._catalog = {
                "strings": strings,
                "scenes": scenes,
                "stats": _stats(strings),
            }
            return self._catalog

    def scene(self, group_id: str) -> dict | None:
        if not GROUP_RE.fullmatch(group_id or ""):
            return None
        with self.lock:
            group = next((g for g in self.groups if g.get("group_id") == group_id), None)
            if not group:
                return None
            paths = [ln.get("field_path") or "" for ln in group.get("lines") or []]
            path_set = set(paths)
            lines = []
            for index, line in enumerate(group.get("lines") or []):
                row = self._row_for_line(line)
                fp = line.get("field_path") or ""
                pair = False
                if fp.endswith(".text") and "secondaryText" not in fp:
                    pair = fp[: -len("text")] + "secondaryText" in path_set
                if row:
                    view = self.line_view(row)
                else:
                    en = line.get("text") or ""
                    view = {
                        "id": "",
                        "cat": "dialogue",
                        "n": 1,
                        "en": en,
                        "pt": "",
                        "game": "",
                        "flags": flags_for(en, ""),
                        "status": "",
                        "note": "",
                        "updated": "",
                        "where": [group_id],
                    }
                view["role"] = role_of(fp, pair)
                view["idx"] = index
                lines.append(view)
            return {
                "id": group_id,
                "girl": group.get("girl") or "",
                "kind": group.get("kind") or "",
                "lines": lines,
            }

    def preview(self, sample_id: str, pt: str) -> dict | None:
        if not ID_RE.fullmatch(sample_id or ""):
            return None
        with self.lock:
            row = self.by_id.get(sample_id)
            if not row:
                return None
            en = row.get("text") or ""
            return {"id": sample_id, "pt": pt, "game": transform(pt), "flags": flags_for(en, pt)}

    def update(self, sample_id: str, pt: str, status: str, note: str) -> dict:
        if not ID_RE.fullmatch(sample_id or ""):
            raise ValueError("frase desconhecida")
        if status not in REVIEW_STATUSES:
            raise ValueError("status inválido")
        if "\n" in pt or "\r" in pt or "\x00" in pt:
            raise ValueError("a tradução precisa ficar em uma linha")
        if len(pt) > 8000:
            raise ValueError("tradução longa demais")
        note = (note or "").strip()
        if len(note) > 500:
            raise ValueError("nota longa demais")
        with self.lock:
            row = self.by_id.get(sample_id)
            if not row:
                raise ValueError("frase desconhecida")
            row["pt_BR"] = pt
            lines = self.review.setdefault("lines", {})
            if status or note:
                lines[sample_id] = {"status": status, "note": note, "updated": _now()}
            else:
                lines.pop(sample_id, None)
            self._write_locale()
            self._write_review()
            export_game_csv(self.locale_path, self.ascii_path)
            self._catalog = None
            where = self._where_index().get(sample_id, [])
            return self.line_view(row, where)

    def _write_locale(self) -> None:
        write_locale_rows(self.locale_path, self.rows, LOCALE_FIELDS)

    def _write_review(self) -> None:
        self.review["version"] = 1
        if not self.review.get("lines"):
            if self.review_path.exists():
                self.review_path.unlink()
            return
        payload = json.dumps(self.review, ensure_ascii=False, indent=2) + "\n"
        self.review_path.parent.mkdir(parents=True, exist_ok=True)
        self.review_path.write_text(payload, encoding="utf-8")

    def apply(self) -> dict:
        with self.lock:
            stats = export_game_csv(self.locale_path, self.ascii_path)
            self._catalog = None
        catalog = self.catalog()
        return {
            "rows": stats["rows"],
            "changed": stats["changed"],
            "file": str(self.ascii_path.relative_to(ROOT)) if self.ascii_path.is_relative_to(ROOT) else str(self.ascii_path),
            "stats": catalog["stats"],
        }


def _needs_review(item: dict) -> bool:
    if item.get("status") == "ok":
        return False
    return any(flag in PROBLEM_FLAGS for flag in item.get("flags") or [])


def _stats(strings: list[dict]) -> dict:
    problems = sum(1 for item in strings if _needs_review(item))
    warnings = sum(
        1
        for item in strings
        if item.get("status") != "ok" and any(flag in WARNING_FLAGS for flag in item.get("flags") or [])
    )
    approved = sum(1 for item in strings if item.get("status") == "ok")
    needs_work = sum(1 for item in strings if item.get("status") == "fix")
    applied = sum(1 for item in strings if (item.get("pt") or "").strip() and item.get("pt") != item.get("en"))
    return {
        "total": len(strings),
        "problems": problems,
        "warnings": warnings,
        "approved": approved,
        "needs_work": needs_work,
        "applied": applied,
    }
