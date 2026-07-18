import { useFrame } from "@react-three/fiber";
import React, { useMemo, useRef } from "react";
import * as THREE from "three";
import { scrollState } from "./scroll.js";

// Deep-space particle field in two parallax layers, plus a line-segment
// layer that stretches radially with speed — pinpoints at rest, streaks
// as the camera accelerates (peaking later in the warp).
export default function Starfield({ count = 6000 }) {
  const near = useRef();
  const far = useRef();
  const streaks = useRef();

  const [nearGeo, farGeo] = useMemo(() => {
    const make = (n, rMin, rMax) => {
      const positions = new Float32Array(n * 3);
      const sizes = new Float32Array(n);
      for (let i = 0; i < n; i++) {
        // uniform shell distribution
        const r = rMin + Math.pow(Math.random(), 0.6) * (rMax - rMin);
        const phi = Math.random() * Math.PI * 2;
        const cosT = Math.random() * 2 - 1;
        const sinT = Math.sqrt(1 - cosT * cosT);
        positions[i * 3] = r * sinT * Math.cos(phi);
        positions[i * 3 + 1] = r * sinT * Math.sin(phi);
        positions[i * 3 + 2] = r * cosT;
        sizes[i] = 0.5 + Math.random() * 1.6;
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      geo.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
      return geo;
    };
    return [
      make(Math.floor(count * 0.35), 12, 30),
      make(Math.ceil(count * 0.65), 30, 90),
    ];
  }, [count]);

  // Streak lines: two vertices per star (head + tail); the tail vertex is
  // pushed radially outward in view space by uStreak, so lines point away
  // from the direction of travel — the classic hyperspace stretch.
  const [streakGeo, streakMat] = useMemo(() => {
    const src = nearGeo.attributes.position.array;
    const n = Math.floor(src.length / 3 / 2); // half the near stars
    const positions = new Float32Array(n * 6);
    const ends = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) {
      const sx = src[i * 3], sy = src[i * 3 + 1], sz = src[i * 3 + 2];
      positions.set([sx, sy, sz, sx, sy, sz], i * 6);
      ends[i * 2] = 0;
      ends[i * 2 + 1] = 1;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("aEnd", new THREE.BufferAttribute(ends, 1));

    const mat = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uStreak: { value: 0 },
        uAlpha: { value: 0 },
      },
      vertexShader: /* glsl */ `
        attribute float aEnd;
        uniform float uStreak;
        varying float vEnd;
        void main() {
          vEnd = aEnd;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          mv.xyz *= 1.0 + uStreak * 0.28 * aEnd;
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform float uAlpha;
        varying float vEnd;
        void main() {
          gl_FragColor = vec4(vec3(0.62, 0.78, 1.0),
                              uAlpha * (1.0 - vEnd * 0.85));
        }
      `,
    });
    return [geo, mat];
  }, [nearGeo]);

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms: { uOpacity: { value: 1 } },
        vertexShader: /* glsl */ `
          attribute float aSize;
          varying float vTwinkle;
          void main() {
            vec4 mv = modelViewMatrix * vec4(position, 1.0);
            gl_PointSize = aSize * (140.0 / -mv.z);
            vTwinkle = fract(aSize * 17.7);
            gl_Position = projectionMatrix * mv;
          }
        `,
        fragmentShader: /* glsl */ `
          uniform float uOpacity;
          varying float vTwinkle;
          void main() {
            vec2 c = gl_PointCoord - 0.5;
            float d = length(c);
            float glow = smoothstep(0.5, 0.05, d);
            vec3 cold = mix(vec3(0.55, 0.72, 1.0), vec3(0.85, 0.9, 1.0), vTwinkle);
            gl_FragColor = vec4(cold, glow * uOpacity * (0.35 + 0.65 * vTwinkle));
          }
        `,
      }),
    []
  );

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const p = scrollState.progress;
    // Slow rotation for life; slight counter-parallax against the push-in.
    if (near.current) {
      near.current.rotation.y = t * 0.004 + p * 0.35;
      near.current.rotation.z = t * 0.001;
    }
    if (far.current) {
      far.current.rotation.y = t * 0.0015 + p * 0.15;
    }

    // Speed builds through the push-in; the warp (Act II) will drive this
    // well past 1.0 for full hyperspace.
    const speed = THREE.MathUtils.smoothstep(p, 0.06, 0.30);
    material.uniforms.uOpacity.value = 1 - speed * 0.45;
    streakMat.uniforms.uStreak.value = speed * 1.6;
    streakMat.uniforms.uAlpha.value = speed * 0.5;
    if (streaks.current) {
      streaks.current.rotation.copy(near.current?.rotation ?? streaks.current.rotation);
    }
  });

  return (
    <>
      <points ref={near} geometry={nearGeo} material={material} />
      <points ref={far} geometry={farGeo} material={material} />
      <lineSegments ref={streaks} geometry={streakGeo} material={streakMat} />
    </>
  );
}
