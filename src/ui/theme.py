"""
Supply Chain Agent — design tokens & global stylesheet.

This module owns the platform's visual identity: color tokens, typography,
spacing, and the CSS that skins Streamlit's native components into a
premium enterprise look. It contains no business logic — nothing here
should ever need to change for an agent's calculations to change.

Pair with .streamlit/config.toml, which sets the native Streamlit theme
(this is what actually turns the default red primary-button color into
the platform blue, fixes the base background, etc. — CSS alone cannot
reach every native control). This file layers the rest on top: the
sidebar, the top bar / agent header, cards, badges, chips, the nav list,
and typography.
"""
from __future__ import annotations

import streamlit as st

# ============================================================
# BRAND
# ============================================================

PRODUCT_NAME = "Supply Chain Agent"

# Navigation — order defines both the sidebar and the Supervisor's
# agent picker. Icons are Material Symbols names (rounded style, the
# set Streamlit ships and renders natively via `:material/<name>:`),
# chosen to represent each agent's function rather than a generic dot.
NAV_KEYS = ["supervisor", "inventory", "category", "knowledge", "reallocation"]

NAV_LABELS = {
    "supervisor":   "Supervisor",
    "inventory":    "Inventory Analysis",
    "category":     "Category Intelligence",
    "knowledge":    "Knowledge Assistant",
    "reallocation": "Stock Reallocation",
}

NAV_ICONS = {
    "supervisor":   ":material/hub:",
    "inventory":    ":material/inventory_2:",
    "category":     ":material/category:",
    "knowledge":    ":material/menu_book:",
    "reallocation": ":material/sync_alt:",
}

SUPERVISOR_AGENT_MAP = {
    "inventory":    "Inventory Analysis",
    "category":     "Category Intelligence",
    "rag":          "Knowledge Assistant",
    "reallocation": "Stock Reallocation",
}

SUPERVISOR_AGENT_ICONS = {
    "inventory":    ":material/inventory_2:",
    "category":     ":material/category:",
    "rag":          ":material/menu_book:",
    "reallocation": ":material/sync_alt:",
}


# ============================================================
# DESIGN TOKENS
# ============================================================
# Deep-navy system. Blue is reserved for primary actions, active
# navigation, selected states and small accents — the interface itself
# is mostly navy surfaces, not blue.

C = {
    # Surfaces
    "bg":            "#07111F",   # main app background
    "sidebar":       "#0A1628",   # sidebar background
    "surface":       "#0E1C31",   # primary surface (cards)
    "elevated":      "#12233D",   # elevated surface (nested cards, hover targets)
    "hover":         "#162A47",   # hover surface

    # Borders
    "border":        "rgba(148, 163, 184, 0.12)",
    "border_strong": "rgba(148, 163, 184, 0.20)",

    # Blue — product color, used sparingly
    "blue":          "#3B82F6",   # primary
    "blue_accent":   "#5B8CFF",   # gradient lift / hover
    "blue_light":    "#60A5FA",   # active text / small accents

    # Text
    "text_primary":   "#F8FAFC",
    "text_secondary": "#94A3B8",
    "text_muted":     "#64748B",

    # Status — reserved semantic colors, never reused as a 4th/5th
    # categorical series
    "good":    "#34D399",
    "warning": "#FBBF24",
    "danger":  "#F87171",
}


# ============================================================
# STYLESHEET
# ============================================================

