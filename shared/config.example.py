# shared/config.py
# ─────────────────────────────────────────────────────────────
# Central configuration for AgentTrade.
#
# Key pair note:
# The private key lives here for demo convenience only.
# In production it would never be stored in a config file —
# it would live in a hardware wallet, an HSM (Hardware Security
# Module), or an encrypted secrets manager like HashiCorp Vault.
#
# The public key is what a real brokerage server would store.
# It can verify signatures without ever seeing the private key.
# ─────────────────────────────────────────────────────────────

BROKERAGE_URL = "http://127.0.0.1:5000"
TRADE_ENDPOINT = "/execute-trade"
TRADE_FEE = 0.50
FEE_CURRENCY = "USDC"
BROKERAGE_WALLET_ADDRESS = "0xBROKERAGE_MOCK_WALLET_001"
AGENT_STARTING_BALANCE = 10.00
MAX_RETRIES = 3

# ── ECDSA Key Pair ────────────────────────────────────────────
# Generated using the SECP256K1 curve (same as Bitcoin/Ethereum).
# Replace these placeholders with your generated keys.
# Keep the triple quotes and exact formatting — newlines matter
# when loading PEM keys.

AGENT_PRIVATE_KEY_PEM = """-----BEGIN PRIVATE KEY-----
YOUR_PRIVATE_KEY_HERE
-----END PRIVATE KEY-----
"""

AGENT_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
YOUR_PUBLIC_KEY_HERE
-----END PUBLIC KEY-----
"""