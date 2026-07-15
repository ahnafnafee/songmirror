import React from "react";
import { Showcase } from "../components/Showcase";
import { COLORS } from "../theme";

export const SceneDashboard: React.FC<{ dur: number }> = ({ dur }) => (
  <Showcase
    dur={dur}
    side="right"
    eyebrow="Dashboard"
    title={
      <>
        One place for
        <br />
        <span style={{ color: COLORS.orange }}>every library.</span>
      </>
    }
    sub="See every sync, service and change at a glance — Spotify, Apple Music, YouTube Music and a local Jellyfin mirror."
    src="shots/dashboard.png"
    imgAspect={0.92969}
    label="songmirror · dashboard"
    panFrom={0}
    panTo={0.14}
  />
);
