"""WebSocket streaming tools — subscribe/unsubscribe for live data."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

import websockets

from ..demo import require_live_mode

logger = logging.getLogger(__name__)

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Active subscriptions
_subscriptions: dict[str, dict[str, Any]] = {}
_tasks: dict[str, asyncio.Task[None]] = {}


async def _market_listener(sub_id: str, token_id: str) -> None:
    """Listen to market WebSocket channel with auto-reconnect."""
    backoff = 1
    max_backoff = 60

    while sub_id in _subscriptions:
        try:
            async with websockets.connect(WS_URL) as ws:
                subscribe_msg = json.dumps(
                    {
                        "type": "subscribe",
                        "channel": "market",
                        "assets_ids": [token_id],
                    }
                )
                await ws.send(subscribe_msg)
                logger.info("WebSocket connected for subscription %s (token=%s)", sub_id, token_id)
                backoff = 1

                async for message in ws:
                    if sub_id not in _subscriptions:
                        break
                    data = json.loads(message)
                    _subscriptions[sub_id]["last_event"] = data
                    _subscriptions[sub_id]["event_count"] = (
                        _subscriptions[sub_id].get("event_count", 0) + 1
                    )
        except Exception as e:
            if sub_id not in _subscriptions:
                break
            logger.warning(
                "WebSocket disconnected for %s: %s, reconnecting in %ds",
                sub_id,
                e,
                backoff,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


async def _user_listener(sub_id: str) -> None:
    """Listen to user WebSocket channel for order updates."""
    backoff = 1
    max_backoff = 60

    while sub_id in _subscriptions:
        try:
            async with websockets.connect(WS_URL) as ws:
                subscribe_msg = json.dumps(
                    {
                        "type": "subscribe",
                        "channel": "user",
                    }
                )
                await ws.send(subscribe_msg)
                logger.info("WebSocket connected for user subscription %s", sub_id)
                backoff = 1

                async for message in ws:
                    if sub_id not in _subscriptions:
                        break
                    data = json.loads(message)
                    _subscriptions[sub_id]["last_event"] = data
                    _subscriptions[sub_id]["event_count"] = (
                        _subscriptions[sub_id].get("event_count", 0) + 1
                    )
        except Exception as e:
            if sub_id not in _subscriptions:
                break
            logger.warning(
                "User WebSocket disconnected for %s: %s, reconnecting in %ds",
                sub_id,
                e,
                backoff,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


def register(mcp: Any) -> None:
    """Register all WebSocket streaming tools with the MCP server."""

    @mcp.tool()
    def subscribe_market(token_id: str) -> str:
        """Open a WebSocket subscription to live orderbook + price updates for a token.

        Maintains connection with auto-reconnect and exponential backoff.

        token_id: the outcome token ID
        Returns: { subscription_id, status: "active" }
        """
        sub_id = str(uuid.uuid4())[:8]
        _subscriptions[sub_id] = {
            "token_id": token_id,
            "channel": "market",
            "status": "active",
            "created_at": int(time.time()),
            "event_count": 0,
        }

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        task = loop.create_task(_market_listener(sub_id, token_id))
        _tasks[sub_id] = task

        return json.dumps({"subscription_id": sub_id, "status": "active"})

    @mcp.tool()
    def subscribe_orders() -> str:
        """Subscribe to live order status updates for the authenticated wallet.

        Pushes events when orders are filled, cancelled, or matched.
        Returns: { subscription_id, status: "active" }
        """
        demo_err = require_live_mode()
        if demo_err:
            return demo_err

        sub_id = str(uuid.uuid4())[:8]
        _subscriptions[sub_id] = {
            "channel": "user",
            "status": "active",
            "created_at": int(time.time()),
            "event_count": 0,
        }

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        task = loop.create_task(_user_listener(sub_id))
        _tasks[sub_id] = task

        return json.dumps({"subscription_id": sub_id, "status": "active"})

    @mcp.tool()
    def unsubscribe(subscription_id: str) -> str:
        """Close an active WebSocket subscription.

        subscription_id: the ID returned by subscribe_market or subscribe_orders
        Returns: { unsubscribed: true, subscription_id }
        """
        if subscription_id not in _subscriptions:
            return json.dumps({"error": f"No subscription found with id={subscription_id}"})

        del _subscriptions[subscription_id]
        task = _tasks.pop(subscription_id, None)
        if task and not task.done():
            task.cancel()

        return json.dumps({"unsubscribed": True, "subscription_id": subscription_id})

    @mcp.tool()
    def list_subscriptions() -> str:
        """List all active WebSocket subscriptions.

        Returns: Subscription[] with token_id, channel, status, created_at
        """
        subs = []
        for sub_id, info in _subscriptions.items():
            subs.append(
                {
                    "subscription_id": sub_id,
                    "token_id": info.get("token_id"),
                    "channel": info.get("channel"),
                    "status": info.get("status"),
                    "created_at": info.get("created_at"),
                    "event_count": info.get("event_count", 0),
                }
            )
        return json.dumps(subs)
