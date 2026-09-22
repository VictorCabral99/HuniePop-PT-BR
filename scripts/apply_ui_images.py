"""Paste PT-BR UI sprites back into atlas Texture2D and rebuild sharedassets0.

Uses same-size image payloads + expand-style object table rewrite (Unity 4 safe).
Texture2D.save()/get_raw_data() is a no-op on Unity 4 here — we splice encoded
pixels into the object raw (ARGB32 stays ARGB32 with Y-flip + channel order).

Prereq:
  python scripts/extract_ui_images.py
  python scripts/generate_ui_pt.py

Usage:
  python scripts/apply_ui_images.py
  python scripts/apply_ui_images.py --install
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import UnityPy
from PIL import Image
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = Path(r"C:/Program Files (x86)/Steam/steamapps/common/HuniePop")
DEFAULT_ASSETS = ROOT / "build" / "patch_expand" / "sharedassets0.assets"
FALLBACK_ASSETS = (
    ROOT / "assets" / "original" / "backup_20260921_151112" / "sharedassets0.assets"
)
SPR_DIR = ROOT / "export" / "ui_sprites"
PT_DIR = SPR_DIR / "pt"
OUT_DIR = ROOT / "build" / "patch_ui"


def align8(n: int) -> int:
    return (n + 7) & ~7


def locate_object_table(data: bytes, objects_by_path: dict[int, tuple[int, int]]):
    # Same locator as expand patch (keeps Unity 4 metadata intact)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _apply_patch_expand_impl import locate_object_table as _loc  # type: ignore

    return _loc(data, objects_by_path)


def to_atlas_orientation(img: Image.Image, flipped: int) -> Image.Image:
    """Inverse of extract crop: view-space -> atlas packing orientation."""
    if flipped == 1:
        # extract used TRANSVERSE; inverse of TRANSVERSE is TRANSVERSE
        return img.transpose(Image.TRANSVERSE)
    return img


def encode_texture_pixels(img: Image.Image, texture_format: int) -> bytes:
    """PIL top-down RGBA -> Unity Texture2D image_data bytes for format.

    Unity stores bottom-up. ARGB32=5, RGBA32=4 (UnityPy TextureFormat).
    """
    rgba = np.asarray(img.convert("RGBA"), dtype=np.uint8)
    bottom = np.flipud(rgba)
    fmt = int(texture_format)
    if fmt == 5:  # ARGB32
        return bottom[:, :, [3, 0, 1, 2]].tobytes()
    if fmt == 4:  # RGBA32
        return bottom.tobytes()
    raise ValueError(f"unsupported TextureFormat {fmt}")


def paste_sprites(atlas: Image.Image, entries: list[dict], pt_dir: Path) -> tuple[Image.Image, int]:
    """Paste PT sprites into atlas. Returns (modified_atlas, count)."""
    atlas = atlas.convert("RGBA").copy()
    n = 0
    for e in entries:
        name = e["name"]
        pt_path = pt_dir / f"{name}.png"
        if not pt_path.exists():
            continue
        if e["texture_pid"] is None:
            continue
        spr = Image.open(pt_path).convert("RGBA")
        flipped = int(e.get("flipped") or 0)
        packed = to_atlas_orientation(spr, flipped)
        box = tuple(e["crop_box_pil"])
        x0, y0, x1, y1 = box
        region_w, region_h = x1 - x0, y1 - y0
        if packed.size != (region_w, region_h):
            if packed.size == (region_h, region_w) and flipped == 1:
                packed = spr.transpose(Image.TRANSVERSE)
            if packed.size != (region_w, region_h):
                print(
                    f"  skip {name}: pt {spr.size} packed {packed.size} != region {(region_w, region_h)}",
                    flush=True,
                )
                continue
        atlas.paste(packed, (x0, y0), packed)
        n += 1
        print(f"  pasted {name} @ {box}", flush=True)
    return atlas, n


def rebuild_with_textures(
    src: Path,
    dest: Path,
    game: Path,
    pt_dir: Path,
    manifest: list[dict],
) -> dict:
    print(f"Loading {src.name}...", flush=True)
    original = bytearray(src.read_bytes())
    gen = TypeTreeGenerator("4.2.2f1")
    gen.load_local_game(str(game))
    env = UnityPy.load(str(src))
    env.typetree_generator = gen
    sf = list(env.files.values())[0]
    data_offset = sf.header.data_offset

    # Group sprites by texture path_id
    by_tex: dict[int, list[dict]] = {}
    for e in manifest:
        pt = pt_dir / f"{e['name']}.png"
        if pt.exists():
            by_tex.setdefault(e["texture_pid"], []).append(e)

    objects_by_path = {
        oid: (obj.byte_start, obj.byte_size) for oid, obj in sf.objects.items()
    }
    metas = locate_object_table(bytes(original), objects_by_path)
    meta_by_id = {m.path_id: m for m in metas}
    if len(meta_by_id) < len(objects_by_path) * 0.95:
        raise RuntimeError("object table locate failed")

    new_payloads: dict[int, bytes] = {}
    tex_changed = 0
    sprites_pasted = 0

    for obj in sf.objects.values():
        raw = obj.get_raw_data()
        if obj.type.name != "Texture2D" or obj.path_id not in by_tex:
            new_payloads[obj.path_id] = raw
            continue
        tex = obj.read()
        try:
            img = tex.image
        except Exception as e:
            print(f"  read image fail {obj.path_id}: {e}", flush=True)
            new_payloads[obj.path_id] = raw
            continue
        if img is None:
            new_payloads[obj.path_id] = raw
            continue
        img, n = paste_sprites(img, by_tex[obj.path_id], pt_dir)
        if not n:
            new_payloads[obj.path_id] = raw
            continue
        sprites_pasted += n
        old_img = bytes(tex.image_data or b"")
        fmt = int(tex.m_TextureFormat)
        try:
            new_img = encode_texture_pixels(img, fmt)
        except ValueError as e:
            print(f"  reject tex {obj.path_id}: {e}", flush=True)
            new_payloads[obj.path_id] = raw
            continue
        if (
            not old_img
            or len(new_img) != len(old_img)
            or len(new_img) != int(tex.m_CompleteImageSize)
        ):
            print(
                f"  reject tex {obj.path_id}: image_data len "
                f"old={len(old_img)} new={len(new_img)} complete={tex.m_CompleteImageSize}",
                flush=True,
            )
            new_payloads[obj.path_id] = raw
            continue
        # UnityPy Texture2D.save() does NOT refresh get_raw_data() on Unity 4 —
        # splice encoded pixels into the object payload (keep header/format).
        if raw[-len(old_img) :] == old_img:
            new_raw = raw[: -len(old_img)] + new_img
        else:
            pos = raw.find(old_img[:4096])
            if pos < 0 or raw[pos : pos + len(old_img)] != old_img:
                print(f"  reject tex {obj.path_id}: cannot locate image_data in raw", flush=True)
                new_payloads[obj.path_id] = raw
                continue
            new_raw = raw[:pos] + new_img + raw[pos + len(old_img) :]
        if len(new_raw) != len(raw):
            print(
                f"  reject tex {obj.path_id}: raw size {len(raw)} -> {len(new_raw)}",
                flush=True,
            )
            new_payloads[obj.path_id] = raw
            continue
        new_payloads[obj.path_id] = new_raw
        tex_changed += 1
        delta = sum(1 for a, b in zip(old_img, new_img) if a != b)
        print(
            f"  texture {tex.m_Name} pid={obj.path_id} sprites={n} "
            f"fmt={fmt} img_delta={delta}",
            flush=True,
        )

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
        f"  textures={tex_changed} sprites={sprites_pasted} size {len(original)} -> {len(out)}",
        flush=True,
    )
    return {
        "textures_changed": tex_changed,
        "sprites_pasted": sprites_pasted,
        "out_size": len(out),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", type=Path, default=DEFAULT_GAME)
    ap.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--install", action="store_true")
    args = ap.parse_args()

    man_path = SPR_DIR / "manifest.json"
    if not man_path.exists() or not PT_DIR.exists():
        print("Need extract_ui_images.py + generate_ui_pt.py first", file=sys.stderr)
        return 1

    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    src = args.assets
    if not src.exists():
        src = FALLBACK_ASSETS
    if not src.exists():
        src = args.game / "HuniePop_Data" / "sharedassets0.assets"

    dest = args.out / "sharedassets0.assets"
    stats = rebuild_with_textures(src, dest, args.game, PT_DIR, manifest)
    print(json.dumps(stats, indent=2))

    if args.install:
        game_asset = args.game / "HuniePop_Data" / "sharedassets0.assets"
        backup = (
            ROOT
            / "assets"
            / "original"
            / f"backup_ui_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(game_asset, backup / "sharedassets0.assets")
        shutil.copy2(dest, game_asset)
        print(f"installed -> {game_asset} (backup {backup})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
