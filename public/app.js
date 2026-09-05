/* DREEK v3 - voice in, brain, voice out. */
import { setMood, setLevel, setSpectrum } from './dreek.js';

const el = (id) => document.getElementById(id);
const hud = {
  status: el('status'), mic: el('micPip'), brain: el('brainPip'), wake: el('wakePip'),
  caption: el('caption'), log: el('log'), input: el('textInput'),
  micBtn: el('micBtn'), langSel: el('langSel'), voiceSel: el('voiceSel'),
  moodTag: el('moodTag'), act: el('activity'), openBtn: el('openBtn'),
};

const LANGS = { en: 'en-IN', hi: 'hi-IN', gu: 'gu-IN' };
const WAKE = ['dreek', 'drake', 'derek', 'dreak', 'drik', 'd rek'];

let lang = localStorage.getItem('dreek.lang') || 'en';
let handsFree = localStorage.getItem('dreek.handsfree') !== '0';
let busy = false;
let speaking = false;

/* ---------- hud ---------- */
function status(text, tone) {
  hud.status.textContent = text;
  hud.status.dataset.tone = tone || 'idle';
}
function pip(node, on, title) {
  if (!node) return;
  node.dataset.on = on ? '1' : '0';
  if (title) node.title = title;
}
function activity(text) {
  hud.act.textContent = text || '';
  hud.act.dataset.on = text ? '1' : '0';
}
function logLine(who, text) {
  const d = document.createElement('div');
  d.className = 'line ' + who;
  d.textContent = text;
  hud.log.appendChild(d);
  hud.log.scrollTop = hud.log.scrollHeight;
  while (hud.log.childElementCount > 60) hud.log.removeChild(hud.log.firstChild);
}

/* ---------- microphone: level + spectrum ---------- */
let audioCtx = null, analyser = null, freq = null, micStream = null;
const spec = new Float32Array(48);
let micLevel = 0;

function embeddedViewer() {
  // The Claude Code browser pane and similar embedded viewers block
  // getUserMedia at the container level - no page-side permission can fix it.
  return window.top !== window.self || !!window.__CLAUDE_PANE__ ||
         /Claude/i.test(navigator.userAgent);
}

function micFailureReason(err) {
  const n = err && err.name;
  if (n === 'NotAllowedError' || n === 'SecurityError') {
    return embeddedViewer()
      ? 'This viewer blocks the microphone at the container level, so no permission prompt can help. Press "Open in a real browser" and the mic will work.'
      : 'Microphone permission was refused. Click the padlock in the address bar, allow the microphone, then press Enable again.';
  }
  if (n === 'NotFoundError' || n === 'OverconstrainedError') {
    return 'No microphone was found. Plug one in, or pick one in Windows sound settings.';
  }
  if (n === 'NotReadableError') {
    return 'Another app is holding the microphone. Close Zoom, Teams or Discord and press Enable again.';
  }
  if (!window.isSecureContext) {
    return 'This page is not on a secure origin, so the browser blocks the microphone. Open it on http://localhost.';
  }
  return 'Microphone failed: ' + (n || 'unknown') + '. ' + ((err && err.message) || '');
}

async function openRealBrowser() {
  try {
    const r = await (await fetch('/api/open-browser', { method: 'POST' })).json();
    logLine('sys', r.ok ? 'Opening DREEK in ' + r.browser + '. Use that window - the mic works there.'
                        : 'Could not launch a browser: ' + r.error);
  } catch {
    logLine('sys', 'Could not reach the server to open a browser.');
  }
}

async function enableMic() {
  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (err) {
    pip(hud.mic, false, 'mic off');
    status('mic blocked', 'alert');
    setMood('concerned');
    logLine('sys', micFailureReason(err));
    hud.openBtn.hidden = false;
    return false;
  }

  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const src = audioCtx.createMediaStreamSource(micStream);
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 512;
  analyser.smoothingTimeConstant = 0.7;
  src.connect(analyser);
  freq = new Uint8Array(analyser.frequencyBinCount);

  pip(hud.mic, true, 'mic live');
  hud.micBtn.hidden = true;
  status(handsFree ? 'say "dreek"' : 'listening', 'idle');
  startRecognition();
  pumpAudio();
  return true;
}

