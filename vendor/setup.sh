#!/usr/bin/env bash
set -euo pipefail

VENDOR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$(cd "$VENDOR_DIR/../.." && pwd)"

echo "Setting up vendor references in $VENDOR_DIR..."

# Link local chrome-devtools-axi if available
AXI_SOURCE="$SKILLS_DIR/../pi/agent/skills/chrome-devtools-axi-local/chrome-devtools-axi"
if [ -d "$AXI_SOURCE" ]; then
  if [ -L "$VENDOR_DIR/axi" ] && [ ! -e "$VENDOR_DIR/axi" ]; then
    rm "$VENDOR_DIR/axi"
  fi
  if [ ! -e "$VENDOR_DIR/axi" ]; then
    ln -s "$AXI_SOURCE" "$VENDOR_DIR/axi"
    echo "Linked $VENDOR_DIR/axi -> $AXI_SOURCE"
  fi
fi

echo "Vendor setup completed."
