"""Safety validation tests — no API calls needed."""

import json

from polymarket_mcp.safety import risk_assessment, validate_order
from polymarket_mcp.types import SafetyConfig


def _config() -> SafetyConfig:
    return SafetyConfig(
        max_order_size_usd=1000,
        max_total_exposure_usd=5000,
        max_position_per_market=2000,
        min_liquidity_required=10000,
        max_spread_tolerance=0.05,
        require_confirmation_above=500,
    )


def test_order_within_limits():
    result = validate_order(_config(), price=0.50, size=100, side="BUY")
    assert result["ok"] is True
    assert "requires_confirmation" not in result


def test_order_exceeds_max_size():
    result = validate_order(_config(), price=0.50, size=1500, side="BUY")
    assert "error" in result
    assert result["check"] == "order_size"


def test_order_requires_confirmation():
    result = validate_order(_config(), price=0.50, size=600, side="BUY")
    assert result["ok"] is True
    assert result["requires_confirmation"] is True
    assert "confirmation_token" in result


def test_spread_too_wide():
    result = validate_order(_config(), price=0.50, size=100, side="BUY", spread=0.10)
    assert "error" in result
    assert result["check"] == "spread"


def test_spread_within_tolerance():
    result = validate_order(_config(), price=0.50, size=100, side="BUY", spread=0.03)
    assert result["ok"] is True


def test_liquidity_too_low():
    result = validate_order(_config(), price=0.50, size=100, side="BUY", liquidity=5000)
    assert "error" in result
    assert result["check"] == "liquidity"


def test_exposure_exceeded():
    result = validate_order(
        _config(),
        price=0.50,
        size=100,
        side="BUY",
        current_exposure=4950,
    )
    assert "error" in result
    assert result["check"] == "exposure"


def test_exposure_within_limits():
    result = validate_order(
        _config(),
        price=0.50,
        size=100,
        side="BUY",
        current_exposure=1000,
    )
    assert result["ok"] is True


def test_risk_assessment_safe():
    result = json.loads(
        risk_assessment(
            _config(),
            price=0.50,
            size=100,
            side="BUY",
            spread=0.02,
            liquidity=20000,
        )
    )
    assert result["safe"] is True
    assert result["risk_score"] <= 3
    assert result["checks"]["order_size_ok"] is True
    assert result["checks"]["spread_ok"] is True
    assert result["checks"]["liquidity_ok"] is True


def test_risk_assessment_risky():
    result = json.loads(
        risk_assessment(
            _config(),
            price=0.50,
            size=1500,
            side="BUY",
            spread=0.10,
            liquidity=5000,
        )
    )
    assert result["safe"] is False
    assert result["risk_score"] >= 5
    assert len(result["warnings"]) >= 2
