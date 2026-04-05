# Agent Integration Guide

How Claude Code should reason about and use Polymarket MCP tools.

## How to discover markets

1. Use `search_markets("topic")` to find relevant markets by keyword
2. Use `get_trending_markets(period="24h")` to find active markets
3. Use `get_market(slug=...)` to get full detail including token_ids
4. Always extract `token_id` from `tokens[]` — never use conditionId with CLOB tools

## How to evaluate a market before trading

1. `get_spread(token_id)` — if spread > MAX_SPREAD_TOLERANCE, skip
2. `get_orderbook(token_id)` — check depth at the price level you want
3. `analyze_market_opportunity(token_id)` — get structured recommendation
4. `get_risk_assessment(token_id, price, size, side)` — validate before placing

## How to place an order safely

1. Always call `get_risk_assessment` first
2. If `risk_score > 7`, reconsider size or skip
3. Call `place_order` — if size > REQUIRE_CONFIRMATION_ABOVE_USD, you'll get a `requires_confirmation` response. Call `confirm_order` to proceed.
4. After placement, call `get_order(order_id)` to verify status
5. If status stays LIVE for more than a few seconds, the order is resting in the book — use `cancel_order` if you need to exit

## How to monitor positions

1. `get_positions()` — full portfolio with unrealized PnL
2. `get_open_orders()` — resting orders not yet filled
3. `subscribe_orders()` — stream fills and status changes in real time
4. `analyze_portfolio()` — concentration risk and suggestions

## Safety limit behaviour

- Orders above `MAX_ORDER_SIZE_USD` → rejected before API call with clear error
- Spread above `MAX_SPREAD_TOLERANCE` → rejected with spread value in error
- Market liquidity below `MIN_LIQUIDITY_REQUIRED` → rejected with liquidity value
- Orders above `REQUIRE_CONFIRMATION_ABOVE_USD` → returns confirmation prompt, not an error. Call `confirm_order(confirmation_token)` to proceed.
- Total exposure check happens against live positions — call `get_portfolio_value` first if unsure how close you are to the cap

## DEMO mode behaviour

- All market discovery, orderbook, pricing, and analysis tools work normally
- `place_order`, `place_market_order`, `smart_trade`, `rebalance_position`, `cancel_order`, `cancel_all_orders` → return DEMO_MODE error immediately
- `get_positions`, `get_portfolio_value` → return empty (no wallet)
- `subscribe_market` → works (market channel needs no auth)
- `subscribe_orders` → returns DEMO_MODE error (needs wallet)

## Common mistakes to avoid

- Passing `conditionId` to CLOB tools — always use `token_id` from `tokens[]`
- Placing orders without checking spread — wide spread = bad fill or no fill
- Not calling `get_risk_assessment` before large orders
- Ignoring the `requires_confirmation` response — it's not an error, call `confirm_order`
- Using `subscribe_orders` without `send_heartbeat` in long sessions
