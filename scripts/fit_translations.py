"""Shrink pt_BR so each line fits HuniePop in-place byte budget (len UTF-8 <= EN).

Writes locale/pt-BR/unique_texts_fitted.csv for apply_patch_inplace.py.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "locale" / "pt-BR" / "unique_texts.csv"
OUT = ROOT / "locale" / "pt-BR" / "unique_texts_fitted.csv"


def utf8_len(s: str) -> int:
    return len(s.encode("utf-8"))


def fit_utf8(text: str, max_bytes: int) -> str:
    if max_bytes <= 0:
        return ""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    cut = raw[:max_bytes]
    while cut:
        try:
            s = cut.decode("utf-8")
            break
        except UnicodeDecodeError:
            cut = cut[:-1]
    else:
        return ""
    # Prefer breaking on last space if we keep enough content
    if " " in s and utf8_len(s) > 6:
        head = s.rsplit(" ", 1)[0]
        if utf8_len(head) >= max(3, max_bytes // 3):
            s = head
    return s.rstrip(" ,.;:!")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    rows = list(csv.DictReader(args.src.open(encoding="utf-8")))
    fields = list(rows[0].keys())
    if "fit_note" not in fields:
        fields.append("fit_note")

    kept = shortened = dropped = empty = 0
    out_rows = []
    for row in rows:
        en = row["text"]
        pt = (row.get("pt_BR") or "").strip()
        note = ""
        if not pt:
            empty += 1
            row = dict(row)
            row["fit_note"] = "empty"
            out_rows.append(row)
            continue
        max_b = utf8_len(en)
        if utf8_len(pt) <= max_b:
            kept += 1
            note = "ok"
            fitted = pt
        else:
            fitted = fit_utf8(pt, max_b)
            if not fitted or utf8_len(fitted) > max_b:
                dropped += 1
                note = "drop"
                fitted = ""
            else:
                shortened += 1
                note = f"shortened:{utf8_len(pt)}->{utf8_len(fitted)}"
        row = dict(row)
        row["pt_BR"] = fitted
        row["fit_note"] = note
        out_rows.append(row)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    usable = sum(1 for r in out_rows if (r.get("pt_BR") or "").strip())
    print(
        f"wrote {args.out} usable={usable} kept={kept} shortened={shortened} "
        f"dropped={dropped} empty={empty}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
