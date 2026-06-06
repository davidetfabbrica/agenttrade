# wallet/mock_wallet.py
# ─────────────────────────────────────────────────────────────
# Simulated crypto wallet using real ECDSA signing.
#
# Previously used HMAC-style signing (SHA256 + shared secret).
# This version uses proper public/private key cryptography:
#
#   - The private key signs payment authorisations
#   - The public key (shared with the server) verifies them
#   - The private key never leaves this file
#
# This matches how real x402 wallets work — the server only
# ever needs the public key to verify a payment.
# ─────────────────────────────────────────────────────────────

import json
import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature
)
from cryptography.hazmat.primitives import hashes, serialization
import base64

from shared.config import (
    AGENT_STARTING_BALANCE,
    AGENT_PRIVATE_KEY_PEM,
)


class MockWallet:
    """
    A wallet that signs payment authorisations using ECDSA.
    The private key signs; the server verifies with the public key.
    """

    def __init__(self):
        self.balance = AGENT_STARTING_BALANCE
        self.transaction_log = []

        # Load the private key from PEM format
        # This happens once at startup — not on every signing operation
        self._private_key = serialization.load_pem_private_key(
            AGENT_PRIVATE_KEY_PEM.strip().encode(),
            password=None,
        )

        print(f"[Wallet] Initialised with {self.balance:.2f} mock USDC")
        print(f"[Wallet] ECDSA signing active (SECP256K1)")


    def has_sufficient_funds(self, amount: float) -> bool:
        """Returns True if the wallet balance covers the fee."""
        return self.balance >= amount


    def sign_payment(self, fee: float, currency: str,
                     recipient: str, nonce: str) -> dict:
        """
        Signs a payment authorisation using ECDSA with the private key.

        The signature is produced by:
          1. Building a canonical JSON string of the payment payload
          2. Signing it with the private key using ECDSA + SHA256
          3. Encoding the signature as base64 for safe transport in headers

        The server verifies using only the public key —
        the private key is never transmitted.

        Returns a dict containing the payload and the base64 signature.
        """
        if not self.has_sufficient_funds(fee):
            raise ValueError(
                f"[Wallet] Insufficient funds. "
                f"Balance: {self.balance:.2f}, Required: {fee:.2f}"
            )

        payment_payload = {
            "fee":       fee,
            "currency":  currency,
            "recipient": recipient,
            "nonce":     nonce,
        }

        # Canonical JSON — sort_keys ensures consistent ordering
        payload_string = json.dumps(payment_payload, sort_keys=True)

        # Sign the payload bytes using ECDSA with SHA256
        # ECDSA produces a different signature each time (it includes
        # a random component) — unlike our previous HMAC approach.
        # This is normal and correct behaviour.
        signature_bytes = self._private_key.sign(
            payload_string.encode(),
            ec.ECDSA(hashes.SHA256())
        )

        # Encode signature as base64 so it's safe to put in an HTTP header
        signature_b64 = base64.b64encode(signature_bytes).decode()

        payment_proof = {
            "payload":   payment_payload,
            "signature": signature_b64,
        }

        print(f"[Wallet] Payment signed (ECDSA). "
              f"Fee: {fee} {currency} | Nonce: {nonce}")
        print(f"[Wallet] Signature: {signature_b64[:20]}...")

        return payment_proof


    def deduct(self, amount: float, trade_ref: str) -> None:
        """Deducts a fee and logs the transaction."""
        self.balance -= amount

        log_entry = {
            "transaction_id": str(uuid.uuid4()),
            "trade_ref":      trade_ref,
            "amount_paid":    amount,
            "balance_after":  round(self.balance, 2),
            "timestamp":      datetime.now(timezone.utc).isoformat(),
        }

        self.transaction_log.append(log_entry)
        print(f"[Wallet] Deducted {amount} USDC. "
              f"Remaining balance: {self.balance:.2f} USDC")


    def print_statement(self) -> None:
        """Prints all transactions to the terminal."""
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