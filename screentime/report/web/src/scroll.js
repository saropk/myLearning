import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";

gsap.registerPlugin(ScrollTrigger);

// One mutable scroll state, read every frame inside the Canvas. Scroll is
// the master timeline scrubber: 0 at the top, 1 at the end of the journey.
export const scrollState = { progress: 0 };

export function initScroll() {
  // Look-dev: ?p=0.18 pins the timeline at a fixed progress so any beat
  // of the sequence can be inspected (or screenshotted) without scrolling.
  const fixed = new URLSearchParams(location.search).get("p");
  if (fixed !== null) {
    scrollState.progress = Math.min(1, Math.max(0, parseFloat(fixed) || 0));
    return () => {};
  }

  const lenis = new Lenis({
    smoothWheel: true,
    // Inertial smoothing is what keeps a scrubbed animation from stepping.
    lerp: 0.09,
  });

  lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add((time) => lenis.raf(time * 1000));
  gsap.ticker.lagSmoothing(0);

  const trigger = ScrollTrigger.create({
    trigger: document.body,
    start: "top top",
    end: "bottom bottom",
    scrub: true,
    onUpdate: (self) => {
      scrollState.progress = self.progress;
    },
  });

  return () => {
    trigger.kill();
    lenis.destroy();
  };
}