def load_css() -> None:
    """Inject the global stylesheet. Call once, near the top of main()."""
    st.markdown(
        f"""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;650;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
        :root {{
            --bg: {C['bg']};
            --sidebar: {C['sidebar']};
            --surface: {C['surface']};
            --elevated: {C['elevated']};
            --hover: {C['hover']};
            --border: {C['border']};
            --border-strong: {C['border_strong']};
            --blue: {C['blue']};
            --blue-accent: {C['blue_accent']};
            --blue-light: {C['blue_light']};
            --text-primary: {C['text_primary']};
            --text-secondary: {C['text_secondary']};
            --text-muted: {C['text_muted']};
            --good: {C['good']};
            --warning: {C['warning']};
            --danger: {C['danger']};
        }}
        html, body, [class*="css"] {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        code, pre, .stCode, [data-testid="stCodeBlock"] {{
            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace !important;
        }}
        /* ── Layout & spacing ─────────────────────────────────── */
        [data-testid="stAppViewContainer"], [data-testid="stApp"] {{
            background: var(--bg);
        }}
        [data-testid="stMainBlockContainer"] {{
            padding-top: 2rem;
            padding-left: 2.5rem;
            padding-right: 2.5rem;
            max-width: 1440px;
        }}
        [data-testid="stVerticalBlock"] {{
            gap: 0.6rem;
        }}
        /* Bordered containers (st.container(border=True)) act as our
           card primitive: navy surface, soft border, generous padding. */
        div.stVerticalBlock[data-testid="stVerticalBlock"] {{
            border-color: var(--border) !important;
        }}
        div[style*="border"][data-testid="stVerticalBlock"],
        .stVerticalBlock:has(> [data-testid="stElementContainer"]) {{
            border-radius: 14px;
        }}
        [data-testid="stVerticalBlockBorderWrapper"],
        div.stVerticalBlock[style*="1px solid"] {{
            background: var(--surface);
            border: 1px solid var(--border) !important;
            border-radius: 14px !important;
            padding: 22px 22px !important;
        }}
        hr {{
            border-color: var(--border) !important;
            margin: 20px 0 !important;
        }}
        ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: var(--elevated); border-radius: 6px; }}
        @media (prefers-reduced-motion: reduce) {{
            * {{ animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }}
        }}
        /* ── Sidebar ──────────────────────────────────────────── */
        [data-testid="stSidebar"] {{
            background: var(--sidebar);
            border-right: 1px solid var(--border);
        }}
        [data-testid="stSidebarContent"] {{ padding-top: 0.5rem; }}
        .sb-brand {{
            display: flex; align-items: center; gap: 11px;
            padding: 14px 8px 18px 8px;
            margin-bottom: 4px;
            border-bottom: 1px solid var(--border);
        }}
        .sb-icon {{
            width: 32px; height: 32px; border-radius: 9px; flex: none;
            background: linear-gradient(160deg, var(--blue-accent), var(--blue));
            color: #ffffff; font-size: 12.5px; font-weight: 700; letter-spacing: 0.2px;
            display: flex; align-items: center; justify-content: center;
        }}
        .sb-name {{
            font-size: 15px; font-weight: 650; color: var(--text-primary);
            letter-spacing: -0.1px; line-height: 1.2;
        }}
        .sb-section {{
            font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
            text-transform: uppercase; color: var(--text-muted);
            padding: 4px 10px 8px 10px;
        }}
        .sb-footer {{
            display: flex; align-items: center; gap: 9px;
            padding: 12px 10px; margin-top: 10px;
            border-top: 1px solid var(--border);
        }}
        .sb-dot {{
            width: 7px; height: 7px; border-radius: 50%; background: var(--good);
            box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.15); flex: none;
        }}
        .sb-status {{ font-size: 12.5px; font-weight: 500; color: var(--text-secondary); }}
        .sb-env {{ font-size: 11px; color: var(--text-muted); }}
        /* Sidebar nav — tertiary buttons reskinned as a nav list.
           Active state is applied by a small scoped rule injected per
           render (see render_sidebar()), targeting that item's
           .st-key-navbtn_<key> class — never a saturated block fill,
           just a soft tint + left accent, per spec. */
        [data-testid="stSidebar"] button[kind="tertiary"] {{
            width: 100%; justify-content: flex-start; gap: 10px;
            padding: 9px 10px !important; border-radius: 9px !important;
            color: var(--text-secondary) !important;
            font-weight: 500; font-size: 13.5px;
            border-left: 2px solid transparent;
            transition: background 120ms ease, color 120ms ease;
        }}
        [data-testid="stSidebar"] button[kind="tertiary"]:hover {{
            background: var(--hover) !important;
            color: var(--text-primary) !important;
        }}
        [data-testid="stSidebar"] [data-testid="stIconMaterial"] {{
            font-size: 18px !important;
        }}
        /* ── Typography ───────────────────────────────────────── */
        .page-title {{ font-size: 30px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.3px; }}
        .section-title {{ font-size: 17px; font-weight: 600; color: var(--text-primary); }}
        .card-title {{ font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }}
        .body-text {{ font-size: 14.5px; font-weight: 400; color: var(--text-secondary); line-height: 1.55; }}
        .meta-text {{ font-size: 11.5px; font-weight: 400; color: var(--text-muted); }}
        .eyebrow {{ font-size: 12px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); }}
        [data-testid="stMarkdownContainer"] strong {{ color: var(--text-primary); }}
        /* ── Top bar / breadcrumb ─────────────────────────────── */
        .top-bar {{
            display: flex; align-items: center; justify-content: space-between;
            padding-bottom: 14px; margin-bottom: 18px;
            border-bottom: 1px solid var(--border);
        }}
        .breadcrumb {{ font-size: 13px; color: var(--text-muted); }}
        .bc-current {{ color: var(--text-secondary); font-weight: 500; }}
        .session-badge {{
            display: inline-flex; align-items: center; gap: 6px;
            font-size: 12px; color: var(--text-muted);
        }}
        .s-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--good); }}
        .agent-header {{
            display: flex; align-items: flex-start; justify-content: space-between;
            gap: 16px; margin-bottom: 26px;
        }}
        .agent-title {{ font-size: 22px; font-weight: 650; color: var(--text-primary); letter-spacing: -0.2px; }}
        .agent-desc {{ font-size: 14px; color: var(--text-secondary); margin-top: 4px; max-width: 640px; }}
        /* ── Badges ───────────────────────────────────────────── */
        .badge {{
            display: inline-flex; align-items: center; gap: 6px;
            font-size: 12px; font-weight: 600; padding: 5px 12px;
            border-radius: 999px; white-space: nowrap; line-height: 1.3;
        }}
        .badge::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; }}
        .badge-ready {{ background: rgba(59, 130, 246, 0.12); color: var(--blue-light); border: 1px solid rgba(59, 130, 246, 0.25); }}
        .badge-ready::before {{ background: var(--blue-light); }}
        .badge-processing {{ background: rgba(251, 191, 36, 0.12); color: var(--warning); border: 1px solid rgba(251, 191, 36, 0.25); }}
        .badge-processing::before {{ background: var(--warning); }}
        .badge-success {{ background: rgba(52, 211, 153, 0.12); color: var(--good); border: 1px solid rgba(52, 211, 153, 0.25); }}
        .badge-success::before {{ background: var(--good); }}
        .badge-error {{ background: rgba(248, 113, 113, 0.12); color: var(--danger); border: 1px solid rgba(248, 113, 113, 0.25); }}
        .badge-error::before {{ background: var(--danger); }}
        /* ── Buttons ──────────────────────────────────────────── */
        .stButton button, .stDownloadButton button {{
            font-weight: 600 !important;
            transition: filter 120ms ease, transform 120ms ease, background 120ms ease;
        }}
        button[kind="primary"] {{
            background: linear-gradient(180deg, var(--blue-accent), var(--blue)) !important;
            border: none !important;
            padding-top: 0.62rem !important; padding-bottom: 0.62rem !important;
        }}
        button[kind="primary"]:hover {{ filter: brightness(1.08); transform: translateY(-1px); }}
        button[kind="primary"]:active {{ filter: brightness(0.92); transform: translateY(0); }}
        button[kind="primary"]:disabled {{ filter: grayscale(0.3) brightness(0.75); transform: none; box-shadow: none; }}
        button[kind="secondary"] {{
            background: var(--elevated) !important;
            border: 1px solid var(--border-strong) !important;
            color: var(--text-primary) !important;
        }}
        button[kind="secondary"]:hover {{ background: var(--hover) !important; border-color: var(--border-strong) !important; }}
        button[kind="tertiary"] {{ color: var(--blue-light) !important; font-weight: 600 !important; }}
        button[kind="tertiary"]:hover {{ background: var(--hover) !important; }}
        button:focus-visible {{ outline: 2px solid var(--blue-light) !important; outline-offset: 2px; }}
        /* ── Tabs ─────────────────────────────────────────────── */
        [data-testid="stTabs"] [data-testid="stTab"] {{
            font-size: 13.5px; font-weight: 500; color: var(--text-muted);
            padding: 8px 4px;
        }}
        [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] {{
            color: var(--text-primary); font-weight: 600;
        }}
        /* ── Inputs ───────────────────────────────────────────── */
        [data-testid="stTextArea"] textarea, [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input {{
            background: var(--elevated) !important;
            border: 1px solid var(--border-strong) !important;
            color: var(--text-primary) !important;
        }}
        [data-testid="stTextArea"] textarea::placeholder,
        [data-testid="stTextInput"] input::placeholder {{
            color: var(--text-muted) !important;
        }}
        [data-baseweb], .react-aria-ComboBox [role="group"] {{
            background: var(--elevated);
        }}
        /* ── File uploader ────────────────────────────────────── */
        [data-testid="stFileUploaderDropzone"] {{
            background: var(--surface) !important;
            border: 1.5px dashed var(--border-strong) !important;
            border-radius: 12px !important;
            transition: border-color 150ms ease, background 150ms ease;
        }}
        [data-testid="stFileUploaderDropzone"]:hover {{
            border-color: var(--blue) !important;
            background: var(--elevated) !important;
        }}
        [data-testid="stFileUploaderDropzoneInstructions"] {{ color: var(--text-muted); }}
        .stFileChip, [data-testid="stFileChip"] {{
            background: var(--elevated) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            position: relative;
        }}
        [data-testid="stFileChip"]::after {{
            content: "check_circle";
            font-family: "Material Symbols Rounded";
            font-size: 17px; color: var(--good);
            position: absolute; right: 40px; top: 50%; transform: translateY(-50%);
        }}
        [data-testid="stFileChipName"] {{ color: var(--text-primary) !important; font-weight: 500; }}
        /* ── Metrics ──────────────────────────────────────────── */
        [data-testid="stMetric"] {{
            background: var(--elevated); border: 1px solid var(--border);
            border-radius: 12px; padding: 14px 16px;
        }}
        [data-testid="stMetricLabel"] {{ color: var(--text-muted) !important; font-size: 12px !important; }}
        [data-testid="stMetricLabel"] p {{
            font-size: 12px !important; font-weight: 500 !important;
            text-transform: uppercase; letter-spacing: 0.04em;
        }}
        [data-testid="stMetricValue"] {{ color: var(--text-primary) !important; }}
        /* ── Chips (column requirements) ─────────────────────── */
        .col-chip {{
            display: inline-flex; align-items: center; gap: 5px;
            font-size: 12.5px; font-weight: 500; font-family: 'JetBrains Mono', monospace;
            padding: 4px 10px; border-radius: 7px; margin: 3px 6px 3px 0;
        }}
        .col-chip-required {{ background: rgba(59, 130, 246, 0.10); border: 1px solid rgba(59, 130, 246, 0.30); color: var(--blue-light); }}
        .col-chip-optional {{ background: var(--elevated); border: 1px solid var(--border); color: var(--text-secondary); }}
        /* ── Category rows ────────────────────────────────────── */
        .cat-row {{
            display: flex; align-items: center; gap: 10px;
            padding: 10px 12px; margin-bottom: 6px;
            background: var(--elevated); border: 1px solid var(--border);
            border-radius: 9px; font-size: 13.5px; color: var(--text-primary);
        }}
        .cat-row .mat-ico {{
            font-family: 'Material Symbols Rounded', 'Material Symbols Outlined';
            font-size: 17px; color: var(--text-muted); flex: none;
        }}
        /* ── Tip card ─────────────────────────────────────────── */
        .tip-card {{
            display: flex; gap: 10px; padding: 13px 14px;
            background: rgba(59, 130, 246, 0.06); border: 1px solid rgba(59, 130, 246, 0.18);
            border-radius: 11px; margin-top: 4px;
        }}
        .tip-card .mat-ico {{
            font-family: 'Material Symbols Rounded', 'Material Symbols Outlined';
            font-size: 18px; color: var(--blue-light); flex: none;
        }}
        .tip-title {{ font-size: 12.5px; font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }}
        .tip-body {{ font-size: 12.5px; color: var(--text-secondary); line-height: 1.5; }}
        /* ── Empty / error states ─────────────────────────────── */
        .empty-state {{
            text-align: center; padding: 56px 24px;
            border: 1px dashed var(--border-strong); border-radius: 14px;
            background: var(--surface);
        }}
        .empty-icon {{ font-size: 30px; color: var(--text-muted); margin-bottom: 10px; }}
        .empty-title {{ font-size: 15px; font-weight: 600; color: var(--text-primary); }}
        .empty-hint {{ font-size: 13px; color: var(--text-muted); margin-top: 4px; }}
        .error-box {{
            padding: 16px 18px; border-radius: 12px;
            background: rgba(248, 113, 113, 0.08); border: 1px solid rgba(248, 113, 113, 0.25);
        }}
        .error-title {{ font-size: 14px; font-weight: 650; color: var(--danger); }}
        .error-body {{ font-size: 13.5px; color: var(--text-secondary); margin-top: 4px; }}
        /* ── Misc ─────────────────────────────────────────────── */
        [data-testid="stExpander"] {{
            background: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
        }}
        [data-testid="stDataFrame"] {{
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_active_nav_style(active_key: str) -> None:
    """
    Scoped follow-up rule that tints only the active sidebar nav item —
    a soft blue background + left accent + brighter text, never a
    saturated block fill. Uses the stable `.st-key-navbtn_<key>` class
    Streamlit assigns from the button's `key=`.
    """
    st.markdown(
        f"""
        <style>
        [data-testid="stSidebar"] .st-key-navbtn_{active_key} button[kind="tertiary"] {{
            background: rgba(59, 130, 246, 0.12) !important;
            color: {C['blue_light']} !important;
            border-left: 2px solid {C['blue']};
            font-weight: 600;
        }}
        [data-testid="stSidebar"] .st-key-navbtn_{active_key} [data-testid="stIconMaterial"] {{
            color: {C['blue_light']} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
