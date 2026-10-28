#!/usr/bin/env python3
import os
import sys
import json
import time
import shutil
import signal
import subprocess
import threading
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STORAGE_DIR = os.environ.get(
    "CCTV_STORAGE_DIR",
    "/root/cctv_recordings" if os.path.exists("/root/cctv_recordings") else os.path.join(BASE_DIR, "recordings")
)
CONFIG_FILE = os.path.join(DEFAULT_STORAGE_DIR, "recorder_config.json")
RTSP_HOST = os.environ.get("RTSP_HOST", "127.0.0.1:8554")

STREAMS = {
    "left": {
        "id": "left",
        "name": "Lensa 1 (Kiri)",
        "rtsp": f"rtsp://{RTSP_HOST}/cctv_garasi_kiri"
    },
    "right": {
        "id": "right",
        "name": "Lensa 2 (Kanan)",
        "rtsp": f"rtsp://{RTSP_HOST}/cctv_garasi_kanan"
    }
}

DEFAULT_CONFIG = {
    "storage_dir": DEFAULT_STORAGE_DIR,
    "auto_record_enabled": False,
    "auto_record_lens": "both",       # "left", "right", "both"
    "segment_minutes": 15,            # 5, 15, 30, 60
    "retention_days": 7,
    "min_free_space_gb": 5.0
}

class RecorderManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.config = dict(DEFAULT_CONFIG)
        self.manual_procs = {}  # "left": Popen, "right": Popen
        self.manual_start_times = {}
        self.auto_procs = {}    # "left": Popen, "right": Popen
        self.load_config()
        self.ensure_storage_dir()

        # Start maintenance background thread for retention and disk cleanup
        self.cleanup_thread = threading.Thread(target=self._maintenance_loop, daemon=True)
        self.cleanup_thread.start()

        # If auto-record was enabled, start it
        if self.config.get("auto_record_enabled", False):
            self.start_auto()

    def ensure_storage_dir(self):
        os.makedirs(self.config["storage_dir"], exist_ok=True)

    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.config.update(saved)
        except Exception as e:
            print(f"[Recorder] Error loading config: {e}", file=sys.stderr)

    def save_config(self):
        try:
            self.ensure_storage_dir()
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"[Recorder] Error saving config: {e}", file=sys.stderr)

    def update_config(self, new_data):
        with self.lock:
            for k in ["storage_dir", "auto_record_enabled", "auto_record_lens", "segment_minutes", "retention_days", "min_free_space_gb"]:
                if k in new_data:
                    self.config[k] = new_data[k]
            self.ensure_storage_dir()
            self.save_config()

            # Handle auto-record state toggle
            if self.config.get("auto_record_enabled", False):
                self._restart_auto_locked()
            else:
                self._stop_auto_locked()

        return self.get_status()

    # Manual Recording
    def start_manual(self, lens="both"):
        with self.lock:
            lenses = ["left", "right"] if lens == "both" else [lens]
            res = {}
            for l in lenses:
                if l not in STREAMS:
                    continue
                # If already recording, skip or report active
                p = self.manual_procs.get(l)
                if p and p.poll() is None:
                    res[l] = "already_running"
                    continue

                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"manual_{l}_{ts}.mp4"
                filepath = os.path.join(self.config["storage_dir"], filename)

                cmd = [
                    "ffmpeg", "-y", "-rtsp_transport", "tcp",
                    "-i", STREAMS[l]["rtsp"],
                    "-c", "copy",
                    "-movflags", "+faststart",
                    filepath
                ]
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.manual_procs[l] = proc
                self.manual_start_times[l] = time.time()
                res[l] = "started"
            return res

    def stop_manual(self, lens="both"):
        with self.lock:
            lenses = ["left", "right"] if lens == "both" else [lens]
            res = {}
            for l in lenses:
                p = self.manual_procs.get(l)
                if p and p.poll() is None:
                    try:
                        p.send_signal(signal.SIGINT)
                        try:
                            p.wait(timeout=4)
                        except subprocess.TimeoutExpired:
                            p.kill()
                    except Exception as e:
                        print(f"[Recorder] Stop error {l}: {e}", file=sys.stderr)
                    res[l] = "stopped"
                else:
                    res[l] = "not_running"
                self.manual_procs.pop(l, None)
                self.manual_start_times.pop(l, None)
            return res

    # Auto Segmented Recording (DVR Continuous)
    def start_auto(self):
        with self.lock:
            self._restart_auto_locked()

    def _restart_auto_locked(self):
        self._stop_auto_locked()
        selected_lens = self.config.get("auto_record_lens", "both")
        lenses = ["left", "right"] if selected_lens == "both" else [selected_lens]
        seg_sec = max(60, int(self.config.get("segment_minutes", 15)) * 60)

        for l in lenses:
            if l not in STREAMS:
                continue
            pattern = os.path.join(self.config["storage_dir"], f"dvr_{l}_%Y%m%d_%H%M%S.mp4")
            cmd = [
                "ffmpeg", "-y", "-rtsp_transport", "tcp",
                "-i", STREAMS[l]["rtsp"],
                "-c", "copy",
                "-f", "segment",
                "-segment_time", str(seg_sec),
                "-segment_format", "mp4",
                "-reset_timestamps", "1",
                "-strftime", "1",
                "-movflags", "+faststart",
                pattern
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.auto_procs[l] = proc

    def stop_auto(self):
        with self.lock:
            self._stop_auto_locked()

    def _stop_auto_locked(self):
        for l, p in list(self.auto_procs.items()):
            if p and p.poll() is None:
                try:
                    p.send_signal(signal.SIGINT)
                    try:
                        p.wait(timeout=4)
                    except subprocess.TimeoutExpired:
                        p.kill()
                except Exception as e:
                    print(f"[Recorder] Auto stop error {l}: {e}", file=sys.stderr)
        self.auto_procs.clear()

    # Status and Listing
    def get_status(self):
        with self.lock:
            manual_status = {}
            for l in ["left", "right"]:
                p = self.manual_procs.get(l)
                is_active = (p is not None and p.poll() is None)
                manual_status[l] = {
                    "active": is_active,
                    "started_at": self.manual_start_times.get(l) if is_active else None,
                    "duration_sec": int(time.time() - self.manual_start_times[l]) if (is_active and l in self.manual_start_times) else 0
                }

            auto_status = {}
            for l in ["left", "right"]:
                p = self.auto_procs.get(l)
                auto_status[l] = (p is not None and p.poll() is None)

            # Disk usage
            storage_dir = self.config["storage_dir"]
            try:
                total, used, free = shutil.disk_usage(storage_dir)
            except Exception:
                total, used, free = 1, 0, 1

            recordings_count, recordings_bytes = self._calc_storage_usage(storage_dir)

            return {
                "manual": manual_status,
                "auto": {
                    "enabled": bool(self.config.get("auto_record_enabled", False)),
                    "procs": auto_status
                },
                "config": dict(self.config),
                "disk": {
                    "total_gb": round(total / (1024**3), 2),
                    "used_gb": round(used / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2),
                    "free_pct": round((free / total) * 100, 1) if total else 0,
                    "recordings_count": recordings_count,
                    "recordings_mb": round(recordings_bytes / (1024**2), 1)
                }
            }

    def _calc_storage_usage(self, sdir):
        count = 0
        total_size = 0
        if not os.path.exists(sdir):
            return 0, 0
        for entry in os.scandir(sdir):
            if entry.is_file() and entry.name.endswith(".mp4"):
                count += 1
                try:
                    total_size += entry.stat().st_size
                except Exception:
                    pass
        return count, total_size

    def list_recordings(self):
        sdir = self.config["storage_dir"]
        if not os.path.exists(sdir):
            return []

        items = []
        for entry in os.scandir(sdir):
            if not entry.is_file() or not entry.name.endswith(".mp4"):
                continue
            name = entry.name
            try:
                st = entry.stat()
                size_bytes = st.st_size
                mtime = st.st_mtime
            except Exception:
                continue

            # Identify camera
            if "left" in name or "kiri" in name:
                lens = "Lensa 1 (Kiri)"
                lens_key = "left"
            elif "right" in name or "kanan" in name:
                lens = "Lensa 2 (Kanan)"
                lens_key = "right"
            else:
                lens = "Kamera"
                lens_key = "unknown"

            # Identify mode
            mode = "Manual" if name.startswith("manual_") else "Otomatis (DVR)"

            dt = datetime.fromtimestamp(mtime)
            created_str = dt.strftime("%d %b %Y, %H:%M:%S")

            items.append({
                "filename": name,
                "lens": lens,
                "lens_key": lens_key,
                "mode": mode,
                "size_bytes": size_bytes,
                "size_formatted": self._format_size(size_bytes),
                "timestamp": mtime,
                "created_str": created_str,
                "stream_url": f"/api/recordings/{name}/stream",
                "download_url": f"/api/recordings/{name}/download"
            })

        # Sort newest first
        items.sort(key=lambda x: x["timestamp"], reverse=True)
        return items

    def _format_size(self, size_bytes):
        if size_bytes >= 1024 * 1024 * 1024:
            return f"{round(size_bytes / (1024**3), 2)} GB"
        elif size_bytes >= 1024 * 1024:
            return f"{round(size_bytes / (1024**2), 1)} MB"
        elif size_bytes >= 1024:
            return f"{round(size_bytes / 1024, 1)} KB"
        return f"{size_bytes} B"

    def delete_recording(self, filename):
        # Security: protect against path traversal
        clean_name = os.path.basename(filename)
        if clean_name != filename or not filename.endswith(".mp4"):
            return False, "Invalid filename"

        target = os.path.join(self.config["storage_dir"], clean_name)
        if not os.path.exists(target):
            return False, "File not found"

        try:
            os.remove(target)
            return True, "Deleted successfully"
        except Exception as e:
            return False, str(e)

    def generate_timelapse(self, lens="left"):
        sdir = self.config["storage_dir"]
        recs = [r for r in self.list_recordings() if r["lens_key"] == lens]
        if not recs:
            return False, "Tidak ada rekaman untuk lensa ini"
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"timelapse_{lens}_{ts}.mp4"
        out_path = os.path.join(sdir, out_name)
        
        target_file = os.path.join(sdir, recs[0]["filename"])
        cmd = [
            "ffmpeg", "-y", "-i", target_file,
            "-vf", "setpts=0.08*PTS",
            "-an", "-c:v", "libx264", "-preset", "ultrafast",
            "-movflags", "+faststart",
            out_path
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                return True, out_name
            return False, "Gagal membuat video timelapse"
        except Exception as e:
            return False, str(e)

    # Periodic background retention & disk cleaner
    def _maintenance_loop(self):
        while True:
            time.sleep(300) # Every 5 minutes
            try:
                self._run_cleanup()
            except Exception as e:
                print(f"[Recorder] Cleanup loop error: {e}", file=sys.stderr)

    def _run_cleanup(self):
        sdir = self.config["storage_dir"]
        if not os.path.exists(sdir):
            return

        retention_days = float(self.config.get("retention_days", 7))
        min_free_gb = float(self.config.get("min_free_space_gb", 5.0))
        now = time.time()
        max_age_sec = retention_days * 86400

        files = []
        for entry in os.scandir(sdir):
            if entry.is_file() and entry.name.endswith(".mp4"):
                try:
                    files.append((entry.path, entry.stat().st_mtime, entry.stat().st_size))
                except Exception:
                    pass

        # 1. Delete expired files by retention days
        for path, mtime, _ in files:
            if (now - mtime) > max_age_sec:
                try:
                    os.remove(path)
                    print(f"[Recorder Cleanup] Expired file removed: {path}")
                except Exception:
                    pass

        # 2. Free space check
        try:
            total, used, free = shutil.disk_usage(sdir)
            free_gb = free / (1024**3)
            if free_gb < min_free_gb:
                # Sort oldest first
                files.sort(key=lambda x: x[1])
                for path, _, _ in files:
                    if not os.path.exists(path):
                        continue
                    try:
                        os.remove(path)
                        print(f"[Recorder Cleanup] Disk low ({free_gb:.1f}GB), removed: {path}")
                        total, used, free = shutil.disk_usage(sdir)
                        if (free / (1024**3)) >= min_free_gb:
                            break
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Recorder Cleanup] Disk space check error: {e}", file=sys.stderr)

recorder = RecorderManager()
