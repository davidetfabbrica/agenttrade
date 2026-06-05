# shared/config.py
# ─────────────────────────────────────────────────────────────
# Central configuration for AgentTrade.
# All tunable values live here. Nothing is hardcoded elsewhere.
# If you want to change a fee, a balance, or a URL — do it here.
# ─────────────────────────────────────────────────────────────

# The URL where the brokerage server runs locally on your machine.
# Flask defaults to port 5000. We use localhost (127.0.0.1) because
# nothing is deployed — it all runs on your computer.
BROKERAGE_URL = "http://127.0.0.1:5000"

# The single endpoint the agent calls to place a trade.
TRADE_ENDPOINT = "/execute-trade"

# The fee charged per trade, in mock USDC.
# In a real x402 system this would be denominated in an actual stablecoin.
TRADE_FEE = 0.50

# The currency label — purely cosmetic in this demo, but realistic.
FEE_CURRENCY = "USDC"

# The mock wallet address of the brokerage — i.e. who receives the fee.
# In a real system this would be a blockchain address (e.g. Ethereum).
# Here it is just a string we can check against.
BROKERAGE_WALLET_ADDRESS = "0xBROKERAGE_MOCK_WALLET_001"

# The agent's mock private key, used to sign payment headers.
# In a real system this would be a cryptographic private key — never
# stored in plain text like this. For this demo it is a dummy string.
AGENT_PRIVATE_KEY = "mock-private-key-agent-001"

# The agent's starting balance in mock USDC.
AGENT_STARTING_BALANCE = 10.00

# Maximum number of times the agent will retry a request.
# Prevents infinite loops if something goes wrong.
MAX_RETRIES = 3