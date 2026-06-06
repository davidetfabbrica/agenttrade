# agent/trading_agent.py
# ─────────────────────────────────────────────────────────────
# The autonomous trading agent.
#
# This agent decides what to trade, handles the x402 payment
# flow automatically, and logs the result.
#
# "Autonomous" here means: it handles the 402 response and
# retries without any human involvement. That's the core idea
# behind agentic payments — the agent acts on its own behalf.
#
# Flow:
#   1. Build a trade order
#   2. POST it to the brokerage server
#   3. If 402 received → sign payment → retry with proof
#   4. If 200 received → log the confirmed trade
#   5. If anything else → handle the error cleanly
# ─────────────────────────────────────────────────────────────

import json
import requests  # The standard Python HTTP library

from shared.config import (
    BROKERAGE_URL,
    TRADE_ENDPOINT,
    TRADE_FEE,
    FEE_CURRENCY,
    BROKERAGE_WALLET_ADDRESS,
    MAX_RETRIES,
)
from wallet.mock_wallet import MockWallet


def execute_trade(ticker: str, direction: str, quantity: float,
                  wallet: MockWallet) -> dict | None:
    """
    Attempts to execute a single trade via the brokerage server.

    Handles the full x402 payment flow automatically:
      - First attempt has no payment header
      - On 402, signs the payment and retries
      - On 200, returns the trade confirmation
      - On any other status, raises an error

    ticker:    stock ticker symbol, e.g. "AAPL"
    direction: "BUY" or "SELL"
    quantity:  number of shares
    wallet:    the agent's MockWallet instance

    Returns the trade confirmation dict on success, or None on failure.
    """

    url = BROKERAGE_URL + TRADE_ENDPOINT

    # The trade order — this is the body of every request we send.
    # It stays the same whether or not we include a payment header.
    trade_order = {
        "ticker":    ticker.upper(),
        "direction": direction.upper(),
        "quantity":  quantity,
    }

    print(f"\n[Agent] ── New Trade Order ──────────────────────────")
    print(f"[Agent] {direction.upper()} {quantity} {ticker.upper()}")
    print(f"[Agent] Sending to: {url}")

    # We attempt the request up to MAX_RETRIES times.
    # In practice the flow is: attempt 1 → 402 → attempt 2 → 200.
    # MAX_RETRIES guards against infinite loops if something goes wrong.
    for attempt in range(1, MAX_RETRIES + 1):

        print(f"\n[Agent] Attempt {attempt} of {MAX_RETRIES}")

        # On the first attempt we send no payment header.
        # On subsequent attempts we attach the signed payment proof.
        # The headers dict starts empty and we add to it if needed.
        headers = {"Content-Type": "application/json"}

        # ── Attempt the request ───────────────────────────────
        try:
            response = requests.post(url, json=trade_order, headers=headers)
        except requests.exceptions.ConnectionError:
            # The server isn't running or isn't reachable.
            # This is a clear, actionable error message.
            print(f"[Agent] ERROR: Could not connect to {url}")
            print(f"[Agent] Is the brokerage server running?")
            return None

        print(f"[Agent] Server responded with status: {response.status_code}")

        # ── Handle 402: Payment Required ─────────────────────
        if response.status_code == 402:

            payment_instructions = response.json()
            nonce     = payment_instructions["nonce"]
            fee       = payment_instructions["fee"]
            currency  = payment_instructions["currency"]
            recipient = payment_instructions["recipient"]

            print(f"[Agent] 402 received. Fee required: {fee} {currency}")
            print(f"[Agent] Recipient: {recipient}")
            print(f"[Agent] Nonce: {nonce}")

            # Check the wallet can cover the fee before attempting to sign.
            if not wallet.has_sufficient_funds(fee):
                print(f"[Agent] Insufficient funds to pay fee. "
                      f"Balance: {wallet.balance:.2f}, Required: {fee}")
                return None

            # Sign the payment using the wallet.
            # This produces the payment proof we'll attach to the retry.
            payment_proof = wallet.sign_payment(
                fee=fee,
                currency=currency,
                recipient=recipient,
                nonce=nonce,
            )

            # Serialise the payment proof to a JSON string.
            # HTTP headers must be strings — we can't send a dict directly.
            headers["X-Payment"] = json.dumps(payment_proof)

            print(f"[Agent] Payment proof attached to X-Payment header.")
            print(f"[Agent] Retrying request with payment...")

            # Retry the request with the payment header attached.
            try:
                response = requests.post(url, json=trade_order, headers=headers)
            except requests.exceptions.ConnectionError:
                print(f"[Agent] ERROR: Lost connection on retry.")
                return None

            print(f"[Agent] Server responded with status: {response.status_code}")

        # ── Handle 200: Trade Confirmed ───────────────────────
        if response.status_code == 200:

            confirmation = response.json()

            # Deduct the fee from the wallet now that we have confirmation.
            # We only deduct on confirmed success — never speculatively.
            wallet.deduct(TRADE_FEE, confirmation["trade_ref"])

            print(f"\n[Agent] ── Trade Confirmed ✓ ─────────────────────────")
            print(f"[Agent] Reference:   {confirmation['trade_ref']}")
            print(f"[Agent] Status:      {confirmation['status']}")
            print(f"[Agent] {confirmation['direction']} "
                  f"{confirmation['quantity']} "
                  f"{confirmation['ticker']} "
                  f"@ ${confirmation['fill_price']}")
            print(f"[Agent] Trade value: ${confirmation['trade_value']}")
            print(f"[Agent] Fee paid:    {confirmation['fee_paid']} "
                  f"{confirmation['currency']}")
            print(f"[Agent] Timestamp:   {confirmation['timestamp']}")

            return confirmation

        # ── Handle anything else ──────────────────────────────
        # 400 = bad request (our fault), 401 = bad signature,
        # 500 = server error. Log the detail and stop.
        if response.status_code not in (200, 402):
            error_detail = response.json().get("error", "Unknown error")
            print(f"[Agent] ERROR {response.status_code}: {error_detail}")
            return None

    # If we exit the loop without returning, all retries were exhausted.
    print(f"[Agent] Failed to complete trade after {MAX_RETRIES} attempts.")
    return None


