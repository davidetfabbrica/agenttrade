# data/market_prices.py
# ─────────────────────────────────────────────────────────────
# Mock market prices for a handful of well-known stocks.
# These are static — they don't change during a run.
#
# In a real system you would replace this with a call to a
# market data API (e.g. Yahoo Finance, Polygon.io).
# The rest of the code doesn't care — it just calls get_price().
# That means swapping in a real API later requires changing
# only this file. That's good design.
# ─────────────────────────────────────────────────────────────

# A dictionary mapping ticker symbols to mock prices in USD.
# Dictionary syntax in Python: { "KEY": VALUE, ... }
MOCK_PRICES = {
    "AAPL":  307.87,
    "GOOGL":  366.33,
    "MSFT":  415.29,
    "NVDA":  205.37,
    "BRK.B":  487.56,
}


def get_price(ticker: str) -> float:
    """
    Returns the mock price for a given ticker symbol.

    ticker: a string like "AAPL" or "TSLA"

    Raises a ValueError if the ticker is not in our mock data.
    This is deliberate — we never want to silently return a
    wrong price in a trading context.
    """
    ticker = ticker.upper()  # Normalise to uppercase so "aapl" and "AAPL" both work

    if ticker not in MOCK_PRICES:
        raise ValueError(f"Ticker '{ticker}' not found in mock price data.")

    return MOCK_PRICES[ticker]


def list_available_tickers() -> list:
    """
    Returns a list of all available ticker symbols.
    Useful for the agent to know what it can trade.
    """
    return list(MOCK_PRICES.keys())