function pumpAudio() {
  if (!analyser) return;
  analyser.getByteFrequencyData(freq);
  let sum = 0;
  const bins = spec.length;
  const per = Math.floor(freq.length * 0.6 / bins);   // the top of the spectrum is dead air
  for (let i = 0; i < bins; i++) {
    let v = 0;
    for (let j = 0; j < per; j++) v += freq[i * per + j];
    v = v / per / 255;
    spec[i] = spec[i] * 0.55 + v * 0.45;
    sum += v;
  }
  micLevel = sum / bins;
  if (!speaking) {
    setLevel(Math.min(1, Math.pow(micLevel * 2.6, 1.25)));
    setSpectrum(spec);
  } else if (micLevel > 0.30) {
    // Barge-in: talking over DREEK stops it, the way it would stop a person.
    bargeIn();
  }
  requestAnimationFrame(pumpAudio);
}

/* ---------- speech recognition ---------- */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recog = null, recogWanted = false, finalBuffer = '', settleTimer = null;
let armed = false, armedUntil = 0;

function stripWake(s) {
  let t = s.trim();
  for (const w of WAKE) {
    const rx = new RegExp('^\\s*(hey\\s+|ok\\s+)?' + w + '[\\s,.!?-]*', 'i');
    if (rx.test(t)) return { hit: true, rest: t.replace(rx, '').trim() };
  }
  return { hit: false, rest: t };
}

function heardWake(s) {
  const low = ' ' + s.toLowerCase() + ' ';
  return WAKE.some((w) => low.includes(' ' + w + ' ') || low.includes(' ' + w + ','));
}

function startRecognition() {
  if (!SR) {
    logLine('sys', 'This browser has no speech recognition. Use Chrome or Edge, or type below.');
    return;
  }
  recogWanted = true;
  recog = new SR();
  recog.lang = LANGS[lang];
  recog.continuous = true;
  recog.interimResults = true;

  recog.onresult = (e) => {
    let interim = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) finalBuffer += r[0].transcript + ' ';
      else interim += r[0].transcript;
    }
    const whole = (finalBuffer + interim).trim();
    if (!whole) return;

    if (handsFree && !armed) {
      if (!heardWake(whole)) {
        // Not addressed to DREEK: show nothing, keep the buffer from growing.
        if (finalBuffer.length > 400) finalBuffer = '';
        return;
      }
      armed = true;
      armedUntil = Date.now() + 15000;
      pip(hud.wake, true, 'awake');
      status('listening', 'busy');
      setMood('listening', 8000);
      const st = stripWake(whole);
      finalBuffer = st.rest ? st.rest + ' ' : '';
    }

    setCaption(handsFree ? (finalBuffer + interim).trim() : whole, false);
    if (!busy) setMood('listening', 6000);

    clearTimeout(settleTimer);
    // Answering the instant you stop talking feels mechanical; wait for a real pause.
    settleTimer = setTimeout(() => {
      let said = stripWake(finalBuffer).rest.trim();
      finalBuffer = '';
      if (said.length > 1) { ask(said); }
      else if (armed) { status('listening', 'busy'); }
    }, 900);
  };

  recog.onerror = (e) => {
    if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
      pip(hud.mic, false, 'mic denied');
      logLine('sys', 'Speech recognition was denied. Allow the microphone for this page.');
      recogWanted = false;
      status('mic blocked', 'alert');
    }
  };
  recog.onend = () => { if (recogWanted) { try { recog.start(); } catch (_) {} } };

  try { recog.start(); } catch (_) {}
}

function pauseRecognition() { recogWanted = false; if (recog) { try { recog.stop(); } catch (_) {} } }
function resumeRecognition() {
  if (!recog) return;
  recogWanted = true;
  try { recog.start(); } catch (_) {}
}

