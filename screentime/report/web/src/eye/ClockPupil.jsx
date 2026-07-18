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
  const hourMat = useRef();
  const minuteMat = useRef();
  const pinMat = useRef();
  const vortexA = useRef();
  const vortexB = useRef();

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const p = scrollState.progress;

    // The ring tracks the pupil radius from the iris shader (disc space
    // 0..1 maps to iris radius 0.60).
    const pupilR = uniforms.uPupil.value * 0.6 * 2.0;
    if (group.current) {
      group.current.scale.setScalar(pupilR / 0.17);
    }

    // Hands sweep faster the closer the camera gets — and past the point
    // of readability they smear into a spinning vortex: time dissolving
    // as you enter it.
    const push = THREE.MathUtils.smoothstep(p, 0.10, 0.30);
    const accel = 1.0 + push * push * 220.0;
    const vortex = THREE.MathUtils.smoothstep(p, 0.20, 0.27);

    if (minuteHand.current) minuteHand.current.rotation.z = -t * 0.11 * accel;
    if (hourHand.current) hourHand.current.rotation.z = -t * 0.009 * accel;
    if (minuteMat.current) minuteMat.current.opacity = 1 - vortex;
    if (hourMat.current) hourMat.current.opacity = 1 - vortex;
    // The pin would otherwise fill the frame at close range — the camera
    // flies into blackness, not into a button.
    if (pinMat.current) pinMat.current.opacity = 1 - vortex;

    // Two blur arcs at different radii/speeds read as motion smear.
    if (vortexA.current) {
      vortexA.current.rotation.z = -t * 9.0;
      vortexA.current.material.opacity = vortex * 0.3;
    }
    if (vortexB.current) {
      vortexB.current.rotation.z = -t * 14.0 - 2.1;
      vortexB.current.material.opacity = vortex * 0.22;
    }
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
            ref={minuteMat}
            transparent
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
            ref={hourMat}
            transparent
            color={dark}
            emissive={rim}
            emissiveIntensity={1.1}
          />
        </mesh>
      </group>
      {/* vortex smear arcs — thin additive trails, only at the through
          moment, spinning fast enough to read as motion blur */}
      <mesh ref={vortexA} position={[0, 0, 0.006]}>
        <ringGeometry args={[0.095, 0.118, 64, 1, 0, 4.4]} />
        <meshBasicMaterial
          transparent
          opacity={0}
          color="#2f5fae"
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>
      <mesh ref={vortexB} position={[0, 0, 0.007]}>
        <ringGeometry args={[0.055, 0.07, 64, 1, 0, 3.1]} />
        <meshBasicMaterial
          transparent
          opacity={0}
          color="#4f83d8"
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>
      {/* centre pin */}
      <mesh position={[0, 0, 0.005]}>
        <circleGeometry args={[0.012, 24]} />
        <meshStandardMaterial
          ref={pinMat}
          transparent
          color={rim}
          emissive={rim}
          emissiveIntensity={1.4}
        />
      </mesh>
    </group>
  );
}
