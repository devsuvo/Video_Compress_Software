"""Video Compressor & Converter - size komay, quality same rakhe. Je kono format e convert kore.

GPU (AMD AMF / NVIDIA NVENC / Intel QSV) auto detect kore -> boro file (13-14 GB) o onek fast.
"Target Size" mode e je size chan (jemon 100 MB) oi size er kache output dey, resolution max 1080p.
"""
import os
import re
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# format -> (video codec, audio codec, extra args)
FORMATS = {
    "mp4":  ("libx264", "aac", ["-movflags", "+faststart"]),
    "mkv":  ("libx264", "aac", []),
    "mov":  ("libx264", "aac", ["-movflags", "+faststart"]),
    "webm": ("libvpx-vp9", "libopus", ["-row-mt", "1"]),
    "avi":  ("libx264", "mp3", []),
    "flv":  ("libx264", "aac", []),
    "wmv":  ("wmv2", "wmav2", []),
    "mpeg": ("mpeg2video", "mp2", []),
    "3gp":  ("libx264", "aac", []),
    "m4v":  ("libx264", "aac", []),
    "ts":   ("libx264", "aac", []),
    "gif":  (None, None, []),
    "mp3 (audio only)": (None, "libmp3lame", []),
}
# ei format gulo te GPU / H.265 encoder use kora jay
HW_FORMATS = ("mp4", "mkv", "mov", "m4v", "ts")

# quality preset -> CRF (kom CRF = beshi quality)
QUALITY = {
    "Visually Lossless (best)": 18,
    "High (recommended)": 23,
    "Medium (smaller)": 28,
    "Low (smallest)": 32,
}

MODES = ["Target Size (MB)", "Quality (CRF)"]
SPEED = ["Fastest", "Balanced", "Best quality (slower)"]
RESOLUTIONS = {"Original": None, "2160p (4K)": 2160, "1440p": 1440,
               "1080p": 1080, "720p": 720, "480p": 480, "360p": 360}

# encoder name -> (label, codec family). Upore thaka gulo age try hobe.
ENCODERS = [
    ("hevc_nvenc", "NVIDIA GPU - H.265", "hevc"),
    ("hevc_amf",   "AMD GPU - H.265",    "hevc"),
    ("hevc_qsv",   "Intel GPU - H.265",  "hevc"),
    ("h264_nvenc", "NVIDIA GPU - H.264", "h264"),
    ("h264_amf",   "AMD GPU - H.264",    "h264"),
    ("h264_qsv",   "Intel GPU - H.264",  "h264"),
    ("libx265",    "CPU - H.265 (slow, small)", "hevc"),
    ("libx264",    "CPU - H.264 (compatible)",  "h264"),
]
ENC_LABEL = {e: lbl for e, lbl, _ in ENCODERS}
ENC_FAMILY = {e: fam for e, _, fam in ENCODERS}

# speed index (0 fastest .. 2 best) -> encoder preset args
PRESETS = {
    "amf":  [["-quality", "speed"], ["-quality", "balanced"], ["-quality", "quality"]],
    "nvenc": [["-preset", "p2"], ["-preset", "p4"], ["-preset", "p6"]],
    "qsv":  [["-preset", "veryfast"], ["-preset", "medium"], ["-preset", "slower"]],
    "cpu":  [["-preset", "veryfast"], ["-preset", "fast"], ["-preset", "slow"]],
}

# 1080p e ei video bitrate (kbps) er niche gele quality chokhe pora drop korbe
MIN_KBPS = {"hevc": 1200, "h264": 2000}


def human(n):
    for u in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.2f} {u}"
        n /= 1024
    return f"{n:.2f} TB"


def hms(sec):
    sec = int(sec)
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}"


