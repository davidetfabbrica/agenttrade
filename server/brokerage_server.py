# server/brokerage_server.py
# ─────────────────────────────────────────────────────────────
# The brokerage server — the "seller" in the x402 flow.
#
# This is a Flask HTTP server exposing one endpoint:
#   POST /execute-trade
#
# The x402 flow it implements:
#   1. Agent sends a trade request with no payment
#   2. Server responds 402 with fee instructions and a nonce
#   3. Agent attaches payment proof and retries
#   4. Server verifies the signature and nonce, executes the trade
#   5. Server returns a trade confirmation
#
# Flask is a "micro-framework" — it gives you just enough to run
# an HTTP server without forcing a large amount of structure on you.
# It's widely used for APIs in fintech prototyping and internal tools.
# ─────────────────────────────────────────────────────────────

import hashlib
import json
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify

from shared.config import (
    TRADE_FEE,
    FEE_CURRENCY,
    BROKERAGE_WALLET_ADDRESS,
    AGENT_PRIVATE_KEY,
)
from data.market_prices import get_price

# ── Flask app setup ───────────────────────────────────────────
# Flask(__name__) creates the application object.
# __name__ tells Flask where to look for templates and resources.
# We don't use templates here, but it's always passed by convention.
app = Flask(__name__)

# ── Nonce store ───────────────────────────────────────────────
# A nonce (Number used ONCE) is a unique token issued per request.
# The server issues one inside the 402 response.
# The agent must include it in the payment proof.
# Once used, the server marks it as spent — any attempt to reuse
# the same nonce is rejected. This prevents replay attacks, where
# someone captures a valid payment and resubmits it to get free trades.
#
# Here we use a Python set stored in memory.
# In production this would be a database or Redis cache.
issued_nonces = set()    # Nonces the server has issued
used_nonces = set()      # Nonces that have already been spent


# ── Helper: generate a nonce ──────────────────────────────────
def generate_nonce() -> str:
    """
    Generates a unique one-time token using UUID4 (random UUID).
    UUIDs are 128-bit random numbers — collision probability is
    negligibly small for any practical use case.
    """
    nonce = str(uuid.uuid4())
    issued_nonces.add(nonce)
    return nonce


# ── Helper: verify payment signature ─────────────────────────
def verify_signature(payload: dict, received_signature: str) -> bool:
    """
    Verifies that the payment proof was signed by the legitimate agent.

    We recreate the signature using the same method the wallet used:
      hash(JSON payload + private key)

    If the result matches the received signature, the payment is valid.

    IMPORTANT NOTE FOR PORTFOLIO REVIEWERS:
    In production x402, the server would verify using the agent's
    PUBLIC key only — the private key never leaves the agent's wallet.
    This demo uses a shared secret (HMAC-style) for simplicity.
    Real implementations use ECDSA (Elliptic Curve Digital Signature
    Algorithm) as specified in the x402 protocol documentation.
    """
    # Recreate the exact string the wallet hashed
    payload_string = json.dumps(payload, sort_keys=True)
    raw = payload_string + AGENT_PRIVATE_KEY

    # Compute what the signature should be
    expected_signature = hashlib.sha256(raw.encode()).hexdigest()

    # Compare securely
    # Note: we use == here for simplicity. In production you would use
    # hmac.compare_digest() to prevent timing attacks — a real attack
    # where an adversary measures how long comparison takes to guess
    # the signature one character at a time.
    return received_signature == expected_signature


# ── Helper: validate trade request body ──────────────────────
def validate_trade_request(data: dict) -> tuple[bool, str]:
    """
    Checks that the incoming trade request contains the required fields
    and that the values are sensible.

    Returns a tuple: (is_valid, error_message)
    If valid: (True, "")
    If invalid: (False, "description of the problem")

    Never trust incoming data — always validate before using it.
    This is a core principle in any financial API.
    """
    required_fields = ["ticker", "direction", "quantity"]

    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: '{field}'"

    if data["direction"] not in ("BUY", "SELL"):
        return False, "Field 'direction' must be 'BUY' or 'SELL'"

    if not isinstance(data["quantity"], (int, float)) or data["quantity"] <= 0:
        return False, "Field 'quantity' must be a positive number"

    return True, ""


