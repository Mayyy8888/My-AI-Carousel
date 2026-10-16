"""Short-form editor: source URL/file -> vertical captioned clip.

Steps: yt-dlp download -> faster-whisper word timestamps -> FFmpeg cut ->
OpenCV speaker-following 9:16 crop -> Puppeteer caption overlay -> FFmpeg mux.
"""
import argparse, json, subprocess, sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent


def run(cmd):
    print("+", " ".join(map(str, cmd)), file=sys.stderr)
    subprocess.run(cmd, check=True)


def fetch(src, work):
    if Path(src).exists():
        return Path(src)
    out = work / "source.mp4"
    run(["yt-dlp", "-f", "bv*[height<=1080]+ba/b", "--merge-output-format", "mp4", "-o", str(out), src])
    return out


def transcribe(video, model="small"):
    from faster_whisper import WhisperModel
    m = WhisperModel(model, compute_type="int8")
    segs, _ = m.transcribe(str(video), word_timestamps=True, vad_filter=True)
    return [{"w": w.word.strip(), "s": w.start, "e": w.end} for s in segs for w in s.words]


def snap(words, start, end):
    """Move cut points to word boundaries so no word is clipped."""
    inside = [w for w in words if w["e"] > start and w["s"] < end]
    if not inside:
        return start, end
    return max(0, inside[0]["s"] - 0.08), inside[-1]["e"] + 0.15


def face_track(video, start, end, step=0.2):
    """Return [(t, center_x_fraction)] following the largest face (proxy for the speaker)."""
    cap = cv2.VideoCapture(str(video))
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    pts, t, last = [], start, 0.5
    while t < end:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = det.detectMultiScale(g, 1.1, 5, minSize=(60, 60))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            last = (x + w / 2) / frame.shape[1]
        pts.append((t - start, last))
        t += step
    cap.release()
    xs = np.array([p[1] for p in pts]) if pts else np.array([0.5])
    k = 7  # smooth to avoid jittery camera
    xs = np.convolve(np.pad(xs, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
    return [(p[0], float(x)) for p, x in zip(pts, xs)]


def crop_expr(track, src_w, crop_w):
    """Piecewise-constant FFmpeg expression for crop x over time."""
    expr = str(int(max(0, min(src_w - crop_w, track[-1][1] * src_w - crop_w / 2))))
    for t, cx in reversed(track):
        x = int(max(0, min(src_w - crop_w, cx * src_w - crop_w / 2)))
        expr = f"if(lt(t,{t:.2f}),{x},{expr})" if t > 0 else expr
    return expr


def probe(video):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                   "-show_entries", "stream=width,height", "-of", "json", str(video)])
    s = json.loads(out)["streams"][0]
    return s["width"], s["height"]


def render(src, start, end, words, title, out, work, style="bold", emphasis=(), top=None):
    start, end = snap(words, start, end)
    w, h = probe(src)
    vert = work / "vertical.mp4"
    if w / h <= 9 / 16 + 0.01:  # already vertical: no reframing needed
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    else:
        crop_w = int(h * 9 / 16) // 2 * 2
        xexpr = crop_expr(face_track(src, start, end), w, crop_w).replace(",", "\\,")
        vf = f"crop={crop_w}:{h}:x='{xexpr}':y=0,scale=1080:1920"
    if style == "stacked":  # soft warm grade of the reference look
        vf += ",eq=saturation=1.06:contrast=1.03,colorbalance=rs=.03:bs=-.03:rm=.02:bm=-.02"
    run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
         "-vf", vf + ",setsar=1,fps=30",
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", str(vert)])
    clip_words = [{**x, "s": x["s"] - start, "e": x["e"] - start} for x in words
                  if x["s"] >= start and x["e"] <= end]
    spec = work / "captions.json"
    spec.write_text(json.dumps({"duration": end - start, "fps": 30, "title": title, "words": clip_words,
                                "style": style, "emphasis": [e.lower() for e in emphasis], "top": top}))
    overlay = work / "overlay.webm"
    run(["node", str(HERE / "captions.mjs"), str(spec), str(overlay)])
    run(["ffmpeg", "-y", "-i", str(vert), "-c:v", "libvpx-vp9", "-i", str(overlay),
         "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1[v]", "-map", "[v]", "-map", "0:a",
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", str(out)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="URL (yt-dlp) or local file")
    ap.add_argument("--start", type=float, help="clip start (s)")
    ap.add_argument("--end", type=float, help="clip end (s)")
    ap.add_argument("--title", default="")
    ap.add_argument("--style", default="bold", choices=["bold", "stacked"],
                    help="stacked = editorial kinetic type (yellow Playfair italic key word)")
    ap.add_argument("--emphasis", nargs="*", default=[], help="words to force as the big yellow word")
    ap.add_argument("--top", type=int, help="stacked: caption block top in px (of 1920)")
    ap.add_argument("--model", default="small")
    ap.add_argument("--transcribe-only", action="store_true", help="dump transcript to pick moments")
    ap.add_argument("-o", "--out", default="out/clip.mp4")
    a = ap.parse_args()
    work = Path("work"); work.mkdir(exist_ok=True); Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    src = fetch(a.source, work)
    tpath = work / f"{src.stem}.words.json"
    words = json.loads(tpath.read_text()) if tpath.exists() else transcribe(src, a.model)
    tpath.write_text(json.dumps(words))
    if a.transcribe_only or a.start is None:
        for x in words:
            print(f"{x['s']:8.2f} {x['w']}")
        return
    render(src, a.start, a.end, words, a.title, Path(a.out), work, a.style, a.emphasis, a.top)
    print(a.out)


if __name__ == "__main__":
    main()
