#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Memeriksa proses go2rtc..."
if ! pgrep -f "go2rtc -c" > /dev/null; then
  echo "Menjalankan go2rtc gateway..."
  /root/go2rtc -c "$DIR/go2rtc.yaml" > /dev/null 2>&1 &
fi

echo "Memeriksa proses cctv dashboard server..."
if ! pgrep -f "cctv_dashboard/server.py" > /dev/null; then
  echo "Menjalankan cctv server di port 8088..."
  python3 "$DIR/server.py" > /dev/null 2>&1 &
fi

echo "Sistem CCTV Xiaomi CW100 aktif:"
echo "Dashboard Web: http://0.0.0.0:8088"
echo "go2rtc WebRTC: http://0.0.0.0:1984"
