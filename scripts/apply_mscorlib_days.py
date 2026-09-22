"""Patch mscorlib.dll culture day names EN → PT-BR ASCII (same #US block size).

HuniePop DayLabel / TransitionScreenDayLabel use DateTime formatting, which
pulls weekday names from mscorlib — not from .assets sprites.

Usage:
  python scripts/apply_mscorlib_days.py
  python scripts/apply_mscorlib_days.py --install
"""
from __future__ import annotations

import argparse
import shutil
import struct
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAME = Path(r"C:/Program Files (x86)/Steam/steamapps/common/HuniePop")
MSC = "mscorlib.dll"

# Exact 3-letter abbrevs (same UTF-16 size as Sun..Sat)
ABBREV = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]
# Full names (packed into original Sunday..Saturday budget)
FULL = ["Domingo", "Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado"]


def us_entry(text: str) -> bytes:
    """ECMA #US-style: 1-byte length + UTF-16LE + trailing 0x00."""
    payload = text.encode("utf-16le") + b"\x00"
    if len(payload) > 255:
        raise ValueError(f"string too long for #US byte length: {text!r}")
    return bytes([len(payload)]) + payload


def pack_full_days(budget: int) -> bytes:
    parts = [us_entry(s) for s in FULL[:-1]]
    used = sum(len(p) for p in parts)
    remaining = budget - used
    if remaining < len(us_entry(FULL[-1])):
        raise RuntimeError(f"budget {budget} too small (need >= {used + len(us_entry(FULL[-1]))})")
    # Pad last name with spaces so total == budget
    body_budget = remaining - 1  # excludes length byte; includes trailing 0x00
    content = body_budget - 1
    if content < 0 or content % 2:
        raise RuntimeError(f"bad content budget {content}")
    base = FULL[-1].encode("utf-16le")
    if len(base) > content:
        raise RuntimeError("last day name too long")
    spaces = (content - len(base)) // 2
    last = FULL[-1] + (" " * spaces)
    out = b"".join(parts) + us_entry(last)
    if len(out) != budget:
        raise RuntimeError(f"packed {len(out)} != budget {budget}")
    return out


def patch_block(data: bytearray, start: int, expected: list[str], replacement: bytes) -> None:
    i = start
    for exp in expected:
        ln = data[i]
        payload = bytes(data[i + 1 : i + 1 + ln])
        if not payload or payload[-1] != 0:
            raise RuntimeError(f"bad entry at {i}")
        text = payload[:-1].decode("utf-16le")
        if text != exp:
            raise RuntimeError(f"expected {exp!r} at {i}, found {text!r}")
        i += 1 + ln
    size = i - start
    if len(replacement) != size:
        raise RuntimeError(f"replacement size {len(replacement)} != block {size}")
    data[start:i] = replacement


def find_abbrev_start(data: bytes) -> int:
    needle = b"\x07S\x00u\x00n\x00\x00"
    idx = 0
    while True:
        i = data.find(needle, idx)
        if i < 0:
            raise RuntimeError("abbrev Sun block not found")
        j = i
        ok = True
        for expect in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]:
            ln = data[j]
            payload = data[j + 1 : j + 1 + ln]
            try:
                text = payload[:-1].decode("utf-16le")
            except Exception:
                ok = False
                break
            if text != expect:
                ok = False
                break
            j += 1 + ln
        if ok:
            return i
        idx = i + 1


def find_full_start(data: bytes) -> int:
    needle = b"\x0dS\x00u\x00n\x00d\x00a\x00y\x00\x00"
    i = data.find(needle)
    if i < 0:
        raise RuntimeError("full Sunday block not found")
    return i


def apply(dll_path: Path) -> dict:
    raw = bytearray(dll_path.read_bytes())
    abbrev_at = find_abbrev_start(raw)
    full_at = find_full_start(raw)
    abbrev_repl = b"".join(us_entry(s) for s in ABBREV)
    # measure full block size
    i = full_at
    for exp in ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]:
        ln = raw[i]
        payload = bytes(raw[i + 1 : i + 1 + ln])
        text = payload[:-1].decode("utf-16le")
        if text != exp:
            raise RuntimeError(f"full day mismatch {exp!r} vs {text!r}")
        i += 1 + ln
    budget = i - full_at
    full_repl = pack_full_days(budget)

    patch_block(
        raw,
        abbrev_at,
        ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        abbrev_repl,
    )
    patch_block(
        raw,
        full_at,
        ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        full_repl,
    )
    dll_path.write_bytes(raw)
    return {
        "abbrev_at": abbrev_at,
        "full_at": full_at,
        "full_budget": budget,
        "abbrev": ABBREV,
        "full": FULL,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", type=Path, default=DEFAULT_GAME)
    ap.add_argument("--install", action="store_true", help="Patch game Managed/mscorlib.dll")
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "build" / "patch_mscorlib" / MSC,
    )
    args = ap.parse_args()

    src = args.game / "HuniePop_Data" / "Managed" / MSC
    if not src.is_file():
        print(f"missing {src}")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, args.out)
    info = apply(args.out)
    print(info)

    if args.install:
        backup = (
            ROOT
            / "assets"
            / "original"
            / f"backup_mscorlib_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, backup / MSC)
        shutil.copy2(args.out, src)
        print(f"installed {src} (backup {backup})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
