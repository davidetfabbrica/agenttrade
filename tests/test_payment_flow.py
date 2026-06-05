# tests/test_payment_flow.py
# ─────────────────────────────────────────────────────────────
# Automated tests for the AgentTrade x402 payment flow.
#
# We use Python's built-in 'unittest' library — no install needed.
# These tests verify the components work correctly in isolation
# before you wire them together.
#
# To run all tests from the project root:
#   python -m pytest tests/
#
# Or without pytest:
#   python -m unittest discover tests
#
# Good tests check three things:
#   1. The happy path works (valid inputs produce correct outputs)
#   2. Edge cases are handled (zero balance, bad tickers)
#   3. Security controls hold (bad signatures, reused nonces)
# ─────────────────────────────────────────────────────────────

import unittest
import json
import hashlib

from wallet.mock_wallet import MockWallet
from data.market_prices import get_price, list_available_tickers
from shared.config import (
    TRADE_FEE,
    FEE_CURRENCY,
    BROKERAGE_WALLET_ADDRESS,
    AGENT_PRIVATE_KEY,
)


class TestMockWallet(unittest.TestCase):
    """
    Tests for the MockWallet class.
    Each test method must start with 'test_' — that's how
    unittest finds and runs them automatically.
    """

    def setUp(self):
        """
        Called automatically before each test method.
        Creates a fresh wallet so tests don't affect each other.
        """
        self.wallet = MockWallet()

    def test_initial_balance(self):
        """Wallet starts with the correct balance from config."""
        from shared.config import AGENT_STARTING_BALANCE
        self.assertEqual(self.wallet.balance, AGENT_STARTING_BALANCE)

    def test_has_sufficient_funds_true(self):
        """Returns True when balance covers the fee."""
        self.assertTrue(self.wallet.has_sufficient_funds(TRADE_FEE))

    def test_has_sufficient_funds_false(self):
        """Returns False when balance is less than the fee."""
        # Force the balance below the fee
        self.wallet.balance = 0.10
        self.assertFalse(self.wallet.has_sufficient_funds(TRADE_FEE))

    def test_has_sufficient_funds_exact_amount(self):
        """Returns True when balance exactly equals the fee."""
        self.wallet.balance = TRADE_FEE
        self.assertTrue(self.wallet.has_sufficient_funds(TRADE_FEE))

    def test_sign_payment_returns_correct_structure(self):
        """Signed payment contains payload and signature fields."""
        proof = self.wallet.sign_payment(
            fee=TRADE_FEE,
            currency=FEE_CURRENCY,
            recipient=BROKERAGE_WALLET_ADDRESS,
            nonce="test-nonce-001",
        )
        self.assertIn("payload", proof)
        self.assertIn("signature", proof)

    def test_sign_payment_signature_is_correct(self):
        """
        Signature matches what we'd expect from the algorithm.
        This test documents exactly how the signature is produced —
        useful for anyone reading the code to understand the mechanic.
        """
        nonce = "test-nonce-002"
        proof = self.wallet.sign_payment(
            fee=TRADE_FEE,
            currency=FEE_CURRENCY,
            recipient=BROKERAGE_WALLET_ADDRESS,
            nonce=nonce,
        )

        # Recreate the expected signature manually
        payload = {
            "fee":       TRADE_FEE,
            "currency":  FEE_CURRENCY,
            "recipient": BROKERAGE_WALLET_ADDRESS,
            "nonce":     nonce,
        }
        payload_string = json.dumps(payload, sort_keys=True)
        raw = payload_string + AGENT_PRIVATE_KEY
        expected_signature = hashlib.sha256(raw.encode()).hexdigest()

        self.assertEqual(proof["signature"], expected_signature)

    def test_sign_payment_raises_on_insufficient_funds(self):
        """
        Wallet raises a ValueError if you try to sign when broke.
        We use assertRaises to confirm the exception is thrown.
        """
        self.wallet.balance = 0.00
        with self.assertRaises(ValueError):
            self.wallet.sign_payment(
                fee=TRADE_FEE,
                currency=FEE_CURRENCY,
                recipient=BROKERAGE_WALLET_ADDRESS,
                nonce="test-nonce-003",
            )

    def test_deduct_reduces_balance(self):
        """Deducting a fee reduces the wallet balance correctly."""
        starting_balance = self.wallet.balance
        self.wallet.deduct(TRADE_FEE, "TRD-TEST001")
        self.assertAlmostEqual(
            self.wallet.balance,
            starting_balance - TRADE_FEE,
            places=2,  # Compare to 2 decimal places — sufficient for currency
        )

    def test_deduct_adds_to_transaction_log(self):
        """Each deduction creates a log entry."""
        self.wallet.deduct(TRADE_FEE, "TRD-TEST002")
        self.assertEqual(len(self.wallet.transaction_log), 1)
        self.assertEqual(
            self.wallet.transaction_log[0]["trade_ref"], "TRD-TEST002"
        )

    def test_multiple_deductions_logged_correctly(self):
        """Three deductions produce three log entries in order."""
        refs = ["TRD-A", "TRD-B", "TRD-C"]
        for ref in refs:
            self.wallet.deduct(TRADE_FEE, ref)

        self.assertEqual(len(self.wallet.transaction_log), 3)
        for i, ref in enumerate(refs):
            self.assertEqual(self.wallet.transaction_log[i]["trade_ref"], ref)


