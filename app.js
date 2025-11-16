// ilo wawa (web)
// minimal static port: sitelen lasina → UCSUR, glyph palette, details

// -------------------------------------------------------------------
// global state
// -------------------------------------------------------------------

let vocabList = [];  // [{ word, cp, gloss, semantic_long, url_long }]
let tpToUcsur = {};  // word -> codepoint

const state = {
  options: {
    allowAscii: true,
    passUnknown: true,
    removeSpaces: true,
    preserveNewlines: true,
  },
  currentDetailsEntry: null,
};

// -------------------------------------------------------------------
// data loading (mirrors data.py load_all_data)
// -------------------------------------------------------------------

function cleanTpName(name) {
  name = (name || "").toLowerCase().trim();
  name = name.replace(/\s*\(.*?\)\s*/g, "");
  name = name.replace(/-/g, "+");
  return name;
}

async function loadAllData() {
  const primaryUrl = "tp/tp_semantic_spaces.json";
  const suppUrl = "tp/juniko.json";

  let primary = [];
  let supp = [];

  try {
    primary = await fetch(primaryUrl).then(r => r.json());
  } catch (e) {
    console.error("failed to load primary data", e);
  }

  try {
    supp = await fetch(suppUrl).then(r => r.json());
  } catch (e) {
    console.warn("supplementary data not found or error", e);
  }

  vocabList = [];
  tpToUcsur = {};

  // primary
  for (const item of primary || []) {
    const word = (item.word || "").toLowerCase().trim();
    if (!word) continue;

    let cpStr = String(item.codepoint || "").replace(/^U\+/i, "");
    const cp = parseInt(cpStr, 16);
    if (!Number.isNaN(cp)) {
      const gloss = (item.definition || "").trim();
      const rawSem = item.semantic_space;
      const semanticLong = typeof rawSem === "string" ? rawSem.trim() : "";
      const urlLong = "https://lipamanka.gay/essays/dictionary#" + encodeURIComponent(word);

      vocabList.push({
        word,
        cp,
        gloss,
        semantic_long: semanticLong,
        url_long: urlLong,
      });

      tpToUcsur[word] = cp;
    }
  }

  // ali → ale
  if (tpToUcsur["ale"] != null) {
    tpToUcsur["ali"] = tpToUcsur["ale"];
  }

  // supplementary (juniko etc.)
  let added = 0;
  for (const item of supp || []) {
    const name = cleanTpName(item.name || "");
    if (!name) continue;
    if (tpToUcsur[name] != null) continue;

    let cpStr = String(item.code_hex || "").replace(/^U\+/i, "");
    const cp = parseInt(cpStr, 16);
    if (Number.isNaN(cp)) continue;

    tpToUcsur[name] = cp;
    added++;
  }

  console.log(`loaded ${vocabList.length} primary entries, +${added} supplementary glyphs`);
}

// -------------------------------------------------------------------
// converter (port of convert.py)
// -------------------------------------------------------------------

// token regex (mirrors TOK_RE)
const TOK_RE = /\r\n|\r|\n|[ \t]+|[A-Za-z][A-Za-z0-9+-]*|[\[\]\(\)\{\}\-+._:=]|./g;

// variation selector regex (mirrors VAR_TAIL_RE)
const VAR_TAIL_RE = /^([A-Za-z][A-Za-z-]*?)([1-8]+)$/;

// ASCII → UCSUR mapping
const ASCII_TO_UCSUR = {
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
};

// variation selectors U+E0101…U+E0108
const VARIATION_BY_DIGIT = {};
for (let i = 1; i <= 8; i++) {
  VARIATION_BY_DIGIT[String(i)] = 0xE0100 + (i - 1);
}

function ch(cp) {
  return String.fromCodePoint(cp);
}

function emitVariations(digits) {
  let s = "";
  for (const d of digits) {
    const cp = VARIATION_BY_DIGIT[d];
    if (cp != null) s += ch(cp);
  }
  return s;
}

function tpToUcsurChar(word) {
  const cp = tpToUcsur[word.toLowerCase()];
  return cp != null ? ch(cp) : word;
}

function expandJoinCompound(tok, opts, out) {
  if (!tok.includes("+") && !tok.includes("-")) return false;
  if (!/^[A-Za-z]/.test(tok)) return false;

  const parts = tok.split(/([\-+])/);
  let hadAny = false;

  for (const p of parts) {
    if (!p) continue;

    if (p === "-") {
      if (opts.allowAscii) {
        out.push(ch(ASCII_TO_UCSUR["-"]));
        hadAny = true;
      }
      continue;
    }

    if (p === "+") {
      out.push("\u200D");
      hadAny = true;
      continue;
    }

    let glyph = tpToUcsurChar(p);
    if (glyph === p && !opts.passUnknown) {
      continue;
    }
    out.push(glyph);
    hadAny = true;
  }

  return hadAny;
}

