import React, { useEffect, useRef, useState } from "react";
import Experience from "./Experience.jsx";
import { detectTier, prefersReducedMotion } from "./quality.js";
import { initScroll, scrollState } from "./scroll.js";
import { computeStrain, loadReport } from "./strain.js";

const PLAIN_URL = "http://127.0.0.1:5177/";

// Act I ends inside the pupil: a black veil resolves in as the pupil fills
// the frame (the scene-handoff moment where Act II will take over).
function BlackVeil() {
  const ref = useRef();
  useEffect(() => {
    let raf;
    const loop = () => {
      const p = scrollState.progress;
      const a = Math.min(1, Math.max(0, (p - 0.27) / 0.04));
      if (ref.current) {
        ref.current.style.opacity = a;
        ref.current.style.pointerEvents = a > 0.9 ? "auto" : "none";
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div
      ref={ref}
      style={{
        position: "fixed",
        inset: 0,
        background: "#000",
        opacity: 0,
        display: "grid",
        placeItems: "center",
        zIndex: 3,
      }}
    >
      <p style={{ color: "#31435f", letterSpacing: "0.3em", fontSize: 13 }}>
        THROUGH THE PUPIL — ACT II BEGINS HERE
      </p>
    </div>
  );
}

function Hud() {
  return (
    <>
      <header
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "1.4rem 2rem",
          zIndex: 4,
          mixBlendMode: "screen",
        }}
      >
        <span
          style={{
            letterSpacing: "0.35em",
            fontSize: 13,
            fontWeight: 600,
            color: "#7fb8ff",
          }}
        >
          SCREEN&nbsp;TIME
        </span>
        <a
          href={PLAIN_URL}
          style={{
            color: "#6c7a92",
            fontSize: 12,
            letterSpacing: "0.12em",
            textDecoration: "none",
            border: "1px solid #182138",
            borderRadius: 999,
            padding: "0.35rem 0.9rem",
          }}
        >
          plain numbers
        </a>
      </header>
      <div
        style={{
          position: "fixed",
          bottom: "1.6rem",
          left: 0,
          right: 0,
          textAlign: "center",
          zIndex: 4,
          color: "#31435f",
          fontSize: 12,
          letterSpacing: "0.25em",
          animation: "pulse 2.6s ease-in-out infinite",
        }}
      >
        SCROLL
        <style>{`@keyframes pulse { 0%,100% {opacity:.35} 50% {opacity:.9} }`}</style>
      </div>
    </>
  );
}

function StaticFallback({ reason }) {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        textAlign: "center",
        padding: "2rem",
      }}
    >
      <div>
        <p style={{ color: "#7fb8ff", letterSpacing: "0.3em", fontSize: 13 }}>
          SCREEN TIME
        </p>
        <p style={{ color: "#6c7a92", maxWidth: "34rem", margin: "1.2rem auto" }}>
          {reason === "motion"
            ? "Reduced motion is on, so the 3D journey stays parked."
            : "This device can't run the 3D journey."}{" "}
          The full report is available as plain numbers — same data, no
          spectacle.
        </p>
        <a href={PLAIN_URL} style={{ color: "#7fb8ff" }}>
          Open the report →
        </a>
      </div>
    </main>
  );
}

export default function App() {
  const [tier] = useState(detectTier);
  const [strain, setStrain] = useState(0.2);
  const reduced = prefersReducedMotion();

  useEffect(() => {
    // Look-dev: ?strain=0.9 pins the bloodshot level directly.
    const override = new URLSearchParams(location.search).get("strain");
    if (override !== null) {
      setStrain(Math.min(1, Math.max(0, parseFloat(override) || 0)));
      return;
    }
    loadReport().then((report) => setStrain(computeStrain(report)));
  }, []);

  useEffect(() => {
    if (reduced || tier === "off") return undefined;
    return initScroll();
  }, [reduced, tier]);

  if (reduced) return <StaticFallback reason="motion" />;
  if (tier === "off") return <StaticFallback reason="gpu" />;

  return (
    <>
      {/* Scroll runway: Act I owns 0–30% of it. Acts II–III extend this. */}
      <div style={{ height: "400vh" }} />
      <Experience tier={tier} strain={strain} />
      <BlackVeil />
      <Hud />
    </>
  );
}
