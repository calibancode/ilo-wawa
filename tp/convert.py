# convert.py
# -------------------------------------------------------------------
# sitelen lasina → UCSUR converter
# token parser + mapping using TP_TO_UCSUR from data.py
# -------------------------------------------------------------------

import re
from dataclasses import dataclass
from typing import List

from data import TP_TO_UCSUR


# -------------------------------------------------------------------
# TOKENS
# -------------------------------------------------------------------

# regex tokenizing latin words, ascii controls, joiners, punctuation, etc.
TOK_RE = re.compile(
    r"\r\n|\r|\n|"              # newlines
    r"[ \t]+|"                  # spaces/tabs
    r"[A-Za-z][A-Za-z0-9+-]*|"  # toki pona words w/ possible '+' or '-'
    r"[\[\]\(\)\{\}\-+._:=]|"   # ASCII UCSUR controls
    r"."                        # fallback catch-all
)

# variation selector block (digits 1–8)
VAR_TAIL_RE = re.compile(
    r"^(?P<word>[A-Za-z][A-Za-z-]*?)(?P<var>[1-8]+)$"
)

# ASCII → UCSUR symbol mapping
ASCII_TO_UCSUR = {
    "[": 0xF1990,
    "]": 0xF1991,
    "=": 0xF1992,
    "(": 0xF1997,
    ")": 0xF1998,
    "_": 0xF1999,
    "{": 0xF199A,
    "}": 0xF199B,
    "-": 0xF1995,
    "+": 0xF1996,
    ".": 0xF199C,
    ":": 0xF199D,
}

# variation selectors U+E0101…U+E0108
VARIATION_BY_DIGIT = {
    str(i): 0xE0100 + (i - 1) for i in range(1, 9)
}


# -------------------------------------------------------------------
# OPTIONS
# -------------------------------------------------------------------

@dataclass
class Options:
    allow_ascii: bool = True
    pass_unknown: bool = True
    remove_spaces: bool = True
    preserve_newlines: bool = True


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def _ch(cp: int) -> str:
    return chr(cp)


def _emit_variations(digits: str) -> str:
    return "".join(
        chr(VARIATION_BY_DIGIT[d])
        for d in digits if d in VARIATION_BY_DIGIT
    )


def _tp_to_ucsur(word: str) -> str:
    """map toki pona word → UCSUR glyph, or return original if missing"""
    cp = TP_TO_UCSUR.get(word.lower())
    return chr(cp) if cp is not None else word


def _expand_join_compound(tok: str, opts: Options, out: List[str]) -> bool:
    """
    Handle tokens like 'toki+pona' or 'toki-pona'.
    Returns True if handled, False if caller should fallback.
    """
    if "+" not in tok and "-" not in tok:
        return False

    if not tok[0].isalpha():
        return False

    parts = re.split(r"([\-+])", tok)
    had_any = False

    for p in parts:
        if not p:
            continue

        if p == "-":
            if opts.allow_ascii:
                out.append(_ch(ASCII_TO_UCSUR["-"]))
                had_any = True
            continue

        if p == "+":
            out.append("\u200D")
            had_any = True
            continue

        glyph = _tp_to_ucsur(p)
        if glyph == p and not opts.pass_unknown:
            continue
        out.append(glyph)
        had_any = True

    return had_any


# -------------------------------------------------------------------
# MAIN CONVERSION
# -------------------------------------------------------------------

def convert_text(text: str, opts: Options) -> str:
    """convert sitelen lasina → UCSUR using cleaned token rules"""
    out: List[str] = []

    for tok in TOK_RE.findall(text):
        if not tok:
            continue

        # newlines
        if tok in ("\r\n", "\r", "\n"):
            out.append(tok if opts.preserve_newlines else "")
            continue

        # spaces / tabs
        if tok.isspace():
            if opts.remove_spaces:
                continue
            out.append(tok)
            continue

        # literal ZWJ / ZWNJ passed through
        if tok in ("\u200D", "\u200C"):
            out.append(tok)
            continue

        # standalone ASCII controls → UCSUR
        if opts.allow_ascii and tok in ASCII_TO_UCSUR:
            out.append(_ch(ASCII_TO_UCSUR[tok]))
            continue

        # ------------------------------------------------------
        # NEW: for tokens with '+', prefer explicit compound
        # expansion (word+word → word ZWJ word) over any
        # monolithic TP_TO_UCSUR mapping (e.g. juniko ligatures)
        # ------------------------------------------------------
        if "+" in tok:
            if _expand_join_compound(tok, opts, out):
                continue

        # direct word → glyph (primary data + supplementary)
        low = tok.lower()
        if low in TP_TO_UCSUR:
            out.append(chr(TP_TO_UCSUR[low]))
            continue

        # word with variation digits, e.g. toki2, ni33
        m = VAR_TAIL_RE.match(tok)
        if m:
            base = m.group("word")
            variations = m.group("var")

            glyph = _tp_to_ucsur(base)
            if glyph == base and not opts.pass_unknown:
                glyph = ""

            out.append(glyph + _emit_variations(variations))
            continue

        # last-resort compound handling (still handles things
        # like toki-pona by inserting the stack mark + glyphs
        # when there's no direct mapping)
        if _expand_join_compound(tok, opts, out):
            continue

        # unknown token
        out.append(tok if opts.pass_unknown else "")

    return "".join(out)
