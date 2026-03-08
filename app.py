"""
AI Act Compliance Tool — Streamlit UI (V5)

Changes in V5:
- st.html() for CSS injection (fixes visible CSS text bug)
- Conversations stored + listed in sidebar
- Example questions properly trigger model
- Intent detection (user describing their AI system -> offer to register)
- Registry: cards/table toggle, proper inline-styled cards
- Copy answer button on assistant messages
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

# Load .env file if present (must happen before any LiteLLM/API key reads)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EU Compliance",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

logging.basicConfig(level=logging.WARNING)

DATA_DIR     = Path("data/chroma");   DATA_DIR.mkdir(parents=True, exist_ok=True)
CONV_DIR     = Path("data/conversations"); CONV_DIR.mkdir(parents=True, exist_ok=True)
REGISTRY_PATH = Path("data/registry.json"); REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── CSS ───────────────────────────────────────────────────────────────────
# Layout and component CSS injected via st.html() (avoids visible-text bug
# from st.markdown in modern Streamlit).
#
# Dark / light theme strategy:
#   Streamlit's native [theme.light] / [theme.dark] in config.toml handles
#   all built-in component colours (background, inputs, sidebar, text, etc.).
#   The toggle is in ⋮ → Settings → Theme, or follows OS preference.
#
#   _make_css_script() injects ONLY custom CSS variables (--bg, --t1, etc.)
#   into the parent page for our hand-crafted HTML elements (cards, badges,
#   citations…). It detects the current mode via st.context.theme.type and
#   re-injects on every rerun. No element overrides needed — Streamlit's
#   theme system covers those.

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Crimson+Pro:ital,wght@0,300;0,400;0,500;1,400&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&family=DM+Mono:wght@300;400&display=swap');
/* ── Design tokens — light (default) ───────────────────────────── */
/* NOTE: These vars are also re-injected into the parent page by         */
/* _make_css_script() to ensure var(--*) resolves in inline styles.     */
:root {
  --bg:      #F9F8F5;
  --bg-sb:   #F3F2EF;
  --sur:     #FFFFFF;
  --t1:      #1A1917;
  --t2:      #6B6760;
  --t3:      #9B9894;
  --bd:      #E5E3DE;
  --bd2:     #C8C5BF;
  --acc:     #EDECEA;
  --bg-warn: #FDFAF3;
  --bd-warn: #E8DEBB;
  --fd:      "Crimson Pro", Georgia, serif;
  --fu:      "DM Sans", system-ui, sans-serif;
  --fm:      "DM Mono", "Courier New", monospace;
  --r:       3px;
  --tr:      160ms ease;
  /* Responsive sizing */
  --sidebar-w: 240px;
  --rp-w:      260px;
  --chat-max:  800px;
}

/* ── Dark mode is applied by JS injecting <style id="dm-override">   ──
   into window.parent.document.head — see _make_css_script() below.
   No html.dark{} rules needed here (they'd be scoped to this iframe). */



/* ── Hide Streamlit chrome ─────────────────────────────────────── */
#MainMenu, footer { visibility: hidden !important; height: 0 !important; }
/* IMPORTANT: Do NOT use display:none on stHeader.
   The sidebar collapse button (kind=headerNoPadding) lives inside it.
   Instead collapse height to 0 with overflow:visible so the button
   escapes its container and remains clickable at all times. */
header[data-testid=stHeader] {
  height: 0 !important;
  min-height: 0 !important;
  padding: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  border: none !important;
  overflow: visible !important;
}
.stDeployButton { display: none !important; }

/* ── App shell ─────────────────────────────────────────────────── */
.stApp { background: var(--bg) !important; font-family: var(--fu) !important; }
section[data-testid=stBottom],
section[data-testid=stBottom] > div {
  background: var(--bg) !important;
  border-top: 1px solid var(--bd) !important;
}

/* ── Sidebar ───────────────────────────────────────────────────── */
[data-testid=stSidebar] {
  background: var(--bg-sb) !important;
  border-right: 1px solid var(--bd) !important;
  min-width: var(--sidebar-w) !important;
  max-width: var(--sidebar-w) !important;
}
[data-testid=stSidebar] > div:first-child {
  padding: 20px 14px 14px !important;
}

/* ── Sidebar collapse/expand toggle ─────────────────────────────
   The button (kind="headerNoPadding") lives inside stHeader.
   We no longer need position:fixed tricks — the header is kept
   at height:0 with overflow:visible above, so the button naturally
   stays at the top-left corner and survives reruns.
   ────────────────────────────────────────────────────────────── */

/* Wrapper that Streamlit places around the button */
[data-testid="stSidebarCollapseButton"] {
  position: absolute !important;
  top: 8px !important;
  left: 8px !important;
  z-index: 999 !important;
}

/* The button itself — match the sidebar conversation button style */
[data-testid="stBaseButton-headerNoPadding"],
[data-testid="stSidebarCollapseButton"] button {
  width: 30px !important;
  height: 30px !important;
  min-width: 30px !important;
  min-height: 30px !important;
  padding: 0 !important;
  border-radius: var(--r) !important;
  background: var(--bg-sb) !important;
  border: 1px solid var(--bd) !important;
  box-shadow: none !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  transition: background var(--tr), border-color var(--tr) !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
}
[data-testid="stBaseButton-headerNoPadding"]:hover,
[data-testid="stSidebarCollapseButton"] button:hover {
  background: var(--acc) !important;
  border-color: var(--bd2) !important;
}
[data-testid="stBaseButton-headerNoPadding"] [data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"] {
  font-size: 16px !important;
  color: var(--t2) !important;
  line-height: 1 !important;
}

/* Legacy Streamlit fallback (collapsedControl) */
[data-testid="collapsedControl"] {
  background: var(--bg-sb) !important;
  border: 1px solid var(--bd) !important;
  border-left: none !important;
  border-radius: 0 var(--r) var(--r) 0 !important;
  z-index: 999 !important;
  visibility: visible !important;
  opacity: 1 !important;
  pointer-events: auto !important;
}
[data-testid="collapsedControl"]:hover { background: var(--acc) !important; }
[data-testid="collapsedControl"] svg { stroke: var(--t2) !important; fill: none !important; }

/* ── Main content area ─────────────────────────────────────────── */
.main .block-container {
  padding: 6px 32px 100px !important;
  max-width: 1280px !important;
  overflow-x: hidden !important;
}

/* ── Typography ────────────────────────────────────────────────── */
h1, h2, h3 {
  font-family: var(--fd) !important;
  font-weight: 400 !important;
  color: var(--t1) !important;
}

/* ── Tabs ──────────────────────────────────────────────────────── */
.stTabs [data-baseweb=tab-list] {
  gap: 0 !important;
  border-bottom: 1px solid var(--bd) !important;
  background: transparent !important;
  flex-wrap: nowrap !important;
  overflow-x: auto !important;
}
.stTabs [data-baseweb=tab] {
  font-family: var(--fu) !important;
  font-size: 13px !important;
  color: var(--t3) !important;
  padding: 8px 20px !important;
  background: transparent !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  margin-bottom: -1px !important;
  white-space: nowrap !important;
}
.stTabs [data-baseweb=tab]:hover { color: var(--t2) !important; background: transparent !important; }
.stTabs [aria-selected=true] {
  color: var(--t1) !important;
  font-weight: 500 !important;
  border-bottom: 2px solid var(--t1) !important;
  background: transparent !important;
}
.stTabs [data-baseweb=tab-highlight],
.stTabs [data-baseweb=tab-border] { display: none !important; }
.stTabs [data-baseweb=tab-panel] {
  background: var(--bg) !important;
  padding: 24px 0 0 !important;
}

/* ── Buttons — core fix ────────────────────────────────────────── */
/* Base reset: ensure all buttons size correctly and wrap text */
.stButton > button {
  font-family: var(--fu) !important;
  font-size: 12.5px !important;
  border-radius: var(--r) !important;
  padding: 7px 14px !important;
  border: 1px solid var(--bd) !important;
  background: transparent !important;
  color: var(--t1) !important;
  box-shadow: none !important;
  transition: all var(--tr) !important;
  /* CRITICAL: prevent overflow/clipping */
  white-space: normal !important;
  word-break: break-word !important;
  overflow-wrap: break-word !important;
  height: auto !important;
  min-height: 34px !important;
  line-height: 1.4 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center !important;
  width: 100% !important;
  box-sizing: border-box !important;
  /* Prevent text from being cut off */
  overflow: visible !important;
  max-width: 100% !important;
}
.stButton > button:hover {
  background: var(--acc) !important;
  border-color: var(--bd2) !important;
}
.stButton > button:active {
  opacity: 0.8 !important;
}
.stButton > button:focus {
  box-shadow: 0 0 0 2px rgba(26,25,23,0.12) !important;
  outline: none !important;
}
/* Primary variant */
.stButton > button[kind=primary] {
  background: var(--t1) !important;
  color: var(--bg) !important;
  border-color: var(--t1) !important;
}
.stButton > button[kind=primary]:hover { opacity: 0.88 !important; }

/* Small action buttons in horizontal rows (Edit / Delete / ×) —
   keep decent padding, just a bit more compact than full buttons */
[data-testid="stHorizontalBlock"] .stButton > button {
  min-height: 32px !important;
  padding: 5px 12px !important;
  font-size: 12px !important;
}

/* Conversation list buttons — left-aligned text, no overflow clipping */
[data-testid=stSidebar] .stButton > button {
  justify-content: flex-start !important;
  text-align: left !important;
  font-size: 12.5px !important;
  padding: 6px 10px !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
  word-break: normal !important;
  display: block !important;
  max-width: 100% !important;
}
/* Sidebar footer buttons (Settings + Dark mode) — centered, not left-aligned */
[data-testid=stSidebar] [data-testid=stHorizontalBlock] .stButton > button {
  justify-content: center !important;
  text-align: center !important;
  display: inline-flex !important;
  font-size: 12px !important;
  padding: 6px 8px !important;
  overflow: hidden !important;
  white-space: nowrap !important;
}
/* Sidebar delete (×) button — compact square, full border visible */
[data-testid=stSidebar] [data-testid=stHorizontalBlock] div:last-child .stButton > button {
  padding: 4px 0 !important;
  font-size: 13px !important;
  line-height: 1 !important;
  width: 28px !important;
  min-width: 28px !important;
  max-width: 28px !important;
  justify-content: center !important;
  display: inline-flex !important;
  margin-left: 2px !important;    /* prevent left border from being hidden under sibling column */
}

/* ── Inputs ────────────────────────────────────────────────────── */
[data-testid=stTextInput] input,
[data-testid=stTextArea] textarea {
  background: var(--sur) !important;
  border: 1px solid var(--bd) !important;
  border-radius: var(--r) !important;
  font-family: var(--fu) !important;
  font-size: 13px !important;
  color: var(--t1) !important;
  box-shadow: none !important;
  width: 100% !important;
  box-sizing: border-box !important;
}
[data-testid=stTextInput] input:focus,
[data-testid=stTextArea] textarea:focus {
  border-color: var(--bd2) !important;
  box-shadow: 0 0 0 2px rgba(26,25,23,0.08) !important;
}
[data-testid=stSelectbox] > div > div {
  background: var(--sur) !important;
  border: 1px solid var(--bd) !important;
  border-radius: var(--r) !important;
  font-family: var(--fu) !important;
  font-size: 13px !important;
  color: var(--t1) !important;
}
[data-testid=stWidgetLabel] p {
  font-family: var(--fu) !important;
  font-size: 11.5px !important;
  color: var(--t2) !important;
}

/* ── Radio (segmented control) ─────────────────────────────────── */
[data-testid=stRadio] > div {
  flex-direction: row !important;
  gap: 0 !important;
  flex-wrap: nowrap !important;
  /* Contain so borders don't get clipped */
  overflow: visible !important;
}
[data-testid=stRadio] label {
  font-family: var(--fu) !important;
  font-size: 12.5px !important;
  padding: 7px 14px !important;
  margin: 0 !important;
  border: 1px solid var(--bd) !important;
  border-right: none !important;          /* share single border between adjacent labels */
  border-radius: 0 !important;
  cursor: pointer !important;
  flex: 1 !important;
  text-align: center !important;
  background: var(--sur) !important;
  color: var(--t2) !important;
  min-width: 52px !important;
  white-space: nowrap !important;
  box-sizing: border-box !important;
  transition: background var(--tr), color var(--tr) !important;
  /* Ensure full height — nothing clipped */
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  min-height: 34px !important;
}
/* Restore right border only on the last label */
[data-testid=stRadio] label:last-child {
  border-right: 1px solid var(--bd) !important;
  border-radius: 0 var(--r) var(--r) 0 !important;
}
[data-testid=stRadio] label:first-child { border-radius: var(--r) 0 0 var(--r) !important; }
[data-testid=stRadio] label:has(input:checked) {
  background: var(--acc) !important;
  color: var(--t1) !important;
  font-weight: 500 !important;
  border-color: var(--bd2) !important;
  /* Keep the right border consistent when selected */
  border-right-color: var(--bd2) !important;
  z-index: 1 !important;
  position: relative !important;
}
/* When selected label is not last, the next label needs its left border from the selected */
[data-testid=stRadio] label:has(input:checked) + label {
  border-left: 1px solid var(--bd2) !important;
}
[data-testid=stRadio] > div > label > div:first-child { display: none !important; }

/* ── Chat messages ─────────────────────────────────────────────── */
[data-testid=stChatMessage] {
  background: transparent !important;
  border: none !important;
  padding: 0 0 2px !important;
  gap: 0 !important;
}
[data-testid=stChatMessageAvatarUser],
[data-testid=stChatMessageAvatarAssistant] { display: none !important; }
[data-testid=stChatMessage]:has([data-testid=stChatMessageAvatarUser]) {
  padding-left: min(80px, 10vw) !important;
}
[data-testid=stChatMessage]:has([data-testid=stChatMessageAvatarUser]) [data-testid=stChatMessageContent] {
  border-left: 2px solid var(--bd2) !important;
  padding-left: 12px !important;
}
[data-testid=stChatMessageContent] { padding: 0 !important; }
[data-testid=stChatMessageContent] p {
  font-size: 14px !important;
  line-height: 1.72 !important;
  color: var(--t1) !important;
}

/* ── Chat input ────────────────────────────────────────────────── */
[data-testid=stChatInput] textarea {
  background: var(--sur) !important;
  border: 1px solid var(--bd) !important;
  border-radius: var(--r) !important;
  font-family: var(--fu) !important;
  font-size: 13px !important;
  color: var(--t1) !important;
  box-shadow: none !important;
}
[data-testid=stChatInput] button {
  background: var(--t1) !important;
  border-radius: var(--r) !important;
}

/* ── Expanders ─────────────────────────────────────────────────── */
[data-testid=stExpander] {
  border: 1px solid var(--bd) !important;
  border-radius: var(--r) !important;
  background: var(--sur) !important;
  box-shadow: none !important;
}
[data-testid=stExpander] summary {
  font-family: var(--fu) !important;
  font-size: 12px !important;
  color: var(--t2) !important;
  padding: 7px 12px !important;
}

/* ── Metrics ───────────────────────────────────────────────────── */
[data-testid=stMetricValue] {
  font-family: var(--fm) !important;
  font-size: 22px !important;
  font-weight: 300 !important;
  color: var(--t1) !important;
}
[data-testid=stMetricLabel] p {
  font-family: var(--fu) !important;
  font-size: 10px !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase !important;
  color: var(--t3) !important;
}

/* ── Alerts ────────────────────────────────────────────────────── */
.stAlert {
  border-radius: var(--r) !important;
  font-family: var(--fu) !important;
  font-size: 13px !important;
}

/* ── Scrollbar ─────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--bd2); border-radius: 2px; }

/* ── Right panel ───────────────────────────────────────────────── */
.rp-wrap {
  background: var(--bg-sb);
  border: 1px solid var(--bd);
  border-radius: 4px;
  padding: 14px 12px 12px;
  position: sticky;
  top: 20px;
  /* Don't overflow on narrow screens */
  min-width: 0;
  overflow: hidden;
}

/* ── Column overflow fix ───────────────────────────────────────── */
/* Prevent columns from pushing layout wider than viewport */
[data-testid=stHorizontalBlock] {
  flex-wrap: nowrap !important;
  min-width: 0 !important;
  overflow: visible !important;
}
[data-testid=stHorizontalBlock] > div {
  min-width: 0 !important;
  overflow: hidden !important;
}

/* ── Responsive breakpoints ────────────────────────────────────── */
@media (max-width: 900px) {
  .main .block-container { padding: 16px 16px 80px !important; }
  [data-testid=stChatMessage]:has([data-testid=stChatMessageAvatarUser]) {
    padding-left: 24px !important;
  }
}
@media (max-width: 640px) {
  .main .block-container { padding: 12px 10px 80px !important; }
  [data-testid=stChatMessage]:has([data-testid=stChatMessageAvatarUser]) {
    padding-left: 0 !important;
  }
  [data-testid=stChatMessage]:has([data-testid=stChatMessageAvatarUser]) [data-testid=stChatMessageContent] {
    border-left: none !important;
    padding-left: 0 !important;
  }
  .stTabs [data-baseweb=tab] { padding: 8px 12px !important; font-size: 12px !important; }
}

/* ── Intent / registry card / copy button ─────────────────────── */
.intent-banner {
  background: #FDFAF3;
  border: 1px solid #E8DEBB;
  border-radius: var(--r);
  padding: 12px 14px;
  margin: 8px 0;
}
.reg-card {
  background: var(--sur);
  border: 1px solid var(--bd);
  border-radius: var(--r);
  padding: 14px 16px;
  margin-bottom: 6px;
  transition: border-color var(--tr);
}
.reg-card:hover { border-color: var(--bd2); }
.copy-btn {
  font-family: var(--fm);
  font-size: 10px;
  color: var(--t3);
  background: transparent;
  border: 1px solid var(--bd);
  border-radius: 2px;
  padding: 1px 7px;
  cursor: pointer;
  transition: all var(--tr);
}
.copy-btn:hover { background: var(--acc); color: var(--t1); }

/* ── Welcome example buttons ───────────────────────────────────── */
/* Example question buttons: left-aligned, full text, generous padding.
   Note: Streamlit doesn't expose the key in data-testid for buttons,
   so we target them via their container context instead. */
.stTabs [data-baseweb=tab-panel] .stButton > button {
  text-align: left !important;
  justify-content: flex-start !important;
  height: auto !important;
  min-height: 52px !important;
  padding: 10px 14px !important;
  font-size: 13px !important;
  white-space: normal !important;
  line-height: 1.45 !important;
  word-break: break-word !important;
  overflow-wrap: break-word !important;
}
/* But keep the clear / save / delete action buttons centered */
.stTabs [data-baseweb=tab-panel] [data-testid=stHorizontalBlock] .stButton > button {
  text-align: center !important;
  justify-content: center !important;
  min-height: 34px !important;
  padding: 6px 12px !important;
  font-size: 12.5px !important;
  white-space: nowrap !important;
}

/* ── Page header row (title + clear) sits flush above tabs ────── */
/* Collapse the bottom margin of the header columns block */
.main .block-container > div > div:first-child [data-testid=stHorizontalBlock] {
  margin-bottom: 0 !important;
  padding-bottom: 0 !important;
  align-items: flex-end !important;
}
/* Remove top padding from the stTabs bar so it sits tight below header */
.stTabs { margin-top: 0 !important; padding-top: 0 !important; }
.stTabs [data-baseweb=tab-list] { margin-top: 0 !important; }
@keyframes sk-shimmer {
  0%   { background-position: -600px 0; }
  100% { background-position:  600px 0; }
}
.sk-wrap { padding: 40px 0 0; max-width: 540px; }
.sk-block {
  border-radius: 3px;
  background: linear-gradient(90deg, var(--bd) 0%, var(--acc) 40%, var(--bd) 80%);
  background-size: 600px 100%;
  animation: sk-shimmer 1.6s ease-in-out infinite;
  margin-bottom: 12px;
}
.sk-title-1  { height: 40px; width: 70%; }
.sk-title-2  { height: 40px; width: 52%; margin-bottom: 20px; }
.sk-sub      { height: 13px; width: 86%; }
.sk-sub2     { height: 13px; width: 60%; margin-bottom: 28px; }
.sk-label    { height: 9px;  width: 72px; margin-bottom: 16px; }
.sk-btn-row  { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px; }
.sk-btn      { height: 50px; }

/* ── Hide the st.html() iframe wrapper itself ────────────────────
   st.html injects an <iframe> via stCustomComponentV1; we zero its
   height so it takes no vertical space in the layout. */
iframe[title="stCustomComponentV1"] {
  display: block !important;
  height: 0 !important;
  min-height: 0 !important;
  border: none !important;
  margin: 0 !important;
  padding: 0 !important;
}
[data-testid="stCustomComponentV1"] {
  height: 0 !important;
  min-height: 0 !important;
  overflow: hidden !important;
  margin: 0 !important;
  padding: 0 !important;
}
</style>
"""

