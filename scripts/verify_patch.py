"""Verify that expected PT-BR strings exist in patched asset bytes."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATCH = ROOT / "build" / "patch_inplace"
ASSET_NAMES = ("resources.assets", "sharedassets0.assets")


def load_expected(csv_paths: list[Path]) -> list[str]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from locale_csv import read_locale_rows  # type: ignore

    out: list[str] = []
    for path in csv_paths:
        rows, _ = read_locale_rows(path)
        for row in rows:
            pt = (row.get("pt_BR") or "").strip()
            en = (row.get("text") or "").strip()
            if pt and pt != en:
                out.append(pt)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch-dir", type=Path, default=DEFAULT_PATCH)
    ap.add_argument("--locale", type=Path, action="append", default=None)
    ap.add_argument("--pilot", action="store_true")
    args = ap.parse_args(argv)

    locales = list(args.locale) if args.locale else [ROOT / "locale" / "pt-BR" / "unique_texts.csv"]
    if args.pilot:
        locales.append(ROOT / "locale" / "pt-BR" / "pilot.csv")

    expected = load_expected(locales)
    if not expected:
        print("No pt_BR strings to verify.", file=sys.stderr)
        return 1

    blobs: list[bytes] = []
    for name in ASSET_NAMES:
        path = args.patch_dir / name
        if path.is_file():
            print(f"Reading {path}...", flush=True)
            blobs.append(path.read_bytes())
    if not blobs:
        print(f"No assets in {args.patch_dir}", file=sys.stderr)
        return 1

    ok = missing = 0
    for pt in expected:
        raw = pt.encode("utf-8")
        found = any(raw in b for b in blobs)
        if found:
            ok += 1
        else:
            missing += 1
            print(f"MISSING: {pt!r}")
    print(f"ok={ok} missing={missing} total={len(expected)}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
