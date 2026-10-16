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

## Styles
- `--style bold` — 3-word chunks near the bottom, current word highlighted.
- `--style stacked` — editorial kinetic type (modelled on a reference reel): each sentence builds word by word in the upper third, small white **Sen** with staggered lines, one key word large in yellow **Playfair Display Italic**, soft warm grade. The key word is picked automatically (numbers first, then the longest meaningful word); override with `--emphasis riskiest mother`. Move the block with `--top 600`.

Brand fonts live in `editor/fonts/` (SIL OFL, from Google Fonts).

Claude Code skill: `.claude/skills/short-form-editor/SKILL.md` documents the full workflow.
