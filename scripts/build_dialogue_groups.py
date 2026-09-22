"""Build dialogue groups from export/en/strings.csv for contextual translation.

Groups by object_name (scene/asset). Each group keeps English lines in step order
so a translator can use nearby lines as context (EN is the source of truth).

Writes:
  export/en/dialogue_groups.json
  export/en/dialogue_groups.csv  (flat: group_id, idx, text, ...)

Usage:
  python scripts/build_dialogue_groups.py
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRINGS = ROOT / "export" / "en" / "strings.csv"
OUT_JSON = ROOT / "export" / "en" / "dialogue_groups.json"
OUT_CSV = ROOT / "export" / "en" / "dialogue_groups.csv"

GIRL_RE = re.compile(
    r"(Aiko|Audrey|Beli|Celeste|Jessie|Kyanna|Kyu|Lola|Momo|Nikki|Tiffany|Venus|Suzume)",
    re.I,
)
KIND_RE = re.compile(
    r"^(Intro|Greeting|Valediction|DateGreeting|DateValediction|AskDate|"
    r"GivenGift|GivenDrink|GivenFood|GivenDateGift|Question|MatchToken|"
    r"GameOpeningPart|Date)",
    re.I,
)


def step_key(field_path: str) -> tuple:
    nums = [int(x) for x in re.findall(r"\[(\d+)\]", field_path or "")]
    # distinguish option labels vs replies lightly
    kind = 0
    fp = field_path or ""
    if fp.endswith(".text") and "responseOptions" in fp and "steps" not in fp.split("responseOptions")[-1]:
        kind = 1  # player choice label
    return tuple(nums + [kind])


def scene_meta(object_name: str) -> dict:
    girl = None
    m = GIRL_RE.search(object_name or "")
    if m:
        girl = m.group(1).title()
        if girl.lower() == "beli":
            girl = "Beli"
    kind = None
    km = KIND_RE.match(object_name or "")
    if km:
        kind = km.group(1)
    return {"girl": girl, "kind": kind}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strings", type=Path, default=STRINGS)
    args = ap.parse_args()

    rows = list(csv.DictReader(args.strings.open(encoding="utf-8")))
    dlg = [r for r in rows if r.get("category") == "dialogue"]
    by: dict[str, list[dict]] = defaultdict(list)
    for r in dlg:
        by[r.get("object_name") or f"path_{r['path_id']}"].append(r)

    groups = []
    flat = []
    for name in sorted(by.keys()):
        items = sorted(by[name], key=lambda r: step_key(r.get("field_path") or ""))
        # dedupe consecutive identical texts inside scene
        lines = []
        seen_local = set()
        for r in items:
            text = r.get("text") or ""
            key = (r.get("field_path"), text)
            if key in seen_local:
                continue
            seen_local.add(key)
            lines.append(
                {
                    "id": r.get("id"),
                    "path_id": int(r["path_id"]),
                    "field_path": r.get("field_path"),
                    "text": text,
                }
            )
        meta = scene_meta(name)
        groups.append(
            {
                "group_id": name,
                "object_name": name,
                "girl": meta["girl"],
                "kind": meta["kind"],
                "n_lines": len(lines),
                "lines": lines,
            }
        )
        for i, line in enumerate(lines):
            flat.append(
                {
                    "group_id": name,
                    "girl": meta["girl"] or "",
                    "kind": meta["kind"] or "",
                    "idx": i,
                    "n_lines": len(lines),
                    "id": line["id"],
                    "path_id": line["path_id"],
                    "field_path": line["field_path"],
                    "text": line["text"],
                }
            )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8")
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0].keys()) if flat else [])
        if flat:
            w.writeheader()
            w.writerows(flat)

    print(f"groups={len(groups)} lines={len(flat)} -> {OUT_JSON}")
    # show a couple intros
    for g in groups:
        if g["object_name"].startswith("Intro") and g["n_lines"] >= 5:
            print(f"  sample {g['object_name']} girl={g['girl']} lines={g['n_lines']}")
            for line in g["lines"][:3]:
                print(f"    - {line['text'][:70]!r}")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
