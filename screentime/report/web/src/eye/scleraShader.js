// Sclera with strain-driven bloodshot veins. uStrain (0..1) comes from the
// day's eye-strain score: 0 = clear white, 1 = angry. Veins are procedural
// ridged noise radiating from the periphery toward the iris; their reach
// and intensity grow with strain, so the eye itself is the first data
// visualization the viewer reads.

export const scleraVertex = /* glsl */ `
  varying vec3 vNormalV;
  varying vec3 vDir;

  void main() {
    vNormalV = normalize(normalMatrix * normal);
    vDir = normalize(position);      // object space: +Z is the iris axis
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

export const scleraFragment = /* glsl */ `
  uniform float uStrain;
  varying vec3 vNormalV;
  varying vec3 vDir;

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
      p *= 2.15;
      a *= 0.5;
    }
    return v;
  }

  void main() {
    vec3 n = normalize(vNormalV);

    // Museum lighting approximation: one cool key + blue rim.
    float lam = max(dot(n, normalize(vec3(0.45, 0.32, 0.83))), 0.0);
    float rim = pow(1.0 - max(n.z, 0.0), 2.6);
    vec3 col = vec3(0.90, 0.87, 0.84) * (0.26 + 0.74 * lam)
             + vec3(0.35, 0.5, 0.9) * rim * 0.14;

    // The upper lid casts a soft shadow onto the globe, and the corners
    // fall off into shadow — a sclera that is evenly white everywhere is
    // a big part of what reads as fake. (Object space: world-up = -z,
    // world-x = x after the mesh's +90° X rotation.)
    float up = clamp(-vDir.z, 0.0, 1.0);
    col *= 1.0 - smoothstep(0.05, 0.7, up) * 0.5;
    col *= 1.0 - smoothstep(0.55, 0.95, abs(vDir.x)) * 0.4;

    // --- veins. front = 1 on the iris axis, 0 at the equator.
    // The mesh is rotated +90° about X so the geometry pole faces the
    // viewer: in object space the iris axis is +Y.
    float front = clamp(vDir.y, 0.0, 1.0);
    float theta = atan(vDir.z, vDir.x);

    // ridged noise: thin bright lines out of fbm
    float band = fbm(vec2(theta * 7.0, front * 9.0));
    float ridge = 1.0 - abs(band * 2.0 - 1.0);
    float fine = fbm(vec2(theta * 21.0 + 4.7, front * 15.0));
    float vein = smoothstep(0.72, 0.94, ridge * (0.7 + 0.5 * fine));

    // veins creep from the periphery toward the iris as strain rises
    float reach = 0.15 + 0.8 * uStrain;
    float visible = clamp((reach - front) * 3.5, 0.0, 1.0)
                  + smoothstep(0.4, 0.0, front) * 0.35;

    vec3 blood = vec3(0.52, 0.08, 0.06);
    col = mix(col, blood, vein * clamp(visible, 0.0, 1.0)
                           * (0.25 + 0.75 * uStrain));

    // overall tired flush at high strain, strongest at the periphery
    col = mix(col, vec3(0.82, 0.5, 0.45),
              0.14 * uStrain * (1.0 - front));

    gl_FragColor = vec4(col, 1.0);
  }
`;
