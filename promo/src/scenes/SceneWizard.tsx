import React from "react";
import { Showcase } from "../components/Showcase";
import { COLORS } from "../theme";

export const SceneWizard: React.FC<{ dur: number }> = ({ dur }) => (
  <Showcase
    dur={dur}
    side="left"
    eyebrow="Sync"
    title={
      <>
        One-way or
        <br />
        <span style={{ color: COLORS.orange }}>bidirectional</span> — your call.
      </>
    }
    sub="Pick a single source of truth, or let every connected service mirror every other. N-way sync, on your schedule."
    src="shots/wizard.png"
    imgAspect={0.70313}
    label="songmirror · new sync"
    panFrom={0.32}
    panTo={0.5}
  />
);
