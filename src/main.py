import sys
from pathlib import Path

# Ajoute la racine du projet au path Python
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger import setup_logger
from src.utils.config import Config
from src.pipeline import run_pipeline

setup_logger()

if __name__ == "__main__":
    cfg = Config()

    results = run_pipeline(
        holdco_path=cfg.HOLDCO_PATH,
        holdco_sheet=cfg.HOLDCO_SHEET,
        output_path=cfg.OUTPUT_PATH,
    )

    kpi = results["kpi_summary"]

    print("\n" + "=" * 45)
    print("   SUPPLY CHAIN AGENT — RÉSULTATS")
    print("=" * 45)
    print(f"  Total items      : {kpi['total_items']:,}")
    print(f"  🔴 OOS           : {kpi['oos_count']:,} ({kpi['oos_pct']}%)")
    print(f"  🟠 Risk          : {kpi['risk_count']:,}")
    print(f"  🟢 Optimum       : {kpi['optimum_count']:,}")
    print(f"  🟡 Excess        : {kpi['excess_count']:,}")
    print("-" * 45)
    print(f"  Valeur à commander : {kpi['total_value_to_order_sar']:,.0f} SAR")
    print(f"  Coverage moyen     : {kpi['avg_actual_coverage']} mois")
    print("=" * 45)
    print(f"  Output : {cfg.OUTPUT_PATH}")
    print("=" * 45 + "\n")
