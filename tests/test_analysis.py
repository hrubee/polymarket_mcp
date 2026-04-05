"""Analysis tool tests — works in DEMO mode (read-only data)."""

import json

import pytest

from polymarket_mcp.auth import load_safety_config
from polymarket_mcp.client import PolymarketClient


@pytest.fixture
def analysis_tools():
    poly = PolymarketClient()
    safety = load_safety_config()

    class MockMCP:
        def __init__(self):
            self._tools = {}

        def tool(self):
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn

            return decorator

    mcp = MockMCP()
    from polymarket_mcp.tools.analysis import register

    register(mcp, poly, safety)
    return mcp._tools


def test_analyze_market_invalid_strategy(analysis_tools):
    result = json.loads(
        analysis_tools["analyze_market_opportunity"](
            token_id="fake",
            strategy="yolo",
        )
    )
    assert "error" in result


def test_compare_markets_too_many(analysis_tools):
    result = json.loads(
        analysis_tools["compare_markets"](
            token_ids=["a", "b", "c", "d", "e", "f"],
        )
    )
    assert "error" in result


def test_analyze_portfolio_invalid_strategy(analysis_tools):
    result = json.loads(analysis_tools["analyze_portfolio"](strategy="yolo"))
    assert "error" in result


def test_analyze_portfolio_no_wallet(analysis_tools):
    """Without wallet address, returns empty portfolio."""
    import os

    old = os.environ.pop("FUNDER_ADDRESS", None)
    old2 = os.environ.pop("POLYGON_ADDRESS", None)
    try:
        result = json.loads(analysis_tools["analyze_portfolio"](strategy="balanced"))
        assert result["total_value"] == "0"
    finally:
        if old:
            os.environ["FUNDER_ADDRESS"] = old
        if old2:
            os.environ["POLYGON_ADDRESS"] = old2
