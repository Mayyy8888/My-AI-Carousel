"""Word timestamps without Hugging Face access, using sherpa-onnx models from GitHub.

Whisper (small.en) gives accurate text with punctuation; a zipformer transducer
gives per-token times. Whisper words are aligned onto the zipformer timeline.
Usage: python transcribe_offline.py MODELS_DIR video.mp4 > words.json
"""
import difflib, json, re, subprocess, sys
from pathlib import Path

import numpy as np
import sherpa_onnx

SR = 16000


def audio(video):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", video, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"])
    return np.frombuffer(raw, dtype=np.float32)


def chunks(x, win=25):
    """Split at the quietest point near every `win` seconds (whisper takes <=30 s)."""
    out, start = [], 0
    while len(x) - start > win * SR:
        lo, hi = start + (win - 5) * SR, start + win * SR
        e = np.convolve(np.abs(x[lo:hi]), np.ones(SR // 10), "same")
        cut = lo + int(np.argmin(e))
        out.append((start, cut)); start = cut
    out.append((start, len(x)))
    return out


def main(models, video):
    m = Path(models)
    w = next(m.glob("sherpa-onnx-whisper-*"))
    wh = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=str(next(w.glob("*-encoder.int8.onnx"))), decoder=str(next(w.glob("*-decoder.int8.onnx"))),
        tokens=str(next(w.glob("*-tokens.txt"))), language="en", task="transcribe")
    z = next(m.glob("sherpa-onnx-zipformer-*"))
    zp = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(next(z.glob("encoder*.int8.onnx"))), decoder=str(next(z.glob("decoder*.onnx"))),
        joiner=str(next(z.glob("joiner*.int8.onnx"))), tokens=str(z / "tokens.txt"))
    x = audio(video)
    words = []
    for a, b in chunks(x):
        off = a / SR
        s = zp.create_stream(); s.accept_waveform(SR, x[a:b]); zp.decode_stream(s)
        r = s.result
        zw = []  # group BPE tokens into words (a leading space or "▁" marks a word start)
        for tok, t in zip(r.tokens, r.timestamps):
            if tok.startswith((" ", "▁")) or not zw:
                zw.append({"w": tok.lstrip(" ▁").lower(), "s": off + t, "e": off + t + 0.2})
            else:
                zw[-1]["w"] += tok.lower(); zw[-1]["e"] = off + t + 0.2
        for i in range(len(zw) - 1):
            zw[i]["e"] = min(zw[i]["e"] + 0.15, zw[i + 1]["s"])
        s = wh.create_stream(); s.accept_waveform(SR, x[a:b]); wh.decode_stream(s)
        ww = s.result.text.split()
        norm = lambda t: re.sub(r"[^a-z0-9']", "", t.lower())
        sm = difflib.SequenceMatcher(a=[norm(t) for t in ww], b=[t["w"] for t in zw], autojunk=False)
        times = [None] * len(ww)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i1, i2):
                    zk = zw[j1 + k - i1]; times[k] = (zk["s"], zk["e"])
            elif tag == "replace" and j2 > j1:
                for k in range(i1, i2):  # spread replaced spans evenly over the matched zipformer span
                    f = (k - i1) / max(1, i2 - i1); g = (k - i1 + 1) / max(1, i2 - i1)
                    s0, e0 = zw[j1]["s"], zw[j2 - 1]["e"]
                    times[k] = (s0 + f * (e0 - s0), s0 + g * (e0 - s0))
        for k, t in enumerate(times):  # fill unmatched words between neighbours
            if t is None:
                prev = next((times[j][1] for j in range(k - 1, -1, -1) if times[j]), off)
                nxt = next((times[j][0] for j in range(k + 1, len(times)) if times[j]), prev + 0.3)
                times[k] = (prev, max(prev + 0.1, min(nxt, prev + 0.4)))
        words += [{"w": t, "s": round(se[0], 2), "e": round(se[1], 2)} for t, se in zip(ww, times)]
    json.dump(words, sys.stdout)


if __name__ == "__main__":
    main(*sys.argv[1:3])
