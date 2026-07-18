// Quality tiers: particle counts and pixel ratio scaled to the GPU.
// Deliberately conservative heuristics — a wellbeing tool must not become
// the thing that's frying the machine.

export function detectTier() {
  try {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl2") || canvas.getContext("webgl");
    if (!gl) return "off";

    const maxTex = gl.getParameter(gl.MAX_TEXTURE_SIZE);
    const isMobile = /Mobi|Android/i.test(navigator.userAgent);
    if (isMobile || maxTex < 8192) return "low";
    if (maxTex >= 16384 && (navigator.hardwareConcurrency || 4) >= 8) {
      return "high";
    }
    return "medium";
  } catch {
    return "off";
  }
}

export const TIERS = {
  low: { stars: 2500, dpr: [1, 1.25], bloom: false },
  medium: { stars: 6000, dpr: [1, 1.5], bloom: true },
  high: { stars: 12000, dpr: [1, 2], bloom: true },
};

export function prefersReducedMotion() {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}
