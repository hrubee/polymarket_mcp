"""MCP server entry point, tool registration, transport setup (stdio or SSE)."""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server

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


def create_server() -> Server:
    """Create and configure the MCP server with all tools."""
    load_dotenv()

    log_level = os.getenv("LOG_LEVEL", "info").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    mcp = Server("polymarket-mcp")

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


async def run_stdio(server: Server) -> None:
    """Run the server using stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Entry point for the MCP server."""
    import asyncio

    server = create_server()
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "stdio":
        asyncio.run(run_stdio(server))
    elif transport == "sse":
        import uvicorn
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route

        sse = SseServerTransport("/messages")

        async def handle_sse(request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await server.run(streams[0], streams[1], server.create_initialization_options())

        app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=sse.handle_post_message, methods=["POST"]),
            ]
        )

        port = int(os.getenv("MCP_PORT", "3100"))
        logger.info("Starting SSE transport on port %d", port)
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        logger.error("Unknown MCP_TRANSPORT=%s (use 'stdio' or 'sse')", transport)
        sys.exit(1)


if __name__ == "__main__":
    main()