# _make_css_script: injects CSS variables into the parent page for custom HTML
# elements (cards, badges, etc.). In dark mode also injects element overrides
# so native Streamlit components (buttons, inputs, etc.) match the dark palette
# — this works on top of the [theme.dark] config which handles backgrounds.
def _make_css_script(is_dark: bool) -> str:
    if is_dark:
        css = """
:root {
  --bg:#141312; --bg-sb:#1C1B19; --sur:#1F1E1C;
  --t1:#EDEAE4; --t2:#9B9690;  --t3:#5E5C58;
  --bd:#2E2C29; --bd2:#3F3D39; --acc:#252320;
  --bg-warn:#1E1C12; --bd-warn:#3A3518;
  --r:3px; --tr:160ms ease;
}
body,.stApp,[data-testid=stAppViewContainer],[data-testid=stMain]{background:#141312!important;color:#EDEAE4!important}
[data-testid=stSidebar]{background:#1C1B19!important;border-right-color:#2E2C29!important}
section[data-testid=stBottom],section[data-testid=stBottom]>div{background:#141312!important;border-top-color:#2E2C29!important}
p,li,h1,h2,h3,h4,h5,h6,label,.stMarkdown p,[data-testid=stMarkdownContainer] p,[data-testid=stMarkdownContainer] li{color:#EDEAE4!important}
[data-testid=stWidgetLabel] p{color:#9B9690!important}
[data-testid=stTextInput] input,[data-testid=stTextArea] textarea,[data-testid=stChatInput] textarea{background:#1F1E1C!important;border-color:#2E2C29!important;color:#EDEAE4!important}
[data-testid=stSelectbox]>div>div{background:#1F1E1C!important;border-color:#2E2C29!important;color:#EDEAE4!important}
[data-baseweb=select] [data-baseweb=popover],[data-baseweb=menu],[data-baseweb=select] ul{background:#1F1E1C!important;border-color:#2E2C29!important}
[data-baseweb=menu] li,[data-baseweb=select] li{background:#1F1E1C!important;color:#EDEAE4!important}
[data-baseweb=menu] li:hover,[data-baseweb=select] li:hover{background:#252320!important}
.stTabs [data-baseweb=tab-list]{border-bottom-color:#2E2C29!important}
.stTabs [data-baseweb=tab-panel]{background:#141312!important}
.stTabs [data-baseweb=tab]{color:#5E5C58!important}
.stTabs [aria-selected=true]{color:#EDEAE4!important;border-bottom-color:#EDEAE4!important}
[data-testid=stExpander]{background:#1F1E1C!important;border-color:#2E2C29!important}
[data-testid=stExpander] summary,[data-testid=stExpander] summary p{color:#9B9690!important}
.stButton>button{background:transparent!important;border-color:#2E2C29!important;color:#EDEAE4!important}
.stButton>button:hover{background:#252320!important;border-color:#3F3D39!important}
.stButton>button[kind=primary]{background:#EDEAE4!important;color:#141312!important;border-color:#EDEAE4!important}
[data-testid=stRadio] label{background:#1F1E1C!important;border-color:#2E2C29!important;color:#9B9690!important}
[data-testid=stRadio] label:has(input:checked){background:#252320!important;border-color:#3F3D39!important;color:#EDEAE4!important}
[data-testid=stChatInput] button{background:#EDEAE4!important}
[data-testid=stChatMessageContent] p{color:#EDEAE4!important}
.stAlert{border-color:#2E2C29!important;background:#1F1E1C!important}
[data-testid=stMetricValue]{color:#EDEAE4!important}
[data-testid=stMetricLabel] p{color:#5E5C58!important}
.reg-card{background:#1F1E1C!important;border-color:#2E2C29!important}
.rp-wrap{background:#1C1B19!important;border-color:#2E2C29!important}
.copy-btn{color:#5E5C58!important;border-color:#2E2C29!important}
.copy-btn:hover{background:#252320!important;color:#EDEAE4!important}
.intent-banner{background:#1E1C12!important;border-color:#3A3518!important}
::-webkit-scrollbar-thumb{background:#3F3D39!important}
[data-testid=stBaseButton-headerNoPadding],[data-testid=stSidebarCollapseButton] button{background:#1C1B19!important;border-color:#2E2C29!important}
code,pre,[data-testid=stMarkdownContainer] code{background:#252320!important;color:#9B9690!important}
table th{background:#1F1E1C!important;color:#9B9690!important;border-color:#2E2C29!important}
table td{background:#141312!important;color:#EDEAE4!important;border-color:#2E2C29!important}
"""
    else:
        css = """
:root {
  --bg:#F9F8F5; --bg-sb:#F3F2EF; --sur:#FFFFFF;
  --t1:#1A1917; --t2:#6B6760;  --t3:#9B9894;
  --bd:#E5E3DE; --bd2:#C8C5BF; --acc:#EDECEA;
  --bg-warn:#FDFAF3; --bd-warn:#E8DEBB;
  --r:3px; --tr:160ms ease;
}
"""

    return f"""<script>
(function() {{
  var css = {repr(css)};
  var sid = 'st-theme-vars';
  function inject() {{
    try {{
      var doc = (window.parent && window.parent !== window)
                ? window.parent.document : document;
      var el = doc.getElementById(sid);
      if (el) {{ if (el.textContent !== css) el.textContent = css; return; }}
      el = doc.createElement('style');
      el.id = sid;
      el.textContent = css;
      (doc.head || doc.documentElement).appendChild(el);
    }} catch(e) {{}}
  }}
  inject();
  [40, 120, 300, 700, 1500].forEach(function(d) {{ setTimeout(inject, d); }});
  /* Re-inject if Streamlit wipes our tag */
  try {{
    var root = (window.parent && window.parent !== window)
               ? window.parent.document.documentElement : document.documentElement;
    new MutationObserver(function() {{
      var d = root.ownerDocument || document;
      if (!d.getElementById(sid)) inject();
    }}).observe(root, {{childList:true, subtree:false}});
  }} catch(e) {{}}
}})();
</script>"""



