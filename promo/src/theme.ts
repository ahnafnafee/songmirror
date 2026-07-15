// Central brand + layout tokens for the SongMirror promo.

export const COLORS = {
  // Near-black stage
  bg: "#0E0E0E",
  bgDeep: "#080808",
  panel: "#161513",
  panelBorder: "rgba(255,255,255,0.08)",

  // Vivid tangerine brand
  orange: "#F2601A",
  orangeBright: "#FF7A2E",
  amber: "#FDBA74",
  ember: "#C2410C",

  // Cream (from the light wordmark lockup)
  cream: "#EDE6D8",

  // Type
  text: "#F6F3EE",
  textMuted: "#A7A199",
  textFaint: "#6E6963",

  // Service brand accents
  spotify: "#1DB954",
  apple: "#FA2D48",
  ytmusic: "#FF3B30",
  jellyfin: "#AA5CC3",
} as const;

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

// Crossfade overlap between scenes (frames).
export const XF = 12;

// Scene timeline. Each scene starts XF frames before the previous ends so the
// per-scene opacity fades overlap into a continuous crossfade.
type SceneDef = { id: string; from: number; dur: number };

const build = (durations: { id: string; dur: number }[]): SceneDef[] => {
  const out: SceneDef[] = [];
  let cursor = 0;
  for (const d of durations) {
    out.push({ id: d.id, from: cursor, dur: d.dur });
    cursor += d.dur - XF;
  }
  return out;
};

export const SCENES = build([
  { id: "logo", dur: 100 },
  { id: "tagline", dur: 112 },
  { id: "dashboard", dur: 116 },
  { id: "wizard", dur: 116 },
  { id: "transfers", dur: 122 },
  { id: "bullets", dur: 108 },
  { id: "outro", dur: 118 },
]);

export const scene = (id: string): SceneDef => {
  const s = SCENES.find((x) => x.id === id);
  if (!s) throw new Error(`Unknown scene ${id}`);
  return s;
};

export const TOTAL_FRAMES =
  SCENES[SCENES.length - 1].from + SCENES[SCENES.length - 1].dur;
