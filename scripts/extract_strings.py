"""Extract translatable English strings from HuniePop Unity assets.

Text-only fan translation pipeline (no audio).
Requires: UnityPy, TypeTreeGeneratorAPI
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import UnityPy
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = Path(r"C:/Program Files (x86)/Steam/steamapps/common/HuniePop")
EXPORT_DIR = ROOT / "export" / "en"

# Skip technical / non-UI noise
SKIP_FIELD_RE = re.compile(
    r"(m_Script|m_FileID|m_PathID|guid|hash|shader|material|texture|mesh|audio|"
    r"clipName|fileName|bundle|assetPath|m_Father|m_Children|"
    r"Sprite|sprite|bgSprite|headerSprite|iconName|animName|prefab|"
    r"m_Name$)",
    re.I,
)
MARKUP_RE = re.compile(r"\[\[[^\]]+\][^\]]*\]")
HAS_LETTER = re.compile(r"[A-Za-z]")


@dataclass
class StringHit:
    id: str
    source_file: str
    path_id: int
    type_name: str
    object_name: str
    field_path: str
    text: str
    category: str


def categorize(text: str, field_path: str, object_name: str) -> str:
    fp = field_path.lower()
    on = (object_name or "").lower()
    if "dialog" in fp or "dialog" in on or "speech" in fp or "line" in fp:
        return "dialogue"
    if "message" in fp or "message" in on:
        return "message"
    if "tutorial" in fp or "tutorial" in on or "tip" in fp:
        return "tutorial"
    if "item" in fp or "gift" in fp or "desc" in fp:
        return "item"
    if "ui" in fp or "label" in fp or "button" in fp or "title" in fp:
        return "ui"
    if " " in text and len(text) > 40:
        return "dialogue"
    return "other"


PLACEHOLDER_TEXTS = {
    "Dialog...",
    "Item Name",
    "Message text goes here...",
    "Option Label",
    "Option label goes here...",
    "Detail Value",
    "Preference Value",
    "Style Name",
    "Sent by Girl | Date | Time",
}


def is_translatable(text: str, field_path: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    if SKIP_FIELD_RE.search(field_path):
        return False
    t = text.strip()
    if len(t) < 2:
        return False
    if t in PLACEHOLDER_TEXTS:
        return False
    # hex colors / ids
    if re.fullmatch(r"[0-9A-Fa-f]{6}", t):
        return False
    if not HAS_LETTER.search(t):
        return False
    # SFX / moan markers like *ccaacc* (keep only if mixed with real words)
    if re.fullmatch(r"[\*·.•\sA-Za-z]*", t) and "*" in t and " " not in t.strip("*"):
        if len(re.sub(r"[^A-Za-z]", "", t)) <= 12:
            return False
    # pure markup / identifiers
    if re.fullmatch(r"[\w./\\-]+", t) and " " not in t and len(t) < 40:
        # allow short UI words like OK, Start — still skip CamelCase identifiers
        if re.search(r"[a-z][A-Z]", t) or "_" in t or "/" in t or "\\" in t:
            return False
    # skip file-like
    if t.endswith((".png", ".wav", ".ogg", ".prefab", ".mat", ".shader", ".cs")):
        return False
    return True


def walk_strings(obj, prefix: str = ""):
    if isinstance(obj, str):
        yield prefix, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            yield from walk_strings(v, p)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{prefix}[{i}]")


def make_id(source_file: str, path_id: int, field_path: str, text: str) -> str:
    raw = f"{source_file}|{path_id}|{field_path}|{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def extract_asset(
    path: Path,
    generator: TypeTreeGenerator,
    limit: int | None = None,
) -> list[StringHit]:
    print(f"Loading {path.name}...", flush=True)
    env = UnityPy.load(str(path))
    env.typetree_generator = generator
    hits: list[StringHit] = []
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
        object_name = str(tree.get("m_Name") or "")
        for field_path, text in walk_strings(tree):
            if not is_translatable(text, field_path):
                continue
            hits.append(
                StringHit(
                    id=make_id(path.name, obj.path_id, field_path, text),
                    source_file=path.name,
                    path_id=int(obj.path_id),
                    type_name="MonoBehaviour",
                    object_name=object_name,
                    field_path=field_path,
                    text=text,
                    category=categorize(text, field_path, object_name),
                )
            )
        if limit is not None and mono_ok >= limit:
            break

    print(f"  MonoBehaviour ok={mono_ok} err={mono_err} strings={len(hits)}", flush=True)
    return hits


def write_exports(hits: list[StringHit], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # dedupe by id (same string same place)
    by_id = {h.id: h for h in hits}
    unique = list(by_id.values())

    json_path = out_dir / "strings.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(h) for h in unique], f, ensure_ascii=False, indent=2)

    csv_path = out_dir / "strings.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "category",
                "source_file",
                "path_id",
                "object_name",
                "field_path",
                "text",
                "pt_BR",
            ],
        )
        w.writeheader()
        for h in sorted(unique, key=lambda x: (x.category, x.source_file, x.path_id, x.field_path)):
            row = asdict(h)
            row["pt_BR"] = ""
            w.writerow({k: row[k] for k in w.fieldnames})

    # unique texts for translators (lighter)
    uniq_text: dict[str, dict] = {}
    for h in unique:
        if h.text not in uniq_text:
            uniq_text[h.text] = {
                "text": h.text,
                "pt_BR": "",
                "category": h.category,
                "occurrences": 0,
                "sample_id": h.id,
            }
        uniq_text[h.text]["occurrences"] += 1

    flat = out_dir / "unique_texts.csv"
    with flat.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["sample_id", "category", "occurrences", "text", "pt_BR"],
        )
        w.writeheader()
        for row in sorted(uniq_text.values(), key=lambda r: (-r["occurrences"], r["category"], r["text"])):
            w.writerow(row)

    by_cat: dict[str, int] = defaultdict(int)
    for h in unique:
        by_cat[h.category] += 1
    summary = {
        "total_entries": len(unique),
        "unique_texts": len(uniq_text),
        "by_category": dict(sorted(by_cat.items(), key=lambda x: -x[1])),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print(f"Wrote {json_path}", flush=True)
    print(f"Wrote {csv_path}", flush=True)
    print(f"Wrote {flat}", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract HuniePop EN strings (text only)")
    ap.add_argument("--game", type=Path, default=DEFAULT_GAME, help="HuniePop install root")
    ap.add_argument(
        "--assets",
        nargs="*",
        default=["resources.assets", "sharedassets0.assets"],
        help="Asset filenames under *_Data",
    )
    ap.add_argument("--limit", type=int, default=None, help="Max MonoBehaviours per file (debug)")
    ap.add_argument("--out", type=Path, default=EXPORT_DIR)
    args = ap.parse_args(argv)

    data_dir = args.game / "HuniePop_Data"
    if not data_dir.is_dir():
        print(f"Game data not found: {data_dir}", file=sys.stderr)
        return 1

    print("Building TypeTree from Managed DLLs...", flush=True)
    gen = TypeTreeGenerator("4.2.2f1")
    gen.load_local_game(str(args.game))

    all_hits: list[StringHit] = []
    for name in args.assets:
        path = data_dir / name
        if not path.is_file():
            print(f"Missing {path}", file=sys.stderr)
            continue
        all_hits.extend(extract_asset(path, gen, limit=args.limit))

    write_exports(all_hits, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
