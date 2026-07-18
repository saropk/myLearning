import { useFrame } from "@react-three/fiber";
import React, { useMemo, useRef } from "react";
import * as THREE from "three";
import { scrollState } from "../scroll.js";

// The almond fissure: upper and lower lids floating in space (no face),
// meeting at pointed corners, lashes fanning off the lid margins. The
// lash-line is the "fish curve" — a skewed sine arc with a lifted outer
// corner. Lid shells hug the globe; geometry is rebuilt each frame so
// blinks and the scroll-driven opening are real lid movement.

const SEG_U = 56;
const SEG_V = 16;
const R = 1.05;
const W = 0.94;

function lashLineY(t, H, tilt, peakWarp) {
  // Real lids are asymmetric: the upper arc peaks toward the inner third
  // (peakWarp < 1 shifts the peak inward), the lower sits flatter with
  // its peak toward the outer third (peakWarp > 1). Tilt (the outer-
  // corner lift) is damped by the arc so both lash lines land on exactly
  // the same corner points. t: 0 = inner corner, 1 = outer corner.
  const arc = Math.sin(Math.PI * Math.pow(t, peakWarp));
  return H * Math.pow(arc, 0.9) + tilt * (t - 0.5) * arc * 2;
}

function lidParams(isUpper, open) {
  return {
    // The upper aperture is deep enough that the lid still crosses the
    // top of the iris (radius 0.60) — a full visible iris circle is
    // what reads as cartoon.
    H: (isUpper ? 0.56 : 0.36) * open + 0.015,
    tilt: isUpper ? 0.06 : -0.02,
    peakWarp: isUpper ? 0.82 : 1.22,
    sign: isUpper ? 1 : -1,
    yFar: isUpper ? 0.99 : -0.97,
  };
}

function fillLid(pos, nor, isUpper, open) {
  const { H, tilt, peakWarp, sign, yFar } = lidParams(isUpper, open);
  let k = 0;
  for (let j = 0; j <= SEG_V; j++) {
    const s = j / SEG_V;
    for (let i = 0; i <= SEG_U; i++) {
      const t = i / SEG_U;
      const x = W * (2 * t - 1);
      const yl = sign * lashLineY(t, H, tilt, peakWarp);
      const yEdge = Math.sqrt(Math.max(R * R * 0.985 - x * x, 0.0001)) * sign;
      const yTarget = isUpper ? Math.min(yFar, yEdge) : Math.max(yFar, yEdge);
      const y = yl + (yTarget - yl) * s;
      // Shell sits on the globe, with a slight lip at the lash margin.
      const lip = (1 - s) * 0.018;
      const z = Math.sqrt(Math.max(R * R - x * x - y * y, 0.0008)) + lip;
      pos[k] = x;
      pos[k + 1] = y;
      pos[k + 2] = z;
      const inv = 1 / Math.hypot(x, y, z);
      nor[k] = x * inv;
      nor[k + 1] = y * inv;
      nor[k + 2] = z * inv;
      k += 3;
    }
  }
}

function makeLidGeometry() {
  const verts = (SEG_U + 1) * (SEG_V + 1);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute(
    "position",
    new THREE.BufferAttribute(new Float32Array(verts * 3), 3)
  );
  geo.setAttribute(
    "normal",
    new THREE.BufferAttribute(new Float32Array(verts * 3), 3)
  );
  const index = [];
  for (let j = 0; j < SEG_V; j++) {
    for (let i = 0; i < SEG_U; i++) {
      const a = j * (SEG_U + 1) + i;
      const b = a + 1;
      const c = a + SEG_U + 1;
      const d = c + 1;
      index.push(a, c, b, b, c, d);
    }
  }
  geo.setIndex(index);
  return geo;
}

const _pos = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _quat = new THREE.Quaternion();
const _scale = new THREE.Vector3();
const _mat = new THREE.Matrix4();
const UP = new THREE.Vector3(0, 1, 0);

