"""
Supply Chain Agent — Streamlit application.
Entry point: streamlit_app.py  →  main()
"""
from __future__ import annotations

import io
import re
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.ui.theme import (
    PRODUCT_NAME,
    NAV_KEYS,
    NAV_LABELS,
    NAV_ICONS,
    SUPERVISOR_AGENT_MAP,
    SUPERVISOR_AGENT_ICONS,
    C,
    load_css,
    inject_active_nav_style,
)
from src.utils.clusters import CLUSTERS

# ── Page config — must be FIRST Streamlit call ───────────────────────────────
st.set_page_config(
    page_title=PRODUCT_NAME,
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# DATA HELPERS
# ============================================================

def _read_excel(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        raise ValueError("No file provided.")
    uploaded_file.seek(0)
    return pd.read_excel(uploaded_file)


def _exception_payload(exc: Exception) -> Dict[str, Any]:
    return {
        "success":   False,
        "error":     str(exc),
        "traceback": traceback.format_exc(),
    }


def df_to_excel_bytes(sheets: Dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, index=False, sheet_name=name[:31])
    return buf.getvalue()


# ============================================================
# COLUMN-MATCHING HELPERS
# ============================================================

def _norm(s: str) -> str:
    if s is None:
        return ""
    t = re.sub(r"\s+", " ", str(s).strip().lower().replace("_", " ")).strip()
    return "".join(ch for ch in t if ch.isalnum())


def _find_col(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    norm_map = {col: _norm(col) for col in df.columns}
    targets  = {_norm(c) for c in candidates if c is not None}
    for col, normed in norm_map.items():
        if normed and normed in targets:
            return col
    return None


def _find_col_ci(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    col_map = {c.strip().lower(): c for c in df.columns}
    for c in candidates:
        if c.strip().lower() in col_map:
            return col_map[c.strip().lower()]
    return None


# ============================================================
# INVENTORY CALCULATION  (pure Python, no agent dependency)
# ============================================================

def _calculate_inventory(
    df_in: pd.DataFrame,
    target_coverage: float = 6.0,
    use_soh_for_oos: bool  = False,
):
    """Returns (result_df, messages)."""
    messages: list[str] = []

    col_soh     = _find_col(df_in, "SOH", "stock on hand", "stock_on_hand",
                             "total stock", "nupco_total_stock")
    col_mc      = _find_col(df_in, "consumption", "monthly consumption",
                             "monthly_consumption", "nupco_monthly_consumption",
                             "nupco_monthly consumption")
    col_price   = _find_col(df_in, "unit_price", "unit price", "unit sar", "price")
    col_expired = _find_col(df_in, "expired_qty", "expired quantity", "expired",
                             "nupco_expired", "expiry qty", "expiry quantity")
    col_req     = _find_col(df_in, "request_qty", "request quantity", "requested_qty",
                             "requested quantity", "qty_request", "qty requested", "requestqty")
    col_open    = _find_col(df_in, "open_qty", "open qty", "openqty",
                             "po open qty", "on order", "open quantity")
    col_cont    = _find_col(df_in, "contract_qty", "contract qty",
                             "contract quantity", "contractqty", "contract_quantity")
    col_recv    = _find_col(df_in, "received_qty", "received qty", "receivedqty",
                             "supplied_qty", "supplied qty", "suppliedqty",
                             "delivered_qty", "delivered qty", "deliveredqty")

    missing = [n for n, c in [("SOH", col_soh), ("consumption", col_mc),
                                ("unit_price", col_price)] if c is None]
    if missing:
        messages.append("Missing required columns: " + ", ".join(missing)
                        + ". Required minimum: SOH, consumption, unit_price.")
        return df_in.copy(), messages

    try:
        target_coverage = max(float(target_coverage), 0.0)
    except Exception:
        target_coverage = 6.0

    idx = df_in.index

    def to_f(x):
        try:
            v = float(x)
            return 0.0 if pd.isna(v) else v
        except Exception:
            return 0.0

    soh   = df_in[col_soh].apply(to_f)
    mc    = df_in[col_mc].apply(to_f)
    price = df_in[col_price].apply(to_f)

    exp_units = (df_in[col_expired].apply(to_f)
                 if col_expired else pd.Series(0.0, index=idx))
    req_qty   = (df_in[col_req].apply(to_f)
                 if col_req else pd.Series(0.0, index=idx))

    if col_open:
        open_qty = df_in[col_open].apply(to_f)
    elif col_cont and col_recv:
        open_qty = (df_in[col_cont].apply(to_f)
                    - df_in[col_recv].apply(to_f)).clip(lower=0.0)
    else:
        open_qty = pd.Series(0.0, index=idx)

    total   = soh + open_qty
    cov     = pd.Series(0.0, index=idx).mask(mc > 0, total / mc).fillna(0.0)

    def status(c):
        if c == 0:              return "OOS"
        if c < target_coverage: return "Risk of OOS"
        if c <= target_coverage * 1.2: return "Optimum"
        return "Excess"

    inv_status = cov.apply(status)

    if use_soh_for_oos:
        mask       = (soh == 0) & (mc > 0)
        inv_status = inv_status.where(~mask, "OOS")
        flag_oos   = pd.Series("SOH", index=idx).where(~mask, "OOS")
    else:
        flag_oos = pd.Series("", index=idx)

    need        = inv_status.isin(["OOS", "Risk of OOS"]) & (mc > 0)
    to_order    = (pd.Series(0.0, index=idx)
                   .mask(need, target_coverage * mc - total)
                   .fillna(0.0).clip(lower=0).round(0))
    to_order_s  = (to_order * price).round(2)
    req_sar     = (req_qty  * price).round(2)
    exp_sar     = (exp_units* price).round(2)

    def final(r, t):
        if r <= 0 and t <= 0: return 0.0
        if r <= 0:             return t
        if t <= 0:             return 0.0
        return min(r, t)

    fin_qty = pd.Series(
        [final(r, t) for r, t in zip(req_qty, to_order)], index=idx
    ).round(0)
    fin_sar  = (fin_qty * price).round(2)
    sav_sar  = (req_sar - fin_sar).clip(lower=0).round(2)

    def alert(c):
        if c < target_coverage:      return "ORDER MORE"
        if c <= target_coverage*1.2: return "MAINTAIN / REVIEW"
        return "HOLD OFF ORDERING"

    out = df_in.copy()
    out["Open qty (used in calc)"] = open_qty
    out["Actual coverage"]         = cov.round(2)
    out["Target coverage"]         = target_coverage
    out["Inventory status"]        = inv_status
    out["Flag OOS (SOH)"]          = flag_oos
    out["To order qty"]            = to_order
    out["To order SAR"]            = to_order_s
    out["Request SAR"]             = req_sar
    out["Final decision qty"]      = fin_qty
    out["Final decision SAR"]      = fin_sar
    out["Saving SAR"]              = sav_sar
    out["Expired SAR"]             = exp_sar
    out["Inventory status alert"]  = cov.apply(alert)

    return out, messages


# ============================================================
# AGENT RUNNERS
# ============================================================

def run_inventory_agent(
    uploaded_file,
    target_coverage: float = 6.0,
    use_soh_for_oos: bool  = False,
) -> Dict[str, Any]:
    try:
        df          = _read_excel(uploaded_file)
        df.columns  = [str(c).strip() for c in df.columns]

        try:
            from src.agents.inventory_agent import process_inventory  # type: ignore
        except ImportError:
            process_inventory = None

        if process_inventory is not None:
            # Real module found — let a genuine business-logic error
            # (bad columns, bad data, ...) surface as a real error
            # instead of being silently masked by the fallback below.
            out    = process_inventory(df, target_coverage, use_soh_for_oos)
            df_out = out["data"]
            return {"success": True, "dataframe": df, "result": df_out,
                    "summary": out.get("summary", {}), "messages": [],
                    "agent": "inventory_agent"}

        df_out, msgs = _calculate_inventory(df, target_coverage, use_soh_for_oos)
        return {"success": True, "dataframe": df, "result": df_out,
                "messages": msgs, "agent": "inventory_agent"}
    except Exception as exc:
        return _exception_payload(exc)


def run_category_agent(
    question: str = "",
    uploaded_file=None,
) -> Dict[str, Any]:
    try:
        if uploaded_file is not None:
            df = _read_excel(uploaded_file)

            try:
                from src.agents.category_agent import run_category_agent as _real  # type: ignore
            except ImportError:
                _real = None

            if _real is not None:
                # Real module found — let a genuine classification error
                # surface instead of being silently swallowed and
                # replaced by a confusing "enter a question" message.
                result = _real(df)
                return {"success": True, "result": result, "agent": "category_agent"}

            return {
                "success": True,
                "result":  None,
                "agent":   "category_agent",
                "warning": ("src/agents/category_agent.py not found — no classification "
                            "was run. Add the file under src/agents/ and re-run the analysis."),
            }

        if not (question or "").strip():
            raise ValueError("Please enter a question or upload a file.")

        return {
            "success": True,
            "result":  f"Category agent received: {question}",
            "agent":   "category_agent",
            "warning": "Text-mode classification not yet connected. Upload a product file for full analysis.",
        }
    except Exception as exc:
        return _exception_payload(exc)


def run_rag_agent(question: str) -> Dict[str, Any]:
    try:
        if not (question or "").strip():
            raise ValueError("Please enter a question.")
        try:
            from src.agents.RAG_agent import ask_rag  # type: ignore
            return {"success": True, "result": ask_rag(question), "agent": "RAG_agent"}
        except Exception:
            pass
        try:
            from src.agents.RAG_agent import RAGAgent  # type: ignore
            agent = RAGAgent()
            for m in ("run", "ask", "query"):
                if hasattr(agent, m):
                    return {"success": True, "result": getattr(agent, m)(question),
                            "agent": "RAG_agent"}
        except Exception:
            pass
        return {
            "success": True,
            "result":  f"Knowledge assistant received: {question}",
            "agent":   "RAG_agent",
            "warning": "Knowledge base not yet connected. Showing placeholder response.",
        }
    except Exception as exc:
        return _exception_payload(exc)


def run_reallocation_agent(uploaded_file) -> Dict[str, Any]:
    try:
        df = _read_excel(uploaded_file)

        try:
            from src.agents.reallocation_agent import process_reallocation  # type: ignore
        except ImportError:
            process_reallocation = None

        if process_reallocation is not None:
            # Real module found — let a genuine business-logic error
            # (unrecognized clusters, bad columns, ...) surface instead
            # of being silently masked by the preview fallback below.
            result = process_reallocation(df)
            return {"success": True, "dataframe": df, "result": result,
                    "agent": "reallocation_agent"}

        try:
            from src.agents.reallocation_agent import ReallocationAgent  # type: ignore
        except ImportError:
            ReallocationAgent = None

        if ReallocationAgent is not None:
            agent = ReallocationAgent()
            for m in ("run", "optimize", "process"):
                if hasattr(agent, m):
                    return {"success": True, "dataframe": df,
                            "result": getattr(agent, m)(df), "agent": "reallocation_agent"}

        return {
            "success":  True,
            "dataframe": df,
            "result":   {"rows": len(df), "columns": list(df.columns),
                         "preview": df.head(10)},
            "agent":    "reallocation_agent",
            "warning":  "Reallocation logic not yet implemented. Showing file preview.",
        }
    except Exception as exc:
        return _exception_payload(exc)


def run_supervisor(
    mode: str,
    uploaded_file=None,
    question: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        mode = (mode or "").strip().lower()
        if mode == "inventory":   return run_inventory_agent(uploaded_file)
        if mode == "category":    return run_category_agent(question or "")
        if mode == "rag":         return run_rag_agent(question or "")
        if mode == "reallocation":return run_reallocation_agent(uploaded_file)
        raise ValueError(f"Unknown agent mode: {mode}")
    except Exception as exc:
        return _exception_payload(exc)


# ============================================================
# INVENTORY DASHBOARD
# ============================================================

# Status palette (fixed, semantic — never reused for anything else).
# good / warning / serious / critical, per the validated dark-surface
# reference palette (distinct from the categorical hues below so a
# status color never impersonates a series).
_STATUS_COLORS = {
    "Optimum":     "#0ca30c",   # good
    "Risk of OOS": "#fab219",   # warning
    "Excess":      "#ec835a",   # serious
    "OOS":         "#d03b3b",   # critical
}
_STATUS_ORDER = ["OOS", "Risk of OOS", "Optimum", "Excess"]

# Categorical theme (dark-mode steps), fixed order — used only for the
# handful of product categories (Clinical / LAB / Pharma / ...), never
# for Region (too many values for a categorical hue to stay legible).
_CATEGORY_PALETTE = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"]

# Sequential single hue for plain magnitude bars (order value, etc.)
_SEQUENTIAL_BLUE = "#3987e5"

_CHART_GRIDCOLOR = "#2c2c2a"   # dark hairline gridline
_CHART_AXISCOLOR = "#383835"   # dark baseline/axis


def _category_color_map(categories) -> Dict[str, str]:
    cats = sorted(str(c) for c in categories)
    return {c: _CATEGORY_PALETTE[i % len(_CATEGORY_PALETTE)] for i, c in enumerate(cats)}


def _dark_fig(fig, show_legend: bool = True):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=C["text_secondary"],
        legend_title_text="",
        showlegend=show_legend,
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h",
                    y=1.08, x=0, font=dict(color=C["text_secondary"])),
        margin=dict(l=10, r=10, t=40, b=10),
        hoverlabel=dict(bgcolor=C["elevated"], font_color=C["text_primary"],
                        bordercolor=C["border"]),
    )
    fig.update_xaxes(showgrid=False, color=C["text_muted"], linecolor=_CHART_AXISCOLOR)
    fig.update_yaxes(showgrid=True, gridcolor=_CHART_GRIDCOLOR, gridwidth=1,
                     zeroline=False, color=C["text_muted"], linecolor=_CHART_AXISCOLOR)
    return fig


def _stacked_bar(totals: pd.DataFrame, order: list, colors: dict, orientation: str = "v"):
    """
    Guaranteed-correct stacked bar: each series gets an explicit `base`
    (cumulative sum of the series below it) instead of relying on
    `barmode="stack"` alone, so segments always stack rather than
    rendering side by side.
    """
    fig = go.Figure()
    bottom = pd.Series(0.0, index=totals.index)
    for key in order:
        vals = totals[key] if key in totals.columns else pd.Series(0.0, index=totals.index)
        if orientation == "v":
            fig.add_bar(x=totals.index, y=vals, base=bottom, name=key,
                       marker_color=colors.get(key, C["blue"]), marker_line_width=0)
        else:
            fig.add_bar(y=totals.index, x=vals, base=bottom, name=key, orientation="h",
                       marker_color=colors.get(key, C["blue"]), marker_line_width=0)
        bottom = bottom + vals
    fig.update_layout(barmode="overlay", bargap=0.3)
    return fig


def _inventory_dashboard(df: pd.DataFrame) -> None:
    COL_S = "Inventory status"
    COL_O = "To order SAR"
    COL_E = "Expired SAR"

    if COL_S not in df.columns:
        st.warning("Dashboard requires the 'Inventory status' column.")
        return

    tc  = st.session_state.get("target_coverage", "N/A")
    soh = st.session_state.get("use_soh_for_oos", False)
    st.caption(f"Target coverage: **{tc} months**  |  "
               f"{'OOS mode: SOH only' if soh else 'OOS mode: SOH + Open Qty'}")

    COL_REGION = _find_col_ci(df, "region")
    COL_CAT    = _find_col_ci(df, "category", "Category")

    if COL_REGION:
        regions  = sorted(df[COL_REGION].dropna().unique())
        selected = st.multiselect("Filter by Region", options=regions,
                                  default=regions, key="dash_region")
        df = df[df[COL_REGION].isin(selected)]

    if df.empty:
        st.warning("No data after filtering.")
        return

    st.markdown("---")
    pct = (df[COL_S].value_counts(normalize=True)
           .reindex(_STATUS_ORDER).fillna(0) * 100)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("OOS",         f"{pct['OOS']:.1f}%")
    with c2: st.metric("Risk of OOS", f"{pct['Risk of OOS']:.1f}%")
    with c3: st.metric("Optimum",     f"{pct['Optimum']:.1f}%")
    with c4: st.metric("Excess",      f"{pct['Excess']:.1f}%")

    st.markdown("---")

    if COL_REGION:
        p = (pd.crosstab(df[COL_REGION], df[COL_S])
             .reindex(columns=_STATUS_ORDER, fill_value=0))
        p = p.div(p.sum(axis=1), axis=0) * 100
        # Sort by "most at-risk first" (OOS + Risk of OOS share) rather
        # than alphabetically — the ordering itself carries information.
        p = p.loc[(p["OOS"] + p["Risk of OOS"]).sort_values(ascending=False).index]
        fig = _dark_fig(_stacked_bar(p, _STATUS_ORDER, _STATUS_COLORS))
        fig.update_layout(title="Inventory Status by Region (%)")
        fig.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True, theme=None)

    if COL_CAT:
        p2 = (pd.crosstab(df[COL_CAT], df[COL_S])
              .reindex(columns=_STATUS_ORDER, fill_value=0))
        p2 = p2.div(p2.sum(axis=1), axis=0) * 100
        p2 = p2.loc[(p2["OOS"] + p2["Risk of OOS"]).sort_values(ascending=False).index]
        fig2 = _dark_fig(_stacked_bar(p2, _STATUS_ORDER, _STATUS_COLORS))
        fig2.update_layout(title="Inventory Status by Category (%)")
        fig2.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig2, use_container_width=True, theme=None)

    if COL_O in df.columns and COL_REGION:
        ov = (df.groupby(COL_REGION, as_index=False)[COL_O].sum()
              .sort_values(COL_O, ascending=True))
        fig3 = go.Figure(go.Bar(
            y=ov[COL_REGION], x=ov[COL_O], orientation="h",
            marker_color=_SEQUENTIAL_BLUE, marker_line_width=0,
        ))
        fig3 = _dark_fig(fig3, show_legend=False)
        fig3.update_layout(title="Order Value by Region (SAR)", bargap=0.25,
                           height=max(320, 22 * len(ov)))
        fig3.update_xaxes(tickformat=",.0f")
        st.plotly_chart(fig3, use_container_width=True, theme=None)

    if COL_CAT and COL_O in df.columns:
        ov2 = (df.groupby(COL_CAT, as_index=False)[COL_O].sum()
               .sort_values(COL_O, ascending=False))
        fig4 = go.Figure(go.Bar(
            x=ov2[COL_CAT], y=ov2[COL_O],
            marker_color=_SEQUENTIAL_BLUE, marker_line_width=0,
        ))
        fig4 = _dark_fig(fig4, show_legend=False)
        fig4.update_layout(title="Order Value by Category (SAR)", bargap=0.35)
        fig4.update_yaxes(tickformat=",.0f")
        st.plotly_chart(fig4, use_container_width=True, theme=None)

    if COL_E in df.columns and COL_REGION and COL_CAT:
        df_e = df[df[COL_E] > 0]
        if len(df_e) > 0:
            cat_map = _category_color_map(df_e[COL_CAT].dropna().unique())
            piv = (df_e.groupby([COL_REGION, COL_CAT])[COL_E].sum()
                   .unstack(fill_value=0.0))
            piv = piv.loc[piv.sum(axis=1).sort_values(ascending=True).index]
            fig5 = _stacked_bar(piv, list(piv.columns), cat_map, orientation="h")
            fig5 = _dark_fig(fig5)
            fig5.update_layout(title="Expired Value by Region & Category (SAR)",
                               height=max(320, 22 * len(piv)))
            fig5.update_xaxes(tickformat=",.0f")
            st.plotly_chart(fig5, use_container_width=True, theme=None)
        else:
            st.info("No expired items in current selection.")

    st.markdown("---")
    st.subheader("Detailed Table")
    st.dataframe(df, use_container_width=True)


def _render_inventory_results(df_out: pd.DataFrame, messages: Optional[list] = None) -> None:
    """
    Full Inventory Analysis result view — KPI cards + Results/Dashboard
    tabs. Shared by the dedicated Inventory Analysis page AND the
    Supervisor page, so running this agent from either place shows the
    same dashboard instead of Supervisor's generic table-only fallback.
    """
    for msg in messages or []:
        st.warning(msg)

    st.markdown("---")
    if "Inventory status" in df_out.columns:
        total = len(df_out)
        oos   = int((df_out["Inventory status"] == "OOS").sum())
        risk  = int((df_out["Inventory status"] == "Risk of OOS").sum())
        opt_  = int((df_out["Inventory status"] == "Optimum").sum())
        exc   = int((df_out["Inventory status"] == "Excess").sum())
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: st.metric("Total items", f"{total:,}")
        with c2: st.metric("OOS",         f"{oos:,}")
        with c3: st.metric("Risk of OOS", f"{risk:,}")
        with c4: st.metric("Optimum",     f"{opt_:,}")
        with c5: st.metric("Excess",      f"{exc:,}")

    if "To order SAR" in df_out.columns:
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("To order (SAR)",         f"{df_out['To order SAR'].sum():,.0f}")
        if "Final decision SAR" in df_out.columns:
            with c2: st.metric("Final decision (SAR)",  f"{df_out['Final decision SAR'].sum():,.0f}")
        if "Saving SAR" in df_out.columns:
            with c3: st.metric("Savings (SAR)",         f"{df_out['Saving SAR'].sum():,.0f}")

    st.markdown("---")
    tab1, tab2 = st.tabs(["Results", "Dashboard"])

    with tab1:
        col_dl, _ = st.columns([1, 3])
        with col_dl:
            st.download_button(
                "Download results",
                data=df_to_excel_bytes({"OUTPUT": df_out}),
                file_name=f"inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                icon=":material/download:",
                key=f"inv_dl_{id(df_out)}",
            )
        st.dataframe(df_out, use_container_width=True)

    with tab2:
        _inventory_dashboard(df_out)


# ============================================================
# SHARED UI COMPONENTS
# ============================================================

def _top_bar(page_label: str) -> None:
    st.markdown(
        f"""
        <div class="top-bar">
            <div class="breadcrumb">
                <span class="bc-root">Agents</span>
                <span class="bc-sep"> &nbsp;/&nbsp; </span>
                <span class="bc-current">{page_label}</span>
            </div>
            <div class="session-badge">
                <span class="s-dot"></span>
                Secure session
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _agent_header(title: str, description: str, status: str = "ready") -> None:
    badge_map = {
        "ready":      ("Ready",       "badge-ready"),
        "processing": ("Processing",  "badge-processing"),
        "success":    ("Completed",   "badge-success"),
        "error":      ("Error",       "badge-error"),
    }
    label, cls = badge_map.get(status, badge_map["ready"])
    st.markdown(
        f"""
        <div class="agent-header">
            <div>
                <div class="agent-title">{title}</div>
                <div class="agent-desc">{description}</div>
            </div>
            <span class="badge {cls}">{label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _empty_state(title: str, hint: str) -> None:
    st.markdown(
        f"""
        <div class="empty-state">
            <div class="empty-icon">&#8999;</div>
            <div class="empty-title">{title}</div>
            <div class="empty-hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _error_state(payload: Dict[str, Any]) -> None:
    msg = payload.get("error", "An unexpected error occurred.")
    st.markdown(
        f"""
        <div class="error-box">
            <div class="error-title">Analysis failed</div>
            <div class="error-body">{msg}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    tb = payload.get("traceback", "")
    if tb:
        safe_tb = re.sub(
            r"(api[_-]?key|password|token|secret)\s*=\s*\S+",
            r"\1=***", tb, flags=re.IGNORECASE
        )
        with st.expander("Technical details"):
            st.code(safe_tb, language="python")


def _render_result(payload: Dict[str, Any]) -> None:
    """Generic result renderer used by several pages."""
    if not payload.get("success", False):
        _error_state(payload)
        return

    if payload.get("warning"):
        st.warning(payload["warning"])

    for msg in payload.get("messages", []):
        st.warning(msg)

    result = payload.get("result")

    if isinstance(result, pd.DataFrame):
        st.markdown("---")
        col_dl, _ = st.columns([1, 3])
        with col_dl:
            st.download_button(
                "Download results",
                data=df_to_excel_bytes({"OUTPUT": result}),
                file_name=f"supplychain_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                icon=":material/download:",
            )
        st.dataframe(result.head(200), use_container_width=True)
        return

    if isinstance(result, dict):
        st.markdown("---")
        preview = result.get("preview")
        rest    = {k: v for k, v in result.items() if k != "preview"}
        if isinstance(preview, pd.DataFrame):
            st.subheader("Data preview")
            st.dataframe(preview, use_container_width=True)
        if rest:
            st.subheader("Summary")
            st.json(rest)
        return

    if result is not None:
        st.markdown("---")
        st.markdown(
            f'<div style="padding:14px 16px;background:{C["elevated"]};'
            f'border:1px solid {C["border"]};border-radius:10px;'
            f'font-size:14px;color:{C["text_primary"]};">{result}</div>',
            unsafe_allow_html=True,
        )


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar() -> str:
    """Render the sidebar. Returns the currently selected page key."""

    # Brand block — icon + name only, no tagline.
    st.sidebar.markdown(
        f"""
        <div class="sb-brand">
            <div class="sb-icon">SC</div>
            <div class="sb-name">{PRODUCT_NAME}</div>
        </div>
        <div class="sb-section">Agents</div>
        """,
        unsafe_allow_html=True,
    )

    # Navigation — one tertiary button per agent (not a radio) so each
    # item can carry its own Material icon. Selection lives in
    # session_state and is applied on click with an explicit rerun;
    # the active item's subtle tint/left-accent is layered on afterwards
    # via inject_active_nav_style(), scoped to that button's key= class.
    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = NAV_KEYS[0]

    for key in NAV_KEYS:
        if st.sidebar.button(
            NAV_LABELS[key],
            icon=NAV_ICONS[key],
            use_container_width=True,
            type="tertiary",
            key=f"navbtn_{key}",
        ):
            st.session_state["nav_page"] = key
            st.rerun()

    inject_active_nav_style(st.session_state["nav_page"])

    # Footer
    st.sidebar.markdown(
        """
        <div class="sb-footer">
            <div class="sb-dot"></div>
            <div>
                <div class="sb-status">All systems operational</div>
                <div class="sb-env">Development</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return st.session_state["nav_page"]


# ============================================================
# PAGE: SUPERVISOR
# ============================================================

def page_supervisor() -> None:
    _top_bar("Supervisor")
    _agent_header(
        "Supervisor",
        "Route complex requests to the appropriate specialist agent and monitor execution.",
    )

    col_left, col_right = st.columns([3, 2], gap="medium")

    with col_left:
        with st.container(border=True):
            st.markdown("**Select Agent & Input**")

            agent_keys    = list(SUPERVISOR_AGENT_MAP.keys())
            agent_display = [SUPERVISOR_AGENT_MAP[k] for k in agent_keys]

            selected_idx = st.selectbox(
                "Agent",
                options=range(len(agent_keys)),
                format_func=lambda i: agent_display[i],
                key="sv_agent",
            )
            selected_key = agent_keys[selected_idx]
            needs_file   = selected_key in ("inventory", "reallocation")
            needs_q      = selected_key in ("category", "rag")

            question = ""
            uploaded_file = None

            if needs_q:
                question = st.text_area(
                    "Question or instruction",
                    height=110,
                    placeholder="Describe what you need the agent to analyze...",
                    key="sv_question",
                )

            if needs_file or selected_key == "category":
                uploaded_file = st.file_uploader(
                    "Attach a file (Excel)",
                    type=["xlsx", "xls"],
                    key="sv_file",
                )

            can_run = not (needs_file and uploaded_file is None
                           and not (needs_q and question.strip()))
            run_clicked = st.button(
                "Run with Supervisor",
                type="primary",
                icon=":material/auto_awesome:",
                use_container_width=True,
                disabled=not can_run,
                key="sv_run",
            )

    with col_right:
        with st.container(border=True):
            st.markdown("**Selected Agent**")
            st.markdown(
                f'<div style="font-size:14px;font-weight:500;'
                f'color:{C["text_primary"]};margin-bottom:8px;">'
                f'{SUPERVISOR_AGENT_MAP[selected_key]}</div>',
                unsafe_allow_html=True,
            )
            descs = {
                "inventory":    "Analyzes stock health, coverage, and out-of-stock risks from an inventory file.",
                "category":     "Classifies products and standardizes category structures.",
                "rag":          "Answers grounded questions from the supply-chain knowledge base.",
                "reallocation": "Identifies transfer opportunities and rebalances stock between locations.",
            }
            st.markdown(
                f'<div style="font-size:13px;color:{C["text_secondary"]};">'
                f'{descs.get(selected_key, "")}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("")
            st.markdown(
                '<span class="badge badge-ready">Ready</span>',
                unsafe_allow_html=True,
            )

    # Run
    if run_clicked:
        with st.spinner(f"Running {SUPERVISOR_AGENT_MAP[selected_key]}..."):
            payload = run_supervisor(
                mode=selected_key,
                uploaded_file=uploaded_file,
                question=question,
            )
        st.session_state["sv_payload"] = payload

    # Render (persists across reruns, e.g. touching a dashboard filter
    # widget inside the rendered result, instead of only right after
    # the click) — and routes to the same rich renderer used by the
    # dedicated Inventory / Reallocation pages instead of Supervisor's
    # generic table-only fallback.
    if "sv_payload" in st.session_state:
        payload = st.session_state["sv_payload"]
        if not payload.get("success", False):
            _error_state(payload)
        else:
            agent  = payload.get("agent")
            result = payload.get("result")
            if agent == "inventory_agent" and isinstance(result, pd.DataFrame):
                if payload.get("warning"):
                    st.warning(payload["warning"])
                _render_inventory_results(result, messages=payload.get("messages", []))
            elif (agent == "reallocation_agent" and isinstance(result, dict)
                  and "kpi_before" in result):
                if payload.get("warning"):
                    st.warning(payload["warning"])
                _render_reallocation_results(result)
            else:
                _render_result(payload)
    else:
        _empty_state(
            "No results yet",
            "Select an agent, provide the required input, and click Run with Supervisor.",
        )


# ============================================================
# PAGE: INVENTORY ANALYSIS
# ============================================================

_TEMPLATE_COLS = [
    "item_code", "item_description",
    "SOH", "consumption", "unit_price",
    "request_qty", "open_qty", "contract_qty",
    "received_qty", "expired_qty",
    "region", "category", "sub_category",
]


def page_inventory() -> None:
    _top_bar("Inventory Analysis")
    _agent_header(
        "Inventory Analysis Agent",
        "Analyze stock health, coverage and out-of-stock risks from your inventory file.",
    )

    col_upload, col_settings = st.columns([3, 2], gap="medium")

    # ── Upload panel ──────────────────────────────────────────
    with col_upload:
        with st.container(border=True):
            st.markdown("**Upload Inventory File**")
            st.caption("Excel only (.xlsx / .xls) — max 200 MB")

            uploaded_file = st.file_uploader(
                "Drop your inventory file here",
                type=["xlsx", "xls"],
                key="inventory_file",
                label_visibility="collapsed",
            )

        st.markdown("---")

        # Template download
        template_df = pd.DataFrame(columns=_TEMPLATE_COLS)
        st.download_button(
            "Download input template",
            data=df_to_excel_bytes({"TEMPLATE": template_df}),
            file_name=f"supplychain_agent_template_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
        )

        with st.expander("Input data requirements"):
            st.markdown("""
**Required fields**

| Field | Type | Description |
|---|---|---|
| `item_code` | text | Unique item identifier |
| `item_description` | text | Item name or description |
| `SOH` | number | Stock on hand (units) |
| `consumption` | number | Monthly consumption (units/month) |
| `unit_price` | number | Price per unit (SAR) |

**Optional fields**

| Field | Type | Description |
|---|---|---|
| `request_qty` | number | Quantity requested by the cluster |
| `open_qty` | number | Open PO quantity |
| `contract_qty` | number | Contracted quantity |
| `received_qty` | number | Received quantity |
| `expired_qty` | number | Expired units |
| `region` | text | Region or cluster |
| `category` | text | Item category |
| `sub_category` | text | Sub-category |
""")

    # ── Settings panel ────────────────────────────────────────
    with col_settings:
        with st.container(border=True):
            st.markdown("**Analysis Settings**")

            target_cov = st.number_input(
                "Target coverage (months)",
                min_value=0.0,
                value=float(st.session_state.get("target_coverage", 6.0)),
                step=0.5,
                help="Target months of stock to maintain.",
            )

            flag_oos = st.checkbox(
                "Flag zero stock as OOS",
                value=st.session_state.get("use_soh_for_oos", False),
                help="Items with SOH = 0 are flagged OOS regardless of open POs.",
            )

            st.markdown("---")

            run_clicked = st.button(
                "Run inventory analysis",
                type="primary",
                icon=":material/auto_awesome:",
                use_container_width=True,
                disabled=(uploaded_file is None),
                key="inv_run",
            )
            if uploaded_file is None:
                st.caption("Upload a file above to enable analysis.")

    # ── Run ───────────────────────────────────────────────────
    if run_clicked and uploaded_file is not None:
        with st.spinner("Analyzing inventory data..."):
            payload = run_inventory_agent(
                uploaded_file,
                target_coverage=target_cov,
                use_soh_for_oos=flag_oos,
            )

        if not payload.get("success"):
            _error_state(payload)
            return

        df_out = payload.get("result")
        if not isinstance(df_out, pd.DataFrame):
            st.error("The calculation did not return a valid result.")
            return

        st.session_state["df_vba"]           = df_out
        st.session_state["inv_messages"]     = payload.get("messages", [])
        st.session_state["target_coverage"]  = float(target_cov)
        st.session_state["use_soh_for_oos"]  = flag_oos

    # ── Render (persists across reruns — e.g. touching a dashboard
    #    filter widget — instead of only right after the click) ──
    if "df_vba" in st.session_state:
        _render_inventory_results(
            st.session_state["df_vba"],
            messages=st.session_state.get("inv_messages", []),
        )
    else:
        _empty_state(
            "No analysis yet",
            "Upload an inventory file and click Run inventory analysis to get started.",
        )


# ============================================================
# PAGE: CATEGORY INTELLIGENCE
# ============================================================

# Official category → Material icon shown in the sidebar-style panel.
_CATEGORY_INFO = {
    "Clinical":         "medical_services",
    "LAB":              "science",
    "Pharma":           "medication",
    "Not In Catalogue": "help",
}

_CATEGORY_EXAMPLES = [
    ("category",     "Classify uncategorized products",
     "Upload a file with blank or missing category values — the agent assigns "
     "Clinical, LAB, Pharma or Not In Catalogue from the item name and sub-category."),
    ("rule_settings", "Standardize existing categories",
     "Mis-cased or misspelled categories (e.g. \"pharma\", \"Lab\") are normalized "
     "to the four official categories automatically."),
    ("fact_check",    "Review low-confidence items",
     "Items the agent isn't fully sure about are flagged with a confidence score "
     "below 70% so your team can review them."),
]


def _column_chip(name: str, required: bool) -> str:
    cls = "col-chip-required" if required else "col-chip-optional"
    return f'<span class="col-chip {cls}">{name}</span>'


def _render_category_results(payload: Dict[str, Any]) -> None:
    """
    Category Intelligence result view — analysis summary computed from
    the real output (no invented metrics), a View results / Download
    Excel pair, and this session's real run history.
    """
    if not payload.get("success", False):
        _error_state(payload)
        return

    if payload.get("warning"):
        st.warning(payload["warning"])

    result = payload.get("result")

    if isinstance(result, pd.DataFrame) and "category" in result.columns:
        st.markdown(
            '<div style="margin:20px 0 12px 0;">'
            '<span class="badge badge-success">Analysis complete</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="section-title">Analysis summary</div>', unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        conf = result["category_confidence"] if "category_confidence" in result.columns else None
        stats = [("Products analyzed", f"{len(result):,}")]
        stats.append(("Categories identified", f"{int(result['category'].nunique())}"))
        if conf is not None:
            stats.append(("Items requiring review", f"{int((conf < 0.70).sum()):,}"))
            stats.append(("Avg. confidence", f"{conf.mean() * 100:.0f}%"))
        stats.append(("Uncategorized", f"{int((result['category'] == 'Not In Catalogue').sum()):,}"))

        cols = st.columns(len(stats))
        for col, (label, value) in zip(cols, stats):
            with col:
                st.metric(label, value)

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        b1, b2, _sp = st.columns([1.3, 1.3, 3])
        with b1:
            if st.button("View results", type="primary", icon=":material/table_view:",
                         use_container_width=True, key="cat_view_toggle"):
                st.session_state["cat_show_table"] = not st.session_state.get("cat_show_table", False)
        with b2:
            st.download_button(
                "Download Excel",
                data=df_to_excel_bytes({"CATEGORIES": result}),
                file_name=f"category_intelligence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                icon=":material/download:",
                use_container_width=True,
                key="cat_dl",
            )

        if st.session_state.get("cat_show_table", False):
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.dataframe(result, use_container_width=True)

    elif result is not None:
        st.markdown("---")
        st.markdown(
            f'<div style="padding:14px 16px;background:{C["elevated"]};'
            f'border:1px solid {C["border"]};border-radius:10px;'
            f'font-size:14px;color:{C["text_primary"]};">{result}</div>',
            unsafe_allow_html=True,
        )

    # ── Recent analyses — a real, session-scoped run log (not fake
    #    persisted history: it resets on app restart, and says so). ──
    history = st.session_state.get("cat_history", [])
    if history:
        st.markdown('<div class="section-title" style="margin-top:30px;">Recent analyses</div>',
                    unsafe_allow_html=True)
        st.caption("This browser session only — not yet persisted between app restarts.")
        hist_df = pd.DataFrame(history)[["file", "date", "status", "categories"]].rename(columns={
            "file": "File", "date": "Date", "status": "Status", "categories": "Categories identified",
        })
        st.dataframe(hist_df, use_container_width=True, hide_index=True)


def page_category() -> None:
    _top_bar("Category Intelligence")
    _agent_header(
        "Category Intelligence Agent",
        "Classify products and standardize category structures with AI assistance.",
    )

    if "cat_running" not in st.session_state:
        st.session_state["cat_running"] = False
    if "cat_history" not in st.session_state:
        st.session_state["cat_history"] = []

    col_left, col_right = st.columns([3, 2], gap="medium")

    with col_left:
        with st.container(border=True):
            tab_file, tab_ask, tab_examples = st.tabs([
                ":material/upload_file: Analyse a file",
                ":material/chat: Ask a question",
                ":material/lightbulb: Examples",
            ])

            with tab_file:
                uploaded_file = st.file_uploader(
                    "Upload a product file",
                    type=["xlsx", "xls"],
                    key="cat_file",
                    label_visibility="collapsed",
                )
                st.caption("Supported formats: XLSX, XLS")

                st.markdown(
                    '<div class="meta-text" style="margin-top:14px;margin-bottom:6px;">Required column</div>'
                    + _column_chip("item_name", True)
                    + '<div class="meta-text" style="margin-top:12px;margin-bottom:6px;">Optional columns</div>'
                    + _column_chip("sub_category", False) + _column_chip("category", False),
                    unsafe_allow_html=True,
                )

                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                is_running   = st.session_state["cat_running"]
                cta_label    = "Analyzing products…" if is_running else "Run category analysis"
                run_file_clicked = st.button(
                    cta_label,
                    type="primary",
                    icon=None if is_running else ":material/auto_awesome:",
                    use_container_width=True,
                    disabled=is_running or uploaded_file is None,
                    key="cat_run_file",
                )

            with tab_ask:
                question = st.text_area(
                    "Question",
                    height=110,
                    placeholder="Ask the Category Intelligence Agent…",
                    label_visibility="collapsed",
                    key="cat_question",
                )
                st.caption("Example: Where should surgical gloves be categorized?")
                run_ask_clicked = st.button(
                    "Ask",
                    type="primary",
                    icon=":material/send:",
                    use_container_width=True,
                    disabled=not bool(question.strip()),
                    key="cat_run_ask",
                )

            with tab_examples:
                for icon, title, body in _CATEGORY_EXAMPLES:
                    st.markdown(
                        f'<div class="cat-row" style="align-items:flex-start;">'
                        f'<span class="mat-ico">{icon}</span>'
                        f'<div><div style="font-weight:600;color:{C["text_primary"]};font-size:13.5px;">{title}</div>'
                        f'<div class="meta-text" style="margin-top:2px;">{body}</div></div></div>',
                        unsafe_allow_html=True,
                    )

    with col_right:
        with st.container(border=True):
            h1, h2 = st.columns([2.2, 1])
            with h1:
                st.markdown('<div class="card-title">Official Categories</div>', unsafe_allow_html=True)
            with h2:
                st.button("Manage", type="tertiary", icon=":material/tune:", key="cat_manage")

            for cat, icon in _CATEGORY_INFO.items():
                st.markdown(
                    f'<div class="cat-row"><span class="mat-ico">{icon}</span>{cat}</div>',
                    unsafe_allow_html=True,
                )

            st.button("Add custom category", type="tertiary", icon=":material/add:",
                       use_container_width=True, key="cat_add_custom")

        st.markdown(
            """
            <div class="tip-card">
                <span class="mat-ico">tips_and_updates</span>
                <div>
                    <div class="tip-title">Tip</div>
                    <div class="tip-body">For better results, include product name,
                    description or existing category columns.</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Run: file analysis is two-phase so the CTA can visibly switch
    #    to "Analyzing products…" before the (potentially slow) call —
    #    click sets cat_running + reruns once to repaint the disabled
    #    button, then the actual run happens on that next pass. ──
    if run_file_clicked and not st.session_state["cat_running"]:
        st.session_state["cat_running"]      = True
        st.session_state["cat_run_filename"] = uploaded_file.name if uploaded_file else "—"
        st.rerun()

    if st.session_state["cat_running"]:
        with st.spinner("Analyzing products…"):
            payload = run_category_agent(question="", uploaded_file=uploaded_file)
        st.session_state["cat_running"] = False
        st.session_state["cat_payload"] = payload

        if payload.get("success") and isinstance(payload.get("result"), pd.DataFrame):
            res = payload["result"]
            st.session_state["cat_history"].insert(0, {
                "file":       st.session_state.get("cat_run_filename", "—"),
                "date":       datetime.now().strftime("%d %b %Y, %H:%M"),
                "status":     "Completed",
                "categories": int(res["category"].nunique()) if "category" in res.columns else "—",
            })
            st.session_state["cat_history"] = st.session_state["cat_history"][:8]
        st.rerun()

    if run_ask_clicked:
        with st.spinner("Thinking…"):
            payload = run_category_agent(question=question, uploaded_file=None)
        st.session_state["cat_payload"] = payload

    # ── Render (persists across reruns instead of only right after
    #    the click — e.g. toggling "View results") ──
    if "cat_payload" in st.session_state:
        _render_category_results(st.session_state["cat_payload"])
    else:
        _empty_state(
            "No analysis yet",
            "Upload a product file or ask a question, then run the analysis.",
        )


# ============================================================
# PAGE: KNOWLEDGE ASSISTANT
# ============================================================

def page_knowledge() -> None:
    _top_bar("Knowledge Assistant")
    _agent_header(
        "Knowledge Assistant",
        "Ask grounded questions across your supply-chain knowledge base.",
    )

    col_left, col_right = st.columns([3, 2], gap="medium")

    with col_left:
        with st.container(border=True):
            st.markdown("**Ask a Question**")

            question = st.text_area(
                "Question",
                height=130,
                placeholder=(
                    "e.g. What is the average lead time for surgical consumables "
                    "in Region A?"
                ),
                label_visibility="collapsed",
                key="kb_question",
            )

            run_clicked = st.button(
                "Search knowledge base",
                type="primary",
                icon=":material/search:",
                use_container_width=True,
                disabled=not question.strip(),
                key="kb_run",
            )

    with col_right:
        with st.container(border=True):
            st.markdown("**Knowledge Base Status**")
            st.markdown(
                '<span class="badge badge-processing">Not connected</span>',
                unsafe_allow_html=True,
            )
            st.markdown("")
            st.markdown(
                f'<div style="font-size:12px;color:{C["text_muted"]};">'
                "The knowledge base index has not been built yet. "
                "Responses are placeholders until the RAG pipeline is connected."
                "</div>",
                unsafe_allow_html=True,
            )

    if run_clicked:
        with st.spinner("Searching knowledge base..."):
            payload = run_rag_agent(question)
        _render_result(payload)
    else:
        _empty_state(
            "No results yet",
            "Enter a question and click Search knowledge base.",
        )


# ============================================================
# PAGE: STOCK REALLOCATION
# ============================================================

def _render_reallocation_results(result: Dict[str, Any]) -> None:
    """
    Full Reallocation result view — KPI cards, By Cluster, Transfer
    Flow Matrix, Network Map, Transfers detail. Shared by the
    dedicated Stock Reallocation page AND the Supervisor page.
    """
    kb, ka = result["kpi_before"], result["kpi_after"]

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Availability before", f'{kb["availability_pct"]:.1f}%')
    with c2: st.metric("Availability after", f'{ka["availability_after_pct"]:.1f}%',
                       delta=f'+{ka["availability_lift_pp"]:.1f} pp')
    with c3: st.metric("Cost avoidance", f'{ka["cost_avoidance_sar"]:,.0f} SAR')
    with c4: st.metric("Capital lock after", f'{ka["capital_lock_after_sar"]:,.0f} SAR')

    st.caption(
        f'{ka["transfer_lines"]} transfer lines '
        f'({ka["wave1_lines"]} Wave 1 · {ka["wave2_lines"]} Wave 2) — '
        f'{ka["skus_transferred"]} SKUs — {ka["total_transfer_qty"]:,.0f} units moved'
    )

    st.markdown("---")
    st.subheader("By Cluster")
    bc_rows = []
    for code, before_v in kb["by_cluster"].items():
        after_v = ka["by_cluster"].get(code, {})
        bc_rows.append({
            "Cluster": CLUSTERS.get(code, (code,))[0],
            "Availability before %": before_v["availability_pct"],
            "Availability after %": after_v.get("availability_after_pct"),
            "Zero stock items": before_v["zero_stock"],
            "Excess items": before_v["excess"],
            "Capital lock (SAR)": before_v["capital_lock_sar"],
            "Received qty": after_v.get("received_qty"),
            "Received value (SAR)": after_v.get("received_value_sar"),
        })
    bc_df = pd.DataFrame(bc_rows).sort_values("Availability before %")
    st.dataframe(bc_df, use_container_width=True, hide_index=True)

    tf_df = result["transfers"]

    # ── Transfer Flow Matrix ────────────────────────────────
    st.markdown("---")
    st.subheader("Transfer Flow Matrix")
    if isinstance(tf_df, pd.DataFrame) and not tf_df.empty:
        flow = tf_df.copy()
        flow["Donor"]    = flow["Donor Cluster"].map(lambda c: CLUSTERS.get(c, (c,))[0])
        flow["Receiver"] = flow["Receiver Cluster"].map(lambda c: CLUSTERS.get(c, (c,))[0])
        matrix = flow.pivot_table(
            index="Donor", columns="Receiver",
            values="Transfer Value (SAR)", aggfunc="sum", fill_value=0,
        )
        fig_matrix = px.imshow(
            matrix,
            text_auto=",.0f",
            color_continuous_scale="Blues",
            aspect="auto",
            labels=dict(x="Receiver cluster", y="Donor cluster", color="SAR"),
        )
        fig_matrix.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color=C["text_secondary"],
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(fig_matrix, use_container_width=True, theme=None)
        st.caption("Cell value = total transfer value (SAR) from donor cluster (row) to receiver cluster (column).")
    else:
        st.info("No transfers to display in the matrix.")

    # ── Network Map ──────────────────────────────────────────
    st.markdown("---")
    st.subheader("Network Map")
    if isinstance(tf_df, pd.DataFrame) and not tf_df.empty:
        try:
            import folium
            from streamlit_folium import st_folium

            flow_map = tf_df.groupby(
                ["Donor Cluster", "Receiver Cluster"], as_index=False
            ).agg(
                value=("Transfer Value (SAR)", "sum"),
                qty=("Final Transfer Qty", "sum"),
            )

            all_lats = [v[2] for v in CLUSTERS.values()]
            all_lons = [v[3] for v in CLUSTERS.values()]
            center = [sum(all_lats) / len(all_lats), sum(all_lons) / len(all_lons)]

            m = folium.Map(location=center, zoom_start=5, tiles="CartoDB dark_matter")

            touched = set(flow_map["Donor Cluster"]) | set(flow_map["Receiver Cluster"])
            for code in touched:
                if code not in CLUSTERS:
                    continue
                name, full_name, lat, lon = CLUSTERS[code]
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color="#4C8BF5",
                    fill=True,
                    fill_color="#4C8BF5",
                    fill_opacity=0.9,
                    popup=full_name,
                    tooltip=name,
                ).add_to(m)

            max_value = flow_map["value"].max() if len(flow_map) else 1
            for _, row in flow_map.iterrows():
                d, r = row["Donor Cluster"], row["Receiver Cluster"]
                if d not in CLUSTERS or r not in CLUSTERS:
                    continue
                _, _, lat_d, lon_d = CLUSTERS[d]
                _, _, lat_r, lon_r = CLUSTERS[r]
                weight = 1.5 + 4.5 * ((row["value"] / max_value) if max_value else 0)
                folium.PolyLine(
                    locations=[[lat_d, lon_d], [lat_r, lon_r]],
                    color="#F5A623",
                    weight=weight,
                    opacity=0.7,
                    tooltip=(
                        f"{CLUSTERS[d][0]} → {CLUSTERS[r][0]}: "
                        f"{row['qty']:,.0f} units — {row['value']:,.0f} SAR"
                    ),
                ).add_to(m)

            st_folium(m, use_container_width=True, height=480, key=f"realloc_map_{id(result)}")
        except ImportError:
            st.info(
                "Install `folium` and `streamlit-folium` "
                "(`pip install folium streamlit-folium`) to display the network map."
            )
    else:
        st.info("No transfers to display on the map.")

    # ── Transfers detail table ───────────────────────────────
    st.markdown("---")
    st.subheader("Transfers")
    col_dl, _ = st.columns([1, 3])
    with col_dl:
        st.download_button(
            "Download transfers",
            data=df_to_excel_bytes({"TRANSFERS": tf_df}),
            file_name=f"reallocation_transfers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            icon=":material/download:",
            key=f"realloc_dl_{id(result)}",
        )
    st.dataframe(tf_df, use_container_width=True)


def page_reallocation() -> None:
    _top_bar("Stock Reallocation")
    _agent_header(
        "Stock Reallocation Agent",
        "Identify transfer opportunities and rebalance stock between locations.",
    )

    col_upload, col_status = st.columns([3, 2], gap="medium")

    with col_upload:
        with st.container(border=True):
            st.markdown("**Upload Stock File**")
            st.caption("Excel only (.xlsx / .xls) — Cluster Compiled format")

            uploaded_file = st.file_uploader(
                "Drop your stock file here",
                type=["xlsx", "xls"],
                key="realloc_file",
                label_visibility="collapsed",
            )

            st.markdown("---")
            run_clicked = st.button(
                "Run reallocation analysis",
                type="primary",
                icon=":material/auto_awesome:",
                use_container_width=True,
                disabled=(uploaded_file is None),
                key="realloc_run",
            )
            if uploaded_file is None:
                st.caption("Upload a file above to enable analysis.")

    with col_status:
        with st.container(border=True):
            st.markdown("**Agent Status**")
            st.markdown(
                '<span class="badge badge-ready">Ready</span>',
                unsafe_allow_html=True,
            )
            st.markdown("")
            st.markdown(
                f'<div style="font-size:12px;color:{C["text_muted"]};">'
                "Wave 1 / Wave 2 reallocation engine — closest donor first, "
                "SAR 1,000 minimum transfer value."
                "</div>",
                unsafe_allow_html=True,
            )

    if run_clicked and uploaded_file is not None:
        with st.spinner("Processing stock data..."):
            payload = run_reallocation_agent(uploaded_file)

        if not payload.get("success"):
            _error_state(payload)
            return

        result = payload.get("result")
        if not isinstance(result, dict) or "kpi_before" not in result:
            st.error("The engine did not return the expected format.")
            _render_result(payload)
            return

        st.session_state["realloc_result"] = result

    if "realloc_result" in st.session_state:
        _render_reallocation_results(st.session_state["realloc_result"])
    else:
        _empty_state(
            "No results yet",
            "Upload a stock file and click Run reallocation analysis.",
        )

# ============================================================
# MAIN
# ============================================================

def main() -> None:
    load_css()
    page = render_sidebar()

    if   page == "supervisor":   page_supervisor()
    elif page == "inventory":    page_inventory()
    elif page == "category":     page_category()
    elif page == "knowledge":    page_knowledge()
    elif page == "reallocation": page_reallocation()
    else:                        page_supervisor()


if __name__ == "__main__":
    main()
