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

function lashLineY(t, H, tilt) {
  // Tilt (the outer-corner lift) is damped by sin(πt) so both lids'
  // lash lines land on exactly the same corner points.
  const arc = Math.sin(Math.PI * t);
  return H * Math.pow(arc, 0.85) + tilt * (t - 0.5) * arc * 2;
}

function lidParams(isUpper, open) {
  return {
    H: (isUpper ? 0.46 : 0.34) * open + 0.015,
    tilt: isUpper ? 0.05 : -0.03,
    sign: isUpper ? 1 : -1,
    yFar: isUpper ? 0.99 : -0.97,
  };
}

function fillLid(pos, nor, isUpper, open) {
  const { H, tilt, sign, yFar } = lidParams(isUpper, open);
  let k = 0;
  for (let j = 0; j <= SEG_V; j++) {
    const s = j / SEG_V;
    for (let i = 0; i <= SEG_U; i++) {
      const t = i / SEG_U;
      const x = W * (2 * t - 1);
      const yl = sign * lashLineY(t, H, tilt);
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
  const { H, tilt, sign } = lidParams(isUpper, open);
  const n = mesh.count;
  const baseLen = isUpper ? 0.11 : 0.055;
  for (let i = 0; i < n; i++) {
    const t = 0.07 + (0.86 * i) / (n - 1);
    const x = W * (2 * t - 1);
    const y = sign * lashLineY(t, H, tilt);
    const z = Math.sqrt(Math.max(R * R - x * x - y * y, 0.0008)) + 0.012;
    _pos.set(x, y, z);

    // Lashes sweep outward and away from the fissure, fanning with x.
    _dir
      .set(x * 0.35, sign * 1.0, 0.62 - Math.abs(x) * 0.18)
      .normalize();
    const len = baseLen * (0.75 + seeds[i] * 0.5);
    _quat.setFromUnitVectors(UP, _dir);
    _scale.set(1, len, 1);
    _mat.compose(
      _pos.addScaledVector(_dir, len * 0.5),
      _quat,
      _scale
    );
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

  // Near-black lids: the shells dissolve into the starfield so the
  // fissure reads as a floating almond opening in space — no face,
  // no visible ball silhouette. A faint cool sheen keeps the lid
  // curvature legible where the rim light grazes it.
  const lidMaterial = (
    <meshStandardMaterial
      color="#0b0f1a"
      roughness={0.75}
      metalness={0}
      side={THREE.DoubleSide}
    />
  );

  return (
    <group>
      <mesh ref={upper} geometry={upperGeo}>{lidMaterial}</mesh>
      <mesh ref={lower} geometry={lowerGeo}>{lidMaterial}</mesh>
      <instancedMesh ref={upperLashes} args={[undefined, undefined, 72]}>
        <coneGeometry args={[0.0045, 1, 5]} />
        <meshStandardMaterial color="#0a0c12" roughness={0.8} />
      </instancedMesh>
      <instancedMesh ref={lowerLashes} args={[undefined, undefined, 44]}>
        <coneGeometry args={[0.003, 1, 5]} />
        <meshStandardMaterial color="#0a0c12" roughness={0.8} />
      </instancedMesh>
    </group>
  );
}
