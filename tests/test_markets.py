"""Market discovery tests — hits real Gamma API, works in DEMO mode."""

import json

import pytest


@pytest.fixture
def markets_tools():
    """Create a minimal MCP-like object and register market tools."""

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


def test_get_markets(markets_tools):
    result = json.loads(markets_tools["get_markets"](limit=5))
    assert isinstance(result, list)
    assert len(result) <= 5
    if result:
        assert "question" in result[0] or "id" in result[0]


def test_get_markets_with_search(markets_tools):
    result = json.loads(markets_tools["get_markets"](limit=5, search="election"))
    assert isinstance(result, list)


def test_get_trending_markets(markets_tools):
    result = json.loads(markets_tools["get_trending_markets"](period="24h", limit=5))
    assert isinstance(result, list)


def test_get_trending_invalid_period(markets_tools):
    result = json.loads(markets_tools["get_trending_markets"](period="1y"))
    assert "error" in result


def test_search_markets(markets_tools):
    result = json.loads(markets_tools["search_markets"](query="bitcoin", limit=5))
    assert isinstance(result, list)


def test_get_events(markets_tools):
    result = json.loads(markets_tools["get_events"](limit=5))
    assert isinstance(result, list)


def test_get_tags(markets_tools):
    result = json.loads(markets_tools["get_tags"]())
    assert isinstance(result, list)


def test_get_market_requires_id_or_slug(markets_tools):
    result = json.loads(markets_tools["get_market"]())
    assert "error" in result
