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
const W = 0.97;
// The whole fissure tilts: the outer corner sits higher than the inner
// (measured off the reference painting).
const CORNER_TILT = 0.07;

function lashLineY(t, H, tilt, peakWarp, sign) {
  // Real lids are asymmetric: the upper arc peaks toward the inner third
  // (peakWarp < 1 shifts the peak inward), the lower sits much flatter
  // with its weight toward the outer third (peakWarp > 1). Tilt is
  // damped by the arc so both lash lines land on exactly the same
  // corner points; CORNER_TILT raises the outer corner for the whole
  // fissure. t: 0 = inner corner, 1 = outer corner. Returns world y.
  const arc = Math.sin(Math.PI * Math.pow(t, peakWarp));
  return (
    sign * (H * Math.pow(arc, 0.9) + tilt * (t - 0.5) * arc * 2) +
    CORNER_TILT * (t - 0.5)
  );
}

function lidParams(isUpper, open) {
  return {
    // Aperture sized so the iris (radius 0.42 — ~43% of fissure width,
    // per the reference) sits with sclera clear on both sides, the
    // upper lid grazing its top.
    H: (isUpper ? 0.58 : 0.30) * open + 0.015,
    tilt: isUpper ? 0.05 : -0.015,
    peakWarp: isUpper ? 0.82 : 1.3,
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
      const yl = lashLineY(t, H, tilt, peakWarp, sign);
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
  // Margin gradient baked into vertex colors: a soft blue-grey ledge at
  // the lash line (the lid's physical presence) falling to the exact
  // background colour within ~30% of the lid span. Vertex colours on a
  // basic material share the background's colour pipeline, so the far
  // lid is genuinely indistinguishable from the void — no silhouette.
  // Vertex colours are linear; the background hex goes through
  // sRGB→linear conversion — convert ours the same way or "matching
  // black" renders ~10× brighter than the background.
  const margin = new THREE.Color(0.1, 0.11, 0.17).convertSRGBToLinear();
  const voidCol = new THREE.Color(0.0078, 0.0118, 0.0314).convertSRGBToLinear();
  const waterC = new THREE.Color(0.05, 0.06, 0.09).convertSRGBToLinear();
  const colors = new Float32Array(verts * 3);
  let k = 0;
  for (let j = 0; j <= SEG_V; j++) {
    const s = j / SEG_V;
    const f = THREE.MathUtils.smoothstep(s, 0.01, 0.3);
    const water = 1 - THREE.MathUtils.smoothstep(s, 0.0, 0.06);
    for (let i = 0; i <= SEG_U; i++) {
      colors[k++] = margin.r * (1 - f) + voidCol.r * f + waterC.r * water;
      colors[k++] = margin.g * (1 - f) + voidCol.g * f + waterC.g * water;
      colors[k++] = margin.b * (1 - f) + voidCol.b * f + waterC.b * water;
    }
  }
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
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
  // Long, swooping lashes; lower lashes much shorter and sparser.
  // Denser and finer than comb teeth — softness comes from count.
  const baseLen = isUpper ? 0.17 : 0.08;
  for (let i = 0; i < n; i++) {
    const seed = seeds[i];
    // cluster jitter: lashes bunch rather than spacing like comb teeth
    const t =
      0.06 + (0.88 * i) / (n - 1) + (seed - 0.5) * 0.018;
    const x = W * (2 * t - 1);
    const y = lashLineY(t, H, tilt, peakWarp, sign);
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
    return new THREE.TubeGeometry(curve, 9, 0.0023, 5, false);
  }, []);
  const seeds = useMemo(() => {
    const rng = [];
    let s = 7;
    for (let i = 0; i < 160; i++) {
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
    const open = (0.74 + push * 0.66) * (1 - blink * 0.97);

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

  // Basic material + baked vertex colours (see makeLidGeometry): the
  // margin ledge is visible, the far lid matches the background exactly.
  const lidMaterial = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        vertexColors: true,
        side: THREE.DoubleSide,
      }),
    []
  );

  return (
    <group>
      <mesh ref={upper} geometry={upperGeo} material={lidMaterial} />
      <mesh ref={lower} geometry={lowerGeo} material={lidMaterial} />
      <instancedMesh
        ref={upperLashes}
        args={[lashGeo, undefined, 140]}
      >
        <meshStandardMaterial color="#050608" roughness={0.85} />
      </instancedMesh>
      <instancedMesh
        ref={lowerLashes}
        args={[lashGeo, undefined, 70]}
      >
        <meshStandardMaterial color="#050608" roughness={0.85} />
      </instancedMesh>
      {/* Caruncle: the tear-duct mound rounds off the inner corner.
          Muted mauve — present, not gory. */}
      <mesh position={[-0.95, -0.035, 0.4]} scale={[1.5, 0.85, 0.7]}>
        <sphereGeometry args={[0.055, 16, 12]} />
        <meshStandardMaterial color="#43302f" roughness={0.6} />
      </mesh>
    </group>
  );
}
