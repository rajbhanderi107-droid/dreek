/* DREEK v3 - reactive particle humanoid.
   Everything on screen is generated: no photograph, no sprite sheet. */

const C = document.getElementById('stage');
const ctx = C.getContext('2d', { alpha: false });

const PAL = {
  bg:     [2, 5, 12],
  cyan:   [86, 214, 255],
  deep:   [24, 118, 214],
  orange: [255, 139, 31],
  hot:    [255, 226, 170],
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
  const r = Math.round(radius * 2) / 2;
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

  const rx = Math.min(W * 0.088, H * 0.185);
  F = {
    cx: W / 2,
    cy: H * 0.30,
    rx: rx,
    ry: rx * 1.24,
    neckW: rx * 0.40,
    neckLen: rx * 0.62,
    shoulder: rx * 3.1,
    horizon: H * 0.78,
  };
}

/* ---------- particles ---------- */
const P = [];
const G = { RIM: 0, SKULL: 1, NECK: 2, SHOULDER: 3, FILAMENT: 4, FACE: 5, RIDGE: 6, MOTE: 7, WING: 8 };
const BANDS = 6;

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
  const neckW = F.neckW, neckLen = F.neckLen, shoulder = F.shoulder, horizon = F.horizon;

  // Head rim: one tight bright contour. The glow is a separate, much fainter
  // shell - mixing the two into one scattered band is what reads as fog.
  for (let i = 0; i < 1300; i++) {
    const a = (i / 1300) * Math.PI * 2;
    const squash = 1 - 0.13 * Math.max(0, Math.cos(a));       // slight jaw taper
    const sh = rnd(0.997, 1.003);
    push(G.RIM, cx + Math.cos(a) * rx * sh, cy + Math.sin(a) * ry * sh * squash,
      { s: rnd(1.0, 1.9), a: rnd(0.88, 1), layer: 0.9 });
  }
  for (let i = 0; i < 260; i++) {
    const a = Math.random() * Math.PI * 2;
    const sh = rnd(1.02, 1.14);
    const squash = 1 - 0.13 * Math.max(0, Math.cos(a));
    push(G.RIM, cx + Math.cos(a) * rx * sh, cy + Math.sin(a) * ry * sh * squash,
      { s: rnd(0.6, 1.2), a: rnd(0.05, 0.16), layer: 0.9 });
  }

  // Skull striations: faint horizontal contour lines banding the head interior.
  const LINES = 22;
  for (let l = 0; l < LINES; l++) {
    const v = -0.92 + (l / (LINES - 1)) * 1.84;
    const halfW = Math.sqrt(Math.max(0, 1 - v * v)) * rx * 0.93;
    const n = Math.max(5, Math.round(halfW * 0.34));
    for (let i = 0; i < n; i++) {
      push(G.SKULL, cx + rnd(-halfW, halfW), cy + v * ry + rnd(-0.8, 0.8),
        { s: rnd(0.4, 0.8), a: rnd(0.05, 0.15), layer: 0.55 });
    }
  }

  const jaw = cy + ry * 0.90;
  const collar = jaw + neckLen;

  // Neck: two side curves flaring into the collar.
  const sides = [-1, 1];
  for (let si = 0; si < 2; si++) {
    const side = sides[si];
    for (let i = 0; i < 420; i++) {
      const u = i / 419;
      const w = neckW * (1 + Math.pow(u, 2.2) * 1.9);
      push(G.NECK, cx + side * w + rnd(-1.5, 1.5) - side * Math.pow(Math.random(), 2.4) * neckW * 0.9, jaw + u * neckLen,
        { s: rnd(0.7, 1.6), a: rnd(0.45, 1), layer: 0.85, u: u });
    }
  }

  // Shoulders: a broad collar arc that slopes down and out, not a thin stick.
  for (let si = 0; si < 2; si++) {
    const side = sides[si];
    for (let i = 0; i < 1500; i++) {
      const u = Math.pow(i / 1499, 0.85);
      const x = cx + side * (neckW * 1.7 + u * shoulder);
      const drop = Math.pow(u, 0.62) * ry * 0.55;
      // Fill downward from the shoulder line so it reads as mass, not an outline.
      const fill = Math.pow(Math.random(), 1.6) * ry * 0.85;
      push(G.SHOULDER, x + rnd(-4, 4), collar + drop + fill,
        { s: rnd(0.6, 1.7), a: fill < ry * 0.06 ? rnd(0.9, 1) : rnd(0.10, 0.30), layer: 0.8, u: u });
    }
  }

  // Chest filaments: branching neural veins running down from the throat.
  const xLimit = shoulder * 1.05;
  const seeds = [];
  for (let b = 0; b < 5; b++) {
    seeds.push({ x: cx + rnd(-neckW, neckW), y: jaw + neckLen * 0.2, ang: Math.PI / 2 + rnd(-0.45, 0.45) });
  }
  for (let si = 0; si < seeds.length && si < 16; si++) {
    let x = seeds[si].x, y = seeds[si].y, ang = seeds[si].ang;
    const steps = 80;
    for (let i = 0; i < steps; i++) {
      ang += rnd(-0.15, 0.15);
      ang += (Math.PI / 2 - ang) * 0.06;                       // keep the flow downward
      x += Math.cos(ang) * rnd(2, 5);
      y += Math.sin(ang) * rnd(2, 5);
      if (y > horizon || Math.abs(x - cx) > xLimit) break;
      push(G.FILAMENT, x, y, { s: rnd(0.5, 1.4), a: rnd(0.3, 0.95), layer: 0.75, u: i / steps });
      if (Math.random() < 0.04 && seeds.length < 16) {
        seeds.push({ x: x, y: y, ang: ang + (Math.random() < 0.5 ? -0.6 : 0.6) });
      }
    }
  }

  // Face waveform: separated horizontal ripple lines, the way the face actually reads.
  for (let b = 0; b < BANDS; b++) {
    for (let i = 0; i < 220; i++) {
      push(G.FACE, cx, cy, { s: rnd(1.0, 1.7), a: rnd(0.82, 1), layer: 0.95, band: b, u: i / 220 });
    }
  }

  // Spectrum terrain: three ridge layers each side, driven by audio bins.
  for (let si = 0; si < 2; si++) {
    const side = sides[si];
    for (let layer = 0; layer < 3; layer++) {
      const n = 460;
      for (let i = 0; i < n; i++) {
        const u = i / (n - 1);
        push(G.RIDGE, 0, 0, {
          s: rnd(0.6, 1.8), a: rnd(0.35, 1),
          layer: 0.25 + layer * 0.22,
          u: u * side || 0.0001 * side,
          band: layer,
          bin: Math.floor(u * 44),
        });
      }
    }
  }

  // Wings: feathered arcs sweeping up and out from the shoulders. Each feather
  // is driven by its own spectrum bin, so the span opens when there is sound.
  const FEATHERS = 15;
  for (let si = 0; si < 2; si++) {
    const side = sides[si];
    for (let f = 0; f < FEATHERS; f++) {
      const n = 60;
      for (let i = 0; i < n; i++) {
        push(G.WING, 0, 0, {
          s: rnd(0.45, 1.3), a: rnd(0.30, 1),
          layer: 0.30 + (f / FEATHERS) * 0.55,
          // Density falls off toward the tip, so a feather tapers instead of
          // ending in a blunt edge.
          u: Math.pow(i / (n - 1), 0.72) * side || 0.0001 * side,
          band: f,
          bin: Math.floor((f / 15) * 40),
        });
      }
    }
  }

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
// The face is a set of nested contour rings, squashed wide so they read as
// stacked ripples. Audio pushes the rings outward and warps them.
function faceTarget(p, t, out) {
  const cx = F.cx, cy = F.cy, rx = F.rx, ry = F.ry;
  const lvl = state.levelSmooth;
  // Rings start well off centre; if the innermost one is tiny it collapses into
  // a blob and the whole set stops reading as contours.
  const k = (p.band + 1.5) / (BANDS + 0.6);
  const th = p.u * Math.PI * 2;

  const grow = 1 + lvl * 0.22;
  const wob = 1
    + 0.055 * Math.sin(th * 3 + t * 1.6 + p.band * 0.8)
    + 0.035 * Math.sin(th * 6 - t * 2.3 + p.band)
    + lvl * 0.16 * Math.sin(th * 2 + t * 5.0 + p.band * 1.4);

  out[0] = cx + Math.cos(th) * rx * 0.78 * k * grow * wob;
  out[1] = cy + ry * 0.18 + Math.sin(th) * ry * 0.62 * k * grow * wob;
}

