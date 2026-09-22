"""Fold pt_BR accents to ASCII base letters + light EU→BR colloquial tweaks.

Bitmap Exo fonts only have ASCII glyphs — accented chars vanish in-game.
User preference: nao/faco (keep letter) instead of dropping to no/fao.

Writes locale/pt-BR/unique_texts_ascii.csv (source of truth for binary expand).

Usage:
  python scripts/fold_ascii_pt.py
  python scripts/fold_ascii_pt.py --src locale/pt-BR/unique_texts.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "locale" / "pt-BR" / "unique_texts.csv"
OUT = ROOT / "locale" / "pt-BR" / "unique_texts_ascii.csv"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from locale_csv import read_locale_rows, write_locale_rows  # noqa: E402

# Common Argos EU-PT → more casual BR (applied on original before fold)
# Also: BR uses voce/voces (3rd-person verbs), never tu/vos.
COLLOQUIAL: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brapariga\b", re.I), "garota"),
    (re.compile(r"\braparigas\b", re.I), "garotas"),
    (re.compile(r"\bmiúda\b", re.I), "mina"),
    (re.compile(r"\bmiúdas\b", re.I), "minas"),
    (re.compile(r"\bputo\b", re.I), "cara"),  # EU slang
    (re.compile(r"\bfixe\b", re.I), "legal"),
    (re.compile(r"\bgiro\b", re.I), "bonito"),
    (re.compile(r"\bgira\b", re.I), "bonita"),
    (re.compile(r"\btelemóvel\b", re.I), "celular"),
    (re.compile(r"\btelemovel\b", re.I), "celular"),
    (re.compile(r"\bautocarro\b", re.I), "onibus"),
    (re.compile(r"\bpequeno-almoço\b", re.I), "cafe da manha"),
    (re.compile(r"\bpequeno almoço\b", re.I), "cafe da manha"),
    (re.compile(r"\badepto\b", re.I), "fa"),
    (re.compile(r"\bequipa\b", re.I), "time"),
    (re.compile(r"\bequipas\b", re.I), "times"),
    (re.compile(r"\bdesporto\b", re.I), "esporte"),
    (re.compile(r"\bcomboio\b", re.I), "trem"),
    (re.compile(r"\bfacto\b", re.I), "fato"),
    (re.compile(r"\bactual\b", re.I), "atual"),
    (re.compile(r"\bactualmente\b", re.I), "agora"),
    (re.compile(r"\bcontacto\b", re.I), "contato"),
    (re.compile(r"\bóptimo\b", re.I), "otimo"),
    (re.compile(r"\bótimo\b", re.I), "otimo"),
    (re.compile(r"\bà procura de\b", re.I), "procurando"),
    (re.compile(r"\bestá à procura\b", re.I), "ta procurando"),
    (re.compile(r"\bestá a procurar\b", re.I), "ta procurando"),
    # --- tu / vos → voce / voces (verbs in 3rd person) ---
    (re.compile(r"\bcontigo\b", re.I), "com voce"),
    (re.compile(r"\bconvosco\b", re.I), "com voces"),
    (re.compile(r"\bEi,\s*tu\b", re.I), "Ei, voce"),
    (re.compile(r"\bSim,\s*tu\b", re.I), "Sim, voce"),
    (re.compile(r"\bQuem és tu\b", re.I), "Quem e voce"),
    (re.compile(r"\bQuem es tu\b", re.I), "Quem e voce"),
    (re.compile(r"\bés tu\b", re.I), "e voce"),
    (re.compile(r"\bes tu\b", re.I), "e voce"),
    (re.compile(r"\bés só tu\b", re.I), "e so voce"),
    (re.compile(r"\bes so tu\b", re.I), "e so voce"),
    (re.compile(r"\bcomo tu\b", re.I), "como voce"),
    (re.compile(r"\bdo que tu\b", re.I), "do que voce"),
    (re.compile(r"\bsejas tu\b", re.I), "seja voce"),
    (re.compile(r"\bAí estás tu\b", re.I), "Ai esta voce"),
    (re.compile(r"\bAi estas tu\b", re.I), "Ai esta voce"),
    (re.compile(r"\bestás tu\b", re.I), "esta voce"),
    (re.compile(r"\bestas tu\b", re.I), "esta voce"),
    (re.compile(r"\bTu és\b"), "Voce e"),
    (re.compile(r"\bTu es\b"), "Voce e"),
    (re.compile(r"\btu és\b", re.I), "voce e"),
    (re.compile(r"\btu es\b", re.I), "voce e"),
    (re.compile(r"\bTu\b"), "Voce"),
    (re.compile(r"\btu\b"), "voce"),
    (re.compile(r"\bvós\b", re.I), "voces"),
    (re.compile(r"\bvosso\b", re.I), "seu"),
    (re.compile(r"\bvossa\b", re.I), "sua"),
    (re.compile(r"\bvossos\b", re.I), "seus"),
    (re.compile(r"\bvossas\b", re.I), "suas"),
    (re.compile(r"\bpara vos\b", re.I), "pra voces"),
    (re.compile(r"\bassegurar-vos\b", re.I), "assegurar voces"),
    (re.compile(r"\bdar-vos\b", re.I), "dar pra voces"),
    (re.compile(r"\bvos dar\b", re.I), "dar pra voces"),
    (re.compile(r"\bvos\b", re.I), "voces"),
    (re.compile(r"\bpara ti\b", re.I), "pra voce"),
    (re.compile(r"\bpor ti\b", re.I), "por voce"),
    (re.compile(r"\bde ti\b", re.I), "de voce"),
    (re.compile(r"\bteu\b", re.I), "seu"),
    (re.compile(r"\btua\b", re.I), "sua"),
    (re.compile(r"\bteus\b", re.I), "seus"),
    (re.compile(r"\btuas\b", re.I), "suas"),
    # tu verbs → voce (3rd person); keep BR clitics like "te" (ok with voce)
    (re.compile(r"\bsejas\b", re.I), "seja"),
    (re.compile(r"\bem ti\b", re.I), "em voce"),
    (re.compile(r"\ba ti\b", re.I), "a voce"),
    (re.compile(r"\bde ti\b", re.I), "de voce"),
    (re.compile(r"\bpor ti\b", re.I), "por voce"),
    (re.compile(r"\bsobre ti\b", re.I), "sobre voce"),
    (re.compile(r"\bcom ti\b", re.I), "com voce"),
    (re.compile(r"\bsem ti\b", re.I), "sem voce"),
    (re.compile(r"\bpara ti\b", re.I), "pra voce"),
    (re.compile(r"\bestava a ler\b", re.I), "tava lendo"),
    (re.compile(r"\bestava a pensar\b", re.I), "tava pensando"),
    (re.compile(r"\bestava a (?=\w+)", re.I), "tava "),
    (re.compile(r"\bestou a (?=\w+)", re.I), "to "),
    (re.compile(r"\bestás a (?=\w+)", re.I), "ta "),
    (re.compile(r"\bestas a (?=\w+)", re.I), "ta "),
    (re.compile(r"\bvais\b", re.I), "vai"),
    (re.compile(r"\btens\b", re.I), "tem"),
    (re.compile(r"\bqueres\b", re.I), "quer"),
    (re.compile(r"\bpodes\b", re.I), "pode"),
    (re.compile(r"\bfazes\b", re.I), "faz"),
    (re.compile(r"\bdizes\b", re.I), "diz"),
    (re.compile(r"\bsabes\b", re.I), "sabe"),
    (re.compile(r"\bgostas\b", re.I), "gosta"),
    (re.compile(r"\bolhas\b", re.I), "olha"),
    (re.compile(r"\bouves\b", re.I), "ouve"),
    (re.compile(r"\bfalas\b", re.I), "fala"),
    (re.compile(r"\bamas\b", re.I), "ama"),
    (re.compile(r"\bprecisas\b", re.I), "precisa"),
    (re.compile(r"\bpensas\b", re.I), "pensa"),
    (re.compile(r"\bachas\b", re.I), "acha"),
    (re.compile(r"\bentendes\b", re.I), "entende"),
    (re.compile(r"\bconheces\b", re.I), "conhece"),
    (re.compile(r"\blembras-te\b", re.I), "lembra"),
    (re.compile(r"\blembras\b", re.I), "lembra"),
    (re.compile(r"\bquereres\b", re.I), "querer"),
    (re.compile(r"\bquiseres\b", re.I), "quiser"),
    (re.compile(r"\bfizeste\b", re.I), "fez"),
    (re.compile(r"\bdisseste\b", re.I), "disse"),
    (re.compile(r"\bviste\b", re.I), "viu"),
    (re.compile(r"\bfoste\b", re.I), "foi"),
    (re.compile(r"\bvieste\b", re.I), "veio"),
    (re.compile(r"\btrouxeste\b", re.I), "trouxe"),
    (re.compile(r"\badoraste\b", re.I), "adorou"),
    (re.compile(r"\bFormaste-te\b"), "Voce se formou"),
    (re.compile(r"\bformaste-te\b", re.I), "voce se formou"),
    (re.compile(r"\bserás\b", re.I), "vai ser"),
    (re.compile(r"\bseras\b", re.I), "vai ser"),
    (re.compile(r"\bfosses\b", re.I), "fosse"),
    (re.compile(r"\btendes\b", re.I), "tem"),
    (re.compile(r"\bfazeis\b", re.I), "fazem"),
    (re.compile(r"\bquereis\b", re.I), "querem"),
    (re.compile(r"\bpodeis\b", re.I), "podem"),
    (re.compile(r"\bsois\b", re.I), "sao"),
    (re.compile(r"\bestais\b", re.I), "estao"),
    # estás / estas (tu) — avoid demonstrative "estas cores/coisas/..."
    (
        re.compile(
            r"\best[aá]s\b(?!\s+(?:cores|coisas|meninas|garotas|gajas|pastas|raparigas|"
            r"pessoas|horas|vezes|palavras|fotos|livros|cartas|notas|roupas|minas))",
            re.I,
        ),
        "esta",
    ),
    # EU progressive "esta(s) a + inf" → BR "ta + gerund-ish / esta"
    (re.compile(r"\besta a (?=\w+)", re.I), "ta "),
    (re.compile(r"\bnão é\b", re.I), "nao e"),
    (re.compile(r"\bacção\b", re.I), "acao"),
    (re.compile(r"\bacções\b", re.I), "acoes"),
    (re.compile(r"\bafecte\b", re.I), "afete"),
    (re.compile(r"\bafecta\b", re.I), "afeta"),
    (re.compile(r"\baccão\b", re.I), "acao"),
    (re.compile(r"\baccao\b", re.I), "acao"),
    (re.compile(r"\baccoes\b", re.I), "acoes"),
    (re.compile(r"\bAccao\b"), "Acao"),
    (re.compile(r"\bÉ uma\b"), "E uma"),
    (re.compile(r"\bÉ um\b"), "E um"),
]


def fold_ascii(text: str) -> str:
    """NFKD + drop combining marks → base Latin letters (ç→c, ã→a)."""
    if not text:
        return text
    # Fancy punctuation → ASCII (also missing from bitmap fonts)
    repl = {
        "\u2014": "-",  # em dash
        "\u2013": "-",  # en dash
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00ab": '"',
        "\u00bb": '"',
        "\u00b7": ".",  # middle dot
        "\u2022": "-",  # bullet
        "\u00ad": "",  # soft hyphen
        "\u2026": "...",
        "\u25a1": "",  # white square (junk)
    }
    for a, b in repl.items():
        text = text.replace(a, b)
    norm = unicodedata.normalize("NFKD", text)
    out = "".join(ch for ch in norm if not unicodedata.combining(ch))
    # Drop any remaining non-ASCII that isn't printable Latin
    return "".join(ch if ord(ch) < 128 else "" for ch in out)


def colloquialize(text: str) -> str:
    out = text
    for pat, repl in COLLOQUIAL:
        out = pat.sub(repl, out)
    return out


def transform(text: str) -> str:
    return fold_ascii(colloquialize(text))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    rows, _ = read_locale_rows(args.src)
    if not rows or "pt_BR" not in rows[0]:
        print("CSV needs pt_BR column")
        return 1

    changed = 0
    accented = 0
    for row in rows:
        old = row.get("pt_BR") or ""
        new = transform(old)
        if any(unicodedata.combining(c) or ord(c) > 127 for c in unicodedata.normalize("NFKD", old)):
            if old != fold_ascii(old):
                accented += 1
        if new != old:
            changed += 1
        row["pt_BR"] = new

    fieldnames = list(rows[0].keys())
    if "char_diff" not in fieldnames and "pt_BR" in fieldnames:
        i = fieldnames.index("pt_BR") + 1
        fieldnames = fieldnames[:i] + ["char_diff"] + fieldnames[i:]
    elif "char_diff" not in fieldnames:
        fieldnames = fieldnames + ["char_diff"]
    # stable order: char_diff right after pt_BR
    if "pt_BR" in fieldnames and "char_diff" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "char_diff"]
        fieldnames.insert(fieldnames.index("pt_BR") + 1, "char_diff")

    text_i = fieldnames.index("text") + 1
    pt_i = fieldnames.index("pt_BR") + 1

    def _excel_col(n: int) -> str:
        s = ""
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    # Excel consumes sep=$: header=row1, data from row2
    for i, row in enumerate(rows):
        row["char_diff"] = (
            f"=LEN({_excel_col(pt_i)}{i + 2})-LEN({_excel_col(text_i)}{i + 2})"
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_locale_rows(args.out, rows, fieldnames)

    print(f"rows={len(rows)} changed={changed} had_accents~={accented} -> {args.out}")
    # samples
    samples = [
        ("Não tenha",),
        ("faço",),
        ("rapariga",),
        ("Acção",),
    ]
    for row in rows[:50]:
        pass
    shown = 0
    for row in rows:
        pt = row["pt_BR"]
        en = row.get("text") or ""
        if shown >= 8:
            break
        if any(x in (row.get("pt_BR") or "") for x in ("nao ", "garota", "faco", "cao")):
            print(f"  EN: {en[:60]!r}")
            print(f"  PT: {pt[:80]!r}")
            shown += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
