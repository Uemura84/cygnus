from dataclasses import dataclass
from .period import Period


@dataclass
class IncomeStatement:
    company_id: str
    period: Period

    # Revenue
    revenue: float | None = None
    cost_of_goods_sold: float | None = None     # positive = cost, stored as absolute value
    gross_profit: float | None = None

    # Operating expenses
    sga_expenses: float | None = None
    selling_expenses: float | None = None
    general_admin: float | None = None
    other_operating: float | None = None

    # Operating profit
    ebit: float | None = None
    depreciation_amortization: float | None = None  # D&A — sourced from DFC in CVM
    ebitda: float | None = None

    # Below the line
    financial_result: float | None = None
    income_before_tax: float | None = None
    income_tax: float | None = None
    net_income: float | None = None

    # Derived ratios (computed by Step 4, not stored by adapter)
    gross_margin_pct: float | None = None
    ebit_margin_pct: float | None = None
    ebitda_margin_pct: float | None = None
    cogs_pct_revenue: float | None = None
    sga_pct_revenue: float | None = None


@dataclass
class BalanceSheet:
    company_id: str
    period: Period

    # Assets
    total_assets: float | None = None
    current_assets: float | None = None
    cash_and_equivalents: float | None = None
    accounts_receivable: float | None = None
    inventories: float | None = None
    non_current_assets: float | None = None
    property_plant_equipment: float | None = None
    intangible_assets: float | None = None

    # Liabilities
    total_liabilities: float | None = None
    current_liabilities: float | None = None
    accounts_payable: float | None = None
    short_term_debt: float | None = None
    non_current_liabilities: float | None = None
    long_term_debt: float | None = None

    # Equity
    total_equity: float | None = None
    retained_earnings: float | None = None

    # Derived metrics (computed by Step 4) — all None until Sprint 3
    net_debt: float | None = None
    working_capital: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    debt_to_ebitda: float | None = None
    receivable_days: float | None = None
    inventory_days: float | None = None
    payable_days: float | None = None
    cash_conversion_cycle: float | None = None
    return_on_assets: float | None = None
    return_on_equity: float | None = None
    asset_turnover: float | None = None


@dataclass
class CashFlow:
    company_id: str
    period: Period

    # Operating
    operating_cash_flow: float | None = None
    depreciation_amortization: float | None = None
    working_capital_change: float | None = None
    other_operating: float | None = None

    # Investing
    investing_cash_flow: float | None = None
    capex: float | None = None
    acquisitions: float | None = None
    other_investing: float | None = None

    # Financing
    financing_cash_flow: float | None = None
    debt_issuance: float | None = None
    debt_repayment: float | None = None
    dividends_paid: float | None = None
    equity_issuance: float | None = None
    other_financing: float | None = None

    # Derived metrics (computed by Step 4) — all None until Sprint 3
    free_cash_flow: float | None = None
    ocf_to_net_income: float | None = None
    capex_to_revenue: float | None = None
    capex_to_depreciation: float | None = None
