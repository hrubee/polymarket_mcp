"""Verify credentials and check for geo-blocking."""

import os
import sys

from dotenv import load_dotenv
from py_clob_client.client import ClobClient

CLOB_HOST = "https://clob.polymarket.com"
CHAIN_ID = 137


def main() -> None:
    load_dotenv()

    private_key = os.getenv("POLYGON_PRIVATE_KEY", "")
    if not private_key:
        print("Error: POLYGON_PRIVATE_KEY not set", file=sys.stderr)
        sys.exit(1)

    sig_type = int(os.getenv("SIGNATURE_TYPE", "2"))
    funder = os.getenv("FUNDER_ADDRESS", "")

    print("Initializing ClobClient...")
    client = ClobClient(
        host=CLOB_HOST,
        chain_id=CHAIN_ID,
        key=private_key,
        signature_type=sig_type,
        funder=funder if funder else None,
    )

    # Test public endpoint
    print("Testing connection (GET /time)...")
    try:
        server_time = client.get_server_time()
        print(f"  Server time: {server_time}")
    except Exception as e:
        print(f"  FAILED: {e}", file=sys.stderr)
        sys.exit(1)

    # Set L2 creds
    api_key = os.getenv("POLY_API_KEY", "")
    secret = os.getenv("POLY_SECRET", "")
    passphrase = os.getenv("POLY_PASSPHRASE", "")

    if not all([api_key, secret, passphrase]):
        print("Warning: L2 credentials not set — skipping authenticated check")
        print("Run: python scripts/derive_creds.py")
        return

    creds = type(
        "ApiCreds",
        (),
        {
            "api_key": api_key,
            "secret": secret,
            "api_passphrase": passphrase,
        },
    )()
    client.set_api_creds(creds)

    # Test authenticated endpoint
    print("Testing authenticated endpoint...")
    try:
        client.get_api_keys()
        print("  Authenticated endpoint accessible")
    except Exception as e:
        if "403" in str(e):
            print(
                "  GEO-BLOCKED: 403 Forbidden. Your VPS IP is blocked by Polymarket.",
                file=sys.stderr,
            )
            print(
                "  Use a VPS outside US/OFAC-sanctioned regions (EU, Singapore, UAE).",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"  FAILED: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nAll checks passed!")


if __name__ == "__main__":
    main()
