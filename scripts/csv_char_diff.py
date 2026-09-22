"""Add/refresh `char_diff` on locale CSVs (human reference only).

Patch scripts only read `text` + `pt_BR` — char_diff / sep= line are ignored.

Excel BR forces ';' on normal CSV. We force the delimiter with a first line:
  sep=$
and separate columns with '$' — confirmed absent from HuniePop EN dialogue.
UTF-8 BOM for accents. char_diff = =LEN(pt)-LEN(en) (live in Excel).

Usage:
  python scripts/csv_char_diff.py
  python scripts/csv_char_diff.py --static
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = [
    ROOT / "locale" / "pt-BR" / "unique_texts.csv",
    ROOT / "locale" / "pt-BR" / "unique_texts_ascii.csv",
    ROOT / "locale" / "pt-BR" / "unique_texts_fitted.csv",
    ROOT / "locale" / "pt-BR" / "menus_only.csv",
    ROOT / "locale" / "pt-BR" / "pilot.csv",
    ROOT / "locale" / "pt-BR" / "safe_partial.csv",
]

CHAR_DIFF_COL = "char_diff"
# Absent from HuniePop EN (+ current PT). Not comma/semicolon/parens.
DELIMITER = "$"
SEP_LINE = f"sep={DELIMITER}"


def excel_col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def detect_delimiter(header_line: str) -> str:
    if header_line.startswith("sep=") and len(header_line) >= 5:
        return header_line.split("=", 1)[1][:1] or DELIMITER
    if header_line.count("\t") >= 2:
        return "\t"
    if header_line.count("$") >= 2:
        return "$"
    if header_line.count(";") >= 2:
        return ";"
    if header_line.count(",") >= 2:
        return ","
    return DELIMITER


def read_csv(path: Path) -> tuple[list[dict], list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    lines = [ln for ln in text.splitlines() if ln.strip() or ln == ""]
    # drop blank-only
    lines = text.splitlines()
    if not lines:
        return [], []
    if lines[0].lower().startswith("sep="):
        delim = detect_delimiter(lines[0])
        data_lines = lines[1:]
    else:
        delim = detect_delimiter(lines[0])
        data_lines = lines
    if not data_lines:
        return [], []
    rows = list(csv.DictReader(data_lines, delimiter=delim))
    if not rows:
        return [], []
    return rows, list(rows[0].keys())


def format_char_diff_static(en: str, pt: str) -> str:
    d = len(pt or "") - len(en or "")
    return f"{d:+d}" if d else "0"


def ensure_fieldnames(fields: list[str]) -> list[str]:
    fields = [f for f in fields if f != CHAR_DIFF_COL]
    if "pt_BR" in fields:
        i = fields.index("pt_BR") + 1
        return fields[:i] + [CHAR_DIFF_COL] + fields[i:]
    return fields + [CHAR_DIFF_COL]


def formula_for_row(fields: list[str], row_1based: int) -> str:
    # +1 because Excel row 1 will be sep=$, row 2 = header, data starts row 3
    text_i = fields.index("text") + 1
    pt_i = fields.index("pt_BR") + 1
    return f"=LEN({excel_col(pt_i)}{row_1based})-LEN({excel_col(text_i)}{row_1based})"


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path = path.with_suffix(".csv")  # always .csv so Excel is default app
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        f.write(SEP_LINE + "\r\n")
        w = csv.DictWriter(
            f,
            fieldnames=fields,
            delimiter=DELIMITER,
            quoting=csv.QUOTE_MINIMAL,
            extrasaction="ignore",
            lineterminator="\r\n",
        )
        w.writeheader()
        w.writerows(rows)


def refresh_csv(path: Path, *, static: bool) -> int:
    rows, _ = read_csv(path)
    if not rows or "text" not in rows[0] or "pt_BR" not in rows[0]:
        print(f"skip {path}: need text,pt_BR", file=sys.stderr)
        return 0

    fields = ensure_fieldnames(list(rows[0].keys()))
    # Excel consumes sep=$ (not shown as a row): header=row1, data from row2
    for i, row in enumerate(rows):
        if static:
            row[CHAR_DIFF_COL] = format_char_diff_static(
                row.get("text") or "", row.get("pt_BR") or ""
            )
        else:
            row[CHAR_DIFF_COL] = formula_for_row(fields, i + 2)

    out = path.with_suffix(".csv")
    write_csv(out, rows, fields)
    if path.resolve() != out.resolve() and path.exists() and path.suffix.lower() == ".tsv":
        path.unlink()
    filled = sum(1 for r in rows if (r.get("pt_BR") or "").strip())
    mode = "static" if static else "excel-formula"
    print(f"{out.name}: rows={len(rows)} filled={filled} delim=$ sep= line char_diff={mode}")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csvs", nargs="*", type=Path, default=None)
    ap.add_argument("--static", action="store_true")
    args = ap.parse_args()
    paths = list(args.csvs) if args.csvs else list(DEFAULTS)
    # also accept leftover .tsv
    if not args.csvs:
        for p in list(paths):
            tsv = p.with_suffix(".tsv")
            if tsv.is_file() and not p.is_file():
                paths[paths.index(p)] = tsv
    for p in paths:
        if not p.is_file():
            # try .tsv sibling
            alt = p.with_suffix(".tsv")
            if alt.is_file():
                p = alt
            else:
                print(f"missing {p}", file=sys.stderr)
                continue
        refresh_csv(p, static=args.static)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