function convertText(text, opts) {
  const out = [];

  const tokens = text.match(TOK_RE) || [];
  for (const tok of tokens) {
    if (!tok) continue;

    // newlines
    if (tok === "\r\n" || tok === "\r" || tok === "\n") {
      if (opts.preserveNewlines) out.push(tok);
      continue;
    }

    // spaces/tabs
    if (/^[ \t]+$/.test(tok)) {
      if (!opts.removeSpaces) out.push(tok);
      continue;
    }

    // literal ZWJ/ZWNJ
    if (tok === "\u200D" || tok === "\u200C") {
      out.push(tok);
      continue;
    }

    // standalone ASCII controls
    if (opts.allowAscii && ASCII_TO_UCSUR.hasOwnProperty(tok)) {
      out.push(ch(ASCII_TO_UCSUR[tok]));
      continue;
    }

    // explicit compounds with '+'
    if (tok.includes("+")) {
      if (expandJoinCompound(tok, opts, out)) continue;
    }

    const low = tok.toLowerCase();

    // direct word → glyph
    if (tpToUcsur[low] != null) {
      out.push(ch(tpToUcsur[low]));
      continue;
    }

    // variation tail (e.g. toki2, ni33)
    const m = tok.match(VAR_TAIL_RE);
    if (m) {
      const base = m[1];
      const variations = m[2];

      let glyph = tpToUcsurChar(base);
      if (glyph === base && !opts.passUnknown) {
        glyph = "";
      }

      out.push(glyph + emitVariations(variations));
      continue;
    }

    // fallback compound with '-' or '+'
    if (expandJoinCompound(tok, opts, out)) continue;

    // unknown token
    if (opts.passUnknown) out.push(tok);
  }

  return out.join("");
}

// -------------------------------------------------------------------
// unknown token analysis (port of _highlight_unknowns, but as a list)
// -------------------------------------------------------------------

function collectUnknownTokens(text) {
  const unknown = new Set();
  const tokens = text.match(TOK_RE) || [];
  let pos = 0;

  for (const tok of tokens) {
    const start = pos;
    const end = pos + tok.length;
    pos = end;

    if (tok === "\r" || tok === "\n" || tok === "\r\n") continue;
    if (/^\s+$/.test(tok)) continue;

    const m = tok.match(VAR_TAIL_RE);
    const base = m ? m[1] : tok;

    if (base && /^[A-Za-z]/.test(base)) {
      const low = base.toLowerCase();
      if (tpToUcsur[low] == null) {
        unknown.add(low);
      }
    }
  }

  return Array.from(unknown.values()).sort();
}

// -------------------------------------------------------------------
// DOM helpers
// -------------------------------------------------------------------

function $(id) {
  return document.getElementById(id);
}

function showStatus(msg) {
  const el = $("status-bar");
  if (el) el.textContent = msg;
}

function insertAtCursor(textarea, text) {
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const value = textarea.value;
  textarea.value = value.slice(0, start) + text + value.slice(end);
  const pos = start + text.length;
  textarea.selectionStart = textarea.selectionEnd = pos;
  textarea.focus();
}

function insertWithSpacing(textarea, token, plusMode) {
  const text = textarea.value;
  let pos = textarea.selectionStart;

  const before = text.slice(0, pos);
  const after = text.slice(pos);

  const last = before.slice(-1);

  let insertText = "";

  if (plusMode) {
    if (!last || /\s/.test(last) || last === "+") {
      insertText = token;
    } else {
      insertText = "+" + token;
    }
  } else {
    if (last && (/[A-Za-z0-9]/.test(last) || (last !== " " && last !== "+"))) {
      insertText = " " + token;
    } else {
      insertText = token;
    }
  }

  textarea.value = before + insertText + after;
  const newPos = before.length + insertText.length;
  textarea.selectionStart = textarea.selectionEnd = newPos;
  textarea.focus();
}

// -------------------------------------------------------------------
// palette rendering (port of ui_palette._rebuild keyword search branch)
// -------------------------------------------------------------------

