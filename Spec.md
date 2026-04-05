# Polymarket MCP

Always-on MCP server for Polymarket prediction markets. Runs 24x7 on a VPS. Any MCP client — primarily Claude Code on the same VPS — can connect and execute trades, query markets, manage positions, and stream live data.

The MCP server IS the trading interface. No web UI, no dashboard. Claude Code is the operator.

## Why

Polymarket has a full CLOB trading API (markets, orderbook, order placement, positions, trades) but no MCP interface. This means AI agents can't natively interact with it. This project bridges that gap:

- Claude Code on the VPS connects to the local MCP server via stdio or SSE
- The MCP server handles all Polymarket API complexity: L1/L2 auth, EIP-712 signing, order construction, HMAC headers
- Claude Code reasons over markets and executes trades through named tools — no raw API calls
- Server runs as a systemd service, always available, survives reboots

## Design Principles

1. **MCP server is the only interface.** No REST wrapper, no separate CLI. Tools are the API.
2. **Auth complexity is server-side.** L1 private key signing, L2 HMAC generation, EIP-712 structs — all handled inside the server. Claude Code never sees raw credentials.
3. **Tool names map 1:1 to intent.** `place_order`, `cancel_order`, `get_market`, `get_positions` — not `post_clob_v1_orders`. Tools are designed for an agent, not an engineer.
4. **Read tools are always safe.** Market data, orderbook, prices, positions — all read-only tools have no side effects and can be called freely.
5. **Write tools are explicit.** Order placement, cancellation — clearly named, always return confirmation with order ID.
6. **Credentials live in `.env`, never in code or tool responses.** Private key, API key, secret, passphrase — loaded at startup, never echoed.
7. **Safety limits are first-class config.** Max order size, max total exposure, spread tolerance, confirmation thresholds — all configurable in `.env`, enforced before any order reaches the API.
8. **DEMO mode ships day one.** Read-only mode with no wallet required. Full market discovery and analysis tools work. Trading tools return a clear `DEMO_MODE=true` error. Lets anyone evaluate the server without funds.
9. **Zero custom signing logic.** Uses the official `py-clob-client` SDK for all EIP-712 signing, HMAC generation, and order construction.

## Polymarket API Surface

Three public APIs, one authenticated:

| API | Base URL | Auth required | Used for |
|---|---|---|---|
| Gamma API | `https://gamma-api.polymarket.com` | No | Market discovery, events, tags, search |
| Data API | `https://data-api.polymarket.com` | No | Positions, trades, history, leaderboard |
| CLOB API (public) | `https://clob.polymarket.com` | No | Orderbook, prices, spreads |
| CLOB API (trading) | `https://clob.polymarket.com` | Yes (L2) | Place orders, cancel orders, heartbeat |

### Authentication model

**L1 (private key)** — used once at startup to derive L2 credentials. Signs an EIP-712 message. Never sent in requests after credential derivation.

**L2 (API key)** — derived from L1. Three values: `apiKey`, `secret`, `passphrase`. All trading requests include 5 `POLY_*` headers signed with HMAC-SHA256 using the `secret`.

**Signature type** — must match the wallet type:

| Type | Value | When to use |
|---|---|---|
| EOA | `0` | Standard Ethereum wallet |
| POLY_PROXY | `1` | Magic Link / Google login export |
| GNOSIS_SAFE | `2` | Default for most users on Polymarket.com |

The funder address is the proxy wallet shown on `polymarket.com/settings`.

### Token IDs vs Condition IDs

Polymarket uses two distinct identifiers that are easy to confuse:

| Identifier | Field | Where used | Example |
|---|---|---|---|
| `conditionId` | Market-level | Gamma API, Data API — identifies the whole market | `0x1234...abcd` |
| `token_id` | Outcome-level | CLOB API — identifies one outcome (Yes or No) | `71321045679...` (uint256 string) |

Every market has one `conditionId` and two `token_id` values — one per outcome. All CLOB tools (`place_order`, `get_orderbook`, `get_price`, etc.) take `token_id`, not `conditionId`.

The `get_market` tool returns both: the top-level `id` is the `conditionId`, and the `tokens` array contains one entry per outcome with its `token_id` and outcome label.

**Lookup flow for Claude Code:**
```
search_markets("Will X happen?")
  → returns Market with conditionId + tokens[]
  → tokens[0] = { token_id: "71321...", outcome: "Yes" }
  → tokens[1] = { token_id: "98432...", outcome: "No" }
  → pass token_id to place_order, get_orderbook, get_price
```

