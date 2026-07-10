"""
Entity resolution — maps company name variants to canonical tickers.

Used by the LLM extractor to normalise names extracted from unstructured text
before they are written to extracted_edges.json or compared against the graph.

Extend ALIAS_TABLE as new name variants appear in extraction runs.
"""

# ---------------------------------------------------------------------------
# Alias table — name variant (lowercase) → canonical ticker
# ---------------------------------------------------------------------------

ALIAS_TABLE: dict[str, str] = {
    # NVIDIA
    "nvidia": "NVDA",
    "nvidia corporation": "NVDA",
    "nvidia corp": "NVDA",

    # AMD
    "amd": "AMD",
    "advanced micro devices": "AMD",
    "advanced micro devices inc": "AMD",
    "advanced micro devices, inc.": "AMD",

    # Intel
    "intel": "INTC",
    "intel corporation": "INTC",
    "intel corp": "INTC",

    # Microsoft
    "microsoft": "MSFT",
    "microsoft corporation": "MSFT",
    "microsoft corp": "MSFT",

    # Alphabet / Google
    "alphabet": "GOOGL",
    "alphabet inc": "GOOGL",
    "alphabet inc.": "GOOGL",
    "google": "GOOGL",
    "google llc": "GOOGL",
    "google cloud": "GOOGL",
    "deepmind": "GOOGL",
    "google deepmind": "GOOGL",

    # Amazon
    "amazon": "AMZN",
    "amazon.com": "AMZN",
    "amazon.com inc": "AMZN",
    "amazon web services": "AMZN",
    "aws": "AMZN",

    # Meta
    "meta": "META",
    "meta platforms": "META",
    "meta platforms inc": "META",
    "facebook": "META",

    # Apple
    "apple": "AAPL",
    "apple inc": "AAPL",
    "apple inc.": "AAPL",

    # Palantir
    "palantir": "PLTR",
    "palantir technologies": "PLTR",

    # Snowflake
    "snowflake": "SNOW",
    "snowflake inc": "SNOW",

    # Salesforce
    "salesforce": "CRM",
    "salesforce inc": "CRM",
    "salesforce.com": "CRM",

    # ServiceNow
    "servicenow": "NOW",
    "service now": "NOW",

    # Oracle
    "oracle": "ORCL",
    "oracle corporation": "ORCL",
    "oracle corp": "ORCL",

    # Cloudflare
    "cloudflare": "NET",
    "cloudflare inc": "NET",

    # MongoDB
    "mongodb": "MDB",
    "mongodb inc": "MDB",

    # Elastic
    "elastic": "ESTC",
    "elastic nv": "ESTC",

    # Broadcom
    "broadcom": "AVGO",
    "broadcom inc": "AVGO",
    "broadcom corporation": "AVGO",

    # TSMC
    "tsmc": "TSM",
    "taiwan semiconductor": "TSM",
    "taiwan semiconductor manufacturing": "TSM",
    "taiwan semiconductor manufacturing company": "TSM",

    # Qualcomm
    "qualcomm": "QCOM",
    "qualcomm incorporated": "QCOM",
    "qualcomm inc": "QCOM",

    # Workday
    "workday": "WDAY",
    "workday inc": "WDAY",
    "workday inc.": "WDAY",

    # Pass-through — already a ticker
    "nvda": "NVDA", "amd": "AMD", "intc": "INTC", "msft": "MSFT",
    "googl": "GOOGL", "amzn": "AMZN", "meta": "META", "aapl": "AAPL",
    "pltr": "PLTR", "snow": "SNOW", "crm": "CRM", "now": "NOW",
    "orcl": "ORCL", "net": "NET", "mdb": "MDB", "estc": "ESTC",
    "avgo": "AVGO", "tsm": "TSM", "qcom": "QCOM", "wday": "WDAY",
}

# Known tickers (for quick membership checks)
KNOWN_TICKERS: frozenset[str] = frozenset(ALIAS_TABLE.values())

# Reverse index — ticker -> every known name variant (lowercase), including
# the ticker itself. Used to check whether a ticker is "mentioned" in free
# text that more naturally refers to the company by name (e.g. "Nvidia"
# rather than "NVDA").
TICKER_TO_ALIASES: dict[str, frozenset[str]] = {
    ticker: frozenset(name for name, t in ALIAS_TABLE.items() if t == ticker)
    for ticker in KNOWN_TICKERS
}


def aliases_for(ticker: str) -> frozenset[str]:
    """All known lowercase name variants for a canonical ticker (including itself)."""
    return TICKER_TO_ALIASES.get(ticker.strip().upper(), frozenset({ticker.strip().lower()}))


def resolve(name: str) -> str | None:
    """
    Map a company name or ticker variant to a canonical ticker.
    Returns None if the name is not recognised.
    """
    return ALIAS_TABLE.get(name.strip().lower())


def resolve_or_keep(name: str) -> str:
    """
    Resolve a name to a ticker, or return the original string uppercased
    if it looks like a ticker already (2-5 uppercase letters).
    Falls back to the original string if neither matches.
    """
    hit = resolve(name)
    if hit:
        return hit
    stripped = name.strip()
    if stripped.isupper() and 2 <= len(stripped) <= 5:
        return stripped
    return name


def is_known(ticker: str) -> bool:
    return ticker in KNOWN_TICKERS


if __name__ == "__main__":
    samples = [
        "Google", "AWS", "Meta Platforms", "Advanced Micro Devices",
        "Broadcom Inc", "AAPL", "unknown corp", "DeepMind",
    ]
    for s in samples:
        print(f"  {s!r:35s} → {resolve(s)!r}")
