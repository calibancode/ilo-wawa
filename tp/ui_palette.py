# ui_palette.py
# -------------------------------------------------------------------
# glyph palette dock: searchable, semantic-search-aware, details menu
# -------------------------------------------------------------------

from __future__ import annotations

from PySide6.QtCore import Qt, QSize, QTimer, QPoint
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QCheckBox, QSpinBox, QScrollArea, QGridLayout, QPushButton,
    QFrame, QDockWidget, QMenu, QApplication
)

from data import VOCAB_MAP, VocabEntry
from corpus import CorpusSearcher
from log import log


class GlyphPaletteDock(QDockWidget):
    """the glyph list sidebar: grid of glyph buttons w/ search + semantic search"""

    def __init__(self, owner):
        super().__init__("glyphs")
        self.owner = owner
        self.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.setObjectName("GlyphPaletteDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        container = QWidget()
        self.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ------------------------------------------------------------
        # search bar + mode
        # ------------------------------------------------------------
        row = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("search: word / gloss / concept…")
        self.filter.textChanged.connect(self._schedule_rebuild)
        row.addWidget(self.filter, 1)

        self.mode = QComboBox()
        self.mode.addItems(["insert latin", "insert glyph"])
        row.addWidget(self.mode)

        root.addLayout(row)

        # ------------------------------------------------------------
        # semantic search options
        # ------------------------------------------------------------
        opt_row = QHBoxLayout()

        self.semantic_check = QCheckBox("semantic")
        self.semantic_check.toggled.connect(self._update_semantic_state)
        self.semantic_check.toggled.connect(self._schedule_rebuild)
        opt_row.addWidget(self.semantic_check)

        opt_row.addWidget(QLabel("top:"))
        self.top_n = QSpinBox()
        self.top_n.setRange(10, 1000)
        self.top_n.setValue(100)
        self.top_n.valueChanged.connect(self._schedule_rebuild)
        opt_row.addWidget(self.top_n)

        opt_row.addWidget(QLabel("min relevance:"))
        self.min_rel = QSpinBox()
        self.min_rel.setRange(1, 100)
        self.min_rel.setValue(20)
        self.min_rel.valueChanged.connect(self._schedule_rebuild)
        opt_row.addWidget(self.min_rel)

        root.addLayout(opt_row)

        self.semantic_check.setEnabled(False)
        self.top_n.setEnabled(False)
        self.min_rel.setEnabled(False)

        # ------------------------------------------------------------
        # sizing
        # ------------------------------------------------------------
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("size:"))
        self.btn_size = QSpinBox()
        self.btn_size.setRange(18, 96)
        self.btn_size.setValue(28)
        self.btn_size.valueChanged.connect(self._schedule_rebuild)
        size_row.addWidget(self.btn_size)
        size_row.addStretch(1)

        root.addLayout(size_row)

        # ------------------------------------------------------------
        # scroll area for grid
        # ------------------------------------------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.gridwrap = QWidget()
        self.grid = QGridLayout(self.gridwrap)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll.setWidget(self.gridwrap)
        root.addWidget(self.scroll, 1)

        self.footer = QLabel("0 shown")
        root.addWidget(self.footer)

        # ------------------------------------------------------------
        # internal state
        # ------------------------------------------------------------
        self.entries = []
        self.buttons = {}
        self.rebuild_timer = QTimer(self)
        self.rebuild_timer.setSingleShot(True)
        self.rebuild_timer.setInterval(250)
        self.rebuild_timer.timeout.connect(self._rebuild)

        self._is_rebuilding = False
        self.nlp = None
        self.corpus = None

    # ------------------------------------------------------------
    # external API
    # ------------------------------------------------------------

    def set_vocab(self, vocab_list):
        self.entries = vocab_list
        self._init_nlp()
        self._rebuild()

    def refresh_fonts(self):
        self._schedule_rebuild()

    # ------------------------------------------------------------
    # NLP & semantic search init
    # ------------------------------------------------------------

    def _init_nlp(self):
        if self.nlp is not None:
            return

        log.info("loading spaCy model…")

        try:
            import spacy
            self.nlp = spacy.load("en_core_web_lg")
        except Exception as e:
            log.info(f"failed to load spaCy: {e}")
            self.semantic_check.setEnabled(False)
            return

        log.info("initializing semantic corpus…")

        try:
            self.corpus = CorpusSearcher(self.owner, self.nlp, "tatoeba.tsv")
        except Exception as e:
            log.info(f"failed to init corpus searcher: {e}")
            self.semantic_check.setEnabled(False)
            return

        self.semantic_check.setEnabled(True)
        self._update_semantic_state()

    # ------------------------------------------------------------
    # delayed rebuild scheduling
    # ------------------------------------------------------------

    def _schedule_rebuild(self):
        self.rebuild_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_rebuild()

    # ------------------------------------------------------------
    # semantic toggle
    # ------------------------------------------------------------

    def _update_semantic_state(self):
        enabled = self.semantic_check.isChecked() and self.corpus is not None
        self.top_n.setEnabled(enabled)
        self.min_rel.setEnabled(enabled)

    # ------------------------------------------------------------
    # context menu per glyph
    # ------------------------------------------------------------

    def _context_menu(self, word: str, button: QPushButton, pos: QPoint):
        menu = QMenu(button)

        act_details = menu.addAction("details…")
        menu.addSeparator()
        act_ins_latin = menu.addAction("insert latin")
        act_ins_glyph = menu.addAction("insert glyph")


        action = menu.exec(button.mapToGlobal(pos))
        if not action:
            return

        if action is act_ins_latin:
            self.mode.setCurrentIndex(0)
            self._insert(word)

        elif action is act_ins_glyph:
            self.mode.setCurrentIndex(1)
            self._insert(word)

        elif action is act_details:
            self.owner.show_glyph_details(word)

    # ------------------------------------------------------------
    # rebuild the grid
    # ------------------------------------------------------------

    def _rebuild(self):
        if self._is_rebuilding:
            return

        self._is_rebuilding = True
        try:
            while self.grid.count():
                item = self.grid.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            self.buttons.clear()

            query = self.filter.text().strip().lower()
            is_sem = bool(query) and self.semantic_check.isChecked() and self.corpus

            entries_to_show = []
            relevance_map = {}

            # semantic search
            if is_sem:
                results = self.corpus.search(query, top_n_sentences=self.top_n.value())
                min_rel = self.min_rel.value()

                for word, score in results:
                    if word in VOCAB_MAP and score >= min_rel:
                        entries_to_show.append(VOCAB_MAP[word])
                        relevance_map[word] = score

            # --------------------------------------------------------
            # keyword search
            # --------------------------------------------------------
            else:
                if not query:
                    entries_to_show = self.entries
                else:
                    exact = []
                    gloss = []
                    longtxt = []

                    for e in self.entries:
                        w = e.word.lower()
                        g = e.gloss.lower() if e.gloss else ""
                        lt = e.semantic_long.lower() if e.semantic_long else ""

                        if query == w:
                            exact.append(e)
                        elif query in g:
                            gloss.append(e)
                        elif query in lt:
                            longtxt.append(e)

                    entries_to_show = exact + gloss + longtxt

            # --------------------------------------------------------
            # layout grid
            # --------------------------------------------------------
            font = self.owner.output.font()
            size = self.btn_size.value()

            f = QFont(font)
            f.setPointSize(size)

            btn_w = size + 24
            spacing = self.grid.spacing()
            avail = self.scroll.viewport().width()

            cols = max(1, (avail + spacing) // (btn_w + spacing))

            r = 0
            c = 0

            for entry in entries_to_show:
                word = entry.word
                cp = entry.cp

                b = QPushButton(chr(cp))
                b.setFont(f)
                b.setFixedSize(btn_w, btn_w)

                tip = entry.word
                if entry.gloss:
                    tip += f"\n{entry.gloss}"

                if is_sem and word in relevance_map:
                    tip += f"\nrelevance: {relevance_map[word]}"

                b.setToolTip(tip)

                b.clicked.connect(lambda ev=None, w=word: self._insert(w, shift=(QApplication.keyboardModifiers() & Qt.ShiftModifier)))
                b.setContextMenuPolicy(Qt.CustomContextMenu)
                b.customContextMenuRequested.connect(
                    lambda pos, w=word, btn=b: self._context_menu(w, btn, pos)
                )

                self.grid.addWidget(b, r, c)
                self.buttons[word] = b

                c += 1
                if c >= cols:
                    c = 0
                    r += 1

            self.footer.setText(f"{len(entries_to_show)} shown")

        finally:
            self._is_rebuilding = False

    # ------------------------------------------------------------
    # insertion helper
    # ------------------------------------------------------------

    def _insert(self, word: str, shift: bool = False):
        if self.mode.currentIndex() == 0:
            token = word
        else:
            token = chr(VOCAB_MAP[word].cp)

        cursor = self.owner.input.textCursor()
        text = self.owner.input.toPlainText()

        if not text:
            cursor.insertText(token)
            return

        last = text[-1]

        if shift:
            if last.isspace() or last == "+":
                cursor.insertText(token)
            else:
                cursor.insertText("+" + token)
            return

        if last.isalnum() or last not in (" ", "+"):
            cursor.insertText(" " + token)
        else:
            cursor.insertText(token)
