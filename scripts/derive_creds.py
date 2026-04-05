"""Derive L2 credentials from POLYGON_PRIVATE_KEY. Run once before first use."""

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
        print("Error: POLYGON_PRIVATE_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    sig_type = int(os.getenv("SIGNATURE_TYPE", "2"))
    funder = os.getenv("FUNDER_ADDRESS", "")

    client = ClobClient(
        host=CLOB_HOST,
        chain_id=CHAIN_ID,
        key=private_key,
        signature_type=sig_type,
        funder=funder if funder else None,
    )

    print("Deriving L2 credentials from private key...")
    creds = client.derive_api_key()

    print("\n# Add these to your .env file:")
    print(f'POLY_API_KEY="{creds.api_key}"')
    print(f'POLY_SECRET="{creds.secret}"')
    print(f'POLY_PASSPHRASE="{creds.api_passphrase}"')


if __name__ == "__main__":
    main()
