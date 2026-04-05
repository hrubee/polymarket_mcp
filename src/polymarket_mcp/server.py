"""MCP server entry point, tool registration, transport setup (stdio or SSE)."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from . import __version__
from .auth import (
    check_geo_block,
    init_clob_client,
    is_demo_mode,
    load_safety_config,
    validate_connection,
)
from .client import PolymarketClient
from .tools import analysis, markets, orderbook, orders, positions, stream

logger = logging.getLogger(__name__)

VERSION = __version__


def create_server() -> FastMCP:
    """Create and configure the MCP server with all tools."""
    load_dotenv()

    transport = os.getenv("MCP_TRANSPORT", "stdio")
    port = int(os.getenv("MCP_PORT", "3100"))

    log_level = os.getenv("LOG_LEVEL", "info").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    mcp_kwargs: dict[str, Any] = {"name": "polymarket-mcp"}
    if transport == "sse":
        mcp_kwargs["host"] = "0.0.0.0"
        mcp_kwargs["port"] = port

    mcp = FastMCP(**mcp_kwargs)

    demo = is_demo_mode()
    safety_config = load_safety_config()

    clob_client = None
    poly_client: PolymarketClient

    if demo:
        logger.info("Starting in DEMO mode — trading tools disabled")
        poly_client = PolymarketClient(clob_client=None)
    else:
        logger.info("Starting in LIVE mode — initializing wallet")
        clob_client = init_clob_client()
        validate_connection(clob_client)
        check_geo_block(clob_client)
        poly_client = PolymarketClient(clob_client=clob_client)

    # Register all tool modules
    markets.register(mcp)
    orderbook.register(mcp)
    orders.register(mcp, clob_client, poly_client, safety_config)
    positions.register(mcp, poly_client)
    analysis.register(mcp, poly_client, safety_config)
    stream.register(mcp)

    logger.info(
        "Polymarket MCP v%s ready — %s mode",
        VERSION,
        "DEMO" if demo else "LIVE",
    )
    return mcp


def main() -> None:
    """Entry point for the MCP server."""
    load_dotenv()
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    server = create_server()

    if transport in ("stdio", "sse"):
        if transport == "sse":
            logger.info("Starting SSE transport on port %s", os.getenv("MCP_PORT", "3100"))
        server.run(transport=transport)
    else:
        logger.error("Unknown MCP_TRANSPORT=%s (use 'stdio' or 'sse')", transport)
        sys.exit(1)


if __name__ == "__main__":
    main()
