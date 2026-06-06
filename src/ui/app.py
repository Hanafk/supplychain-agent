from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from src.ui.adapters import (
    run_category_agent,
    run_inventory_agent,
    run_rag_agent,
    run_reallocation_agent,
    run_supervisor,
)


st.set_page_config(
    page_title="Supply Chain Agent",
    page_icon="📦",
    layout="wide",
)


# ============================================================
# RENDER RESULT
# ============================================================

def render_result(payload: dict[str, Any]) -> None:
    if not payload.get("success", False):
        st.error(payload.get("error", "Erreur inconnue"))
        with st.expander("Traceback"):
            st.code(payload.get("traceback", ""), language="python")
        return

    if payload.get("warning"):
        st.warning(payload["warning"])

    result = payload.get("result")

    if isinstance(result, pd.DataFrame):
        st.dataframe(result, use_container_width=True)
        return

    if isinstance(result, dict):
        preview = result.get("preview")
        result_copy = dict(result)

        if isinstance(preview, pd.DataFrame):
            st.subheader("Preview")
            st.dataframe(preview, use_container_width=True)
            result_copy.pop("preview", None)

        if result_copy:
            st.subheader("Résultat")
            st.json(result_copy)

        return

    if isinstance(result, list):
        st.write(result)
        return

    st.write(result)


# ============================================================
# INVENTORY PAGE
# ============================================================

def page_inventory() -> None:
    st.title("📦 Inventory Agent")
    st.write("Charge un fichier Excel pour l’analyse d’inventaire.")

    # ---------- UPLOAD ----------
    uploaded_file = st.file_uploader(
        "Importer un fichier Excel",
        type=["xlsx", "xls"],
        key="inventory_file",
    )

    if uploaded_file is not None:
        try:
            df_preview = pd.read_excel(uploaded_file)
            st.subheader("Aperçu du fichier")
            st.dataframe(df_preview.head(20), use_container_width=True)
            uploaded_file.seek(0)
        except Exception as exc:
            st.error(f"Impossible de lire le fichier : {exc}")
            return

    # ---------- TEMPLATE SECTION ----------
    st.markdown("---")

    # ---------- INTRO ----------
    st.markdown(
        """
Download the Excel template below, fill it with your data, and upload it on this page.
"""
    )

    # ---------- TEMPLATE COLUMNS ----------
    TEMPLATE_COLUMNS = [
        "item_code",
        "item_description",
        "SOH",
        "consumption",
        "unit_price",
        "request_qty",
        "open_qty",
        "contract_qty",
        "received_qty",
        "expired_qty",
        "region",
        "category",
        "sub_category",
    ]

    template_df = pd.DataFrame(columns=TEMPLATE_COLUMNS)

    # ---------- EXPORT FUNCTION ----------
    def df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "TEMPLATE") -> bytes:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        return output.getvalue()

    # ---------- DOWNLOAD BUTTON ----------
    xls_bytes = df_to_excel_bytes(template_df)

    st.download_button(
        label="📥 Download Excel Template",
        data=xls_bytes,
        file_name=f"tool_holdco_template_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # ---------- FIELD DESCRIPTION ----------
    st.subheader("Field Description")

    st.markdown(
        """
### 🔹 Required fields
- **item_code** — Unique identifier
- **item_description** — Item name / description
- **SOH** — Stock on hand (units)
- **consumption** — Monthly consumption (units/month)
- **unit_price** — Price per unit (SAR)
- **request_qty** — Quantity initially requested by the cluster (units)

### 🔹 Optional fields
- **open_qty** — Open PO quantity
- **contract_qty** — Contracted quantity
- **received_qty** — Received quantity
- **expired_qty** — Expired units
- **region** — Region / cluster
- **category** — Item category
- **sub_category** — Sub category
"""
    )

    # ---------- RUN BUTTON ----------
    st.markdown("---")

    if st.button("Lancer Inventory Agent", use_container_width=True):
        if uploaded_file is None:
            st.warning("Ajoute un fichier Excel.")
            return

        with st.spinner("Analyse en cours..."):
            payload = run_inventory_agent(uploaded_file)

        render_result(payload)


# ============================================================
# OTHER PAGES
# ============================================================

def page_category() -> None:
    st.title("🏷️ Category Agent")
    st.write("Pose une question liée à la catégorisation.")

    question = st.text_area("Question", height=150)

    if st.button("Lancer Category Agent", use_container_width=True):
        payload = run_category_agent(question)
        render_result(payload)


def page_rag() -> None:
    st.title("🧠 RAG Agent")

    question = st.text_area("Question RAG", height=150)

    if st.button("Lancer RAG Agent", use_container_width=True):
        payload = run_rag_agent(question)
        render_result(payload)


def page_reallocation() -> None:
    st.title("🔄 Reallocation Agent")

    uploaded_file = st.file_uploader("Importer un fichier Excel")

    if st.button("Lancer Reallocation Agent", use_container_width=True):
        payload = run_reallocation_agent(uploaded_file)
        render_result(payload)


def page_general() -> None:
    st.title("🧭 General / Supervisor")

    mode = st.selectbox(
        "Sélectionne un agent",
        ["inventory", "category", "rag", "reallocation"],
    )

    question = st.text_area("Question")
    uploaded_file = st.file_uploader("Fichier")

    if st.button("Lancer via Supervisor", use_container_width=True):
        payload = run_supervisor(mode, uploaded_file, question)
        render_result(payload)


# ============================================================
# SIDEBAR
# ============================================================

def sidebar() -> str:
    st.sidebar.title("Navigation")
    return st.sidebar.radio(
        "Choisis une vue",
        [
            "General / Supervisor",
            "Inventory Agent",
            "Category Agent",
            "RAG Agent",
            "Reallocation Agent",
        ],
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    page = sidebar()

    if page == "Inventory Agent":
        page_inventory()
    elif page == "Category Agent":
        page_category()
    elif page == "RAG Agent":
        page_rag()
    elif page == "Reallocation Agent":
        page_reallocation()
    else:
        page_general()


if __name__ == "__main__":
    main()