function rebuildPalette() {
  const grid = $("palette-grid");
  const filter = $("palette-filter");
  const footer = $("palette-footer");
  // const sizeSlider = $("palette-size");
  const output = $("output");

  if (!grid || !filter || !footer) return;

  const query = filter.value.trim().toLowerCase();
  let entriesToShow = [];

  if (!query) {
    entriesToShow = vocabList;
  } else {
    const exact = [];
    const gloss = [];
    const longtxt = [];

    for (const e of vocabList) {
      const w = (e.word || "").toLowerCase();
      const g = (e.gloss || "").toLowerCase();
      const lt = (e.semantic_long || "").toLowerCase();

      if (query === w) {
        exact.push(e);
      } else if (g.includes(query)) {
        gloss.push(e);
      } else if (lt.includes(query)) {
        longtxt.push(e);
      }
    }

    entriesToShow = exact.concat(gloss, longtxt);
  }

  grid.innerHTML = "";

  const fontFamily = window.getComputedStyle(output).fontFamily;
  // const baseSize = parseInt(sizeSlider.value, 10) || 28;
  // const btnSize = baseSize + 12;

  for (const entry of entriesToShow) {
    const btn = document.createElement("button");
    btn.className = "glyph-btn";
    btn.textContent = String.fromCodePoint(entry.cp);
    // btn.style.fontSize = baseSize + "px";
    btn.style.fontFamily = fontFamily;

    let tip = entry.word;
    if (entry.gloss) tip += "\n" + entry.gloss;
    btn.title = tip;

    btn.addEventListener("click", (ev) => {
      insertFromPalette(entry, ev.shiftKey);
    });

    btn.addEventListener("contextmenu", (ev) => {
      ev.preventDefault();
      showDetails(entry);
    });

    grid.appendChild(btn);
  }

  footer.textContent = `${entriesToShow.length} shown`;
}

function insertFromPalette(entry, shiftHeld) {
  const modeSel = $("palette-mode");
  const input = $("input");
  if (!modeSel || !input) return;

  const mode = modeSel.value;
  let token;

  if (mode === "latin") {
    token = entry.word;
  } else {
    token = String.fromCodePoint(entry.cp);
  }

  insertWithSpacing(input, token, !!shiftHeld);
  maybeConvert();
}

// -------------------------------------------------------------------
// details dialog (port of GlyphDetailDialog)
// -------------------------------------------------------------------

function showDetails(entry) {
  const dlg = $("dialog-details");
  if (!dlg) return;

  $("details-glyph").textContent = String.fromCodePoint(entry.cp);
  $("details-word").textContent = entry.word;
  $("details-gloss").textContent = entry.gloss || "—";

  const linkEl = $("details-link");
  if (entry.url_long) {
    linkEl.innerHTML =
      `<a href="${entry.url_long}" target="_blank" rel="noopener">open semantic entry (lipamanka)</a>`;
  } else {
    linkEl.textContent = "";
  }

  $("details-body").textContent =
    entry.semantic_long || "(no extended text available)";

  state.currentDetailsEntry = entry;
  dlg.showModal();
}

// -------------------------------------------------------------------
// unknown list
// -------------------------------------------------------------------

function updateUnknownList() {
  const input = $("input");
  const ul = $("unknown-list");
  if (!input || !ul) return;

  const unknown = collectUnknownTokens(input.value);
  if (!unknown.length) {
    ul.textContent = "none";
    return;
  }

  ul.innerHTML = "";
  for (const w of unknown) {
    const span = document.createElement("span");
    span.className = "badge";
    span.textContent = w;
    ul.appendChild(span);
  }
}

// -------------------------------------------------------------------
// conversion + status
// -------------------------------------------------------------------

function readOptionsFromUI() {
  state.options = {
    allowAscii: $("opt-ascii-map").checked,
    passUnknown: $("opt-keep-unknown").checked,
    removeSpaces: !$("opt-keep-spaces").checked,
    preserveNewlines: $("opt-keep-newlines").checked,
  };
}

function convertNow() {
  const input = $("input");
  const output = $("output");
  if (!input || !output) return;

  readOptionsFromUI();
  const text = input.value;
  const out = convertText(text, state.options);
  output.value = out;

  updateUnknownList();
  updateStatusFromOutput();
}

function maybeConvert() {
  const auto = $("opt-auto");
  if (auto && auto.checked) {
    convertNow();
  } else {
    updateUnknownList();
  }
}

function updateStatusFromOutput() {
  const output = $("output");
  if (!output) return;

  const pos = output.selectionStart;
  const s = output.value;

  if (pos > 0 && pos <= s.length) {
    const code = s.codePointAt(pos - 1);
    if (code != null) {
      showStatus("U+" + code.toString(16).toUpperCase().padStart(4, "0"));
      return;
    }
  }
  showStatus("ready");
}

// -------------------------------------------------------------------
// font + palette sync
// -------------------------------------------------------------------

function applyFontFromDialog(){
  const famSel = $("font-family");
  const custom = $("font-custom");
  const sizeInput = $("font-size");
  const output = $("output");
  if(!famSel || !sizeInput || !output) return;

  let fam = famSel.value === "custom"
    ? (custom.disabled = false, custom.value.trim() || "sitelen seli kiwen juniko")
    : (custom.disabled = true, famSel.value);

  const size = parseInt(sizeInput.value,10) || 32;

  output.style.fontFamily = fam;
  output.style.fontSize = size + "px";

  // key line: drive palette/output via the css var
  document.documentElement.style.setProperty("--font-glyph", fam);

  rebuildPalette();
}