# ── Session state ─────────────────────────────────────────────────────────

def _is_dark() -> bool:
    """Current theme: session_state overrides native theme detection."""
    return st.session_state.get("dark_mode", False)

def _init():
    defaults = {
        "current_conv_id": None,
        "model": "ollama/mistral",
        "api_key": "",
        "model_status": "standby",
        "source_filter": None,
        "language_filter": None,
        "registry_view": "cards",
        "editing_id": None,
        "show_add_form": False,
        "pending_prompt": None,
        "pending_register": None,
        "intent_checked_for": None,
        "show_right_panel": True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # Seed dark_mode from native Streamlit theme on first run only
    if "dark_mode" not in st.session_state:
        try:
            st.session_state["dark_mode"] = st.context.theme.type == "dark"
        except AttributeError:
            st.session_state["dark_mode"] = False

_init()

# ── Cached resources ──────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Initialising store...")
def _get_store():
    from ingestion.store import DocumentStore
    return DocumentStore(db_path=DATA_DIR)

@st.cache_resource(show_spinner="Loading retrieval...")
def _get_retriever(_store):
    from retrieval.retriever import Retriever
    return Retriever(store=_store)

@st.cache_resource(show_spinner="Connecting to model...")
def _get_chain(_model: str, _api_key: str):
    from generation.chain import ComplianceChain
    from generation.llm import LLMConfig
    store = _get_store()
    retriever = _get_retriever(store)
    return ComplianceChain(
        llm_config=LLMConfig(model=_model, api_key=_api_key or None),
        store=store, retriever=retriever,
    )

def _get_llm_client():
    from generation.llm import LLMClient, LLMConfig
    return LLMClient(LLMConfig(
        model=st.session_state.model,
        api_key=st.session_state.api_key or None,
        temperature=0.1, max_tokens=256,
    ))

# ── Conversation persistence ──────────────────────────────────────────────

def _list_conversations() -> list:
    convs = []
    for p in CONV_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text())
            convs.append({"id": data["id"], "title": data.get("title", "Untitled"),
                          "created_at": data.get("created_at", "")})
        except Exception:
            pass
    return sorted(convs, key=lambda x: x["created_at"], reverse=True)

