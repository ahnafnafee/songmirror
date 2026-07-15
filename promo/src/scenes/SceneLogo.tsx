import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Mark } from "../components/Mark";
import { SyncRing } from "../components/SyncRing";
import { Eyebrow } from "../components/Eyebrow";
import { COLORS } from "../theme";
import { FONT } from "../fonts";
import { enter, fadeInOut, rise } from "../util/anim";

export const SceneLogo: React.FC<{ dur: number }> = ({ dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = enter(frame, fps, 0, { stiffness: 90, damping: 14, mass: 1 });
  const markScale = interpolate(p, [0, 1], [0.55, 1]);
  const wordP = enter(frame, fps, 14);
  const eyeP = enter(frame, fps, 28);

  return (
    <AbsoluteFill
      style={{
        opacity: fadeInOut(frame, dur, 10, 16),
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 36,
        }}
      >
        <div
          style={{
            position: "relative",
            width: 268,
            height: 268,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div style={{ position: "absolute" }}>
            <SyncRing
              size={256}
              stroke={5}
              spinFrames={240}
              drawIn={34}
              opacity={0.5}
            />
          </div>
          <div style={{ transform: `scale(${markScale})`, opacity: p }}>
            <Mark size={150} glow={0.6} />
          </div>
        </div>

        <div
          style={{
            opacity: wordP,
            transform: `translateY(${rise(wordP, 24)}px)`,
            fontFamily: FONT,
            fontWeight: 800,
            fontSize: 96,
            letterSpacing: -2,
            lineHeight: 1,
            textShadow: "0 6px 44px rgba(242,96,26,0.35)",
          }}
        >
          <span style={{ color: COLORS.text }}>Song</span>
          <span style={{ color: COLORS.orange }}>Mirror</span>
        </div>

        <div style={{ opacity: eyeP }}>
          <Eyebrow align="center" color={COLORS.textMuted} size={22}>
            Playlist sync, everywhere
          </Eyebrow>
        </div>
      </div>
    </AbsoluteFill>
  );
};
