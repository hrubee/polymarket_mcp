"""Position tests — requires wallet credentials."""

import json
import os

import pytest


@pytest.fixture
def position_tools():
    from dotenv import load_dotenv

    load_dotenv()

    if os.getenv("DEMO_MODE", "false").lower() == "true":
        pytest.skip("Position tests require DEMO_MODE=false")

    from polymarket_mcp.client import PolymarketClient

    poly = PolymarketClient()

    class MockMCP:
        def __init__(self):
            self._tools = {}

        def tool(self):
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn

            return decorator

    mcp = MockMCP()
    from polymarket_mcp.tools.positions import register

    register(mcp, poly)
    return mcp._tools


def test_demo_mode_blocks_positions():
    """In DEMO mode, position tools return DEMO_MODE error."""
    os.environ["DEMO_MODE"] = "true"
    try:
        from polymarket_mcp.client import PolymarketClient

        poly = PolymarketClient()

        class MockMCP:
            def __init__(self):
                self._tools = {}

            def tool(self):
                def decorator(fn):
                    self._tools[fn.__name__] = fn
                    return fn

                return decorator

        mcp = MockMCP()
        from polymarket_mcp.tools.positions import register

        register(mcp, poly)

        result = json.loads(mcp._tools["get_positions"]())
        assert result["error"] == "DEMO_MODE"
    finally:
        os.environ.pop("DEMO_MODE", None)
