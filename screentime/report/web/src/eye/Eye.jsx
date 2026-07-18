import { useFrame } from "@react-three/fiber";
import React, { useMemo, useRef } from "react";
import * as THREE from "three";
import { scrollState } from "../scroll.js";
import ClockPupil from "./ClockPupil.jsx";
import Eyelids from "./Eyelids.jsx";
import { irisFragment, irisVertex } from "./irisShader.js";
import { scleraFragment, scleraVertex } from "./scleraShader.js";

// The full eye: the globe (sclera + iris + cornea + clock pupil) drifts
// gently behind a stationary almond fissure of lids and lashes — the
// eyeball moves, the lids stay, as real eyes do. Strain (0..1) reddens
// the sclera.
export default function Eye({ strain = 0.2 }) {
  const drift = useRef();

  const irisUniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uPupil: { value: 0.16 },
    }),
    []
  );
  const scleraUniforms = useMemo(
    () => ({ uStrain: { value: strain } }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const p = scrollState.progress;
    scleraUniforms.uStrain.value = strain;

    // Idle drift — the globe wanders behind the lids, alive before the
    // user touches anything; it calms as the push-in starts.
    const calm = 1.0 - THREE.MathUtils.smoothstep(p, 0.0, 0.12);
    if (drift.current) {
      drift.current.rotation.y =
        Math.sin(t * 0.23) * 0.13 * calm + Math.sin(t * 0.071) * 0.04 * calm;
      drift.current.rotation.x = Math.cos(t * 0.17) * 0.07 * calm;
    }

    // Pupil: slow idle breathing, then dilation as the camera approaches —
    // "time expanding as you near it" (spec: the key beat of Act I).
    const idlePupil = 0.16 + Math.sin(t * 0.5) * 0.015;
    const dilation = THREE.MathUtils.smoothstep(p, 0.10, 0.30) * 0.22;
    irisUniforms.uPupil.value = idlePupil + dilation;
    irisUniforms.uTime.value = t;
  });

  return (
    <group>
      <group ref={drift}>
        {/* Sclera — polar cap cut out of the front so the iris shows.
            Poles face ±Z after the rotation; the front hole radius
            (sin 0.56 ≈ 0.53) matches the iris disc. */}
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <sphereGeometry
            args={[1, 64, 64, 0, Math.PI * 2, 0.56, Math.PI - 0.56]}
          />
          <shaderMaterial
            vertexShader={scleraVertex}
            fragmentShader={scleraFragment}
            uniforms={scleraUniforms}
            side={THREE.DoubleSide}
          />
        </mesh>

        {/* Iris — a disc set into the front of the globe */}
        <mesh position={[0, 0, 0.86]}>
          <circleGeometry args={[0.52, 96]} />
          <shaderMaterial
            vertexShader={irisVertex}
            fragmentShader={irisFragment}
            uniforms={irisUniforms}
          />
        </mesh>

        {/* Clock pupil, floating just in front of the iris */}
        <ClockPupil position={[0, 0, 0.875]} uniforms={irisUniforms} />

        {/* Cornea — refractive shell over the front; the wet highlight */}
        <mesh position={[0, 0, 0.08]} scale={[1, 1, 1.06]}>
          <sphereGeometry args={[0.98, 64, 64, 0, Math.PI * 2, 0, Math.PI]} />
          <meshPhysicalMaterial
            transparent
            opacity={0.22}
            roughness={0.02}
            transmission={0.9}
            thickness={0.4}
            ior={1.376}
            clearcoat={1}
            clearcoatRoughness={0.04}
            color="#bcd8ff"
            side={THREE.FrontSide}
            depthWrite={false}
          />
        </mesh>
      </group>

      {/* The almond fissure: lids + lashes, stationary over the globe */}
      <Eyelids />
    </group>
  );
}
