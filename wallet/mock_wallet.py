# wallet/mock_wallet.py
# ─────────────────────────────────────────────────────────────
# A simulated crypto wallet for the trading agent.
#
# In a real x402 system, the wallet would:
#   1. Hold actual USDC on a blockchain (e.g. Base, Ethereum)
#   2. Sign payment authorisations using a real private key
#      via elliptic curve cryptography (ECDSA)
#   3. Broadcast signed transactions to the network
#
# Here we simulate all three behaviours without touching a
# blockchain. The concepts — signing, balance checks,
# transaction logs — are identical to the real thing.
# ─────────────────────────────────────────────────────────────

import hashlib   # Built-in Python library for hashing
import json      # Built-in library for working with JSON data
import uuid      # Built-in library for generating unique IDs
from datetime import datetime, timezone  # For timestamping transactions

from shared.config import AGENT_STARTING_BALANCE, AGENT_PRIVATE_KEY


class MockWallet:
    """
    Simulates a crypto wallet that can sign payment authorisations
    and track a running balance.

    A class is the right structure here because a wallet has both
    data (balance, transaction history) and behaviour (sign, deduct).
    """

    def __init__(self):
        """
        Called automatically when you create a new MockWallet().
        Sets the starting balance and creates an empty transaction log.
        """
        self.balance = AGENT_STARTING_BALANCE
        self.transaction_log = []  # A list that grows with each payment

        print(f"[Wallet] Initialised with {self.balance:.2f} {' mock USDC'}")


    def has_sufficient_funds(self, amount: float) -> bool:
        """
        Returns True if the wallet has enough balance to cover the fee.
        We check this before attempting to sign — no point signing
        a payment we can't afford.
        """
        return self.balance >= amount


    def sign_payment(self, fee: float, currency: str,
                     recipient: str, nonce: str) -> dict:
        """
        Creates a signed payment authorisation.

        In real crypto, 'signing' means applying your private key to
        a hash of the payment data using ECDSA. The result proves you
        authorised this exact payment without revealing your private key.

        Here we simulate that by:
          1. Building a string from the payment details
          2. Hashing it together with the mock private key using SHA-256
          3. Using that hash as the 'signature'

        The server can verify this by performing the same hash and
        comparing the result — exactly as real signature verification works.

        fee:       the amount being paid
        currency:  e.g. "USDC"
        recipient: the brokerage wallet address
        nonce:     a one-time token from the server (prevents replay attacks)

        Returns a dictionary representing the payment proof.
        """

        if not self.has_sufficient_funds(fee):
            # Raise an exception rather than returning silently.
            # In trading systems, silent failures are dangerous.
            raise ValueError(
                f"[Wallet] Insufficient funds. "
                f"Balance: {self.balance:.2f}, Required: {fee:.2f}"
            )

        # Build the payload — the exact data we're authorising.
        # Every field matters. Changing any one of them produces a
        # completely different hash (that's the point of hashing).
        payment_payload = {
            "fee":       fee,
            "currency":  currency,
            "recipient": recipient,
            "nonce":     nonce,
        }

        # Convert the payload to a consistent string for hashing.
        # sort_keys=True ensures the order is always the same,
        # regardless of how Python internally stores the dictionary.
        payload_string = json.dumps(payment_payload, sort_keys=True)

        # Create the signature by hashing the payload + private key together.
        # SHA-256 produces a fixed 64-character hex string from any input.
        # We concatenate the private key so only someone with the key
        # can produce a valid signature — same principle as real crypto.
        raw = payload_string + AGENT_PRIVATE_KEY
        signature = hashlib.sha256(raw.encode()).hexdigest()

        # Build the complete payment proof that will be sent to the server.
        payment_proof = {
            "payload":   payment_payload,
            "signature": signature,
        }

        print(f"[Wallet] Payment signed. Fee: {fee} {currency} | Nonce: {nonce}")
        print(f"[Wallet] Signature: {signature[:20]}...") # Only show the start — it's long

        return payment_proof


    def deduct(self, amount: float, trade_ref: str) -> None:
        """
        Deducts a fee from the balance and records it in the transaction log.
        Only called after the server confirms the trade was successful.

        amount:    the fee amount to deduct
        trade_ref: the trade reference number, for the log
        """
        self.balance -= amount

        # Record the transaction with a timestamp.
        # This is the same pattern used in real ledger systems.
        log_entry = {
            "transaction_id": str(uuid.uuid4()),  # Unique ID for this log entry
            "trade_ref":      trade_ref,
            "amount_paid":    amount,
            "balance_after":  round(self.balance, 2),
            "timestamp":      datetime.now(timezone.utc).isoformat(),
        }

        self.transaction_log.append(log_entry)

        print(f"[Wallet] Deducted {amount} USDC. "
              f"Remaining balance: {self.balance:.2f} USDC")


    def print_statement(self) -> None:
        """
        Prints a summary of all transactions to the terminal.
        Useful for reviewing what the agent spent during a run.
        """
        print("\n[Wallet] ── Transaction Statement ──────────────────")
        if not self.transaction_log:
            print("[Wallet] No transactions recorded.")
        else:
            for entry in self.transaction_log:
                print(f"  {entry['timestamp']}  |  "
                      f"Trade: {entry['trade_ref']}  |  "
                      f"Paid: {entry['amount_paid']} USDC  |  "
                      f"Balance after: {entry['balance_after']} USDC")
        print(f"[Wallet] Current balance: {self.balance:.2f} USDC")
        print("[Wallet] ────────────────────────────────────────────\n")