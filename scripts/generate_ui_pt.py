"""Generate PT-BR replacements for loadscreen word-sprites.

Reads cropped EN sprites from export/ui_sprites/, redraws label text,
writes to export/ui_sprites/pt/ (same pixel size, RGBA).

Usage:
  python scripts/generate_ui_pt.py
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "export" / "ui_sprites"
OUT = SRC / "pt"

# EN sprite name -> PT label (None = skip / decorative only)
LABELS: dict[str, str | None] = {
    "loadscreen_button_continuegame": "Continuar",
    "loadscreen_button_continuegame_over": "Continuar",
    "loadscreen_button_startmale": "Homem",
    "loadscreen_button_startmale_over": "Homem",
    "loadscreen_button_startfemale": "Mulher",
    "loadscreen_button_startfemale_over": "Mulher",
    "loadscreen_button_cancel": "Cancelar",
    "loadscreen_button_cancel_over": "Cancelar",
    "loadscreen_button_credits": "Creditos",
    "loadscreen_button_credits_over": "Creditos",
    "loadscreen_button_erase": "Apagar",
    "loadscreen_button_erase_over": "Apagar",
    "loadscreen_button_erasegame": "Apagar Jogo",
    "loadscreen_button_erasegame_over": "Apagar Jogo",
    "loadscreen_button_gallery": "Galeria",
    "loadscreen_button_gallery_over": "Galeria",
    "loadscreen_button_settings": "Opcoes",
    "loadscreen_button_settings_over": "Opcoes",
    "loadscreen_nodata_background": "SEM DADOS",
    "loadscreen_settings_close": "Fechar",
    "loadscreen_settings_close_over": "Fechar",
    "ui_transition_screen_gamesaved": "Jogo Salvo",
    "loadscreen_screen_prompts": "Janela  /  Tela Cheia (F)  /  Proporcao (A)",
    "titlescreen_prompt": "CLIQUE PARA COMECAR",
}

# Keep backgrounds (resprite only labels we know how to paint)
SKIP_KEEP = {
    "loadscreen_data_background",
    "loadscreen_overlay",
    "loadscreen_savefile_background",
    "loadscreen_settings_background",
}


def find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:/Windows/Fonts/seguisb.ttf"),  # Segoe UI Semibold
        Path(r"C:/Windows/Fonts/segoeuib.ttf"),
        Path(r"C:/Windows/Fonts/arialbd.ttf"),
        Path(r"C:/Windows/Fonts/tahomabd.ttf"),
        Path(r"C:/Windows/Fonts/calibrib.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def sample_text_color(img: Image.Image) -> tuple[int, int, int, int]:
    """Pick a dark opaque pixel near center as ink color."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    best = None
    best_luma = 999
    for y in range(h // 4, 3 * h // 4):
        for x in range(w // 5, 4 * w // 5):
            r, g, b, a = rgba.getpixel((x, y))
            if a < 200:
                continue
            luma = 0.299 * r + 0.587 * g + 0.114 * b
            # Prefer dark ink on light button
            if luma < best_luma and luma < 140:
                best_luma = luma
                best = (r, g, b, 255)
    if best:
        return best
    # Fallback: gray for NO DATA style
    return (140, 140, 140, 255)


def clear_label_band(img: Image.Image) -> Image.Image:
    """Cover central label with sampled button fill (keeps border/hearts roughly)."""
    rgba = img.convert("RGBA")
    w, h = rgba.size
    # sample fill from upper-middle area (button body)
    fills = []
    for y in range(max(1, h // 5), max(2, h // 3)):
        for x in range(w // 4, 3 * w // 4):
            p = rgba.getpixel((x, y))
            if p[3] > 200:
                fills.append(p)
    if not fills:
        return rgba
    # median-ish: average
    n = len(fills)
    fill = tuple(sum(c[i] for c in fills) // n for i in range(4))
    out = rgba.copy()
    draw = ImageDraw.Draw(out)
    # wipe a band leaving ~10% margin (preserve side hearts on continue)
    margin_x = max(8, int(w * 0.12))
    margin_y = max(4, int(h * 0.18))
    draw.rounded_rectangle(
        [margin_x, margin_y, w - margin_x, h - margin_y],
        radius=max(4, h // 4),
        fill=fill,
    )
    return out


def fit_font(text: str, max_w: int, max_h: int) -> ImageFont.ImageFont:
    size = min(28, max_h - 4)
    while size >= 10:
        font = find_font(size)
        bbox = font.getbbox(text)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= max_w and th <= max_h:
            return font
        size -= 1
    return find_font(10)


def redraw(name: str, src: Path, label: str) -> Image.Image:
    base = Image.open(src).convert("RGBA")
    w, h = base.size
    ink = sample_text_color(base)

    # Full-bleed text panels (NO DATA / prompts / game saved)
    if name in (
        "loadscreen_nodata_background",
        "loadscreen_screen_prompts",
        "ui_transition_screen_gamesaved",
        "titlescreen_prompt",
    ):
        out = base.copy()
        draw = ImageDraw.Draw(out)
        if name == "loadscreen_nodata_background":
            draw.rectangle([40, 20, w - 40, h - 20], fill=(20, 20, 22, 255))
            ink = (160, 160, 165, 255)
        elif name == "ui_transition_screen_gamesaved":
            edge = base.getpixel((2, h // 2))
            draw.rectangle([0, 0, w, h], fill=edge)
        elif name == "titlescreen_prompt":
            # black plate + lavender fill + dark outline (matches EN sprite)
            draw.rectangle([0, 0, w, h], fill=(0, 0, 0, 255))
            ink = (200, 170, 190, 255)
            outline = (90, 40, 70, 255)
            font = fit_font(label, w - 16, h - 6)
            bbox = font.getbbox(label)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (w - tw) // 2 - bbox[0]
            y = (h - th) // 2 - bbox[1]
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)):
                draw.text((x + ox, y + oy), label, font=font, fill=outline)
            draw.text((x, y), label, font=font, fill=ink)
            return out
        else:
            draw.rectangle([70, 0, w, h], fill=(0, 0, 0, 255))
            ink = (180, 160, 200, 255)
        font = fit_font(label, w - 20, h - 8)
        bbox = font.getbbox(label)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (w - tw) // 2 - bbox[0]
        y = (h - th) // 2 - bbox[1]
        draw.text((x, y), label, font=font, fill=ink)
        return out

    out = clear_label_band(base)
    draw = ImageDraw.Draw(out)
    max_w = int(w * 0.70)
    max_h = int(h * 0.70)
    font = fit_font(label, max_w, max_h)
    bbox = font.getbbox(label)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (w - tw) // 2 - bbox[0]
    y = (h - th) // 2 - bbox[1]
    draw.text((x, y), label, font=font, fill=ink)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = SRC / "manifest.json"
    if not manifest_path.exists():
        print("Run extract_ui_images.py first")
        return 1
    man = {e["name"]: e for e in json.loads(manifest_path.read_text(encoding="utf-8"))}

    n = 0
    for name, label in LABELS.items():
        if label is None or name in SKIP_KEEP:
            continue
        src = SRC / f"{name}.png"
        if not src.exists():
            print("missing", name)
            continue
        # Re-crop with fixed orientation if extract was old
        img = redraw(name, src, label)
        dest = OUT / f"{name}.png"
        img.save(dest)
        meta = man.get(name, {})
        print(f"pt {name} {img.size} <- {label!r} flipped={meta.get('flipped')}")
        n += 1

    (OUT / "labels.json").write_text(
        json.dumps(LABELS, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"generated {n} PT sprites -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
