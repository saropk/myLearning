import { useFrame } from "@react-three/fiber";
import React, { useRef } from "react";
import * as THREE from "three";
import { scrollState } from "../scroll.js";

// The hook of Act I: the pupil is a clock. A thin dark ring with two hands,
// idling at a slow tick — and sweeping faster as the camera pushes in.
export default function ClockPupil({ position, uniforms }) {
  const group = useRef();
  const hourHand = useRef();
  const minuteHand = useRef();

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const p = scrollState.progress;

    // The ring tracks the pupil radius from the iris shader (disc space
    // 0..1 maps to iris radius 0.52).
    const pupilR = uniforms.uPupil.value * 0.52 * 2.0;
    if (group.current) {
      group.current.scale.setScalar(pupilR / 0.17);
    }

    // Hands sweep faster the closer the camera gets — time accelerating
    // as you approach it.
    const accel = 1.0 + THREE.MathUtils.smoothstep(p, 0.10, 0.30) * 40.0;
    if (minuteHand.current) minuteHand.current.rotation.z = -t * 0.11 * accel;
    if (hourHand.current) hourHand.current.rotation.z = -t * 0.009 * accel;
  });

  const dark = "#04060a";
  const rim = "#0d1b33";

  return (
    <group ref={group} position={position}>
      {/* aperture ring */}
      <mesh>
        <ringGeometry args={[0.145, 0.17, 64]} />
        <meshStandardMaterial
          color={rim}
          emissive={rim}
          emissiveIntensity={0.65}
          roughness={0.6}
        />
      </mesh>
      {/* pupil disc backing (near-black, slight depth) */}
      <mesh position={[0, 0, -0.002]}>
        <circleGeometry args={[0.15, 64]} />
        <meshBasicMaterial color={dark} />
      </mesh>
      {/* minute hand */}
      <group ref={minuteHand}>
        <mesh position={[0, 0.062, 0.004]}>
          <planeGeometry args={[0.012, 0.124]} />
          <meshStandardMaterial
            color={dark}
            emissive={rim}
            emissiveIntensity={1.1}
          />
        </mesh>
      </group>
      {/* hour hand */}
      <group ref={hourHand}>
        <mesh position={[0, 0.04, 0.004]}>
          <planeGeometry args={[0.016, 0.08]} />
          <meshStandardMaterial
            color={dark}
            emissive={rim}
            emissiveIntensity={1.1}
          />
        </mesh>
      </group>
      {/* centre pin */}
      <mesh position={[0, 0, 0.005]}>
        <circleGeometry args={[0.012, 24]} />
        <meshStandardMaterial
          color={rim}
          emissive={rim}
          emissiveIntensity={1.4}
        />
      </mesh>
    </group>
  );
}