// Terrain must have relief even in silence, otherwise the mountains vanish
// whenever nobody is talking. Audio lifts this floor, it does not replace it.
function binAt(i, t) {
  const idle = 0.34
    + 0.22 * Math.sin(i * 0.55 + t * 0.21)
    + 0.16 * Math.sin(i * 1.31 - t * 0.13)
    + 0.10 * Math.sin(i * 2.70 + t * 0.37);
  const live = state.spectrum[i < 47 ? i : 47] || 0;
  return Math.max(idle, live * 1.15);
}

// A feather runs from the shoulder outward along an arc that lifts as it goes.
// Its reach and spread answer to the audio, so the wings beat when DREEK speaks.
const FEATHERS = 15;

function wingTarget(p, t, out) {
  const side = p.u < 0 ? -1 : 1;
  const u = Math.abs(p.u);
  const f = p.band / (FEATHERS - 1);
  const lvl = state.levelSmooth;
  const bin = binAt(p.bin, t);

  const root = F.cx + side * (F.neckW * 1.8);
  const rootY = F.cy + F.ry * 0.9 + F.neckLen;

  // The angle must not carry the side, or one wing lifts while the other drops.
  // Only x mirrors; both wings rise by the same amount.
  const beat = Math.sin(t * 1.5 + f * 2.4) * (0.05 + lvl * 0.16);
  const a = -0.22 + f * 1.20 + beat;                 // below horizontal up to steeply raised
  const stagger = 0.82 + 0.18 * Math.sin(f * 9.7);  // ragged trailing edge
  const reach = F.rx * (1.6 + f * 1.7) * stagger * (0.74 + 0.28 * bin + lvl * 0.28);

  const curve = Math.pow(u, 1.2);
  out[0] = root + side * curve * reach;
  out[1] = rootY - Math.sin(a) * curve * reach * 0.70;
}

