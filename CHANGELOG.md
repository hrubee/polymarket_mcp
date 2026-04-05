# Changelog

## 0.1.0

Initial release.

- MCP server with stdio and SSE transport
- Market discovery tools (Gamma API): get_markets, get_market, get_events, get_event, get_trending_markets, search_markets, get_tags, get_market_tags
- Orderbook and pricing tools (CLOB public): get_orderbook, get_price, get_midpoint, get_spread, get_last_trade_price, get_price_history, get_fee_rate, get_tick_size
- Order management tools (CLOB authenticated): place_order, confirm_order, place_market_order, smart_trade, rebalance_position, cancel_order, cancel_all_orders, cancel_market_orders, get_order, get_open_orders, get_trades, send_heartbeat
- Position tools (Data API): get_positions, get_closed_positions, get_portfolio_value, get_activity
- Analysis tools: analyze_market_opportunity, get_risk_assessment, compare_markets, get_top_holders, analyze_portfolio
- WebSocket streaming: subscribe_market, subscribe_orders, unsubscribe, list_subscriptions
- Safety system with configurable limits (order size, exposure, spread, liquidity, confirmation threshold)
- DEMO mode for read-only operation without wallet
- Setup scripts: derive_creds, check_auth, approve_usdc, check_balance, list_positions
- systemd service file and install script
- CI/CD with GitHub Actions
