"""L1/L2 auth, credential loading from .env, ClobClient initialization."""

from __future__ import annotations

import logging
import os

from py_clob_client.client import ClobClient

from .types import SafetyConfig

logger = logging.getLogger(__name__)

CLOB_HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon mainnet


def load_safety_config() -> SafetyConfig:
    """Load safety limits from environment variables."""
    return SafetyConfig(
        max_order_size_usd=float(os.getenv("MAX_ORDER_SIZE_USD", "1000")),
        max_total_exposure_usd=float(os.getenv("MAX_TOTAL_EXPOSURE_USD", "5000")),
        max_position_per_market=float(os.getenv("MAX_POSITION_SIZE_PER_MARKET", "2000")),
        min_liquidity_required=float(os.getenv("MIN_LIQUIDITY_REQUIRED", "10000")),
        max_spread_tolerance=float(os.getenv("MAX_SPREAD_TOLERANCE", "0.05")),
        require_confirmation_above=float(os.getenv("REQUIRE_CONFIRMATION_ABOVE_USD", "500")),
    )


def is_demo_mode() -> bool:
    """Check if running in DEMO mode."""
    return os.getenv("DEMO_MODE", "false").lower() == "true"


def init_clob_client() -> ClobClient:
    """Initialize ClobClient with L1 private key and L2 credentials from .env."""
    private_key = os.getenv("POLYGON_PRIVATE_KEY", "")
    if not private_key:
        raise RuntimeError("POLYGON_PRIVATE_KEY not set in .env")

    funder = os.getenv("FUNDER_ADDRESS", "")
    sig_type = int(os.getenv("SIGNATURE_TYPE", "2"))

    api_key = os.getenv("POLY_API_KEY", "")
    secret = os.getenv("POLY_SECRET", "")
    passphrase = os.getenv("POLY_PASSPHRASE", "")

    if not all([api_key, secret, passphrase]):
        raise RuntimeError(
            "L2 credentials (POLY_API_KEY, POLY_SECRET, POLY_PASSPHRASE) not set. "
            "Run: python scripts/derive_creds.py"
        )

    client = ClobClient(
        host=CLOB_HOST,
        chain_id=CHAIN_ID,
        key=private_key,
        signature_type=sig_type,
        funder=funder if funder else None,
    )
    client.set_api_creds(
        client.create_or_derive_api_creds()
        if not api_key
        else type(
            "ApiCreds",
            (),
            {
                "api_key": api_key,
                "secret": secret,
                "api_passphrase": passphrase,
            },
        )()
    )

    logger.info("ClobClient initialized (chain_id=%d, sig_type=%d)", CHAIN_ID, sig_type)
    return client


def validate_connection(client: ClobClient) -> None:
    """Validate connection by hitting the /time endpoint."""
    try:
        server_time = client.get_server_time()
        logger.info("Connected to CLOB API, server time: %s", server_time)
    except Exception as e:
        raise RuntimeError(f"Failed to connect to CLOB API: {e}") from e


def check_geo_block(client: ClobClient) -> None:
    """Test an authenticated endpoint to detect geo-blocking."""
    try:
        client.get_api_keys()
        logger.info("Geo-block check passed — authenticated endpoint accessible")
    except Exception as e:
        error_str = str(e)
        if "403" in error_str:
            raise RuntimeError(
                "403 Forbidden on authenticated endpoint. Your VPS IP is likely "
                "geo-blocked by Polymarket. Use a VPS outside US/OFAC regions "
                "(EU, Singapore, UAE recommended)."
            ) from e
        logger.warning("Geo-block check inconclusive: %s", e)
