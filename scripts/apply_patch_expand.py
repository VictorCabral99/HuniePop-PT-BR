"""Expand patch for HuniePop — rewrites MonoBehaviour payloads, keeps metadata.

Root cause of prior black screen: bad MT entries (e.g. 12KB credits -> 16 chars)
collapsed objects via save_typetree. Filters + size guards are now required.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> int:
    impl = Path(__file__).with_name("_apply_patch_expand_impl.py")
    sys.argv[0] = str(impl)
    runpy.run_path(str(impl), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
