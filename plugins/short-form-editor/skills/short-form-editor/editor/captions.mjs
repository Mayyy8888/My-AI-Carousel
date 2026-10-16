// Renders captions + title to a transparent WebM (default 1080x1920; spec.width/height override) with headless Chrome.
// Styles: "bold" (3-word chunks, bottom, karaoke highlight) and
// "stacked" (editorial kinetic type: phrases build line by line, key word in
// yellow Playfair Display Italic, small white Sen for the rest — brand fonts).
import puppeteer from "puppeteer";
import { readFileSync, mkdtempSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const [specPath, outPath] = process.argv.slice(2);
const spec = JSON.parse(readFileSync(specPath, "utf8"));
const W = spec.width || 1080, H = spec.height || 1920;
const frames = mkdtempSync(join(tmpdir(), "cap-"));
const fontDir = join(dirname(fileURLToPath(import.meta.url)), "fonts");
const font = (f) => `data:font/ttf;base64,${readFileSync(join(fontDir, f)).toString("base64")}`;

const STOP = new Set(("a an the and or but so to of in on at for with from by is are was were be been am i im i'm " +
  "you your we our they their he she it its this that these those my me just really very then than as if " +
  "do did does have has had not no yes can could would should will what when where who how why there here " +
  "about into out up down over all some any more most much many also even get got").split(" "));

// Split words into on-screen phrases: break on sentence punctuation, pauses, or length.
function phrases(words, maxWords) {
  const out = [];
  let cur = [];
  words.forEach((w, i) => {
    cur.push(w);
    const next = words[i + 1];
    if (/[.?!]$/.test(w.w) || !next || next.s - w.e > 0.6 || cur.length >= maxWords) { out.push(cur); cur = []; }
  });
  return out;
}

function pickEmphasis(group, forced) {
  const clean = (w) => w.w.toLowerCase().replace(/[^\w%'-]/g, "");
  const f = group.findIndex((w) => forced.includes(clean(w)));
  if (f >= 0) return f;
  const num = group.findIndex((w) => /\d/.test(w.w));
  if (num >= 0) return num;
  let best = -1, len = 4;
  group.forEach((w, i) => { const c = clean(w); if (!STOP.has(c) && c.length > len) { best = i; len = c.length; } });
  return best;
}

// Lay a phrase out as lines: small words flow together; the emphasis word gets its own line.
function layout(group, emph) {
  const lines = [];
  let cur = [];
  group.forEach((w, i) => {
    if (i === emph) { if (cur.length) lines.push(cur); lines.push([{ ...w, big: true }]); cur = []; }
    else { cur.push(w); if (cur.length >= 3) { lines.push(cur); cur = []; } }
  });
  if (cur.length) lines.push(cur);
  return lines;
}

const css = `
@font-face{font-family:Grotesk;src:url(${font("Sen.ttf")})}
@font-face{font-family:Serif;src:url(${font("PlayfairItalic.ttf")});font-style:italic}
html,body{margin:0;width:${W}px;height:${H}px;background:transparent;overflow:hidden}
.ph{position:absolute;left:0;right:0;display:flex;flex-direction:column;align-items:center;gap:4px}
.ln{display:flex;gap:14px;align-items:baseline;font:700 50px/1.05 Grotesk;color:#fff;letter-spacing:-0.5px;
  text-shadow:0 2px 14px rgba(0,0,0,.35)}
.w{opacity:0;transform:translateY(14px);transition:none;display:inline-block}
.w.on{opacity:1;transform:none}
.big{font:italic 600 128px/1 Serif;color:#F7D417;letter-spacing:-2px;text-shadow:0 3px 18px rgba(0,0,0,.25)}
.title .big{font-size:150px;display:inline-block;margin:6px 0}
.title{position:absolute;top:${spec.titleTop ?? 170}px;left:60px;right:60px;text-align:center;font:700 64px/1.1 Grotesk;color:#fff;
  text-shadow:0 4px 18px rgba(0,0,0,.4)}
`;

const html = `<html><head><style>${css}</style></head><body><div id="root"></div>
<script>
const S = ${JSON.stringify(spec)};
const root = document.getElementById('root');
const groups = ${JSON.stringify(
  spec.style === "stacked"
    ? phrases(spec.words, 10).map((g) => layout(g, pickEmphasis(g, spec.emphasis || [])))
    : phrases(spec.words, 3).map((g) => [g]),
)};
const flat = g => g.flat();
const shift = [-60, 50, -30, 70, -50];  // stagger lines like hand-placed type
groups.forEach((g, gi) => {
  const ph = document.createElement('div');
  ph.className = 'ph'; ph.style.top = (S.style === 'stacked' ? (S.top ?? 330) : 1250) + 'px';
  g.forEach((line, li) => {
    const ln = document.createElement('div');
    ln.className = 'ln';
    if (S.style === 'stacked') ln.style.transform = 'translateX(' + shift[li % shift.length] + 'px)';
    else ln.style.cssText = 'font:900 96px/1.1 Grotesk;-webkit-text-stroke:6px #000;paint-order:stroke fill;text-transform:uppercase';
    line.forEach(w => {
      const s = document.createElement('span');
      s.className = 'w' + (w.big ? ' big' : '');
      if (w.big) { const t = w.w.replace(/[,.!?]$/, ''); s.textContent = t[0].toUpperCase() + t.slice(1); }
      else s.textContent = w.w;
      s.dataset.s = w.s; s.dataset.e = w.e;
      ln.appendChild(s);
    });
    ph.appendChild(ln);
  });
  ph.dataset.s = flat(g)[0].s; ph.dataset.e = flat(g).at(-1).e;
  root.appendChild(ph);
});
if (S.title) { const t = document.createElement('div'); t.className = 'title'; t.id = 'title'; t.innerHTML = S.title.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])).replace(/\\*([^*]+)\\*/g, '<br><span class="big">$1</span><br>'); root.appendChild(t); }
const ease = x => 1 - Math.pow(1 - Math.min(Math.max(x, 0), 1), 3);
window.draw = t => {
  const phs = [...document.querySelectorAll('.ph')];
  phs.forEach((ph, i) => {
    const next = phs[i + 1] ? +phs[i + 1].dataset.s : Infinity;
    const vis = t >= +ph.dataset.s - 0.05 && t < Math.min(next, +ph.dataset.e + 0.8);
    ph.style.display = vis ? 'flex' : 'none';
    if (!vis) return;
    ph.querySelectorAll('.w').forEach(w => {
      const p = ease((t - +w.dataset.s + 0.05) / 0.18);
      w.style.opacity = p;
      w.style.transform = 'translateY(' + (1 - p) * 16 + 'px) scale(' + (w.classList.contains('big') ? 0.9 + 0.1 * p : 1) + ')';
      if (S.style !== 'stacked') w.style.color = t >= +w.dataset.s && t <= +w.dataset.e ? '#FFE14D' : '#fff';
    });
  });
  const ti = document.getElementById('title');
  if (ti) ti.style.opacity = t < 2.5 ? 1 : Math.max(0, 1 - (t - 2.5) / 0.3);
};
</script></body></html>`;

const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || undefined, args: ["--no-sandbox"] });
const page = await browser.newPage();
await page.setViewport({ width: W, height: H });
await page.setContent(html);
await page.evaluate(() => document.fonts.ready);
const n = Math.ceil(spec.duration * spec.fps);
for (let i = 0; i < n; i++) {
  await page.evaluate((t) => window.draw(t), i / spec.fps);
  await page.screenshot({ path: join(frames, `${String(i).padStart(6, "0")}.png`), omitBackground: true });
}
await browser.close();
const r = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-framerate", String(spec.fps), "-i", join(frames, "%06d.png"),
  "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M", outPath], { stdio: "inherit" });
process.exit(r.status);
