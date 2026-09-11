#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
APP_DIR="$DIR/macos/build/Brown.app"

if [ ! -d "$APP_DIR" ]; then
    echo "Brown.app not found. Building native macOS application..."
    "$DIR/scripts/build_macos_app.sh"
fi

echo "Launching native Brown menu-bar presence..."
open "$APP_DIR"