def encoder_works(enc):
    """Choto ekta test encode kore dekhe ei PC te encoder ta kaj kore kina."""
    try:
        r = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                            "-i", "color=black:s=640x360:d=0.2", "-frames:v", "3",
                            "-c:v", enc, "-f", "null", "-"],
                           capture_output=True, timeout=20, creationflags=NO_WINDOW)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def probe(path):
    """ffmpeg -i diye duration (sec) ar video height ber kore."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    dur = height = None
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if m:
        dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    m = re.search(r"Stream #.*Video:.*?, (\d{2,5})x(\d{2,5})", r.stderr)
    if m:
        height = int(m[2])
    return dur, height


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Compressor & Converter")
        self.geometry("680x600")
        self.minsize(600, 560)
        self.proc = None
        self.duration = None
        self.src_height = None
        self.encoders = ["libx264", "libx265"]

        pad = {"padx": 10, "pady": 5}
        f = ttk.Frame(self, padding=10)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)

        ttk.Label(f, text="Input Video:").grid(row=0, column=0, sticky="w", **pad)
        self.inp = tk.StringVar()
        ttk.Entry(f, textvariable=self.inp).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(f, text="Browse / Upload", command=self.browse_in).grid(row=0, column=2, **pad)

        ttk.Label(f, text="Output Folder:").grid(row=1, column=0, sticky="w", **pad)
        self.outdir = tk.StringVar()
        ttk.Entry(f, textvariable=self.outdir).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(f, text="Choose", command=self.browse_out).grid(row=1, column=2, **pad)

        self.fmt = self._combo(f, 2, "Output Format:", list(FORMATS), "mp4")
        self.mode = self._combo(f, 3, "Compress Mode:", MODES, MODES[0])

        ttk.Label(f, text="Target Size (MB):").grid(row=4, column=0, sticky="w", **pad)
        self.target = tk.StringVar(value="100")
        ttk.Entry(f, textvariable=self.target).grid(row=4, column=1, sticky="ew", **pad)

        self.quality = self._combo(f, 5, "Quality (CRF mode):", list(QUALITY), "High (recommended)")
        self.enc_box = ttk.Combobox(f, state="readonly")
        ttk.Label(f, text="Encoder:").grid(row=6, column=0, sticky="w", **pad)
        self.enc_box.grid(row=6, column=1, sticky="ew", **pad)
        self.enc_box.set("Detecting GPU...")
        self.res = self._combo(f, 7, "Max Resolution:", list(RESOLUTIONS), "1080p")
        self.speed = self._combo(f, 8, "Speed:", SPEED, "Balanced")

        self.info = tk.StringVar(value="Video select korun.")
        ttk.Label(f, textvariable=self.info, foreground="#333", wraplength=620).grid(
            row=9, column=0, columnspan=3, sticky="w", **pad)

        self.bar = ttk.Progressbar(f, maximum=100)
        self.bar.grid(row=10, column=0, columnspan=3, sticky="ew", **pad)
        self.status = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.status).grid(row=11, column=0, columnspan=3, sticky="w", **pad)

        bf = ttk.Frame(f)
        bf.grid(row=12, column=0, columnspan=3, pady=15)
        self.start_btn = ttk.Button(bf, text="▶ Start Compress / Convert", command=self.start,
                                    state="disabled")
        self.start_btn.pack(side="left", padx=5, ipadx=10, ipady=5)
        self.cancel_btn = ttk.Button(bf, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=5, ipady=5)
        ttk.Button(bf, text="Open Output Folder", command=self.open_out).pack(side="left", padx=5, ipady=5)

        for v in (self.target, self.mode, self.res, self.fmt):
            v.trace_add("write", lambda *_: self.update_estimate())
        self.enc_box.bind("<<ComboboxSelected>>", lambda _: self.update_estimate())
        threading.Thread(target=self.detect_encoders, daemon=True).start()

    def _combo(self, f, row, label, values, default):
        ttk.Label(f, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=5)
        v = tk.StringVar(value=default)
        ttk.Combobox(f, textvariable=v, values=values, state="readonly").grid(
            row=row, column=1, sticky="ew", padx=10, pady=5)
        return v

    def detect_encoders(self):
        found = [e for e, _, _ in ENCODERS if encoder_works(e)]
        self.after(0, self._set_encoders, found or ["libx264"])

    def _set_encoders(self, found):
        self.encoders = found
        self.enc_box["values"] = [ENC_LABEL[e] for e in found]
        self.enc_box.current(0)  # list er prothom ta sobcheye fast (GPU thakle GPU)
        self.start_btn.config(state="normal")
        self.update_estimate()

    def encoder(self):
        """Selected encoder name; GPU/H.265 na chole emon format hole None."""
        if self.fmt.get() not in HW_FORMATS:
            return None
        lbl = self.enc_box.get()
        for e in self.encoders:
            if ENC_LABEL[e] == lbl:
                return e
        return self.encoders[0]

    def out_height(self):
        h = RESOLUTIONS[self.res.get()]
        if h and self.src_height:
            return min(h, self.src_height)
        return h or self.src_height or 1080

    def browse_in(self):
        p = filedialog.askopenfilename(filetypes=[
            ("Video files", "*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.mpeg *.mpg *.3gp *.m4v *.ts"),
            ("All files", "*.*")])
        if p:
            self.inp.set(p)
            if not self.outdir.get():
                self.outdir.set(os.path.dirname(p))
            self.duration, self.src_height = probe(p)
            self._probed = p
            self.update_estimate()

    def browse_out(self):
        d = filedialog.askdirectory()
        if d:
            self.outdir.set(d)

    def open_out(self):
        d = self.outdir.get()
        if d and os.path.isdir(d):
            os.startfile(d)

    def bitrates(self):
        """Target size theke (video_kbps, audio_kbps) ber kore. Possible na hole None."""
        try:
            mb = float(self.target.get())
        except ValueError:
            return None
        if not self.duration or mb <= 0:
            return None
        total = mb * 8 * 1024 * 1024 / self.duration / 1000 * 0.97  # 3% container overhead
        audio = 128 if total > 1500 else 96 if total > 600 else 64 if total > 250 else 48
        video = int(total - audio)
        return (video, audio) if video > 50 else None

    def update_estimate(self):
        p = self.inp.get().strip().strip('"')
        if not os.path.isfile(p):
            return
        txt = f"Original: {human(os.path.getsize(p))}"
        if self.duration:
            txt += f"   Length: {hms(self.duration)}"
        if self.src_height:
            txt += f"   {self.src_height}p"
        if self.mode.get() == MODES[0]:
            br = self.bitrates()
            if not br:
                txt += "\n⚠ Target size onek choto / invalid."
            else:
                enc = self.encoder()
                fam = ENC_FAMILY.get(enc, "h264")
                need = MIN_KBPS[fam] * (self.out_height() / 1080) ** 2
                txt += f"\nVideo bitrate: {br[0]} kbps, audio {br[1]} kbps @ {self.out_height()}p"
                if br[0] < need:
                    good_mb = (need + 96) * 1000 * self.duration / 8 / 1024 / 1024 / 0.97
                    txt += (f"\n⚠ Ei length er video te {self.target.get()} MB e {self.out_height()}p "
                            f"quality kichuta kombe. Bhalo quality er jonno ~{good_mb:.0f} MB+ din.")
        self.info.set(txt)

    def build_cmd(self, src, dst):
        fmt = self.fmt.get()
        vcodec, acodec, extra = FORMATS[fmt]
        crf = QUALITY[self.quality.get()]
        height = RESOLUTIONS[self.res.get()]
        # bilinear scale onek fast, downscale e quality pray same
        scale = f"scale=-2:'min({height},ih)':flags=bilinear" if height else None
        cmd = [FFMPEG, "-y", "-i", src]

        if fmt == "gif":
            h = height or 480
            cmd += ["-vf", f"fps=12,scale=-2:'min({h},ih)':flags=lanczos,split[a][b];"
                           "[a]palettegen[p];[b][p]paletteuse", "-loop", "0"]
            return cmd + [dst]
        if fmt.startswith("mp3"):
            return cmd + ["-vn", "-c:a", acodec, "-q:a", "2", dst]

        target = self.mode.get() == MODES[0]
        br = self.bitrates() if target else None
        abr = f"{br[1]}k" if br else "128k"

        # prothom video + prothom audio; mkv te subtitle copy, baki format e subtitle bad
        cmd += ["-map", "0:v:0", "-map", "0:a:0?"]
        if fmt == "mkv":
            cmd += ["-map", "0:s?", "-c:s", "copy"]
        else:
            cmd += ["-sn"]
        cmd += ["-dn", "-map_metadata", "0", "-map_chapters", "0"]

        enc = self.encoder()
        if enc:
            vcodec = enc
        cmd += ["-c:v", vcodec]
        sp = SPEED.index(self.speed.get())

        if enc:
            kind = "amf" if "amf" in enc else "nvenc" if "nvenc" in enc else \
                   "qsv" if "qsv" in enc else "cpu"
            cmd += PRESETS[kind][sp]
            if br:
                v = br[0]
                rate = ["-b:v", f"{v}k", "-maxrate", f"{v * 2}k", "-bufsize", f"{v * 2}k"]
                if kind == "amf":
                    cmd += ["-rc", "vbr_peak"] + rate
                elif kind == "nvenc":
                    cmd += ["-rc", "vbr", "-multipass", "qres", "-spatial-aq", "1"] + rate
                else:
                    cmd += rate
            else:
                q = crf + 4 if ENC_FAMILY[enc] == "hevc" and kind == "cpu" else crf
                if kind == "amf":
                    cmd += ["-rc", "cqp", "-qp_i", str(q), "-qp_p", str(q + 2), "-qp_b", str(q + 4)]
                elif kind == "nvenc":
                    cmd += ["-rc", "vbr", "-cq", str(q), "-b:v", "0"]
                elif kind == "qsv":
                    cmd += ["-global_quality", str(q)]
                else:
                    cmd += ["-crf", str(q)]
            if enc == "libx265":
                cmd += ["-x265-params", "log-level=error"]
            if ENC_FAMILY[enc] == "hevc" and fmt in ("mp4", "mov", "m4v"):
                cmd += ["-tag:v", "hvc1"]  # iPhone / Mac e play korar jonno
            vf = ",".join(x for x in (scale, "format=yuv420p") if x)
            cmd += ["-vf", vf]
        else:
            if vcodec == "libvpx-vp9":
                cmd += ["-deadline", "good", "-cpu-used", "4" if sp == 0 else "2"]
                cmd += ["-b:v", f"{br[0]}k"] if br else ["-crf", str(crf + 8), "-b:v", "0"]
            elif br:
                cmd += ["-b:v", f"{br[0]}k"]
            else:  # wmv2 / mpeg2: quantizer based
                cmd += ["-q:v", str(max(2, (crf - 16) // 2))]
            if scale:
                cmd += ["-vf", scale]

        cmd += ["-c:a", acodec]
        if acodec in ("aac", "libopus", "mp3"):
            cmd += ["-b:a", abr, "-ac", "2"]  # 5.1 audio ke stereo -> size onek kome
        if acodec == "mp3":
            cmd[cmd.index("mp3")] = "libmp3lame"
        return cmd + extra + [dst]

    def start(self):
        src = self.inp.get().strip().strip('"')
        if not os.path.isfile(src):
            messagebox.showerror("Error", "Valid video file select korun.")
            return
        if src != getattr(self, "_probed", None):
            self.duration, self.src_height = probe(src)
            self._probed = src
        if self.mode.get() == MODES[0] and not self.fmt.get().startswith(("gif", "mp3")):
            if not self.bitrates():
                messagebox.showerror("Error", "Target size valid na / video length paoa jayni.")
                return
        outdir = self.outdir.get().strip() or os.path.dirname(src)
        os.makedirs(outdir, exist_ok=True)
        ext = self.fmt.get().split()[0]
        base = os.path.splitext(os.path.basename(src))[0]
        dst = os.path.join(outdir, f"{base}_compressed.{ext}")
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(outdir, f"{base}_compressed_{i}.{ext}")
            i += 1

        cmd = self.build_cmd(src, dst)
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.bar["value"] = 0
        self.status.set("Processing...")
        threading.Thread(target=self.run, args=(cmd, src, dst), daemon=True).start()

    def run(self, cmd, src, dst):
        duration = self.duration
        log = []
        t0 = time.time()
        self.proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                     text=True, encoding="utf-8", errors="replace",
                                     creationflags=NO_WINDOW)
        for line in self.proc.stderr:
            log.append(line)
            if len(log) > 200:
                del log[:100]
            if duration is None:
                m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", line)
                if m:
                    duration = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
            m = re.search(r"time=(\d+):(\d+):([\d.]+)", line)
            if m and duration:
                t = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
                pct = min(100, t / duration * 100)
                sp = re.search(r"speed=\s*([\d.]+x)", line)
                el = time.time() - t0
                eta = el * (100 - pct) / pct if pct > 0.5 else None
                self.after(0, self._progress, pct, sp[1] if sp else "", eta)
        code = self.proc.wait()
        self.after(0, self._done, code, src, dst, "".join(log[-15:]))

    def _progress(self, pct, speed, eta):
        left = f"  ~{hms(eta)} baki" if eta else ""
        self.bar["value"] = pct
        self.status.set(f"Processing... {pct:.1f}%  (speed {speed}){left}")

    def _done(self, code, src, dst, log):
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.proc = None
        if code == 0 and os.path.exists(dst):
            a, b = os.path.getsize(src), os.path.getsize(dst)
            saved = (1 - b / a) * 100
            self.bar["value"] = 100
            self.status.set("Done ✔")
            self.info.set(f"Original: {human(a)}  →  New: {human(b)}   ({saved:+.1f}% saved)")
            messagebox.showinfo("Done", f"Saved to:\n{dst}\n\n{human(a)} → {human(b)}")
        else:
            if os.path.exists(dst):
                try:
                    os.remove(dst)
                except OSError:
                    pass
            self.status.set("Failed / Cancelled")
            if code not in (None, 0) and code != -1:
                messagebox.showerror("Error", log)

    def cancel(self):
        if self.proc:
            self.proc.terminate()


if __name__ == "__main__":
    App().mainloop()
