import logging
from src.utils.logger import setup_logger
from src.io.load_data import load_holdco, data_quality_report
from src.agents.decision_agent import run_decision_agent, generate_decision_summary

from src.agents.category_agent import run_category_agent

logger = logging.getLogger(__name__)


def run_pipeline(
    holdco_path: str,
    holdco_sheet: str = "Data ",
    output_path: str = "outputs/results.xlsx",
) -> dict:

    logger.info("=" * 50)
    logger.info("SUPPLY CHAIN AGENT — DÉMARRAGE")
    logger.info("=" * 50)

    # ÉTAPE 1 — Chargement
    logger.info("[1/3] Chargement des données...")
    df = load_holdco(holdco_path, sheet_name=holdco_sheet)
    quality = data_quality_report(df)

    # ÉTAPE 1.5 — Category agent
    logger.info("[1.5/3] Classification des catégories...")
    df = run_category_agent(df)

    # ÉTAPE 2 — Decision agent
    logger.info("[2/3] Calcul des décisions HOLDCO...")
    df = run_decision_agent(df)
    kpi = generate_decision_summary(df)

    logger.info(f"  ├─ OOS     : {kpi['oos_count']:,} items ({kpi['oos_pct']}%)")
    logger.info(f"  ├─ Risk    : {kpi['risk_count']:,} items")
    logger.info(f"  ├─ Optimum : {kpi['optimum_count']:,} items")
    logger.info(f"  ├─ Excess  : {kpi['excess_count']:,} items")
    logger.info(f"  └─ Valeur à commander : {kpi['total_value_to_order_sar']:,.0f} SAR")


    # ÉTAPE 3 — Export
    logger.info("[3/3] Export des résultats...")
    from src.io.export_results import export_to_excel
    export_to_excel(df, kpi, quality, output_path)

    logger.info("=" * 50)
    logger.info("PIPELINE TERMINÉ")
    logger.info("=" * 50)

    return {
        "df"            : df,
        "kpi_summary"   : kpi,
        "quality_report": quality,
    }
