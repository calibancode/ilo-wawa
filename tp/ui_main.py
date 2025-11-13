# ui_main.py
# -----------------------------------------
# main application window
# handles input/output, conversion,
# data loading, and UI assembly
# -----------------------------------------

from __future__ import annotations

import os
from typing import List

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import (
    QAction, QClipboard, QFont, QGuiApplication,
    QKeySequence, QTextCursor, QTextCharFormat
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QGroupBox,
    QLabel, QLineEdit, QMainWindow, QMenu, QStatusBar,
    QTextEdit, QToolBar, QToolButton, QVBoxLayout, QWidget,
    QSpinBox, QComboBox, QSplitter, QMessageBox
)

from log import log
from data import load_all_data, VOCAB_MAP, TP_TO_UCSUR, VocabEntry
from convert import convert_text, TOK_RE, VAR_TAIL_RE
from ui_palette import GlyphPaletteDock
from ui_details import GlyphDetailDialog


# --------------------------------------------------------------

class Options:
    def __init__(self,
                 allow_ascii=True,
                 pass_unknown=True,
                 remove_spaces=True,
                 preserve_newlines=True):
        self.allow_ascii = allow_ascii
        self.pass_unknown = pass_unknown
        self.remove_spaces = remove_spaces
        self.preserve_newlines = preserve_newlines