Never pass a `conditionId` to a CLOB tool — the API will return a 400.

## On-Disk Format

```
polymarket-mcp/
  pyproject.toml                      # Project metadata + dependencies
  uv.lock                             # Lock file (uv package manager)
  .python-version                     # Python version pin (3.11)
  biome.json                          # JS/JSON formatting (for config files)
  .gitignore
  .env.example
  CHANGELOG.md
  README.md
  CLAUDE.md
  AGENT_INTEGRATION_GUIDE.md          # How Claude Code should reason about and use tools
  install.sh                          # One-command VPS install + systemd setup
  scripts/
    version_bump.py
    derive_creds.py                   # One-time: derive L2 creds from private key
    approve_usdc.py                   # One-time: set USDC approval on Polygon
    check_balance.py                  # Check USDC + POL balance for funder wallet
    check_auth.py                     # Verify credentials + geo-block check
    list_positions.py                 # Quick position dump to stdout
  .claude/
    commands/
      release.md
  .github/
    workflows/
      ci.yml
      auto-tag.yml
  src/
    polymarket_mcp/
      __init__.py
      server.py                       # MCP server entry point + VERSION constant
      types.py                        # All dataclasses: Order, Market, Position, Trade
      auth.py                         # L1/L2 auth, credential loading, ClobClient init
      client.py                       # Polymarket client wrapper (CLOB + Gamma + Data)
      safety.py                       # Safety limit enforcement (pre-trade validation)
      demo.py                         # DEMO mode guard — blocks write tools, returns error
      tools/
        markets.py                    # Market discovery tools (Gamma API)
        orderbook.py                  # Orderbook + pricing tools (CLOB public)
        orders.py                     # Order placement + cancellation (CLOB authenticated)
        positions.py                  # Position + portfolio tools (Data API)
        analysis.py                   # AI-assist tools: opportunity, risk, portfolio analysis
        stream.py                     # WebSocket tools: subscribe_market, subscribe_orders
  tests/
    test_markets.py
    test_orderbook.py
    test_orders.py
    test_positions.py
    test_analysis.py
    test_stream.py
    test_safety.py
  systemd/
    polymarket-mcp.service            # systemd unit file
```

### .env (never committed)

```bash
# Mode
DEMO_MODE="false"                   # "true" = read-only, no wallet needed

# Wallet (required when DEMO_MODE=false)
POLYGON_PRIVATE_KEY="0x..."         # Ethereum private key (L1) — with 0x prefix
POLYGON_ADDRESS="0x..."             # Your wallet address (EOA or proxy)
FUNDER_ADDRESS="0x..."              # Proxy wallet from polymarket.com/settings
SIGNATURE_TYPE="2"                  # 0=EOA, 1=POLY_PROXY, 2=GNOSIS_SAFE

# L2 credentials (derived from L1 — run scripts/derive_creds.py once)
POLY_API_KEY="550e8400-..."
POLY_SECRET="base64EncodedSecret"
POLY_PASSPHRASE="randomPassphrase"

# Safety limits
MAX_ORDER_SIZE_USD="1000"           # Maximum USDC per single order
MAX_TOTAL_EXPOSURE_USD="5000"       # Maximum total open position value
MAX_POSITION_SIZE_PER_MARKET="2000" # Maximum USDC in any single market
MIN_LIQUIDITY_REQUIRED="10000"      # Minimum market liquidity to trade
MAX_SPREAD_TOLERANCE="0.05"         # Maximum spread (5%) before order blocked
REQUIRE_CONFIRMATION_ABOVE_USD="500" # Orders above this return a confirmation request

# Server
MCP_TRANSPORT="stdio"               # "stdio" for Claude Code local, "sse" for remote
MCP_PORT="3100"                     # Only used when MCP_TRANSPORT=sse
LOG_LEVEL="info"                    # debug | info | warn | error
VPS_REGION="eu-central"            # Documentation only — not enforced by server
```

### .env.example

```bash
# Mode
DEMO_MODE="false"

# Wallet
POLYGON_PRIVATE_KEY=""
POLYGON_ADDRESS=""
FUNDER_ADDRESS=""
SIGNATURE_TYPE="2"

# L2 credentials
POLY_API_KEY=""
POLY_SECRET=""
POLY_PASSPHRASE=""

# Safety limits (recommended defaults)
MAX_ORDER_SIZE_USD="1000"
MAX_TOTAL_EXPOSURE_USD="5000"
MAX_POSITION_SIZE_PER_MARKET="2000"
MIN_LIQUIDITY_REQUIRED="10000"
MAX_SPREAD_TOLERANCE="0.05"
REQUIRE_CONFIRMATION_ABOVE_USD="500"

# Server
MCP_TRANSPORT="stdio"
MCP_PORT="3100"
LOG_LEVEL="info"
VPS_REGION=""
```

