import re
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

STATUS_OOS = "OOS"
STATUS_RISK = "Risk of OOS"
STATUS_OPTIMUM = "Optimum"
STATUS_EXCESS = "Excess"


def normalize_header(s: str) -> str:
    if s is None:
        return ""
    t = str(s).strip().lower().replace("_", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return "".join(ch for ch in t if ch.isalnum())


def find_col(df: pd.DataFrame, *candidates):
    targets = {normalize_header(c) for c in candidates if c is not None}
    for col in df.columns:
        if normalize_header(col) in targets:
            return col
    return None


def as_num(series, index=None):
    if series is None:
        return pd.Series(0.0, index=index)
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def process_inventory(
    df: pd.DataFrame,
    target_coverage: float = 6.0,
    use_soh_for_oos: bool = False,
):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    idx = df.index

    col_soh = find_col(
        df,
        "SOH",
        "stock on hand",
        "stock_on_hand",
        "total stock",
        "nupco_total_stock",
    )
    col_mc = find_col(
        df,
        "consumption",
        "monthly consumption",
        "monthly_consumption",
        "nupco_monthly_consumption",
        "nupco_monthly consumption",
    )
    col_price = find_col(
        df,
        "unit_price",
        "unit price",
        "unit sar",
        "price",
    )
    col_expired = find_col(
        df,
        "expired_qty",
        "expired quantity",
        "expired",
        "nupco_expired",
        "expiry qty",
        "expiry quantity",
    )
    col_request_qty = find_col(
        df,
        "request_qty",
        "request quantity",
        "requested_qty",
        "requested quantity",
        "qty_request",
        "qty requested",
        "requestqty",
    )
    col_open = find_col(
        df,
        "open_qty",
        "open qty",
        "openqty",
        "po open qty",
        "on order",
        "open quantity",
    )
    col_contract = find_col(
        df,
        "contract_qty",
        "contract qty",
        "contract quantity",
        "contractqty",
        "contract_quantity",
    )
    col_received = find_col(
        df,
        "received_qty",
        "received qty",
        "receivedqty",
        "received_quantity",
        "received quantity",
        "supplied_qty",
        "supplied qty",
        "suppliedqty",
        "delivered_qty",
        "delivered qty",
        "deliveredqty",
    )

    missing = [
        name
        for name, col in [
            ("SOH", col_soh),
            ("consumption", col_mc),
            ("unit_price", col_price),
        ]
        if col is None
    ]

    if missing:
        raise ValueError(
            "Colonnes obligatoires manquantes : "
            + ", ".join(missing)
            + ". Minimum requis : SOH, consumption, unit_price."
        )

    try:
        target_coverage = float(target_coverage)
        if target_coverage < 0:
            target_coverage = 6.0
    except Exception:
        target_coverage = 6.0

    soh = as_num(df[col_soh], idx)
    mc = as_num(df[col_mc], idx)
    price = as_num(df[col_price], idx)

    expired_qty = as_num(df[col_expired], idx) if col_expired else pd.Series(0.0, index=idx)
    request_qty = as_num(df[col_request_qty], idx) if col_request_qty else pd.Series(0.0, index=idx)

    if col_open is not None:
        open_qty = as_num(df[col_open], idx)
    elif col_contract is not None and col_received is not None:
        contract_qty = as_num(df[col_contract], idx)
        received_qty = as_num(df[col_received], idx)
        open_qty = (contract_qty - received_qty).clip(lower=0.0)
    else:
        open_qty = pd.Series(0.0, index=idx)

    total_available = soh + open_qty

    actual_coverage = pd.Series(0.0, index=idx)
    actual_coverage = actual_coverage.mask(mc > 0, total_available / mc).fillna(0.0)

    def status_from_coverage(c):
        if c == 0:
            return STATUS_OOS
        if c < target_coverage:
            return STATUS_RISK
        if c <= target_coverage * 1.2:
            return STATUS_OPTIMUM
        return STATUS_EXCESS

    inventory_status = actual_coverage.apply(status_from_coverage)

    if use_soh_for_oos:
        soh_oos = (soh == 0) & (mc > 0)
        inventory_status = inventory_status.where(~soh_oos, STATUS_OOS)
        flag_oos = pd.Series("SOH", index=idx).where(~soh_oos, "OOS")
    else:
        flag_oos = pd.Series("", index=idx)

    need_order = inventory_status.isin([STATUS_OOS, STATUS_RISK]) & (mc > 0)

    to_order_qty = pd.Series(0.0, index=idx)
    to_order_qty = to_order_qty.mask(
        need_order,
        target_coverage * mc - total_available,
    ).fillna(0.0)

    to_order_qty = to_order_qty.clip(lower=0).round(0)
    to_order_sar = (to_order_qty * price).round(2)

    request_sar = (request_qty * price).round(2)
    expired_sar = (expired_qty * price).round(2)

    def compute_final_decision_qty(request, to_order):
        if request <= 0 and to_order <= 0:
            return 0.0
        if request <= 0 and to_order > 0:
            return to_order
        if request > 0 and to_order <= 0:
            return 0.0
        return min(request, to_order)

    final_decision_qty = pd.Series(
        [
            compute_final_decision_qty(r, t)
            for r, t in zip(request_qty, to_order_qty)
        ],
        index=idx,
    ).round(0)

    final_decision_sar = (final_decision_qty * price).round(2)
    saving_sar = (request_sar - final_decision_sar).clip(lower=0).round(2)

    def alert_from_coverage(c):
        if c < target_coverage:
            return "⚠ ORDER MORE"
        if c <= target_coverage * 1.2:
            return "✔ MAINTAIN / REVIEW"
        return "\U0001F6D1 HOLD OFF ORDERING"

    inventory_status_alert = actual_coverage.apply(alert_from_coverage)

    out = df.copy()
    out["Open qty (used in calc)"] = open_qty
    out["Actual coverage"] = actual_coverage.round(2)
    out["Target coverage"] = target_coverage
    out["Inventory status"] = inventory_status
    out["Flag OOS (SOH)"] = flag_oos
    out["To order qty"] = to_order_qty
    out["To order SAR"] = to_order_sar
    out["Request SAR"] = request_sar
    out["Final decision qty"] = final_decision_qty
    out["Final decision SAR"] = final_decision_sar
    out["Saving SAR"] = saving_sar
    out["Expired SAR"] = expired_sar
    out["Inventory status alert"] = inventory_status_alert
    out["Price alert"] = price <= 0

    summary = generate_decision_summary(out)

    return {
        "data": out,
        "summary": summary,
    }


def generate_decision_summary(df: pd.DataFrame):
    return {
        "total_items": len(df),
        "oos_count": int((df["Inventory status"] == STATUS_OOS).sum()),
        "risk_count": int((df["Inventory status"] == STATUS_RISK).sum()),
        "optimum_count": int((df["Inventory status"] == STATUS_OPTIMUM).sum()),
        "excess_count": int((df["Inventory status"] == STATUS_EXCESS).sum()),
        "oos_pct": round((df["Inventory status"] == STATUS_OOS).mean() * 100, 1),
        "total_to_order_sar": round(df["To order SAR"].sum(), 2),
        "total_final_decision_sar": round(df["Final decision SAR"].sum(), 2),
        "total_saving_sar": round(df["Saving SAR"].sum(), 2),
        "total_expired_sar": round(df["Expired SAR"].sum(), 2),
        "items_to_order": int((df["To order qty"] > 0).sum()),
        "avg_actual_coverage": round(df["Actual coverage"].mean(), 2),
    }
