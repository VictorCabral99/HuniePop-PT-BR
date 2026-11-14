"""Generate PT-BR replacements for the baked-text UI sprites.

The title/save/load UI draws some labels as word-sprites baked into tk2d
atlases.  This script keeps each original plate, icon, shadow and alpha channel
and repaints only the glyph area:

  * the EN glyph pixels are removed by row-wise inpainting (gradients survive,
    icons such as X / heart / gear / save disk are left untouched);
  * the ink / outline colors are sampled from the original glyphs;
  * the PT text is re-rendered with the game's own typeface (Exo, SIL OFL) at
    the original cap height, condensed when the translation is longer.

Output: export/ui_sprites/pt/<name>.png (same pixel size, RGBA), consumed by
scripts/apply_ui_images.py.

Usage:
  python scripts/generate_ui_pt.py
  python scripts/generate_ui_pt.py --preview
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "export" / "ui_sprites"
OUT = SRC / "pt"
PREVIEW = ROOT / "export" / "ui_pt_preview"
FONT_PATH = ROOT / "assets" / "fonts" / "Exo-Variable.ttf"


@dataclass
class Target:
    name: str
    label: str
    kind: str  # button | close | title | nodata | saved
    weight: str = "Black"
    text_x0: int | None = None  # glyph area starts after the baked icon
    anchor: str = "left"
    desc: bool = False  # EN label has a descender
    cap: int | None = None  # cap-height override
    stroke: int | None = None  # outline width override
    box: tuple[int, int, int, int] | None = None
    avail_end: int | None = None  # stop before a baked icon on the right


TARGETS: list[Target] = []


def _btn(name: str, label: str, width: int, text_x0: int | None, desc: bool = False,
         anchor: str = "left", weight: str = "Black") -> None:
    TARGETS.append(Target(name, label, "button", weight=weight, text_x0=text_x0,
                          anchor=anchor, desc=desc, box=(16, 8, width - 14, 44)))


# 170px buttons (icon + label)
_btn("loadscreen_button_cancel", "Cancelar", 170, 64)
_btn("loadscreen_button_cancel_over", "Cancelar", 170, 64)
_btn("loadscreen_button_credits", "Créditos", 170, 62)
_btn("loadscreen_button_credits_over", "Créditos", 170, 62)
_btn("loadscreen_button_erase", "Apagar", 170, 71)
_btn("loadscreen_button_erase_over", "Apagar", 170, 71)
_btn("loadscreen_button_gallery", "Galeria", 170, 62, desc=True)
_btn("loadscreen_button_gallery_over", "Galeria", 170, 62, desc=True)
_btn("loadscreen_button_settings", "Opções", 170, 54, desc=True)
_btn("loadscreen_button_settings_over", "Opções", 170, 54, desc=True)
# 334px buttons
_btn("loadscreen_button_continuegame", "Continuar", 334, 86)
_btn("loadscreen_button_continuegame_over", "Continuar", 334, 86)
_btn("loadscreen_button_erasegame", "Apagar jogo", 334, 102)
_btn("loadscreen_button_erasegame_over", "Apagar jogo", 334, 102)
for _t in TARGETS:
    if _t.name.startswith("loadscreen_button_continuegame"):
        _t.avail_end = 255
    elif _t.name.startswith("loadscreen_button_erasegame"):
        _t.avail_end = 240
# 194px start buttons have no icon and centre the label
_btn("loadscreen_button_startmale", "Jogar como homem", 194, None, anchor="center")
_btn("loadscreen_button_startmale_over", "Jogar como homem", 194, None, anchor="center")
_btn("loadscreen_button_startfemale", "Jogar como mulher", 194, None, anchor="center")
_btn("loadscreen_button_startfemale_over", "Jogar como mulher", 194, None, anchor="center")

TARGETS += [
    Target("loadscreen_settings_close", "Fechar", "close", "Black", text_x0=66,
           box=(66, 10, 154, 52)),
    Target("loadscreen_settings_close_over", "Fechar", "close", "Black", text_x0=66,
           box=(66, 10, 154, 52)),
    Target("titlescreen_prompt", "CLIQUE PARA COMEÇAR", "title", "Black", cap=36, stroke=3),
    Target("loadscreen_nodata_background", "SEM DADOS", "nodata", "Bold"),
    Target("ui_transition_screen_gamesaved", "Jogo salvo", "saved", "Medium",
           box=(60, 7, 202, 30)),
]

# The hint strip holds three icon+label pairs; only the labels are repainted.
PROMPTS_NAME = "loadscreen_screen_prompts"
PROMPTS = [
    ("Tamanho da janela", (96, 0, 320, 44), 99, 480),
    ("Tela cheia", (528, 0, 730, 44), 533, 880),
    ("Proporção da tela", (930, 0, 1190, 44), 937, 1192),
]


def lum(a: np.ndarray) -> np.ndarray:
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def erode(mask: np.ndarray, px: int) -> np.ndarray:
    im = Image.fromarray((mask * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.MinFilter(2 * px + 1))) > 127


def dilate(mask: np.ndarray, px: int) -> np.ndarray:
    im = Image.fromarray((mask * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.MaxFilter(2 * px + 1))) > 127


def glyph_mask(img: Image.Image, target: Target) -> np.ndarray:
    """Pixels that belong to the EN glyphs (never to plates, rims or icons)."""
    a = np.asarray(img).astype(np.int16)
    h, w = a.shape[:2]
    if target.kind in ("button", "close"):
        inner = erode(a[..., 3] > 200, 8)
        m = inner & (a[..., 3] > 200) & (lum(a) < 140)
        m = m & (a[..., 3] > 200)
    elif target.kind == "saved":
        m = (a[..., 3] > 60) & (lum(a) > 230)
    else:  # title / nodata: the plate is translucent, glyphs are near-opaque
        m = a[..., 3] > 120
    if target.box:
        x0, y0, x1, y1 = target.box
        keep = np.zeros((h, w), bool)
        keep[y0:y1, x0:x1] = True
        m &= keep
    if target.text_x0:
        keep = np.zeros((h, w), bool)
        keep[:, target.text_x0:] = True
        m &= keep
    return m


def bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def sample_colors(img: Image.Image, mask: np.ndarray, kind: str) -> tuple[tuple, tuple]:
    a = np.asarray(img).astype(np.int16)
    px = a[mask]
    light = lum(px.astype(np.float32))
    if kind in ("button", "close"):
        core = px[light <= np.percentile(light, 15)]
    elif kind == "saved":
        core = px[light >= np.percentile(light, 85)]
    else:
        alpha = px[:, 3]
        core = px[alpha >= np.percentile(alpha, 90)]
    fill = np.median(core, axis=0)
    border = a[mask & ~erode(mask, 2)]
    edge = np.median(border, axis=0) if len(border) else fill
    return tuple(int(v) for v in fill), tuple(int(v) for v in edge)


def inpaint(img: Image.Image, mask: np.ndarray) -> np.ndarray:
    """Row-wise linear fill between each run's neighbours (keeps gradients)."""
    out = np.asarray(img).astype(np.float32).copy()
    h, w = mask.shape
    for y in range(h):
        xs = np.where(mask[y])[0]
        if len(xs) == 0:
            continue
        for run in np.split(xs, np.where(np.diff(xs) > 1)[0] + 1):
            a0, b0 = int(run[0]), int(run[-1])
            left_x = a0 - 1
            while left_x >= 0 and mask[y, left_x]:
                left_x -= 1
            right_x = b0 + 1
            while right_x < w and mask[y, right_x]:
                right_x += 1
            left = out[y, left_x] if left_x >= 0 else None
            right = out[y, right_x] if right_x < w else None
            if left is None and right is None:
                continue
            if left is None:
                out[y, a0:b0 + 1] = right
            elif right is None:
                out[y, a0:b0 + 1] = left
            else:
                t = np.linspace(0, 1, b0 - a0 + 3)[1:-1][:, None]
                out[y, a0:b0 + 1] = left[None, :] * (1 - t) + right[None, :] * t
    return np.clip(out, 0, 255)


