import React from "react";
import { Img, staticFile } from "remotion";

// The SongMirror logo mark with an optional soft tangerine halo behind it.
export const Mark: React.FC<{ size: number; glow?: number }> = ({
  size,
  glow = 0.5,
}) => (
  <div style={{ position: "relative", width: size, height: size }}>
    {glow > 0 && (
      <div
        style={{
          position: "absolute",
          inset: 0,
          filter: `blur(${size * 0.16}px)`,
          opacity: glow,
        }}
      >
        <Img
          src={staticFile("brand/omni-mark.png")}
          style={{ width: size, height: size }}
        />
      </div>
    )}
    <Img
      src={staticFile("brand/omni-mark.png")}
      style={{
        width: size,
        height: size,
        position: "relative",
        filter: "drop-shadow(0 8px 30px rgba(242,96,26,0.35))",
      }}
    />
  </div>
);
