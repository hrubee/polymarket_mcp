"""All dataclasses for Polymarket MCP: Market, Order, Position, Trade, SafetyConfig."""

from dataclasses import dataclass, field


@dataclass
class Token:
    token_id: str  # Used in all CLOB API calls
    outcome: str  # "Yes" | "No"


@dataclass
class Market:
    id: str  # Condition ID (hex)
    question: str
    slug: str
    outcomes: list[str]  # e.g. ["Yes", "No"]
    outcome_prices: list[str]  # current prices, parallel to outcomes
    tokens: list[Token]  # one per outcome
    volume: str  # total USDC volume
    liquidity: str
    active: bool
    closed: bool
    end_date_iso: str  # ISO 8601 resolution date
    description: str | None
    tags: list[str] = field(default_factory=list)


@dataclass
class Order:
    id: str
    status: str  # "LIVE" | "MATCHED" | "DELAYED" | "CANCELLED" | "CLOSED"
    token_id: str
    price: str
    size: str  # original size
    size_matched: str  # filled size
    size_remaining: str
    side: str  # "BUY" | "SELL"
    type: str  # "LIMIT" | "MARKET" | "FOK" | "GTD"
    created_at: int  # Unix timestamp
    expiration: int  # Unix timestamp, 0 = GTC


@dataclass
class Position:
    market: str  # Condition ID
    question: str
    outcome: str
    token_id: str
    size: str  # shares held
    avg_price: str
    current_price: str
    unrealized_pnl: str
    realized_pnl: str


@dataclass
class Trade:
    trade_id: str
    token_id: str
    price: str
    size: str
    side: str  # "BUY" | "SELL"
    timestamp: int
    fee_rate_bps: str


@dataclass
class SafetyConfig:
    max_order_size_usd: float  # from MAX_ORDER_SIZE_USD
    max_total_exposure_usd: float  # from MAX_TOTAL_EXPOSURE_USD
    max_position_per_market: float  # from MAX_POSITION_SIZE_PER_MARKET
    min_liquidity_required: float  # from MIN_LIQUIDITY_REQUIRED
    max_spread_tolerance: float  # from MAX_SPREAD_TOLERANCE
    require_confirmation_above: float  # from REQUIRE_CONFIRMATION_ABOVE_USD