def font(size: int, weight: str) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONT_PATH), size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


_cap_cache: dict[tuple[int, str], int] = {}


def cap_height(size: int, weight: str) -> int:
    key = (size, weight)
    if key not in _cap_cache:
        canvas = Image.new("L", (size * 3 + 20, size * 3 + 20), 0)
        ImageDraw.Draw(canvas).text((10, 10), "H", font=font(size, weight), fill=255)
        bb = canvas.getbbox()
        _cap_cache[key] = bb[3] - bb[1]
    return _cap_cache[key]


def size_for_cap(target: int, weight: str) -> int:
    size = 8
    for s in range(8, 200):
        if cap_height(s, weight) <= target:
            size = s
        else:
            break
    return size


def render_glyphs(text: str, size: int, weight: str, stroke: int) -> tuple[Image.Image, Image.Image]:
    f = font(size, weight)
    pad = 4 + stroke
    canvas = Image.new("L", (size * len(text) * 2 + 80, size * 3 + 40), 0)
    ImageDraw.Draw(canvas).text((pad, pad), text, font=f, fill=255,
                                stroke_width=stroke, stroke_fill=255)
    crop = canvas.getbbox()
    coverage = canvas.crop(crop)
    stroke_canvas = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(stroke_canvas).text((pad, pad), text, font=f, fill=0,
                                       stroke_width=stroke, stroke_fill=255)
    return coverage, stroke_canvas.crop(crop)