// Drop back to sleep after a quiet spell so it is not permanently open.
setInterval(() => {
  if (armed && !busy && !speaking && Date.now() > armedUntil) {
    armed = false;
    pip(hud.wake, false, 'asleep');
    if (analyser) status('say "dreek"', 'idle');
  }
}, 1000);

/* ---------- speech synthesis ---------- */
let voices = [];

function voiceScore(v, want) {
  let s = 0;
  if (v.lang.toLowerCase().startsWith(want)) s += 40;
  if (/-IN\b/i.test(v.lang)) s += 20;
  // Neural voices are a large quality jump over the bundled robotic ones.
  if (/natural|neural|online/i.test(v.name)) s += 30;
  if (v.localService) s += 2;
  return s;
}

function loadVoices() {
  voices = speechSynthesis.getVoices();
  if (!voices.length) return;
  const want = LANGS[lang].slice(0, 2).toLowerCase();
  const ranked = voices.slice().sort((a, b) => voiceScore(b, want) - voiceScore(a, want));
  hud.voiceSel.innerHTML = '';
  for (const v of ranked) {
    const o = document.createElement('option');
    o.value = v.name;
    o.textContent = v.name.replace(/^Microsoft /, '') + '  (' + v.lang + ')';
    hud.voiceSel.appendChild(o);
  }
  const saved = localStorage.getItem('dreek.voice');
  if (saved && ranked.some((v) => v.name === saved)) hud.voiceSel.value = saved;
}
speechSynthesis.onvoiceschanged = loadVoices;
loadVoices();

// The caption is built from word spans so each one can brighten exactly when
// the synthesiser reaches it, rather than the whole line appearing at once.
let capWords = [];

function setCaption(text, synced) {
  hud.caption.innerHTML = '';
  capWords = [];
  if (!text) return;
  let at = 0;
  for (const w of text.split(/(\s+)/)) {
    if (!w) continue;
    if (/^\s+$/.test(w)) { hud.caption.appendChild(document.createTextNode(w)); at += w.length; continue; }
    const span = document.createElement('span');
    span.className = synced ? 'w' : 'w said';
    span.textContent = w;
    hud.caption.appendChild(span);
    capWords.push({ span, start: at });
    at += w.length;
  }
}

function markSpokenTo(charIndex) {
  for (const w of capWords) if (w.start <= charIndex) w.span.classList.add('said');
}

let speakRaf = 0;
function stopSpeechEnvelope() {
  cancelAnimationFrame(speakRaf);
  speakRaf = 0;
  speaking = false;
  setLevel(0);
}

function bargeIn() {
  if (!speaking && !sayQueue.length) return;
  sayQueue.length = 0;
  speechSynthesis.cancel();
  stopSpeechEnvelope();
  resumeRecognition();
  status('listening', 'busy');
  logLine('sys', 'Stopped - you started talking.');
}

// Where this utterance starts inside the caption, so word highlighting
// keeps working across the sentence-by-sentence queue.
let spokenBase = 0;

function speak(text) {
  if (!text) return Promise.resolve();
  return new Promise((resolve) => {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const v = voices.find((x) => x.name === hud.voiceSel.value);
    if (v) u.voice = v;
    u.lang = (v && v.lang) || LANGS[lang];
    u.rate = 1.03;
    u.pitch = 0.96;

    // The synthesiser's own audio cannot be tapped, so the field is driven from
    // an envelope keyed to speech progress rather than a flat fake level.
    let env = 0, charAt = 0;
    const total = Math.max(1, text.length);
    const tick = () => {
      const prog = charAt / total;
      const n = performance.now();
      const wob = 0.55 + 0.45 * Math.sin(n / 90) * Math.sin(n / 37);
      env += ((0.38 + 0.5 * wob) * (1 - 0.2 * prog) - env) * 0.18;
      setLevel(env);
      for (let i = 0; i < spec.length; i++) {
        const f = i / spec.length;
        spec[i] = env * (0.95 - 0.6 * f) * (0.6 + 0.4 * Math.sin(n / (60 + i * 9)));
      }
      setSpectrum(spec);
      speakRaf = requestAnimationFrame(tick);
    };

    u.onboundary = (e) => {
      charAt = e.charIndex || charAt;
      markSpokenTo(spokenBase + charAt);
    };
    u.onstart = () => { speaking = true; pauseRecognition(); tick(); };
    const doneWords = () => markSpokenTo(spokenBase + text.length);
    const done = () => {
      doneWords();
      spokenBase += text.length + 1;
      stopSpeechEnvelope();
      resumeRecognition();
      resolve();
    };
    u.onend = done;
    u.onerror = done;
    speechSynthesis.speak(u);
  });
}

