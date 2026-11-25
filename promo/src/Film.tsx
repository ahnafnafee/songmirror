import React from "react";
import { AbsoluteFill, Html5Audio, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";
import cues from "../cues.json";

const ink = "#161210";
const cream = "#f6ead9";
const muted = "#d5bcaa";
const copper = "#ff854a";
const framesPerBeat = cues.fps * 60 / cues.bpm;
const timeline = [...cues.scenes].reverse();
const clamp = (value: number) => Math.min(1, Math.max(0, value));
const arrive = (beat: number, delay = 0) => 1 - (1 - clamp((beat - delay) / 0.67)) ** 3;
const row: React.CSSProperties = { flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: "0 102px", gap: 54 };

function Signal({ beat, scene, lite }: { beat: number; scene: string; lite: boolean }) {
  const hook = scene === "hook";
  const closing = scene === "outro";
  const gathering = closing ? 0 : clamp((beat - 45.75) / 1.25);
  const rest = beat >= cues.breakBeat && beat < 48;
  const accent = lite ? 0 : Math.exp(-6 * (beat % 1));
  const phase = lite ? 0 : beat * Math.PI;
  const lock = hook ? arrive(beat, 4.25) : 1;
  const start = hook ? 995 : closing ? 1100 : 180;
  const width = hook ? 745 : closing ? 780 : 1560;
  const amplitude = (hook ? 38 : closing ? 103 : 136) * (1 - gathering * 0.92);
  return (
    <svg width="1920" height="1080" viewBox="0 0 1920 1080" style={{ position: "absolute", inset: 0 }} aria-hidden="true">
      <defs><pattern id="film-grid" width="64" height="64" patternUnits="userSpaceOnUse"><path d="M64 0H0V64" fill="none" stroke="#533323" /></pattern></defs>
      <rect width="1920" height="1080" fill="url(#film-grid)" opacity={rest ? 0.05 : 0.26} />
      {rest ? <circle cx="960" cy="540" r="9" fill={copper} /> : [0, 1, 2].map(lane => {
        const baseline = hook ? 392 + lane * 154 : 449 + lane * 96;
        const opacity = hook ? 0.8 - lane * 0.14 : closing ? 0.43 - lane * 0.09 : 0.24 - lane * 0.05;
        const points = Array.from({ length: 81 }, (_, index) => {
          const position = index / 80;
          const offset = lane * 1.85 * (1 - lock);
          const tone = 0.75 * Math.sin(position * 31 - phase + offset) + 0.25 * Math.sin(position * 68 - phase * 1.1 + offset);
          const response = Math.sin(position * Math.PI) ** 1.35;
          return `${(start + width * position).toFixed(1)},${(baseline + amplitude * response * tone).toFixed(1)}`;
        }).join(" ");
        const playhead = (beat * 0.24 + lane * 0.145 * (1 - lock)) % 1;
        return <g key={lane} opacity={opacity * (1 - gathering * 0.78) + accent * 0.045}>
          {hook && <path d={`M${start} ${baseline}h${width}`} stroke="#5b3825" strokeWidth="2" />}
          <polyline points={points} fill="none" stroke={[copper, "#dc6a38", "#f5c9aa"][lane]} strokeWidth={lane === 0 ? 4 : 2.5} strokeLinejoin="round" />
          {hook && <circle cx={start + playhead * width} cy={baseline} r={8 + 3 * accent} fill={copper} />}
        </g>;
      })}
    </svg>
  );
}

function reveal(localBeat: number, delay: number, color: string): React.CSSProperties {
  const progress = arrive(localBeat, delay);
  return { display: "block", color, transform: `translateY(${44 * (1 - progress)}px)`, clipPath: `inset(${100 * (1 - progress)}% 0 0)` };
}

function Copy({ eyebrow, lines, detail, localBeat, width = 620 }: { eyebrow: string; lines: string[]; detail?: string; localBeat: number; width?: number }) {
  return (
    <div style={{ width, flex: "none" }}>
      <div style={{ ...reveal(localBeat, 0, copper), marginBottom: 29, fontWeight: 780, fontSize: 23, letterSpacing: "0.16em" }}>{eyebrow}</div>
      <div style={{ fontSize: 90, fontWeight: 880, letterSpacing: "-0.066em", lineHeight: 0.99 }}>
        <span style={reveal(localBeat, 0.33, cream)}>{lines[0]}</span>
        <span style={reveal(localBeat, 0.95, copper)}>{lines[1]}</span>
      </div>
      {detail && <div style={{ ...reveal(localBeat, 1.55, muted), fontSize: 30, lineHeight: 1.27, maxWidth: 520, marginTop: 24 }}>{detail}</div>}
    </div>
  );
}

function Feature({ scene, localBeat }: { scene: typeof cues.scenes[number]; localBeat: number }) {
  const reverse = scene.id === "transfer" || scene.id === "local";
  const enter = arrive(localBeat, 0.25);
  const leave = clamp((localBeat - 7.63) / 0.37);
  const side = reverse ? -1 : 1;
  return (
    <AbsoluteFill style={{ ...row, flexDirection: reverse ? "row-reverse" : "row" }}>
      <Copy eyebrow={scene.eyebrow!} lines={scene.headline!} detail={scene.detail} localBeat={localBeat} />
      <div style={{
        width: 1000, flex: "none", overflow: "hidden", background: "#1a1513", border: "2px solid #704631",
        borderRadius: 16, boxShadow: "0 29px 64px #080503b0",
        transform: `translateX(${side * (148 * (1 - enter) - 60 * leave)}px) perspective(2400px) rotateY(${side * (9 - 5 * enter + 9 * leave)}deg)`,
        clipPath: `inset(0 ${(reverse ? 1 - enter : leave) * 100}% 0 ${(reverse ? leave : 1 - enter) * 100}%)`,
      }}>
        <OffthreadVideo src={staticFile(`footage/${scene.id}.mp4`)} muted style={{ display: "block", width: "100%" }} />
      </div>
    </AbsoluteFill>
  );
}

export const Film: React.FC<{ lite?: boolean }> = ({ lite = false }) => {
  const beat = useCurrentFrame() / framesPerBeat;
  const scene = timeline.find(cue => cue.beat <= beat) ?? cues.scenes[0];
  const localBeat = beat - scene.beat;
  const rest = scene.id === "host" && beat >= cues.breakBeat;
  return (
    <AbsoluteFill style={{ fontFamily: "SongMirror Archivo, Arial, sans-serif", background: ink, color: cream, overflow: "hidden" }}>
      <style>{`@font-face{font-family:"SongMirror Archivo";src:url("${staticFile("footage/archivo.woff2")}") format("woff2");font-weight:100 900;font-display:block}`}</style>
      {!lite && <Html5Audio src={staticFile("audio/soundtrack.wav")} />}
      <Signal beat={beat} scene={scene.id} lite={lite} />

      {scene.id === "hook" && (
        <AbsoluteFill style={{ ...row, paddingLeft: 125 }}>
          <Copy eyebrow="PLAYLIST SYNC" lines={["One playlist.", "Three libraries."]} localBeat={localBeat} width={790} />
          <div style={{ position: "absolute", top: 356, left: 1000, display: "grid", gap: 129 }}>
            {["SPOTIFY", "APPLE MUSIC", "YOUTUBE MUSIC"].map((service, index) => (
              <span key={service} style={{ ...reveal(localBeat, 1.1 + index * 0.75, muted), fontSize: 22, fontWeight: 730 }}>{service}</span>
            ))}
          </div>
        </AbsoluteFill>
      )}

      {scene.headline && (
        <Sequence from={scene.beat * framesPerBeat} durationInFrames={8 * framesPerBeat} layout="none">
          <Feature scene={scene} localBeat={localBeat} />
        </Sequence>
      )}

      {scene.id === "host" && !rest && (
        <AbsoluteFill style={row}>
          <Copy eyebrow="SELF-HOSTED" lines={["Run it on", "your server."]} detail="Start with Docker. Open SongMirror in your browser." localBeat={localBeat} />
          <div style={{ position: "relative", width: 1010, height: 600 }}>
            {["dashboard", "playlists", "transfers"].map((asset, index) => {
              const entrance = arrive(localBeat, 0.9 + index * 0.55);
              const collapse = clamp((localBeat - 5.68) / 1.32);
              return <div key={asset} style={{
                position: "absolute", left: 4 + index * 168, top: 28 + index * 112, width: 622,
                height: 352, overflow: "hidden", border: "2px solid #80503a", borderRadius: 12,
                clipPath: `inset(0 ${100 * (1 - entrance)}% 0 0)`,
                transform: `translate(${(1 - entrance) * 118 - collapse * (index * 175 + 160)}px,${collapse * (265 - index * 118)}px) scale(${1 - collapse * 0.99})`,
                opacity: 1 - collapse * 0.95, boxShadow: "0 20px 44px #0503029e",
              }}>
                <Img src={staticFile(`shots/${asset}.png`)} style={{ width: "100%", display: "block" }} />
              </div>;
            })}
          </div>
        </AbsoluteFill>
      )}

      {scene.id === "outro" && (
        <AbsoluteFill style={{ ...row, paddingInline: 125 }}>
          <div>
            <div style={{ ...reveal(localBeat, 0.37, cream), fontSize: 127, fontWeight: 890, letterSpacing: "-0.065em", lineHeight: 1.02 }}>
              Song<span style={{ color: copper }}>Mirror</span>
            </div>
            <div style={{ ...reveal(localBeat, 1.12, muted), marginTop: 26, fontWeight: 660, fontSize: 38 }}>Free, open-source playlist sync</div>
            <div style={{ ...reveal(localBeat, 1.75, copper), marginTop: 20, fontSize: 34 }}>songmirror.ahnafnafee.dev</div>
          </div>
          <div style={{ position: "absolute", right: 150, width: 490, height: 490, display: "grid", placeItems: "center" }}>
            {[0, 1, 2, 3].map(i => <div key={i} style={{
              position: "absolute", border: `${i === 0 ? 4 : 2}px solid ${copper}`, borderRadius: "50%",
              width: 290 + i * 103 + (lite ? 0 : 20 * localBeat), aspectRatio: "1",
              opacity: arrive(localBeat, i * 0.16) * (0.52 - i * 0.1),
            }} />)}
            <Img src={staticFile("brand/omni-mark.png")} style={{ width: 204, height: 204, objectFit: "contain", transform: `scale(${0.34 + 0.66 * arrive(localBeat)})` }} />
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