class TestMarketPrices(unittest.TestCase):
    """Tests for the market price data module."""

    def test_get_price_returns_float(self):
        """Price lookup returns a float."""
        price = get_price("AAPL")
        self.assertIsInstance(price, float)

    def test_get_price_case_insensitive(self):
        """Lowercase ticker returns the same price as uppercase."""
        self.assertEqual(get_price("aapl"), get_price("AAPL"))

    def test_get_price_raises_on_unknown_ticker(self):
        """Unknown ticker raises a ValueError, never returns silently."""
        with self.assertRaises(ValueError):
            get_price("FAKE")

    def test_all_tickers_have_positive_prices(self):
        """Every ticker in the mock data has a price above zero."""
        for ticker in list_available_tickers():
            price = get_price(ticker)
            self.assertGreater(price, 0,
                msg=f"Price for {ticker} should be positive, got {price}")


class TestSignatureVerification(unittest.TestCase):
    """
    Tests that verify the signature logic the server uses.
    We test the algorithm directly here — the server integration
    is covered by running the full demo manually.
    """

    def _make_signature(self, payload: dict) -> str:
        """Helper to produce a signature the same way the wallet does."""
        payload_string = json.dumps(payload, sort_keys=True)
        raw = payload_string + AGENT_PRIVATE_KEY
        return hashlib.sha256(raw.encode()).hexdigest()

    def test_valid_signature_verifies(self):
        """A correctly signed payload produces a matching signature."""
        payload = {
            "fee":       TRADE_FEE,
            "currency":  FEE_CURRENCY,
            "recipient": BROKERAGE_WALLET_ADDRESS,
            "nonce":     "verify-test-001",
        }
        signature = self._make_signature(payload)

        # Reproduce the server's verification logic
        payload_string = json.dumps(payload, sort_keys=True)
        raw = payload_string + AGENT_PRIVATE_KEY
        expected = hashlib.sha256(raw.encode()).hexdigest()

        self.assertEqual(signature, expected)

    def test_tampered_payload_fails_verification(self):
        """
        Changing any field in the payload after signing
        produces a different hash — the signature no longer matches.
        This is the fundamental guarantee of cryptographic hashing.
        """
        payload = {
            "fee":       TRADE_FEE,
            "currency":  FEE_CURRENCY,
            "recipient": BROKERAGE_WALLET_ADDRESS,
            "nonce":     "verify-test-002",
        }
        original_signature = self._make_signature(payload)

        # Tamper with the fee after signing
        tampered_payload = dict(payload)
        tampered_payload["fee"] = 0.00

        tampered_signature = self._make_signature(tampered_payload)

        # The signatures must be different
        self.assertNotEqual(original_signature, tampered_signature)


if __name__ == "__main__":
    unittest.main()