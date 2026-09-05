/* DREEK - reactive particle portrait.
   The head is a halftone of a real face: a luminance map sampled on a grid,
   one particle per cell, dot size and brightness following the tone. */
import { faceAt, FACE_W, FACE_H } from './face-data.js';
import { bodyLum } from './body.js';

const C = document.getElementById('stage');
const ctx = C.getContext('2d', { alpha: false });

const PAL = {
  bg:     [8, 6, 9],
  cyan:   [86, 214, 255],
  deep:   [24, 118, 214],
  orange: [255, 139, 31],
  hot:    [255, 206, 150],
  white:  [255, 238, 214],
  dust:   [182, 158, 132],
};

const MOODS = {
  neutral:   { warm:  0.00, gain: 1.00, breath: 1.00, drift: 1.00, ring: 1.00 },
  listening: { warm: -0.10, gain: 1.14, breath: 1.30, drift: 1.35, ring: 1.55 },
  thinking:  { warm: -0.22, gain: 0.86, breath: 1.55, drift: 1.70, ring: 0.60 },
  curious:   { warm: -0.06, gain: 1.10, breath: 1.35, drift: 1.30, ring: 1.30 },
  focused:   { warm:  0.06, gain: 1.06, breath: 0.80, drift: 0.70, ring: 0.80 },
  pleased:   { warm:  0.26, gain: 1.28, breath: 1.10, drift: 1.10, ring: 1.25 },
  concerned: { warm: -0.30, gain: 0.80, breath: 0.70, drift: 0.80, ring: 0.70 },
  sorry:     { warm: -0.34, gain: 0.72, breath: 0.62, drift: 0.70, ring: 0.55 },
  alert:     { warm:  0.46, gain: 1.34, breath: 2.10, drift: 1.60, ring: 2.20 },
};

const state = {
  t: 0, boot: 0, bootDone: false,
  px: 0, py: 0, pxT: 0, pyT: 0,
  level: 0.10, levelSmooth: 0.10,
  spectrum: new Float32Array(48),
  mood: 'neutral', moodMix: Object.assign({}, MOODS.neutral), moodUntil: 0,
};

/* ---------- sprite cache: additive dots without shadowBlur ---------- */
const sprites = new Map();
function sprite(rgb, radius, haloScale) {
  const safe = Number.isFinite(radius) ? Math.min(24, Math.max(0.4, radius)) : 0.8;
  const r = Math.round(safe * 2) / 2;
  const hs = haloScale || 2.6;
  const key = rgb[0] + ',' + rgb[1] + ',' + rgb[2] + '|' + r + '|' + hs;
  let s = sprites.get(key);
  if (s) return s;
  // Halo plus a solid core. A pure radial gradient at 1-2px radius throws away
  // almost all of its energy, which reads as haze instead of a point of light.
  const halo = r * hs;
  const d = Math.ceil(halo * 2) + 2;
  const cv = document.createElement('canvas');
  cv.width = cv.height = d;
  const c2 = cv.getContext('2d');
  const rgbs = rgb[0] + ',' + rgb[1] + ',' + rgb[2];
  const g = c2.createRadialGradient(d / 2, d / 2, 0, d / 2, d / 2, halo);
  g.addColorStop(0, 'rgba(' + rgbs + ',0.65)');
  g.addColorStop(0.4, 'rgba(' + rgbs + ',0.16)');
  g.addColorStop(1, 'rgba(' + rgbs + ',0)');
  c2.fillStyle = g;
  c2.fillRect(0, 0, d, d);
  c2.fillStyle = 'rgb(' + rgbs + ')';
  c2.beginPath();
  c2.arc(d / 2, d / 2, r, 0, Math.PI * 2);
  c2.fill();
  sprites.set(key, cv);
  return cv;
}

/* ---------- geometry ---------- */
let W = 0, H = 0, DPR = 1, F = {};

function layout() {
  DPR = Math.min(window.devicePixelRatio || 1, 2);
  W = C.clientWidth; H = C.clientHeight;
  C.width = Math.round(W * DPR); C.height = Math.round(H * DPR);
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);

  // The face is the subject, so it sets the scale: everything else is derived
  // from it. Sized off both axes so it never crops on a wide or a tall window.
  const faceH = Math.min(H * 0.60, W * 0.46 * (FACE_H / FACE_W));
  const faceW = faceH * (FACE_W / FACE_H);
  const rx = faceW / 2.10;

  F = {
    cx: W / 2,
    cy: H * 0.40,
    rx: rx,
    ry: rx * 1.24,
    faceW: faceW,
    faceH: faceH,
    faceT: H * 0.40 - faceH * 0.56,
    hw: faceW * 0.57,                 // the head itself, without the map margin
    jawY: (H * 0.40 - faceH * 0.56) + faceH * 0.82,
    neckW: rx * 0.40,
    neckLen: rx * 0.62,
    shoulder: rx * 3.1,
    horizon: H * 0.84,
  };
}