### .gitignore

```
.env
.env.*
!.env.example
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
```

### systemd unit file

```ini
[Unit]
Description=Polymarket MCP Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/polymarket-mcp
EnvironmentFile=/root/polymarket-mcp/.env
ExecStart=/root/polymarket-mcp/.venv/bin/python -m polymarket_mcp.server
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## MCP Tools

All tools follow the MCP tool spec: `name`, `description`, `inputSchema` (JSON Schema), return structured JSON.

### Market discovery tools (Gamma API — no auth, works in DEMO mode)

```
get_markets
  List tradeable markets with optional filters.
  Params: limit?, offset?, active?, closed?, tag?, search?
  Returns: Market[] with id, question, slug, outcomes, volume, liquidity

get_market
  Get a single market by ID or slug.
  Params: id? | slug? (one required)
  Returns: Market detail with outcomes, resolution criteria, end date

get_events
  List events (groups of related markets).
  Params: limit?, offset?, tag?, active?
  Returns: Event[] with markets array

get_event
  Get a single event by ID or slug.
  Params: id? | slug?
  Returns: Event detail with all markets

get_trending_markets
  Get markets sorted by volume over a time window.
  Params: period ("24h" | "7d" | "30d"), limit?
  Returns: Market[] sorted by volume descending

search_markets
  Full-text search across markets, events, and profiles.
  Params: query (required), limit?
  Returns: SearchResult[] with type and matched entity

get_tags
  List all market tags/categories.
  Returns: Tag[] with id, label, slug

get_market_tags
  Get tags for a specific market.
  Params: market_id (required)
  Returns: Tag[]
```

### Orderbook and pricing tools (CLOB public — no auth, works in DEMO mode)

```
get_orderbook
  Get full orderbook depth for a market outcome token.
  Params: token_id (required)
  Returns: { bids: PriceLevel[], asks: PriceLevel[], market, asset_id }

get_price
  Get current best price for a token.
  Params: token_id (required), side ("BUY" | "SELL")
  Returns: { price: string }

get_midpoint
  Get midpoint price (average of best bid and ask).
  Params: token_id (required)
  Returns: { mid: string }

get_spread
  Get spread between best bid and ask.
  Params: token_id (required)
  Returns: { spread: string }

get_last_trade_price
  Get the price of the most recent trade.
  Params: token_id (required)
  Returns: { price: string }

get_price_history
  Get historical price data for a token.
  Params: token_id (required), interval? ("1m"|"5m"|"1h"|"6h"|"1d"), start_ts?, end_ts?
  Returns: PricePoint[] with t (timestamp) and p (price)

get_fee_rate
  Get current maker/taker fee rates.
  Params: token_id (required)
  Returns: { maker_amount: string, taker_amount: string }

get_tick_size
  Get minimum price increment for a token.
  Params: token_id (required)
  Returns: { minimum_tick_size: string }
```

### Analysis tools (Gamma + CLOB public — no auth, works in DEMO mode)

These tools synthesize data from multiple endpoints and return structured assessments
Claude Code can reason over directly.

```
analyze_market_opportunity
  Analyze a market for trading opportunity.
  Params: token_id (required), strategy? ("aggressive"|"passive"|"mid", default "mid")
  Returns: {
    recommendation: "BUY" | "SELL" | "HOLD",
    confidence: "high" | "medium" | "low",
    suggested_price: string,
    suggested_size: string,
    reasoning: string,
    spread: string,
    liquidity: string,
    risk_score: number (1-10)
  }

get_risk_assessment
  Score a potential order for risk before placing.
  Params: token_id, price, size, side
  Returns: {
    safe: boolean,
    risk_score: number (1-10),
    checks: {
      order_size_ok: boolean,
      liquidity_ok: boolean,
      spread_ok: boolean,
      exposure_ok: boolean,
    },
    warnings: string[]
  }

compare_markets
  Side-by-side comparison of multiple markets.
  Params: token_ids (string[], max 5)
  Returns: ComparisonResult[] with price, spread, volume, liquidity per token

get_top_holders
  Get the largest position holders for a market.
  Params: token_id (required), limit?
  Returns: Holder[] with address, size, avg_price

