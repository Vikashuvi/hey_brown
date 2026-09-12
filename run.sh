#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# 1. Use virtualenv python
PYTHON="$DIR/.venv/bin/python"
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"
fi

echo "========================================================"
echo " 🇮🇳 Brown — Personal AI Computer Assistant Launcher"
echo "========================================================"

# 2. Check if backend is already running on port 8766
if lsof -i :8766 > /dev/null 2>&1; then
    echo "[*] Backend is already running on port 8766."
else
    echo "[*] Starting Brown Python Backend in background..."
    nohup "$PYTHON" -u main.py > "$DIR/backend.log" 2>&1 &
    echo "[*] Backend started (PID: $!). Logs: backend.log"
    sleep 2
fi

# 3. Launch native desktop app on macOS
if [ -d "$DIR/macos/build/Brown.app" ]; then
    echo "[*] Launching native Brown Desktop App..."
    open "$DIR/macos/build/Brown.app"
    echo "✅ Brown is now active on your desktop!"
    echo "   - Say 'Hey Brown' to activate voice"
    echo "   - Press Cmd+, or hover over the mascot to open the Geist Control Panel"
else
    echo "[*] Launching browser/desktop interface..."
    "$PYTHON" scripts/run_desktop.py
fi
