"""HuniePop PT-BR patch entrypoint — safe in-place by default.

UnityPy full rewrite (apply_patch_unitypy.py) black-screens Unity 4.2.
This wraps apply_patch_inplace.py.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    if "--unitypy" in sys.argv:
        print(
            "WARNING: --unitypy rewrites the whole .assets and caused black screen on HuniePop.",
            file=sys.stderr,
        )
        sys.argv = [a for a in sys.argv if a != "--unitypy"]
        target = Path(__file__).with_name("apply_patch_unitypy.py")
    else:
        target = Path(__file__).with_name("apply_patch_inplace.py")
    if target.name == "apply_patch_inplace.py" and "--out" not in sys.argv:
        sys.argv.extend(
            ["--out", str(Path(__file__).resolve().parents[1] / "build" / "patch_inplace")]
        )
    sys.argv[0] = str(target)
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
