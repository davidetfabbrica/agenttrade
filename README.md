# AgentTrade — x402 Agentic Payment Demo

A working demonstration of the [x402 payment protocol](https://x402.org) applied 
to a fintech use case: an autonomous trading agent that pays a brokerage fee 
per trade execution, with no human involvement.

Built as a learning project in Python. No real money, no blockchain, no API keys required.

---

## What is x402?

HTTP has included a `402 Payment Required` status code since the early days of the web. 
The x402 protocol — created by Coinbase and now supported by Google, Visa, Cloudflare, 
and Anthropic — gives that status code a real implementation for machine-to-machine payments.

The flow:
1. A client requests a resource
2. The server responds `402` with fee instructions and a one-time nonce
3. The client signs a payment proof and retries with it in the `X-Payment` header
4. The server verifies the signature and nonce, then fulfils the request

This project implements that full flow for a simulated trade execution endpoint.

---

## Project structure

agenttrade/
│
├── server/
│   └── brokerage_server.py     # Flask server — 402 logic, trade execution
│
├── agent/
│   └── trading_agent.py        # Autonomous agent — payment flow and retry logic
│
├── wallet/
│   └── mock_wallet.py          # Simulated wallet — signing, balance, transaction log
│
├── shared/
│   └── config.py               # All configuration in one place
│
├── data/
│   └── market_prices.py        # Mock stock prices
│
├── tests/
│   └── test_payment_flow.py    # 16 automated tests
│
└── README.md

---

## How to run it

### Prerequisites

- Python 3.12 (managed via pyenv — see setup notes below)
- macOS, Linux, or Windows (WSL)

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/agenttrade.git
cd agenttrade
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the brokerage server

In one terminal:

```bash
python -m server.brokerage_server
```

You should see:

[Server] AgentTrade Brokerage Server starting...
[Server] Listening on http://127.0.0.1:5000
[Server] Trade fee: 0.5 USDC per execution

### 5. Run the trading agent

In a second terminal (with venv active):

```bash
python -m agent.trading_agent
```

The agent will place three trades. For each one you will see:
- A `402 Payment Required` response with fee instructions
- The wallet signing the payment proof
- The signed retry request
- A trade confirmation with reference number, fill price, and timestamp
- The wallet balance reducing by 0.50 USDC

### 6. Run the tests

```bash
python -m pytest tests/ -v
```

All 16 tests should pass.

---

## The x402 flow in detail

Agent                          Brokerage Server
│                                   │
│── POST /execute-trade ──────────► │
│   { ticker, direction, quantity } │
│                                   │
│◄─ 402 Payment Required ───────── │
│   { fee, currency, recipient,     │
│     nonce, instructions }         │
│                                   │
│  [Agent signs payment proof]      │
│                                   │
│── POST /execute-trade ──────────► │
│   body:   { ticker, ... }         │  [Server verifies signature]
│   header: X-Payment: { payload,   │  [Server checks nonce unused]
│             signature }           │  [Server executes trade]
│                                   │
│◄─ 200 OK ─────────────────────── │
│   { trade_ref, status, ticker,    │
│     fill_price, trade_value,      │
│     fee_paid, timestamp }         │
│                                   │
[Wallet deducts fee, logs entry]

---

## Security design

| Concern | Approach |
|---|---|
| Replay attacks | Server issues a unique nonce per request; each nonce can only be used once |
| Payment tampering | SHA-256 signature covers all payment fields; any change breaks the signature |
| Hardcoded secrets | All keys and addresses in `config.py`, not in logic files |
| Invalid requests | Server validates all fields before processing |
| Insufficient funds | Wallet refuses to sign if balance is below the required fee |

### Note on signature scheme

This demo uses an HMAC-style signature: `SHA-256(payload + private_key)`.  
The server shares the private key for verification — which would be insecure in production.

A real x402 implementation uses **ECDSA** (Elliptic Curve Digital Signature Algorithm):
the agent signs with a private key, the server verifies with the corresponding public key.
The private key never leaves the agent's wallet.

---

## Configuration

All settings live in `shared/config.py`:

| Setting | Default | Description |
|---|---|---|
| `BROKERAGE_URL` | `http://127.0.0.1:5000` | Server address |
| `TRADE_FEE` | `0.50` | Fee per trade in mock USDC |
| `AGENT_STARTING_BALANCE` | `10.00` | Starting wallet balance |
| `MAX_RETRIES` | `3` | Maximum agent retry attempts |

---

## Stack

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12.9 | Language |
| Flask | 3.1.1 | Brokerage server |
| requests | 2.32.3 | Agent HTTP calls |
| pytest | 8.3.5 | Test runner |
| hashlib | built-in | Payment signing |
| uuid | built-in | Nonce and trade reference generation |

---

## Possible extensions

- Add a `GET /portfolio` endpoint — agent pays to retrieve its holdings
- Swap `data/market_prices.py` for a live market data API
- Implement real ECDSA signing using the `cryptography` Python library
- Add a `--dry-run` flag that shows what the agent would pay without executing
- Persist the nonce store and transaction log to a file between runs

---

## License

MIT