"""Retranslate dialogue using scene groups + English context window.

Source of truth = English (`text`). Nearby lines in the same object_name
(scene) are passed to the translator so wording stays consistent.

Backends:
  --backend argos   (default) chunked numbered blocks
  --backend echo    dry-run (copies EN)

Afterward run:
  python scripts/fold_ascii_pt.py
  python scripts/apply_patch_expand.py --locale locale/pt-BR/unique_texts_ascii.csv --install

Usage:
  python scripts/retranslate_contextual.py --prefix Intro --limit-groups 3
  python scripts/retranslate_contextual.py --categories dialogue --force
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS_JSON = ROOT / "export" / "en" / "dialogue_groups.json"
LOCALE_CSV = ROOT / "locale" / "pt-BR" / "unique_texts.csv"

MARKUP_RE = re.compile(r"\[\[[^\]]+\][^\]]*\]")
# HuniePop timing dots (middle dot / ellipsis runs) — must not go through MT
PAUSE_RE = re.compile(r"(?:\u00b7|\u2022|\u2027|\u22c5|\u2219|\.){2,}|…+")


def protect_markup(text: str) -> tuple[str, list[str]]:
    parts: list[str] = []

    def repl_markup(m: re.Match) -> str:
        parts.append(m.group(0))
        return f"[[M{len(parts) - 1}]]"

    def repl_pause(m: re.Match) -> str:
        parts.append(m.group(0))
        return f"[[P{len(parts) - 1}]]"

    out = MARKUP_RE.sub(repl_markup, text)
    out = PAUSE_RE.sub(repl_pause, out)
    return out, parts


def restore_markup(text: str, parts: list[str]) -> str:
    out = text
    # restore longest tokens first
    for i in range(len(parts) - 1, -1, -1):
        tag = parts[i]
        for token in (f"[[M{i}]]", f"[[P{i}]]", f"«M{i}»", f"<<M{i}>>", f"M{i}", f"P{i}"):
            if token in out:
                out = out.replace(token, tag)
    return out


def scene_brief(group: dict) -> str:
    bits = ["HuniePop dating-sim dialogue"]
    if group.get("kind"):
        bits.append(f"scene_type={group['kind']}")
    if group.get("girl"):
        bits.append(f"character={group['girl']}")
    bits.append(f"asset={group.get('object_name')}")
    bits.append("Tone: casual Brazilian Portuguese (voce/voces), spoken, not formal EU-PT.")
    bits.append("Never use tu/vos conjugations or teu/tua/contigo; use voce/voces + 3rd-person verbs (voce esta, voce tem, com voce).")
    bits.append("Keep [[markup]] tags unchanged. Keep ····· pause dots.")
    return " | ".join(bits)


def translate_argos_block(lines_en: list[str], brief: str) -> list[str]:
    """Translate a small EN block with shared context via numbered list."""
    import argostranslate.translate as tr

    protected = []
    parts_list = []
    for en in lines_en:
        p, parts = protect_markup(en)
        protected.append(p)
        parts_list.append(parts)

    # One Argos call: brief + numbered EN lines (model sees neighbors)
    blob = brief + "\nTranslate each numbered line to Portuguese:\n"
    for i, p in enumerate(protected, 1):
        blob += f"{i}. {p}\n"
    try:
        out = tr.translate(blob, "en", "pt")
    except Exception as e:
        print(f"  block fail ({e}), falling back line-by-line", flush=True)
        return [
            restore_markup(tr.translate(p, "en", "pt"), parts)
            for p, parts in zip(protected, parts_list)
        ]

    # Parse "1. ..." lines; fallback if parse fails
    found: dict[int, str] = {}
    for m in re.finditer(r"(?m)^\s*(\d+)\.\s*(.+)$", out):
        found[int(m.group(1))] = m.group(2).strip()

    results = []
    for i, (p, parts) in enumerate(zip(protected, parts_list), 1):
        if i in found and found[i]:
            pt = found[i]
        else:
            try:
                pt = tr.translate(p, "en", "pt")
            except Exception:
                pt = ""
        results.append(restore_markup(pt, parts).strip())
    return results


def translate_echo_block(lines_en: list[str], brief: str) -> list[str]:
    return list(lines_en)


def chunked(xs: list, n: int):
    for i in range(0, len(xs), n):
        yield i, xs[i : i + n]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--groups", type=Path, default=GROUPS_JSON)
    ap.add_argument("--csv", type=Path, default=LOCALE_CSV)
    ap.add_argument("--backend", choices=("argos", "echo"), default="argos")
    ap.add_argument("--prefix", default="", help="Only groups whose name starts with this")
    ap.add_argument("--girl", default="", help="Only this girl (e.g. Aiko)")
    ap.add_argument("--chunk", type=int, default=6, help="Lines per Argos context block")
    ap.add_argument("--limit-groups", type=int, default=0)
    ap.add_argument(
        "--order",
        choices=("smallest", "largest"),
        default="smallest",
        help="Process short scenes first (default) or long ones first",
    )
    ap.add_argument(
        "--skip-prefix",
        action="append",
        default=[],
        help="Skip groups whose name starts with this (repeatable)",
    )
    ap.add_argument("--force", action="store_true", help="Overwrite existing pt_BR")
    ap.add_argument("--categories", nargs="*", default=["dialogue"])
    args = ap.parse_args()

    if not args.groups.exists():
        print("Run build_dialogue_groups.py first", file=sys.stderr)
        return 1

    groups = json.loads(args.groups.read_text(encoding="utf-8"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from locale_csv import read_locale_rows, write_locale_rows  # type: ignore

    rows, fields = read_locale_rows(args.csv)
    by_text = {r["text"]: r for r in rows}

    # Map EN text -> all group occurrences (for unique csv we translate once,
    # preferring the longest scene context that contains it)
    text_contexts: dict[str, list[tuple[str, int, list[str]]]] = defaultdict(list)
    selected = []
    for g in groups:
        name = g["object_name"]
        if args.prefix and not name.startswith(args.prefix):
            continue
        if args.girl and (g.get("girl") or "").lower() != args.girl.lower():
            continue
        selected.append(g)
        en_lines = [ln["text"] for ln in g["lines"]]
        for idx, en in enumerate(en_lines):
            # window: prev + current + next inside scene
            lo = max(0, idx - 1)
            hi = min(len(en_lines), idx + 2)
            text_contexts[en].append((name, idx, en_lines[lo:hi]))

    if args.skip_prefix:
        selected = [
            g
            for g in selected
            if not any(g["object_name"].startswith(p) for p in args.skip_prefix)
        ]

    if args.order == "smallest":
        selected.sort(key=lambda g: (g.get("n_lines", 0), g.get("object_name") or ""))
    else:
        selected.sort(key=lambda g: (-g.get("n_lines", 0), g.get("object_name") or ""))

    if args.limit_groups:
        selected = selected[: args.limit_groups]

    translate_block = translate_argos_block if args.backend == "argos" else translate_echo_block
    print(
        f"order={args.order} groups={len(selected)} "
        f"first={selected[0]['object_name'] if selected else '-'} "
        f"last={selected[-1]['object_name'] if selected else '-'}",
        flush=True,
    )

    updated = 0
    skipped = 0
    # Translate scene-by-scene so neighbors share a block
    done_texts: set[str] = set()
    for gi, g in enumerate(selected):
        brief = scene_brief(g)
        lines = g["lines"]
        en_list = [ln["text"] for ln in lines]
        print(f"[{gi+1}/{len(selected)}] {g['object_name']} ({len(en_list)} lines) {brief[:60]}...", flush=True)

        pt_list: list[str] = [""] * len(en_list)
        for start, chunk in chunked(list(enumerate(en_list)), args.chunk):
            idxs = [i for i, _ in chunk]
            ens = [t for _, t in chunk]
            # include one previous EN line as frozen context inside brief
            ctx_prev = en_list[idxs[0] - 1] if idxs[0] > 0 else ""
            block_brief = brief
            if ctx_prev:
                block_brief += f" | Previous line EN: {ctx_prev[:120]}"
            pts = translate_block(ens, block_brief)
            if len(pts) != len(ens):
                pts = (pts + [""] * len(ens))[: len(ens)]
            for i, pt in zip(idxs, pts):
                pt_list[i] = pt

        for en, pt in zip(en_list, pt_list):
            if not pt or en in done_texts:
                continue
            row = by_text.get(en)
            if not row:
                continue
            if row.get("category") not in args.categories:
                continue
            if (row.get("pt_BR") or "").strip() and not args.force:
                skipped += 1
                done_texts.add(en)
                continue
            row["pt_BR"] = pt
            done_texts.add(en)
            updated += 1

        if (gi + 1) % 5 == 0:
            write_locale_rows(args.csv, rows, fields)
            print(f"  checkpoint updated={updated}", flush=True)

    write_locale_rows(args.csv, rows, fields)

    print(f"done updated={updated} skipped_kept={skipped} groups={len(selected)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
