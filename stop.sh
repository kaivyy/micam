#!/usr/bin/env bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Menghentikan layanan CCTV Dashboard..."
pkill -f "server.py" || true
pkill -f "go2rtc.*go2rtc.yaml" || true

echo "Semua layanan CCTV berhasil dihentikan."