analyze_portfolio
  Analyse the current portfolio for risk and diversification.
  Params: strategy? ("conservative"|"balanced"|"aggressive")
  Returns: {
    total_value: string,
    concentration_risk: string,
    liquidity_risk: string,
    suggestions: string[],
    diversification_score: number (1-10)
  }
```

### Order management tools (CLOB authenticated — requires L2, blocked in DEMO mode)

All write tools run through `safety.py` pre-trade validation before any API call.
If `DEMO_MODE=true`, all tools in this section return `{"error": "DEMO_MODE", "message": "Trading disabled. Set DEMO_MODE=false and provide wallet credentials."}`.

```
place_order
  Place a limit order on a market outcome.
  Pre-trade checks: order size, spread tolerance, market liquidity, total exposure.
  Params:
    token_id   string   required   The outcome token ID
    price      number   required   Limit price (0.01–0.99)
    size       number   required   Order size in USDC
    side       string   required   "BUY" | "SELL"
    expiration number   optional   Unix timestamp, default GTC
  Returns: { order_id, status, token_id, price, size, side }
  Returns (if size > REQUIRE_CONFIRMATION_ABOVE_USD):
    { requires_confirmation: true, order_summary: {...}, confirm_tool: "confirm_order" }

confirm_order
  Confirm and submit a pending large order (above REQUIRE_CONFIRMATION_ABOVE_USD).
  Params: confirmation_token (required, returned by place_order)
  Returns: { order_id, status, token_id, price, size, side }

place_market_order
  Place a market order (fills at best available price).
  Pre-trade checks: same as place_order.
  Params:
    token_id   string   required
    amount     number   required   USDC to spend (BUY) or shares to sell (SELL)
    side       string   required   "BUY" | "SELL"
  Returns: { order_id, status, filled_price, filled_size }

smart_trade
  Natural language → automated order strategy. Analyses orderbook, selects
  optimal price and size, places order, returns execution summary.
  Params:
    token_id   string   required
    intent     string   required   e.g. "buy $200 of YES aggressively"
    max_size   number   optional   Cap on USDC spend
  Returns: { orders_placed: Order[], total_spent: string, avg_price: string }

rebalance_position
  Adjust an existing position to a target size with slippage protection.
  Params:
    token_id      string   required
    target_size   number   required   Target USDC value
    max_slippage  number   optional   Default 0.02 (2%)
  Returns: { orders_placed: Order[], position_before: string, position_after: string }

cancel_order
  Cancel a single open order by ID.
  Params: order_id (required)
  Returns: { cancelled: true, order_id }

cancel_all_orders
  Cancel all open orders across all markets.
  Returns: { cancelled_count: number }

cancel_market_orders
  Cancel all open orders for a specific market.
  Params: token_id (required)
  Returns: { cancelled_count: number }

get_order
  Get a single order by ID.
  Params: order_id (required)
  Returns: Order with status, fills, remaining size

get_open_orders
  List all open orders for the authenticated user.
  Params: token_id? (filter by market)
  Returns: Order[]

get_trades
  Get trade history for the authenticated user.
  Params: token_id?, limit?, before?
  Returns: Trade[] with price, size, side, timestamp

send_heartbeat
  Send a heartbeat to keep authenticated session alive.
  Returns: { ok: true }
```

### Position and portfolio tools (Data API — requires wallet address, blocked in DEMO mode)

```
get_positions
  Get current open positions for the authenticated wallet.
  Returns: Position[] with market, outcome, size, avg_price, current_price, pnl

get_closed_positions
  Get resolved/closed positions.
  Params: limit?, offset?
  Returns: ClosedPosition[] with settlement_price, profit_loss

get_portfolio_value
  Get total value of all open positions.
  Returns: { total_value: string, positions_count: number }

get_activity
  Get recent trading activity for the wallet.
  Params: limit?, offset?
  Returns: Activity[] with type, market, amount, timestamp
```

### WebSocket streaming tools (CLOB WSS — no auth for market channel, L2 for user channel)

```
subscribe_market
  Open a WebSocket subscription to live orderbook + price updates for a token.
  Maintains connection with auto-reconnect and exponential backoff.
  Params: token_id (required)
  Returns: { subscription_id, status: "active" }
  Subsequent pushes: price_change and book events streamed as MCP progress notifications

subscribe_orders
  Subscribe to live order status updates for the authenticated wallet.
  Pushes events when orders are filled, cancelled, or matched.
  Returns: { subscription_id, status: "active" }
  Subsequent pushes: order events streamed as MCP progress notifications