/* ---------- particles ---------- */
const P = [];
const G = { SKIN: 0, BODY: 1, EYE: 2, MOTE: 7 };

function rnd(a, b) { return a + Math.random() * (b - a); }

function push(g, tx, ty, opt) {
  opt = opt || {};
  P.push({
    g: g, tx: tx, ty: ty,
    x: 0, y: 0, vx: 0, vy: 0, bx: 0, by: 0, delay: 0,
    s: opt.s !== undefined ? opt.s : rnd(0.7, 1.7),
    a: opt.a !== undefined ? opt.a : rnd(0.45, 1),
    ph: Math.random() * Math.PI * 2,
    layer: opt.layer !== undefined ? opt.layer : Math.random(),
    band: opt.band || 0,
    u: opt.u || 0,
    bin: opt.bin || 0,
  });
}

function buildFigure() {
  P.length = 0;
  const cx = F.cx, cy = F.cy, rx = F.rx, ry = F.ry;

  // The head is a cloud, not a print. Particles are scattered by rejection
  // sampling against the face map, so it is their DENSITY that carries the
  // tone - many where the face is lit, almost none in shadow. Every one is the
  // same kind of speck, free to drift; a grid of differently sized dots reads
  // as halftone, which is exactly what this is not.
  const faceW = F.faceW, faceH = F.faceH;
  const faceL = cx - faceW / 2;
  const faceT = cy - faceH * 0.56;

  // Scaled to the face so the cloud keeps its density on a small window without
  // over-drawing, and stays affordable on a large one.
  const WANT = Math.max(9000, Math.min(26000, Math.round(faceW * faceH * 0.42)));
  let placed = 0, tries = 0;
  while (placed < WANT && tries < WANT * 40) {
    tries++;
    const u = Math.random();
    const v = Math.random();
    const lum = faceAt(u, v);
    if (lum < 0.05) continue;
    // Accept with probability rising with tone. The exponent below 1 keeps the
    // mid tones populated, otherwise only the highlights survive.
    if (Math.random() > Math.pow(lum, 1.15)) continue;
    placed++;
    push(G.SKIN, faceL + u * faceW, faceT + v * faceH, {
      s: rnd(0.34, 0.86),
      a: 0.16 + lum * 0.26,
      layer: 0.45 + lum * 0.4,
      u: u,
      // Each speck keeps its own small orbit so the cloud is never still.
      bin: Math.floor(rnd(0.6, 3.4) * 100),
    });
  }

  // Eyes. Empty sockets are the single thing that makes a face read as a ghost
  // rather than a person, so each gets an iris and a catchlight. Measured from
  // the map, not guessed: the tone profile dips at u = 0.34 and 0.66, v = 0.45.
  for (const eu of [0.335, 0.665]) {
    const ex = faceL + eu * faceW;
    const ey = faceT + 0.452 * faceH;
    const er = faceW * 0.043;

    for (let i = 0; i < 240; i++) {                 // the eye itself, softly filled
      const a = Math.random() * Math.PI * 2;
      const rr = er * Math.pow(Math.random(), 0.62);
      push(G.EYE, ex + Math.cos(a) * rr, ey + Math.sin(a) * rr * 0.80,
        { s: rnd(0.32, 0.72), a: rnd(0.22, 0.46), layer: 0.8, u: 0.25 });
    }
    for (let i = 0; i < 34; i++) {                  // catchlight, up and inward
      const a = Math.random() * Math.PI * 2;
      const rr = er * 0.22 * Math.sqrt(Math.random());
      push(G.EYE, ex + Math.cos(a) * rr - er * 0.24, ey + Math.sin(a) * rr - er * 0.28,
        { s: rnd(0.34, 0.62), a: rnd(0.34, 0.58), layer: 0.95, u: 0.85 });
    }
  }

  // The body: neck, trapezius, clavicles and upper chest, sampled from the same
  // kind of luminance field as the face so the two read as one person rather
  // than a portrait sitting on top of some geometry.
  //
  // bodyLum works in head-widths from the jawline, so both are anchored to the
  // actual head inside the face map - not to the map's padded box.
  const hw = F.hw, jawY = F.jawY;

  const BODY_WANT = Math.max(6000, Math.min(16000, Math.round(hw * hw * 0.95)));
  let bPlaced = 0, bTries = 0;
  while (bPlaced < BODY_WANT && bTries < BODY_WANT * 40) {
    bTries++;
    const bx = rnd(-1.55, 1.55);
    const by = rnd(-0.02, 1.58);
    const lum = bodyLum(bx, by);
    if (lum < 0.05) continue;
    if (Math.random() > Math.pow(lum, 1.15)) continue;
    bPlaced++;
    push(G.BODY, cx + bx * hw, jawY + by * hw, {
      s: rnd(0.34, 0.86),
      a: 0.12 + lum * 0.28,
      layer: 0.4 + lum * 0.35,
      u: bx,
      bin: Math.floor(rnd(0.5, 2.8) * 100),
    });
  }

  const sides = [-1, 1];

  // Parallax dust.
  for (let i = 0; i < 420; i++) {
    push(G.MOTE, rnd(0, W), rnd(0, H), { s: rnd(0.4, 1.8), a: rnd(0.08, 0.5) });
  }

}

