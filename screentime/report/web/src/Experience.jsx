import { Canvas } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import React from "react";
import CameraRig from "./CameraRig.jsx";
import Eye from "./eye/Eye.jsx";
import Starfield from "./Starfield.jsx";
import { TIERS } from "./quality.js";

export default function Experience({ tier, strain = 0.2 }) {
  const q = TIERS[tier] ?? TIERS.medium;

  return (
    <Canvas
      dpr={q.dpr}
      camera={{ position: [0.9, 0.25, 5.2], fov: 42 }}
      gl={{ antialias: true, alpha: false }}
      style={{
        position: "fixed",
        inset: 0,
        background: "#020308",
      }}
    >
      <color attach="background" args={["#020308"]} />

      {/* Museum lighting: one cool key, a blue rim from behind, no fill. */}
      <directionalLight position={[3, 2.2, 4]} intensity={2.1} color="#dbe8ff" />
      <pointLight position={[-4, -1, -3]} intensity={9} color="#3f6fd8" />

      <Starfield count={q.stars} />
      <Eye strain={strain} />
      <CameraRig />

      {q.bloom && (
        <EffectComposer>
          <Bloom
            intensity={0.55}
            luminanceThreshold={0.35}
            luminanceSmoothing={0.3}
            mipmapBlur
          />
        </EffectComposer>
      )}
    </Canvas>
  );
}
