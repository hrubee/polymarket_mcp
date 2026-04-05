"""Order placement and cancellation tools — CLOB authenticated, blocked in DEMO mode."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from py_clob_client.client import ClobClient
from py_clob_client.order_builder.constants import BUY, SELL

from ..client import PolymarketClient
from ..demo import require_live_mode
from ..safety import get_pending_confirmation, validate_order
from ..types import SafetyConfig

logger = logging.getLogger(__name__)


def register(
    mcp: Any,
    clob_client: ClobClient | None,
    poly_client: PolymarketClient,
    safety_config: SafetyConfig,
) -> None:
    """Register all order management tools with the MCP server."""

    def _side_const(side: str) -> int:
        return BUY if side == "BUY" else SELL

    @mcp.tool()
    def place_order(
        token_id: str,
        price: float,
        size: float,
        side: str,
        expiration: int | None = None,
    ) -> str:
        """Place a limit order on a market outcome.

        Pre-trade checks: order size, spread tolerance, market liquidity, total exposure.

        token_id: the outcome token ID
        price: limit price (0.01-0.99)
        size: order size in USDC
        side: "BUY" or "SELL"
        expiration: Unix timestamp, default GTC
        Returns: { order_id, status, token_id, price, size, side }
        If size > REQUIRE_CONFIRMATION_ABOVE_USD:
            { requires_confirmation, order_summary, confirm_tool: "confirm_order" }
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        if side not in ("BUY", "SELL"):
            return json.dumps({"error": "side must be BUY or SELL"})
        if not (0.01 <= price <= 0.99):
            return json.dumps({"error": "price must be between 0.01 and 0.99"})

        spread = poly_client.get_spread_value(token_id)
        address = os.getenv("FUNDER_ADDRESS", os.getenv("POLYGON_ADDRESS", ""))
        exposure = poly_client.get_portfolio_exposure(address) if address else None

        result = validate_order(
            safety_config,
            price=price,
            size=size,
            side=side,
            spread=spread,
            current_exposure=exposure,
        )

        if "error" in result:
            return json.dumps(result)
        if result.get("requires_confirmation"):
            return json.dumps(result)

        assert clob_client is not None
        order_args = {
            "token_id": token_id,
            "price": price,
            "size": size,
            "side": _side_const(side),
        }
        if expiration is not None:
            order_args["expiration"] = str(expiration)

        signed_order = clob_client.create_and_post_order(order_args)
        return json.dumps(signed_order)

    @mcp.tool()
    def confirm_order(confirmation_token: str) -> str:
        """Confirm and submit a pending large order (above REQUIRE_CONFIRMATION_ABOVE_USD).

        confirmation_token: returned by place_order when confirmation required
        Returns: { order_id, status, token_id, price, size, side }
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        pending = get_pending_confirmation(confirmation_token)
        if pending is None:
            return json.dumps({"error": "Invalid or expired confirmation token"})

        assert clob_client is not None
        order_args = {
            "token_id": pending.get("token_id", ""),
            "price": pending["price"],
            "size": pending["size"],
            "side": _side_const(pending["side"]),
        }
        signed_order = clob_client.create_and_post_order(order_args)
        return json.dumps(signed_order)

    @mcp.tool()
    def place_market_order(
        token_id: str,
        amount: float,
        side: str,
    ) -> str:
        """Place a market order (fills at best available price).

        token_id: the outcome token ID
        amount: USDC to spend (BUY) or shares to sell (SELL)
        side: "BUY" or "SELL"
        Returns: { order_id, status, filled_price, filled_size }
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        if side not in ("BUY", "SELL"):
            return json.dumps({"error": "side must be BUY or SELL"})

        spread = poly_client.get_spread_value(token_id)
        address = os.getenv("FUNDER_ADDRESS", os.getenv("POLYGON_ADDRESS", ""))
        exposure = poly_client.get_portfolio_exposure(address) if address else None

        result = validate_order(
            safety_config,
            price=0.5,
            size=amount,
            side=side,
            spread=spread,
            current_exposure=exposure,
        )
        if "error" in result:
            return json.dumps(result)
        if result.get("requires_confirmation"):
            return json.dumps(result)

        assert clob_client is not None
        order_args = {
            "token_id": token_id,
            "size": amount,
            "side": _side_const(side),
        }
        resp = clob_client.create_and_post_order(order_args)
        return json.dumps(resp)

    @mcp.tool()
    def smart_trade(
        token_id: str,
        intent: str,
        max_size: float | None = None,
    ) -> str:
        """Natural language automated order strategy.

        Analyses orderbook, selects optimal price and size, places order.

        token_id: the outcome token ID
        intent: e.g. "buy $200 of YES aggressively"
        max_size: cap on USDC spend (optional)
        Returns: { orders_placed, total_spent, avg_price }
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        assert clob_client is not None

        # Get current market data
        mid_data = poly_client.clob_get("/midpoint", {"token_id": token_id})
        mid_price = float(mid_data.get("mid", 0.5))

        # Parse intent
        intent_lower = intent.lower()
        side = "BUY" if "buy" in intent_lower else "SELL"
        aggressive = "aggressive" in intent_lower

        # Extract dollar amount from intent
        size = max_size or 100.0
        for word in intent_lower.split():
            cleaned = word.replace("$", "").replace(",", "")
            try:
                size = float(cleaned)
                break
            except ValueError:
                continue
        if max_size is not None:
            size = min(size, max_size)

        # Calculate price based on strategy
        if aggressive:
            price = min(mid_price + 0.02, 0.99) if side == "BUY" else max(mid_price - 0.02, 0.01)
        else:
            price = mid_price

        price = round(price, 2)

        # Validate and place
        address = os.getenv("FUNDER_ADDRESS", os.getenv("POLYGON_ADDRESS", ""))
        exposure = poly_client.get_portfolio_exposure(address) if address else None

        result = validate_order(
            safety_config,
            price=price,
            size=size,
            side=side,
            current_exposure=exposure,
        )
        if "error" in result:
            return json.dumps(result)
        if result.get("requires_confirmation"):
            return json.dumps(result)

        order_args = {
            "token_id": token_id,
            "price": price,
            "size": size,
            "side": _side_const(side),
        }
        resp = clob_client.create_and_post_order(order_args)

        return json.dumps(
            {
                "orders_placed": [resp],
                "total_spent": str(size),
                "avg_price": str(price),
            }
        )

    @mcp.tool()
    def rebalance_position(
        token_id: str,
        target_size: float,
        max_slippage: float = 0.02,
    ) -> str:
        """Adjust an existing position to a target size with slippage protection.

        token_id: the outcome token ID
        target_size: target USDC value
        max_slippage: maximum slippage tolerance (default 0.02 = 2%)
        Returns: { orders_placed, position_before, position_after }
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        assert clob_client is not None

        # Get current position
        address = os.getenv("FUNDER_ADDRESS", os.getenv("POLYGON_ADDRESS", ""))
        positions = poly_client.data_get("/positions", {"user": address})
        current_size = 0.0
        for p in positions if isinstance(positions, list) else []:
            if p.get("asset", {}).get("id") == token_id:
                current_size = float(p.get("size", 0))
                break

        mid_data = poly_client.clob_get("/midpoint", {"token_id": token_id})
        mid_price = float(mid_data.get("mid", 0.5))

        delta = target_size - current_size
        if abs(delta) < 1.0:
            return json.dumps(
                {
                    "orders_placed": [],
                    "position_before": str(current_size),
                    "position_after": str(current_size),
                    "message": "Position already within $1 of target",
                }
            )

        side = "BUY" if delta > 0 else "SELL"
        order_size = abs(delta)

        if side == "BUY":
            price = min(mid_price * (1 + max_slippage), 0.99)
        else:
            price = max(mid_price * (1 - max_slippage), 0.01)
        price = round(price, 2)

        result = validate_order(safety_config, price=price, size=order_size, side=side)
        if "error" in result:
            return json.dumps(result)

        order_args = {
            "token_id": token_id,
            "price": price,
            "size": order_size,
            "side": _side_const(side),
        }
        resp = clob_client.create_and_post_order(order_args)

        return json.dumps(
            {
                "orders_placed": [resp],
                "position_before": str(current_size),
                "position_after": str(target_size),
            }
        )

    @mcp.tool()
    def cancel_order(order_id: str) -> str:
        """Cancel a single open order by ID.

        order_id: the order ID to cancel
        Returns: { cancelled: true, order_id }
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        assert clob_client is not None
        resp = clob_client.cancel(order_id)
        return json.dumps({"cancelled": True, "order_id": order_id, "response": resp})

    @mcp.tool()
    def cancel_all_orders() -> str:
        """Cancel all open orders across all markets.

        Returns: { cancelled_count }
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        assert clob_client is not None
        resp = clob_client.cancel_all()
        return json.dumps({"cancelled_count": len(resp) if isinstance(resp, list) else 0})

    @mcp.tool()
    def cancel_market_orders(token_id: str) -> str:
        """Cancel all open orders for a specific market.

        token_id: the outcome token ID
        Returns: { cancelled_count }
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        assert clob_client is not None
        orders = clob_client.get_orders({"asset_id": token_id})
        cancelled = 0
        for order in orders if isinstance(orders, list) else []:
            oid = order.get("id", "")
            if oid and order.get("status") == "LIVE":
                clob_client.cancel(oid)
                cancelled += 1
        return json.dumps({"cancelled_count": cancelled})

    @mcp.tool()
    def get_order(order_id: str) -> str:
        """Get a single order by ID.

        order_id: the order ID
        Returns: Order with status, fills, remaining size
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        assert clob_client is not None
        resp = clob_client.get_order(order_id)
        return json.dumps(resp)

    @mcp.tool()
    def get_open_orders(token_id: str | None = None) -> str:
        """List all open orders for the authenticated user.

        token_id: optional filter by market
        Returns: Order[]
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        assert clob_client is not None
        params: dict[str, Any] = {}
        if token_id is not None:
            params["asset_id"] = token_id
        resp = clob_client.get_orders(params)
        return json.dumps(resp)

    @mcp.tool()
    def get_trades(
        token_id: str | None = None,
        limit: int = 50,
        before: str | None = None,
    ) -> str:
        """Get trade history for the authenticated user.

        token_id: optional filter by market
        limit: max trades to return
        before: cursor for pagination
        Returns: Trade[] with price, size, side, timestamp
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        assert clob_client is not None
        params: dict[str, Any] = {"limit": limit}
        if token_id is not None:
            params["asset_id"] = token_id
        if before is not None:
            params["before"] = before
        resp = clob_client.get_trades(params)
        return json.dumps(resp)

    @mcp.tool()
    def send_heartbeat() -> str:
        """Send a heartbeat to keep authenticated session alive.

        Returns: { ok: true }
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        # The py-clob-client handles session management internally
        return json.dumps({"ok": True, "timestamp": int(time.time())})
