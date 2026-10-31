import json
import os
import subprocess
import threading
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "youtube_config.json")
RTSP_HOST = os.environ.get("RTSP_HOST", "127.0.0.1:8554")
STREAM_LEFT = os.environ.get("CCTV_STREAM_LEFT", "cctv_lensa_kiri")
STREAM_RIGHT = os.environ.get("CCTV_STREAM_RIGHT", "cctv_lensa_kanan")

DEFAULT_CONFIG = {
    "stream_key": "",
    "lens": "left",
    "quality": "native",
    "silent_audio": True,
    "auto_start": False,
}


def mask_stream_key(key):
    if not key:
        return ""
    clean = key.strip()
    if len(clean) <= 8:
        return "••••••••"
    return f"{clean[:4]}••••{clean[-4:]}"


class YouTubeStreamer:
    def __init__(self):
        self.lock = threading.Lock()
        self.config = dict(DEFAULT_CONFIG)
        self.process = None
        self.supervisor_thread = None
        self.running = False
        self.started_at = None
        self.last_error = None
        self.load_config()

        if self.config.get("auto_start") and self.config.get("stream_key"):
            self.start()

    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.config.update(saved)
        except Exception as e:
            self.last_error = f"Error loading config: {e}"

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.last_error = f"Error saving config: {e}"

    def _get_stream_rtsp(self, lens):
        stream_name = STREAM_RIGHT if lens == "right" else STREAM_LEFT
        return f"rtsp://{RTSP_HOST}/{stream_name}"

    def _build_ffmpeg_cmd(self, stream_key, lens, quality, silent_audio):
        rtsp_url = self._get_stream_rtsp(lens)
        clean_key = stream_key.strip()
        if clean_key.startswith("rtmp://") or clean_key.startswith("rtmps://"):
            rtmp_url = clean_key
        else:
            # Modern standard: RTMPS (Secure RTMP over TLS port 443)
            rtmp_url = f"rtmps://a.rtmps.youtube.com/live2/{clean_key}"

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-v",
            "warning",
            "-re",
            "-rtsp_transport",
            "tcp",
            "-i",
            rtsp_url,
        ]

        if silent_audio:
            cmd.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=44100",
                ]
            )

        if quality == "720p":
            cmd.extend(["-vf", "scale=1280:-2", "-b:v", "1200k", "-maxrate", "1500k", "-bufsize", "1500k"])
        elif quality == "1080p":
            cmd.extend(["-vf", "scale=1920:-2", "-b:v", "2000k", "-maxrate", "2500k", "-bufsize", "2500k"])
        else:
            # Native 2.5K (2304x1296)
            cmd.extend(["-b:v", "2500k", "-maxrate", "3000k", "-bufsize", "3000k"])

        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-tune",
                "zerolatency",
                "-threads",
                "2",
                "-g",
                "40",
                "-keyint_min",
                "40",
                "-sc_threshold",
                "0",
                "-pix_fmt",
                "yuv420p",
            ]
        )

        if silent_audio:
            cmd.extend(["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "128k", "-ar", "44100"])
        else:
            cmd.extend(["-map", "0:v:0", "-map", "0:a:0?", "-c:a", "aac", "-b:a", "128k", "-ar", "44100"])

        cmd.extend(["-f", "flv", "-flvflags", "no_duration_filesize", rtmp_url])
        return cmd

    def start(self, stream_key=None, lens=None, quality=None, silent_audio=None, auto_start=None):
        with self.lock:
            if stream_key is not None:
                self.config["stream_key"] = stream_key.strip()
            if lens is not None:
                self.config["lens"] = lens
            if quality is not None:
                self.config["quality"] = quality
            if silent_audio is not None:
                self.config["silent_audio"] = bool(silent_audio)
            if auto_start is not None:
                self.config["auto_start"] = bool(auto_start)

            self.save_config()

            key = self.config.get("stream_key", "").strip()
            if not key:
                return False, "Stream Key YouTube belum diisi."

            if self.running and self.process and self.process.poll() is None:
                return True, "Streaming YouTube sudah aktif."

            self.running = True
            self.started_at = datetime.now()
            self.last_error = None

            self.supervisor_thread = threading.Thread(target=self._supervisor_loop, daemon=True)
            self.supervisor_thread.start()
            return True, "Streaming YouTube berhasil dimulai."

    def _supervisor_loop(self):
        while self.running:
            key = self.config.get("stream_key", "").strip()
            lens = self.config.get("lens", "left")
            quality = self.config.get("quality", "native")
            silent = self.config.get("silent_audio", True)

            cmd = self._build_ffmpeg_cmd(key, lens, quality, silent)
            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.process.wait()
            except Exception as e:
                self.last_error = f"FFmpeg execution failed: {e}"

            if not self.running:
                break

            # Auto-restart interval on unexpected disconnect
            time.sleep(5)

    def stop(self):
        with self.lock:
            if not self.running:
                return True, "Streaming YouTube sudah tidak aktif."

            self.running = False
            self.started_at = None

            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
                except Exception as e:
                    self.last_error = f"Error stopping FFmpeg: {e}"
                finally:
                    self.process = None

            return True, "Streaming YouTube berhasil dihentikan."

    def get_status(self):
        with self.lock:
            is_alive = bool(self.running and self.process and self.process.poll() is None)
            uptime_sec = 0
            if is_alive and self.started_at:
                uptime_sec = int((datetime.now() - self.started_at).total_seconds())

            return {
                "active": is_alive,
                "stream_key_set": bool(self.config.get("stream_key")),
                "masked_key": mask_stream_key(self.config.get("stream_key", "")),
                "lens": self.config.get("lens", "left"),
                "quality": self.config.get("quality", "native"),
                "silent_audio": self.config.get("silent_audio", True),
                "auto_start": self.config.get("auto_start", False),
                "started_at": self.started_at.strftime("%Y-%m-%d %H:%M:%S") if self.started_at else None,
                "uptime_sec": uptime_sec,
                "last_error": self.last_error,
            }


youtube_streamer = YouTubeStreamer()
