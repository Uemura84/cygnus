from dataclasses import dataclass
from pathlib import Path
import os

# ---------------------------------------------------------------------------
# Directory layout — relative to this file (backend/)
# ---------------------------------------------------------------------------
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = BASE_DIR / "cache"

DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# Years to fetch from CVM open data portal
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]


@dataclass
class AppConfig:
    company_name: str = "BRASKEM S.A."
    company_cvm_code: str = "14191"
    language: str = "en"  # "en" | "pt-br"
    cache_mode: bool = False

    # Phase 2 preparation: all pipeline logic receives company as a parameter,
    # never reads it from a global — this config is only for defaults/display.


# Single in-memory config instance (single-user demo app)
app_config = AppConfig()


# In-memory pipeline state — holds the output of each completed step
pipeline_state: dict = {
    "step1": None,
    "step2": None,
    "step3": None,
    "step4": None,
    "step5": None,
    "step6": None,
    "step7": None,
    "step8": None,
}
