# ui_details.py
# -------------------------------------------------------------------
# the details dialog for a single glyph: large glyph display, gloss,
# long semantic text (from primary data), clickable link to lipamanka
# -------------------------------------------------------------------

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QTextCharFormat
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QTextEdit,
    QDialogButtonBox, QToolButton, QWidget
)
from PySide6.QtGui import QTextCursor, QDesktopServices


class GlyphDetailDialog(QDialog):
    """expanded detail view for a single toki pona glyph"""

    def __init__(self, parent: QWidget,
                 entry,
                 font: QFont,
                 query: str = ""):
        super().__init__(parent)

        self.setWindowTitle(f"{entry.word} — details")
        self.resize(650, 520)

        main = QVBoxLayout(self)

        # ------------------------------------------------------------
        # header row
        # ------------------------------------------------------------
        head = QHBoxLayout()

        glyph_label = QLabel(chr(entry.cp))
        glyph_font = QFont(font)
        glyph_font.setPointSize(max(font.pointSize(), 48))
        glyph_label.setFont(glyph_font)
        glyph_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        glyph_label.setFixedWidth(100)

        head.addWidget(glyph_label, 0)
        txtcol = QVBoxLayout()

        word_label = QLabel(f"<b>{entry.word}</b>")
        txtcol.addWidget(word_label)

        gloss = entry.gloss or "—"
        gloss_label = QLabel(gloss)
        gloss_label.setWordWrap(True)
        txtcol.addWidget(gloss_label)

        if entry.url_long:
            b = QToolButton()
            b.setText("open semantic entry (lipamanka)")
            b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(entry.url_long)))
            txtcol.addWidget(b)

        lic = QLabel(
            'semantic text © lipamanka — '
            '<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">CC BY-NC-SA 4.0</a>'
        )
        lic.setOpenExternalLinks(True)
        lic.setStyleSheet("color: #555")
        txtcol.addWidget(lic)
        txtcol.addStretch(1)

        head.addLayout(txtcol, 1)
        main.addLayout(head)


        # ------------------------------------------------------------
        # long semantic text
        # ------------------------------------------------------------
        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setPlainText(entry.semantic_long or "(no extended text available)")
        main.addWidget(self.body, 1)

        if query:
            self._highlight(query)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        main.addWidget(btns)

    # ------------------------------------------------------------------

    def _highlight(self, query: str):
        """highlight occurrences of query in details pane"""
        q = query.strip()
        if not q:
            return

        cursor = self.body.textCursor()
        doc = self.body.document()

        fmt = QTextCharFormat()
        fmt.setBackground(Qt.yellow)

        cursor.beginEditBlock()
        cursor.setPosition(0)

        import re
        pattern = re.compile(re.escape(q), re.IGNORECASE)

        text = self.body.toPlainText()
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()

            cur = self.body.textCursor()
            cur.setPosition(start)
            cur.setPosition(end, QTextCursor.KeepAnchor)
            cur.mergeCharFormat(fmt)

        cursor.endEditBlock()
