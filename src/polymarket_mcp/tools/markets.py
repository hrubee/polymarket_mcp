"""Market discovery tools — Gamma API, no auth, works in DEMO mode."""

from __future__ import annotations

import json
from typing import Any

import httpx

GAMMA_BASE = "https://gamma-api.polymarket.com"


def _gamma_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{GAMMA_BASE}{path}"
    with httpx.Client(timeout=15) as client:
        r = client.get(url, params=params)
        r.raise_for_status()
        return r.json()


def register(mcp: Any) -> None:
    """Register all market discovery tools with the MCP server."""

    @mcp.tool()
    def get_markets(
        limit: int = 20,
        offset: int = 0,
        active: bool | None = None,
        closed: bool | None = None,
        tag: str | None = None,
        search: str | None = None,
    ) -> str:
        """List tradeable markets with optional filters.

        Returns a JSON array of Market objects. Each market includes:
        id (conditionId), question, slug, outcomes, outcome_prices, tokens
        (with token_id per outcome for CLOB calls), volume, liquidity,
        active, closed, end_date_iso, description, tags.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if active is not None:
            params["active"] = str(active).lower()
        if closed is not None:
            params["closed"] = str(closed).lower()
        if tag is not None:
            params["tag"] = tag
        if search is not None:
            params["_c"] = search

        data = _gamma_get("/markets", params)
        return json.dumps(data)

    @mcp.tool()
    def get_market(
        id: str | None = None,
        slug: str | None = None,
    ) -> str:
        """Get a single market by condition ID or slug.

        Exactly one of id or slug must be provided.

        Returns Market detail including outcomes, resolution criteria,
        end_date_iso, tokens[] (use tokens[i].token_id for CLOB tools).
        """
        if id is None and slug is None:
            return json.dumps({"error": "Provide either id or slug"})
        if id is not None and slug is not None:
            return json.dumps({"error": "Provide only one of id or slug, not both"})

        if id is not None:
            data = _gamma_get(f"/markets/{id}")
        else:
            markets = _gamma_get("/markets", {"slug": slug})
            if not markets:
                return json.dumps({"error": f"No market found with slug={slug!r}"})
            data = markets[0]

        return json.dumps(data)

    @mcp.tool()
    def get_events(
        limit: int = 20,
        offset: int = 0,
        tag: str | None = None,
        active: bool | None = None,
    ) -> str:
        """List events (groups of related markets).

        Returns a JSON array of Event objects, each containing a markets[]
        array with all markets in that event.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if tag is not None:
            params["tag"] = tag
        if active is not None:
            params["active"] = str(active).lower()

        data = _gamma_get("/events", params)
        return json.dumps(data)

    @mcp.tool()
    def get_event(
        id: str | None = None,
        slug: str | None = None,
    ) -> str:
        """Get a single event by ID or slug.

        Exactly one of id or slug must be provided.
        Returns Event detail with all markets in the event.
        """
        if id is None and slug is None:
            return json.dumps({"error": "Provide either id or slug"})
        if id is not None and slug is not None:
            return json.dumps({"error": "Provide only one of id or slug, not both"})

        if id is not None:
            data = _gamma_get(f"/events/{id}")
        else:
            events = _gamma_get("/events", {"slug": slug})
            if not events:
                return json.dumps({"error": f"No event found with slug={slug!r}"})
            data = events[0]

        return json.dumps(data)

    @mcp.tool()
    def get_trending_markets(
        period: str = "24h",
        limit: int = 20,
    ) -> str:
        """Get markets sorted by volume over a time window.

        period: "24h" | "7d" | "30d"
        Returns Market[] sorted by volume descending.
        """
        if period not in ("24h", "7d", "30d"):
            return json.dumps({"error": "period must be one of: 24h, 7d, 30d"})

        params: dict[str, Any] = {
            "limit": limit,
            "active": "true",
            "order": "volume",
            "ascending": "false",
        }
        if period == "7d":
            params["order"] = "volume1Week"
        elif period == "30d":
            params["order"] = "volume1Month"

        data = _gamma_get("/markets", params)
        return json.dumps(data)

    @mcp.tool()
    def search_markets(
        query: str,
        limit: int = 20,
    ) -> str:
        """Full-text search across markets, events, and profiles.

        query: required search string
        Returns SearchResult[] with type ("market" | "event") and the
        matched entity object.
        """
        results: list[dict[str, Any]] = []

        market_data = _gamma_get("/markets", {"_c": query, "limit": limit})
        for m in market_data if isinstance(market_data, list) else []:
            results.append({"type": "market", "entity": m})

        if len(results) < limit:
            remaining = limit - len(results)
            event_data = _gamma_get("/events", {"_c": query, "limit": remaining})
            for e in event_data if isinstance(event_data, list) else []:
                results.append({"type": "event", "entity": e})

        return json.dumps(results[:limit])

    @mcp.tool()
    def get_tags() -> str:
        """List all market tags/categories.

        Returns Tag[] with id, label, slug.
        """
        data = _gamma_get("/tags")
        return json.dumps(data)

    @mcp.tool()
    def get_market_tags(market_id: str) -> str:
        """Get tags for a specific market.

        market_id: the conditionId (hex) of the market
        Returns Tag[] with id, label, slug.
        """
        data = _gamma_get(f"/markets/{market_id}/tags")
        return json.dumps(data)
