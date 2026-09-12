# ─────────────────────────────────────────────────────────────────
#  reallocation_engine.py — Cluster Request core engine (Wave 1/2)
#
#  Ported from the validated HHC V4 business logic, core only:
#  no palletization, no warehouse capacity, no receiver-file /
#  item-decision classification. Extended from 7 to 20 clusters by
#  computing donor distance from real coordinates (haversine)
#  instead of the old hardcoded 7x7 table.
#
#  Validated rules preserved exactly:
#    - Coverage      = Available / Monthly Need
#    - Extra         = Available - (6 x Monthly Need)          [coverage_threshold]
#    - Wave 1 recv   : Available = 0 AND Monthly Need > 0
#    - Wave 2 recv   : 0 < Coverage < 3 months AND not already served in Wave 1
#    - Donor order   : closest first (greedy, sequential) by distance
#    - Final filter  : SAR 1,000 minimum transfer value, applied after allocation
#    - Rows with blank Available Stock Quantity are excluded entirely
#    - Near Expiry / Expired are reporting-only — never used in the
#      transfer decision (hard architectural boundary from V4)
# ─────────────────────────────────────────────────────────────────

import numpy as np
import pandas as pd

from src.utils.clusters import CLUSTERS, NAME_TO_CODE, CLUSTER_DISTANCE_KM

STATUS_OOS     = "OOS"
STATUS_RISK    = "Risk of OOS"
STATUS_OPTIMUM = "Optimum"
STATUS_EXCESS  = "Excess"


# ═══════════════════════════════════════════════════════════════════
# LOAD + NORMALIZE  (Compile Sheet -> internal schema)
# ═══════════════════════════════════════════════════════════════════

