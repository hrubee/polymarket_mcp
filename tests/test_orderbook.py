"""Orderbook and pricing tests — hits real CLOB API, works in DEMO mode."""

import json

import pytest


@pytest.fixture
def orderbook_tools():
    class MockMCP:
        def __init__(self):
            self._tools = {}

        def tool(self):
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn

            return decorator

    mcp = MockMCP()
    from polymarket_mcp.tools.orderbook import register

    register(mcp)
    return mcp._tools


@pytest.fixture
def sample_token_id(markets_tools_for_orderbook):
    """Get a real token_id from a live market."""
    result = json.loads(markets_tools_for_orderbook["get_markets"](limit=1, active=True))
    if not result:
        pytest.skip("No active markets available")
    market = result[0]
    tokens = market.get("tokens", [])
    if not tokens:
        # Try clobTokenIds
        clob_ids = market.get("clobTokenIds", "")
        if clob_ids:
            return clob_ids.split(",")[0].strip()
        pytest.skip("No token IDs in market response")
    return tokens[0].get("token_id", tokens[0].get("id", ""))


@pytest.fixture
def markets_tools_for_orderbook():
    class MockMCP:
        def __init__(self):
            self._tools = {}

        def tool(self):
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn

            return decorator

    mcp = MockMCP()
    from polymarket_mcp.tools.markets import register

    register(mcp)
    return mcp._tools


def test_get_price_invalid_side(orderbook_tools):
    result = json.loads(orderbook_tools["get_price"](token_id="fake", side="INVALID"))
    assert "error" in result


def test_get_price_history_invalid_interval(orderbook_tools):
    result = json.loads(orderbook_tools["get_price_history"](token_id="fake", interval="2h"))
    assert "error" in result
