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
    "layout": "side",
    "swap": False,
    "fit": "contain",
    "pip_corner": "br",
    "pip_size": 30,
}

LENS_CHOICES = ("left", "right", "both")
LAYOUT_CHOICES = ("side", "stack", "pip")
FIT_CHOICES = ("contain", "cover")
PIP_CORNERS = ("tl", "tr", "bl", "br")
PIP_MARGIN = 16
FPS_BOTH = 25

# Canvas used when both lenses share one frame. Native is capped at 1080p
# because two 2.5K H.265 decodes plus a larger encode overload a small host.
CANVAS = {
    "720p": (1280, 720, "2500k", "3000k"),
    "1080p": (1920, 1080, "4500k", "5500k"),
    "native": (1920, 1080, "4500k", "5500k"),
}


def normalize_layout_options(cfg):
    out = {}
    out["layout"] = cfg.get("layout") if cfg.get("layout") in LAYOUT_CHOICES else "side"
    out["swap"] = bool(cfg.get("swap", False))
    out["fit"] = cfg.get("fit") if cfg.get("fit") in FIT_CHOICES else "contain"
    out["pip_corner"] = cfg.get("pip_corner") if cfg.get("pip_corner") in PIP_CORNERS else "br"
    try:
        size = int(cfg.get("pip_size", 30))
    except (TypeError, ValueError):
        size = 30
    out["pip_size"] = max(15, min(50, size))
    return out


def _fit_chain(w, h, fit):
    if fit == "cover":
        return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    )


