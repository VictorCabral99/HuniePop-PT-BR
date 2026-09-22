"""Extract UI Texture2D atlases + crop loadscreen/title text sprites (tk2d).

HuniePop title/save buttons are baked word-sprites in atlases, not MonoBehaviour
strings. Fonts (Exo*) are ASCII-only (127 glyphs) — accents need atlas work later.

Usage:
  python scripts/extract_ui_images.py
  python scripts/extract_ui_images.py --assets path/to/sharedassets0.assets
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import UnityPy
from PIL import Image
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = Path(r"C:/Program Files (x86)/Steam/steamapps/common/HuniePop")
DEFAULT_ASSETS = (
    ROOT / "assets" / "original" / "backup_20260921_151112" / "sharedassets0.assets"
)
OUT_TEX = ROOT / "export" / "ui_images"
OUT_SPR = ROOT / "export" / "ui_sprites"

# Word-sprites that still show English on title / save UI
TEXT_SPRITE_PREFIXES = (
    "loadscreen_button_",
    "loadscreen_nodata",
    "loadscreen_data_",
    "loadscreen_screen_prompts",
    "loadscreen_settings_close",
    "ui_transition_screen_gamesaved",
    "titlescreen_prompt",
)


def safe_name(name: str, limit: int = 80) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:limit]


def crop_from_uvs(img: Image.Image, uvs: list, flipped: int) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Crop sprite from atlas using tk2d UVs (y=0 at bottom). flipped=1 => packed rotated."""
    xs = [u["x"] for u in uvs]
    ys = [u["y"] for u in uvs]
    w, h = img.size
    x0 = int(math.floor(min(xs) * w))
    x1 = int(math.ceil(max(xs) * w))
    y_bot = min(ys) * h
    y_top = max(ys) * h
    py0 = int(math.floor(h - y_top))
    py1 = int(math.ceil(h - y_bot))
    x0, py0 = max(0, x0), max(0, py0)
    x1, py1 = min(w, x1), min(h, py1)
    crop = img.crop((x0, py0, x1, py1))
    # tk2d FlipMode Tk2d (=1): atlas stores sprite rotated; TRANSVERSE restores view
    if flipped == 1:
        crop = crop.transpose(Image.TRANSVERSE)
    return crop, (x0, py0, x1, py1)


def is_text_sprite(name: str) -> bool:
    if name.startswith("loadscreen_"):
        return True
    return any(name.startswith(p) or p in name for p in TEXT_SPRITE_PREFIXES)


def export_textures(env, out: Path) -> dict[int, tuple[str, int, int, Image.Image]]:
    out.mkdir(parents=True, exist_ok=True)
    tex_imgs: dict[int, tuple[str, int, int, Image.Image]] = {}
    n = 0
    for obj in env.objects:
        if obj.type.name != "Texture2D":
            continue
        tex = obj.read()
        name = getattr(tex, "m_Name", None) or f"tex_{obj.path_id}"
        try:
            img = tex.image
        except Exception as e:
            print(f"image fail {name}: {e}", file=sys.stderr)
            continue
        if img is None:
            continue
        dest = out / f"{safe_name(str(name))}__{obj.path_id}.png"
        img.save(dest)
        tex_imgs[obj.path_id] = (str(name), tex.m_Width, tex.m_Height, img)
        n += 1
        print(f"tex {dest.name} {img.size}")
    print(f"exported textures: {n}")
    return tex_imgs


def export_text_sprites(env, tex_imgs: dict, out: Path) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict):
            continue
        defs = tree.get("spriteDefinitions")
        if not isinstance(defs, list):
            continue
        textures = tree.get("textures") or []
        if not textures:
            continue
        tex_pid = textures[0].get("m_PathID")
        if tex_pid not in tex_imgs:
            continue
        tname, tw, th, img = tex_imgs[tex_pid]
        coll = tree.get("spriteCollectionName") or tree.get("m_Name") or f"coll_{obj.path_id}"

        for d in defs:
            if not isinstance(d, dict):
                continue
            name = d.get("name") or ""
            if not is_text_sprite(name):
                continue
            uvs = d.get("uvs")
            if not uvs or len(uvs) < 4:
                continue
            flipped = int(d.get("flipped") or 0)
            crop, box = crop_from_uvs(img, uvs, flipped)
            dest = out / f"{safe_name(name)}.png"
            crop.save(dest)
            entry = {
                "name": name,
                "collection": coll,
                "collection_pid": obj.path_id,
                "texture_pid": tex_pid,
                "texture_name": tname,
                "texture_size": [tw, th],
                "flipped": flipped,
                "uvs": uvs,
                "crop_box_pil": list(box),
                "crop_size": list(crop.size),
                "file": dest.as_posix(),
            }
            manifest.append(entry)
            print(f"sprite {name} {crop.size} <- {tname} flipped={flipped}")

    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"exported text sprites: {len(manifest)}")
    return manifest


def export_font_index(env, out: Path) -> None:
    """Dump tk2d font glyph counts / coverage (ASCII 127 = no PT accents)."""
    out.mkdir(parents=True, exist_ok=True)
    fonts = []
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if not isinstance(tree, dict):
            continue
        if "chars" not in tree or "lineHeight" not in tree:
            continue
        chars = tree.get("chars") or []
        fonts.append(
            {
                "path_id": obj.path_id,
                "m_Name": tree.get("m_Name") or "",
                "n_chars": len(chars),
                "lineHeight": tree.get("lineHeight"),
                "char_keys": list(chars[0].keys()) if chars and isinstance(chars[0], dict) else [],
                "spriteCollection": tree.get("spriteCollection"),
                "has_latin1": len(chars) > 127,
            }
        )
    dest = out / "fonts_index.json"
    dest.write_text(json.dumps(fonts, indent=2, default=str), encoding="utf-8")
    print(f"font index: {len(fonts)} -> {dest}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", type=Path, default=DEFAULT_GAME)
    ap.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    args = ap.parse_args()

    if not args.assets.exists():
        alt = args.game / "HuniePop_Data" / "sharedassets0.assets"
        if alt.exists():
            args.assets = alt
        else:
            print(f"assets not found: {args.assets}", file=sys.stderr)
            return 1

    print(f"loading {args.assets} ...")
    gen = TypeTreeGenerator("4.2.2f1")
    gen.load_local_game(str(args.game))
    env = UnityPy.load(str(args.assets))
    env.typetree_generator = gen

    tex_imgs = export_textures(env, OUT_TEX)
    export_text_sprites(env, tex_imgs, OUT_SPR)
    export_font_index(env, OUT_SPR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
