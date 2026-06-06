# AgentTrade — x402 Agentic Payment Demo

A working demonstration of the [x402 payment protocol](https://x402.org) applied 
to a fintech use case: an autonomous trading agent that pays a brokerage fee per 
trade execution, with no human involvement, no real money, and no blockchain required.

Built in Python. Includes real ECDSA signing, live market prices, a portfolio 
endpoint, and a live dashboard.

---

## What is x402?

HTTP has included a `402 Payment Required` status code since the early days of the 
web. The x402 protocol — created by Coinbase and now supported by Google, Visa, 
Cloudflare, and Anthropic — gives that status code a real implementation for 
machine-to-machine payments.

The flow:
1. A client requests a resource
2. The server responds `402` with fee instructions and a one-time nonce
3. The client signs a payment proof and retries with it in the `X-Payment` header
4. The server verifies the signature and nonce, then fulfils the request

This project implements that full flow for a simulated trade execution endpoint.

---

## Project structure

```
agenttrade/
│
├── server/
│   ├── brokerage_server.py     # Flask server — 402 logic, trade and portfolio endpoints
│   └── templates/
│       └── dashboard.html      # Live dashboard UI
│
├── agent/
│   └── trading_agent.py        # Autonomous agent — payment flow, retry logic
│
├── wallet/
│   └── mock_wallet.py          # Wallet — ECDSA signing, balance, transaction log
│
├── shared/
│   ├── config.py               # All configuration (excluded from version control)
│   └── config.example.py       # Template — copy to config.py and add your keys
│
├── data/
│   ├── market_prices.py        # Live prices via yfinance, with fallback
│   └── portfolio_store.py      # In-memory portfolio holdings
│
├── tests/
│   └── test_payment_flow.py    # 16 automated tests
│
└── README.md
```

---

## How to run it

### Prerequisites

- Python 3.12 (managed via pyenv — see note below)
- macOS, Linux, or Windows (WSL)

### 1. Clone the repository

```bash
git clone https://github.com/davidetfabbrica/agenttrade.git
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

### 4. Set up configuration

```bash
cp shared/config.example.py shared/config.py
```

Generate a key pair:

```bash
python3 -c "
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

private_key = ec.generate_private_key(ec.SECP256K1())

print(private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
).decode())

print(private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
).decode())
"
```

Paste the private and public keys into `shared/config.py`.

### 5. Start the brokerage server

In one terminal:

```bash
python -m server.brokerage_server
```

You should see:
```
[Server] AgentTrade Brokerage Server starting...
[Server] Listening on http://127.0.0.1:5000
[Server] Trade fee: 0.5 USDC per execution
```

### 6. Run the trading agent

In a second terminal (with venv active):

```bash
python -m agent.trading_agent
```

The agent will place three trades and fetch the portfolio. For each trade you will see:
- A `402 Payment Required` response with fee instructions and a nonce
- The wallet signing with ECDSA
- The signed retry
- A trade confirmation with reference number, fill price, and timestamp
- The wallet balance reducing by 0.50 USDC

The portfolio query follows, costing 0.25 USDC.

### 7. View the dashboard

With the server running, open your browser at:

```
http://127.0.0.1:5000/dashboard
```

The dashboard refreshes every three seconds and shows live trade history, portfolio 
holdings, transaction log, and wallet stats.

### 8. Run the tests

```bash
python -m pytest tests/ -v
```

All 16 tests should pass.

---

## The x402 flow in detail

```
Agent                          Brokerage Server
  │                                   │
  │── POST /execute-trade ──────────► │
  │   { ticker, direction, quantity } │
  │                                   │
  │◄─ 402 Payment Required ───────── │
  │   { fee, currency, recipient,     │
  │     nonce, instructions }         │
  │                                   │
  │  [Agent signs with ECDSA]         │
  │                                   │
  │── POST /execute-trade ──────────► │  [Server verifies ECDSA signature]
  │   body:   { ticker, ... }         │  [Server checks nonce unused]
  │   header: X-Payment: { payload,   │  [Server executes trade]
  │             signature }           │
  │                                   │
  │◄─ 200 OK ─────────────────────── │
  │   { trade_ref, status, ticker,    │
  │     fill_price, trade_value,      │
  │     fee_paid, timestamp }         │
  │                                   │
  [Wallet deducts fee, logs entry]
```

The same flow applies to `GET /portfolio`, with a fee of 0.25 USDC.

---

## Security design

| Concern | Approach |
|---|---|
| Replay attacks | Server issues a unique nonce per request; each nonce can only be used once |
| Payment tampering | ECDSA signature covers all payment fields; any change breaks verification |
| Key management | Private key excluded from version control via `.gitignore` |
| Invalid requests | Server validates all fields before processing |
| Insufficient funds | Wallet refuses to sign if balance is below the required fee |

### Signature scheme

This project uses **ECDSA on SECP256K1** — the same curve used by Bitcoin and 
Ethereum — via Python's `cryptography` library.

The agent signs with the private key. The server verifies with the public key. 
The private key never leaves the wallet. This is the signature scheme specified 
in the x402 protocol documentation.

> **Note on key storage:** The private key lives in `config.py` for demo 
> convenience. In production it would never be stored in a config file — it would 
> live in a hardware security module (HSM) or encrypted secrets manager.

---

## Configuration

All settings live in `shared/config.py` (copy from `config.example.py`):

| Setting | Default | Description |
|---|---|---|
| `BROKERAGE_URL` | `http://127.0.0.1:5000` | Server address |
| `TRADE_FEE` | `0.50` | Fee per trade in mock USDC |
| `AGENT_STARTING_BALANCE` | `10.00` | Starting wallet balance |
| `MAX_RETRIES` | `3` | Maximum agent retry attempts |
| `AGENT_PRIVATE_KEY_PEM` | — | ECDSA private key (generate with the script above) |
| `AGENT_PUBLIC_KEY_PEM` | — | ECDSA public key (derived from private key) |

---

## Market data

Prices are fetched from Yahoo Finance via `yfinance` — no API key required. A 
session cache means each ticker is fetched at most once per server run. If Yahoo 
Finance is unavailable or rate limiting, the module falls back to static prices 
so the demo runs cleanly outside market hours.

Supported tickers: `AAPL`, `TSLA`, `MSFT`, `NVDA`, `AMZN`

---

## Stack

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12.9 | Language |
| Flask | 3.1.1 | Brokerage server and dashboard |
| requests | 2.32.3 | Agent HTTP calls |
| yfinance | 0.2.54 | Live market prices |
| cryptography | 42.0.8 | ECDSA signing and verification |
| pytest | 8.3.5 | Test runner |
| uuid | built-in | Nonce and trade reference generation |

---

## Python version note

This project uses Python 3.12.9 rather than the current 3.14. Flask and several 
HTTP libraries are not yet compatible with 3.14. Use pyenv to manage versions:

```bash
brew install pyenv
pyenv install 3.12.9
pyenv local 3.12.9
```

---

## License

MIT