def build_both_filter(quality, layout, swap, fit, pip_corner, pip_size):
    """Return (filter_complex, bitrate, maxrate) for two lenses in one frame."""
    cw, ch, bitrate, maxrate = CANVAS.get(quality, CANVAS["native"])
    first, second = ("1:v", "0:v") if swap else ("0:v", "1:v")
    fps = f"fps={FPS_BOTH}"

    if layout == "pip":
        sw = int(cw * pip_size / 100) // 2 * 2
        sh = int(sw * 9 / 16) // 2 * 2
        x = f"{PIP_MARGIN}" if pip_corner in ("tl", "bl") else f"W-w-{PIP_MARGIN}"
        y = f"{PIP_MARGIN}" if pip_corner in ("tl", "tr") else f"H-h-{PIP_MARGIN}"
        graph = (
            f"[{first}]{fps},{_fit_chain(cw, ch, fit)}[main];"
            f"[{second}]{fps},{_fit_chain(sw, sh, 'cover')}[small];"
            f"[main][small]overlay={x}:{y}:shortest=0[v]"
        )
    elif layout == "stack":
        cell_h = ch // 2 // 2 * 2
        graph = (
            f"[{first}]{fps},{_fit_chain(cw, cell_h, fit)}[a];"
            f"[{second}]{fps},{_fit_chain(cw, cell_h, fit)}[b];"
            f"[a][b]vstack=inputs=2[v]"
        )
    else:
        cell_w = cw // 2 // 2 * 2
        graph = (
            f"[{first}]{fps},{_fit_chain(cell_w, ch, fit)}[a];"
            f"[{second}]{fps},{_fit_chain(cell_w, ch, fit)}[b];"
            f"[a][b]hstack=inputs=2[v]"
        )
    return graph, bitrate, maxrate


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
        self.paused_by_standby = False
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
        clean_key = stream_key.strip()
        if clean_key.startswith("rtmp://") or clean_key.startswith("rtmps://"):
            rtmp_url = clean_key
        else:
            # Modern standard: RTMPS (Secure RTMP over TLS port 443)
            rtmp_url = f"rtmps://a.rtmps.youtube.com/live2/{clean_key}"

        both = lens == "both"
        cmd = ["ffmpeg", "-hide_banner", "-v", "warning"]

        if both:
            for name in (STREAM_LEFT, STREAM_RIGHT):
                cmd.extend(["-thread_queue_size", "512", "-rtsp_transport", "tcp", "-i", f"rtsp://{RTSP_HOST}/{name}"])
        else:
            cmd.extend(["-re", "-rtsp_transport", "tcp", "-i", self._get_stream_rtsp(lens)])

        audio_index = 2 if both else 1
        if silent_audio:
            cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

        if both:
            opts = normalize_layout_options(self.config)
            graph, bitrate, maxrate = build_both_filter(
                quality, opts["layout"], opts["swap"], opts["fit"], opts["pip_corner"], opts["pip_size"]
            )
            cmd.extend(["-filter_complex", graph, "-b:v", bitrate, "-maxrate", maxrate, "-bufsize", maxrate])
            video_map = "[v]"
            gop = str(FPS_BOTH * 2)
        else:
            if quality == "720p":
                cmd.extend(["-vf", "scale=1280:-2", "-b:v", "1200k", "-maxrate", "1500k", "-bufsize", "1500k"])
            elif quality == "1080p":
                cmd.extend(["-vf", "scale=1920:-2", "-b:v", "2000k", "-maxrate", "2500k", "-bufsize", "2500k"])
            else:
                # Native 2.5K (2304x1296)
                cmd.extend(["-b:v", "2500k", "-maxrate", "3000k", "-bufsize", "3000k"])
            video_map = "0:v:0"
            gop = "40"

        cmd.extend(
            [
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
                "-threads", "3" if both else "2",
                "-g", gop,
                "-keyint_min", gop,
                "-sc_threshold", "0",
                "-pix_fmt", "yuv420p",
            ]
        )

        if silent_audio:
            cmd.extend(["-map", video_map, "-map", f"{audio_index}:a:0", "-c:a", "aac", "-b:a", "128k", "-ar", "44100"])
        else:
            cmd.extend(["-map", video_map, "-map", "0:a:0?", "-c:a", "aac", "-b:a", "128k", "-ar", "44100"])

        cmd.extend(["-f", "flv", "-flvflags", "no_duration_filesize", rtmp_url])
        return cmd

    def start(self, stream_key=None, lens=None, quality=None, silent_audio=None, auto_start=None, layout_options=None):
        with self.lock:
            if stream_key is not None:
                self.config["stream_key"] = stream_key.strip()
            if lens is not None and lens in LENS_CHOICES:
                self.config["lens"] = lens
            if layout_options:
                self.config.update(normalize_layout_options({**self.config, **layout_options}))
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
        fail_count = 0
        while self.running:
            key = self.config.get("stream_key", "").strip()
            lens = self.config.get("lens", "left")
            quality = self.config.get("quality", "native")
            silent = self.config.get("silent_audio", True)

            cmd = self._build_ffmpeg_cmd(key, lens, quality, silent)
            start_t = time.time()
            stderr_data = b""
            exit_code = 0
            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                _, stderr_data = self.process.communicate()
                exit_code = self.process.returncode
            except Exception as e:
                self.last_error = f"FFmpeg execution failed: {e}"
                exit_code = -1

            elapsed = time.time() - start_t
            if not self.running:
                break

            if elapsed > 60:
                fail_count = 0
            else:
                fail_count += 1

            err_msg = stderr_data.decode("utf-8", errors="replace").strip()[-300:] if stderr_data else ""
            if exit_code != 0:
                self.last_error = f"FFmpeg exit ({exit_code}): {err_msg}" if err_msg else f"FFmpeg exit code {exit_code}"

            if fail_count >= 3:
                with self.lock:
                    self.running = False
                    self.process = None
                break

            time.sleep(5)

    def stop(self):
        with self.lock:
            if not self.running and not self.process:
                return True, "Streaming YouTube sudah tidak aktif."

            self.running = False
            self.started_at = None
            self.paused_by_standby = False
            proc = self.process
            self.process = None

        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            except Exception as e:
                self.last_error = f"Error stopping FFmpeg: {e}"

        return True, "Streaming YouTube berhasil dihentikan."

    def pause_for_standby(self):
        with self.lock:
            if self.running or (self.process and self.process.poll() is None):
                self.paused_by_standby = True
                self.running = False
                proc = self.process
                self.process = None
            else:
                proc = None

        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def resume_from_standby(self):
        with self.lock:
            if self.paused_by_standby:
                self.paused_by_standby = False
                key = self.config.get("stream_key", "").strip()
                if key:
                    self.running = True
                    self.started_at = datetime.now()
                    self.supervisor_thread = threading.Thread(target=self._supervisor_loop, daemon=True)
                    self.supervisor_thread.start()

    def get_status(self):
        with self.lock:
            is_alive = bool(self.running and self.process and self.process.poll() is None)
            uptime_sec = 0
            if is_alive and self.started_at:
                uptime_sec = int((datetime.now() - self.started_at).total_seconds())

            return {
                "active": is_alive,
                "paused_by_standby": self.paused_by_standby,
                "stream_key_set": bool(self.config.get("stream_key")),
                "masked_key": mask_stream_key(self.config.get("stream_key", "")),
                "lens": self.config.get("lens", "left"),
                "quality": self.config.get("quality", "native"),
                "silent_audio": self.config.get("silent_audio", True),
                "auto_start": self.config.get("auto_start", False),
                **normalize_layout_options(self.config),
                "started_at": self.started_at.strftime("%Y-%m-%d %H:%M:%S") if self.started_at else None,
                "uptime_sec": uptime_sec,
                "last_error": self.last_error,
            }


youtube_streamer = YouTubeStreamer()
