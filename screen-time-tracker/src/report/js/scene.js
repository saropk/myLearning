/**
 * All 3D actors of the report journey:
 *   starfield & nebulae → the eye (icy iris, hourglass pupil) →
 *   the optic nerve (glowing tube + flowing signal particles + app bubbles) →
 *   the brain (vivid particle cloud).
 */
import * as THREE from '../vendor/three.module.js';

/* ---------------- shared helpers ---------------- */

export function softSpriteTexture(inner = 'rgba(255,255,255,1)', outer = 'rgba(255,255,255,0)') {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, inner);
  grad.addColorStop(0.35, inner.replace(/,1\)$/, ',0.55)'));
  grad.addColorStop(1, outer);
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/* ---------------- starfield & nebulae ---------------- */

export function makeStarfield() {
  const group = new THREE.Group();
  const N = 3500;
  const pos = new Float32Array(N * 3);
  const col = new Float32Array(N * 3);
  const tint = [new THREE.Color('#cfe6ff'), new THREE.Color('#ffffff'), new THREE.Color('#c9b8ff'), new THREE.Color('#9fd8ff')];
  for (let i = 0; i < N; i++) {
    // shell around the whole journey (eye at 0 → brain near z=-16)
    const r = 34 + Math.random() * 32;
    const th = Math.random() * Math.PI * 2;
    const ph = Math.acos(2 * Math.random() - 1);
    pos[i * 3] = r * Math.sin(ph) * Math.cos(th);
    pos[i * 3 + 1] = r * Math.cos(ph) * 0.7;
    pos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th) - 8;
    const c = tint[(Math.random() * tint.length) | 0].clone().multiplyScalar(0.55 + Math.random() * 0.45);
    col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  const stars = new THREE.Points(geo, new THREE.PointsMaterial({
    size: 0.14, map: softSpriteTexture(), vertexColors: true, transparent: true,
    opacity: 0.95, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true,
  }));
  group.add(stars);

  // large soft nebulae sprites
  const nebulaColors = ['rgba(80,130,255,1)', 'rgba(150,90,255,1)', 'rgba(255,110,200,1)', 'rgba(60,190,255,1)'];
  for (let i = 0; i < 7; i++) {
    const tex = softSpriteTexture(nebulaColors[i % nebulaColors.length]);
    const mat = new THREE.SpriteMaterial({
      map: tex, transparent: true, opacity: 0.10 + Math.random() * 0.07,
      depthWrite: false, blending: THREE.AdditiveBlending,
    });
    const sp = new THREE.Sprite(mat);
    const s = 16 + Math.random() * 26;
    sp.scale.set(s, s, 1);
    sp.position.set((Math.random() - 0.5) * 55, (Math.random() - 0.5) * 26, -4 - Math.random() * 26);
    group.add(sp);
  }
  group.userData.update = (t) => { stars.rotation.y = t * 0.008; };
  return group;
}

/* ---------------- the eye ---------------- */

const IRIS_FRAG = /* glsl */`
  varying vec2 vIris; // iris-local coords in [-1, 1]
  uniform float uTime;

  float hash(float n) { return fract(sin(n) * 43758.5453123); }

  // hourglass / sand-clock pupil mask, 1 = inside pupil
  float hourglass(vec2 p) {
    p /= 0.44;                              // pupil size within iris
    float ax = abs(p.x), ay = abs(p.y);
    float w = ay * 0.58 + 0.055;            // bowtie: width grows with |y|
    float body = (1.0 - smoothstep(w - 0.03, w + 0.03, ax)) * (1.0 - smoothstep(0.95, 1.0, ay));
    float cap = (1.0 - smoothstep(0.66, 0.72, ax)) *
                smoothstep(0.82, 0.88, ay) * (1.0 - smoothstep(0.97, 1.03, ay));
    return max(body, cap);
  }

  void main() {
    vec2 p = vIris;
    float r = length(p);
    float a = atan(p.y, p.x);
    if (r > 1.0) discard;

    // icy radial fibres
    float f1 = sin(a * 38.0 + sin(a * 7.0 + uTime * 0.15) * 2.4 + r * 9.0);
    float f2 = sin(a * 61.0 - r * 14.0 + 1.7);
    float fibre = 0.5 + 0.35 * f1 + 0.15 * f2;

    vec3 deep = vec3(0.02, 0.10, 0.30);
    vec3 ice  = vec3(0.45, 0.78, 1.0);
    vec3 frost= vec3(0.85, 0.96, 1.0);
    vec3 col = mix(deep, ice, fibre);
    col = mix(col, frost, smoothstep(0.35, 0.42, r) * (1.0 - smoothstep(0.5, 0.95, r)) * fibre * 0.6);

    // limbal ring (dark outer edge)
    col *= 1.0 - smoothstep(0.82, 1.0, r) * 0.85;
    // glow ring around the pupil
    float pupil = hourglass(p);
    float rim = hourglass(p * 0.90) - pupil;
    col = mix(col, vec3(0.0, 0.02, 0.07), pupil);
    col += vec3(0.5, 0.85, 1.0) * max(rim, 0.0) * (0.9 + 0.35 * sin(uTime * 2.0));

    // trickling "sand" glint inside the lower bulb
    float sand = pupil * smoothstep(0.05, 0.5, -p.y) *
                 (0.5 + 0.5 * sin(p.y * 40.0 + uTime * 3.0)) * 0.25;
    col += vec3(0.65, 0.85, 1.0) * sand;

    gl_FragColor = vec4(col, 1.0);
  }
`;

