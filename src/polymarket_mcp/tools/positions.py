"""Position and portfolio tools — Data API, requires wallet address."""

from __future__ import annotations

import json
import os
from typing import Any

from ..client import PolymarketClient
from ..demo import require_live_mode


def register(mcp: Any, poly_client: PolymarketClient) -> None:
    """Register all position and portfolio tools with the MCP server."""

    def _get_address() -> str:
        return os.getenv("FUNDER_ADDRESS", os.getenv("POLYGON_ADDRESS", ""))

    @mcp.tool()
    def get_positions() -> str:
        """Get current open positions for the authenticated wallet.

        Returns: Position[] with market, outcome, size, avg_price, current_price, pnl
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        address = _get_address()
        if not address:
            return json.dumps({"error": "No wallet address configured"})

        data = poly_client.data_get("/positions", {"user": address})
        return json.dumps(data)

    @mcp.tool()
    def get_closed_positions(
        limit: int = 50,
        offset: int = 0,
    ) -> str:
        """Get resolved/closed positions.

        limit: max positions to return
        offset: pagination offset
        Returns: ClosedPosition[] with settlement_price, profit_loss
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        address = _get_address()
        if not address:
            return json.dumps({"error": "No wallet address configured"})

        data = poly_client.data_get(
            "/positions",
            {"user": address, "status": "closed", "limit": limit, "offset": offset},
        )
        return json.dumps(data)

    @mcp.tool()
    def get_portfolio_value() -> str:
        """Get total value of all open positions.

        Returns: { total_value, positions_count }
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        address = _get_address()
        if not address:
            return json.dumps({"error": "No wallet address configured"})

        positions = poly_client.data_get("/positions", {"user": address})
        total = 0.0
        count = 0
        for p in positions if isinstance(positions, list) else []:
            size = float(p.get("size", 0))
            price = float(p.get("currentPrice", p.get("current_price", 0)))
            total += size * price
            count += 1

        return json.dumps(
            {
                "total_value": f"{total:.2f}",
                "positions_count": count,
            }
        )

    @mcp.tool()
    def get_activity(
        limit: int = 50,
        offset: int = 0,
    ) -> str:
        """Get recent trading activity for the wallet.

        limit: max entries to return
        offset: pagination offset
        Returns: Activity[] with type, market, amount, timestamp
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        address = _get_address()
        if not address:
            return json.dumps({"error": "No wallet address configured"})

        data = poly_client.data_get(
            "/activity",
            {"user": address, "limit": limit, "offset": offset},
        )
        return json.dumps(data)
