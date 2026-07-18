import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { scrollState } from "./scroll.js";

// Act I camera: starts slightly off-axis in front of the eye, dollies
// straight into the pupil as scroll advances. The full journey will ride
// one spline (eye → pupil → nerve → brain); for Act I the segment is a
// simple eased dolly, which is exactly the spline's first leg.
export default function CameraRig() {
  useFrame(({ camera }) => {
    const p = scrollState.progress;

    // Push-in: 0 → 0.30 of scroll covers approach and entry into the pupil.
    const push = THREE.MathUtils.smoothstep(p, 0.0, 0.30);
    const z = THREE.MathUtils.lerp(5.2, 0.92, push);

    // Start slightly off to the side; centre as the push begins so the
    // shot reads as "the eye turns to meet you."
    const offX = THREE.MathUtils.lerp(0.9, 0.0, THREE.MathUtils.smoothstep(p, 0.0, 0.15));
    const offY = THREE.MathUtils.lerp(0.25, 0.0, THREE.MathUtils.smoothstep(p, 0.0, 0.15));

    camera.position.set(offX, offY, z);
    camera.lookAt(0, 0, 0.86);

    // Narrowing FOV tightens the frame as we near the pupil.
    camera.fov = THREE.MathUtils.lerp(42, 30, push);
    camera.updateProjectionMatrix();
  });

  return null;
}
