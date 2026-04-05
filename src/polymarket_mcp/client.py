"""Polymarket client wrapper aggregating CLOB, Gamma, and Data API calls."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from py_clob_client.client import ClobClient

logger = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
DATA_BASE = "https://data-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"


class PolymarketClient:
    """Unified client for all three Polymarket APIs."""

    def __init__(self, clob_client: ClobClient | None = None) -> None:
        self.clob = clob_client
        self._http = httpx.Client(timeout=15)

    def close(self) -> None:
        self._http.close()

    # --- Gamma API (no auth) ---

    def gamma_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        r = self._http.get(f"{GAMMA_BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()

    # --- Data API (no auth) ---

    def data_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        r = self._http.get(f"{DATA_BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()

    # --- CLOB public (no auth) ---

    def clob_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        r = self._http.get(f"{CLOB_BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()

    # --- CLOB authenticated (requires clob_client) ---

    def get_spread_value(self, token_id: str) -> float | None:
        """Get numeric spread for a token. Returns None on error."""
        try:
            data = self.clob_get("/spread", {"token_id": token_id})
            return float(data.get("spread", 0))
        except Exception:
            return None

    def get_liquidity_value(self, market_id: str) -> float | None:
        """Get numeric liquidity for a market from Gamma. Returns None on error."""
        try:
            data = self.gamma_get(f"/markets/{market_id}")
            return float(data.get("liquidity", 0))
        except Exception:
            return None

    def get_portfolio_exposure(self, address: str) -> float:
        """Calculate total portfolio exposure from positions."""
        try:
            positions = self.data_get("/positions", {"user": address})
            total = 0.0
            for p in positions if isinstance(positions, list) else []:
                size = float(p.get("size", 0))
                price = float(p.get("currentPrice", 0))
                total += size * price
            return total
        except Exception:
            return 0.0