function ridgeTarget(p, t, out) {
  const side = p.u < 0 ? -1 : 1;
  const u = Math.abs(p.u);
  const spanIn = F.cx + side * F.rx * 1.35;
  const spanOut = F.cx + side * (W * 0.55);
  const bin = binAt(p.bin, t);
  const base = H * (0.23 + 0.10 * p.band);
  const ridge = Math.abs(Math.sin(u * (5 + p.band * 3) + p.band * 2.1 + t * 0.16))
    * (0.45 + 0.55 * Math.abs(Math.sin(u * (13 + p.band * 5) - t * 0.09)));
  const relief = base * (0.30 + 0.90 * bin) * ridge;
  const skirt = Math.pow(Math.random(), 1.9) * relief;   // fills the slope below the crest
  out[0] = spanIn + (spanOut - spanIn) * u;
  out[1] = F.horizon + p.band * H * 0.030 - relief + skirt;
}

/* ---------- colour ---------- */
function mix(a, b, k) {
  k = k < 0 ? 0 : k > 1 ? 1 : k;
  return [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
}
function groupColor(g, u) {
  const warm = state.moodMix.warm;
  switch (g) {
    case G.FACE:     return mix(PAL.orange, PAL.hot, 0.25 + 0.55 * state.levelSmooth + warm * 0.4);
    case G.FILAMENT: return mix(PAL.orange, PAL.cyan, u * 0.9 - warm);
    case G.RIM:      return mix(PAL.cyan, PAL.hot, Math.max(0, warm) * 0.5);
    case G.SKULL:    return mix(PAL.deep, PAL.cyan, 0.5);
    case G.WING:     return mix(PAL.deep, PAL.cyan, 0.35 + Math.abs(u) * 0.65 + warm * 0.3);
    default:         return mix(PAL.deep, PAL.cyan, 0.65 + warm * 0.2);
  }
}

/* ---------- sonar rings and lightning veins ---------- */
const rings = [];
let ringClock = 0;

function drawRings(dt) {
  ringClock += dt * state.moodMix.ring;
  if (ringClock > 1.6) { ringClock = 0; rings.push({ r: F.rx * 1.02, a: 1.0 }); }
  ctx.lineWidth = 1.2;
  for (let i = rings.length - 1; i >= 0; i--) {
    const r = rings[i];
    r.r += dt * (60 + 180 * state.levelSmooth);
    r.a -= dt * 0.22;
    if (r.a <= 0) { rings.splice(i, 1); continue; }
    ctx.strokeStyle = 'rgba(86,214,255,' + (r.a * 0.34).toFixed(3) + ')';
    ctx.beginPath();
    ctx.ellipse(F.cx, F.cy, r.r, r.r * 0.96, 0, Math.PI * 0.08, Math.PI * 0.92);
    ctx.stroke();
    ctx.beginPath();
    ctx.ellipse(F.cx, F.cy, r.r, r.r * 0.96, 0, Math.PI * 1.08, Math.PI * 1.92);
    ctx.stroke();
  }
}

function drawVeins(t) {
  ctx.lineWidth = 1.4;
  const sides = [-1, 1];
  for (let si = 0; si < 2; si++) {
    const side = sides[si];
    for (let k = 0; k < 3; k++) {
      const flick = 0.30 + 0.45 * Math.abs(Math.sin(t * (0.7 + k * 0.4) + side * k));
      ctx.strokeStyle = 'rgba(255,150,50,' + (flick * (0.35 + 0.5 * state.levelSmooth)).toFixed(3) + ')';
      ctx.beginPath();
      for (let i = 0; i <= 80; i++) {
        const u = i / 80;
        const x = F.cx + side * (F.rx * 1.35 + u * (W * 0.55 - F.rx * 1.35));
        const bin = binAt(Math.floor(u * 44), t);
        const base = H * (0.23 + 0.10 * k);
        const ridge = Math.abs(Math.sin(u * (5 + k * 3) + k * 2.1 + t * 0.16))
          * (0.45 + 0.55 * Math.abs(Math.sin(u * (13 + k * 5) - t * 0.09)));
        const y = F.horizon + k * H * 0.030 - base * (0.30 + 0.90 * bin) * ridge * 0.42
          + Math.sin(u * 40 + t * 3 + k) * 4;
        if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
      }
      ctx.stroke();
    }
  }
}


/* One particle's motion for a single tick. Separated from drawing so the
   simulation can be advanced without waiting on requestAnimationFrame. */
function stepParticle(p, t, breath, M) {
  let tx = p.tx, ty = p.ty;

    if (p.g === G.FACE) { faceTarget(p, t, tgt); tx = tgt[0]; ty = tgt[1]; }
    else if (p.g === G.RIDGE) { ridgeTarget(p, t, tgt); tx = tgt[0]; ty = tgt[1]; }
    else if (p.g === G.WING) { wingTarget(p, t, tgt); tx = tgt[0]; ty = tgt[1]; }
    else if (p.g === G.MOTE) {
      tx = p.tx + Math.sin(t * (0.2 + p.layer * 0.5) + p.ph) * 40 * p.layer;
      ty = p.ty + Math.cos(t * (0.17 + p.layer * 0.4) + p.ph) * 26 * p.layer;
    }

    // Nearer layers swing further, so the bust turns rather than slides.
    tx += state.px * (6 + p.layer * 22);
    ty += state.py * (4 + p.layer * 14);

    if (p.g !== G.MOTE && p.g !== G.RIDGE && p.g !== G.FACE && p.g !== G.WING) {
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
    } else {
      if (p.g === G.FACE) {
        // Direct easing, no momentum. The damped spring below is only stable
        // while 2.57*k < 1, and the face needs to track its target much faster
        // than that allows - with momentum it overshoots and flings outward.
        p.x += (tx - p.x) * 0.34;
        p.y += (ty - p.y) * 0.34;
      } else {
        const k = 0.12 + 0.16 * p.layer;
        p.vx = (p.vx + (tx - p.x) * k) * 0.72;
        p.vy = (p.vy + (ty - p.y) * k) * 0.72;
        p.x += p.vx; p.y += p.vy;
      }
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

  drawRings(dt);
  drawVeins(t);

  const bootE = state.bootDone ? 1 : 1 - Math.pow(1 - Math.min(1, state.boot * 1.5), 3);

  const onlyG = window.DREEK_ONLY;
  for (let i = 0; i < P.length; i++) {
    const p = P[i];
    if (onlyG !== undefined && p.g !== onlyG) continue;
    stepParticle(p, t, breath, M);
    const col = groupColor(p.g, p.u);
    let bright = p.a * M.gain * (0.55 + 0.45 * breath) * bootE;
    if (p.g === G.FACE) bright *= 1.0 + 0.5 * state.levelSmooth;
    // Wing tips thin out rather than stopping dead.
    if (p.g === G.WING) bright *= 1.05 - 0.55 * Math.abs(p.u);
    const size = p.s * (1 + state.levelSmooth * (p.g === G.FACE ? 0.8 : 0.25)) * (0.6 + p.layer * 0.8);
    const face = p.g === G.FACE;
    // A wide halo on the face bands bleeds across the gaps and fills them in.
    const img = sprite([col[0] | 0, col[1] | 0, col[2] | 0], Math.max(0.7, size * (face ? 0.72 : 0.78)), face ? 1.5 : 2.6);
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