# --------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ilo wawa")
        self.resize(1280, 960)

        self.primary_data_path = os.path.join(os.getcwd(), "tp_semantic_spaces.json")
        self.supplementary_data_path = os.path.join(os.getcwd(), "juniko.json")

        self.opts = Options()
        self._in_convert = False

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        layout.addWidget(self._build_toolbar())

        split = QSplitter(Qt.Vertical)
        layout.addWidget(split, 1)

        self.input = QTextEdit()
        self.input.setAcceptRichText(False)
        self.input.setPlaceholderText("type toki pona…")
        self.input.textChanged.connect(self._maybe_convert)
        split.addWidget(self._boxed("input (sitelen lasina)", self.input))

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("sitelen seli kiwen juniko", 32))
        self.output.cursorPositionChanged.connect(self._update_status)
        split.addWidget(self._boxed("output (UCSUR)", self.output))

        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status = QLabel("ready")
        self.statusBar().addPermanentWidget(self.status)

        data_menu = self.menuBar().addMenu("Data")
        act_reload = QAction("Reload Glossary from JSON…", self)
        act_reload.setShortcut(QKeySequence("Ctrl+R"))
        act_reload.triggered.connect(self.reload_data)
        data_menu.addAction(act_reload)

        self.palette = GlyphPaletteDock(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.palette)

        self._load_initial_data()
        self._highlight_unknowns()

    # ----------------------------------------------------------

    def _load_initial_data(self):
        status, vocab = load_all_data(
            primary_path=self.primary_data_path,
            supplementary_path=self.supplementary_data_path
        )

        if not vocab:
            QMessageBox.critical(self, "Data Error", status)

        self.palette.set_vocab(vocab)
        self.statusBar().showMessage(status, 5000)
        log.info(status)

    # ----------------------------------------------------------

    def reload_data(self):
        status, vocab = load_all_data(
            primary_path=self.primary_data_path,
            supplementary_path=self.supplementary_data_path
        )
        self.palette.set_vocab(vocab)
        QMessageBox.information(self, "Reload Data", status)
        self.convert()

    # ----------------------------------------------------------

    def insert_text(self, s: str):
        self._insert(s)

    # ----------------------------------------------------------

    def _boxed(self, title: str, widget: QWidget) -> QWidget:
        box = QGroupBox(title)
        v = QVBoxLayout(box)
        v.addWidget(widget)
        return box

    # ----------------------------------------------------------

    def _build_toolbar(self) -> QWidget:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))

        # convert button
        act_convert = QAction("convert", self)
        act_convert.setShortcut(QKeySequence("Ctrl+Return"))
        act_convert.triggered.connect(self.convert)
        tb.addAction(act_convert)

        self.auto = QCheckBox("auto")
        self.auto.setChecked(True)
        tb.addWidget(self.auto)

        tb.addSeparator()

        btn_insert = QToolButton()
        btn_insert.setText("insert")
        btn_insert.setPopupMode(QToolButton.InstantPopup)
        menu_insert = QMenu(btn_insert)

        join_menu = menu_insert.addMenu("joiners")
        for label, token in [
            ("ZWJ", "\u200D"),
            ("ZWNJ", "\u200C"),
            ("stack -", "-"),
            ("scale +", "+")
        ]:
            a = QAction(label, self)
            a.triggered.connect(lambda _, t=token: self._insert(t))
            join_menu.addAction(a)

        cart_menu = menu_insert.addMenu("cartouche")
        for token in ["[", "]", "="]:
            a = QAction(token, self)
            a.triggered.connect(lambda _, t=token: self._insert(t))
            cart_menu.addAction(a)

        long_menu = menu_insert.addMenu("long marks")
        for token in ["(", ")", "_", "{", "}"]:
            a = QAction(token, self)
            a.triggered.connect(lambda _, t=token: self._insert(t))
            long_menu.addAction(a)

        var_menu = menu_insert.addMenu("variations")
        for d in "12345678":
            a = QAction(f"VAR{int(d):02d}", self)
            a.triggered.connect(lambda _, t=d: self._insert(t))
            var_menu.addAction(a)

        btn_insert.setMenu(menu_insert)
        tb.addWidget(btn_insert)

        fontbtn = QToolButton()
        fontbtn.setText("font")
        fontbtn.setPopupMode(QToolButton.InstantPopup)
        font_menu = QMenu(fontbtn)

        self.font_combo = QComboBox()
        self.font_combo.addItems([
            "sitelen seli kiwen juniko",
            "nasin-nanpa",
            "custom…",
        ])
        self.font_combo.currentIndexChanged.connect(self._font_changed)

        self.font_custom = QLineEdit()
        self.font_custom.setPlaceholderText("custom font family…")
        self.font_custom.setFixedWidth(220)
        self.font_custom.editingFinished.connect(self._apply_font)
        self.font_custom.setEnabled(False)

        self.font_size = QSpinBox()
        self.font_size.setRange(8, 96)
        self.font_size.setValue(24)
        self.font_size.valueChanged.connect(self._apply_font)

        from PySide6.QtWidgets import QWidgetAction
        font_panel = QWidget()
        fv = QVBoxLayout(font_panel)
        fv.setContentsMargins(8, 8, 8, 8)
        fv.setSpacing(6)

        row1 = QVBoxLayout()
        row1.addWidget(QLabel("family:"))
        row1.addWidget(self.font_combo)

        row2 = QVBoxLayout()
        row2.addWidget(QLabel("custom:"))
        row2.addWidget(self.font_custom)

        row3 = QVBoxLayout()
        row3.addWidget(QLabel("size:"))
        row3.addWidget(self.font_size)

        fv.addLayout(row1)
        fv.addLayout(row2)
        fv.addLayout(row3)

        wa_font = QWidgetAction(self)
        wa_font.setDefaultWidget(font_panel)
        font_menu.addAction(wa_font)

        fontbtn.setMenu(font_menu)
        tb.addWidget(fontbtn)

        filebtn = QToolButton()
        filebtn.setText("file")
        filebtn.setPopupMode(QToolButton.InstantPopup)
        file_menu = QMenu(filebtn)

        act_open = QAction("open…", self)
        act_open.triggered.connect(self.open_text)
        act_save = QAction("save output…", self)
        act_save.triggered.connect(self.save_output)
        act_copy = QAction("copy output", self)
        act_copy.triggered.connect(self.copy_output)
        act_codes = QAction("copy codepoints", self)
        act_codes.triggered.connect(self.copy_codepoints)
        act_swap = QAction("swap input/output", self)
        act_swap.triggered.connect(self.swap_io)
        act_clear = QAction("clear", self)
        act_clear.triggered.connect(self.clear_all)

        file_menu.addAction(act_open)
        file_menu.addAction(act_save)
        file_menu.addSeparator()
        file_menu.addAction(act_copy)
        file_menu.addAction(act_codes)
        file_menu.addSeparator()
        file_menu.addAction(act_swap)
        file_menu.addAction(act_clear)

        filebtn.setMenu(file_menu)
        tb.addWidget(filebtn)

        optsbtn = QToolButton()
        optsbtn.setText("options")
        optsbtn.setPopupMode(QToolButton.InstantPopup)
        opts_menu = QMenu(optsbtn)

        self.keep_spaces = QCheckBox("keep spaces")
        self.keep_spaces.setChecked(False)
        self.keep_spaces.toggled.connect(self.convert)

        self.keep_newlines = QCheckBox("keep newlines")
        self.keep_newlines.setChecked(True)
        self.keep_newlines.toggled.connect(self.convert)

        self.ascii_map = QCheckBox("ASCII→UCSUR")
        self.ascii_map.setChecked(True)
        self.ascii_map.toggled.connect(self.convert)

        self.keep_unknown = QCheckBox("keep unknown")
        self.keep_unknown.setChecked(True)
        self.keep_unknown.toggled.connect(self.convert)

        opts_panel = QWidget()
        ov = QVBoxLayout(opts_panel)
        ov.setContentsMargins(8, 8, 8, 8)
        ov.setSpacing(4)

        for w in (self.keep_spaces, self.keep_newlines,
                  self.ascii_map, self.keep_unknown):
            ov.addWidget(w)

        wa_opts = QWidgetAction(self)
        wa_opts.setDefaultWidget(opts_panel)
        opts_menu.addAction(wa_opts)

        optsbtn.setMenu(opts_menu)
        tb.addWidget(optsbtn)

        return tb

    # ----------------------------------------------------------

    def _insert(self, s: str):
        cursor = self.input.textCursor()
        cursor.insertText(s)
        self.input.setTextCursor(cursor)
        self._maybe_convert()

    # ----------------------------------------------------------

    def _font_changed(self):
        idx = self.font_combo.currentIndex()
        self.font_custom.setEnabled(idx == 2)
        self._apply_font()

    # ----------------------------------------------------------

    def _apply_font(self):
        if self.font_combo.currentIndex() == 2:
            fam = self.font_custom.text().strip() or "sitelen seli kiwen juniko"
        else:
            fam = self.font_combo.currentText()

        size = self.font_size.value()
        self.output.setFont(QFont(fam, size))

        if hasattr(self.palette, "refresh_fonts"):
            self.palette.refresh_fonts()

    # ----------------------------------------------------------

    def _maybe_convert(self):
        if self.auto.isChecked():
            self.convert()
        else:
            self._highlight_unknowns()

    # ----------------------------------------------------------

    def convert(self):
        if self._in_convert:
            return
        self._in_convert = True

        try:
            txt = self.input.toPlainText()
            opts = Options(
                allow_ascii=self.ascii_map.isChecked(),
                pass_unknown=self.keep_unknown.isChecked(),
                remove_spaces=not self.keep_spaces.isChecked(),
                preserve_newlines=self.keep_newlines.isChecked(),
            )
            out = convert_text(txt, opts)
            self.output.setPlainText(out)

            self._highlight_unknowns()
            self._update_status()
        finally:
            self._in_convert = False

    # ----------------------------------------------------------

    def _highlight_unknowns(self):
        sels = []
        txt = self.input.toPlainText()
        pos = 0

        for tok in TOK_RE.findall(txt):
            start, end = pos, pos + len(tok)
            pos = end

            if tok in ("\r", "\n", "\r\n"):
                continue
            if tok.isspace():
                continue

            m = VAR_TAIL_RE.match(tok)
            base = m.group("word") if m else tok

            if base and base[0].isalpha() and base.lower() not in TP_TO_UCSUR:
                sel = QTextEdit.ExtraSelection()

                fmt = QTextCharFormat()
                fmt.setUnderlineStyle(QTextCharFormat.DashUnderline)
                sel.format = fmt

                cursor = self.input.textCursor()
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.KeepAnchor)
                sel.cursor = cursor

                sels.append(sel)

        self.input.setExtraSelections(sels)

    # ----------------------------------------------------------

    def _update_status(self):
        cur = self.output.textCursor()
        pos = cur.position()
        s = self.output.toPlainText()

        if 0 < pos <= len(s):
            self.status.setText(f"U+{ord(s[pos-1]):04X}")
        else:
            self.status.setText("ready")

    # ----------------------------------------------------------

    def copy_output(self):
        QGuiApplication.clipboard().setText(
            self.output.toPlainText(), QClipboard.Clipboard
        )
        self.statusBar().showMessage("copied", 1500)

    def copy_codepoints(self):
        s = self.output.toPlainText()
        codes = " ".join(f"U+{ord(c):04X}" for c in s)
        QGuiApplication.clipboard().setText(codes, QClipboard.Clipboard)
        self.statusBar().showMessage("copied codepoints", 1500)

    # ----------------------------------------------------------

    def swap_io(self):
        a = self.input.toPlainText()
        b = self.output.toPlainText()
        self.input.setPlainText(b)
        self.output.setPlainText(a)
        self._maybe_convert()

    # ----------------------------------------------------------

    def clear_all(self):
        self.input.clear()
        self.output.clear()
        self.status.setText("ready")

    # ----------------------------------------------------------

    def open_text(self):
        fn, _ = QFileDialog.getOpenFileName(
            self, "open text", os.getcwd(),
            "Text files (*.txt);;All files (*.*)"
        )
        if fn:
            with open(fn, "r", encoding="utf-8") as f:
                self.input.setPlainText(f.read())
            self._maybe_convert()

    # ----------------------------------------------------------

    def save_output(self):
        fn, _ = QFileDialog.getSaveFileName(
            self, "save output", os.getcwd(), "Text files (*.txt)"
        )
        if fn:
            with open(fn, "w", encoding="utf-8") as f:
                f.write(self.output.toPlainText())
            self.statusBar().showMessage("saved", 1500)

    # ----------------------------------------------------------

    def show_glyph_details(self, word: str):
        entry = VOCAB_MAP.get(word)
        if not entry:
            return

        dlg = GlyphDetailDialog(
            self,
            entry,
            self.output.font(),
            query=""
        )
        dlg.exec()
