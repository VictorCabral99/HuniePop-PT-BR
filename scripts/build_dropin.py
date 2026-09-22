"""Build a copy-paste drop-in folder mirroring the HuniePop install layout.

Output:
  dist/HuniePop_PT-BR/
    LEIA-ME.txt
    VERSION
    HuniePop_Data/
      sharedassets0.assets
      resources.assets

End users merge HuniePop_Data into their Steam game folder.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATCH = ROOT / "build" / "patch_expand"
DEFAULT_OUT = ROOT / "dist" / "HuniePop_PT-BR"
README_SRC = ROOT / "packaging" / "dropin" / "LEIA-ME.txt"
VERSION_FILE = ROOT / "VERSION"
ASSET_NAMES = ("resources.assets", "sharedassets0.assets")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build HuniePop PT-BR drop-in package")
    ap.add_argument("--patch-dir", type=Path, default=DEFAULT_PATCH)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--include-unchanged",
        action="store_true",
        help="Also copy assets with 0 string replacements (larger package)",
    )
    ap.add_argument(
        "--zip",
        action="store_true",
        help="Also write dist/HuniePop_PT-BR-<version>.zip",
    )
    args = ap.parse_args(argv)

    version = "0.0.0"
    if VERSION_FILE.is_file():
        version = VERSION_FILE.read_text(encoding="utf-8").strip() or version

    summary_path = args.patch_dir / "patch_summary.json"
    if not summary_path.is_file():
        print(f"Missing {summary_path}. Run apply_patch_expand.py first.", file=sys.stderr)
        return 1

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    by_name = {a["file"]: a for a in summary.get("assets", [])}

    if args.out.exists():
        shutil.rmtree(args.out)
    data_out = args.out / "HuniePop_Data"
    data_out.mkdir(parents=True)

    copied = []
    for name in ASSET_NAMES:
        src = args.patch_dir / name
        info = by_name.get(name, {})
        replaced = int(info.get("strings_replaced", 0))
        if not src.is_file():
            print(f"Skip missing: {src}", flush=True)
            continue
        if replaced == 0 and not args.include_unchanged:
            print(f"Skip unchanged: {name}", flush=True)
            continue
        dest = data_out / name
        print(f"Copy {name} ({src.stat().st_size} bytes, strings={replaced})...", flush=True)
        shutil.copy2(src, dest)
        copied.append(
            {"file": name, "strings_replaced": replaced, "size": dest.stat().st_size}
        )

    if not copied:
        print("Nothing to package — no patched assets.", file=sys.stderr)
        return 1

    if README_SRC.is_file():
        shutil.copy2(README_SRC, args.out / "LEIA-ME.txt")
    else:
        (args.out / "LEIA-ME.txt").write_text(
            "Copie a pasta HuniePop_Data para dentro da pasta do HuniePop na Steam.\n",
            encoding="utf-8",
        )
    (args.out / "VERSION").write_text(version + "\n", encoding="utf-8")

    meta = {
        "package": "HuniePop_PT-BR",
        "version": version,
        "channel": "alpha",
        "install": "Merge HuniePop_Data into the Steam HuniePop folder",
        "files": copied,
        "source_summary": summary_path.name,
        "mappings": summary.get("mappings"),
        "strings_replaced": summary.get("total_strings_replaced"),
    }
    (args.out / "package.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total = sum(f["size"] for f in copied)
    print(f"Drop-in ready: {args.out} (v{version})", flush=True)
    print(f"  files={len(copied)} size_mb={total / (1024 * 1024):.1f}", flush=True)

    if args.zip:
        zip_path = ROOT / "dist" / f"HuniePop_PT-BR-{version}.zip"
        if zip_path.exists():
            zip_path.unlink()
        print(f"Zipping -> {zip_path} ...", flush=True)
        # Don't use Path.with_suffix — breaks versions like 0.0.1 (.1 -> .zip)
        archive_base = ROOT / "dist" / f"HuniePop_PT-BR-{version}"
        shutil.make_archive(
            str(archive_base), "zip", root_dir=args.out.parent, base_dir=args.out.name
        )
        print(f"  zip size_mb={zip_path.stat().st_size / (1024 * 1024):.1f}", flush=True)

    print("  User action: copy HuniePop_Data into the game folder (merge/replace).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
