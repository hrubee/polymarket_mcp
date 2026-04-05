"""Analysis tools — synthesized from Gamma + CLOB data, no auth, works in DEMO mode."""

from __future__ import annotations

import json
import os
from typing import Any

from ..client import PolymarketClient
from ..safety import risk_assessment
from ..types import SafetyConfig


def register(
    mcp: Any,
    poly_client: PolymarketClient,
    safety_config: SafetyConfig,
) -> None:
    """Register all analysis tools with the MCP server."""

    @mcp.tool()
    def analyze_market_opportunity(
        token_id: str,
        strategy: str = "mid",
    ) -> str:
        """Analyze a market for trading opportunity.

        token_id: the outcome token ID
        strategy: "aggressive" | "passive" | "mid" (default "mid")
        Returns: { recommendation, confidence, suggested_price, suggested_size,
                   reasoning, spread, liquidity, risk_score }
        """
        if strategy not in ("aggressive", "passive", "mid"):
            return json.dumps({"error": "strategy must be: aggressive, passive, or mid"})

        # Gather market data
        try:
            book = poly_client.clob_get("/book", {"token_id": token_id})
            mid_data = poly_client.clob_get("/midpoint", {"token_id": token_id})
            spread_data = poly_client.clob_get("/spread", {"token_id": token_id})
        except Exception as e:
            return json.dumps({"error": f"Failed to fetch market data: {e}"})

        mid_price = float(mid_data.get("mid", 0.5))
        spread = float(spread_data.get("spread", 0))

        bids = book.get("bids", [])
        asks = book.get("asks", [])
        bid_depth = sum(float(b.get("size", 0)) for b in bids)
        ask_depth = sum(float(a.get("size", 0)) for a in asks)
        total_liquidity = bid_depth + ask_depth

        # Analyze
        risk_score = 1
        warnings: list[str] = []

        if spread > safety_config.max_spread_tolerance:
            risk_score += 3
            warnings.append("Wide spread")
        if total_liquidity < safety_config.min_liquidity_required:
            risk_score += 2
            warnings.append("Low liquidity")

        # Determine recommendation
        if risk_score >= 6:
            recommendation = "HOLD"
            confidence = "low"
        elif mid_price < 0.3:
            recommendation = "BUY"
            confidence = "medium" if risk_score <= 3 else "low"
        elif mid_price > 0.7:
            recommendation = "SELL"
            confidence = "medium" if risk_score <= 3 else "low"
        else:
            recommendation = "HOLD"
            confidence = "medium"

        # Suggested price based on strategy
        if strategy == "aggressive":
            suggested = mid_price + 0.01 if recommendation == "BUY" else mid_price - 0.01
        elif strategy == "passive":
            suggested = mid_price - 0.02 if recommendation == "BUY" else mid_price + 0.02
        else:
            suggested = mid_price
        suggested = round(max(0.01, min(0.99, suggested)), 2)

        # Suggested size (conservative)
        suggested_size = min(100.0, safety_config.max_order_size_usd * 0.1)

        risk_score = min(risk_score, 10)

        return json.dumps(
            {
                "recommendation": recommendation,
                "confidence": confidence,
                "suggested_price": str(suggested),
                "suggested_size": str(suggested_size),
                "reasoning": (
                    f"Mid={mid_price:.3f}, spread={spread:.4f}, "
                    f"bid_depth={bid_depth:.0f}, ask_depth={ask_depth:.0f}. "
                    + ("; ".join(warnings) if warnings else "Market looks healthy.")
                ),
                "spread": str(spread),
                "liquidity": str(total_liquidity),
                "risk_score": risk_score,
            }
        )

    @mcp.tool()
    def get_risk_assessment(
        token_id: str,
        price: float,
        size: float,
        side: str,
    ) -> str:
        """Score a potential order for risk before placing.

        token_id: the outcome token ID
        price: intended order price
        size: intended order size in USDC
        side: "BUY" or "SELL"
        Returns: { safe, risk_score, checks: {...}, warnings: [...] }
        """
        spread = poly_client.get_spread_value(token_id)
        address = os.getenv("FUNDER_ADDRESS", os.getenv("POLYGON_ADDRESS", ""))
        exposure = poly_client.get_portfolio_exposure(address) if address else None

        return risk_assessment(
            safety_config,
            price=price,
            size=size,
            side=side,
            spread=spread,
            current_exposure=exposure,
        )

    @mcp.tool()
    def compare_markets(token_ids: list[str]) -> str:
        """Side-by-side comparison of multiple markets.

        token_ids: list of token IDs (max 5)
        Returns: ComparisonResult[] with price, spread, volume, liquidity per token
        """
        if len(token_ids) > 5:
            return json.dumps({"error": "Maximum 5 token IDs allowed"})

        results: list[dict[str, Any]] = []
        for tid in token_ids:
            try:
                mid = poly_client.clob_get("/midpoint", {"token_id": tid})
                spread = poly_client.clob_get("/spread", {"token_id": tid})
                book = poly_client.clob_get("/book", {"token_id": tid})

                bids = book.get("bids", [])
                asks = book.get("asks", [])
                depth = sum(float(b.get("size", 0)) for b in bids) + sum(
                    float(a.get("size", 0)) for a in asks
                )

                results.append(
                    {
                        "token_id": tid,
                        "midpoint": mid.get("mid", "N/A"),
                        "spread": spread.get("spread", "N/A"),
                        "book_depth": f"{depth:.0f}",
                    }
                )
            except Exception as e:
                results.append({"token_id": tid, "error": str(e)})

        return json.dumps(results)

    @mcp.tool()
    def get_top_holders(
        token_id: str,
        limit: int = 20,
    ) -> str:
        """Get the largest position holders for a market.

        token_id: the outcome token ID
        limit: max holders to return
        Returns: Holder[] with address, size, avg_price
        """
        try:
            data = poly_client.data_get(
                "/positions",
                {"asset_id": token_id, "limit": limit, "order": "size", "ascending": "false"},
            )
            return json.dumps(data)
        except Exception as e:
            return json.dumps({"error": f"Failed to fetch holders: {e}"})

    @mcp.tool()
    def analyze_portfolio(
        strategy: str = "balanced",
    ) -> str:
        """Analyse the current portfolio for risk and diversification.

        strategy: "conservative" | "balanced" | "aggressive"
        Returns: { total_value, concentration_risk, liquidity_risk,
                   suggestions, diversification_score }
        """
        if strategy not in ("conservative", "balanced", "aggressive"):
            return json.dumps({"error": "strategy must be: conservative, balanced, or aggressive"})

        address = os.getenv("FUNDER_ADDRESS", os.getenv("POLYGON_ADDRESS", ""))
        if not address:
            return json.dumps(
                {
                    "total_value": "0",
                    "concentration_risk": "unknown",
                    "liquidity_risk": "unknown",
                    "suggestions": ["Configure wallet address to analyze portfolio"],
                    "diversification_score": 0,
                }
            )

        try:
            positions = poly_client.data_get("/positions", {"user": address})
        except Exception:
            positions = []

        if not isinstance(positions, list) or not positions:
            return json.dumps(
                {
                    "total_value": "0",
                    "concentration_risk": "none",
                    "liquidity_risk": "none",
                    "suggestions": ["No open positions found"],
                    "diversification_score": 10,
                }
            )

        # Calculate metrics
        values: list[float] = []
        for p in positions:
            size = float(p.get("size", 0))
            price = float(p.get("currentPrice", p.get("current_price", 0)))
            values.append(size * price)

        total = sum(values)
        max_position = max(values) if values else 0
        num_positions = len(values)

        # Concentration
        concentration_pct = (max_position / total * 100) if total > 0 else 0
        if concentration_pct > 50:
            concentration_risk = "high"
        elif concentration_pct > 30:
            concentration_risk = "medium"
        else:
            concentration_risk = "low"

        # Diversification score
        div_score = min(10, num_positions * 2)
        if concentration_pct > 50:
            div_score = max(1, div_score - 3)

        # Suggestions
        suggestions: list[str] = []
        if concentration_pct > 40:
            suggestions.append(
                f"Largest position is {concentration_pct:.0f}% of portfolio — consider reducing"
            )
        if num_positions < 3:
            suggestions.append("Low diversification — consider spreading across more markets")
        if total > safety_config.max_total_exposure_usd * 0.8:
            suggestions.append("Approaching maximum exposure limit")

        thresholds = {
            "conservative": 0.6,
            "balanced": 0.8,
            "aggressive": 1.0,
        }
        limit_pct = thresholds[strategy]
        if total > safety_config.max_total_exposure_usd * limit_pct:
            suggestions.append(
                f"Exposure exceeds {strategy} threshold "
                f"(${total:.0f} / ${safety_config.max_total_exposure_usd * limit_pct:.0f})"
            )

        return json.dumps(
            {
                "total_value": f"{total:.2f}",
                "concentration_risk": concentration_risk,
                "liquidity_risk": "low" if total < 1000 else "medium",
                "suggestions": suggestions if suggestions else ["Portfolio looks healthy"],
                "diversification_score": div_score,
            }
        )