const RIM_VERT = /* glsl */`
  varying vec3 vN; varying vec3 vW;
  void main() {
    vN = normalize(mat3(modelMatrix) * normal);
    vec4 w = modelMatrix * vec4(position, 1.0);
    vW = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;

function fresnelMaterial(colorHex, power = 2.6, strength = 1.0) {
  return new THREE.ShaderMaterial({
    vertexShader: RIM_VERT,
    fragmentShader: /* glsl */`
      varying vec3 vN; varying vec3 vW;
      uniform vec3 uColor; uniform float uPower; uniform float uStrength;
      void main() {
        vec3 v = normalize(cameraPosition - vW);
        float f = pow(1.0 - abs(dot(normalize(vN), v)), uPower);
        gl_FragColor = vec4(uColor, f * uStrength);
      }
    `,
    uniforms: {
      uColor: { value: new THREE.Color(colorHex) },
      uPower: { value: power },
      uStrength: { value: strength },
    },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });
}

export function makeEye() {
  const group = new THREE.Group();

  const sclera = new THREE.Mesh(
    new THREE.SphereGeometry(1, 64, 64),
    new THREE.MeshStandardMaterial({ color: '#0d1626', roughness: 0.35, metalness: 0.1 }),
  );
  group.add(sclera);

  const rim = new THREE.Mesh(new THREE.SphereGeometry(1.01, 64, 64), fresnelMaterial('#69b7ff', 2.8, 1.1));
  group.add(rim);

  // The iris is a spherical cap sitting on the eyeball itself (a flat disc
  // would be swallowed by the sclera's curvature). The cap is built around
  // +Y and rotated to face +Z; object-space (x, -z) are its local 2D coords.
  const CAP_ANGLE = 0.48; // sin(0.48) ≈ 0.46 lateral radius
  const irisMat = new THREE.ShaderMaterial({
    vertexShader: /* glsl */`
      varying vec2 vIris;
      void main() {
        vIris = vec2(position.x, -position.z) / ${(Math.sin(0.48)).toFixed(4)};
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: IRIS_FRAG,
    uniforms: { uTime: { value: 0 } },
  });
  const iris = new THREE.Mesh(
    new THREE.SphereGeometry(1.005, 64, 32, 0, Math.PI * 2, 0, CAP_ANGLE), irisMat);
  iris.rotation.x = Math.PI / 2;
  group.add(iris);

  const cornea = new THREE.Mesh(new THREE.SphereGeometry(1.06, 48, 48), fresnelMaterial('#bfe4ff', 3.4, 0.35));
  cornea.scale.z = 1.08;
  group.add(cornea);

  group.userData.update = (t) => {
    irisMat.uniforms.uTime.value = t;
    group.rotation.y = Math.sin(t * 0.3) * 0.06;
    group.rotation.x = Math.cos(t * 0.23) * 0.04;
  };
  return group;
}

/* ---------------- the optic nerve ---------------- */

