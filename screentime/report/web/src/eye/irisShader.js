// Custom GLSL iris: radial stromal fibres, limbal ring, collarette,
// icy-blue palette, animated pupil dilation. The pupil hole is carved
// here; the clock geometry sits just in front of it.

export const irisVertex = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vViewDir;

  void main() {
    vUv = uv;
    vec4 worldPos = modelMatrix * vec4(position, 1.0);
    vViewDir = normalize(cameraPosition - worldPos.xyz);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

export const irisFragment = /* glsl */ `
  uniform float uTime;
  uniform float uPupil;      // pupil radius in disc space, ~0.10..0.30
  varying vec2 vUv;
  varying vec3 vViewDir;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
      mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x),
      f.y);
  }

  float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.55;
    for (int i = 0; i < 4; i++) {
      v += a * noise(p);
      p *= 2.1;
      a *= 0.5;
    }
    return v;
  }

  void main() {
    vec2 c = vUv - 0.5;
    float r = length(c) * 2.0;      // 0 centre → 1 rim
    float theta = atan(c.y, c.x);

    if (r > 1.0) discard;

    // --- stromal fibres: streaks aligned radially, jittered in angle.
    float fibre = fbm(vec2(theta * 14.0, r * 5.5 - uTime * 0.015));
    float fibreFine = fbm(vec2(theta * 42.0 + 7.3, r * 11.0));
    float strands = smoothstep(0.25, 0.85, fibre * 0.65 + fibreFine * 0.45);

    // --- radial zones
    float pupilEdge = smoothstep(uPupil, uPupil + 0.035, r);          // hole
    float collarette = 1.0 - smoothstep(0.0, 0.16, abs(r - (uPupil + 0.13)));
    float limbal = smoothstep(0.78, 1.0, r);                           // dark rim

    // --- icy palette
    vec3 deep = vec3(0.043, 0.102, 0.223);
    vec3 mid  = vec3(0.180, 0.373, 0.640);
    vec3 ice  = vec3(0.560, 0.780, 0.980);

    vec3 col = mix(deep, mid, strands);
    col = mix(col, ice, collarette * 0.55 * (0.4 + 0.6 * strands));
    col += ice * pow(1.0 - r, 2.0) * 0.10;          // inner glow
    col = mix(col, deep * 0.35, limbal);             // limbal ring

    // faint animated shimmer, like moisture catching light
    col += ice * 0.05 * noise(vec2(theta * 6.0, uTime * 0.12));

    // fresnel-ish lift toward grazing view angles
    float grazing = 1.0 - abs(vViewDir.z);
    col += ice * grazing * 0.08;

    // carve the pupil
    col *= pupilEdge;

    gl_FragColor = vec4(col, 1.0);
  }
`;