# ── Main: run the agent ───────────────────────────────────────
# This block runs when you execute:
#   python -m agent.trading_agent
#
# It places three trades in sequence so you can watch the wallet
# balance deplete and see the full flow repeated.

def fetch_portfolio(wallet: MockWallet) -> dict | None:
    """
    Requests the agent's current portfolio from the brokerage server.
    Handles the x402 payment flow identically to execute_trade.

    wallet: the agent's MockWallet instance

    Returns the portfolio dict on success, or None on failure.
    """
    url = BROKERAGE_URL + "/portfolio"

    print(f"\n[Agent] ── Portfolio Request ─────────────────────────")
    print(f"[Agent] Sending to: {url}")

    for attempt in range(1, MAX_RETRIES + 1):

        print(f"\n[Agent] Attempt {attempt} of {MAX_RETRIES}")

        headers = {"Content-Type": "application/json"}

        try:
            response = requests.get(url, headers=headers)
        except requests.exceptions.ConnectionError:
            print(f"[Agent] ERROR: Could not connect to {url}")
            return None

        print(f"[Agent] Server responded with status: {response.status_code}")

        # ── Handle 402 ────────────────────────────────────────
        if response.status_code == 402:

            payment_instructions = response.json()
            nonce     = payment_instructions["nonce"]
            fee       = payment_instructions["fee"]
            currency  = payment_instructions["currency"]
            recipient = payment_instructions["recipient"]

            print(f"[Agent] 402 received. Fee required: {fee} {currency}")

            if not wallet.has_sufficient_funds(fee):
                print(f"[Agent] Insufficient funds. "
                      f"Balance: {wallet.balance:.2f}, Required: {fee}")
                return None

            payment_proof = wallet.sign_payment(
                fee=fee,
                currency=currency,
                recipient=recipient,
                nonce=nonce,
            )

            headers["X-Payment"] = json.dumps(payment_proof)

            print(f"[Agent] Payment proof attached. Retrying...")

            try:
                response = requests.get(url, headers=headers)
            except requests.exceptions.ConnectionError:
                print(f"[Agent] ERROR: Lost connection on retry.")
                return None

            print(f"[Agent] Server responded with status: {response.status_code}")

        # ── Handle 200 ────────────────────────────────────────
        if response.status_code == 200:

            data = response.json()

            # Portfolio queries cost half the trade fee
            portfolio_fee = round(TRADE_FEE / 2, 2)
            wallet.deduct(portfolio_fee, "PORTFOLIO-QUERY")

            print(f"\n[Agent] ── Portfolio Retrieved ✓ ──────────────────────")
            print(f"[Agent] Open positions: {data['positions']}")

            if data["positions"] == 0:
                print(f"[Agent] No open positions.")
            else:
                for ticker, pos in data["holdings"].items():
                    print(f"[Agent]   {ticker:6} | {pos['direction']:5} | "
                          f"Qty: {pos['quantity']:>8} | "
                          f"Avg: ${pos['avg_price']:>8.2f} | "
                          f"Value: ${pos['market_value']:>10.2f}")

            print(f"[Agent] Fee paid: {data['fee_paid']} {data['currency']}")
            return data

        if response.status_code not in (200, 402):
            error_detail = response.json().get("error", "Unknown error")
            print(f"[Agent] ERROR {response.status_code}: {error_detail}")
            return None

    print(f"[Agent] Failed to retrieve portfolio after {MAX_RETRIES} attempts.")
    return None

if __name__ == "__main__":

    print("═" * 55)
    print("  AgentTrade — x402 Agentic Payment Demo")
    print("═" * 55)

    # Create one wallet instance shared across all trades.
    # The balance persists between trades within this run.
    wallet = MockWallet()

    # Define a small batch of trades to execute.
    # Each is a tuple of (ticker, direction, quantity).
    trades = [
        ("AAPL",  "BUY",  10),
        ("NVDA",  "BUY",   5),
        ("TSLA",  "SELL",  20),
    ]

    results = []

    for ticker, direction, quantity in trades:
        result = execute_trade(ticker, direction, quantity, wallet)
        if result:
            results.append(result)
# Fetch the portfolio after all trades are complete
    fetch_portfolio(wallet)
    # Print the wallet statement at the end to show all fees paid.
    wallet.print_statement()

    # Summary
    print("═" * 55)
    print(f"  Trades attempted:  {len(trades)}")
    print(f"  Trades confirmed:  {len(results)}")
    print(f"  Total fees paid:   "
          f"{len(results) * TRADE_FEE} {FEE_CURRENCY}")
    print(f"  Wallet balance:    {wallet.balance:.2f} {FEE_CURRENCY}")
    print("═" * 55)