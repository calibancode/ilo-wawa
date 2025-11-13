# corpus.py
# -------------------------------------------------------------------
# semantic search engine using English→Toki Pona parallel corpus
# -------------------------------------------------------------------

import os
import csv
import pickle
import hashlib
import re
from collections import defaultdict
from typing import List, Tuple

from log import log

# stopwords to exclude from frequency scoring
TOKIPONA_STOPWORDS = {
    "li", "e", "pi", "mi", "ona",
}

WORD_RE = re.compile(r"[a-zA-Z]+")


# -------------------------------------------------------------------

class CorpusSearcher:
    """loads TSV sentence pairs, builds an English→TP semantic index,
    caches vectors, and performs similarity search using spaCy docs.
    """

    def __init__(self, owner, nlp, corpus_path: str):
        self.owner = owner
        self.nlp = nlp
        self.corpus_path = corpus_path

        self.indexed_corpus: List[Tuple["Doc", List[str]]] = []

        cache_file = self._make_cache_filename()

        if not self._load_cache(cache_file):
            self._index_and_save(cache_file)

    # ----------------------------------------------------------------

    def _make_cache_filename(self) -> str:
        """unique cache name based on corpus file + spaCy model version."""
        base = os.path.basename(self.corpus_path)
        model = self.nlp.meta.get("name", "model")
        return f"{base}_{model}.cache.pkl"

    def _source_hash(self) -> str:
        """content hash of TSV file to detect changes."""
        h = hashlib.md5()
        with open(self.corpus_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()

    # ----------------------------------------------------------------

    def _load_cache(self, path: str) -> bool:
        """try loading cached vectors."""
        if not os.path.exists(path):
            log.info("no corpus cache found")
            return False

        try:
            log.info(f"loading corpus cache: {path}")
            with open(path, "rb") as f:
                data = pickle.load(f)

            if data.get("source_hash") != self._source_hash():
                log.info("cache mismatch: corpus changed, rebuilding")
                return False

            self.indexed_corpus = data["indexed_corpus"]
            log.info(f"loaded {len(self.indexed_corpus)} cached entries")
            return True

        except Exception as e:
            log.info(f"failed to load cache: {e}")
            return False

    # ----------------------------------------------------------------

    def _index_and_save(self, path: str):
        """index TSV file and save vector cache."""
        log.info(f"indexing corpus (cold start): {self.corpus_path}")

        english_list = []
        tp_lists = []
        seen_english = set()

        try:
            with open(self.corpus_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                for row in reader:
                    if len(row) < 4:
                        continue

                    en = row[1].strip()
                    tp = row[3].strip().lower()

                    if not en or not tp:
                        continue

                    if en in seen_english:
                        continue
                    seen_english.add(en)

                    words = WORD_RE.findall(tp)
                    words = [w for w in words if w not in TOKIPONA_STOPWORDS]

                    if not words:
                        continue

                    english_list.append(en)
                    tp_lists.append(words)

        except FileNotFoundError:
            log.info(f"corpus file missing: {self.corpus_path}")
            return

        log.info(f"{len(english_list)} usable corpus sentences")

        docs = self.nlp.pipe(english_list, disable=["parser", "ner"])

        self.indexed_corpus = []
        for doc, words in zip(docs, tp_lists):
            if doc.has_vector and doc.vector_norm > 0:
                self.indexed_corpus.append((doc, words))

        log.info(f"indexed {len(self.indexed_corpus)} semantic vectors")

        # save cache
        try:
            with open(path, "wb") as f:
                pickle.dump(
                    {
                        "source_hash": self._source_hash(),
                        "indexed_corpus": self.indexed_corpus,
                    },
                    f,
                )
            log.info("saved new corpus cache")
        except Exception as e:
            log.info(f"failed to save cache: {e}")

    # ----------------------------------------------------------------

    def search(self, query: str, top_n_sentences: int = 25) -> List[Tuple[str, int]]:
        """return ranked toki pona words for semantic query."""
        if not self.indexed_corpus or not query:
            return []

        qdoc = self.nlp(query)
        q_lower = query.lower()

        if not (qdoc.has_vector and qdoc.vector_norm > 0):
            return []

        allowed = None
        if q_lower in TOKIPONA_STOPWORDS:
            allowed = q_lower
            return []

        scored = []
        for doc, tp_words in self.indexed_corpus:
            sim = qdoc.similarity(doc)
            scored.append((sim, tp_words))

        scored.sort(key=lambda x: x[0], reverse=True)

        freqs = defaultdict(int)
        for _, words in scored[:top_n_sentences]:
            for w in words:
                if w not in TOKIPONA_STOPWORDS or w == allowed:
                    freqs[w] += 1

        if not freqs:
            return []

        return sorted(freqs.items(), key=lambda x: x[1], reverse=True)