unsubscribe
  Close an active WebSocket subscription.
  Params: subscription_id (required)
  Returns: { unsubscribed: true, subscription_id }

list_subscriptions
  List all active WebSocket subscriptions.
  Returns: Subscription[] with token_id, channel, status, created_at
```

## Data Model

All types are Python dataclasses. Serialized to/from JSON for MCP tool responses.

### Market

```python
@dataclass
class Token:
    token_id: str       # Used in all CLOB API calls
    outcome: str        # "Yes" | "No"

@dataclass
class Market:
    id: str             # Condition ID (hex)
    question: str
    slug: str
    outcomes: list[str]         # e.g. ["Yes", "No"]
    outcome_prices: list[str]   # current prices, parallel to outcomes
    tokens: list[Token]         # one per outcome
    volume: str                 # total USDC volume
    liquidity: str
    active: bool
    closed: bool
    end_date_iso: str           # ISO 8601 resolution date
    description: str | None
    tags: list[str]
```

### Order

```python
@dataclass
class Order:
    id: str
    status: str         # "LIVE" | "MATCHED" | "DELAYED" | "CANCELLED" | "CLOSED"
    token_id: str
    price: str
    size: str           # original size
    size_matched: str   # filled size
    size_remaining: str
    side: str           # "BUY" | "SELL"
    type: str           # "LIMIT" | "MARKET" | "FOK" | "GTD"
    created_at: int     # Unix timestamp
    expiration: int     # Unix timestamp, 0 = GTC
```

### Position

```python
@dataclass
class Position:
    market: str         # Condition ID
    question: str
    outcome: str
    token_id: str
    size: str           # shares held
    avg_price: str
    current_price: str
    unrealized_pnl: str
    realized_pnl: str
```

### Trade

```python
@dataclass
class Trade:
    trade_id: str
    token_id: str
    price: str
    size: str
    side: str           # "BUY" | "SELL"
    timestamp: int
    fee_rate_bps: str
```

### SafetyConfig

```python
@dataclass
class SafetyConfig:
    max_order_size_usd: float       # from MAX_ORDER_SIZE_USD
    max_total_exposure_usd: float   # from MAX_TOTAL_EXPOSURE_USD
    max_position_per_market: float  # from MAX_POSITION_SIZE_PER_MARKET
    min_liquidity_required: float   # from MIN_LIQUIDITY_REQUIRED
    max_spread_tolerance: float     # from MAX_SPREAD_TOLERANCE
    require_confirmation_above: float  # from REQUIRE_CONFIRMATION_ABOVE_USD
```

## USDC Approval (One-Time Onchain Setup)

Before placing any orders, the wallet must approve the Polymarket CTF Exchange contract to spend USDC on Polygon. This is a one-time onchain transaction — without it, every order placement will fail silently or with a cryptic error.

**What needs approval:**
- USDC contract on Polygon: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`
- Approved spender: CTF Exchange contract: `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`

The `py-clob-client` SDK provides helpers to check and set approval:

```python
from py_clob_client.client import ClobClient

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=137,
    key=os.getenv("POLYGON_PRIVATE_KEY"),
)

# Check if approval is already set
allowance = client.get_collateral_allowance()

# Set approval (one-time onchain tx — requires POL for gas)
if not allowance.get("approved"):
    client.set_allowance()
```

