// Builds the README promo assets end to end and writes them to
// ../.github/assets/ : a full-quality MP4 and an optimized looping GIF.
//
// Requirements on PATH: ffmpeg. gifsicle is fetched on demand via `npx`.
//
// Pipeline:
//   1. Render the full-quality composition -> MP4 (H.264).
//   2. Render the "lite" composition (static background) -> MP4, used purely
//      as the GIF source: near-identical held frames compress far better.
//   3. ffmpeg palettegen/paletteuse -> a high-quality 256-colour GIF.
//   4. gifsicle -O3 --lossy -> shrink it under the README size budget.
//
// Run with: pnpm build:assets   (or: node scripts/build-assets.mjs)

import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { copyFileSync, mkdirSync } from "node:fs";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const assets = resolve(root, "..", ".github", "assets");

// GIF tuning — keeps ~1000px width / ~15fps / <8MB with headroom.
const FPS = 15;
const WIDTH = 1000;
const COLORS = 256;
const LOSSY = 32;

const run = (cmd) => {
  console.log(`\n$ ${cmd}`);
  execSync(cmd, { cwd: root, stdio: "inherit" });
};

mkdirSync(resolve(root, "out"), { recursive: true });
mkdirSync(assets, { recursive: true });

// 1. Full-quality MP4 deliverable.
run(`npx remotion render SongMirrorPromo out/songmirror-demo.mp4 --codec=h264 --crf=18`);
copyFileSync(
  resolve(root, "out/songmirror-demo.mp4"),
  resolve(assets, "songmirror-demo.mp4"),
);

// 2. Lite MP4 — GIF source only.
run(`npx remotion render SongMirrorPromoLite out/songmirror-lite.mp4 --codec=h264 --crf=16`);

// 3. High-quality GIF via a diff-optimised palette.
const scale = `scale=${WIDTH}:-1:flags=lanczos`;
run(
  `ffmpeg -y -i out/songmirror-lite.mp4 -vf "fps=${FPS},${scale},palettegen=stats_mode=diff:max_colors=${COLORS}" out/palette.png`,
);
run(
  `ffmpeg -y -i out/songmirror-lite.mp4 -i out/palette.png -lavfi "fps=${FPS},${scale},paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" out/songmirror-raw.gif`,
);

// 4. Shrink under budget and write the deliverable.
const gifOut = resolve(assets, "songmirror-demo.gif");
run(`npx --yes gifsicle -O3 --lossy=${LOSSY} out/songmirror-raw.gif -o "${gifOut}"`);
copyFileSync(gifOut, resolve(root, "out/songmirror-demo.gif"));

console.log(`\nDone. Wrote:\n  ${resolve(assets, "songmirror-demo.mp4")}\n  ${gifOut}`);