# ── Main endpoint: POST /execute-trade ────────────────────────
@app.route("/execute-trade", methods=["POST"])
def execute_trade():
    """
    The single endpoint the trading agent calls.

    @app.route tells Flask: "when a POST request arrives at
    /execute-trade, run this function".

    The function handles two distinct cases:
      Case A — no payment header present → return 402
      Case B — payment header present    → verify and execute trade
    """

    # Parse the JSON body from the incoming request.
    # silent=True means Flask returns None rather than crashing
    # if the body is not valid JSON.
    data = request.get_json(silent=True)

    if data is None:
        # Malformed request — not even valid JSON
        return jsonify({"error": "Request body must be valid JSON"}), 400

    # Validate the trade fields regardless of whether payment is included
    is_valid, error_message = validate_trade_request(data)
    if not is_valid:
        return jsonify({"error": error_message}), 400

    # ── Case A: No payment header — issue a 402 ───────────────
    # We check for the custom x402 payment header.
    # The header name follows the x402 protocol specification.
    payment_header = request.headers.get("X-Payment")

    if not payment_header:
        # Issue a fresh nonce for this request
        nonce = generate_nonce()

        # The 402 response body tells the agent exactly what to pay,
        # to whom, in what currency, and includes the nonce.
        # This structure mirrors the x402 protocol specification.
        payment_required_response = {
            "x402_version":  1,
            "status_code":   402,
            "message":       "Payment required to execute trade",
            "fee":           TRADE_FEE,
            "currency":      FEE_CURRENCY,
            "recipient":     BROKERAGE_WALLET_ADDRESS,
            "nonce":         nonce,
            "instructions":  (
                "Sign the payment payload and retry with the signature "
                "in the X-Payment header as a JSON string."
            ),
        }

        print(f"\n[Server] 402 issued for {data['direction']} "
              f"{data['quantity']} {data['ticker']} | Nonce: {nonce}")

        return jsonify(payment_required_response), 402

    # ── Case B: Payment header present — verify it ────────────
    # Parse the payment proof from the header.
    # The agent sends it as a JSON string.
    try:
        payment_proof = json.loads(payment_header)
    except json.JSONDecodeError:
        return jsonify({"error": "X-Payment header is not valid JSON"}), 400

    # Check the proof has the fields we expect
    if "payload" not in payment_proof or "signature" not in payment_proof:
        return jsonify({"error": "X-Payment header missing payload or signature"}), 400

    payload   = payment_proof["payload"]
    signature = payment_proof["signature"]

    # ── Nonce validation ──────────────────────────────────────
    nonce = payload.get("nonce")

    if not nonce:
        return jsonify({"error": "Payment payload missing nonce"}), 400

    if nonce not in issued_nonces:
        # Nonce was never issued by this server — reject
        return jsonify({"error": "Nonce not recognised"}), 400

    if nonce in used_nonces:
        # Nonce has already been spent — replay attack or duplicate request
        return jsonify({"error": "Nonce already used — possible replay attack"}), 400

    # ── Signature verification ────────────────────────────────
    if not verify_signature(payload, signature):
        return jsonify({"error": "Invalid payment signature"}), 401

    # ── Fee validation ────────────────────────────────────────
    if payload.get("fee") != TRADE_FEE:
        return jsonify({
            "error": f"Incorrect fee. Expected {TRADE_FEE}, received {payload.get('fee')}"
        }), 400

    if payload.get("recipient") != BROKERAGE_WALLET_ADDRESS:
        return jsonify({"error": "Payment recipient address does not match"}), 400

    # ── All checks passed — mark nonce as spent ───────────────
    # Do this before executing the trade. If anything fails after
    # this point, the nonce is still consumed. This is intentional —
    # it mirrors how blockchain transactions work: once broadcast,
    # they cannot be unsent.
    used_nonces.add(nonce)

    # ── Execute the mock trade ────────────────────────────────
    ticker    = data["ticker"].upper()
    direction = data["direction"]
    quantity  = data["quantity"]

    # Get the mock price — raises ValueError if ticker not found
    try:
        fill_price = get_price(ticker)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Calculate the total trade value
    trade_value = round(fill_price * quantity, 2)

    # Generate a unique trade reference number
    trade_ref = f"TRD-{str(uuid.uuid4())[:8].upper()}"

    # Build the confirmation response
    confirmation = {
        "status":      "FILLED",
        "trade_ref":   trade_ref,
        "ticker":      ticker,
        "direction":   direction,
        "quantity":    quantity,
        "fill_price":  fill_price,
        "trade_value": trade_value,
        "fee_paid":    TRADE_FEE,
        "currency":    FEE_CURRENCY,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "message":     f"Trade executed successfully. {direction} {quantity} "
                       f"{ticker} @ {fill_price} USD",
    }

    print(f"\n[Server] Trade FILLED ✓")
    print(f"[Server] Ref: {trade_ref} | {direction} {quantity} "
          f"{ticker} @ {fill_price} | Value: ${trade_value}")

    return jsonify(confirmation), 200


# ── Run the server ────────────────────────────────────────────
# This block only runs when you execute this file directly:
#   python server/brokerage_server.py
#
# debug=True means Flask will auto-reload if you change the code,
# and show detailed error pages. Never use debug=True in production.
if __name__ == "__main__":
    print("\n[Server] AgentTrade Brokerage Server starting...")
    print(f"[Server] Listening on http://127.0.0.1:5000")
    print(f"[Server] Trade fee: {TRADE_FEE} {FEE_CURRENCY} per execution\n")
    app.run(debug=True)