// Only ever called once. A rebuild must never move live particles back to the
// swirl - if anything re-triggers layout, the figure would keep dissolving.
function placeOnTargets() {
  for (let i = 0; i < P.length; i++) {
    const p = P[i];
    p.x = p.tx; p.y = p.ty; p.vx = 0; p.vy = 0; p.bx = p.tx; p.by = p.ty; p.delay = 0;
  }
}

function seedBootPositions() {
  const sx = F.cx - W * 0.30, sy = F.cy + H * 0.10;
  for (let i = 0; i < P.length; i++) {
    const p = P[i];
    const a = Math.random() * Math.PI * 2;
    const r = Math.pow(Math.random(), 0.4) * W * 0.10;
    p.x = sx + Math.cos(a) * r * 2.4;
    p.y = sy + Math.sin(a) * r;
    p.bx = p.x; p.by = p.y;
    p.delay = Math.random() * 0.42;
  }
}

/* ---------- reactive targets ---------- */
// Skin dots sit on their grid cell and are pushed around by sound: a subtle
// swell outward from the centre of the face, strongest where the tone is
// brightest, so the portrait breathes and reacts without losing the likeness.
function skinTarget(p, t, out) {
  const lvl = state.levelSmooth;
  const sp = p.bin / 100;                       // this speck's own orbit speed
  const r = 1.1 + lvl * 5.5;                    // and how wide it wanders

  const dx = p.tx - F.cx;
  const dy = p.ty - (F.cy + F.ry * 0.05);
  const d = Math.hypot(dx, dy) || 1;
  const swell = lvl * 6.0 * Math.sin(d * 0.045 - t * 2.4);

  out[0] = p.tx + Math.cos(t * sp + p.ph) * r + (dx / d) * swell;
  out[1] = p.ty + Math.sin(t * sp * 0.86 + p.ph * 1.3) * r + (dy / d) * swell;
}

/* ---------- colour ---------- */
function mix(a, b, k) {
  k = k < 0 ? 0 : k > 1 ? 1 : k;
  return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
}
function groupColor(g, u) {
  const warm = state.moodMix.warm;
  switch (g) {
    case G.SKIN:     return mix(PAL.white, PAL.hot, Math.max(0, warm) * 0.75);
    case G.BODY:     return mix(PAL.dust, PAL.white, 0.55 + warm * 0.3);
    case G.EYE:      return mix(PAL.hot, PAL.white, u);
    default:         return mix(PAL.dust, PAL.white, 0.35 + warm * 0.25);
  }
}


/* One particle's motion for a single tick. Separated from drawing so the
   simulation can be advanced without waiting on requestAnimationFrame. */
