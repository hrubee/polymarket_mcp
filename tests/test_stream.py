"""WebSocket streaming tests."""

import json
import os

import pytest


@pytest.fixture
def stream_tools():
    class MockMCP:
        def __init__(self):
            self._tools = {}

        def tool(self):
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn

            return decorator

    mcp = MockMCP()
    from polymarket_mcp.tools.stream import _subscriptions, _tasks, register

    # Clear state between tests
    _subscriptions.clear()
    _tasks.clear()
    register(mcp)
    return mcp._tools


def test_list_subscriptions_empty(stream_tools):
    result = json.loads(stream_tools["list_subscriptions"]())
    assert result == []


def test_subscribe_market(stream_tools):
    result = json.loads(stream_tools["subscribe_market"](token_id="test123"))
    assert result["status"] == "active"
    assert "subscription_id" in result


def test_unsubscribe_invalid(stream_tools):
    result = json.loads(stream_tools["unsubscribe"](subscription_id="nonexistent"))
    assert "error" in result


def test_subscribe_and_unsubscribe(stream_tools):
    sub = json.loads(stream_tools["subscribe_market"](token_id="test123"))
    sub_id = sub["subscription_id"]

    # List should show one
    subs = json.loads(stream_tools["list_subscriptions"]())
    assert len(subs) == 1

    # Unsubscribe
    result = json.loads(stream_tools["unsubscribe"](subscription_id=sub_id))
    assert result["unsubscribed"] is True

    # List should be empty
    subs = json.loads(stream_tools["list_subscriptions"]())
    assert len(subs) == 0


def test_subscribe_orders_blocked_in_demo():
    os.environ["DEMO_MODE"] = "true"
    try:

        class MockMCP:
            def __init__(self):
                self._tools = {}

            def tool(self):
                def decorator(fn):
                    self._tools[fn.__name__] = fn
                    return fn

                return decorator

        mcp = MockMCP()
        from polymarket_mcp.tools.stream import register

        register(mcp)

        result = json.loads(mcp._tools["subscribe_orders"]())
        assert result["error"] == "DEMO_MODE"
    finally:
        os.environ.pop("DEMO_MODE", None)
