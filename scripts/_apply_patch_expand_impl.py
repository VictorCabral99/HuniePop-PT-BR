"""Expand-capable HuniePop patch: binary length-prefixed string rewrite.

Unity 4.2 black-screens if MonoBehaviour payloads are rewritten via
save_typetree (incomplete TypeTrees → "serialization layout" mismatches).

This patcher instead:
1. Finds Unity strings as `<u32 len><utf8><align4>` inside each object blob
2. Replaces EN→PT (size may change)
3. Repacks the data section; patches object table byte_start/byte_size
4. Keeps header+metadata structure intact (no SerializedFile.save)
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import struct
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import UnityPy

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = Path(r"C:/Program Files (x86)/Steam/steamapps/common/HuniePop")
DEFAULT_LOCALE = ROOT / "locale" / "pt-BR" / "unique_texts_ascii.csv"
DEFAULT_OUT = ROOT / "build" / "patch_expand"
ASSET_NAMES = ("resources.assets", "sharedassets0.assets")


def align4(n: int) -> int:
    return (4 - (n % 4)) % 4


def align8(n: int) -> int:
    return (n + 7) & ~7


def string_block(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack("<I", len(raw)) + raw + (b"\x00" * align4(len(raw)))


def load_translations(*csv_paths: Path) -> dict[str, str]:
    """Load EN->PT map, dropping entries that would corrupt assets."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from locale_csv import read_locale_rows  # type: ignore

    mapping: dict[str, str] = {}
    skipped = 0
    for path in csv_paths:
        rows, _ = read_locale_rows(path)
        for row in rows:
            en = (row.get("text") or "").strip("\ufeff")
            pt = (row.get("pt_BR") or "").strip()
            if not en or not pt or en == pt:
                continue
            if len(en) > 800:
                skipped += 1
                continue
            if len(en) >= 80 and len(pt) < max(20, int(len(en) * 0.35)):
                skipped += 1
                continue
            if en.count(",") >= 20 and len(en) > 200:
                skipped += 1
                continue
            # Too short → high false-positive risk in binary scan
            if len(en.encode("utf-8")) < 3:
                skipped += 1
                continue
            mapping[en] = pt
    if skipped:
        print(f"  Filtered out {skipped} unsafe translation entries", flush=True)
    return mapping


def build_needles(mapping: dict[str, str]) -> list[tuple[bytes, int, bytes]]:
    """(en_prefix+bytes, full_old_block_size, pt_block) longest-first."""
    items: list[tuple[bytes, int, bytes]] = []
    for en, pt in mapping.items():
        en_b = en.encode("utf-8")
        needle = struct.pack("<I", len(en_b)) + en_b
        old_size = 4 + len(en_b) + align4(len(en_b))
        items.append((needle, old_size, string_block(pt)))
    items.sort(key=lambda t: -len(t[0]))
    return items


def patch_payload(raw: bytes, needles: list[tuple[bytes, int, bytes]]) -> tuple[bytes, int]:
    """Replace length-prefixed strings inside one object payload."""
    if not raw or not needles:
        return raw, 0
    data = bytes(raw)
    matches: list[tuple[int, int, bytes]] = []
    for needle, old_size, pt_block in needles:
        start = 0
        while True:
            idx = data.find(needle, start)
            if idx < 0:
                break
            if idx + old_size > len(data):
                start = idx + 1
                continue
            matches.append((idx, old_size, pt_block))
            start = idx + len(needle)
    if not matches:
        return raw, 0
    matches.sort(key=lambda m: (m[0], -m[1]))
    chosen: list[tuple[int, int, bytes]] = []
    end = 0
    for idx, old_size, pt_block in matches:
        if idx < end:
            continue
        chosen.append((idx, old_size, pt_block))
        end = idx + old_size
    out = bytearray()
    pos = 0
    count = 0
    for idx, old_size, pt_block in chosen:
        out.extend(data[pos:idx])
        out.extend(pt_block)
        pos = idx + old_size
        count += 1
    out.extend(data[pos:])
    return bytes(out), count


@dataclass
class ObjMeta:
    path_id: int
    byte_start: int
    byte_size: int
    table_pos: int  # file offset of byte_start field (u32 relative)


def locate_object_table(data: bytes, objects_by_path: dict[int, tuple[int, int]]) -> list[ObjMeta]:
    """
    Find each object's byte_start field in metadata by searching for the
    relative offset u32 + size u32 pattern near the path_id.
    objects_by_path: path_id -> (byte_start_abs, byte_size)
    """
    _metadata_size, _file_size, _version, data_offset = struct.unpack_from(">IIII", data, 0)
    metas: list[ObjMeta] = []
    meta_region = data[20:data_offset]
    for path_id, (abs_start, size) in objects_by_path.items():
        rel = abs_start - data_offset
        pat = struct.pack("<iII", path_id, rel, size)
        idx = meta_region.find(pat)
        if idx < 0:
            pid = struct.pack("<i", path_id)
            start = 0
            found = None
            while True:
                j = meta_region.find(pid, start)
                if j < 0:
                    break
                if j + 12 <= len(meta_region):
                    rel_u, sz_u = struct.unpack_from("<II", meta_region, j + 4)
                    if rel_u == rel and sz_u == size:
                        found = j
                        break
                start = j + 1
            if found is None:
                continue
            idx = found
        table_pos = 20 + idx + 4
        metas.append(ObjMeta(path_id, abs_start, size, table_pos))
    return metas


