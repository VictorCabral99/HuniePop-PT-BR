"""Split dialogue groups into packets for colloquial BR rewrite; merge results.

Packets: build/colloquial_packets/packet_NN.json
Results:  build/colloquial_out/packet_NN.json  ({"en": "pt", ...} or list of {en,pt})

Usage:
  python scripts/colloquial_packets.py split --prefix GameOpening --prefix Intro --parts 4
  python scripts/colloquial_packets.py split --categories dialogue --parts 12
  python scripts/colloquial_packets.py merge
  python scripts/fold_ascii_pt.py
  python scripts/apply_patch_expand.py --install
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ROOT / "export" / "en" / "dialogue_groups.json"
LOCALE = ROOT / "locale" / "pt-BR" / "unique_texts.csv"
PACKET_DIR = ROOT / "build" / "colloquial_packets"
OUT_DIR = ROOT / "build" / "colloquial_out"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from locale_csv import read_locale_rows, write_locale_rows  # noqa: E402


def split_packets(
    prefixes: list[str] | None,
    parts: int,
    categories: list[str] | None,
) -> int:
    groups = json.loads(GROUPS.read_text(encoding="utf-8"))
    selected = []
    for g in groups:
        name = g.get("object_name") or ""
        if prefixes and not any(name.startswith(p) for p in prefixes):
            continue
        selected.append(g)
    if not selected and not prefixes:
        selected = groups

    PACKET_DIR.mkdir(parents=True, exist_ok=True)
    for old in PACKET_DIR.glob("packet_*.json"):
        old.unlink()

    # balance by line count
    selected = sorted(selected, key=lambda g: -len(g.get("lines") or []))
    buckets: list[list[dict]] = [[] for _ in range(max(1, parts))]
    weights = [0] * len(buckets)
    for g in selected:
        i = weights.index(min(weights))
        buckets[i].append(g)
        weights[i] += len(g.get("lines") or [])

    n = 0
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        payload = {
            "style": (ROOT / "docs" / "tom-pt-br.md").read_text(encoding="utf-8"),
            "groups": [
                {
                    "object_name": g.get("object_name"),
                    "kind": g.get("kind"),
                    "girl": g.get("girl"),
                    "lines": [{"text": ln["text"]} for ln in g.get("lines") or []],
                }
                for g in bucket
            ],
        }
        path = PACKET_DIR / f"packet_{i:02d}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = sum(len(g["lines"]) for g in payload["groups"])
        print(f"  {path.name}: groups={len(bucket)} lines={lines}")
        n += 1
    print(f"wrote {n} packets -> {PACKET_DIR}")
    return n


def merge_results() -> int:
    rows, fields = read_locale_rows(LOCALE)
    by_en = {r["text"]: r for r in rows}
    updated = 0
    files = sorted(OUT_DIR.glob("packet_*.json"))
    if not files:
        print(f"no results in {OUT_DIR}", file=sys.stderr)
        return 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        pairs: list[tuple[str, str]] = []
        if isinstance(data, dict) and "translations" in data:
            data = data["translations"]
        if isinstance(data, dict):
            pairs = [(k, v) for k, v in data.items() if isinstance(v, str)]
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "en" in item and "pt" in item:
                    pairs.append((item["en"], item["pt"]))
        for en, pt in pairs:
            pt = (pt or "").strip()
            if not en or not pt:
                continue
            row = by_en.get(en)
            if not row:
                continue
            if row.get("pt_BR") != pt:
                row["pt_BR"] = pt
                updated += 1
        print(f"  merged {path.name}: {len(pairs)} pairs")
    write_locale_rows(LOCALE, rows, fields)
    print(f"updated {updated} rows in {LOCALE.name}")
    return updated


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("split")
    sp.add_argument("--prefix", action="append", default=None)
    sp.add_argument("--parts", type=int, default=4)
    sp.add_argument("--categories", nargs="*", default=None)
    sub.add_parser("merge")
    args = ap.parse_args()
    if args.cmd == "split":
        split_packets(args.prefix, args.parts, args.categories)
    else:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        merge_results()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