def _load_conversation(conv_id: str) -> dict | None:
    p = CONV_DIR / f"{conv_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None

def _save_conversation(conv: dict):
    p = CONV_DIR / f"{conv['id']}.json"
    p.write_text(json.dumps(conv, indent=2, ensure_ascii=False))

def _new_conversation() -> dict:
    conv = {"id": str(uuid.uuid4()), "title": "New conversation",
            "created_at": datetime.now().isoformat(), "messages": []}
    _save_conversation(conv)
    return conv

def _delete_conversation(conv_id: str):
    p = CONV_DIR / f"{conv_id}.json"
    p.unlink(missing_ok=True)

def _current_messages() -> list:
    if not st.session_state.current_conv_id:
        return []
    conv = _load_conversation(st.session_state.current_conv_id)
    return conv["messages"] if conv else []

def _append_message(msg: dict):
    if not st.session_state.current_conv_id:
        conv = _new_conversation()
        st.session_state.current_conv_id = conv["id"]
    conv = _load_conversation(st.session_state.current_conv_id)
    if not conv:
        return
    conv["messages"].append(msg)
    # Auto-title from first user message
    if len(conv["messages"]) == 1 and msg["role"] == "user":
        conv["title"] = msg["content"][:45] + ("…" if len(msg["content"]) > 45 else "")
    _save_conversation(conv)

# ── Registry persistence ──────────────────────────────────────────────────

def _load_registry() -> list:
    if not REGISTRY_PATH.exists():
        return []
    try:
        return json.loads(REGISTRY_PATH.read_text())
    except Exception:
        return []

def _save_registry(entries: list):
    REGISTRY_PATH.write_text(json.dumps(entries, indent=2, ensure_ascii=False))

# ── Intent detection ──────────────────────────────────────────────────────

def _detect_intent(user_message: str) -> dict | None:
    """Returns extracted AI system info if user seems to be describing one, else None."""
    # Quick keyword pre-filter to avoid unnecessary LLM calls
    triggers = ["i am a", "i'm a", "we are", "we use", "i use", "i deploy", "our system",
                "our ai", "my system", "my company", "we have an", "we have a", "i have a",
                "i have an", "deployer", "provider", "operator"]
    msg_lower = user_message.lower()
    if not any(t in msg_lower for t in triggers):
        return None
    # LLM classification
    system = (
        "Determine if the user message describes an AI system they use or deploy. "
        "If yes, extract: name (short name), description (what it does), "
        "role (deployer/provider/operator/user), tags (1-4 keywords). "
        "Respond ONLY with a JSON object with keys: is_ai_system (bool), "
        "name (str), description (str), role (str), tags (array of strings). "
        "If is_ai_system is false all other fields may be empty."
    )
    try:
        client = _get_llm_client()
        raw = client.complete(system=system, user=user_message).strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        if result.get("is_ai_system") and result.get("name"):
            return result
    except Exception:
        pass
    return None

# ── Risk analysis ─────────────────────────────────────────────────────────

def _analyse_entry(entry: dict) -> dict:
    system = (
        "You are an EU AI Act compliance expert. Classify the AI system. "
        "Respond ONLY with JSON with keys: risk_level (one of Unacceptable, High, Limited, Minimal) "
        "and precision (integer 0-100 = confidence). No markdown, no explanation. "
        "Unacceptable: prohibited AI (social scoring, subliminal manipulation). "
        "High: Annex III sectors (biometrics, critical infra, education, employment, "
        "essential services, law enforcement, migration, justice). "
        "Limited: chatbots, emotion recognition, deepfakes. Minimal: everything else."
    )
    tags_str = ", ".join(entry.get("tags", [])) or "none"
    user = f"Name: {entry['name']}\nDescription: {entry['description']}\nTags: {tags_str}\nRole: {entry.get('role') or 'not specified'}"
    try:
        client = _get_llm_client()
        raw = client.complete(system=system, user=user).strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        risk = result.get("risk_level", "Minimal")
        if risk not in ("Unacceptable", "High", "Limited", "Minimal"):
            risk = "Minimal"
        precision = max(0, min(100, int(result.get("precision", 50))))
        st.session_state.model_status = "ready"
        return {"risk_level": risk, "precision": precision}
    except Exception as e:
        st.session_state.model_status = "error"
        return {"risk_level": None, "precision": None, "error": str(e)}

# ── HTML helpers ──────────────────────────────────────────────────────────

def _S(style: str) -> str:
    """Shorthand: wrap style string."""
    return f'style="{style}"'

def _risk_badge(risk: str | None) -> str:
    is_dark = _is_dark()
    if not risk:
        return ('<span style="display:inline-block;font-size:10px;font-weight:500;letter-spacing:.05em;'
                'text-transform:uppercase;padding:2px 8px;border-radius:2px;'
                'background:var(--acc);color:var(--t3);border:1px solid var(--bd)">Pending</span>')
    if is_dark:
        colors = {
            "Unacceptable": ("#3B0A0A", "#F87171", "#7F1D1D"),
            "High":         ("#3A1800", "#FB923C", "#7C2D12"),
            "Limited":      ("#2A2300", "#FCD34D", "#78350F"),
            "Minimal":      ("#052614", "#4ADE80", "#14532D"),
        }
    else:
        colors = {
            "Unacceptable": ("#FEF2F2", "#B91C1C", "#FECACA"),
            "High":         ("#FFF7ED", "#C2510A", "#FED7AA"),
            "Limited":      ("#FEFCE8", "#92690E", "#FDE68A"),
            "Minimal":      ("#F0FDF4", "#1E6A3A", "#BBF7D0"),
        }
    bg, fg, border = colors.get(risk, ("#EDECEA", "#9B9894", "#E5E3DE"))
    return (f'<span style="display:inline-block;font-size:10px;font-weight:500;'
            f'letter-spacing:.05em;text-transform:uppercase;padding:2px 8px;'
            f'border-radius:2px;background:{bg};color:{fg};border:1px solid {border}">'
            f'{risk}</span>')

def _precision_bar(precision: int | None) -> str:
    if precision is None:
        return ""
    pct = int(precision)
    return (
        '<div style="display:flex;align-items:center;gap:8px;margin-top:8px">' 
        '<div style="flex:1;height:3px;background:var(--bd);border-radius:2px;overflow:hidden">' 
        f'<div style="height:100%;width:{pct}%;background:var(--t3);border-radius:2px"></div>' 
        '</div>' 
        f'<span style="font-family:monospace;font-size:10px;color:var(--t3)">{pct}% confidence</span>'
        '</div>'
    )

def _sec_label(text: str) -> str:
    return (
        f'<p style="font-family:sans-serif;font-size:9.5px;font-weight:500;'
        f'letter-spacing:.1em;text-transform:uppercase;color:var(--t3);'
        f'border-bottom:1px solid var(--bd);padding-bottom:6px;margin:16px 0 8px">{text}</p>'
    )

def _model_dot(status: str, name: str, no_key: bool = False) -> str:
    color = {"ready": "#22C55E", "standby": "#F59E0B", "error": "#EF4444"}.get(status, "#F59E0B")
    label = "No key" if no_key else {"ready": "Active", "standby": "Standby", "error": "Error"}.get(status, "Standby")
    short = name.replace("ollama/", "")
    return (
        '<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;'
        'background:var(--sur);border:1px solid var(--bd);border-radius:3px;margin-top:6px">' 
        f'<span style="width:7px;height:7px;border-radius:50%;background:{color};flex-shrink:0;display:inline-block"></span>'
        f'<span style="font-family:monospace;font-size:11px;color:var(--t2);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{short}</span>'
        f'<span style="font-family:sans-serif;font-size:10px;color:var(--t3)">{label}</span>'
        '</div>'
    )

# ── Citations ─────────────────────────────────────────────────────────────

