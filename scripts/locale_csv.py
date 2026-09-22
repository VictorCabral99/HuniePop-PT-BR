"""Shared locale CSV IO: sep=$ + $ delimiter (Excel BR safe)."""
from __future__ import annotations

import csv
from pathlib import Path

DELIMITER = "$"
SEP_LINE = f"sep={DELIMITER}"


def detect_delimiter(header_line: str) -> str:
    if header_line.lower().startswith("sep=") and len(header_line) >= 5:
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


def read_locale_rows(path: Path) -> tuple[list[dict], list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    if not lines:
        return [], []
    if lines[0].lower().startswith("sep="):
        delim = detect_delimiter(lines[0])
        data = lines[1:]
    else:
        delim = detect_delimiter(lines[0])
        data = lines
    if not data:
        return [], []
    rows = list(csv.DictReader(data, delimiter=delim))
    if not rows:
        return [], []
    return rows, list(rows[0].keys())


def write_locale_rows(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    if not rows:
        raise ValueError("no rows")
    fields = fields or list(rows[0].keys())
    path = path.with_suffix(".csv")
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
