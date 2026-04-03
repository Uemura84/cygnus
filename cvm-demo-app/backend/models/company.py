from dataclasses import dataclass


@dataclass
class Company:
    id: str                          # unique identifier (CVM code, SEC CIK, internal ID)
    name: str                        # display name ("BRASKEM S.A.")
    source: str                      # data source identifier ("cvm", "sec", "erp", "manual")
    country: str                     # ISO country code ("BR", "US")
    currency: str                    # reporting currency ("BRL", "USD")
    sector: str | None = None        # sector classification if known
    sector_source: str = "unknown"   # "mapped" | "inferred" | "unknown"
