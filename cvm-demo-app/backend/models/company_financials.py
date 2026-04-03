from dataclasses import dataclass, field
from datetime import date, datetime
from .company import Company
from .financial_statements import IncomeStatement, BalanceSheet, CashFlow


@dataclass
class CompanyFinancials:
    """The output of any source adapter. This is the input to the analysis engine."""

    company: Company
    income_statements: list[IncomeStatement]          # sorted by period date
    balance_sheets: list[BalanceSheet] | None = None  # None if source doesn't provide
    cash_flows: list[CashFlow] | None = None          # None if source doesn't provide

    # Metadata
    source: str = ""
    source_version: str = ""
    extraction_date: datetime = field(default_factory=datetime.now)
    period_range: tuple[date, date] | None = None
    granularity: list[str] = field(default_factory=list)
    data_completeness: dict = field(default_factory=dict)


def determine_active_modules(financials: "CompanyFinancials") -> list[str]:
    """Return the list of analysis modules that can run based on available data.

    Module gating rules:
      - profitability     : requires ≥ 4 income statements
      - balance_sheet_health : requires ≥ 4 balance sheets (Sprint 3)
      - cash_flow_quality    : requires ≥ 4 cash flow statements (Sprint 3)

    In Sprint 1, this always returns ["profitability"] only, since balance_sheets
    and cash_flows are None. The gating mechanism is in place for Sprints 3 and 4.
    """
    active: list[str] = []

    if financials.income_statements and len(financials.income_statements) >= 4:
        active.append("profitability")

    if financials.balance_sheets is not None and len(financials.balance_sheets) >= 4:
        active.append("balance_sheet_health")

    if financials.cash_flows is not None and len(financials.cash_flows) >= 4:
        active.append("cash_flow_quality")

    return active
