# Short-form editor

Long video → 9:16 clip with speaker-following crop and word-synced captions.

| Step | Tool |
|---|---|
| Download | yt-dlp |
| Word-level transcript (cuts snap to word boundaries) | faster-whisper (Whisper) |
| Speaker-following vertical crop | OpenCV |
| Captions + title rendered to transparent video | Puppeteer |
| Cut, crop, loudness-normalize (-14 LUFS), overlay, render | FFmpeg |

HyperFrames (HTML motion graphics) can replace `editor/captions.mjs` for richer titles; the overlay contract is the same (transparent 1080×1920 WebM).

## Setup
```
pip install -r requirements.txt && npm install
```

## Use
```
# 1. Transcript with timestamps, to pick the moment
python editor/pipeline.py "<url or file>" --transcribe-only
# 2. Render the clip
python editor/pipeline.py "<url or file>" --start 63.2 --end 118 --title "The hook line" -o out/clip1.mp4
```
