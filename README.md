# My AI Carousel — short-form editor

Turns raw footage into vertical Reels/TikTok/Shorts with word-synced kinetic captions in the brand style (Sen + one big yellow Playfair Display Italic word per phrase).

## Install (Claude Code)

```
/plugin install short-form-editor --marketplace Mayyy8888/My-AI-Carousel
```

On older Claude Code versions, add the marketplace first:

```
/plugin marketplace add Mayyy8888/My-AI-Carousel
/plugin install short-form-editor@my-ai-carousel
```

The repo is private, so each teammate needs read access to it on GitHub. Then send Claude a video and ask, e.g. *"make 3 versions about 30s with different hooks"*, or run `/short-form-editor`.

## What's inside

`plugins/short-form-editor/skills/short-form-editor/`
- `SKILL.md`: the workflow Claude follows (source → transcript → edit lists → render → QA → deliver)
- `editor/assemble.py`: multi-segment cuts from an edit list, subtitle blur, captions re-timed
- `editor/pipeline.py`: single-clip cut, speaker-following 9:16 crop, `--transcribe-only`
- `editor/transcribe_offline.py`: word timestamps via sherpa-onnx models from GitHub (when Hugging Face is blocked)
- `editor/captions.mjs`: Puppeteer caption renderer (`bold` and `stacked` styles)
- `editor/fonts/`: Sen, Playfair Display Italic (SIL OFL, Google Fonts)

| Step | Tool |
|---|---|
| Download | yt-dlp |
| Word-level transcript | faster-whisper / Whisper (or sherpa-onnx) |
| Speaker-following crop | OpenCV |
| Captions to transparent video | Puppeteer |
| Cut, concat, grade, loudness, render | FFmpeg |

Setup per machine: `pip install -r requirements.txt && npm install` inside the skill folder (the skill does this for you).

`edits/` holds edit lists from past projects, for example `edits/coba-gift-set/`.
