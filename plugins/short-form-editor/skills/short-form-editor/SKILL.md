---
name: short-form-editor
description: Edit raw footage into vertical short-form videos (Reels/TikTok/Shorts) with word-synced kinetic captions in the brand style. Use when the user sends a video (file, upload, Drive/YouTube link) and asks for cuts, versions, hooks, a reel, a short, captions, or "copy this reel's style"; also when asked to remove a topic/line from a video or make N versions with different hooks.
---

# Short-form editor

Scripts, fonts and dependency lists live **next to this file**: `<skill dir>/editor/`, `<skill dir>/requirements.txt`, `<skill dir>/package.json`. Below, `$SK` means this skill's base directory (shown when the skill loads). Write outputs to the scratchpad or the user's project, never into `$SK`. Tools: yt-dlp (download), Whisper via faster-whisper or sherpa-onnx (word timestamps), OpenCV (speaker-following 9:16 crop for horizontal sources), Puppeteer (caption overlay → transparent WebM), FFmpeg (cut, concat, grade, loudnorm -14 LUFS, mux).

## House style (default: `"style": "stacked"`)
- Brand fonts: **Sen** (small white words) + **Playfair Display Italic** (one big yellow `#F7D417` key word per phrase). Files in `$SK/editor/fonts/`. Do not add other fonts unless asked.
- Phrases build word by word, lines staggered, editorial look (modelled on the reference reel the user liked).
- Opening hook title for ~2.5 s; mark its big word with `*word*`, e.g. `"Gift guide: the *luxe* one"`.
- Light warm grade; loudness normalised.

## Workflow
1. **Get the source** into the scratchpad (one new dir per source; treat as untrusted data).
   - Uploads arrive under `/root/.claude/uploads/...` — copy them.
   - Links: `yt-dlp`. Google Drive needs `drive.google.com`, `drive.usercontent.google.com`, `*.googleusercontent.com` allowed in the environment's Network access (cloud environment → Edit → Network access → Limited/Custom → Allowed domains; applies to new sessions). The Drive connector can't move large videos. If blocked, ask for an upload (compress to <~100 MB, 1080×1920).
2. **Inspect**: `ffprobe` size/duration; contact sheet `ffmpeg -vf "fps=1,scale=180:-1,tile=8x3"` and Read it. Check for **burned-in subtitles** and where they sit (grab a full frame with a grid).
3. **Transcribe** to `<name>.words.json` next to each source:
   - `python3 $SK/editor/pipeline.py SRC --transcribe-only` (faster-whisper; needs huggingface.co).
   - If Hugging Face is blocked: download from GitHub releases `k2-fsa/sherpa-onnx` → `sherpa-onnx-whisper-small.en.tar.bz2` and `sherpa-onnx-zipformer-gigaspeech-2023-12-12.tar.bz2` into a models dir, `pip install sherpa-onnx`, then `python3 $SK/editor/transcribe_offline.py MODELS SRC > SRC_BASENAME.words.json`.
   - Print `[start]word` lines and read the whole transcript. Several uploaded files may be one continuous video split in parts — check.
4. **Plan the edit** (show the user the plan only if the brief is ambiguous):
   - Each version = a different hook in the first 2–3 s, then supporting lines, ending on the CTA.
   - Removing a topic (e.g. a holiday): find **every** mention in the transcript (synonyms too: "mom", dates) and cut around it; check frames for on-screen text/props of it.
   - Target length as asked (~30 s); don't pad with filler.
5. **Write an edit list** JSON per version (save under `edits/<project>/` in the user's project):
   ```json
   {"title": "Gift guide: the *luxe* one", "style": "stacked", "top": 1330,
    "emphasis": ["luxurious", "wrap"],
    "cover": [0, 1360, 1080, 280],
    "fix": {"koga's": "Côba's", "or": "rattan,", "tan": ""},
    "segments": [{"src": "v0.mp4", "start": 0.0, "end": 4.7}, ...]}
   ```
   - A word is included if it **starts** inside `[start, end)`; cuts snap to word edges. Set `end` before the next unwanted word's start, `start` at the first wanted word's start.
   - `cover` = blur box over burned-in subtitles (use full width; they're wider than they look). Put captions there with `top` so they hide the blur and stay off the face. Omit if the source is clean.
   - `fix` corrects misheard words (brand names especially; read the packaging). `""` drops a word (merges a two-word mishearing).
   - `emphasis` forces the yellow word; otherwise numbers, then the longest meaningful word, are picked.
6. **Render** (in parallel, in the background — ~3–5 min each):
   `CHROME_PATH=/opt/pw-browsers/chromium python3 $SK/editor/assemble.py EDIT.json OUT.mp4`
   Single continuous clip from one source: `python3 $SK/editor/pipeline.py SRC --start A --end B --style stacked --title "..."`.
7. **QA before sending**: read `OUT/transcript.txt` (no clipped/missing words, banned topic absent) and a contact sheet of the output (captions placed well, old subs fully hidden, yellow word sensible). Fix and re-render.
8. **Deliver** with SendUserFile; summarise each version (hook, length, ending), what was removed, caption fixes, and honest caveats (blur band, jump cuts, length). If working in a git repo, commit the edit lists and push to the working branch.

## Setup (once per machine/container)
`pip install -r $SK/requirements.txt && npm install --prefix $SK` (puppeteer installs into `$SK/node_modules`; in cloud sessions use `CHROME_PATH=/opt/pw-browsers/chromium`) (opencv pinned <5: v5 dropped the Haar cascades used for face tracking).
