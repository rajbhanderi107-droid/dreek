// DREEK - local console server. Serves the UI and fronts the brain.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ask, splitMood, initMemory, brainMode, forgetConversation, MODEL,
         loadReminders, takeDueReminders } from './brain.mjs';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), 'public');
const PORT = Number(process.env.DREEK_PORT || 4173);

const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
};

const sse = (kind, data) => 'event: ' + kind + '\ndata: ' + JSON.stringify(data) + '\n\n';

function json(res, code, obj) {
  res.writeHead(code, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(obj));
}

function authHint(err) {
  if (/not logged in|\/login/i.test(err)) {
    return 'My brain is not authenticated yet. Run claude setup-token in a terminal, or set an API key, then start me again.';
  }
  if (/authentication_error|invalid x-api-key|http_401/i.test(err)) {
    return 'That API key was rejected. Check ANTHROPIC_API_KEY and start me again.';
  }
  if (/network:/i.test(err)) return 'I cannot reach the network right now.';
  if (/http_429|rate/i.test(err)) return 'I am being rate limited. Give me a moment.';
  return 'My brain link failed. ' + err;
}

async function readBody(req) {
  let body = '';
  for await (const chunk of req) body += chunk;
  try { return JSON.parse(body); } catch { return {}; }
}

await initMemory();
await loadReminders();

/* ---- proactive channel: the server can start a conversation ---- */
const listeners = new Set();

function broadcast(kind, data) {
  for (const res of listeners) {
    try { res.write(sse(kind, data)); } catch {}
  }
}

setInterval(async () => {
  for (const r of await takeDueReminders()) broadcast('say', { text: r.say, mood: 'focused' });
}, 5000);

/* ---- escape hatch for embedded viewers that block the microphone ---- */
const BROWSERS = [
  process.env.ProgramFiles + '\Microsoft\Edge\Application\msedge.exe',
  process.env['ProgramFiles(x86)'] + '\Microsoft\Edge\Application\msedge.exe',
  process.env.ProgramFiles + '\Google\Chrome\Application\chrome.exe',
  process.env['ProgramFiles(x86)'] + '\Google\Chrome\Application\chrome.exe',
];

function openRealBrowser() {
  const url = 'http://localhost:' + PORT + '/';
  const exe = BROWSERS.find((p) => p && existsSync(p));
  if (exe) {
    spawn(exe, ['--app=' + url, '--window-size=1600,900'], { detached: true, stdio: 'ignore' }).unref();
    return exe.includes('msedge') ? 'Edge' : 'Chrome';
  }
  // Hard-coded Program Files paths miss per-user and store installs. `start`
  // resolves the name through the App Paths registry, which does not.
  for (const [name, label] of [['msedge', 'Edge'], ['chrome', 'Chrome']]) {
    try {
      spawn('cmd', ['/c', 'start', '', name, '--app=' + url, '--window-size=1600,900'],
        { detached: true, stdio: 'ignore', windowsHide: true }).unref();
      return label;
    } catch {}
  }
  spawn('cmd', ['/c', 'start', '', url], { detached: true, stdio: 'ignore', windowsHide: true }).unref();
  return 'your default browser';
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');

  if (url.pathname === '/api/health') {
    return json(res, 200, {
      ok: true, mode: brainMode(),
      model: brainMode() === 'api' ? MODEL : 'claude-code-cli',
      streaming: brainMode() === 'api',
    });
  }

  // Streamed answer: text arrives token by token so the face can start
  // speaking the first sentence while the rest is still being written.
  if (req.method === 'POST' && url.pathname === '/api/stream') {
    const prompt = String((await readBody(req)).prompt || '').trim();
    if (!prompt) return json(res, 400, { error: 'empty_prompt' });

    res.writeHead(200, {
      'content-type': 'text/event-stream; charset=utf-8',
      'cache-control': 'no-cache',
      connection: 'keep-alive',
      'x-accel-buffering': 'no',
    });
    const send = (kind, data) => {
      if (!res.writableEnded) res.write('event: ' + kind + '\ndata: ' + JSON.stringify(data) + '\n\n');
    };

    let closed = false;
    req.on('close', () => { closed = true; });

    const t0 = Date.now();
    const r = await ask(prompt, (kind, payload) => {
      if (closed) return;
      if (kind === 'text') send('text', { t: payload });
      else if (kind === 'tool') send('tool', { name: payload });
    });

    if (r.error) send('error', { text: authHint(r.error), raw: r.error });
    else send('done', { mood: r.mood || splitMood(r.text).mood, text: splitMood(r.text).text, tools: r.used || [], ms: Date.now() - t0 });
    if (!res.writableEnded) res.end();
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/ask') {
    const prompt = String((await readBody(req)).prompt || '').trim();
    if (!prompt) return json(res, 400, { error: 'empty_prompt' });
    const t0 = Date.now();
    const r = await ask(prompt);
    if (r.error) return json(res, 200, { mood: 'alert', text: authHint(r.error), error: r.error, tools: [] });
    return json(res, 200, { mood: r.mood || splitMood(r.text).mood, text: splitMood(r.text).text, tools: r.used || [], ms: Date.now() - t0 });
  }

  if (url.pathname === '/api/events') {
    res.writeHead(200, {
      'content-type': 'text/event-stream; charset=utf-8',
      'cache-control': 'no-cache', connection: 'keep-alive', 'x-accel-buffering': 'no',
    });
    res.write(sse('ready', {}));
    listeners.add(res);
    req.on('close', () => listeners.delete(res));
    return;
  }

  // The microphone is unavailable inside embedded viewers, and no amount of
  // client-side code can grant it. The server can launch a real browser.
  if (req.method === 'POST' && url.pathname === '/api/open-browser') {
    try { return json(res, 200, { ok: true, browser: openRealBrowser() }); }
    catch (e) { return json(res, 200, { ok: false, error: e.message }); }
  }

  if (req.method === 'POST' && url.pathname === '/api/reset') {
    forgetConversation();
    return json(res, 200, { ok: true });
  }

  const rel = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
  const file = normalize(join(ROOT, rel));
  if (!file.startsWith(ROOT)) { res.writeHead(403).end('forbidden'); return; }
  try {
    const buf = await readFile(file);
    res.writeHead(200, { 'content-type': MIME[extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' });
    res.end(buf);
  } catch {
    res.writeHead(404).end('not found');
  }
});

server.listen(PORT, () => {
  console.log('DREEK  ->  http://localhost:' + PORT);
  console.log('brain: ' + brainMode() + (brainMode() === 'api' ? ' (' + MODEL + ', streaming)' : ' (claude code cli)'));
});
