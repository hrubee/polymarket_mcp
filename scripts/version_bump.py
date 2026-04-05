"""Bump version in pyproject.toml and __init__.py."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/version_bump.py <new_version>")
        print("Example: python scripts/version_bump.py 0.2.0")
        sys.exit(1)

    new_version = sys.argv[1]
    if not re.match(r"^\d+\.\d+\.\d+$", new_version):
        print(f"Invalid version format: {new_version} (expected X.Y.Z)")
        sys.exit(1)

    # Update pyproject.toml
    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text()
    text = re.sub(r'version = "[^"]*"', f'version = "{new_version}"', text, count=1)
    pyproject.write_text(text)
    print(f"Updated pyproject.toml → {new_version}")

    # Update __init__.py
    init = ROOT / "src" / "polymarket_mcp" / "__init__.py"
    text = init.read_text()
    text = re.sub(r'__version__ = "[^"]*"', f'__version__ = "{new_version}"', text, count=1)
    init.write_text(text)
    print(f"Updated __init__.py → {new_version}")


if __name__ == "__main__":
    main()
