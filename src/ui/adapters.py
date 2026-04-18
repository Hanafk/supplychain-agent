from __future__ import annotations

import io
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"

DATA_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)


def _read_excel(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        raise ValueError("Aucun fichier fourni.")
    uploaded_file.seek(0)
    return pd.read_excel(uploaded_file)


def _safe_to_dict(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    return {"result": obj}


def _exception_payload(exc: Exception) -> Dict[str, Any]:
    return {
        "success": False,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }


# ============================================================
# INVENTORY AGENT
# ============================================================
def run_inventory_agent(uploaded_file) -> Dict[str, Any]:
    """
    Attend un Excel en entrée.
    Essaie plusieurs patterns d'appel pour s'adapter à ton code existant.
    """
    try:
        df = _read_excel(uploaded_file)

        # --- tentative 1 : fonction process_inventory(df)
        try:
            from src.agents.inventory_agent import process_inventory  # type: ignore

            result = process_inventory(df)
            return {
                "success": True,
                "dataframe": df,
                "result": result,
                "agent": "inventory_agent",
            }
        except Exception:
            pass

        # --- tentative 2 : classe InventoryAgent avec run/analyze/process
        try:
            from src.agents.inventory_agent import InventoryAgent  # type: ignore

            agent = InventoryAgent()

            if hasattr(agent, "run"):
                result = agent.run(df)
            elif hasattr(agent, "analyze"):
                result = agent.analyze(df)
            elif hasattr(agent, "process"):
                result = agent.process(df)
            else:
                raise AttributeError(
                    "InventoryAgent existe mais n'a pas de méthode run/analyze/process."
                )

            return {
                "success": True,
                "dataframe": df,
                "result": result,
                "agent": "inventory_agent",
            }
        except Exception:
            pass

        # fallback
        summary = {
            "rows": len(df),
            "columns": list(df.columns),
            "missing_values": df.isna().sum().to_dict(),
            "preview": df.head(10),
        }

        return {
            "success": True,
            "dataframe": df,
            "result": summary,
            "agent": "inventory_agent",
            "warning": "Aucune fonction standard trouvée dans inventory_agent.py. Fallback utilisé.",
        }

    except Exception as exc:
        return _exception_payload(exc)


# ============================================================
# CATEGORY AGENT
# ============================================================
def run_category_agent(question: str) -> Dict[str, Any]:
    """
    Attend une question texte.
    """
    try:
        if not question or not question.strip():
            raise ValueError("La question est vide.")

        # --- tentative 1 : fonction ask_category_agent(question)
        try:
            from src.agents.category_agent import ask_category_agent  # type: ignore

            result = ask_category_agent(question)
            return {
                "success": True,
                "result": result,
                "agent": "category_agent",
            }
        except Exception:
            pass

        # --- tentative 2 : classe CategoryAgent
        try:
            from src.agents.category_agent import CategoryAgent  # type: ignore

            agent = CategoryAgent()

            if hasattr(agent, "run"):
                result = agent.run(question)
            elif hasattr(agent, "ask"):
                result = agent.ask(question)
            elif hasattr(agent, "analyze"):
                result = agent.analyze(question)
            else:
                raise AttributeError(
                    "CategoryAgent existe mais n'a pas de méthode run/ask/analyze."
                )

            return {
                "success": True,
                "result": result,
                "agent": "category_agent",
            }
        except Exception:
            pass

        return {
            "success": True,
            "result": f"[Fallback] Category agent reçu : {question}",
            "agent": "category_agent",
            "warning": "Aucune fonction standard trouvée dans category_agent.py. Fallback utilisé.",
        }

    except Exception as exc:
        return _exception_payload(exc)


# ============================================================
# RAG AGENT
# ============================================================
def run_rag_agent(question: str) -> Dict[str, Any]:
    """
    Attend une question texte.
    """
    try:
        if not question or not question.strip():
            raise ValueError("La question est vide.")

        # --- tentative 1 : fonction ask_rag(question)
        try:
            from src.agents.RAG_agent import ask_rag  # type: ignore

            result = ask_rag(question)
            return {
                "success": True,
                "result": result,
                "agent": "RAG_agent",
            }
        except Exception:
            pass

        # --- tentative 2 : classe RAGAgent
        try:
            from src.agents.RAG_agent import RAGAgent  # type: ignore

            agent = RAGAgent()

            if hasattr(agent, "run"):
                result = agent.run(question)
            elif hasattr(agent, "ask"):
                result = agent.ask(question)
            elif hasattr(agent, "query"):
                result = agent.query(question)
            else:
                raise AttributeError(
                    "RAGAgent existe mais n'a pas de méthode run/ask/query."
                )

            return {
                "success": True,
                "result": result,
                "agent": "RAG_agent",
            }
        except Exception:
            pass

        return {
            "success": True,
            "result": f"[Fallback] RAG agent reçu : {question}",
            "agent": "RAG_agent",
            "warning": "Aucune fonction standard trouvée dans RAG_agent.py. Fallback utilisé.",
        }

    except Exception as exc:
        return _exception_payload(exc)


# ============================================================
# REALLOCATION AGENT
# ============================================================
def run_reallocation_agent(uploaded_file) -> Dict[str, Any]:
    """
    Attend un Excel en entrée.
    """
    try:
        df = _read_excel(uploaded_file)

        # --- tentative 1 : fonction process_reallocation(df)
        try:
            from src.agents.reallocation_agent import process_reallocation  # type: ignore

            result = process_reallocation(df)
            return {
                "success": True,
                "dataframe": df,
                "result": result,
                "agent": "reallocation_agent",
            }
        except Exception:
            pass

        # --- tentative 2 : classe ReallocationAgent
        try:
            from src.agents.reallocation_agent import ReallocationAgent  # type: ignore

            agent = ReallocationAgent()

            if hasattr(agent, "run"):
                result = agent.run(df)
            elif hasattr(agent, "optimize"):
                result = agent.optimize(df)
            elif hasattr(agent, "process"):
                result = agent.process(df)
            else:
                raise AttributeError(
                    "ReallocationAgent existe mais n'a pas de méthode run/optimize/process."
                )

            return {
                "success": True,
                "dataframe": df,
                "result": result,
                "agent": "reallocation_agent",
            }
        except Exception:
            pass

        summary = {
            "rows": len(df),
            "columns": list(df.columns),
            "preview": df.head(10),
        }

        return {
            "success": True,
            "dataframe": df,
            "result": summary,
            "agent": "reallocation_agent",
            "warning": "Aucune fonction standard trouvée dans reallocation_agent.py. Fallback utilisé.",
        }

    except Exception as exc:
        return _exception_payload(exc)


# ============================================================
# SUPERVISOR / GENERAL
# ============================================================
def run_supervisor(
    mode: str,
    uploaded_file=None,
    question: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Routeur simple vers l'agent adapté.
    """
    try:
        mode = (mode or "").strip().lower()

        if mode == "inventory":
            return run_inventory_agent(uploaded_file)

        if mode == "category":
            return run_category_agent(question or "")

        if mode == "rag":
            return run_rag_agent(question or "")

        if mode == "reallocation":
            return run_reallocation_agent(uploaded_file)

        raise ValueError(f"Mode inconnu: {mode}")

    except Exception as exc:
        return _exception_payload(exc)
