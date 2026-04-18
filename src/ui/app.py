from __future__ import annotations

import json
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
        # afficher preview si présente
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


def page_inventory() -> None:
    st.title("📦 Inventory Agent")
    st.write("Charge un fichier Excel pour l’analyse d’inventaire.")

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

    if st.button("Lancer Inventory Agent", use_container_width=True):
        if uploaded_file is None:
            st.warning("Ajoute un fichier Excel.")
            return

        with st.spinner("Analyse en cours..."):
            payload = run_inventory_agent(uploaded_file)

        render_result(payload)


def page_category() -> None:
    st.title("🏷️ Category Agent")
    st.write("Pose une question liée à la catégorisation.")

    question = st.text_area(
        "Question",
        placeholder="Ex: Dans quelle catégorie faut-il ranger les produits saisonniers à faible rotation ?",
        height=150,
        key="category_question",
    )

    if st.button("Lancer Category Agent", use_container_width=True):
        with st.spinner("Analyse en cours..."):
            payload = run_category_agent(question)

        render_result(payload)


def page_rag() -> None:
    st.title("🧠 RAG Agent")
    st.write("Pose une question au moteur RAG.")

    question = st.text_area(
        "Question RAG",
        placeholder="Ex: Quels sont les risques de rupture sur la famille X ?",
        height=150,
        key="rag_question",
    )

    if st.button("Lancer RAG Agent", use_container_width=True):
        with st.spinner("Recherche en cours..."):
            payload = run_rag_agent(question)

        render_result(payload)


def page_reallocation() -> None:
    st.title("🔄 Reallocation Agent")
    st.write("Charge un fichier Excel pour la réallocation.")

    uploaded_file = st.file_uploader(
        "Importer un fichier Excel",
        type=["xlsx", "xls"],
        key="reallocation_file",
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

    if st.button("Lancer Reallocation Agent", use_container_width=True):
        if uploaded_file is None:
            st.warning("Ajoute un fichier Excel.")
            return

        with st.spinner("Optimisation en cours..."):
            payload = run_reallocation_agent(uploaded_file)

        render_result(payload)


def page_general() -> None:
    st.title("🧭 General / Supervisor")
    st.write("Choisis quel agent lancer depuis le superviseur.")

    mode = st.selectbox(
        "Sélectionne un agent",
        options=[
            "inventory",
            "category",
            "rag",
            "reallocation",
        ],
        index=0,
    )

    question = None
    uploaded_file = None

    if mode in ["inventory", "reallocation"]:
        uploaded_file = st.file_uploader(
            "Importer un fichier Excel",
            type=["xlsx", "xls"],
            key=f"general_file_{mode}",
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

    if mode in ["category", "rag"]:
        question = st.text_area(
            "Question",
            placeholder="Pose ta question ici...",
            height=150,
            key=f"general_question_{mode}",
        )

    if st.button("Lancer via Supervisor", use_container_width=True):
        with st.spinner("Le supervisor traite la demande..."):
            payload = run_supervisor(
                mode=mode,
                uploaded_file=uploaded_file,
                question=question,
            )
        render_result(payload)


def sidebar() -> str:
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Choisis une vue",
        [
            "General / Supervisor",
            "Inventory Agent",
            "Category Agent",
            "RAG Agent",
            "Reallocation Agent",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.info(
        "General / Supervisor route vers l’agent adapté.\n\n"
        "Chaque agent peut aussi être utilisé séparément."
    )
    return page


def main() -> None:
    page = sidebar()

    if page == "General / Supervisor":
        page_general()
    elif page == "Inventory Agent":
        page_inventory()
    elif page == "Category Agent":
        page_category()
    elif page == "RAG Agent":
        page_rag()
    elif page == "Reallocation Agent":
        page_reallocation()


if __name__ == "__main__":
    main()