export const NERVE_POINTS = [
  new THREE.Vector3(0, 0, -0.9),
  new THREE.Vector3(0.4, -0.35, -3.0),
  new THREE.Vector3(1.5, 0.35, -6.0),
  new THREE.Vector3(1.2, -0.35, -9.2),
  new THREE.Vector3(2.2, 0.1, -12.4),
  new THREE.Vector3(2.5, -0.15, -15.4),
];

export function makeNerve() {
  const group = new THREE.Group();
  const curve = new THREE.CatmullRomCurve3(NERVE_POINTS);
  curve.curveType = 'centripetal'; // avoids corkscrew kinks on uneven spacing

  const tubeMat = new THREE.ShaderMaterial({
    vertexShader: /* glsl */`
      varying vec2 vUv; varying vec3 vN; varying vec3 vW;
      void main() {
        vUv = uv;
        vN = normalize(mat3(modelMatrix) * normal);
        vec4 w = modelMatrix * vec4(position, 1.0);
        vW = w.xyz;
        gl_Position = projectionMatrix * viewMatrix * w;
      }
    `,
    fragmentShader: /* glsl */`
      varying vec2 vUv; varying vec3 vN; varying vec3 vW;
      uniform float uTime;
      void main() {
        vec3 cyan = vec3(0.30, 0.75, 1.0);
        vec3 violet = vec3(0.72, 0.48, 1.0);
        vec3 base = mix(cyan, violet, vUv.x);
        // signal pulses racing toward the brain
        float pulse = pow(0.5 + 0.5 * sin(vUv.x * 90.0 - uTime * 5.0), 4.0);
        float slow  = pow(0.5 + 0.5 * sin(vUv.x * 14.0 - uTime * 1.2), 2.0);
        vec3 v = normalize(cameraPosition - vW);
        float fres = pow(1.0 - abs(dot(normalize(vN), v)), 1.8);
        float alpha = fres * 0.55 + pulse * 0.45 + slow * 0.18;
        gl_FragColor = vec4(base * (0.7 + pulse * 1.6 + slow * 0.5), alpha);
      }
    `,
    uniforms: { uTime: { value: 0 } },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
  });
  const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 220, 0.11, 16, false), tubeMat);
  group.add(tube);

  // outer sheath glow
  const sheath = new THREE.Mesh(new THREE.TubeGeometry(curve, 160, 0.22, 12, false), fresnelMaterial('#5aa8ff', 2.2, 0.35));
  group.add(sheath);

  // flowing signal particles
  const N = 1400;
  const ts = new Float32Array(N);
  const jit = [];
  const pos = new Float32Array(N * 3);
  const col = new Float32Array(N * 3);
  const cA = new THREE.Color('#7fd0ff'), cB = new THREE.Color('#c79bff');
  for (let i = 0; i < N; i++) {
    ts[i] = Math.random();
    jit.push(new THREE.Vector3((Math.random() - 0.5), (Math.random() - 0.5), (Math.random() - 0.5)).multiplyScalar(0.28));
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  const pts = new THREE.Points(geo, new THREE.PointsMaterial({
    size: 0.07, map: softSpriteTexture(), vertexColors: true, transparent: true,
    depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  group.add(pts);

  const tmp = new THREE.Vector3();
  group.userData.update = (t) => {
    tubeMat.uniforms.uTime.value = t;
    const posAttr = geo.getAttribute('position');
    const colAttr = geo.getAttribute('color');
    for (let i = 0; i < N; i++) {
      const u = (ts[i] + t * 0.045) % 1;
      curve.getPointAt(u, tmp);
      posAttr.setXYZ(i, tmp.x + jit[i].x, tmp.y + jit[i].y, tmp.z + jit[i].z);
      const c = cA.clone().lerp(cB, u);
      const tw = 0.5 + 0.5 * Math.sin(t * 3 + i);
      colAttr.setXYZ(i, c.r * tw, c.g * tw, c.b * tw);
    }
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
  };

  group.userData.curve = curve;
  return group;
}

/** Glowing anchor spheres + connector filaments for app report bubbles. */
export function makeBubbleAnchors(apps, curve) {
  const CAT_COLORS = {
    productive: '#6fe3b0', browsing: '#7fc4ff', communication: '#ffd27f',
    entertainment: '#ff8fc7', other: '#b3a7ff',
  };
  const anchors = [];
  const group = new THREE.Group();
  const n = Math.min(apps.length, 6);
  for (let i = 0; i < n; i++) {
    const u = 0.16 + (i / Math.max(n - 1, 1)) * 0.68;
    const base = curve.getPointAt(u);
    const side = i % 2 === 0 ? 1 : -1;
    const offset = new THREE.Vector3(side * (0.9 + (i % 3) * 0.18), (i % 3 - 1) * 0.55 + 0.35, 0);
    const p = base.clone().add(offset);

    const color = CAT_COLORS[apps[i].category] || CAT_COLORS.other;
    const orb = new THREE.Mesh(new THREE.SphereGeometry(0.11, 24, 24),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9 }));
    orb.position.copy(p);
    const halo = new THREE.Mesh(new THREE.SphereGeometry(0.2, 24, 24), fresnelMaterial(color, 2.0, 0.9));
    halo.position.copy(p);

    const lineGeo = new THREE.BufferGeometry().setFromPoints([base, p]);
    const line = new THREE.Line(lineGeo, new THREE.LineBasicMaterial({
      color, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending,
    }));

    group.add(orb, halo, line);
    anchors.push({ app: apps[i], world: p, u, orb, halo, line, color });
  }
  group.userData.update = (t) => {
    anchors.forEach((a, i) => { a.orb.scale.setScalar(1 + 0.15 * Math.sin(t * 2.2 + i * 1.7)); });
  };
  return { group, anchors };
}

/* ---------------- the brain ---------------- */

export const BRAIN_CENTER = new THREE.Vector3(2.55, 0.05, -16.5);

export function makeBrain() {
  const group = new THREE.Group();
  const N = 16000;
  const pos = new Float32Array(N * 3);
  const col = new Float32Array(N * 3);
  const cL = new THREE.Color('#4a7dff'), cR = new THREE.Color('#ff6ec7'), cTop = new THREE.Color('#b58cff');
  let i = 0;
  while (i < N) {
    // random point in unit ball
    const v = new THREE.Vector3(Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random() * 2 - 1);
    if (v.lengthSq() > 1) continue;
    // shell-bias so the cortex (surface) is denser than the core
    const dir = v.clone().normalize();
    const r = 0.55 + 0.45 * Math.cbrt(v.length());
    let p = dir.multiplyScalar(r);
    // cortical folds
    const fold = 0.045 * (Math.sin(p.x * 11) * Math.sin(p.y * 13 + 1.3) * Math.sin(p.z * 9 + 2.1));
    p.multiplyScalar(1 + fold * 2.2);
    // brain proportions: wider than tall, long front-back
    p.set(p.x * 1.15, p.y * 0.92, p.z * 1.45);
    // interhemispheric groove
    if (Math.abs(p.x) < 0.05 && p.y > -0.15) continue;
    // flatten the base
    if (p.y < -0.62) continue;

    pos[i * 3] = p.x; pos[i * 3 + 1] = p.y; pos[i * 3 + 2] = p.z;
    const mixX = (p.x / 1.15 + 1) / 2;
    const c = cL.clone().lerp(cR, mixX).lerp(cTop, Math.max(p.y, 0) * 0.55);
    const bright = 0.5 + 0.5 * Math.abs(fold) * 9;
    col[i * 3] = c.r * bright; col[i * 3 + 1] = c.g * bright; col[i * 3 + 2] = c.b * bright;
    i++;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  const mat = new THREE.PointsMaterial({
    size: 0.045, map: softSpriteTexture(), vertexColors: true, transparent: true,
    opacity: 0.85, depthWrite: false, blending: THREE.AdditiveBlending,
  });
  const cloud = new THREE.Points(geo, mat);
  group.add(cloud);

  const core = new THREE.Mesh(new THREE.SphereGeometry(0.85, 32, 32), fresnelMaterial('#8f7bff', 1.6, 0.5));
  core.scale.set(1.15, 0.9, 1.4);
  group.add(core);

  group.position.copy(BRAIN_CENTER);
  group.userData.materials = { cloud: mat };
  group.userData.update = (t, reveal = 1) => {
    const pulse = 1 + 0.035 * Math.sin(t * 1.8);
    group.scale.setScalar((0.25 + 0.75 * reveal) * pulse);
    group.rotation.y = t * 0.12;
    mat.opacity = 0.85 * reveal;
    core.material.uniforms.uStrength.value = 0.5 * reveal * (0.8 + 0.4 * Math.sin(t * 1.8));
  };
  return group;
}
