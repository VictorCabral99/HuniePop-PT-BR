"""Quick probe: which Unity object types hold HuniePop text."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import UnityPy

GAME_DATA = Path(r"C:/Program Files (x86)/Steam/steamapps/common/HuniePop/HuniePop_Data")
ASSETS = [
    GAME_DATA / "resources.assets",
    GAME_DATA / "sharedassets0.assets",
]


def walk_strings(obj, prefix: str = ""):
    if isinstance(obj, str) and len(obj) >= 6:
        yield prefix, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            yield from walk_strings(v, p)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{prefix}[{i}]")


def probe(path: Path, mono_limit: int = 2000) -> None:
    print(f"=== {path.name} ===", flush=True)
    env = UnityPy.load(str(path))
    types = Counter()
    mono = Counter()
    samples: list[tuple] = []
    mono_seen = 0

    for obj in env.objects:
        tname = obj.type.name
        types[tname] += 1
        if tname != "MonoBehaviour":
            continue
        if mono_seen >= mono_limit:
            continue
        mono_seen += 1
        try:
            tree = obj.read_typetree()
        except Exception as e:
            mono[f"ERR:{type(e).__name__}"] += 1
            continue
        if not isinstance(tree, dict):
            continue
        script = ""
        ms = tree.get("m_Script") or {}
        if isinstance(ms, dict):
            script = ms.get("m_Name") or ms.get("name") or ""
        name = tree.get("m_Name") or tree.get("name") or ""
        mono[f"{script or '?'}:{name or '(unnamed)'}"] += 1
        strs = [(p, s) for p, s in walk_strings(tree) if " " in s or len(s) > 20]
        if strs and len(samples) < 5:
            samples.append((script, name, strs[:6]))

    print("types:", types.most_common(15), flush=True)
    print("mono top:", mono.most_common(20), flush=True)
    print("samples:", flush=True)
    for script, name, strs in samples:
        print(f"  -- {script} | {name}", flush=True)
        for p, s in strs:
            print(f"     {p} => {s[:140]!r}", flush=True)


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    targets = ASSETS
    if which == "resources":
        targets = [ASSETS[0]]
    elif which == "shared":
        targets = [ASSETS[1]]
    for path in targets:
        probe(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
