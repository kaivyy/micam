#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=================================================="
echo "   Xiaomi CW100 Dual CCTV Surveillance System    "
echo "=================================================="

# 1. Periksa dependencies Python
if ! python3 -c "import Crypto" 2>/dev/null; then
    echo "[!] Dependensi pycryptodome belum terinstal."
    echo "    Menginstal via pip..."
    pip3 install -r "$DIR/requirements.txt" || apt-get install -y python3-pycryptodome
fi

# 2. Periksa ffmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "[!] PERINGATAN: FFmpeg belum terinstal. Fitur perekaman DVR memerlukan ffmpeg."
    echo "    Instal dengan: sudo apt-get update && sudo apt-get install -y ffmpeg"
fi

# 3. Cari / Unduh go2rtc binary jika belum ada
GO2RTC_BIN=""
if [ -x "$DIR/go2rtc" ]; then
    GO2RTC_BIN="$DIR/go2rtc"
elif command -v go2rtc >/dev/null 2>&1; then
    GO2RTC_BIN="$(command -v go2rtc)"
elif [ -x "/root/go2rtc" ]; then
    GO2RTC_BIN="/root/go2rtc"
else
    echo "[*] Mengunduh binary go2rtc untuk arsitektur sistem..."
    ARCH="$(uname -m)"
    if [ "$ARCH" = "x86_64" ]; then
        URL="https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_amd64"
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
        URL="https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_arm64"
    elif [ "$ARCH" = "armv7l" ]; then
        URL="https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_arm"
    else
        URL="https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_amd64"
    fi
    curl -L -s "$URL" -o "$DIR/go2rtc"
    chmod +x "$DIR/go2rtc"
    GO2RTC_BIN="$DIR/go2rtc"
fi

# 4. Jalankan go2rtc jika belum berjalan
echo "[*] Memeriksa status go2rtc gateway..."
if ! pgrep -f "go2rtc.*go2rtc.yaml" > /dev/null; then
    echo "    Menjalankan go2rtc gateway..."
    nohup "$GO2RTC_BIN" -c "$DIR/go2rtc.yaml" > "$DIR/go2rtc.log" 2>&1 </dev/null &
    disown
    sleep 1
else
    echo "    go2rtc gateway sudah aktif."
fi

# 5. Jalankan server dashboard jika belum berjalan
echo "[*] Memeriksa status CCTV Dashboard Server..."
if ! pgrep -f "$DIR/server.py" > /dev/null; then
    echo "    Menjalankan CCTV Dashboard Server di port 8088..."
    PYTHONPATH="$DIR" nohup python3 -u "$DIR/server.py" > "$DIR/server.log" 2>&1 </dev/null &
    disown
    sleep 1
else
    echo "    CCTV Dashboard Server sudah aktif."
fi

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
[ -z "$HOST_IP" ] && HOST_IP="127.0.0.1"

echo "--------------------------------------------------"
echo " [OK] Sistem CCTV Berhasil Aktif!"
echo " Web Dashboard : http://$HOST_IP:8088"
echo " go2rtc WebRTC : http://$HOST_IP:1984"
echo " RTSP Stream   : rtsp://$HOST_IP:8554/cctv_lensa_kiri"
echo "               : rtsp://$HOST_IP:8554/cctv_lensa_kanan"
echo " Stop Layanan  : ./stop.sh"
echo "--------------------------------------------------"
