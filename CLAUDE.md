# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Polymarket MCP — an always-on MCP server for Polymarket prediction markets. Runs on a VPS as a systemd service. Claude Code is the primary operator (no web UI). The server exposes Polymarket's full CLOB trading API as MCP tools.

## Tech Stack

- **Python 3.11**, managed with **uv** (package manager)
- **MCP SDK** (`mcp` Python package) for the server framework
- **py-clob-client** — official Polymarket SDK handling EIP-712 signing, HMAC, order construction
- **httpx** for HTTP, **websockets** for streaming, **eth-account** for wallet signing
- **python-dotenv** for `.env` loading at startup
- **systemd** for process supervision on VPS

## Build & Run Commands

```bash
uv sync                                    # Install dependencies, create .venv
source .venv/bin/activate                  # Activate venv
python -m polymarket_mcp.server            # Run server locally (reads .env)

# Systemd (VPS)
systemctl start polymarket-mcp
systemctl status polymarket-mcp
journalctl -u polymarket-mcp -f            # Stream logs
```

## Testing

Tests hit the real Polymarket API (no mocks, no testnet). Credentials from `.env`.

```bash
pytest                                     # Full suite
pytest tests/test_markets.py -v            # Single test file
pytest tests/test_safety.py -v             # Safety tests (no API calls)
pytest --cov=polymarket_mcp --cov-report=term-missing  # With coverage

# Read-only tests (safe, works in DEMO mode)
pytest tests/test_markets.py tests/test_orderbook.py tests/test_analysis.py -v

# DEMO mode (no wallet needed)
DEMO_MODE=true pytest tests/test_markets.py tests/test_orderbook.py -v
```

Order tests (`test_orders.py`) place and immediately cancel $1 USDC orders on mainnet.

## Linting & Type Checking

```bash
ruff check .                               # Lint
ruff format .                              # Format
mypy --strict src/                         # Type checking (strict mode)
```

## Architecture

### Core modules (`src/polymarket_mcp/`)

- **server.py** — MCP server entry point, tool registration, transport setup (stdio or SSE)
- **auth.py** — L1/L2 auth, credential loading from `.env`, ClobClient initialization. All auth is server-side; individual tools never handle auth
- **client.py** — Polymarket client wrapper aggregating CLOB, Gamma, and Data API calls
- **safety.py** — Pre-trade validation enforced before any order reaches the API (order size, spread, liquidity, exposure limits)
- **demo.py** — DEMO mode guard; blocks write tools and returns clear error when `DEMO_MODE=true`
- **types.py** — All dataclasses: Market, Token, Order, Position, Trade, SafetyConfig

### Tool modules (`src/polymarket_mcp/tools/`)

Each file registers MCP tools for one domain:
- **markets.py** — Market discovery (Gamma API, no auth)
- **orderbook.py** — Orderbook + pricing (CLOB public, no auth)
- **orders.py** — Order placement + cancellation (CLOB authenticated)
- **positions.py** — Position + portfolio queries (Data API)
- **analysis.py** — Synthesized analysis tools (opportunity, risk, compare, portfolio)
- **stream.py** — WebSocket streaming (subscribe/unsubscribe for live data)

### Key design patterns

- **Read tools are always safe** — no side effects, work in DEMO mode
- **Write tools go through safety.py** — every order is validated against configurable limits before API submission
- **Orders above `REQUIRE_CONFIRMATION_ABOVE_USD`** return a confirmation request, not an error — caller must invoke `confirm_order` to proceed
- **Token ID vs Condition ID** — CLOB tools require `token_id` (per-outcome), not `conditionId` (per-market). `get_market` returns both; extract `token_id` from the `tokens[]` array

### Three Polymarket APIs

| API | Auth | Purpose |
|---|---|---|
| Gamma (`gamma-api.polymarket.com`) | None | Market discovery, events, search |
| Data (`data-api.polymarket.com`) | None | Positions, trades, history |
| CLOB (`clob.polymarket.com`) | L2 for trading | Orderbook, prices, order placement |

### Auth flow

L1 private key derives L2 credentials (API key, secret, passphrase) once via `scripts/derive_creds.py`. L2 credentials are stored in `.env` and used for all trading requests. The `py-clob-client` SDK handles HMAC header generation per request.

## Setup Scripts

```bash
python scripts/derive_creds.py             # Derive L2 creds from private key (one-time)
python scripts/approve_usdc.py             # Set USDC approval on Polygon (one-time)
python scripts/check_auth.py               # Verify credentials + geo-block check
python scripts/check_balance.py            # Check USDC + POL balance
python scripts/list_positions.py           # Quick position dump
```

## Configuration

All config is in `.env` (see `.env.example`). Key settings:
- `DEMO_MODE` — `true` for read-only operation without wallet
- `MCP_TRANSPORT` — `stdio` (default, for local Claude Code) or `sse` (remote clients, port in `MCP_PORT`)
- Safety limits: `MAX_ORDER_SIZE_USD`, `MAX_TOTAL_EXPOSURE_USD`, `MAX_SPREAD_TOLERANCE`, etc.

## Geographic Restrictions

Polymarket geo-blocks trading from US and OFAC-sanctioned regions at the API level. The VPS must be hosted outside blocked regions (EU, Singapore, UAE recommended). Consistent 403s on trading endpoints indicate IP-level blocking.
