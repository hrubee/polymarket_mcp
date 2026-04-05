# Polymarket MCP

Always-on MCP server for Polymarket prediction markets. Runs 24x7 on a VPS as a systemd service. Claude Code is the primary operator.

## Quick Start

```bash
# Install dependencies
uv sync

# Copy and edit environment
cp .env.example .env

# Run in DEMO mode (no wallet needed)
DEMO_MODE=true python -m polymarket_mcp.server

# Run with wallet
python -m polymarket_mcp.server
```

## Setup

1. Install: `uv sync`
2. Derive L2 credentials: `python scripts/derive_creds.py`
3. Approve USDC: `python scripts/approve_usdc.py`
4. Check auth: `python scripts/check_auth.py`
5. Start: `python -m polymarket_mcp.server`

See [AGENT_INTEGRATION_GUIDE.md](AGENT_INTEGRATION_GUIDE.md) for tool usage patterns.

## Testing

```bash
# Safety tests (no API calls)
pytest tests/test_safety.py -v

# DEMO mode tests
DEMO_MODE=true pytest tests/test_markets.py tests/test_orderbook.py -v

# Full suite (requires credentials)
pytest
```
