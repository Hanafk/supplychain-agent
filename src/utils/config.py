from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent

class Config:
    # Chemins des fichiers
    HOLDCO_PATH  = str(BASE_DIR / "data" / "raw.xlsx")
    TRANSFER_PATH = str(BASE_DIR / "data" / "Extra_Stock_Transfer.xlsx")
    OUTPUT_PATH  = str(BASE_DIR / "outputs" / "results.xlsx")

    # Noms des onglets Excel
    HOLDCO_SHEET  = "Data "
    QASSIM_SHEET  = "Qassim transfer"
    R2_SHEET      = "R2"
    E1_SHEET      = "Shortage E1"

    # Règles métier (modifiables sans toucher au code)
    TARGET_COVERAGE_DEFAULT = 6   # mois
    REALLOCATION_THRESHOLD  = 7   # mois — Qassim garde ce seuil
    TRANSFER_CAP_MONTHS     = 3   # max mois à transférer par destination