def rebuild_asset(
    src: Path,
    dest: Path,
    mapping: dict[str, str],
) -> dict:
    print(f"Loading {src.name}...", flush=True)
    original = bytearray(src.read_bytes())
    env = UnityPy.load(str(src))
    sf = list(env.files.values())[0]
    data_offset = sf.header.data_offset

    objects_by_path = {
        oid: (obj.byte_start, obj.byte_size) for oid, obj in sf.objects.items()
    }
    print(f"  Locating object table ({len(objects_by_path)} objects)...", flush=True)
    metas = locate_object_table(bytes(original), objects_by_path)
    meta_by_id = {m.path_id: m for m in metas}
    print(f"  Located {len(meta_by_id)} / {len(objects_by_path)} table entries", flush=True)
    if len(meta_by_id) < len(objects_by_path) * 0.95:
        raise RuntimeError("Failed to locate enough object table entries; aborting")

    needles = build_needles(mapping)
    print(f"  Binary needles: {len(needles)}", flush=True)

    changed_objects = 0
    strings_replaced = 0
    new_payloads: dict[int, bytes] = {}

    for obj in sf.objects.values():
        raw = obj.get_raw_data()
        new_raw, n = patch_payload(raw, needles)
        if n:
            new_payloads[obj.path_id] = new_raw
            changed_objects += 1
            strings_replaced += n
        else:
            new_payloads[obj.path_id] = raw

    ordered = sorted(sf.objects.values(), key=lambda o: o.byte_start)
    data_blob = bytearray()
    new_abs_starts: dict[int, tuple[int, int]] = {}
    cursor = 0
    for obj in ordered:
        payload = new_payloads[obj.path_id]
        aligned = align8(cursor)
        if aligned != cursor:
            data_blob.extend(b"\x00" * (aligned - cursor))
            cursor = aligned
        abs_start = data_offset + cursor
        data_blob.extend(payload)
        cursor += len(payload)
        new_abs_starts[obj.path_id] = (abs_start, len(payload))

    new_file_size = data_offset + len(data_blob)
    out = bytearray(original[:data_offset]) + data_blob
    struct.pack_into(">I", out, 4, new_file_size)

    for path_id, (abs_start, size) in new_abs_starts.items():
        m = meta_by_id[path_id]
        rel = abs_start - data_offset
        struct.pack_into("<II", out, m.table_pos, rel, size)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(out)
    print(
        f"  changed_objects={changed_objects} strings={strings_replaced} "
        f"size {len(original)} -> {len(out)}",
        flush=True,
    )
    return {
        "file": src.name,
        "objects_changed": changed_objects,
        "strings_replaced": strings_replaced,
        "rejected": 0,
        "out_size": len(out),
        "table_located": len(meta_by_id),
        "mode": "binary_expand",
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
        "Backup dos .assets. Restaure copiando para HuniePop_Data.\n", encoding="utf-8"
    )
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Binary expand HuniePop PT-BR patch")
    ap.add_argument("--game", type=Path, default=DEFAULT_GAME)
    ap.add_argument("--locale", type=Path, action="append", default=None)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--assets", nargs="*", default=list(ASSET_NAMES))
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--backup-dir", type=Path, default=ROOT / "assets" / "original")
    ap.add_argument("--source", type=Path, default=None, help="HuniePop_Data or folder with .assets")
    args = ap.parse_args(argv)

    locale_files = list(args.locale) if args.locale else [DEFAULT_LOCALE]
    if args.pilot:
        locale_files.append(ROOT / "locale" / "pt-BR" / "pilot.csv")

    mapping = load_translations(*locale_files)
    if not mapping:
        print("No translations.", file=sys.stderr)
        return 1
    print(f"Mappings: {len(mapping)}", flush=True)

    src_dir = args.source or (args.game / "HuniePop_Data")
    if not (src_dir / "sharedassets0.assets").is_file() and (
        src_dir / "HuniePop_Data" / "sharedassets0.assets"
    ).is_file():
        src_dir = src_dir / "HuniePop_Data"

    args.out.mkdir(parents=True, exist_ok=True)
    reports = []
    for name in args.assets:
        src = src_dir / name
        if not src.is_file():
            alt = Path(args.source) / name if args.source else None
            if alt and alt.is_file():
                src = alt
            else:
                print(f"Missing {src}", file=sys.stderr)
                continue
        reports.append(rebuild_asset(src, args.out / name, mapping))

    summary = {
        "mode": "binary_expand",
        "mappings": len(mapping),
        "assets": reports,
        "total_strings_replaced": sum(r["strings_replaced"] for r in reports),
    }
    (args.out / "patch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

    if args.install:
        if summary["total_strings_replaced"] == 0:
            print("Nothing replaced.", file=sys.stderr)
            return 1
        backup_game_assets(args.game, args.backup_dir)
        for name in args.assets:
            p = args.out / name
            if p.is_file():
                shutil.copy2(p, args.game / "HuniePop_Data" / name)
                print(f"Installed {name}", flush=True)
        print("Install done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
