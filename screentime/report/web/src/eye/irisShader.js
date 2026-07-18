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
    // High contrast: bright luminous filaments over a near-black field.
    float fibre = fbm(vec2(theta * 16.0, r * 5.5 - uTime * 0.015));
    float fibreFine = fbm(vec2(theta * 48.0 + 7.3, r * 12.0));
    float strands = smoothstep(0.30, 0.88, fibre * 0.62 + fibreFine * 0.5);

    // --- radial zones
    float pupilEdge = smoothstep(uPupil, uPupil + 0.03, r);           // hole
    float collarette = 1.0 - smoothstep(0.0, 0.14, abs(r - (uPupil + 0.11)));
    float limbal = smoothstep(0.60, 0.98, r);        // wide, nearly black rim

    // --- deep cobalt palette: electric blue glowing out of darkness
    vec3 deep = vec3(0.006, 0.028, 0.10);
    vec3 mid  = vec3(0.030, 0.16, 0.52);
    vec3 glow = vec3(0.16, 0.62, 1.0);
    vec3 hot  = vec3(0.55, 0.85, 1.0);

    vec3 col = mix(deep, mid, strands);
    col += glow * pow(strands, 2.2) * 0.85;                 // fibre luminance
    col = mix(col, hot, collarette * 0.45 * (0.3 + 0.7 * strands));
    col += glow * smoothstep(uPupil + 0.16, uPupil + 0.01, r) * 0.35; // pupil-edge halo
    col = mix(col, vec3(0.002, 0.006, 0.02), limbal);       // fade to black edge

    // faint animated shimmer, like moisture catching light
    col += glow * 0.04 * noise(vec2(theta * 6.0, uTime * 0.12));

    // fresnel-ish lift toward grazing view angles
    float grazing = 1.0 - abs(vViewDir.z);
    col += glow * grazing * 0.06;

    // shadow of the upper lid falling across the top of the iris
    float lidShadow = smoothstep(0.30, 0.85, (vUv.y - 0.5) * 2.0);
    col *= 1.0 - lidShadow * 0.5;

    // carve the pupil
    col *= pupilEdge;

    gl_FragColor = vec4(col, 1.0);
  }
`;
