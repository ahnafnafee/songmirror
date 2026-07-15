import React from "react";
import { Img, staticFile } from "remotion";
import { COLORS } from "../theme";
import { FONT_MONO } from "../fonts";

// A browser-window card that frames a screenshot, with a titlebar and the
// ability to vertically pan a tall image via `pan` (0 = top, 1 = bottom).
export const ScreenFrame: React.FC<{
  src: string;
  imgAspect: number;
  width: number;
  viewportHeight: number;
  pan?: number;
  label?: string;
}> = ({ src, imgAspect, width, viewportHeight, pan = 0, label = "songmirror" }) => {
  const bar = 40;
  const scaledH = width * imgAspect;
  const maxOffset = Math.max(0, scaledH - viewportHeight);
  const offsetY = -pan * maxOffset;
  const dot = (bg: string) => (
    <span style={{ width: 11, height: 11, borderRadius: 6, background: bg }} />
  );
  return (
    <div
      style={{
        width,
        borderRadius: 18,
        background: "#0c0b0a",
        border: `1px solid ${COLORS.panelBorder}`,
        boxShadow:
          "0 44px 100px rgba(0,0,0,0.55), 0 10px 26px rgba(0,0,0,0.42)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          height: bar,
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "0 16px",
          background: "linear-gradient(180deg,#1c1b19,#131211)",
          borderBottom: `1px solid ${COLORS.panelBorder}`,
        }}
      >
        {dot("#ff5f57")}
        {dot("#febc2e")}
        {dot("#28c840")}
        <div style={{ flex: 1, display: "flex", justifyContent: "center" }}>
          <div
            style={{
              fontFamily: FONT_MONO,
              fontSize: 13,
              letterSpacing: 1,
              color: COLORS.textFaint,
              background: "rgba(255,255,255,0.04)",
              borderRadius: 8,
              padding: "4px 18px",
            }}
          >
            {label}
          </div>
        </div>
        <span style={{ width: 45 }} />
      </div>
      <div
        style={{
          width,
          height: viewportHeight,
          overflow: "hidden",
          position: "relative",
        }}
      >
        <Img
          src={staticFile(src)}
          style={{
            width,
            height: scaledH,
            transform: `translateY(${offsetY}px)`,
            display: "block",
          }}
        />
      </div>
    </div>
  );
};