function stepParticle(p, t, breath, M) {
  let tx = p.tx, ty = p.ty;

  if (p.g === G.SKIN || p.g === G.BODY || p.g === G.EYE) { skinTarget(p, t, tgt); tx = tgt[0]; ty = tgt[1]; }
  else if (p.g === G.MOTE) {
    tx = p.tx + Math.sin(t * (0.2 + p.layer * 0.5) + p.ph) * 40 * p.layer;
    ty = p.ty + Math.cos(t * (0.17 + p.layer * 0.4) + p.ph) * 26 * p.layer;
  }

  // Nearer layers swing further, so the bust turns rather than slides.
  tx += state.px * (6 + p.layer * 22);
  ty += state.py * (4 + p.layer * 14);

  if (p.g !== G.MOTE) {
    ty += (breath - 0.5) * F.ry * 0.045;
    const d = M.drift * (0.9 + state.levelSmooth * 2.4);
    tx += Math.sin(t * 0.9 + p.ph) * 1.6 * d;
    ty += Math.cos(t * 1.1 + p.ph) * 1.6 * d;
  }

  if (!state.bootDone) {
    const e = Math.max(0, Math.min(1, (state.boot - p.delay) / (1 - p.delay)));
    const k = 1 - Math.pow(1 - e, 3);
    const swirl = (1 - k) * 1.9;
    const ang = Math.atan2(ty - p.by, tx - p.bx) + swirl;
    const dist = Math.hypot(tx - p.bx, ty - p.by) * (1 - k);
    p.x = tx - Math.cos(ang) * dist;
    p.y = ty - Math.sin(ang) * dist;
  } else if (p.g === G.SKIN || p.g === G.BODY || p.g === G.EYE) {
    // Direct easing, no momentum. The damped spring below is only stable while
    // 2.57*k < 1, and the skin needs to track faster than that allows - with
    // momentum the specks overshoot and smear the face.
    p.x += (tx - p.x) * 0.34;
    p.y += (ty - p.y) * 0.34;
  } else {
    const k = 0.12 + 0.16 * p.layer;
    p.vx = (p.vx + (tx - p.x) * k) * 0.72;
    p.vy = (p.vy + (ty - p.y) * k) * 0.72;
    p.x += p.vx; p.y += p.vy;
  }
}

/* ---------- main loop ---------- */
let last = performance.now();
const tgt = [0, 0];


function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  state.t += dt;
  const t = state.t;

  if (state.moodUntil && now > state.moodUntil) setMood('neutral');
  const M = state.moodMix;

  state.levelSmooth += (state.level - state.levelSmooth) * Math.min(1, dt * 9);
  state.px += (state.pxT - state.px) * Math.min(1, dt * 2.2);
  state.py += (state.pyT - state.py) * Math.min(1, dt * 2.2);

  if (!state.bootDone) {
    state.boot += dt / 2.6;
    if (state.boot >= 1 || state.t > 4) { state.boot = 1; state.bootDone = true; }
  }

  // Two breathing periods that do not divide evenly, so the cycle never visibly loops.
  const breath = 0.5 + 0.5 * (0.62 * Math.sin(t * 0.55 * M.breath) + 0.38 * Math.sin(t * 0.31 * M.breath + 1.1));

  ctx.fillStyle = 'rgb(' + PAL.bg[0] + ',' + PAL.bg[1] + ',' + PAL.bg[2] + ')';
  ctx.fillRect(0, 0, W, H);
  ctx.globalCompositeOperation = 'lighter';

  // Ambient warmth behind the head. Without it she is lit from nowhere and
  // floating in black, which is most of why the portrait felt like a haunting.
  {
    const g = ctx.createRadialGradient(F.cx, F.cy, 0, F.cx, F.cy, F.faceH * 0.95);
    const k = 0.085 + 0.05 * state.levelSmooth;
    g.addColorStop(0, 'rgba(120, 92, 66, ' + k.toFixed(3) + ')');
    g.addColorStop(0.55, 'rgba(70, 58, 52, ' + (k * 0.45).toFixed(3) + ')');
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
  }


  const bootE = state.bootDone ? 1 : 1 - Math.pow(1 - Math.min(1, state.boot * 1.5), 3);

  const onlyG = window.DREEK_ONLY;
  for (let i = 0; i < P.length; i++) {
    const p = P[i];
    if (onlyG !== undefined && p.g !== onlyG) continue;
    stepParticle(p, t, breath, M);
    const col = groupColor(p.g, p.u);
    let bright = p.a * M.gain * (0.55 + 0.45 * breath) * bootE;
    if (p.g === G.SKIN) bright *= 1.02 + 0.30 * state.levelSmooth;
    if (p.g === G.BODY) bright *= 0.88 + 0.26 * state.levelSmooth;
    const size = p.g === G.SKIN
      ? p.s * (1 + state.levelSmooth * 0.30)
      : p.s * (1 + state.levelSmooth * 0.25) * (0.6 + p.layer * 0.8);
    const skin = p.g === G.SKIN || p.g === G.BODY || p.g === G.EYE;
    const img = sprite([col[0] | 0, col[1] | 0, col[2] | 0], Math.max(0.4, size * 0.78), skin ? 1.9 : 2.6);
    ctx.globalAlpha = bright < 0 ? 0 : bright > 1 ? 1 : bright;
    ctx.drawImage(img, p.x - img.width / 2, p.y - img.height / 2);
  }

  // Brightness flash as the field settles out of the boot swirl.
  if (!state.bootDone && state.boot > 0.72) {
    ctx.globalAlpha = Math.max(0, Math.min(0.5, (state.boot - 0.72) / 0.28 * (1 - state.boot) * 2.6));
    ctx.fillStyle = '#8fd8ff';
    ctx.fillRect(0, 0, W, H);
  }

  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = 'source-over';
  if (window.DREEK_DEBUG) {
    ctx.strokeStyle = 'rgba(255,60,60,0.9)'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(F.cx - 24, F.cy); ctx.lineTo(F.cx + 24, F.cy);
    ctx.moveTo(F.cx, F.cy - 24); ctx.lineTo(F.cx, F.cy + 24); ctx.stroke();
    ctx.strokeStyle = 'rgba(0,255,120,0.7)';
    ctx.beginPath(); ctx.ellipse(F.cx, F.cy, F.rx, F.ry, 0, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.font = '12px monospace';
    ctx.fillText(W + 'x' + H + '  particles=' + P.length + '  t=' + state.t.toFixed(1), 14, H - 14);
  }
  requestAnimationFrame(frame);
}

