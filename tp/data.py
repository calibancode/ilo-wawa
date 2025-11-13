# data.py
# -------------------------------------------------------------------
# load toki pona glyph data from primary JSON + supplemental sources
# -------------------------------------------------------------------

import json
import os
import re
from typing import List, Dict, Tuple

from log import log


# -------------------------------------------------------------------

class VocabEntry:
    __slots__ = ("word", "cp", "gloss", "semantic_long", "url_long")

    def __init__(self, word: str, cp: int, gloss: str,
                 semantic_long: str, url_long: str | None):
        self.word = word
        self.cp = cp
        self.gloss = gloss
        self.semantic_long = semantic_long
        self.url_long = url_long


TP_TO_UCSUR: Dict[str, int] = {}

VOCAB_MAP: Dict[str, VocabEntry] = {}


# -------------------------------------------------------------------
# UTILITY
# -------------------------------------------------------------------

def _clean_tp_name(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"\s*\(.*?\)\s*", "", name)
    name = name.replace("-", "+")
    return name


# -------------------------------------------------------------------
# PRIMARY DATA LOADER
# -------------------------------------------------------------------

def load_primary_data(path: str) -> Tuple[str, List[VocabEntry]]:
    if not os.path.exists(path):
        msg = f"primary data file missing: {path}"
        log.info(msg)
        return msg, []

    log.info(f"loading primary semantic data: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        msg = f"error parsing primary data: {e}"
        log.info(msg)
        return msg, []

    vocab_list: List[VocabEntry] = []

    VOCAB_MAP.clear()
    TP_TO_UCSUR.clear()

    for item in raw:
        word = item.get("word", "").lower().strip()
        if not word:
            continue

        try:
            cp = int(item.get("codepoint", "").replace("U+", ""), 16)
        except Exception:
            continue

        gloss = item.get("definition", "").strip()
        raw_sem = item.get("semantic_space")

        if isinstance(raw_sem, str):
            semantic_long = raw_sem.strip()
        else:
            semantic_long = ""

        url_long = f"https://lipamanka.gay/essays/dictionary#{word}"

        entry = VocabEntry(word, cp, gloss, semantic_long, url_long)

        vocab_list.append(entry)
        VOCAB_MAP[word] = entry
        TP_TO_UCSUR[word] = cp

    # syn: ali → ale
    if "ale" in TP_TO_UCSUR:
        TP_TO_UCSUR["ali"] = TP_TO_UCSUR["ale"]

    log.info(f"loaded {len(vocab_list)} primary glyph entries")
    return "ok", vocab_list


# -------------------------------------------------------------------
# SUPPLEMENTARY LOADER (juniko etc.)
# provides extra ASCII aliases and special glyphs
# -------------------------------------------------------------------

def load_supplementary(path: str) -> str:
    if not os.path.exists(path):
        msg = f"supplementary file not found: {path}"
        log.info(msg)
        return msg

    log.info(f"loading supplementary glyph data: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        msg = f"error parsing supplementary data: {e}"
        log.info(msg)
        return msg

    added = 0

    for item in raw:
        name = _clean_tp_name(item.get("name", ""))
        if not name:
            continue

        if name in TP_TO_UCSUR:
            continue

        try:
            cp = int(item.get("code_hex", "").replace("U+", ""), 16)
        except Exception:
            continue

        TP_TO_UCSUR[name] = cp
        added += 1

    msg = f"added {added} supplementary glyphs"
    log.info(msg)
    return msg


# -------------------------------------------------------------------
# COMBINED ENTRY POINT
# -------------------------------------------------------------------

def load_all_data(primary_path: str,
                  supplementary_path: str) -> Tuple[str, List[VocabEntry]]:
    log.info("loading unified toki pona data…")

    status_primary, vocab = load_primary_data(primary_path)

    status_extra = load_supplementary(supplementary_path)

    final_msg = f"{status_primary}; {status_extra}"
    return final_msg, vocab
