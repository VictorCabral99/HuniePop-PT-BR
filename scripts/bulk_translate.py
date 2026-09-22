"""Bulk-fill locale/pt-BR/unique_texts.csv using offline Argos (en->pt).

Preserves [[markup]] tags and skips already-filled rows / proper-name-only lines.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import argostranslate.translate as tr

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "locale" / "pt-BR" / "unique_texts.csv"

MARKUP_RE = re.compile(r"\[\[[^\]]+\][^\]]*\]")
# special pause / control-ish chars seen in HuniePop dialogue
SPECIAL_RE = re.compile(r"[\u200b-\u200f\u2028-\u202f\ufeff\ufffd]+")

KEEP_AS_IS = {
    "Hunie",
    "Boops",
    "OK",
    "Normal",
    "Hard",  # may still translate elsewhere
}

NAME_HINTS = {
    "Audrey",
    "Kyanna",
    "Jessie",
    "Tiffany",
    "Nikki",
    "Aiko",
    "Lola",
    "Suzume",
    "Beliath",
    "Miku",
    "Kyu",
}


def protect_markup(text: str) -> tuple[str, list[str]]:
    parts: list[str] = []

    def repl(m: re.Match) -> str:
        parts.append(m.group(0))
        return f"«M{len(parts) - 1}»"

    return MARKUP_RE.sub(repl, text), parts


def restore_markup(text: str, parts: list[str]) -> str:
    out = text
    for i, tag in enumerate(parts):
        for token in (f"«M{i}»", f"<<M{i}>>", f"M{i}"):
            if token in out:
                out = out.replace(token, tag)
    return out


def should_skip(text: str) -> bool:
    t = text.strip()
    if not t or t in KEEP_AS_IS or t in NAME_HINTS:
        return True
    if re.fullmatch(r"[A-Za-z]+", t) and t[0].isupper() and t in NAME_HINTS:
        return True
    if re.fullmatch(r"[0-9A-Fa-f]{6}", t):
        return True
    if len(t) <= 1:
        return True
    return False


def to_pt_br_ish(s: str) -> str:
    """Light European-PT -> BR-ish tweaks."""
    reps = [
        (" ver-te ", " te ver "),
        ("Ver-te ", "Te ver "),
        ("você", "você"),
        ("Vocês", "Vocês"),
        (" para ti", " para você"),
        (" contigo", " com você"),
        (" tu ", " você "),
        (" Tu ", " Você "),
        (" teu ", " seu "),
        (" tua ", " sua "),
        (" teus ", " seus "),
        (" tuas ", " suas "),
    ]
    out = s
    for a, b in reps:
        out = out.replace(a, b)
    return out


def translate_one(text: str) -> str:
    protected, parts = protect_markup(text)
    # Argos can choke on huge lines; keep as-is if empty
    try:
        pt = tr.translate(protected, "en", "pt")
    except Exception as e:
        print(f"  fail: {text[:60]!r} ({e})", flush=True)
        return ""
    pt = restore_markup(pt, parts)
    pt = to_pt_br_ish(pt)
    return pt.strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--limit", type=int, default=0, help="Max new translations (0=all)")
    ap.add_argument("--categories", nargs="*", default=None, help="e.g. dialogue item message ui")
    ap.add_argument("--force", action="store_true", help="Overwrite existing pt_BR")
    args = ap.parse_args(argv)

    rows = list(csv.DictReader(args.csv.open(encoding="utf-8")))
    fields = list(rows[0].keys())
    done = 0
    skipped = 0
    for i, row in enumerate(rows):
        if args.categories and row.get("category") not in args.categories:
            continue
        if (row.get("pt_BR") or "").strip() and not args.force:
            skipped += 1
            continue
        text = row["text"]
        if should_skip(text):
            skipped += 1
            continue
        pt = translate_one(text)
        if not pt:
            skipped += 1
            continue
        row["pt_BR"] = pt
        done += 1
        if done % 50 == 0:
            print(f"... {done} translated (row {i+1}/{len(rows)})", flush=True)
            # checkpoint
            with args.csv.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
        if args.limit and done >= args.limit:
            break

    with args.csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    filled = sum(1 for r in rows if (r.get("pt_BR") or "").strip())
    print(f"new={done} skipped={skipped} filled_total={filled}/{len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