const TOOL_WORDS = {
  search_files: 'searching your files',
  list_folder: 'looking in that folder',
  read_file: 'reading it',
  write_file: 'writing that file',
  open_thing: 'opening it',
  run_command: 'running that',
  machine_status: 'checking the machine',
  remember: 'noting that down',
  recall: 'checking what I know',
  delegate: 'handing it to an agent',
  web_search: 'searching the web',
};

/* ---------- brain ---------- */
// Speech is queued sentence by sentence as the tokens arrive, so DREEK starts
// talking while the rest of the answer is still being written.
const sayQueue = [];
let draining = false;

async function drainQueue() {
  if (draining) return;
  draining = true;
  while (sayQueue.length) await speak(sayQueue.shift());
  draining = false;
}

function pushSpeech(chunk) {
  const t = chunk.trim();
  if (t) { sayQueue.push(t); drainQueue(); }
}

async function askStreaming(text) {
  const res = await fetch('/api/stream', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ prompt: text }),
  });
  if (!res.ok || !res.body) throw new Error('stream unavailable');

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '', full = '', unsaid = '', moodStripped = false;
  let outcome = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });

    const frames = buf.split('\n\n');
    buf = frames.pop();
    for (const frame of frames) {
      const ev = (frame.match(/^event: (.+)$/m) || [])[1];
      const dl = (frame.match(/^data: (.+)$/m) || [])[1];
      if (!ev || !dl) continue;
      let d; try { d = JSON.parse(dl); } catch { continue; }

      if (ev === 'text') {
        full += d.t;
        unsaid += d.t;
        // The mood tag is metadata for the face, never something to read out.
        if (!moodStripped) {
          const m = unsaid.match(/^\s*\[mood:\s*([a-z]+)\s*\]\s*/i);
          if (m) { setMood(m[1].toLowerCase()); unsaid = unsaid.slice(m[0].length); moodStripped = true; }
          else if (unsaid.length > 24 && !/^\s*\[?m?o?o?d?/i.test(unsaid)) moodStripped = true;
        }
        setCaption(full.replace(/^\s*\[mood:[a-z]+\]\s*/i, ''), true);
        // Break on sentence ends so each utterance is a natural phrase.
        let cut;
        while ((cut = unsaid.search(/[.!?。！？](\s|$)/)) !== -1) {
          pushSpeech(unsaid.slice(0, cut + 1));
          unsaid = unsaid.slice(cut + 1);
          status('speaking', 'busy');
        }
      } else if (ev === 'tool') {
        activity(TOOL_WORDS[d.name] || d.name);
      } else if (ev === 'done') {
        outcome = d;
      } else if (ev === 'error') {
        outcome = { mood: 'alert', text: d.text, error: d.raw };
      }
    }
  }

  if (outcome && outcome.error) {
    sayQueue.length = 0;
    return outcome;
  }
  if (unsaid.trim()) pushSpeech(unsaid);
  return outcome || { mood: 'neutral', text: full, tools: [] };
}

