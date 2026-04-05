"""Pre-trade validation enforced before any order reaches the API."""

from __future__ import annotations

import json
import secrets
from typing import Any

from .types import SafetyConfig

# Module-level store for pending confirmations
_pending_confirmations: dict[str, dict[str, Any]] = {}


def validate_order(
    config: SafetyConfig,
    price: float,
    size: float,
    side: str,
    spread: float | None = None,
    liquidity: float | None = None,
    current_exposure: float | None = None,
) -> dict[str, Any]:
    """Validate an order against safety limits.

    Returns a dict with:
      - {"ok": True} if the order passes all checks
      - {"ok": True, "requires_confirmation": True, ...} if above confirmation threshold
      - {"error": "...", "check": "..."} if a check fails
    """
    # Order size check
    if size > config.max_order_size_usd:
        return {
            "error": (
                f"Order size ${size} exceeds MAX_ORDER_SIZE_USD (${config.max_order_size_usd})"
            ),
            "check": "order_size",
        }

    # Spread check
    if spread is not None and spread > config.max_spread_tolerance:
        return {
            "error": (
                f"Spread {spread:.4f} exceeds MAX_SPREAD_TOLERANCE ({config.max_spread_tolerance})"
            ),
            "check": "spread",
        }

    # Liquidity check
    if liquidity is not None and liquidity < config.min_liquidity_required:
        return {
            "error": (
                f"Market liquidity ${liquidity} below MIN_LIQUIDITY_REQUIRED "
                f"(${config.min_liquidity_required})"
            ),
            "check": "liquidity",
        }

    # Exposure check
    if current_exposure is not None:
        projected = current_exposure + size
        if projected > config.max_total_exposure_usd:
            return {
                "error": (
                    f"Projected exposure ${projected} exceeds MAX_TOTAL_EXPOSURE_USD "
                    f"(${config.max_total_exposure_usd})"
                ),
                "check": "exposure",
            }

    # Confirmation threshold
    if size > config.require_confirmation_above:
        token = secrets.token_hex(16)
        order_summary = {
            "price": price,
            "size": size,
            "side": side,
        }
        _pending_confirmations[token] = order_summary
        return {
            "ok": True,
            "requires_confirmation": True,
            "order_summary": order_summary,
            "confirmation_token": token,
            "confirm_tool": "confirm_order",
        }

    return {"ok": True}


def get_pending_confirmation(token: str) -> dict[str, Any] | None:
    """Retrieve and consume a pending confirmation."""
    return _pending_confirmations.pop(token, None)


def risk_assessment(
    config: SafetyConfig,
    price: float,
    size: float,
    side: str,
    spread: float | None = None,
    liquidity: float | None = None,
    current_exposure: float | None = None,
) -> str:
    """Score a potential order for risk. Returns JSON."""
    warnings: list[str] = []
    risk_score = 1

    order_size_ok = size <= config.max_order_size_usd
    if not order_size_ok:
        warnings.append(f"Order size ${size} exceeds limit ${config.max_order_size_usd}")
        risk_score += 3

    spread_ok = True
    if spread is not None:
        spread_ok = spread <= config.max_spread_tolerance
        if not spread_ok:
            warnings.append(f"Spread {spread:.4f} exceeds tolerance {config.max_spread_tolerance}")
            risk_score += 2
        elif spread > config.max_spread_tolerance * 0.7:
            warnings.append(f"Spread {spread:.4f} approaching tolerance limit")
            risk_score += 1

    liquidity_ok = True
    if liquidity is not None:
        liquidity_ok = liquidity >= config.min_liquidity_required
        if not liquidity_ok:
            warnings.append(
                f"Liquidity ${liquidity} below minimum ${config.min_liquidity_required}"
            )
            risk_score += 2

    exposure_ok = True
    if current_exposure is not None:
        projected = current_exposure + size
        exposure_ok = projected <= config.max_total_exposure_usd
        if not exposure_ok:
            warnings.append(
                f"Projected exposure ${projected} exceeds limit ${config.max_total_exposure_usd}"
            )
            risk_score += 3

    risk_score = min(risk_score, 10)

    return json.dumps(
        {
            "safe": order_size_ok and spread_ok and liquidity_ok and exposure_ok,
            "risk_score": risk_score,
            "checks": {
                "order_size_ok": order_size_ok,
                "liquidity_ok": liquidity_ok,
                "spread_ok": spread_ok,
                "exposure_ok": exposure_ok,
            },
            "warnings": warnings,
        }
    )
