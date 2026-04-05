#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/root/polymarket-mcp"
SERVICE_NAME="polymarket-mcp"

echo "=== Polymarket MCP Server Installer ==="

# Check for Python 3.11
if ! command -v python3.11 &>/dev/null; then
    echo "Installing Python 3.11..."
    apt-get update && apt-get install -y python3.11 python3.11-venv
fi

# Install uv
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Clone or update repo
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "Cloning repository..."
    git clone https://github.com/yourorg/polymarket-mcp.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Install dependencies
echo "Installing dependencies..."
uv sync

# Setup .env
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo ""
    echo "=== Configuration ==="
    echo "Edit $INSTALL_DIR/.env with your credentials."
    echo ""
    read -p "POLYGON_PRIVATE_KEY (0x...): " pk
    read -p "FUNDER_ADDRESS (0x...): " funder
    read -p "SIGNATURE_TYPE (0=EOA, 1=POLY_PROXY, 2=GNOSIS_SAFE) [2]: " sig_type
    sig_type=${sig_type:-2}

    sed -i "s|POLYGON_PRIVATE_KEY=\"\"|POLYGON_PRIVATE_KEY=\"$pk\"|" "$INSTALL_DIR/.env"
    sed -i "s|FUNDER_ADDRESS=\"\"|FUNDER_ADDRESS=\"$funder\"|" "$INSTALL_DIR/.env"
    sed -i "s|SIGNATURE_TYPE=\"2\"|SIGNATURE_TYPE=\"$sig_type\"|" "$INSTALL_DIR/.env"

    echo ""
    echo "Deriving L2 credentials..."
    cd "$INSTALL_DIR"
    .venv/bin/python scripts/derive_creds.py | tee /tmp/creds.txt
    # Extract and write creds to .env
    grep "POLY_API_KEY" /tmp/creds.txt | head -1 >> "$INSTALL_DIR/.env" 2>/dev/null || true
    grep "POLY_SECRET" /tmp/creds.txt | head -1 >> "$INSTALL_DIR/.env" 2>/dev/null || true
    grep "POLY_PASSPHRASE" /tmp/creds.txt | head -1 >> "$INSTALL_DIR/.env" 2>/dev/null || true
    rm -f /tmp/creds.txt
fi

# Validate
echo ""
echo "Validating credentials..."
cd "$INSTALL_DIR"
.venv/bin/python scripts/check_auth.py

# Install systemd service
echo ""
echo "Installing systemd service..."
cp "$INSTALL_DIR/systemd/$SERVICE_NAME.service" "/etc/systemd/system/"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo ""
echo "=== Installation complete ==="
echo "Status: systemctl status $SERVICE_NAME"
echo "Logs:   journalctl -u $SERVICE_NAME -f"