async function ask(text) {
  if (busy) return;
  busy = true;
  armedUntil = Date.now() + 15000;
  setCaption(text, false);
  logLine('you', text);
  spokenBase = 0;
  status('thinking', 'busy');
  setMood('thinking', 60000);
  pip(hud.brain, true, 'brain working');

  let reply;
  try {
    reply = await askStreaming(text);
  } catch {
    // Fall back to the whole-answer endpoint if streaming is not available.
    try {
      const r = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ prompt: text }),
      });
      reply = await r.json();
      if (reply.text) pushSpeech(reply.text);
    } catch {
      reply = { mood: 'alert', text: 'I cannot reach my own server. Is it still running on this machine?' };
      pushSpeech(reply.text);
    }
  }

  pip(hud.brain, false, 'brain idle');
  if (reply.tools && reply.tools.length) {
    activity(reply.tools.map((t) => TOOL_WORDS[t] || t).join(', '));
    setTimeout(() => activity(''), 5000);
  } else {
    activity('');
  }
  if (reply.mood) setMood(reply.mood);
  if (reply.text) logLine('dreek', reply.text);
  if (reply.error) { status('brain error', 'alert'); setMood('alert'); pushSpeech(reply.text); }

  // Wait for the queue to finish before listening again, or it hears itself.
  while (sayQueue.length || draining) await new Promise((r) => setTimeout(r, 120));

  busy = false;
  armedUntil = Date.now() + 12000;
  if (!reply.error) setMood('neutral');
  status(analyser ? (handsFree && !armed ? 'say "dreek"' : 'listening') : 'ready', 'idle');
}

/* ---------- wiring ---------- */
hud.micBtn.addEventListener('click', enableMic);
hud.openBtn.addEventListener('click', openRealBrowser);

hud.input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && hud.input.value.trim()) {
    const v = hud.input.value.trim();
    hud.input.value = '';
    ask(v);
  }
});

hud.langSel.value = lang;
hud.langSel.addEventListener('change', () => {
  lang = hud.langSel.value;
  localStorage.setItem('dreek.lang', lang);
  if (recog) { recog.lang = LANGS[lang]; pauseRecognition(); resumeRecognition(); }
  loadVoices();
});

hud.voiceSel.addEventListener('change', () => localStorage.setItem('dreek.voice', hud.voiceSel.value));

const wakeToggle = el('wakeToggle');
function paintWakeToggle() {
  wakeToggle.textContent = handsFree ? 'wake word: on' : 'wake word: off';
  wakeToggle.dataset.on = handsFree ? '1' : '0';
  if (!handsFree) { armed = true; pip(hud.wake, true, 'always on'); }
  else { armed = false; pip(hud.wake, false, 'asleep'); }
  if (analyser) status(handsFree ? 'say "dreek"' : 'listening', 'idle');
}
wakeToggle.addEventListener('click', () => {
  handsFree = !handsFree;
  localStorage.setItem('dreek.handsfree', handsFree ? '1' : '0');
  paintWakeToggle();
});
paintWakeToggle();

document.addEventListener('dreek:mood', (e) => { hud.moodTag.textContent = e.detail; });

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { bargeIn(); speechSynthesis.cancel(); }
  if (e.key === '/' && document.activeElement !== hud.input) { e.preventDefault(); hud.input.focus(); }
});

// A resting shimmer so the face is never inert before the mic is on.
setInterval(() => {
  if (!speaking && !busy && !analyser) setLevel(0.05 + Math.random() * 0.07);
}, 700);

fetch('/api/health').then((r) => r.json()).then((h) => {
  logLine('sys', 'DREEK online. Brain: ' + h.model + '.');
  logLine('sys', handsFree
    ? 'Enable the microphone, then say "Dreek" followed by what you want.'
    : 'Enable the microphone and just talk. Or type below.');
}).catch(() => logLine('sys', 'DREEK online, but the local server did not answer.'));

status('ready', 'idle');
pip(hud.mic, false, 'mic off');
pip(hud.brain, false, 'brain idle');

// The server can start a conversation - a reminder coming due, for instance.
function connectEvents() {
  let es;
  try { es = new EventSource('/api/events'); } catch { return; }
  es.addEventListener('say', (e) => {
    let d; try { d = JSON.parse(e.data); } catch { return; }
    if (!d.text) return;
    logLine('dreek', d.text);
    setCaption(d.text, true);
    setMood(d.mood || 'focused');
    spokenBase = 0;
    pushSpeech(d.text);
  });
  es.onerror = () => { es.close(); setTimeout(connectEvents, 5000); };
}
connectEvents();

window.DREEK = { ask, speak, setMood, setCaption };
