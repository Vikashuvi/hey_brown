#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "=== 1. Building React + feral-blob UI bundle ==="
cd "$DIR/ui"
npm run build

echo "=== 2. Setting up Brown.app bundle structure ==="
APP_NAME="Brown.app"
APP_DIR="$DIR/macos/build/$APP_NAME"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR/ui"

echo "=== 3. Compiling native Swift binary with swiftc ==="
swiftc -O \
  -framework Cocoa \
  -framework WebKit \
  -o "$MACOS_DIR/Brown" \
  "$DIR/macos/BrownNative/main.swift"

echo "=== 4. Copying Info.plist & Assets ==="
cp "$DIR/macos/BrownNative/Info.plist" "$CONTENTS_DIR/Info.plist"
cp -r "$DIR/ui/dist" "$RESOURCES_DIR/ui/dist"

chmod +x "$MACOS_DIR/Brown"

echo "======================================================="
echo "✅ Brown.app built successfully at: $APP_DIR"
echo "To run now: open \"$APP_DIR\""
echo "======================================================="