def _render_citations(citations: list, low_confidence: bool = False):
    if not citations:
        return
    if low_confidence:
        st.markdown(
            '<div style="background:var(--bg-warn,#FDFAF3);border:1px solid var(--bd-warn,#EDE8D8);border-radius:3px;'
            'padding:8px 12px;margin-bottom:8px;font-size:12px;color:var(--t2)">'
            'Low retrieval confidence — consider rephrasing.</div>',
            unsafe_allow_html=True,
        )
    rows = ""
    for c in citations:
        label = c.get("label", ""); source = c.get("source", ""); lang = c.get("language", "").upper()
        ctype = c.get("chunk_type", ""); ps = c.get("page_start"); pe = c.get("page_end")
        page_ref = ""
        if ps and pe:
            page_ref = f"p.{ps}" if ps == pe else f"pp.{ps}–{pe}"
        meta = " · ".join(p for p in [source, lang, page_ref] if p)
        badge = (f'<span style="font-size:9px;letter-spacing:.07em;text-transform:uppercase;'
                 f'background:var(--acc);color:var(--t2);padding:1px 5px;border-radius:1px;margin-left:6px">{ctype}</span>') if ctype else ""
        rows += (
            '<div style="display:grid;grid-template-columns:1fr auto;gap:8px;align-items:baseline;'
            'padding:6px 12px;border-top:1px solid var(--bd);font-family:monospace;font-size:11.5px">' 
            f'<span style="color:var(--t1)">{label}{badge}</span>'
            f'<span style="color:var(--t3);font-size:10.5px;white-space:nowrap">{meta}</span>'
            '</div>'
        )
    st.markdown(
        f'<div style="margin-top:12px;border:1px solid var(--bd);border-radius:3px">' 
        f'<div style="font-family:sans-serif;font-size:10px;letter-spacing:.07em;text-transform:uppercase;'
        f'color:var(--t3);padding:6px 12px;border-bottom:1px solid var(--bd)">'
        f'Sources · {len(citations)}</div>{rows}</div>',
        unsafe_allow_html=True,
    )

# ── Left sidebar — conversations only ───────────────────────────────────

def _render_sidebar():
    with st.sidebar:
        st.markdown(
            '<p style="font-family:Georgia,serif;font-size:17px;font-weight:400;'
            'color:var(--t1);letter-spacing:-.01em;margin:0 0 1px">EU Compliance</p>'
            '<p style="font-family:sans-serif;font-size:11px;color:var(--t3);'
            'font-weight:300;margin:0 0 16px">Grounded answers from legal text</p>',
            unsafe_allow_html=True,
        )
        st.markdown(_sec_label("Conversations"), unsafe_allow_html=True)
        if st.button("＋ New chat", key="new_conv_btn", use_container_width=True):
            conv = _new_conversation()
            st.session_state.current_conv_id = conv["id"]
            st.session_state.pending_prompt = None
            st.session_state.pending_register = None
            st.rerun()

        convs = _list_conversations()
        for conv in convs[:40]:
            cid = conv["id"]
            is_active = cid == st.session_state.current_conv_id
            date_str = conv["created_at"][:10] if conv["created_at"] else ""
            col_a, col_b = st.columns([5, 1])
            with col_a:
                label = conv["title"]
                if st.button(label, key=f"conv_{cid}", help=date_str,
                             use_container_width=True):
                    st.session_state.current_conv_id = cid
                    st.session_state.pending_register = None
                    st.rerun()
            with col_b:
                if st.button("×", key=f"del_conv_{cid}", help="Delete"):
                    _delete_conversation(cid)
                    if st.session_state.current_conv_id == cid:
                        st.session_state.current_conv_id = None
                    st.rerun()

        # ── Sidebar footer: settings + attribution ──────────────────
        st.markdown('<div style="margin-top:auto;padding-top:16px;border-top:1px solid var(--bd)">', unsafe_allow_html=True)
        show_rp = st.session_state.show_right_panel

        rp_lbl = "⊟ Settings" if show_rp else "⊞ Settings"
        if st.button(rp_lbl, key="rp_toggle_sb", use_container_width=True):
            st.session_state.show_right_panel = not show_rp
            st.rerun()

        st.markdown(
            '<p style="font-size:10px;color:var(--t3);margin:8px 0 0">Open source · MIT</p>'
            '</div>',
            unsafe_allow_html=True,
        )


# ── Right panel — model, filters, documents ──────────────────────────────

