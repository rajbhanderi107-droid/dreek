// Anatomical luminance field for the neck, shoulders and upper chest.
// Coordinates are in head-widths: x = 0 is the midline, y = 0 is the jawline,
// y grows downward. Returns 0..1 the way the face map does, so the same density
// sampling draws it.
//
// Built as a lit surface rather than a pile of blobs: a silhouette with a top
// edge, shaded by how far below that edge you are. A torso reads by its outline
// and the light along its top, which is what blobs cannot give you.

const NECK_HALF = 0.255;   // half-width of the neck at the jaw
const SHOULDER_X = 1.30;   // where the trapezius meets the deltoid
const OUTER_X = 1.46;      // outer edge of the upper arm

function smoothstep(a, b, x) {
  const t = Math.max(0, Math.min(1, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
}

// Top edge of the body at a given distance from the midline. The neck-to-
// shoulder corner is real anatomy, but stepping it puts a bright seam straight
// down the render, so it is rounded over a short band.
function topAt(ax) {
  let trap;
  if (ax <= SHOULDER_X) {
    const t = Math.max(0, (ax - NECK_HALF) / (SHOULDER_X - NECK_HALF));
    trap = 0.28 + 0.46 * Math.pow(t, 0.62);
  } else {
    const t = (ax - SHOULDER_X) / (OUTER_X - SHOULDER_X);
    trap = 0.74 + 0.30 * Math.pow(t, 0.55);
  }
  return trap * smoothstep(NECK_HALF - 0.07, NECK_HALF + 0.09, ax);
}

// Outer silhouette at a given depth.
function outerAt(y) {
  if (y < 0.30) return NECK_HALF + 0.10 * Math.pow(y / 0.30, 2);
  const t = Math.min(1, (y - 0.30) / 0.62);
  return NECK_HALF + 0.10 + (OUTER_X - NECK_HALF - 0.10) * Math.pow(t, 0.55);
}

export function bodyLum(x, y) {
  const ax = Math.abs(x);
  if (y < -0.02 || y > 1.60) return 0;

  const top = topAt(ax);
  const outer = outerAt(y);
  if (y < top - 0.03 || ax > outer + 0.03) return 0;

  // Soft silhouette edges so it dissolves into dust instead of ending flat.
  const inTop = Math.min(1, (y - top + 0.03) / 0.07);
  const inSide = Math.min(1, (outer + 0.03 - ax) / 0.09);
  const inside = Math.max(0, Math.min(inTop, inSide));
  if (inside <= 0) return 0;

  // Light from above and slightly in front: brightest just under the top edge,
  // falling away as the surface turns down and to the sides.
  const below = y - top;
  let lum = 0.92 * Math.exp(-below / 0.42) + 0.20;
  lum *= 1 - 0.40 * Math.pow(ax / OUTER_X, 1.8);

  // The neck sits in the shadow of the jaw, or the head looks pasted on.
  if (y < 0.34) lum *= 0.42 + 0.58 * Math.pow(Math.max(0, Math.min(1, y / 0.34)), 0.9);

  // Sternocleidomastoid: the two tendons running down the front of the neck.
  {
    const s = 0.185 - 0.11 * Math.max(0, Math.min(1, (y - 0.08) / 0.62));
    const along = smoothstep(0.08, 0.24, y) * (1 - smoothstep(0.58, 0.78, y));
    lum += 0.22 * Math.exp(-Math.pow((ax - s) / 0.05, 2)) * along;
  }

  // Clavicles: bright ridges sweeping out from the throat.
  const clavY = 0.80 + 0.13 * Math.pow(ax / 1.05, 1.6);
  const clavSpan = smoothstep(0.07, 0.20, ax) * (1 - smoothstep(0.88, 1.16, ax));
  lum += 0.30 * Math.exp(-Math.pow((y - clavY) / 0.05, 2)) * clavSpan;

  // Suprasternal notch: the hollow between them.
  lum -= 0.60 * Math.exp(-(Math.pow(x / 0.085, 2) + Math.pow((y - 0.76) / 0.075, 2)));

  // Pectoral shadow under the collarbones gives the chest some depth.
  lum -= 0.18 * Math.exp(-Math.pow((y - 1.02) / 0.16, 2)) *
         Math.exp(-Math.pow(x / 0.85, 2));

  // Fade out at the bottom: the chest leaves the frame, it does not stop.
  lum *= 1 - smoothstep(1.02, 1.58, y);

  return Math.max(0, Math.min(1, lum * inside));
}
