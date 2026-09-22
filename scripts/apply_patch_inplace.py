"""Safe in-place PT-BR patch for HuniePop Unity 4.2 assets.

UnityPy's full env.save() rewrites the SerializedFile and black-screens
Unity 4.2. This patcher only rewrites length-prefixed UTF-8 strings inside
the existing file bytes, keeping each string's aligned footprint identical
so object offsets stay valid.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import struct
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = Path(r"C:/Program Files (x86)/Steam/steamapps/common/HuniePop")
DEFAULT_LOCALE = ROOT / "locale" / "pt-BR" / "pilot.csv"
DEFAULT_OUT = ROOT / "build" / "patch_inplace"
ASSET_NAMES = ("resources.assets", "sharedassets0.assets")


def align4(n: int) -> int:
    return (4 - (n % 4)) % 4


def string_block_size(byte_len: int) -> int:
    """Size of Unity serialized string: int32 + bytes + align4."""
    return 4 + byte_len + align4(byte_len)


def load_translations(*csv_paths: Path) -> dict[str, str]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from locale_csv import read_locale_rows  # type: ignore

    mapping: dict[str, str] = {}
    for path in csv_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        rows, fields = read_locale_rows(path)
        if "text" not in fields or "pt_BR" not in fields:
            raise ValueError(f"{path}: need text,pt_BR columns")
        for row in rows:
            en = (row.get("text") or "").strip("\ufeff")
            pt = (row.get("pt_BR") or "").strip()
            if en and pt and en != pt:
                mapping[en] = pt
    return mapping


def try_build_replacement(en: str, pt: str) -> bytes | None:
    """Return replacement bytes (same length as original block) or None if unfit."""
    en_b = en.encode("utf-8")
    pt_b = pt.encode("utf-8")
    old_size = string_block_size(len(en_b))
    new_size = string_block_size(len(pt_b))
    if len(pt_b) > len(en_b):
        return None
    if new_size > old_size:
        return None
    # Shorter string OK if we pad the block to old_size with zeros after align
    block = struct.pack("<I", len(pt_b)) + pt_b + (b"\x00" * align4(len(pt_b)))
    if len(block) > old_size:
        return None
    if len(block) < old_size:
        block = block + (b"\x00" * (old_size - len(block)))
    assert len(block) == old_size
    return block


def patch_bytes(data: bytearray, mapping: dict[str, str]) -> dict:
    replaced = 0
    skipped_long: list[dict] = []
    missing: list[str] = []
    # Longest first to avoid partial overlaps
    items = sorted(mapping.items(), key=lambda kv: -len(kv[0].encode("utf-8")))
    for en, pt in items:
        en_b = en.encode("utf-8")
        needle = struct.pack("<I", len(en_b)) + en_b
        if needle not in data:
            # fallback: raw without verifying uniqueness
            if en_b not in data:
                missing.append(en)
            else:
                skipped_long.append({"text": en, "pt_BR": pt, "reason": "no_length_prefix"})
            continue
        repl = try_build_replacement(en, pt)
        if repl is None:
            skipped_long.append(
                {
                    "text": en,
                    "pt_BR": pt,
                    "en_bytes": len(en_b),
                    "pt_bytes": len(pt.encode("utf-8")),
                    "reason": "pt_too_long_for_inplace",
                }
            )
            continue
        count = 0
        start = 0
        while True:
            idx = data.find(needle, start)
            if idx < 0:
                break
            data[idx : idx + len(repl)] = repl
            count += 1
            replaced += 1
            start = idx + len(repl)
        if count == 0:
            missing.append(en)
    return {
        "strings_replaced": replaced,
        "skipped_long": skipped_long,
        "missing": missing,
    }


def backup_game_assets(game: Path, backup_root: Path) -> Path:
    data = game / "HuniePop_Data"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_root / f"backup_{stamp}"
    dest.mkdir(parents=True, exist_ok=False)
    for name in ASSET_NAMES:
        src = data / name
        if src.is_file():
            shutil.copy2(src, dest / name)
    (dest / "README.txt").write_text(
        "Backup dos .assets originais. Restaure copiando de volta para HuniePop_Data.\n",
        encoding="utf-8",
    )
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="In-place HuniePop PT-BR patch (Unity 4.2 safe)")
    ap.add_argument("--game", type=Path, default=DEFAULT_GAME)
    ap.add_argument("--locale", type=Path, action="append", default=None)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--assets", nargs="*", default=list(ASSET_NAMES))
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--backup-dir", type=Path, default=ROOT / "assets" / "original")
    ap.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Read assets from this HuniePop_Data (default: game). Use backup to avoid re-patching.",
    )
    ap.add_argument(
        "--force-mass",
        action="store_true",
        help="Allow unique_texts_fitted.csv (UNSAFE — hung HuniePop before)",
    )
    args = ap.parse_args(argv)

    locale_files: list[Path] = list(args.locale) if args.locale else [DEFAULT_LOCALE]
    if args.pilot:
        locale_files.append(ROOT / "locale" / "pt-BR" / "pilot.csv")

    for lf in locale_files:
        name = lf.name.lower()
        allowed = {"pilot.csv", "menus_only.csv"}
        allowed = {"pilot.csv", "menus_only.csv"}
        risky = name not in allowed
        if risky and not args.force_mass:
            print(
                f"REFUSING {lf.name}: mass in-place hung HuniePop (Not Responding).\n"
                "Safe default is pilot.csv. Override with --force-mass only for debugging.",
                file=sys.stderr,
            )
            return 2

    mapping = load_translations(*locale_files)
    if not mapping:
        print("No translations.", file=sys.stderr)
        return 1
    # Drop entries that cannot fit (avoids multi-GB scan waste)
    mapping = {en: pt for en, pt in mapping.items() if try_build_replacement(en, pt) is not None}
    print(f"Fitting mappings: {len(mapping)}", flush=True)
    if not mapping:
        print("No translations fit in-place byte budget.", file=sys.stderr)
        return 1

    src_data = (args.source or (args.game / "HuniePop_Data")).resolve()
    if not src_data.is_dir():
        print(f"Missing {src_data}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    for name in args.assets:
        src = src_data / name
        if not src.is_file():
            print(f"Missing {src}", file=sys.stderr)
            continue
        print(f"Patching {name} ({src.stat().st_size} bytes)...", flush=True)
        buf = bytearray(src.read_bytes())
        result = patch_bytes(buf, mapping)
        dest = args.out / name
        dest.write_bytes(buf)
        report = {"file": name, "out_size": len(buf), **result}
        reports.append(report)
        print(
            f"  replaced={result['strings_replaced']} "
            f"skipped_long={len(result['skipped_long'])} "
            f"missing={len(result['missing'])}",
            flush=True,
        )
        for s in result["skipped_long"][:8]:
            msg = (
                f"  SKIP long: {s['text']!r} -> {s['pt_BR']!r} "
                f"({s.get('pt_bytes')} > {s.get('en_bytes')} bytes)\n"
            )
            sys.stdout.buffer.write(msg.encode("utf-8", errors="replace"))
        if len(result["skipped_long"]) > 8:
            print(f"  ... +{len(result['skipped_long']) - 8} more skipped", flush=True)

    summary = {
        "mode": "inplace",
        "mappings": len(mapping),
        "locale_files": [str(p) for p in locale_files],
        "assets": reports,
        "total_strings_replaced": sum(r["strings_replaced"] for r in reports),
    }
    (args.out / "patch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

    if summary["total_strings_replaced"] == 0:
        print("Nothing replaced — not installing.", file=sys.stderr)
        return 1

    if args.install:
        backup_game_assets(args.game, args.backup_dir)
        game_data = args.game / "HuniePop_Data"
        for name in args.assets:
            src = args.out / name
            if src.is_file():
                shutil.copy2(src, game_data / name)
                print(f"Installed {name}", flush=True)
        print("Install done. Launch HuniePop to QA.", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
