"""Apply PT-BR translations onto HuniePop Unity assets (text only).

Reads locale CSV (EN -> pt_BR), rewrites MonoBehaviour strings in
resources.assets / sharedassets0.assets, writes patched copies, and can
install into the game folder with an automatic backup.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = Path(r"C:/Program Files (x86)/Steam/steamapps/common/HuniePop")
DEFAULT_LOCALE = ROOT / "locale" / "pt-BR" / "unique_texts.csv"
DEFAULT_OUT = ROOT / "build" / "patch"
ASSET_NAMES = ("resources.assets", "sharedassets0.assets")


def load_translations(*csv_paths: Path) -> dict[str, str]:
    """Map exact English text -> pt_BR (later files override earlier)."""
    mapping: dict[str, str] = {}
    for path in csv_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "text" not in reader.fieldnames:
                raise ValueError(f"{path}: missing 'text' column")
            pt_col = "pt_BR" if "pt_BR" in reader.fieldnames else None
            if pt_col is None:
                raise ValueError(f"{path}: missing 'pt_BR' column")
            for row in reader:
                en = (row.get("text") or "").strip("\ufeff")
                pt = (row.get(pt_col) or "").strip()
                if not en or not pt:
                    continue
                if en == pt:
                    continue
                mapping[en] = pt
    return mapping


def replace_in_tree(obj, mapping: dict[str, str]) -> int:
    count = 0
    if isinstance(obj, dict):
        for key, value in list(obj.items()):
            if isinstance(value, str) and value in mapping:
                obj[key] = mapping[value]
                count += 1
            else:
                count += replace_in_tree(value, mapping)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            if isinstance(value, str) and value in mapping:
                obj[i] = mapping[value]
                count += 1
            else:
                count += replace_in_tree(value, mapping)
    return count


def patch_asset(
    src: Path,
    dest: Path,
    generator: TypeTreeGenerator,
    mapping: dict[str, str],
) -> dict:
    print(f"Loading {src.name}...", flush=True)
    # Load from a temp working copy path via UnityPy; we save to dest dir
    env = UnityPy.load(str(src))
    env.typetree_generator = generator

    objects_changed = 0
    strings_replaced = 0
    mono_ok = mono_err = 0

    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
            mono_ok += 1
        except Exception:
            mono_err += 1
            continue
        if not isinstance(tree, dict):
            continue
        n = replace_in_tree(tree, mapping)
        if n:
            obj.save_typetree(tree)
            objects_changed += 1
            strings_replaced += n

    dest.parent.mkdir(parents=True, exist_ok=True)
    out_dir = dest.parent
    print(
        f"  MonoBehaviour ok={mono_ok} err={mono_err} "
        f"objects_changed={objects_changed} strings={strings_replaced}",
        flush=True,
    )
    if strings_replaced == 0:
        # UnityPy env.save skips unchanged files — copy original so patch set is complete
        print(f"  No changes; copying original -> {dest}", flush=True)
        shutil.copy2(src, dest)
    else:
        print(f"  Saving -> {dest} ...", flush=True)
        env.save(pack="none", out_path=str(out_dir))
        written = out_dir / src.name
        if not written.is_file():
            raise RuntimeError(f"UnityPy did not write {written}")
        if written.resolve() != dest.resolve():
            if dest.exists():
                dest.unlink()
            written.replace(dest)
    return {
        "file": src.name,
        "mono_ok": mono_ok,
        "mono_err": mono_err,
        "objects_changed": objects_changed,
        "strings_replaced": strings_replaced,
        "out": str(dest),
        "out_size": dest.stat().st_size if dest.is_file() else 0,
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
            print(f"Backup: {name} -> {dest / name}", flush=True)
    (dest / "README.txt").write_text(
        "Backup automatico dos .assets originais do HuniePop.\n"
        "Para restaurar, copie estes arquivos de volta para HuniePop_Data.\n",
        encoding="utf-8",
    )
    return dest


def install_patch(patch_dir: Path, game: Path) -> None:
    data = game / "HuniePop_Data"
    for name in ASSET_NAMES:
        src = patch_dir / name
        if not src.is_file():
            print(f"Skip install (missing in patch): {name}", flush=True)
            continue
        dest = data / name
        shutil.copy2(src, dest)
        print(f"Installed: {src.name} -> {dest}", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Apply HuniePop PT-BR text patch")
    ap.add_argument("--game", type=Path, default=DEFAULT_GAME)
    ap.add_argument(
        "--locale",
        type=Path,
        action="append",
        default=None,
        help="CSV with text,pt_BR columns (repeatable). Default: unique_texts.csv",
    )
    ap.add_argument("--pilot", action="store_true", help="Also include locale/pt-BR/pilot.csv")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Directory for patched assets")
    ap.add_argument(
        "--assets",
        nargs="*",
        default=list(ASSET_NAMES),
        help="Asset filenames under HuniePop_Data",
    )
    ap.add_argument(
        "--install",
        action="store_true",
        help="After build, backup originals and copy patch into the game folder",
    )
    ap.add_argument(
        "--backup-dir",
        type=Path,
        default=ROOT / "assets" / "original",
        help="Where to store backups when --install is used",
    )
    args = ap.parse_args(argv)

    locale_files: list[Path] = list(args.locale) if args.locale else [DEFAULT_LOCALE]
    if args.pilot:
        locale_files.append(ROOT / "locale" / "pt-BR" / "pilot.csv")

    data_dir = args.game / "HuniePop_Data"
    if not data_dir.is_dir():
        print(f"Game data not found: {data_dir}", file=sys.stderr)
        return 1

    print("Loading translations...", flush=True)
    mapping = load_translations(*locale_files)
    if not mapping:
        print("No pt_BR entries found — nothing to patch.", file=sys.stderr)
        return 1
    print(f"  {len(mapping)} unique EN->PT mappings from {[p.name for p in locale_files]}", flush=True)

    print("Building TypeTree from Managed DLLs...", flush=True)
    gen = TypeTreeGenerator("4.2.2f1")
    gen.load_local_game(str(args.game))

    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    for name in args.assets:
        src = data_dir / name
        if not src.is_file():
            print(f"Missing {src}", file=sys.stderr)
            continue
        dest = args.out / name
        reports.append(patch_asset(src, dest, gen, mapping))

    summary = {
        "mappings": len(mapping),
        "locale_files": [str(p) for p in locale_files],
        "assets": reports,
        "total_strings_replaced": sum(r["strings_replaced"] for r in reports),
        "total_objects_changed": sum(r["objects_changed"] for r in reports),
    }
    summary_path = args.out / "patch_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print(f"Wrote {summary_path}", flush=True)

    if args.install:
        if summary["total_strings_replaced"] == 0:
            print("Refusing --install: zero strings replaced.", file=sys.stderr)
            return 1
        backup_game_assets(args.game, args.backup_dir)
        install_patch(args.out, args.game)
        print("Install done. Launch HuniePop to QA.", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
