"""Orderbook and pricing tools — CLOB public endpoints, no auth, works in DEMO mode."""

from __future__ import annotations

import json
from typing import Any

import httpx

CLOB_BASE = "https://clob.polymarket.com"


def _clob_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{CLOB_BASE}{path}"
    with httpx.Client(timeout=15) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        return r.json()


def register(mcp: Any) -> None:
    """Register all orderbook and pricing tools with the MCP server."""

    @mcp.tool()
    def get_orderbook(token_id: str) -> str:
        """Get full orderbook depth for a market outcome token.

        token_id: the outcome token ID (from tokens[].token_id in get_market).
        Returns { bids: PriceLevel[], asks: PriceLevel[], market, asset_id }
        where each PriceLevel has { price, size }.

        Note: Always use token_id, never conditionId — CLOB will return 400
        if you pass the conditionId.
        """
        data = _clob_get("/book", {"token_id": token_id})
        return json.dumps(data)

    @mcp.tool()
    def get_price(
        token_id: str,
        side: str,
    ) -> str:
        """Get current best price for a token.

        token_id: the outcome token ID
        side: "BUY" or "SELL"
        Returns { price: string }
        """
        if side not in ("BUY", "SELL"):
            return json.dumps({"error": "side must be BUY or SELL"})
        data = _clob_get("/price", {"token_id": token_id, "side": side})
        return json.dumps(data)

    @mcp.tool()
    def get_midpoint(token_id: str) -> str:
        """Get midpoint price (average of best bid and ask).

        token_id: the outcome token ID
        Returns { mid: string }
        """
        data = _clob_get("/midpoint", {"token_id": token_id})
        return json.dumps(data)

    @mcp.tool()
    def get_spread(token_id: str) -> str:
        """Get spread between best bid and ask.

        token_id: the outcome token ID
        Returns { spread: string }
        """
        data = _clob_get("/spread", {"token_id": token_id})
        return json.dumps(data)

    @mcp.tool()
    def get_last_trade_price(token_id: str) -> str:
        """Get the price of the most recent trade for a token.

        token_id: the outcome token ID
        Returns { price: string }
        """
        data = _clob_get("/last-trade-price", {"token_id": token_id})
        return json.dumps(data)

    @mcp.tool()
    def get_price_history(
        token_id: str,
        interval: str | None = None,
        start_ts: int | None = None,
        end_ts: int | None = None,
    ) -> str:
        """Get historical price data for a token.

        token_id: the outcome token ID
        interval: "1m" | "5m" | "1h" | "6h" | "1d" (optional)
        start_ts: Unix timestamp start (optional)
        end_ts: Unix timestamp end (optional)
        Returns PricePoint[] with t (timestamp) and p (price).
        """
        valid_intervals = ("1m", "5m", "1h", "6h", "1d")
        if interval is not None and interval not in valid_intervals:
            return json.dumps({"error": f"interval must be one of: {', '.join(valid_intervals)}"})

        params: dict[str, Any] = {"market": token_id, "fidelity": 60}
        if interval is not None:
            fidelity_map = {"1m": 1, "5m": 5, "1h": 60, "6h": 360, "1d": 1440}
            params["fidelity"] = fidelity_map[interval]
        if start_ts is not None:
            params["startTs"] = start_ts
        if end_ts is not None:
            params["endTs"] = end_ts

        data = _clob_get("/prices-history", params)
        return json.dumps(data)

    @mcp.tool()
    def get_fee_rate(token_id: str) -> str:
        """Get current maker/taker fee rates for a token.

        token_id: the outcome token ID
        Returns { maker_amount: string, taker_amount: string }
        """
        data = _clob_get("/neg-risk/fee-rate", {"token_id": token_id})
        return json.dumps(data)

    @mcp.tool()
    def get_tick_size(token_id: str) -> str:
        """Get minimum price increment (tick size) for a token.

        token_id: the outcome token ID
        Returns { minimum_tick_size: string }
        """
        data = _clob_get("/tick-size", {"token_id": token_id})
        return json.dumps(data)
