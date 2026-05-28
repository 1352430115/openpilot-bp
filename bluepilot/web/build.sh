#!/usr/bin/env bash
# Build BluePilot web UI without system-wide npm.
# Downloads a portable Node.js binary on first run (linux arm64/x64).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

NODE_VERSION="${BP_WEB_NODE_VERSION:-22.14.0}"
TOOLS_DIR="$SCRIPT_DIR/.tools"
ARCH="$(uname -m)"

case "$ARCH" in
  aarch64|arm64) NODE_ARCH="arm64" ;;
  x86_64|amd64) NODE_ARCH="x64" ;;
  *)
    echo "Unsupported CPU architecture: $ARCH" >&2
    exit 1
    ;;
esac

NODE_DIR="$TOOLS_DIR/node-v${NODE_VERSION}-linux-${NODE_ARCH}"
NODE_BIN="$NODE_DIR/bin/node"
NPM_BIN="$NODE_DIR/bin/npm"

download_node() {
  mkdir -p "$TOOLS_DIR"
  TARBALL="node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz"
  URL="https://nodejs.org/dist/v${NODE_VERSION}/${TARBALL}"
  TMP="$TOOLS_DIR/${TARBALL}"

  echo "Downloading Node.js v${NODE_VERSION} (${NODE_ARCH})..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$URL" -o "$TMP"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$URL" -O "$TMP"
  else
    echo "Need curl or wget to download Node.js." >&2
    exit 1
  fi

  tar -xJf "$TMP" -C "$TOOLS_DIR"
  rm -f "$TMP"
  echo "Node.js installed at $NODE_DIR"
}

if [[ ! -x "$NODE_BIN" ]]; then
  download_node
fi

export PATH="$NODE_DIR/bin:$PATH"

echo "Using node: $($NODE_BIN -v)"
echo "Using npm: $($NPM_BIN -v)"

if [[ ! -d node_modules ]]; then
  echo "Installing npm dependencies..."
  "$NPM_BIN" ci
else
  echo "Dependencies present (run 'rm -rf node_modules' to force reinstall)"
fi

echo "Building web app..."
"$NPM_BIN" run build

echo ""
echo "Build complete. Output: $SCRIPT_DIR/public/"
echo "Restart the BluePilot portal (port 8088) to serve the new files."
