#!/bin/bash
set -e

PLIST_NAME="com.brown.ui.plist"
SOURCE_PLIST="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )/$PLIST_NAME"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$PLIST_NAME"

ACTION="${1:-install}"

case "$ACTION" in
    install)
        mkdir -p "$TARGET_DIR"
        echo "Copying $PLIST_NAME to $TARGET_DIR..."
        cp "$SOURCE_PLIST" "$TARGET_PLIST"
        
        # Unload if already loaded
        launchctl unload "$TARGET_PLIST" 2>/dev/null || true
        
        echo "Loading LaunchAgent..."
        launchctl load -w "$TARGET_PLIST"
        echo "Brown UI LaunchAgent installed and loaded!"
        echo "Logs: /tmp/brown_ui.stdout.log and /tmp/brown_ui.stderr.log"
        ;;
    uninstall)
        echo "Unloading and removing LaunchAgent..."
        launchctl unload "$TARGET_PLIST" 2>/dev/null || true
        rm -f "$TARGET_PLIST"
        echo "Brown UI LaunchAgent removed."
        ;;
    status)
        launchctl list | grep "com.brown.ui" || echo "com.brown.ui is not currently running."
        ;;
    *)
        echo "Usage: $0 [install|uninstall|status]"
        exit 1
        ;;
esac