function fillLashes(mesh, isUpper, open, seeds) {
  const { H, tilt, peakWarp, sign } = lidParams(isUpper, open);
  const n = mesh.count;
  // Long, swooping lashes (ref: they reach ~20% of the eye's width);
  // lower lashes much shorter and sparser.
  const baseLen = isUpper ? 0.21 : 0.09;
  for (let i = 0; i < n; i++) {
    const seed = seeds[i];
    // cluster jitter: lashes bunch rather than spacing like comb teeth
    const t =
      0.06 + (0.88 * i) / (n - 1) + (seed - 0.5) * 0.018;
    const x = W * (2 * t - 1);
    const y = sign * lashLineY(t, H, tilt, peakWarp);
    const z = Math.sqrt(Math.max(R * R - x * x - y * y, 0.0008)) + 0.012;
    _pos.set(x, y, z);

    // Sweep outward and away from the fissure, fanning with x; the
    // instanced geometry itself carries the curl.
    _dir
      .set(
        x * (isUpper ? 0.5 : 0.4),
        sign * (0.85 + seed * 0.25),
        0.55 - Math.abs(x) * 0.15
      )
      .normalize();
    const len = baseLen * (0.6 + seed * 0.8);
    _quat.setFromUnitVectors(UP, _dir);
    _scale.set(1, len, isUpper ? 1 : 0.55);
    _mat.compose(_pos, _quat, _scale);
    mesh.setMatrixAt(i, _mat);
  }
  mesh.instanceMatrix.needsUpdate = true;
}

export default function Eyelids() {
  const upper = useRef();
  const lower = useRef();
  const upperLashes = useRef();
  const lowerLashes = useRef();
  const lastOpen = useRef(-1);

  const [upperGeo, lowerGeo] = useMemo(
    () => [makeLidGeometry(), makeLidGeometry()],
    []
  );

  // One curved lash template (unit length, curling away from the globe),
  // instanced with varied length/direction. Real lashes curve — straight
  // cones read as comb teeth.
  const lashGeo = useMemo(() => {
    const curve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(0, 0.62, 0.06),
      new THREE.Vector3(0, 0.98, 0.5)
    );
    return new THREE.TubeGeometry(curve, 9, 0.0032, 5, false);
  }, []);
  const seeds = useMemo(() => {
    const rng = [];
    let s = 7;
    for (let i = 0; i < 96; i++) {
      s = (s * 16807) % 2147483647;
      rng.push((s % 1000) / 1000);
    }
    return rng;
  }, []);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const p = scrollState.progress;

    const calm = 1 - THREE.MathUtils.smoothstep(p, 0.0, 0.12);
    // The lids part wider as the camera pushes in — the eye opens to
    // let you through.
    const push = THREE.MathUtils.smoothstep(p, 0.08, 0.28);
    const phase = (t % 8.2) / 8.2;
    const blink = Math.exp(-Math.pow((phase - 0.5) * 30, 2)) * calm;
    const open = (0.8 + push * 0.6) * (1 - blink * 0.97);

    if (Math.abs(open - lastOpen.current) < 0.0004) return;
    lastOpen.current = open;

    for (const [ref, isUpper] of [
      [upper, true],
      [lower, false],
    ]) {
      const geo = ref.current?.geometry;
      if (!geo) continue;
      fillLid(
        geo.attributes.position.array,
        geo.attributes.normal.array,
        isUpper,
        open
      );
      geo.attributes.position.needsUpdate = true;
      geo.attributes.normal.needsUpdate = true;
    }
    if (upperLashes.current) fillLashes(upperLashes.current, true, open, seeds);
    if (lowerLashes.current) fillLashes(lowerLashes.current, false, open, seeds);
  });

  // Void-black lids, unlit: they receive no light at all, so the shells
  // are indistinguishable from the background — the ball silhouette
  // disappears and the fissure + lashes silhouette against the glowing
  // eye, the mood of the iris reference.
  const lidMaterial = (
    <meshBasicMaterial color="#020308" side={THREE.DoubleSide} />
  );

  return (
    <group>
      <mesh ref={upper} geometry={upperGeo}>{lidMaterial}</mesh>
      <mesh ref={lower} geometry={lowerGeo}>{lidMaterial}</mesh>
      <instancedMesh
        ref={upperLashes}
        args={[lashGeo, undefined, 96]}
      >
        <meshStandardMaterial color="#050608" roughness={0.85} />
      </instancedMesh>
      <instancedMesh
        ref={lowerLashes}
        args={[lashGeo, undefined, 52]}
      >
        <meshStandardMaterial color="#050608" roughness={0.85} />
      </instancedMesh>
      {/* Caruncle: the tear-duct mound rounds off the inner corner.
          Muted mauve — present, not gory. */}
      <mesh position={[-0.9, -0.01, 0.44]} scale={[1.5, 0.85, 0.7]}>
        <sphereGeometry args={[0.055, 16, 12]} />
        <meshStandardMaterial color="#43302f" roughness={0.6} />
      </mesh>
    </group>
  );
}