def load_cluster_compiled(path_or_df, sheet_name: str = "Compile Sheet") -> pd.DataFrame:
    if isinstance(path_or_df, pd.DataFrame):
        raw = path_or_df.copy()
    else:
        raw = pd.read_excel(path_or_df, sheet_name=sheet_name)

    raw.columns = [str(c).strip() for c in raw.columns]

    col_map = {
        "Cluster Name":                             "cluster_name",
        "NUPCO Code":                                "nupco",
        "Description":                               "description",
        "Category":                                  "category",
        "Monthly Need":                               "amu",
        "SOH":                                        "soh",
        "Available Stock Quantity":                   "available",
        "Expired Quantity (Last 12 Months) ":         "expired_qty",
        "Expired Quantity (Last 12 Months)":          "expired_qty",
        "Near Expiry (Next 90 Days) Quantity":        "near_expiry_qty",
        "Open PO / Available Contract Quantity":      "pending_qty",
        "Unit Price (SAR)":                           "unit_price",
    }
    present = {k: v for k, v in col_map.items() if k in raw.columns}
    df = raw.rename(columns=present)

    required = ["cluster_name", "nupco", "amu", "available", "unit_price"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in the cluster file: {missing}")

    # V4 rule: rows with a BLANK Available Stock Quantity are excluded
    # entirely (no SOH fallback). Zero is valid and kept (Wave 1 signal).
    df = df[df["available"].notna()].copy()

    df["cluster"] = df["cluster_name"].map(NAME_TO_CODE)
    unknown = df[df["cluster"].isna()]["cluster_name"].unique()
    if len(unknown):
        raise ValueError(f"Unrecognized clusters (add them to clusters.py): {list(unknown)}")

    for col in ["amu", "soh", "available", "unit_price", "pending_qty",
                "expired_qty", "near_expiry_qty"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        else:
            df[col] = 0.0

    for col in ["description", "category"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    df["nupco"] = df["nupco"].astype(str)

    keep = ["cluster", "cluster_name", "nupco", "description", "category",
            "amu", "soh", "available", "unit_price", "pending_qty",
            "expired_qty", "near_expiry_qty"]
    return df[keep].reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════
# COVERAGE / EXTRA / STATUS  (display status — same vocabulary as
# the Inventory Agent, kept separate from the Wave 1/2 targeting
# masks below, which follow the specific validated thresholds)
# ═══════════════════════════════════════════════════════════════════

def compute_metrics(df: pd.DataFrame, coverage_threshold: float = 6.0) -> pd.DataFrame:
    df = df.copy()
    df["coverage"] = np.where(df["amu"] > 0, df["available"] / df["amu"], 0.0)
    df["extra_total"] = np.where(
        df["amu"] > 0,
        np.maximum(0.0, df["available"] - df["amu"] * coverage_threshold),
        0.0,
    )

    def _status(c):
        if c == 0:                        return STATUS_OOS
        if c < coverage_threshold:        return STATUS_RISK
        if c <= coverage_threshold * 1.2: return STATUS_OPTIMUM
        return STATUS_EXCESS

    df["status"] = df["coverage"].apply(_status)
    return df


def _distance(donor_code: str, receiver_code: str) -> float:
    return CLUSTER_DISTANCE_KM.get((donor_code, receiver_code), float("inf"))


# ═══════════════════════════════════════════════════════════════════
# WAVE ALLOCATION  (closest donor first, greedy sequential)
# ═══════════════════════════════════════════════════════════════════

def _allocate_wave(pool: pd.DataFrame, receiver_mask: pd.Series, donor_col: str,
                    wave: int, block_po: bool = True) -> tuple:
    transfers = []
    donors    = pool[pool[donor_col] > 0]
    receivers = pool[receiver_mask]
    if donors.empty or receivers.empty:
        return transfers, pool

    match_keys = set(donors["nupco"]) & set(receivers["nupco"])

    for nupco in match_keys:
        kd = pool[(pool["nupco"] == nupco) & (pool[donor_col] > 0)]
        kr = pool[(pool["nupco"] == nupco) & receiver_mask]
        if kd.empty or kr.empty:
            continue

        donor_clusters = set(kd["cluster"])
        valid_recv = []
        for ridx, r in kr.iterrows():
            if not any(dc != r["cluster"] for dc in donor_clusters):
                continue
            if block_po and r.get("pending_qty", 0) > 0:
                continue
            if r.get("amu", 0) <= 0:
                continue
            valid_recv.append(ridx)
        if not valid_recv:
            continue

        for ridx in valid_recv:
            r = pool.loc[ridx]
            need = pool.loc[ridx, "receiver_need"]
            if need <= 0:
                continue
            remaining = float(need)
            recv_cluster = r["cluster"]

            donor_rows = pool[(pool["nupco"] == nupco) &
                              (pool["cluster"] != recv_cluster) &
                              (pool[donor_col] > 0)].copy()
            donor_rows["_dist"] = donor_rows["cluster"].apply(lambda dc: _distance(dc, recv_cluster))
            donor_rows = donor_rows.sort_values("_dist")

            total_supply = donor_rows[donor_col].sum()

            for didx, drow in donor_rows.iterrows():
                if remaining <= 0:
                    break
                donor_avail = pool.loc[didx, donor_col]
                give = float(np.floor(min(donor_avail, remaining)))
                if give <= 0:
                    continue

                dist = drow.get("_dist", None)
                transfers.append({
                    "Wave": wave,
                    "NUPCO Code": nupco,
                    "Description": r.get("description", ""),
                    "Category": r.get("category", ""),
                    "Donor Cluster": drow["cluster"],
                    "Receiver Cluster": recv_cluster,
                    "Distance (km)": None if dist == float("inf") else round(dist, 0),
                    "Donor Coverage (m)": round(drow.get("coverage", 0), 2),
                    "Receiver Available (before)": round(r.get("available", 0), 0),
                    "Receiver AMU": round(r.get("amu", 0), 2),
                    "Receiver Need": round(need, 0),
                    "Total Supply (nupco/receiver)": round(total_supply, 0),
                    "Final Transfer Qty": give,
                    "Unit Price (SAR)": round(drow.get("unit_price", 0), 2),
                    "Transfer Value (SAR)": round(give * drow.get("unit_price", 0), 2),
                })

                pool.loc[didx, donor_col] -= give
                remaining -= give

    return transfers, pool


def run_wave_reallocation(
    df_master: pd.DataFrame,
    coverage_threshold: float = 6.0,
    recv_coverage: float = 3.0,
    block_po: bool = True,
    min_transfer_value: float = 1000.0,
) -> dict:
    """Runs Wave 1 then Wave 2 over the whole 20-cluster network."""

    pool = compute_metrics(df_master, coverage_threshold).copy()
    pool["rem_avl"] = pool["extra_total"].clip(lower=0)

    # ── WAVE 1 — receivers: available = 0 AND amu > 0 ─────────────
    w1_mask = (pool["available"] == 0) & (pool["amu"] > 0)
    pool["receiver_need"] = np.where(w1_mask, pool["amu"] * recv_coverage, 0.0)

    tf1, pool = _allocate_wave(pool, w1_mask, "rem_avl", wave=1, block_po=block_po)

    # ── BETWEEN WAVES — recompute available / coverage / extra ────
    if tf1:
        tf1_df = pd.DataFrame(tf1)
        sent = tf1_df.groupby(["NUPCO Code", "Donor Cluster"])["Final Transfer Qty"].sum()
        recv = tf1_df.groupby(["NUPCO Code", "Receiver Cluster"])["Final Transfer Qty"].sum()
        for idx, row in pool.iterrows():
            sent_qty = sent.get((row["nupco"], row["cluster"]), 0)
            recv_qty = recv.get((row["nupco"], row["cluster"]), 0)
            pool.loc[idx, "available"] = max(0.0, row["available"] - sent_qty + recv_qty)

    pool["coverage"] = np.where(pool["amu"] > 0, pool["available"] / pool["amu"], 0.0)
    pool["extra_total"] = np.where(
        pool["amu"] > 0,
        np.maximum(0.0, pool["available"] - pool["amu"] * coverage_threshold),
        0.0,
    )
    pool["rem_avl"] = pool["extra_total"].clip(lower=0)

    w1_touched = set()
    if tf1:
        tf1_df = pd.DataFrame(tf1)
        for col in ["Donor Cluster", "Receiver Cluster"]:
            for nupco, cl in zip(tf1_df["NUPCO Code"], tf1_df[col]):
                w1_touched.add((nupco, cl))

    # ── WAVE 2 — receivers: 0 < coverage < recv_coverage, not touched in W1
    def _not_touched(row):
        return (row["nupco"], row["cluster"]) not in w1_touched

    w2_mask = (
        (pool["available"] > 0) &
        (pool["coverage"] < recv_coverage) &
        (pool["amu"] > 0) &
        pool.apply(_not_touched, axis=1)
    )
    pool["receiver_need"] = np.where(
        w2_mask,
        (pool["amu"] * recv_coverage - pool["available"] - pool["pending_qty"]).clip(lower=0),
        0.0,
    )

    tf2, pool = _allocate_wave(pool, w2_mask, "rem_avl", wave=2, block_po=block_po)

    all_transfers = tf1 + tf2

    # ── FINAL VALUE FILTER — SAR 1,000, applied after all allocation
    all_transfers = [t for t in all_transfers if t["Transfer Value (SAR)"] >= min_transfer_value]

    return {"transfers": all_transfers, "pool_after": pool}


# ═══════════════════════════════════════════════════════════════════
# POST-TRANSFER SIMULATION
# ═══════════════════════════════════════════════════════════════════

def compute_post_transfer(df_master: pd.DataFrame, transfers: list,
                           coverage_threshold: float = 6.0) -> pd.DataFrame:
    df = compute_metrics(df_master, coverage_threshold).copy()
    df["received_qty"] = 0.0
    df["received_value"] = 0.0
    df["donated_qty"] = 0.0

    if transfers:
        tf = pd.DataFrame(transfers)
        recv = tf.groupby(["NUPCO Code", "Receiver Cluster"], as_index=False).agg(
            received_qty=("Final Transfer Qty", "sum"),
            received_value=("Transfer Value (SAR)", "sum"),
        ).rename(columns={"NUPCO Code": "nupco", "Receiver Cluster": "cluster"})
        df = df.merge(recv, on=["nupco", "cluster"], how="left", suffixes=("", "_new"))
        df["received_qty"] = df["received_qty_new"].fillna(0)
        df["received_value"] = df["received_value_new"].fillna(0)
        df = df.drop(columns=["received_qty_new", "received_value_new"], errors="ignore")

        don = tf.groupby(["NUPCO Code", "Donor Cluster"], as_index=False).agg(
            donated_qty=("Final Transfer Qty", "sum"),
        ).rename(columns={"NUPCO Code": "nupco", "Donor Cluster": "cluster"})
        df = df.merge(don, on=["nupco", "cluster"], how="left", suffixes=("", "_d"))
        df["donated_qty"] = df["donated_qty_d"].fillna(0)
        df = df.drop(columns=["donated_qty_d"], errors="ignore")

    df["available_after"] = (df["available"] + df["received_qty"] - df["donated_qty"]).clip(lower=0)
    df["extra_total_after"] = np.where(
        df["amu"] > 0,
        np.maximum(0.0, df["available_after"] - df["amu"] * coverage_threshold),
        0.0,
    )
    return df


# ═══════════════════════════════════════════════════════════════════
# KPIs — before / after
# ═══════════════════════════════════════════════════════════════════

def compute_kpis(df_before_metrics: pd.DataFrame, df_post: pd.DataFrame, transfers: list) -> dict:
    active = df_before_metrics[df_before_metrics["amu"] > 0]
    total_active = len(active)
    available_count = int((active["available"] > 0).sum())
    availability_pct = round(available_count / total_active * 100, 1) if total_active else 0.0

    capital_lock_sar = round((df_before_metrics["extra_total"] * df_before_metrics["unit_price"]).sum(), 0)
    ne_reporting_sar = round(
        ((df_before_metrics["expired_qty"] + df_before_metrics["near_expiry_qty"])
         * df_before_metrics["unit_price"]).sum(), 0
    )

    by_cluster_before = {}
    for code, g in df_before_metrics.groupby("cluster"):
        act = g[g["amu"] > 0]
        avail_pct = round((act["available"] > 0).mean() * 100, 1) if len(act) else 0.0
        by_cluster_before[code] = {
            "availability_pct": avail_pct,
            "zero_stock": int((g["status"] == STATUS_OOS).sum()),
            "excess": int((g["status"] == STATUS_EXCESS).sum()),
            "capital_lock_sar": round((g["extra_total"] * g["unit_price"]).sum(), 0),
        }

    tf_df = pd.DataFrame(transfers) if transfers else pd.DataFrame()
    active_after = df_post[df_post["amu"] > 0]
    available_after_count = int((active_after["available_after"] > 0).sum())
    availability_after_pct = (
        round(available_after_count / len(active_after) * 100, 1) if len(active_after) else 0.0
    )
    capital_lock_after_sar = round((df_post["extra_total_after"] * df_post["unit_price"]).sum(), 0)

    cost_avoidance_sar = round(tf_df["Transfer Value (SAR)"].sum(), 0) if not tf_df.empty else 0.0
    skus_transferred = int(tf_df["NUPCO Code"].nunique()) if not tf_df.empty else 0
    total_transfer_qty = round(tf_df["Final Transfer Qty"].sum(), 0) if not tf_df.empty else 0.0

    by_cluster_after = {}
    for code, g in df_post.groupby("cluster"):
        act = g[g["amu"] > 0]
        avail_pct = round((act["available_after"] > 0).mean() * 100, 1) if len(act) else 0.0
        by_cluster_after[code] = {
            "availability_after_pct": avail_pct,
            "received_qty": round(g["received_qty"].sum(), 0),
            "received_value_sar": round(g["received_value"].sum(), 0),
        }

    return {
        "before": {
            "total_active": total_active,
            "available_count": available_count,
            "availability_pct": availability_pct,
            "capital_lock_sar": capital_lock_sar,
            "ne_reporting_sar": ne_reporting_sar,
            "by_cluster": by_cluster_before,
        },
        "after": {
            "availability_after_pct": availability_after_pct,
            "availability_lift_pp": round(availability_after_pct - availability_pct, 1),
            "capital_lock_after_sar": capital_lock_after_sar,
            "cost_avoidance_sar": cost_avoidance_sar,
            "skus_transferred": skus_transferred,
            "total_transfer_qty": total_transfer_qty,
            "transfer_lines": len(transfers),
            "wave1_lines": int(tf_df[tf_df["Wave"] == 1].shape[0]) if not tf_df.empty else 0,
            "wave2_lines": int(tf_df[tf_df["Wave"] == 2].shape[0]) if not tf_df.empty else 0,
            "by_cluster": by_cluster_after,
        },
    }


# ═══════════════════════════════════════════════════════════════════
# APP ENTRY POINT
#
# app.py's Stock Reallocation page imports this single function:
#   from src.agents.reallocation_agent import process_reallocation
# and expects back a dict shaped exactly like this — it feeds
# "kpi_before"/"kpi_after" straight into the KPI cards and "By
# Cluster" table, and "transfers" (a DataFrame) into the Transfer
# Flow Matrix, Network Map and Transfers detail table. Nothing in
# the validated logic above is changed — this only wires it
# together and reshapes the return value for the UI.
# ═══════════════════════════════════════════════════════════════════

def process_reallocation(
    df,
    coverage_threshold: float = 6.0,
    recv_coverage: float = 3.0,
    block_po: bool = True,
    min_transfer_value: float = 1000.0,
) -> dict:
    df_master = load_cluster_compiled(df)
    df_before_metrics = compute_metrics(df_master, coverage_threshold)

    wave_result = run_wave_reallocation(
        df_master,
        coverage_threshold=coverage_threshold,
        recv_coverage=recv_coverage,
        block_po=block_po,
        min_transfer_value=min_transfer_value,
    )
    transfers = wave_result["transfers"]

    df_post = compute_post_transfer(df_master, transfers, coverage_threshold)
    kpis = compute_kpis(df_before_metrics, df_post, transfers)

    transfers_df = pd.DataFrame(transfers) if transfers else pd.DataFrame(columns=[
        "Wave", "NUPCO Code", "Description", "Category", "Donor Cluster",
        "Receiver Cluster", "Distance (km)", "Donor Coverage (m)",
        "Receiver Available (before)", "Receiver AMU", "Receiver Need",
        "Total Supply (nupco/receiver)", "Final Transfer Qty",
        "Unit Price (SAR)", "Transfer Value (SAR)",
    ])

    return {
        "kpi_before": kpis["before"],
        "kpi_after": kpis["after"],
        "transfers": transfers_df,
        "pool_after": wave_result["pool_after"],
    }
