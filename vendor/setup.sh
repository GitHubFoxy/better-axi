#!/usr/bin/env bash
set -euo pipefail

VENDOR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="$(cd "$VENDOR_DIR/../.." && pwd)"

echo "Setting up vendor references in $VENDOR_DIR..."

# Link local chrome-devtools-axi if available
if [ -d "$SKILLS_DIR/chrome-devtools-axi-local/chrome-devtools-axi" ] && [ ! -e "$VENDOR_DIR/axi" ]; then
  ln -s "$SKILLS_DIR/chrome-devtools-axi-local/chrome-devtools-axi" "$VENDOR_DIR/axi"
  echo "Linked $VENDOR_DIR/axi -> $SKILLS_DIR/chrome-devtools-axi-local/chrome-devtools-axi"
fi

echo "Vendor setup completed."
