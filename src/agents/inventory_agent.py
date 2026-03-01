import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Constantes statut
STATUS_OOS      = "OOS"
STATUS_RISK     = "Risk of OOS"
STATUS_OPTIMUM  = "Optimum"
STATUS_EXCESS   = "Excess"

# Constantes alertes
ALERT_ORDER = "⚠ TO BE ORDERED"
ALERT_HOLD  = "🛑 HOLD OFF ORDERING"
ALERT_OK    = "✅ OPTIMUM"


def compute_coverage(df):
    df = df.copy()
    df["actual_coverage"] = np.where(
        df["consumption"] > 0,
        df["soh"] / df["consumption"],
        0.0
    )
    return df


def classify_inventory_status(df):
    df = df.copy()
    conditions = [
        df["actual_coverage"] == 0,
        (df["actual_coverage"] > 0) & (df["actual_coverage"] < df["target_coverage"]),
        df["actual_coverage"] > df["target_coverage"],
    ]
    choices = [STATUS_OOS, STATUS_RISK, STATUS_EXCESS]
    df["inventory_status"] = np.select(conditions, choices, default=STATUS_OPTIMUM)
    return df


def compute_to_order_qty(df):
    df = df.copy()
    need_order = df["inventory_status"].isin([STATUS_OOS, STATUS_RISK])
    raw_qty = (df["target_coverage"] * df["consumption"]) - df["soh"]
    df["to_order_qty"] = np.where(need_order, np.maximum(0, raw_qty), 0.0)
    return df


def compute_to_order_sar(df):
    df = df.copy()
    price = df["unit_price"].fillna(0)
    df["to_order_sar"] = (df["to_order_qty"] * price).round(2)
    return df


def compute_expired_sar(df):
    df = df.copy()
    price = df["unit_price"].fillna(0)
    df["expired_sar"] = (df["nupco_expired"] * price).round(2)
    return df


def compute_alerts(df):
    df = df.copy()
    conditions = [
        df["inventory_status"].isin([STATUS_OOS, STATUS_RISK]),
        df["inventory_status"] == STATUS_EXCESS,
    ]
    choices = [ALERT_ORDER, ALERT_HOLD]
    df["inventory_status_alert"] = np.select(conditions, choices, default=ALERT_OK)
    return df


def compute_value_of_request(df):
    df = df.copy()
    price = df["unit_price"].fillna(0)
    df["value_of_request_sar"] = (df["request_qty"] * price).round(2)
    return df


def compute_cost_avoided(df):
    df = df.copy()
    df["cost_avoided_sar"] = np.maximum(
        0, df["value_of_request_sar"] - df["to_order_sar"]
    ).round(2)
    return df


def apply_abr_final_decision(df):
    df = df.copy()
    df["final_decision_qty"] = np.maximum(0, df["to_order_qty"])
    price = df["unit_price"].fillna(0)
    df["final_decision_sar"] = (df["final_decision_qty"] * price).round(2)
    return df


def compute_decision_vs_request(df):
    df = df.copy()
    conditions = [
        df["final_decision_qty"] < df["request_qty"],
        df["final_decision_qty"] > df["request_qty"],
    ]
    choices = ["Less than request", "More than request"]
    df["decision_vs_request"] = np.select(conditions, choices, default="Equal to request")
    return df


def validate_decision(df):
    df = df.copy()
    df["price_alert"] = df["unit_price"].isna() | (df["unit_price"] <= 0)
    return df


def run_decision_agent(df):
    logger.info("Lancement decision agent...")
    df = compute_coverage(df)
    df = classify_inventory_status(df)
    df = compute_to_order_qty(df)
    df = compute_to_order_sar(df)
    df = compute_expired_sar(df)
    df = compute_alerts(df)
    df = compute_value_of_request(df)
    df = compute_cost_avoided(df)
    df = apply_abr_final_decision(df)
    df = compute_decision_vs_request(df)
    df = validate_decision(df)
    logger.info(
        f"OOS={( df.inventory_status == STATUS_OOS).sum()} | "
        f"Risk={(df.inventory_status == STATUS_RISK).sum()} | "
        f"Optimum={(df.inventory_status == STATUS_OPTIMUM).sum()} | "
        f"Excess={(df.inventory_status == STATUS_EXCESS).sum()}"
    )
    return df


def generate_decision_summary(df):
    return {
        "total_items"               : len(df),
        "oos_count"                 : int((df["inventory_status"] == STATUS_OOS).sum()),
        "risk_count"                : int((df["inventory_status"] == STATUS_RISK).sum()),
        "optimum_count"             : int((df["inventory_status"] == STATUS_OPTIMUM).sum()),
        "excess_count"              : int((df["inventory_status"] == STATUS_EXCESS).sum()),
        "oos_pct"                   : round((df["inventory_status"] == STATUS_OOS).mean() * 100, 1),
        "total_value_to_order_sar"  : round(df["to_order_sar"].sum(), 2),
        "total_cost_avoided_sar"    : round(df["cost_avoided_sar"].sum(), 2),
        "total_expired_sar"         : round(df["expired_sar"].sum(), 2),
        "items_to_be_ordered"       : int((df["inventory_status_alert"] == ALERT_ORDER).sum()),
        "avg_actual_coverage"       : round(df["actual_coverage"].mean(), 2),
    }