// -------------------------------------------------------------------
// file actions
// -------------------------------------------------------------------

function handleOpenFile() {
  const hidden = $("file-open");
  if (!hidden) return;
  hidden.value = "";
  hidden.click();

  hidden.onchange = () => {
    const file = hidden.files && hidden.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      $("input").value = reader.result || "";
      maybeConvert();
    };
    reader.readAsText(file, "utf-8");
  };
}

function handleSaveOutput() {
  const output = $("output");
  if (!output) return;

  const blob = new Blob([output.value || ""], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "ilo-wawa-output.txt";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function copyToClipboard(text, okMsg) {
  try {
    await navigator.clipboard.writeText(text);
    showStatus(okMsg);
  } catch (e) {
    console.warn("copy failed", e);
    showStatus("copy failed");
  }
}

function copyOutputText() {
  const output = $("output");
  if (!output) return;
  copyToClipboard(output.value || "", "copied");
}

function copyOutputCodepoints() {
  const output = $("output");
  if (!output) return;
  const s = output.value || "";
  const codes = [];
  for (const ch of s) {
    const code = ch.codePointAt(0);
    codes.push("U+" + code.toString(16).toUpperCase().padStart(4, "0"));
  }
  copyToClipboard(codes.join(" "), "copied codepoints");
}

function swapIO() {
  const input = $("input");
  const output = $("output");
  if (!input || !output) return;
  const a = input.value;
  const b = output.value;
  input.value = b;
  output.value = a;
  maybeConvert();
}

function clearAll() {
  $("input").value = "";
  $("output").value = "";
  updateUnknownList();
  showStatus("ready");
}

// -------------------------------------------------------------------
// dialogs wiring
// -------------------------------------------------------------------

function wireDialogs() {
  const dlgInsert = $("dialog-insert");
  const dlgFont = $("dialog-font");
  const dlgFile = $("dialog-file");
  const dlgOptions = $("dialog-options");
  const dlgDetails = $("dialog-details");

  $("btn-insert").addEventListener("click", () => dlgInsert.showModal());
  $("btn-font").addEventListener("click", () => dlgFont.showModal());
  $("btn-file").addEventListener("click", () => dlgFile.showModal());
  $("btn-options").addEventListener("click", () => dlgOptions.showModal());

  dlgInsert.addEventListener("click", (ev) => {
    if (ev.target.tagName === "BUTTON" && ev.target.dataset.insert != null) {
      const token = ev.target.dataset.insert;
      insertAtCursor($("input"), token);
      maybeConvert();
    }
  });

  $("font-family").addEventListener("change", applyFontFromDialog);
  $("font-custom").addEventListener("input", applyFontFromDialog);
  $("font-size").addEventListener("change", applyFontFromDialog);

  $("file-open-btn").addEventListener("click", handleOpenFile);
  $("file-save-btn").addEventListener("click", handleSaveOutput);
  $("file-copy-output").addEventListener("click", copyOutputText);
  $("file-copy-codes").addEventListener("click", copyOutputCodepoints);
  $("file-swap").addEventListener("click", swapIO);
  $("file-clear").addEventListener("click", clearAll);

  $("details-close").addEventListener("click", () => dlgDetails.close());
  $("details-insert-latin").addEventListener("click", () => {
    if (!state.currentDetailsEntry) return;
    insertWithSpacing($("input"), state.currentDetailsEntry.word, false);
    maybeConvert();
  });
  $("details-insert-glyph").addEventListener("click", () => {
    if (!state.currentDetailsEntry) return;
    insertWithSpacing(
      $("input"),
      String.fromCodePoint(state.currentDetailsEntry.cp),
      false
    );
    maybeConvert();
  });
}

// -------------------------------------------------------------------
// main init
// -------------------------------------------------------------------

async function init() {
  await loadAllData();

  // options default sync
  $("opt-keep-spaces").checked = false;
  $("opt-keep-newlines").checked = true;
  $("opt-ascii-map").checked = true;
  $("opt-keep-unknown").checked = true;

  // core actions
  $("btn-convert").addEventListener("click", convertNow);
  $("opt-auto").addEventListener("change", maybeConvert);
  $("input").addEventListener("input", maybeConvert);
  $("output").addEventListener("click", updateStatusFromOutput);
  $("output").addEventListener("keyup", updateStatusFromOutput);

  $("palette-filter").addEventListener("input", () => rebuildPalette());
  $("palette-mode").addEventListener("change", () => rebuildPalette());

  wireDialogs();
  applyFontFromDialog();
  rebuildPalette();
  updateUnknownList();

  // keyboard shortcut: Ctrl+Enter -> convert
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
      ev.preventDefault();
      convertNow();
    }
  });

  showStatus("ready");
}

document.addEventListener("DOMContentLoaded", init);