def composite(bg: np.ndarray, coverage: Image.Image, stroke_img: Image.Image,
              fill: tuple, edge: tuple, pos: tuple[float, float], anchor: str) -> np.ndarray:
    cov = np.asarray(coverage).astype(np.float32) / 255.0
    stro = np.asarray(stroke_img).astype(np.float32) / 255.0
    h, w = cov.shape
    x, y = pos
    x0 = int(round(x - w / 2)) if anchor == "center" else int(round(x))
    y0 = int(round(y))
    H, W = bg.shape[:2]
    sx0, sy0 = max(0, x0), max(0, y0)
    sx1, sy1 = min(W, x0 + w), min(H, y0 + h)
    if sx1 <= sx0 or sy1 <= sy0:
        return bg
    out = bg.copy()
    c = cov[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0][..., None]
    st = stro[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0][..., None]
    fr = np.array(fill, np.float32)
    er = np.array(edge, np.float32)
    tr = fr[None, None, :3] * (1 - st) + er[None, None, :3] * st
    ta = fr[None, None, 3] * (1 - st) + er[None, None, 3] * st
    reg = out[sy0:sy1, sx0:sx1]
    reg[..., :3] = reg[..., :3] * (1 - c) + tr * c
    reg[..., 3:] = reg[..., 3:] * (1 - c) + ta * c
    return out


def draw_label(bg: np.ndarray, label: str, bb: tuple, avail_w: int, fill: tuple, edge: tuple,
               weight: str, stroke: int, desc: bool, anchor: str, left_x: float | None,
               cap_override: int | None = None) -> tuple[np.ndarray, dict]:
    height = bb[3] - bb[1]
    cap = cap_override if cap_override else (round(height * 0.78) if desc else height)
    size = size_for_cap(cap, weight)
    coverage, stroke_img = render_glyphs(label, size, weight, stroke)
    scale_x = 1.0
    if coverage.width > avail_w:
        scale_x = avail_w / coverage.width
        coverage = coverage.resize((max(1, int(round(coverage.width * scale_x))), coverage.height),
                                   Image.LANCZOS)
        stroke_img = stroke_img.resize(coverage.size, Image.LANCZOS)
    cx = (bb[0] + bb[2]) / 2 if anchor == "center" else (left_x if left_x is not None else bb[0])
    out = composite(bg, coverage, stroke_img, fill, edge, (cx, bb[1]), anchor)
    return out, {"size": size, "cap": cap, "condense": round(scale_x, 3)}


