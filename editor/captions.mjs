// Renders word-by-word captions + title to a transparent WebM with headless Chrome.
import puppeteer from "puppeteer";
import { readFileSync, mkdtempSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [specPath, outPath] = process.argv.slice(2);
const spec = JSON.parse(readFileSync(specPath, "utf8"));
const frames = mkdtempSync(join(tmpdir(), "cap-"));

const html = `<html><body style="margin:0;width:1080px;height:1920px;background:transparent;font-family:Arial Black,Impact,sans-serif">
<div id="t" style="position:absolute;top:180px;width:100%;text-align:center;font-size:72px;color:#fff;
 text-shadow:0 6px 18px #000;padding:0 60px;box-sizing:border-box"></div>
<div id="c" style="position:absolute;top:1250px;width:100%;text-align:center;font-size:96px;line-height:1.1;
 color:#fff;-webkit-text-stroke:6px #000;paint-order:stroke fill;padding:0 70px;box-sizing:border-box"></div>
<script>
const S=${JSON.stringify(spec)};
document.getElementById('t').textContent=S.title||'';
const groups=[];let g=[];
for(const w of S.words){g.push(w);if(g.length===3||/[.?!,]$/.test(w.w)){groups.push(g);g=[]}}
if(g.length)groups.push(g);
window.draw=t=>{
  document.getElementById('t').style.opacity=t<3?1:0;
  const grp=groups.find(x=>t>=x[0].s&&t<=x.at(-1).e+0.25);
  document.getElementById('c').innerHTML=grp?grp.map(w=>
    '<span style="color:'+(t>=w.s&&t<=w.e?'#FFE14D':'#fff')+'">'+w.w.toUpperCase()+'</span>').join(' '):'';
};
</script></body></html>`;

const browser = await puppeteer.launch({
  executablePath: process.env.CHROME_PATH || undefined,
  args: ["--no-sandbox"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1080, height: 1920 });
await page.setContent(html);
const n = Math.ceil(spec.duration * spec.fps);
for (let i = 0; i < n; i++) {
  await page.evaluate((t) => window.draw(t), i / spec.fps);
  await page.screenshot({ path: join(frames, `${String(i).padStart(6, "0")}.png`), omitBackground: true });
}
await browser.close();
const r = spawnSync("ffmpeg", ["-y", "-framerate", String(spec.fps), "-i", join(frames, "%06d.png"),
  "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "2M", outPath], { stdio: "inherit" });
process.exit(r.status);
