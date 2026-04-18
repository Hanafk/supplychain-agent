import pandas as pd
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

HOLDCO_COLUMN_MAP = {
    "Region"                  : "region",
    "item_code"               : "item_code",
    "item_name"               : "item_name",
    "Category"                : "category",
    "Sub-Category"            : "sub_category",
    "contract_quantity"       : "contract_qty",
    "received_quantity"       : "received_qty",
    "tender_check"            : "tender_check",
    "SOH"                     : "soh",
    "nupco_monthly consumption": "consumption",
    "nupco_expired"           : "nupco_expired",
    "unit_price"              : "unit_price",
    # colonnes calculées — absentes dans raw.xlsx, notre agent les crée
    "request_qty"             : "request_qty",
    "Actual coverage"         : "actual_coverage",
    "Target coverage"         : "target_coverage",
}

def load_holdco(filepath: str, sheet_name: str = "Data ") -> pd.DataFrame:
    logger.info(f"Chargement HOLDCO depuis {filepath}")

    # 1. Lire l'Excel
    df = pd.read_excel(filepath, sheet_name=sheet_name, dtype=str)
    df.columns = df.columns.str.strip()

    # 2. Renommer les colonnes
    df.rename(columns=HOLDCO_COLUMN_MAP, inplace=True)

    # 3. Supprimer les lignes complètement vides
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # 4. Colonnes numériques à convertir
    for col in ["soh", "consumption", "unit_price", "request_qty",
                "target_coverage", "contract_qty", "received_qty"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 5. Règles nettoyage Phase 1
    df["soh"]           = df["soh"].fillna(0)
    df["consumption"]   = df["consumption"].fillna(0)
    df["nupco_expired"] = pd.to_numeric(
        df.get("nupco_expired", 0), errors="coerce"
    ).fillna(0)

    # 6. Colonnes optionnelles — si absentes on les crée
    for col in ["request_qty", "contract_qty", "received_qty"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0)

        # target_coverage : toujours forcer à 6 (valeur métier par défaut)
        df["target_coverage"] = 6.0

    # 7. Colonnes texte
    for col in ["region", "item_code", "item_name",
                "category", "sub_category", "tender_check"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    logger.info(f"{len(df)} lignes chargées")
    return df


def data_quality_report(df: pd.DataFrame, dataset_name: str = "HOLDCO") -> dict:
    report = {
        "dataset"          : dataset_name,
        "total_items"      : len(df),
        "missing_by_column": {},
        "anomalies"        : [],
    }

    # % manquant par colonne
    for col in df.columns:
        pct = df[col].isna().mean() * 100
        if pct > 0:
            report["missing_by_column"][col] = round(pct, 2)

    # Items sans prix
    if "unit_price" in df.columns:
        no_price = df["unit_price"].isna() | (df["unit_price"] <= 0)
        report["items_without_price"] = int(no_price.sum())
        if report["items_without_price"] > 0:
            report["anomalies"].append(
                f"{report['items_without_price']} items sans prix — à vérifier"
            )

    # Items sans consommation
    if "consumption" in df.columns:
        report["items_without_consumption"] = int((df["consumption"] == 0).sum())

    # Doublons
    if "item_code" in df.columns and "region" in df.columns:
        dupes = df.duplicated(subset=["item_code", "region"]).sum()
        report["duplicate_count"] = int(dupes)
        if dupes > 0:
            report["anomalies"].append(f"{dupes} doublons sur (item_code, region)")

    logger.info(f"Rapport qualité généré : {report['total_items']} items")
    return report
