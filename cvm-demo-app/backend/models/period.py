from dataclasses import dataclass
from datetime import date


@dataclass
class Period:
    date: date                           # period end date (2025-12-31)
    granularity: str                     # "annual" | "quarterly" | "monthly"
    fiscal_year: int                     # 2025
    fiscal_quarter: int | None = None    # 1-4 for quarterly, None for annual
    fiscal_month: int | None = None      # 1-12 for monthly, None otherwise
    is_standalone: bool = True           # True = standalone period, False = YTD cumulative
    filing_type: str | None = None       # Source-specific: "DFP", "ITR", "10-K", "10-Q", etc.