def _render_right_panel():
    """Renders into whatever container is active (call inside a column)."""
    st.markdown(
        '<div style="background:var(--bg-sb);border:1px solid var(--bd);border-radius:4px;padding:16px 14px 12px">',
        unsafe_allow_html=True,
    )

    # Model
    st.markdown(_sec_label("Model"), unsafe_allow_html=True)
    model_type = st.radio("backend", ["Local", "API"], horizontal=True,
                          label_visibility="collapsed", key="rp_backend")

    if model_type == "Local":
        chosen = st.selectbox("model", [
            "ollama/mistral", "ollama/llama3.2", "ollama/llama3.2:3b",
            "ollama/llama3.1", "ollama/llama3.1:8b",
            "ollama/gemma3:9b", "ollama/qwen2.5:14b", "ollama/qwen2.5:7b", "ollama/phi4",
        ], label_visibility="collapsed", key="rp_local_model")
        if chosen != st.session_state.model:
            st.session_state.model = chosen
            st.session_state.model_status = "standby"
        st.session_state.api_key = ""
        st.markdown(_model_dot(st.session_state.model_status, chosen), unsafe_allow_html=True)
        with st.expander("Hardware guide"):
            st.markdown("| RAM | Model |\n|-----|-------|\n| 8 GB | `mistral` |\n| 16 GB | `llama3.2` |\n| 24 GB+ | `qwen2.5:14b` |")
    else:
        api_key = st.text_input("API key", type="password",
                                placeholder="sk-…  /  sk-ant-…  /  AIza…",
                                value=st.session_state.api_key,
                                key="rp_api_key")
        if api_key.startswith("sk-ant-"):
            detected_model, detected_provider = "anthropic/claude-sonnet-4-6", "Anthropic"
        elif api_key.startswith("sk-"):
            detected_model, detected_provider = "openai/gpt-4o-mini", "OpenAI"
        elif api_key.startswith("AIza"):
            # Google AI Studio keys — route to Gemini via LiteLLM
            detected_model, detected_provider = "gemini/gemini-1.5-flash", "Google"
        elif api_key.strip():
            detected_model, detected_provider = "mistral/mistral-large-latest", "Mistral"
        else:
            # No key entered yet. Keep the current model only if it is already an
            # API-backed model; otherwise fall back to a safe API default so the
            # app never tries to reach Ollama when the user has selected API mode.
            current = st.session_state.model
            detected_model = current if not current.startswith("ollama/") else "openai/gpt-4o-mini"
            detected_provider = None
        if api_key != st.session_state.api_key:
            st.session_state.model_status = "standby"
        if detected_model:
            st.session_state.model = detected_model
        st.session_state.api_key = api_key
        if api_key.strip() and detected_provider:
            st.markdown(
                f'<p style="font-size:11px;color:var(--t3);margin:-2px 0 4px">' 
                f'Detected: {detected_provider} → <code style="font-size:10.5px">{detected_model}</code></p>',
                unsafe_allow_html=True,
            )
        st.markdown(_model_dot(st.session_state.model_status,
                               detected_model or "—",
                               no_key=not api_key.strip()), unsafe_allow_html=True)

    # Search filters
    st.markdown(_sec_label("Filters"), unsafe_allow_html=True)
    store = _get_store()
    try:
        source_names = sorted({r["source"] for r in store.list_sources()})
    except Exception:
        source_names = []
    sel_src = st.selectbox("Source", ["All"] + source_names, key="rp_source")
    st.session_state.source_filter = None if sel_src == "All" else sel_src
    sel_lang = st.selectbox("Language", ["All", "EN", "DE", "FR", "IT", "ES"], key="rp_lang")
    st.session_state.language_filter = None if sel_lang == "All" else sel_lang.lower()

    # Documents
    st.markdown(_sec_label("Documents"), unsafe_allow_html=True)
    try:
        stats = store.stats()
    except Exception:
        stats = {"real_chunks": 0, "by_source": {}}
    if stats["real_chunks"] == 0:
        st.markdown('<p style="font-size:12px;color:var(--t3);font-style:italic">No documents ingested.</p>', unsafe_allow_html=True)
    else:
        for key, counts in stats["by_source"].items():
            st.markdown(
                f'<div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid var(--bd)">' 
                f'<span style="font-size:11.5px;color:var(--t1);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{key}</span>' 
                f'<span style="font-family:monospace;font-size:10px;color:var(--t3)">{counts.get("article",0)}a {counts.get("recital",0)}r {counts.get("annex",0)}x</span>' 
                f'</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ── Welcome screen ────────────────────────────────────────────────────────

def _render_welcome_header():
    """Big heading + subtitle — shown at the top before the chat input."""
    st.markdown(
        '<div style="max-width:540px;padding:32px 0 16px">'
        '<p style="font-family:Georgia,serif;font-size:36px;font-weight:400;'
        'letter-spacing:-.03em;color:var(--t1);line-height:1.15;margin-bottom:10px">'
        'Ask anything about<br>EU AI regulation.</p>'
        '<p style="font-size:13px;color:var(--t2);font-weight:300;line-height:1.6;margin:0">'
        'Compliance questions answered with direct citations to articles, recitals and annexes.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

def _render_welcome_examples():
    """Example question buttons — shown BELOW the chat input."""
    st.markdown(
        '<p style="font-size:9.5px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;'
        'color:var(--t3);margin:16px 0 10px">Examples</p>',
        unsafe_allow_html=True,
    )
    examples = [
        "What transparency obligations apply to high-risk AI systems?",
        "Which AI applications are prohibited under the AI Act?",
        "What are the conformity assessment requirements?",
        "How is a high-risk AI system defined?",
        "What obligations apply to general-purpose AI model providers?",
        "What is the role of the AI Office?",
    ]
    cols = st.columns(2, gap="small")
    for i, q in enumerate(examples):
        with cols[i % 2]:
            if st.button(q, key=f"ex_{i}", use_container_width=True):
                if not st.session_state.current_conv_id:
                    conv = _new_conversation()
                    st.session_state.current_conv_id = conv["id"]
                st.session_state.pending_prompt = q
                st.rerun()

# ── Chat view ─────────────────────────────────────────────────────────────

def _copy_button(text: str, key: str):
    """
    Copy via st.markdown + window.parent.navigator.clipboard.
    st.markdown injects into the main page DOM (no iframe), so the parent
    clipboard API is directly accessible without any permission headers.
    """
    import json as _j, hashlib as _h
    # unique element id so multiple buttons on same page don't collide
    uid = "cb_" + _h.md5((text + key).encode()).hexdigest()[:8]
    payload = _j.dumps(text)          # safe JSON-encoded string
    st.markdown(
        f'''<div style="margin:2px 0 6px">
<button id="{uid}" onclick="(function(){{
  var t={payload};
  var btn=document.getElementById(\'{uid}\');
  var done=function(){{btn.textContent=\'Copied ✓\';btn.style.color=\'#22C55E\';
    setTimeout(function(){{btn.textContent=\'Copy answer\';btn.style.color=\'\'}},1800)}};
  if(window.parent&&window.parent.navigator&&window.parent.navigator.clipboard){{
    window.parent.navigator.clipboard.writeText(t).then(done).catch(function(){{
      try{{var a=document.createElement(\'textarea\');a.value=t;
        document.body.appendChild(a);a.select();document.execCommand(\'copy\');
        document.body.removeChild(a);done()}}catch(e){{btn.textContent=\'Failed\'}}
      }});
  }} else {{
    try{{var a=document.createElement(\'textarea\');a.value=t;
      document.body.appendChild(a);a.select();document.execCommand(\'copy\');
      document.body.removeChild(a);done()}}catch(e){{btn.textContent=\'Failed\'}}
  }}
}})()"
style="font-family:monospace;font-size:10px;color:var(--t3);background:transparent;
border:1px solid var(--bd);border-radius:2px;padding:2px 8px;cursor:pointer;
transition:all 120ms ease">Copy answer</button></div>''',
        unsafe_allow_html=True,
    )

def _render_chat():
    messages = _current_messages()

    # Message history
    for i, msg in enumerate(messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("citations"):
                _render_citations(msg["citations"], msg.get("low_confidence", False))
            if msg["role"] == "assistant":
                _copy_button(msg["content"], key=f"copy_{i}")

    # Intent registration banner
    pr = st.session_state.get("pending_register")
    if pr:
        st.markdown(
            '<div style="background:var(--bg-warn,#FDFAF3);border:1px solid var(--bd-warn,#E8DEBB);border-radius:3px;'
            'padding:12px 16px;margin:8px 0">' 
            '<p style="font-size:13.5px;font-weight:500;color:var(--t1);margin:0 0 3px">'
            'It looks like you described an AI system.</p>' 
            f'<p style="font-size:12px;color:var(--t2);margin:0 0 10px">'
            f'<strong>{pr.get("name","")}</strong> — {pr.get("description","")} ' 
            f'(role: {pr.get("role","—")}). Add it to your registry?</p>' 
            '</div>',
            unsafe_allow_html=True,
        )
        reg_yes, reg_no = st.columns([1, 1])
        with reg_yes:
            if st.button("Yes, register it", key="register_yes", type="primary"):
                entries = _load_registry()
                new_entry = {
                    "id": str(uuid.uuid4()),
                    "name": pr.get("name", "Untitled"),
                    "description": pr.get("description", ""),
                    "tags": pr.get("tags", []),
                    "role": pr.get("role", ""),
                    "risk_level": None, "precision": None,
                }
                with st.spinner("Analysing risk level..."):
                    analysis = _analyse_entry(new_entry)
                new_entry.update(analysis)
                entries.append(new_entry)
                _save_registry(entries)
                st.session_state.pending_register = None
                st.success(f"✓ {new_entry['name']} registered — {new_entry.get('risk_level','?')} risk.")
                st.rerun()
        with reg_no:
            if st.button("No thanks", key="register_no"):
                st.session_state.pending_register = None
                st.rerun()

    # Pending prompt from example buttons
    pending = st.session_state.pop("pending_prompt", None)
    chat_prompt = st.chat_input("Ask a compliance question")
    prompt = pending or chat_prompt

    if not prompt:
        return

    # Ensure a conversation exists
    if not st.session_state.current_conv_id:
        conv = _new_conversation()
        st.session_state.current_conv_id = conv["id"]

    # Show user message
    with st.chat_message("user"):
        st.markdown(prompt)
    _append_message({"role": "user", "content": prompt})

    # Check store
    store = _get_store()
    if store.stats()["real_chunks"] == 0:
        reply = "No documents have been ingested. Run the ingestion pipeline first."
        with st.chat_message("assistant"):
            st.markdown(reply)
        _append_message({"role": "assistant", "content": reply})
        return

    # Generate answer
    with st.chat_message("assistant"):
        try:
            chain = _get_chain(st.session_state.model, st.session_state.api_key)
        except Exception as e:
            st.session_state.model_status = "error"
            st.error(f"Could not initialise model: {e}")
            return

        with st.spinner("Searching..."):
            try:
                retrieval = chain.retriever.retrieve(
                    query=prompt,
                    source=st.session_state.source_filter,
                    language=st.session_state.language_filter,
                )
            except Exception as e:
                st.error(f"Retrieval failed: {e}")
                return

        from generation.prompt import build_system_prompt, build_user_prompt, format_citations
        system = build_system_prompt(low_confidence=retrieval.low_confidence)
        user_prompt_text = build_user_prompt(prompt, retrieval)

        placeholder = st.empty()
        placeholder.markdown(
            '<span style="color:var(--t3);font-style:italic;font-size:13px">… Thinking</span>',
            unsafe_allow_html=True,
        )
        full_response = ""
        try:
            for token in chain.llm.stream(system=system, user=user_prompt_text):
                full_response += token
                placeholder.markdown(full_response + "▌")
            st.session_state.model_status = "ready"
        except RuntimeError as e:
            st.session_state.model_status = "error"
            st.error(str(e))
            if full_response:
                placeholder.markdown(full_response)
            return

        placeholder.markdown(full_response)
        citations = format_citations(retrieval)
        if citations:
            _render_citations(citations, retrieval.low_confidence)
        # Use message count for a unique, stable key that won't collide on rerun
        msg_index = len(_current_messages())
        _copy_button(full_response, key=f"copy_new_{msg_index}")

        _append_message({
            "role": "assistant", "content": full_response,
            "citations": citations, "low_confidence": retrieval.low_confidence,
        })

    # Intent detection (don't re-check if we already checked this exact message)
    if prompt != st.session_state.get("intent_checked_for"):
        st.session_state.intent_checked_for = prompt
        intent = _detect_intent(prompt)
        if intent:
            st.session_state.pending_register = intent
            st.rerun()

# ── Registry ──────────────────────────────────────────────────────────────

def _render_registry():
    st.markdown(
        '<p style="font-family:Georgia,serif;font-size:22px;font-weight:400;'
        'letter-spacing:-.02em;color:var(--t1);margin:0 0 3px">AI Systems Registry</p>'
        '<p style="font-size:12px;color:var(--t3);font-weight:300;margin:0 0 20px">'
        'Track your AI systems and their EU AI Act risk classification.</p>',
        unsafe_allow_html=True,
    )
    entries = _load_registry()

    # Toolbar
    t1, t2, t3 = st.columns([3, 3, 2])
    with t1:
        view = st.radio("view", ["Cards", "Table"], horizontal=True,
                        label_visibility="collapsed",
                        index=0 if st.session_state.registry_view == "cards" else 1)
        st.session_state.registry_view = view.lower()
    with t3:
        lbl = "Cancel" if st.session_state.show_add_form else "+ Add system"
        if st.button(lbl, key="toggle_add"):
            st.session_state.show_add_form = not st.session_state.show_add_form
            st.session_state.editing_id = None
            st.rerun()

    # Add form
    if st.session_state.show_add_form:
        with st.container():
            st.markdown('<p style="font-size:13.5px;font-weight:500;color:var(--t1);margin:12px 0 8px">New AI system</p>', unsafe_allow_html=True)
            n_name = st.text_input("Name *", placeholder="e.g. CV Screening Tool", key="new_name")
            n_desc = st.text_area("Description *", placeholder="What it does, its inputs and outputs.", key="new_desc", height=80)
            c1, c2 = st.columns(2)
            with c1:
                n_tags = st.text_input("Tags", placeholder="nlp, hr, screening", key="new_tags")
            with c2:
                n_role = st.text_input("Role / Owner", placeholder="e.g. Deployer", key="new_role")
            st.caption("Risk level and confidence are determined automatically by the LLM.")
            if st.button("Save & Analyse", type="primary", key="save_new"):
                if not n_name.strip():
                    st.error("Name is required.")
                elif not n_desc.strip():
                    st.error("Description is required.")
                else:
                    new_entry = {
                        "id": str(uuid.uuid4()), "name": n_name.strip(),
                        "description": n_desc.strip(),
                        "tags": [t.strip() for t in n_tags.split(",") if t.strip()],
                        "role": n_role.strip(), "risk_level": None, "precision": None,
                    }
                    with st.spinner("Analysing..."):
                        analysis = _analyse_entry(new_entry)
                    new_entry.update(analysis)
                    if analysis.get("error"):
                        st.warning(f"Analysis failed: {analysis['error']}")
                    entries.append(new_entry)
                    _save_registry(entries)
                    st.session_state.show_add_form = False
                    st.rerun()
        st.markdown('<hr style="border:none;border-top:1px solid var(--bd);margin:14px 0">', unsafe_allow_html=True)

    if not entries:
        st.markdown('<p style="font-size:13px;color:var(--t3);font-style:italic;padding:24px 0">No AI systems registered yet. Click <strong>+ Add system</strong> to get started.</p>', unsafe_allow_html=True)
        return

    # Summary metrics
    by_risk = {}
    for e in entries:
        k = e.get("risk_level") or "Pending"
        by_risk[k] = by_risk.get(k, 0) + 1
    mcols = st.columns(min(len(by_risk) + 1, 6))
    mcols[0].metric("Total", len(entries))
    for idx, rl in enumerate(["Unacceptable", "High", "Limited", "Minimal", "Pending"]):
        if rl in by_risk and idx + 1 < len(mcols):
            mcols[idx + 1].metric(rl, by_risk[rl])
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Table view ────────────────────────────────────────────────────────────────────────
    if st.session_state.registry_view == "table":
        is_dark = _is_dark()
        TH = ("font-size:9.5px;font-weight:500;letter-spacing:.09em;text-transform:uppercase;"
              "color:var(--t3);padding:4px 4px 8px;border-bottom:2px solid var(--bd2);margin:0")
        hcols = st.columns([2.2, 3.2, 2, 1.4, 1.6, 1.1, 1.6])
        for col, lbl in zip(hcols, ["Name", "Description", "Tags", "Role", "Risk", "Conf.", "Actions"]):
            col.markdown(f'<p style="{TH}">{lbl}</p>', unsafe_allow_html=True)
        for idx, e in enumerate(entries):
            eid = e["id"]
            tags_s = ", ".join(e.get("tags", [])) or "—"
            prec = f"{e['precision']}%" if e.get("precision") is not None else "—"
            # Dark-mode aware alternating row backgrounds
            if is_dark:
                bg = "#1C1B19" if idx % 2 == 0 else "#1F1E1C"
            else:
                bg = "#FDFAF3" if idx % 2 == 0 else "#FFFFFF"
            TD = f"background:{bg};border-bottom:1px solid var(--bd);padding:8px 4px;margin:0;line-height:1.4"
            rc = st.columns([2.2, 3.2, 2, 1.4, 1.6, 1.1, 1.6])
            rc[0].markdown(f'<p style="{TD};font-weight:500;color:var(--t1);font-size:13px">{e["name"]}</p>', unsafe_allow_html=True)
            d = e["description"][:65] + ("…" if len(e.get("description","")) > 65 else "")
            rc[1].markdown(f'<p style="{TD};color:var(--t2);font-size:12px">{d}</p>', unsafe_allow_html=True)
            rc[2].markdown(f'<p style="{TD};font-family:monospace;font-size:10.5px;color:var(--t3)">{tags_s}</p>', unsafe_allow_html=True)
            rc[3].markdown(f'<p style="{TD};color:var(--t2);font-size:12px">{e.get("role","—")}</p>', unsafe_allow_html=True)
            rc[4].markdown(f'<p style="{TD}">{_risk_badge(e.get("risk_level"))}</p>', unsafe_allow_html=True)
            rc[5].markdown(f'<p style="{TD};font-family:monospace;font-size:11px;color:var(--t3);text-align:right">{prec}</p>', unsafe_allow_html=True)
            with rc[6]:
                ba, bb = st.columns(2)
                with ba:
                    if st.button("Edit", key=f"te_{eid}", use_container_width=True):
                        st.session_state.editing_id = eid
                        st.session_state.registry_view = "cards"
                        st.rerun()
                with bb:
                    if st.button("Del", key=f"td_{eid}", use_container_width=True):
                        entries = [x for x in entries if x["id"] != eid]
                        _save_registry(entries)
                        st.rerun()
        return

    # ── Cards view ─────────────────────────────────────────────────────────
    for entry in entries:
        eid = entry["id"]
        is_editing = st.session_state.editing_id == eid

        if is_editing:
            with st.container():
                st.markdown(f'<p style="font-size:13.5px;font-weight:500;color:var(--t1);margin:0 0 8px">Editing: {entry["name"]}</p>', unsafe_allow_html=True)
                e_name = st.text_input("Name *", value=entry["name"], key=f"en_{eid}")
                e_desc = st.text_area("Description *", value=entry["description"], key=f"ed_{eid}", height=80)
                ec1, ec2 = st.columns(2)
                with ec1:
                    e_tags = st.text_input("Tags", value=", ".join(entry.get("tags", [])), key=f"et_{eid}")
                with ec2:
                    e_role = st.text_input("Role / Owner", value=entry.get("role", ""), key=f"er_{eid}")
                st.caption("Saving will re-run risk analysis.")
                bc1, bc2, _ = st.columns([1, 1, 5])
                with bc1:
                    if st.button("Save", type="primary", key=f"es_{eid}"):
                        if not e_name.strip() or not e_desc.strip():
                            st.error("Name and description are required.")
                        else:
                            updated = {**entry, "name": e_name.strip(), "description": e_desc.strip(),
                                       "tags": [t.strip() for t in e_tags.split(",") if t.strip()],
                                       "role": e_role.strip(), "risk_level": None, "precision": None}
                            with st.spinner("Re-analysing..."):
                                analysis = _analyse_entry(updated)
                            updated.update(analysis)
                            entries = [updated if x["id"] == eid else x for x in entries]
                            _save_registry(entries)
                            st.session_state.editing_id = None
                            st.rerun()
                with bc2:
                    if st.button("Cancel", key=f"ec_{eid}"):
                        st.session_state.editing_id = None
                        st.rerun()
            st.markdown('<hr style="border:none;border-top:1px solid var(--bd);margin:12px 0">', unsafe_allow_html=True)
        else:
            tags_html = " ".join(
                f'<span style="font-family:monospace;font-size:10px;color:var(--t2);'
                f'background:var(--acc);padding:2px 7px;border-radius:2px">{t}</span>'
                for t in entry.get("tags", [])
            )
            role_html = (f'<span style="font-size:11px;color:var(--t3);margin-left:6px">{entry["role"]}</span>'
                        if entry.get("role") else "")
            st.markdown(
                '<div style="background:var(--sur);border:1px solid var(--bd);border-radius:3px;'
                'padding:14px 16px;margin-bottom:4px">' 
                '  <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:5px">' 
                f'    <span style="font-size:13.5px;font-weight:500;color:var(--t1);flex:1">{entry["name"]}</span>' 
                f'    {_risk_badge(entry.get("risk_level"))}' 
                '  </div>' 
                f'  <p style="font-size:13px;color:var(--t2);line-height:1.55;margin:0 0 8px">{entry["description"]}</p>' 
                f'  <div style="display:flex;flex-wrap:wrap;gap:5px;align-items:center">{tags_html}{role_html}</div>' 
                f'  {_precision_bar(entry.get("precision"))}' 
                '</div>',
                unsafe_allow_html=True,
            )
            b1, b2, _ = st.columns([1, 1, 8])
            with b1:
                if st.button("Edit", key=f"e_{eid}"):
                    st.session_state.editing_id = eid
                    st.rerun()
            with b2:
                if st.button("Delete", key=f"d_{eid}"):
                    entries = [x for x in entries if x["id"] != eid]
                    _save_registry(entries)
                    st.rerun()
            st.markdown("<div style='margin-bottom:6px'></div>", unsafe_allow_html=True)


# ── Help / how-to tab ─────────────────────────────────────────────────────

def _render_help():
    # Use CSS variables throughout — dark mode is applied globally via the
    # _make_css_script injection, so var(--*) tokens just work here.
    # The risk-level colour chips use semantic colours that read well on both
    # light and dark backgrounds (kept as explicit hex for semantic meaning).
    dm = _is_dark()
    # Risk colours — need to differ slightly between modes for readability
    risk_colors = {
        "Unacceptable": "#F87171" if dm else "#B91C1C",
        "High":         "#FB923C" if dm else "#C2510A",
        "Limited":      "#FCD34D" if dm else "#92690E",
        "Minimal":      "#4ADE80" if dm else "#1E6A3A",
    }

    def section(title, body):
        st.markdown(
            f'<div style="background:var(--sur);border:1px solid var(--bd);border-radius:3px;'
            f'padding:20px 22px 18px;margin-bottom:12px">'
            f'<div style="margin-bottom:10px">'
            f'<span style="font-family:Georgia,serif;font-size:16px;font-weight:400;color:var(--t1)">{title}</span>'
            f'</div>'
            f'<div style="font-size:13.5px;line-height:1.75;color:var(--t2);font-family:system-ui,sans-serif">{body}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    def tag(t):
        return (f'<code style="background:var(--acc);color:var(--t2);font-size:11px;'
                f'padding:1px 6px;border-radius:2px;font-family:monospace">{t}</code>')

    def kbd(t):
        return (f'<kbd style="background:var(--acc);color:var(--t1);font-size:11px;'
                f'padding:2px 7px;border-radius:2px;border:1px solid var(--bd);font-family:monospace">{t}</kbd>')

    # ── Header ────────────────────────────────────────────────────
    st.markdown(
        '<h2 style="font-family:Georgia,serif;font-size:26px;font-weight:400;'
        'color:var(--t1);margin:0 0 4px">How to use EU Compliance Tool</h2>'
        '<p style="font-size:13.5px;color:var(--t3);margin:0 0 24px;line-height:1.6">'
        'A RAG pipeline grounded in the official EU AI Act text — ask questions, '
        'classify AI systems, and track your compliance obligations.</p>',
        unsafe_allow_html=True,
    )

    col_l, col_r = st.columns(2, gap="large")

    with col_l:
        section("Compliance Q&A",
            f'Ask any question about the EU AI Act in natural language. '
            f'The tool retrieves the most relevant articles, recitals, and annexes, '
            f'then generates an answer grounded exclusively in that text — no hallucinations.<br><br>'
            f'<b>Tips:</b><br>'
            f'• Be specific: {tag("What are the requirements for high-risk AI systems in Article 9?")} '
            f'works better than {tag("tell me about high-risk AI")}<br>'
            f'• Include the system type: {tag("Does a CV-screening tool need a conformity assessment?")}<br>'
            f'• Ask follow-ups — the tool keeps conversation context within a session<br>'
            f'• If the answer says <em>low confidence</em>, rephrase or check the source PDFs directly'
        )

        section("AI Systems Registry",
            f'Track AI systems your organisation uses or develops. Each entry stores name, '
            f'description, tags, and role (provider / deployer / importer).<br><br>'
            f'<b>AI risk classification</b> is run automatically when you save a new system — '
            f'it calls the active LLM to assign one of four EU AI Act risk tiers:<br><br>'
            f'<div style="display:grid;grid-template-columns:auto 1fr;gap:4px 10px;font-size:12.5px">'
            f'<span style="color:{risk_colors["Unacceptable"]};font-weight:500">Unacceptable</span>'
            f'<span style="color:var(--t2)">Banned systems — e.g. social scoring, real-time biometric surveillance in public spaces</span>'
            f'<span style="color:{risk_colors["High"]};font-weight:500">High risk</span>'
            f'<span style="color:var(--t2)">Annex III systems — e.g. CV screening, credit scoring, biometric identification</span>'
            f'<span style="color:{risk_colors["Limited"]};font-weight:500">Limited risk</span>'
            f'<span style="color:var(--t2)">Transparency-only obligations — e.g. chatbots, deepfake generators</span>'
            f'<span style="color:{risk_colors["Minimal"]};font-weight:500">Minimal risk</span>'
            f'<span style="color:var(--t2)">No specific obligations under the Act</span>'
            f'</div>'
        )

    with col_r:
        section("Settings panel",
            f'Toggle the settings panel with the {kbd("⊟ Settings")} button at the top right.<br><br>'
            f'<b>Model backend:</b><br>'
            f'• <b>Local</b> — requires <a href="https://ollama.ai" style="color:var(--t2)">Ollama</a> running on your machine '
            f'(<code style="font-size:11px">ollama serve</code>). No API key needed, fully private.<br>'
            f'• <b>API</b> — paste an API key; the provider is auto-detected from the key prefix:<br>'
            f'&nbsp;&nbsp;&nbsp;– <code style="font-size:11px">sk-ant-…</code> → Anthropic (Claude)<br>'
            f'&nbsp;&nbsp;&nbsp;– <code style="font-size:11px">sk-…</code> → OpenAI (GPT-4o-mini)<br>'
            f'&nbsp;&nbsp;&nbsp;– <code style="font-size:11px">AIza…</code> → Google AI Studio (Gemini)<br>'
            f'&nbsp;&nbsp;&nbsp;– anything else → Mistral<br><br>'
            f'<b>Filters:</b><br>'
            f'Narrow retrieval to a specific source document or language using the dropdowns. '
            f'Useful when you have ingested multiple language versions of the Act.'
        )

        section("Ingesting documents",
            f'The tool ships with the official EN version of the EU AI Act pre-ingested. '
            f'To add more PDFs (e.g. other languages, delegated acts, guidelines):<br><br>'
            f'<div style="font-family:monospace;font-size:12px;background:var(--acc);'
            f'padding:10px 12px;border-radius:3px;line-height:1.8;color:var(--t2)">'
            f'python -m ingestion.pipeline ingest path/to/file.pdf<br>'
            f'python -m ingestion.pipeline list<br>'
            f'python -m ingestion.pipeline delete "Document Name"'
            f'</div><br>'
            f'Re-ingestion of the same file is safe — chunks are upserted, not duplicated.<br>'
            f'The BM25 index rebuilds automatically on each app start.'
        )

        section("Dark / light mode",
            f'Use the {kbd("☾ Dark")} / {kbd("☀ Light")} toggle at the bottom of the left sidebar. '
            f'The app automatically detects your OS preference on first load. '
            f'Your choice is remembered for the session. '
            f'You can also use the {kbd("⋮")} menu → <b>Settings</b> → <b>Theme</b> for a persistent browser-level preference.'
        )

    # Architecture callout
    st.markdown(
        '<div style="border:1px solid var(--bd);border-radius:3px;padding:16px 20px;margin-top:4px">'
        '<p style="font-family:Georgia,serif;font-size:14px;font-weight:400;color:var(--t1);margin:0 0 10px">Architecture overview</p>'
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--bd);border-radius:2px;overflow:hidden;font-size:12px;text-align:center">'
        '<div style="background:var(--sur);padding:10px 8px;color:var(--t2)"><b style="color:var(--t1);display:block;margin-bottom:3px">Layer 1</b>Ingestion<br><span style="font-size:10.5px;color:var(--t3)">PyMuPDF → chunks → ChromaDB</span></div>'
        '<div style="background:var(--sur);padding:10px 8px;color:var(--t2)"><b style="color:var(--t1);display:block;margin-bottom:3px">Layer 2</b>Retrieval<br><span style="font-size:10.5px;color:var(--t3)">BM25 + dense + RRF + reranker</span></div>'
        '<div style="background:var(--sur);padding:10px 8px;color:var(--t2)"><b style="color:var(--t1);display:block;margin-bottom:3px">Layer 3</b>Generation<br><span style="font-size:10.5px;color:var(--t3)">LiteLLM · Ollama / API</span></div>'
        '<div style="background:var(--sur);padding:10px 8px;color:var(--t2)"><b style="color:var(--t1);display:block;margin-bottom:3px">Layer 4</b>Interface<br><span style="font-size:10.5px;color:var(--t3)">Streamlit · sessions · registry</span></div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ── Skeleton loader ───────────────────────────────────────────────────────

def _render_skeleton():
    """Shimmering placeholder shown while cached resources are warming up."""
    st.markdown(
        '<div class="sk-wrap">'
        '<div class="sk-block sk-title-1"></div>'
        '<div class="sk-block sk-title-2"></div>'
        '<div class="sk-block sk-sub"></div>'
        '<div class="sk-block sk-sub2"></div>'
        '<div class="sk-block sk-label"></div>'
        '<div class="sk-btn-row">'
        '  <div class="sk-block sk-btn"></div>'
        '  <div class="sk-block sk-btn"></div>'
        '</div>'
        '<div class="sk-btn-row">'
        '  <div class="sk-block sk-btn"></div>'
        '  <div class="sk-block sk-btn"></div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    # Layout CSS via st.html(). Theme (dark/light) is handled natively by
    # Streamlit via [theme.light]/[theme.dark] in config.toml.
    # _make_css_script() only injects custom CSS variables for hand-crafted HTML.
    st.html(_CSS)
    st.html(_make_css_script(_is_dark()))

    _render_sidebar()

    show_rp = st.session_state.show_right_panel

    if show_rp:
        col_main, col_right = st.columns([3.2, 1], gap="large")
    else:
        col_main = st.container()

    # ── Warm up the store BEFORE rendering the main column.
    #    Use a placeholder so the skeleton shows instantly while the cache
    #    miss resolves (embedding model + ChromaDB init can take ~2-3 s).
    #    On subsequent reruns _get_store() returns instantly from cache.
    with col_main:
        placeholder = st.empty()

    store_ready = st.session_state.get("_store_ready", False)

    if not store_ready:
        with placeholder.container():
            _render_skeleton()
        # This blocks until the store is warm (first run only)
        _get_store()
        st.session_state["_store_ready"] = True
        placeholder.empty()
        st.rerun()

    # Store is ready — render normally
    if show_rp:
        with col_right:
            _render_right_panel()

    with col_main:
        # ── Page header: title left, Clear button right — flush above tabs ──
        messages = _current_messages()
        h_title, h_clear = st.columns([6, 1], gap="small")
        with h_title:
            active_tab = st.session_state.get("active_tab", 0)
            titles = ["EU AI Act Compliance", "AI Systems Registry", "How to use"]
            subtitles = ["Every claim cites a specific article.", "Track AI systems your organisation develops or deploys.", ""]
            st.markdown(
                f'<div style="padding:0 0 0">'
                f'<p style="font-family:Georgia,serif;font-size:20px;font-weight:400;'
                f'letter-spacing:-.02em;color:var(--t1);margin:0 0 1px;line-height:1.2">'
                f'{titles[active_tab]}</p>'
                f'<p style="font-size:11.5px;color:var(--t3);font-weight:300;margin:0">'
                f'{subtitles[active_tab]}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with h_clear:
            if messages and st.button("Clear", key="clear_chat"):
                if st.session_state.current_conv_id:
                    conv = _load_conversation(st.session_state.current_conv_id)
                    if conv:
                        conv["messages"] = []
                        _save_conversation(conv)
                st.session_state.pending_register = None
                st.rerun()

        tab_qa, tab_reg, tab_help = st.tabs(["Compliance Q&A", "AI Systems Registry", "How to use"])
        with tab_qa:
            st.session_state["active_tab"] = 0
            is_welcome = not messages and not st.session_state.get("pending_prompt")
            if is_welcome:
                _render_welcome_header()   # big heading at top
            _render_chat()                 # message history + sticky chat input
            if is_welcome:
                _render_welcome_examples() # example buttons below the input
        with tab_reg:
            st.session_state["active_tab"] = 1
            _render_registry()
        with tab_help:
            st.session_state["active_tab"] = 2
            _render_help()

if __name__ == "__main__":
    main()