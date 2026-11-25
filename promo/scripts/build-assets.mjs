// Build the frontend first, then run pnpm build:assets from promo/.
// The MP4, README GIF, and website poster come from the same cut.

import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { copyFileSync, mkdirSync, readFileSync, statSync } from "node:fs";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const assets = resolve(root, "..", ".github", "assets");

const cue = JSON.parse(readFileSync(resolve(root, "cues.json"), "utf8"));
const posterAt = cue.posterBeat * 60 / cue.bpm;

const run = (cmd) => {
  console.log(`\n$ ${cmd}`);
  execSync(cmd, { cwd: root, stdio: "inherit" });
};

mkdirSync(resolve(root, "out"), { recursive: true });
mkdirSync(assets, { recursive: true });
run("pnpm run prepare:film");
run("pnpm exec remotion render SongMirrorPromo out/launch-render.mp4 --codec=h264 --crf=19 --concurrency=5");
run("ffmpeg -hide_banner -loglevel error -y -i out/launch-render.mp4 -c copy -movflags +faststart out/songmirror-demo.mp4");
run(`ffmpeg -hide_banner -loglevel error -y -ss ${posterAt} -i out/songmirror-demo.mp4 -frames:v 1 -vf scale=1280:-1:flags=lanczos -quality 88 out/trailer-poster.webp`);
run('ffmpeg -hide_banner -loglevel error -y -i out/songmirror-demo.mp4 -filter_complex "[0:v]fps=10,scale=720:-1:flags=lanczos,split[video][palette_input];[palette_input]palettegen=max_colors=96:stats_mode=diff[p];[video][p]paletteuse=dither=none:diff_mode=rectangle" -loop 0 out/songmirror-demo.gif');
if (statSync(resolve(root, "out/songmirror-demo.gif")).size > 8_000_000) {
  throw new Error("The README GIF exceeded the 8 MB budget");
}
for (const name of ["songmirror-demo.mp4", "songmirror-demo.gif", "trailer-poster.webp"]) {
  copyFileSync(resolve(root, "out", name), resolve(assets, name));
  console.log(resolve(assets, name));
}
