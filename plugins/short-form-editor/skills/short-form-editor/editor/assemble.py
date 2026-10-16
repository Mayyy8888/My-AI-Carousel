"""Assemble a short from an edit list of segments across one or more sources.

Edit list JSON:
{
  "title": "The gift you *don't* wrap",      # optional; *word* = big yellow word
  "style": "stacked", "top": 1330, "emphasis": ["luxurious"],
  "cover": [200, 1390, 680, 220],             # optional x,y,w,h blur over burned-in subs
  "fix": {"koga's": "Côba's"},                # optional caption word replacements
  "segments": [{"src": "v0.mp4", "start": 0.0, "end": 4.8}, ...]
}
Each source needs a <name>.words.json next to it (pipeline.py or transcribe_offline.py).
Cuts snap to word boundaries; captions are re-timed onto the new timeline.
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent


def run(cmd):
    subprocess.run(cmd, check=True)


def snap(words, start, end):
    inside = [w for w in words if start - 0.05 <= w["s"] < end]  # a word belongs to the cut if it starts inside it
    if not inside:
        return start, end, []
    i0, i1 = words.index(inside[0]), words.index(inside[-1])
    prev_e = words[i0 - 1]["e"] if i0 > 0 else 0
    next_s = words[i1 + 1]["s"] if i1 + 1 < len(words) else inside[-1]["e"] + 0.3
    s = max(prev_e, inside[0]["s"] - 0.06)
    e = min(next_s, inside[-1]["e"] + 0.12)
    return s, e, inside


def apply_fixes(words, fix):
    out = []
    for w in words:
        key = w["w"].lower().strip(",.?!")
        if key in fix:
            rep = fix[key]
            if rep == "":  # merge into previous word (e.g. "or" + "tan" -> "rattan")
                continue
            tail = w["w"][len(w["w"].rstrip(",.?!")):]
            w = {**w, "w": rep + tail}
        out.append(w)
    return out


def main(edl_path, out):
    edl = json.loads(Path(edl_path).read_text())
    base = Path(edl_path).parent
    work = Path(out).with_suffix("")
    work.mkdir(parents=True, exist_ok=True)
    inputs, filt, words, t = [], [], [], 0.0
    for i, seg in enumerate(edl["segments"]):
        src = (base / seg["src"]).resolve()
        sw = json.loads(src.with_suffix(".words.json").read_text())
        s, e, inside = snap(sw, seg["start"], seg["end"])
        inputs += ["-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", str(src)]
        d = e - s
        filt.append(f"[{i}:v]setpts=PTS-STARTPTS,fps=30,scale=1080:1920,setsar=1[v{i}];"
                    f"[{i}:a]asetpts=PTS-STARTPTS,afade=t=in:d=0.02,afade=t=out:st={d - 0.03:.3f}:d=0.03[a{i}]")
        words += [{"w": w["w"], "s": round(w["s"] - s + t, 3), "e": round(w["e"] - s + t, 3)} for w in inside]
        t += d
    n = len(edl["segments"])
    chain = "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca]"
    post = "[cv]eq=saturation=1.06:contrast=1.03,colorbalance=rs=.03:bs=-.03:rm=.02:bm=-.02"
    if edl.get("cover"):
        x, y, w, h = edl["cover"]
        post += f",split[m][b];[b]crop={w}:{h}:{x}:{y},boxblur=24:3[bl];[m][bl]overlay={x}:{y}"
    post += "[gv];[ca]loudnorm=I=-14:TP=-1.5:LRA=11[ga]"
    cut = work / "cut.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt) + ";" + chain + ";" + post,
         "-map", "[gv]", "-map", "[ga]", "-c:v", "libx264", "-crf", "17", "-preset", "medium",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(cut)])
    words = apply_fixes(words, {k.lower(): v for k, v in edl.get("fix", {}).items()})
    spec = work / "captions.json"
    spec.write_text(json.dumps({"duration": t, "fps": 30, "title": edl.get("title", ""), "words": words,
                                "style": edl.get("style", "stacked"), "top": edl.get("top"),
                                "emphasis": [e.lower() for e in edl.get("emphasis", [])]}))
    overlay = work / "overlay.webm"
    run(["node", str(HERE / "captions.mjs"), str(spec), str(overlay)])
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(cut), "-c:v", "libvpx-vp9", "-i", str(overlay),
         "-filter_complex", "[0:v][1:v]overlay=0:0[v]", "-map", "[v]", "-map", "0:a",
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out])
    (work / "transcript.txt").write_text(" ".join(w["w"] for w in words))
    print(f"{out}  {t:.1f}s")


if __name__ == "__main__":
    main(*sys.argv[1:3])
