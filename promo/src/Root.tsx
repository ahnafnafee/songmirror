import React from "react";
import { Composition } from "remotion";
import { Film } from "./Film";
import cues from "../cues.json";

const frames = Math.round(cues.beats * cues.fps * 60 / cues.bpm);

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="SongMirrorPromo"
        component={Film}
        durationInFrames={frames}
        fps={cues.fps}
        width={1920}
        height={1080}
        defaultProps={{ lite: false }}
      />
      {/* The GIF cut skips the soundtrack and the moving signal texture. */}
      <Composition
        id="SongMirrorPromoLite"
        component={Film}
        durationInFrames={frames}
        fps={cues.fps}
        width={1920}
        height={1080}
        defaultProps={{ lite: true }}
      />
    </>
  );
};
