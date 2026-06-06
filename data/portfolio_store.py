# data/portfolio_store.py
# ─────────────────────────────────────────────────────────────
# In-memory portfolio store.
#
# Tracks the agent's holdings as trades are executed.
# Each filled trade updates the position for that ticker.
#
# In a real system this would be a database. Here we use a
# plain Python dictionary — the structure is identical, just
# not persisted between runs.
# ─────────────────────────────────────────────────────────────


# Holdings is a dictionary keyed by ticker symbol.
# Each entry records the net quantity held and average cost.
#
# Structure:
# {
#   "AAPL": { "quantity": 10, "avg_price": 189.45, "direction": "LONG" },
#   "TSLA": { "quantity": -20, "avg_price": 172.30, "direction": "SHORT" },
# }
_holdings: dict = {}


def update_position(ticker: str, direction: str,
                    quantity: float, fill_price: float) -> None:
    """
    Updates the portfolio when a trade is filled.

    BUY increases the position (positive quantity = long).
    SELL decreases it (negative quantity = short).

    ticker:     stock ticker, e.g. "AAPL"
    direction:  "BUY" or "SELL"
    quantity:   number of shares traded
    fill_price: the price the trade was filled at
    """
    ticker = ticker.upper()

    # Determine signed quantity — negative for a SELL
    signed_qty = quantity if direction == "BUY" else -quantity

    if ticker not in _holdings:
        # First trade in this ticker — initialise the position
        _holdings[ticker] = {
            "quantity":  signed_qty,
            "avg_price": fill_price,
        }
    else:
        # Update existing position
        existing = _holdings[ticker]
        new_quantity = existing["quantity"] + signed_qty

        if new_quantity == 0:
            # Position fully closed — remove it from holdings
            del _holdings[ticker]
            return

        # Recalculate average price weighted by quantity.
        # This is the standard cost-basis calculation used in
        # portfolio accounting: (old_value + new_value) / total_qty
        old_value = existing["quantity"] * existing["avg_price"]
        new_value = signed_qty * fill_price
        _holdings[ticker]["avg_price"] = round(
            abs(old_value + new_value) / abs(new_quantity), 4
        )
        _holdings[ticker]["quantity"] = new_quantity


def get_portfolio() -> dict:
    """
    Returns the current portfolio holdings with a direction label.

    Adds a human-readable direction: LONG (net positive quantity)
    or SHORT (net negative quantity).
    """
    portfolio = {}

    for ticker, position in _holdings.items():
        portfolio[ticker] = {
            "quantity":  position["quantity"],
            "avg_price": position["avg_price"],
            "direction": "LONG" if position["quantity"] > 0 else "SHORT",
            "market_value": round(
                abs(position["quantity"]) * position["avg_price"], 2
            ),
        }

    return portfolio


def get_position_count() -> int:
    """Returns the number of open positions."""
    return len(_holdings)