/* ---------- control surface ---------- */
export function setMood(name, holdMs) {
  holdMs = holdMs || 22000;
  const known = Object.prototype.hasOwnProperty.call(MOODS, name);
  const m = known ? MOODS[name] : MOODS.neutral;
  state.mood = known ? name : 'neutral';
  state.moodMix = Object.assign({}, m);
  state.moodUntil = state.mood === 'neutral' ? 0 : performance.now() + holdMs;
  document.dispatchEvent(new CustomEvent('dreek:mood', { detail: state.mood }));
}
export function setLevel(v) { state.level = v < 0 ? 0 : v > 1 ? 1 : v; }
export function setSpectrum(arr) {
  for (let i = 0; i < state.spectrum.length; i++) state.spectrum[i] = arr[i] || 0;
}
export function getState() { return state; }

// Setting canvas.width inside layout() can itself trigger another resize event.
// Without this guard the figure is rebuilt every frame and the particles are
// perpetually reset to the boot swirl, so they never reach their targets.
let resizeTimer = 0;
window.addEventListener('resize', function () {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(function () {
    if (C.clientWidth === W && C.clientHeight === H) return;
    layout();
    buildFigure();
    placeOnTargets();
    state.boot = 1; state.bootDone = true;
  }, 150);
});

function breathAt(t, M) {
  return 0.5 + 0.5 * (0.62 * Math.sin(t * 0.55 * M.breath) + 0.38 * Math.sin(t * 0.31 * M.breath + 1.1));
}

// Advance the simulation by n fixed ticks without drawing. Used to settle the
// field on load, and to inspect the resting state where rAF is unavailable.
export function settle(n, dtFixed) {
  const dt = dtFixed || 1 / 60;
  for (let k = 0; k < n; k++) {
    state.t += dt;
    if (!state.bootDone) {
      state.boot += dt / 2.6;
      if (state.boot >= 1) { state.boot = 1; state.bootDone = true; }
    }
    state.levelSmooth += (state.level - state.levelSmooth) * Math.min(1, dt * 9);
  state.px += (state.pxT - state.px) * Math.min(1, dt * 2.2);
  state.py += (state.pyT - state.py) * Math.min(1, dt * 2.2);
    const br = breathAt(state.t, state.moodMix);
    for (let i = 0; i < P.length; i++) stepParticle(P[i], state.t, br, state.moodMix);
  }
}

window.addEventListener('pointermove', function (e) {
  state.pxT = (e.clientX / Math.max(1, W)) * 2 - 1;
  state.pyT = (e.clientY / Math.max(1, H)) * 2 - 1;
});
window.addEventListener('pointerleave', function () { state.pxT = 0; state.pyT = 0; });

layout();
buildFigure();
seedBootPositions();
const q = new URLSearchParams(location.search);
if (q.has('settle')) settle(parseInt(q.get('settle'), 10) || 240);
requestAnimationFrame(frame);
