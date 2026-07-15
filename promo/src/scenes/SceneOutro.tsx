import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Mark } from "../components/Mark";
import { SyncRing } from "../components/SyncRing";
import { COLORS } from "../theme";
import { FONT, FONT_MONO } from "../fonts";
import { enter, fadeInOut, rise } from "../util/anim";

export const SceneOutro: React.FC<{ dur: number }> = ({ dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = enter(frame, fps, 0, { stiffness: 90, damping: 16, mass: 1 });
  const scale = interpolate(p, [0, 1], [0.7, 1]);
  const pUrl = enter(frame, fps, 16);
  const pMit = enter(frame, fps, 26);

  return (
    <AbsoluteFill
      style={{
        opacity: fadeInOut(frame, dur, 12, 20),
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 40,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 28,
            transform: `scale(${scale})`,
            opacity: p,
          }}
        >
          <div
            style={{
              position: "relative",
              width: 132,
              height: 132,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div style={{ position: "absolute" }}>
              <SyncRing size={128} stroke={4} spinFrames={320} drawIn={30} opacity={0.45} />
            </div>
            <Mark size={80} glow={0.55} />
          </div>
          <div
            style={{
              fontFamily: FONT,
              fontWeight: 800,
              fontSize: 78,
              letterSpacing: -2,
              lineHeight: 1,
            }}
          >
            <span style={{ color: COLORS.text }}>Song</span>
            <span style={{ color: COLORS.orange }}>Mirror</span>
          </div>
        </div>

        <div
          style={{
            opacity: pUrl,
            transform: `translateY(${rise(pUrl, 16)}px)`,
            fontFamily: FONT_MONO,
            fontSize: 30,
            letterSpacing: 0.5,
            padding: "16px 32px",
            borderRadius: 14,
            background: "rgba(242,96,26,0.08)",
            border: `1px solid rgba(242,96,26,0.45)`,
          }}
        >
          <span style={{ color: COLORS.textMuted }}>github.com/</span>
          <span style={{ color: COLORS.orange }}>ahnafnafee/songmirror</span>
        </div>

        <div
          style={{
            opacity: pMit,
            fontFamily: FONT,
            fontWeight: 500,
            fontSize: 24,
            letterSpacing: 0.4,
            color: COLORS.textMuted,
          }}
        >
          MIT licensed · Self-hosted · Open source
        </div>
      </div>
    </AbsoluteFill>
  );
};