**Gas requirement:** The approval transaction costs a small amount of POL (Polygon's native gas token). The wallet needs a small POL balance (~0.01 POL) to pay gas. USDC alone is not sufficient.

Add a `check_approval` tool and a `scripts/approve_usdc.py` setup script:

```
scripts/
  approve_usdc.py     # One-time: check + set USDC approval on Polygon
  check_balance.py    # Check USDC + POL balance for the funder wallet
```

Add to `On-Disk Format` scripts directory. These run once during initial wallet setup, before first order.

**Checklist before first order:**
1. Wallet has USDC on Polygon (bridged from Ethereum or bought directly)
2. Wallet has POL for gas (~0.01 minimum, ~0.1 recommended)
3. USDC approval set for CTF Exchange (`python scripts/approve_usdc.py`)
4. L2 credentials derived (`python scripts/derive_creds.py`)
5. `.env` populated with all values
6. Service running (`systemctl status polymarket-mcp`)

## Auth Flow

The server handles all auth at startup. No auth logic in individual tools.

```
Startup
  └── Load .env → POLYGON_PRIVATE_KEY, FUNDER_ADDRESS, POLY_API_KEY, POLY_SECRET, POLY_PASSPHRASE
  └── Check DEMO_MODE — if true, skip wallet init, register read-only tools only
  └── Init ClobClient (py-clob-client) with private key + L2 credentials
  └── Load SafetyConfig from .env limits
  └── Validate connection: GET /time
  └── Check geo-block: test authenticated endpoint, surface 403 clearly
  └── Register all tools with MCP server
  └── Start transport (stdio or SSE)

Per authenticated tool call
  └── safety.py pre-trade validation:
        - order size ≤ MAX_ORDER_SIZE_USD
        - market liquidity ≥ MIN_LIQUIDITY_REQUIRED
        - spread ≤ MAX_SPREAD_TOLERANCE
        - projected exposure ≤ MAX_TOTAL_EXPOSURE_USD
        - if size > REQUIRE_CONFIRMATION_ABOVE_USD → return confirmation request
  └── py-clob-client handles:
        - POLY_ADDRESS header (wallet address)
        - POLY_TIMESTAMP header (current Unix ts)
        - POLY_API_KEY header
        - POLY_PASSPHRASE header
        - POLY_SIGNATURE header (HMAC-SHA256 of request using POLY_SECRET)
  └── Order creation additionally requires:
        - EIP-712 signing of order payload with POLYGON_PRIVATE_KEY (via eth-account)
```

### One-time credential derivation

Run once before first use. Derives L2 credentials from the private key and prints them to stdout to be copied into `.env`:

```bash
python scripts/derive_creds.py
# Output:
# POLY_API_KEY=550e8400-...
# POLY_SECRET=base64...
# POLY_PASSPHRASE=random...
```

## Transport Modes

### stdio (default — Claude Code on same VPS)

Claude Code's MCP client connects via stdin/stdout. No network port needed. Configured in Claude Code's MCP config (`~/.claude/claude_code_config.json`):

```json
{
  "mcpServers": {
    "polymarket": {
      "command": "/root/polymarket-mcp/.venv/bin/python",
      "args": ["-m", "polymarket_mcp.server"],
      "cwd": "/root/polymarket-mcp"
    }
  }
}
```

The `.env` file is loaded by the server process at startup via `python-dotenv`. Claude Code does not need to know the credentials.

**DEMO mode** — set `DEMO_MODE=true` in `.env` to start without wallet credentials. All market discovery, pricing, and analysis tools work. Write tools return a clear error. Useful for evaluating the server before committing funds.

### SSE (remote clients)

Set `MCP_TRANSPORT=sse` and `MCP_PORT=3100` in `.env`. The server exposes an SSE endpoint at `http://localhost:3100/sse`. Remote MCP clients connect over HTTP. Secure behind a reverse proxy (Caddy/nginx) with TLS if exposing beyond localhost.

```bash
systemctl start polymarket-mcp    # Starts as SSE server, always on
```

## Geographic Restrictions

Polymarket geo-blocks trading at the API level. The CLOB API returns `403 Forbidden` for requests originating from restricted regions — no order can be placed, not even read operations on some endpoints.

**Blocked regions include (but are not limited to):** United States, North Korea, Iran, Cuba, Syria, and other OFAC-sanctioned jurisdictions. The full list is enforced by Polymarket and subject to change. See [Polymarket geographic restrictions](https://docs.polymarket.com/api-reference/geoblock) for the current list.

**What this means for VPS deployment:**

The MCP server's outbound requests to `clob.polymarket.com` originate from the VPS's IP address. If the VPS is hosted in a geo-blocked region (e.g. a US datacenter), all authenticated CLOB calls will fail with 403 regardless of the operator's actual location.

**Required:** Use a VPS hosted outside blocked regions. Recommended hosting locations: EU (Germany, Netherlands, France), Singapore, UAE.

The server does not check or enforce geographic restrictions — that is Polymarket's responsibility. If you get consistent 403s on trading endpoints but not read endpoints, the VPS IP is blocked.

**Add to `.env`:**
```bash
# VPS region — for documentation only, not enforced by the server
VPS_REGION="eu-central"
```

**Add to `scripts/check-auth.ts`:** After credential validation, make a test request to a trading endpoint and surface a clear error if 403 is returned, with a message pointing to the geo-block docs.

## CLI Scripts

Not a full CLI — just operational scripts for setup and maintenance.

```bash
python scripts/derive_creds.py      # Derive L2 credentials from POLYGON_PRIVATE_KEY
python scripts/check_auth.py        # Verify credentials + geo-block check (dry run, no orders)
python scripts/approve_usdc.py      # Check + set USDC approval on Polygon (one-time)
python scripts/check_balance.py     # Print USDC + POL balance for funder wallet
python scripts/list_positions.py    # Quick position dump to stdout
```

## Tech Stack

| Concern | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Matches `py-clob-client` — the more mature Polymarket SDK |
| Package manager | `uv` | Fast, lockfile-native, replaces pip/venv |
| MCP SDK | `mcp` (Python) | Official MCP server SDK for Python |
| Polymarket | `py-clob-client` | Official SDK — handles EIP-712 signing, HMAC, order construction |
| HTTP client | `httpx` | Async-capable, used by py-clob-client internally |
| WebSocket | `websockets` | Pure Python, handles auto-reconnect |
| Wallet / signing | `eth-account` | EIP-712 + private key signing |
| Env loading | `python-dotenv` | Loads `.env` at startup |
| Process manager | `systemd` | Native VPS supervision, auto-restart |
| Testing | `pytest` with real API calls, no mocks | Same philosophy as Seeds/Diffract |
| Linting | `ruff` | Fast Python linter + formatter |
| Type checking | `mypy` (strict) | Full type coverage across all modules |

## Testing

Tests call the real Polymarket API. Read-only tests (markets, orderbook, prices, analysis) run freely and work in DEMO mode. Order tests place then immediately cancel very small orders ($1 USDC) on mainnet — there is no Polymarket testnet.

Credentials are stored in `.env`, never hardcoded.

```bash
# Activate venv
source .venv/bin/activate

# Run full test suite
pytest

# Run only read-only tests (safe, works in DEMO mode)
pytest tests/test_markets.py tests/test_orderbook.py tests/test_analysis.py -v

# Run order tests (places + immediately cancels $1 USDC test orders)
pytest tests/test_orders.py -v

# Run with coverage
pytest --cov=polymarket_mcp --cov-report=term-missing

# Run safety validation tests (no API calls)
pytest tests/test_safety.py -v
```

Create `.env` from `.env.example` and fill in credentials before running tests:

```bash
cp .env.example .env
nano .env   # Fill in POLYGON_PRIVATE_KEY, FUNDER_ADDRESS, POLY_* credentials
```

For DEMO mode tests (no wallet needed):

```bash
DEMO_MODE=true pytest tests/test_markets.py tests/test_orderbook.py -v
```

Add to `.gitignore`:

```
.env
.env.*
!.env.example
```

## Install on VPS

```bash
# One-command install
curl -fsSL https://raw.githubusercontent.com/yourorg/polymarket-mcp/main/install.sh | bash
```

The install script:
1. Installs Python 3.11 if not present
2. Installs `uv` (package manager)
3. Clones repo to `/root/polymarket-mcp`
4. Runs `uv sync` to create `.venv` and install dependencies
5. Copies `systemd/polymarket-mcp.service` to `/etc/systemd/system/`
6. Runs setup wizard — prompts for credentials and writes `.env`
7. Runs `python scripts/check_auth.py` to validate credentials + geo-block
8. Enables and starts the systemd service

After install:

```bash
systemctl status polymarket-mcp       # Check service is running
journalctl -u polymarket-mcp -f       # Stream logs

# Run in DEMO mode first to verify tools work before adding wallet
DEMO_MODE=true python -m polymarket_mcp.server
```

## WebSocket Streaming

Shipped in v1. Polymarket's live WebSocket feed at `wss://ws-subscriptions-clob.polymarket.com` provides two channels:

**Market channel** — real-time orderbook and price updates for a token. No auth required:
```json
{ "type": "subscribe", "channel": "market", "assets_ids": ["71321045679..."] }
```
Pushes `book` (full orderbook snapshot) and `price_change` events.

**User channel** — real-time order status updates for the authenticated wallet. Requires L2 auth:
```json
{ "type": "subscribe", "channel": "user", "markets": ["0x1234..."] }
```
Pushes `order` events (filled, cancelled, matched) as they happen.

Implementation lives in `src/polymarket_mcp/tools/stream.py`. The `websockets` library handles the connection; auto-reconnect uses exponential backoff (1s → 2s → 4s → 8s → max 60s). Active subscriptions are tracked in a module-level dict and survive individual tool call failures.

The four streaming tools (`subscribe_market`, `subscribe_orders`, `unsubscribe`, `list_subscriptions`) are documented in the MCP Tools section above.

## AGENT_INTEGRATION_GUIDE.md

A dedicated doc explaining how Claude Code should reason about and use the tools. Lives at repo root alongside `CLAUDE.md`. Content outline:

### How to discover markets

```
1. Use search_markets("topic") to find relevant markets by keyword
2. Use get_trending_markets(period="24h") to find active markets
3. Use get_market(slug=...) to get full detail including token_ids
4. Always extract token_id from tokens[] — never use conditionId with CLOB tools
```

### How to evaluate a market before trading

```
1. get_spread(token_id) — if spread > MAX_SPREAD_TOLERANCE, skip
2. get_orderbook(token_id) — check depth at the price level you want
3. analyze_market_opportunity(token_id) — get structured recommendation
4. get_risk_assessment(token_id, price, size, side) — validate before placing
```

### How to place an order safely

```
1. Always call get_risk_assessment first
2. If risk_score > 7, reconsider size or skip
3. Call place_order — if size > REQUIRE_CONFIRMATION_ABOVE_USD, you'll get
   a requires_confirmation response. Call confirm_order to proceed.
4. After placement, call get_order(order_id) to verify status
5. If status stays LIVE for more than a few seconds, the order is resting
   in the book — use cancel_order if you need to exit
```

### How to monitor positions

```
1. get_positions() — full portfolio with unrealized PnL
2. get_open_orders() — resting orders not yet filled
3. subscribe_orders() — stream fills and status changes in real time
4. analyze_portfolio() — concentration risk and suggestions
```

### Safety limit behaviour

```
- Orders above MAX_ORDER_SIZE_USD → rejected before API call with clear error
- Spread above MAX_SPREAD_TOLERANCE → rejected with spread value in error
- Market liquidity below MIN_LIQUIDITY_REQUIRED → rejected with liquidity value
- Orders above REQUIRE_CONFIRMATION_ABOVE_USD → returns confirmation prompt,
  not an error. Call confirm_order(confirmation_token) to proceed.
- Total exposure check happens against live positions — call get_portfolio_value
  first if unsure how close you are to the cap
```

### DEMO mode behaviour

```
- All market discovery, orderbook, pricing, and analysis tools work normally
- place_order, place_market_order, smart_trade, rebalance_position,
  cancel_order, cancel_all_orders → return DEMO_MODE error immediately
- get_positions, get_portfolio_value → return empty (no wallet)
- subscribe_market → works (market channel needs no auth)
- subscribe_orders → returns DEMO_MODE error (needs wallet)
```

### Common mistakes to avoid

```
- Passing conditionId to CLOB tools — always use token_id from tokens[]
- Placing orders without checking spread — wide spread = bad fill or no fill
- Not calling get_risk_assessment before large orders
- Ignoring the requires_confirmation response — it's not an error, call confirm_order
- Using subscribe_orders without send_heartbeat in long sessions
```

## What This Does NOT Do

- **No web UI.** Claude Code is the interface. The MCP server has no dashboard.
- **No strategy logic.** The server exposes raw Polymarket capabilities plus analysis tools. Claude Code reasons about what to trade. No built-in bots, no auto-trading signals.
- **No multi-wallet support.** One private key, one funder address, one Polymarket account per server instance.
- **No order history persistence.** Orders are queried from Polymarket's API in real time. No local database.
- **No geographic enforcement.** Polymarket geo-blocks certain regions at the API level. The server surfaces a clear error on 403 at startup but does not prevent you from trying — blocked requests fail at the API.
- **No testnet.** Polymarket has no public testnet. Order tests run on mainnet with $1 USDC and immediate cancellation.

## Estimated Size

| Area | Files | LOC |
|---|---|---|
| Core (types, auth, client, safety, demo, server) | 6 | ~550 |
| Market tools (markets, events, search, tags, trending) | 1 | ~280 |
| Orderbook tools (prices, book, spreads, history) | 1 | ~200 |
| Order tools (place, confirm, smart trade, rebalance, cancel, get) | 1 | ~350 |
| Position tools (positions, portfolio, activity) | 1 | ~150 |
| Analysis tools (opportunity, risk, compare, holders, portfolio) | 1 | ~300 |
| WebSocket streaming tools (subscribe, unsubscribe, list) | 1 | ~200 |
| Scripts (derive_creds, check_auth, approve_usdc, check_balance, list_positions) | 5 | ~300 |
| Tests | 7 | ~600 |
| Infra (CLAUDE.md, AGENT_INTEGRATION_GUIDE.md, install.sh, systemd, workflows, pyproject.toml) | 8 | ~350 |
| **Total** | **32** | **~3,280** |