# Video Compressor & Converter

Video er size komay, quality prai same rakhe. Je kono format e convert o kora jay. Simple GUI (Tkinter) app.

## Features

- **Target Size mode**: je size chan (jemon 100 MB) output oi size er kache hobe (resolution max 1080p)
- **Quality (CRF) mode**: Visually Lossless / High / Medium / Low
- **GPU auto detect**: NVIDIA (NVENC), AMD (AMF), Intel (QSV), tai boro file (13-14 GB) o fast hoy. GPU na thakle CPU (x264 / x265) use kore
- **Format**: mp4, mkv, mov, webm, avi, flv, wmv, mpeg, 3gp, m4v, ts, gif, mp3 (shudhu audio)
- **Resolution**: Original, 4K, 1440p, 1080p, 720p, 480p, 360p
- **Speed**: Fastest / Balanced / Best quality

## Requirements

- Python 3.8+ (Tkinter shoho, Windows er Python e default thake)
- `imageio-ffmpeg` (ffmpeg nije theke download hoy, alada install lagbe na)

## Install & Run

```bash
git clone https://github.com/devsuvo/Video_Compress_Software.git
cd Video_Compress_Software
pip install -r requirements.txt
python video_compressor.py
```

## Update korar niyom

Onno jayga theke kora latest change anate:

```bash
git pull
```

Nijer change GitHub e pathate:

```bash
git add .
git commit -m "ki change korecho"
git push
```

## Project structure

```
video_compressor.py   # main app (GUI + ffmpeg logic)
requirements.txt      # Python dependency
.gitignore            # cache ar video file git e jabe na
```
