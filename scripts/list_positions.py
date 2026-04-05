"""Quick position dump to stdout."""

import os
import sys

import httpx
from dotenv import load_dotenv

DATA_BASE = "https://data-api.polymarket.com"


def main() -> None:
    load_dotenv()

    address = os.getenv("FUNDER_ADDRESS", os.getenv("POLYGON_ADDRESS", ""))
    if not address:
        print("Error: FUNDER_ADDRESS or POLYGON_ADDRESS not set", file=sys.stderr)
        sys.exit(1)

    print(f"Positions for: {address}\n")

    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{DATA_BASE}/positions", params={"user": address})
        resp.raise_for_status()
        positions = resp.json()

    if not positions:
        print("No open positions.")
        return

    total_value = 0.0
    for p in positions:
        question = p.get("question", p.get("title", "Unknown"))
        outcome = p.get("outcome", "?")
        size = float(p.get("size", 0))
        price = float(p.get("currentPrice", p.get("current_price", 0)))
        value = size * price
        total_value += value

        print(f"  {question}")
        print(f"    Outcome: {outcome}  Size: {size:.2f}  Price: {price:.3f}  Value: ${value:.2f}")
        print()

    print(f"Total portfolio value: ${total_value:.2f}")


if __name__ == "__main__":
    main()
