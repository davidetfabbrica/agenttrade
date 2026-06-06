# data/market_prices.py
# ─────────────────────────────────────────────────────────────
# Market price data module.
#
# Fetches real prices from Yahoo Finance via yfinance.
# Includes a session cache so each ticker is only fetched once
# per server run — this avoids Yahoo Finance rate limiting,
# which triggers when too many requests arrive in quick succession.
#
# If a live price cannot be fetched, the module falls back to
# static prices so the demo still runs cleanly.
# ─────────────────────────────────────────────────────────────

import time
import yfinance as yf

# Tickers the agent is allowed to trade
SUPPORTED_TICKERS = ["AAPL", "TSLA", "MSFT", "NVDA", "AMZN"]

# Fallback static prices used if Yahoo Finance is unavailable
FALLBACK_PRICES = {
    "AAPL":  189.45,
    "TSLA":  172.30,
    "MSFT":  415.20,
    "NVDA":  875.60,
    "AMZN":  198.10,
}

# Session cache — populated on first fetch, reused thereafter.
# Keyed by ticker symbol, value is the price as a float.
# This means Yahoo Finance is called at most once per ticker
# per server run, regardless of how many trades are placed.
_price_cache: dict = {}


def get_price(ticker: str) -> float:
    """
    Returns the most recent closing price for a given ticker.

    Checks the session cache first. If not cached, fetches from
    Yahoo Finance and stores the result. Falls back to static
    prices if Yahoo Finance is rate limiting or unavailable.

    ticker: a string like "AAPL" or "TSLA"
    """
    ticker = ticker.upper()

    if ticker not in SUPPORTED_TICKERS:
        raise ValueError(
            f"Ticker '{ticker}' is not supported. "
            f"Supported tickers: {', '.join(SUPPORTED_TICKERS)}"
        )

    # Return cached price if we already have it
    if ticker in _price_cache:
        return _price_cache[ticker]

    # Small delay before each fresh Yahoo Finance request.
    # Spacing requests reduces the chance of hitting rate limits.
    time.sleep(0.5)

    try:
        stock = yf.Ticker(ticker)
        price = stock.fast_info.last_price

        if price is None or price <= 0:
            raise ValueError("No valid price returned")

        price = round(float(price), 2)
        _price_cache[ticker] = price  # Store in cache
        print(f"[Prices] Fetched {ticker}: ${price} (live)")
        return price

    except Exception as e:
        # Fall back to static price rather than crashing the demo
        if ticker in FALLBACK_PRICES:
            fallback = FALLBACK_PRICES[ticker]
            _price_cache[ticker] = fallback  # Cache the fallback too
            print(f"[Prices] Could not fetch {ticker} ({str(e)[:50]}). "
                  f"Using fallback: ${fallback}")
            return fallback

        raise ValueError(
            f"Failed to fetch price for '{ticker}' and no fallback available."
        )


def list_available_tickers() -> list:
    """Returns the list of supported ticker symbols."""
    return SUPPORTED_TICKERS.copy()