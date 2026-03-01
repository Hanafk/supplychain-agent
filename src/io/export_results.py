import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Colonnes à inclure dans l'output final (dans l'ordre)
OUTPUT_COLS = [
    "region", "item_code", "item_name", "category", "sub_category",
    "tender_check", "soh", "consumption", "nupco_expired", "unit_price",
    "target_coverage", "actual_coverage", "inventory_status",
    "to_order_qty", "to_order_sar", "expired_sar",
    "inventory_status_alert", "request_qty", "value_of_request_sar",
    "cost_avoided_sar", "final_decision_qty", "final_decision_sar",
    "decision_vs_request", "price_alert",
]


def export_to_excel(
    df: pd.DataFrame,
    kpi: dict,
    quality: dict,
    output_path: str = "outputs/results.xlsx",
) -> str:

    # Créer le dossier outputs si nécessaire
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:

        # Onglet 1 — Décisions item par item
        cols = [c for c in OUTPUT_COLS if c in df.columns]
        df[cols].to_excel(writer, sheet_name="Decisions", index=False)

        # Onglet 2 — KPIs summary
        kpi_rows = [[k, v] for k, v in kpi.items()]
        pd.DataFrame(kpi_rows, columns=["Metric", "Value"]).to_excel(
            writer, sheet_name="KPI_Summary", index=False
        )

        # Onglet 3 — Rapport qualité
        dq_rows = []
        for k, v in quality.items():
            if k == "missing_by_column":
                for col, pct in v.items():
                    dq_rows.append([f"Missing % — {col}", f"{pct}%"])
            elif k == "anomalies":
                for a in v:
                    dq_rows.append(["Anomalie", a])
            else:
                dq_rows.append([k, v])
        pd.DataFrame(dq_rows, columns=["Check", "Value"]).to_excel(
            writer, sheet_name="Data_Quality", index=False
        )

    logger.info(f"Export terminé → {output_path}")
    return output_path
