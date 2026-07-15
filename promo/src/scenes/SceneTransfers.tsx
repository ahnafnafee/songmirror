import React from "react";
import { Showcase } from "../components/Showcase";
import { COLORS } from "../theme";

export const SceneTransfers: React.FC<{ dur: number }> = ({ dur }) => (
  <Showcase
    dur={dur}
    side="right"
    eyebrow="Transfers"
    title={
      <>
        Copy playlists
        <br />
        <span style={{ color: COLORS.orange }}>live.</span>
      </>
    }
    sub="One-off copies between any two services. Watch tracks land in real time — pause, resume or stop whenever."
    src="shots/transfers.png"
    imgAspect={1.13828}
    label="songmirror · transfers"
    panFrom={0.04}
    panTo={0.62}
  />
);