def process(target: Target, preview: bool) -> dict | None:
    src = SRC / f"{target.name}.png"
    if not src.exists():
        print(f"missing {src.name}")
        return None
    img = Image.open(src).convert("RGBA")
    mask = glyph_mask(img, target)
    if not mask.any():
        print(f"empty glyph mask for {target.name}")
        return None
    bb = bbox(mask)
    fill, edge = sample_colors(img, mask, target.kind)
    dist = sum(abs(int(a) - int(b)) for a, b in zip(fill[:3], edge[:3]))
    stroke = target.stroke
    if stroke is None:
        stroke = max(1, round((bb[3] - bb[1]) * 0.06)) if (dist > 45 and edge[3] > 100) else 0
    clean = inpaint(img, dilate(mask, 2))
    if target.text_x0:
        left_x = target.text_x0
        avail = (target.avail_end or img.width - 16) - target.text_x0
    else:
        left_x = None
        avail = img.width - 40
    out, info = draw_label(clean, target.label, bb, avail, fill, edge, target.weight,
                           stroke, target.desc, target.anchor, left_x, target.cap)
    res = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
    res.save(OUT / f"{target.name}.png")
    stats = {"name": target.name, "bb": bb, "fill": fill[:3], "alpha": fill[3],
             "stroke": stroke, **info}
    print(f"pt {target.name:42s} bb={bb} fill={fill[:3]}/{fill[3]} stroke={stroke} {info}")
    if preview:
        save_preview(img, res, target.name)
    return stats


def process_prompts(preview: bool) -> dict | None:
    src = SRC / f"{PROMPTS_NAME}.png"
    if not src.exists():
        print(f"missing {src.name}")
        return None
    img = Image.open(src).convert("RGBA")
    a = np.asarray(img).astype(np.int16)
    total_mask = np.zeros(a.shape[:2], bool)
    parts = []
    for label, box, left, avail_end in PROMPTS:
        x0, y0, x1, y1 = box
        keep = np.zeros(a.shape[:2], bool)
        keep[y0:y1, x0:x1] = True
        m = keep & (a[..., 3] > 120)
        total_mask |= m
        parts.append((label, m, left, avail_end))
    clean = inpaint(img, dilate(total_mask, 2))
    fill, edge = sample_colors(img, total_mask, "title")
    dist = sum(abs(int(x) - int(y)) for x, y in zip(fill[:3], edge[:3]))
    stroke = max(1, round(23 * 0.06)) if (dist > 45 and edge[3] > 100) else 0
    for label, m, left, avail_end in parts:
        bb = bbox(m)
        clean, info = draw_label(clean, label, bb, avail_end - left, fill, edge, "Medium",
                                 stroke, True, "left", left)
        print(f"pt {PROMPTS_NAME:42s} seg {label!r} bb={bb} {info}")
    res = Image.fromarray(np.clip(clean, 0, 255).astype(np.uint8), "RGBA")
    res.save(OUT / f"{PROMPTS_NAME}.png")
    if preview:
        save_preview(img, res, PROMPTS_NAME)
    return {"name": PROMPTS_NAME, "segments": len(parts), "fill": fill[:3]}


def save_preview(orig: Image.Image, pt: Image.Image, name: str) -> None:
    PREVIEW.mkdir(parents=True, exist_ok=True)
    z = 3 if orig.width < 500 else 1
    o = orig.resize((orig.width * z, orig.height * z), Image.NEAREST)
    n = pt.resize((pt.width * z, pt.height * z), Image.NEAREST)
    sheet = Image.new("RGBA", (o.width, o.height * 2 + 8), (90, 90, 90, 255))
    sheet.alpha_composite(o, (0, 0))
    sheet.alpha_composite(n, (0, o.height + 8))
    sheet.save(PREVIEW / f"{name}_en_top_pt_bottom.png")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preview", action="store_true", help="write EN/PT comparison sheets")
    args = ap.parse_args()
    if not FONT_PATH.exists():
        print(f"font missing: {FONT_PATH}")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    stats = [process(t, args.preview) for t in TARGETS]
    stats.append(process_prompts(args.preview))
    labels = {t.name: t.label for t in TARGETS}
    labels[PROMPTS_NAME] = " / ".join(p[0] for p in PROMPTS)
    (OUT / "labels.json").write_text(json.dumps(labels, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    print(f"generated {sum(1 for s in stats if s)} PT sprites -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
