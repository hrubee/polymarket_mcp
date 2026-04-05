"""Check and set USDC approval for Polymarket CTF Exchange on Polygon."""

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

    client = ClobClient(
        host=CLOB_HOST,
        chain_id=CHAIN_ID,
        key=private_key,
        signature_type=sig_type,
        funder=funder if funder else None,
    )

    print("Checking USDC approval for CTF Exchange...")
    try:
        allowance = client.get_collateral_allowance()
        if allowance.get("approved"):
            print("USDC approval already set. No action needed.")
            return
    except Exception as e:
        print(f"Could not check allowance: {e}")
        print("Proceeding to set approval...")

    print("Setting USDC approval (requires POL for gas)...")
    try:
        result = client.set_allowance()
        print(f"Approval transaction submitted: {result}")
        print("USDC approval set successfully.")
    except Exception as e:
        print(f"Failed to set approval: {e}", file=sys.stderr)
        print("Ensure your wallet has POL for gas (~0.01 POL minimum).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
