"""Check USDC and POL balance for the funder wallet."""

import os
import sys

import httpx
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    address = os.getenv("FUNDER_ADDRESS", os.getenv("POLYGON_ADDRESS", ""))
    if not address:
        print("Error: FUNDER_ADDRESS or POLYGON_ADDRESS not set", file=sys.stderr)
        sys.exit(1)

    print(f"Checking balances for: {address}")

    # USDC balance via Polygon RPC
    usdc_contract = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    # ERC20 balanceOf(address) selector
    call_data = f"0x70a08231000000000000000000000000{address[2:]}"

    with httpx.Client(timeout=15) as client:
        # USDC
        try:
            resp = client.post(
                "https://polygon-rpc.com",
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [{"to": usdc_contract, "data": call_data}, "latest"],
                    "id": 1,
                },
            )
            result = resp.json().get("result", "0x0")
            usdc_wei = int(result, 16)
            usdc = usdc_wei / 1e6  # USDC has 6 decimals
            print(f"  USDC: {usdc:.2f}")
        except Exception as e:
            print(f"  USDC: Error — {e}")

        # POL (native) balance
        try:
            resp = client.post(
                "https://polygon-rpc.com",
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_getBalance",
                    "params": [address, "latest"],
                    "id": 2,
                },
            )
            result = resp.json().get("result", "0x0")
            pol_wei = int(result, 16)
            pol = pol_wei / 1e18
            print(f"  POL:  {pol:.4f}")
        except Exception as e:
            print(f"  POL:  Error — {e}")


if __name__ == "__main__":
    main()
