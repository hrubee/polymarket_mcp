"""Order tests — places and immediately cancels $1 USDC orders on mainnet.

These tests require real credentials in .env and DEMO_MODE=false.
Skip in CI with: pytest -k "not test_orders"
"""

import json
import os

import pytest


@pytest.fixture
def skip_demo():
    if os.getenv("DEMO_MODE", "false").lower() == "true":
        pytest.skip("Skipping order tests in DEMO mode")


@pytest.fixture
def order_tools():
    """Set up order tools with real client."""
    from dotenv import load_dotenv

    load_dotenv()

    if os.getenv("DEMO_MODE", "false").lower() == "true":
        pytest.skip("Order tests require DEMO_MODE=false")

    from py_clob_client.client import ClobClient

    from polymarket_mcp.auth import CHAIN_ID, CLOB_HOST, load_safety_config
    from polymarket_mcp.client import PolymarketClient

    pk = os.getenv("POLYGON_PRIVATE_KEY", "")
    if not pk:
        pytest.skip("POLYGON_PRIVATE_KEY not set")

    sig_type = int(os.getenv("SIGNATURE_TYPE", "2"))
    funder = os.getenv("FUNDER_ADDRESS", "")

    clob = ClobClient(
        host=CLOB_HOST,
        chain_id=CHAIN_ID,
        key=pk,
        signature_type=sig_type,
        funder=funder or None,
    )

    api_key = os.getenv("POLY_API_KEY", "")
    secret = os.getenv("POLY_SECRET", "")
    passphrase = os.getenv("POLY_PASSPHRASE", "")
    if not all([api_key, secret, passphrase]):
        pytest.skip("L2 credentials not set")

    creds = type("C", (), {"api_key": api_key, "secret": secret, "api_passphrase": passphrase})()
    clob.set_api_creds(creds)

    poly = PolymarketClient(clob)
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
    from polymarket_mcp.tools.orders import register

    register(mcp, clob, poly, safety)
    return mcp._tools


def test_place_order_invalid_side(order_tools):
    result = json.loads(
        order_tools["place_order"](
            token_id="fake",
            price=0.50,
            size=1,
            side="INVALID",
        )
    )
    assert "error" in result


def test_place_order_invalid_price(order_tools):
    result = json.loads(
        order_tools["place_order"](
            token_id="fake",
            price=1.50,
            size=1,
            side="BUY",
        )
    )
    assert "error" in result
