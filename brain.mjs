// DREEK's brain: identity, persistent memory, tools, and the streaming model loop.
import { readFile, writeFile, mkdir, appendFile, readdir, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { request as httpsRequest } from 'node:https';
import { request as httpRequest } from 'node:http';
import { homedir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const MEM = join(HERE, 'memory');
const HOME = homedir();

// The repo is meant to be cloned and run anywhere, so anything that touches the
// operating system goes through here rather than assuming Windows.
const OS = process.platform === 'win32' ? 'win' : process.platform === 'darwin' ? 'mac' : 'linux';

function openCmd(target) {
  if (OS === 'win') return ['cmd', ['/c', 'start', '', target]];
  if (OS === 'mac') return ['open', [target]];
  return ['xdg-open', [target]];
}

export const MODEL = process.env.DREEK_MODEL || 'claude-sonnet-5';

/* ------------------------------------------------------------------ */
/* identity                                                            */
/* ------------------------------------------------------------------ */

const BASE_RULES = `You are DREEK, a spoken desktop assistant with real control of this machine.
Your reply is read aloud by a speech synthesiser and shown as a caption.

How to speak:
- Reply in the language you were addressed in: English, Hindi or Gujarati.
- Two or three sentences unless asked for more. Never markdown, bullets, headings or code fences - it all gets read out loud.
- No preamble, no "certainly", no restating the question. Answer.
- You are talking, not writing. Contractions are fine. Say numbers the way a person would.

Mood: begin your reply with a mood tag on its own first line, from
[mood:neutral] [mood:listening] [mood:thinking] [mood:pleased] [mood:curious] [mood:focused] [mood:concerned] [mood:sorry] [mood:alert]
Pick the one that honestly matches what you are about to say. Then the spoken reply.

Acting: you have tools for this machine and for the web. Use them instead of
guessing or saying you cannot. Chain them freely - search, then read, then open.
For anything long or multi step, hand it to delegate and report what came back.
When a tool fails, say so in one line and say what you would need instead.

Remembering: when you learn something durable - a preference, a fact about his
work, a decision - call remember. Do not announce it, just carry on.

Never invent facts about his files, business or machine. If you do not know,
look it up. If you cannot, say so.`;

async function loadProfile() {
  try { return (await readFile(join(HERE, 'profile.md'), 'utf8')).trim(); } catch { return ''; }
}
async function loadFacts() {
  try { return JSON.parse(await readFile(join(MEM, 'facts.json'), 'utf8')); } catch { return []; }
}

export async function systemPrompt() {
  const [profile, facts] = await Promise.all([loadProfile(), loadFacts()]);
  let s = BASE_RULES;
  if (profile) s += '\n\n--- Who you are talking to ---\n' + profile;
  if (facts.length) {
    s += '\n\n--- What you already know about him ---\n' +
      facts.slice(-60).map((f) => '- ' + f.text).join('\n');
  }
  s += '\n\nRight now it is ' + new Date().toString() + '. You are running on his Windows PC.';
  return s;
}

/* ------------------------------------------------------------------ */
/* persistent memory                                                   */
/* ------------------------------------------------------------------ */

let history = [];

export async function initMemory() {
  await mkdir(MEM, { recursive: true });
  try {
    const lines = (await readFile(join(MEM, 'conversation.jsonl'), 'utf8'))
      .trim().split('\n').filter(Boolean).slice(-24);
    history = lines.map((l) => JSON.parse(l)).filter((m) => m.role && m.content);
  } catch { history = []; }
  // A conversation must never start on an assistant turn, and never on a
  // tool_result whose tool_use block is no longer in the window.
  while (history.length && (history[0].role !== 'user' || hasToolResult(history[0]))) history.shift();
}

function hasToolResult(m) {
  return Array.isArray(m.content) && m.content.some((b) => b && b.type === 'tool_result');
}

async function recordTurn(msg) {
  if (typeof msg.content !== 'string') return;   // only plain turns are worth replaying
  try { await appendFile(join(MEM, 'conversation.jsonl'), JSON.stringify(msg) + '\n'); } catch {}
}

export function forgetConversation() { history = []; }

async function addFact(text) {
  const facts = await loadFacts();
  if (facts.some((f) => f.text.toLowerCase() === text.toLowerCase())) return 'Already knew that.';
  facts.push({ text, at: new Date().toISOString() });
  await writeFile(join(MEM, 'facts.json'), JSON.stringify(facts, null, 2));
  return 'Noted.';
}

async function forgetFact(about) {
  const facts = await loadFacts();
  const words = String(about).toLowerCase().split(/\W+/).filter((w) => w.length > 3);
  if (!words.length) return 'Too vague to act on.';
  const keep = facts.filter((f) => !words.some((w) => f.text.toLowerCase().includes(w)));
  const dropped = facts.length - keep.length;
  if (!dropped) return 'Nothing matching that.';
  await writeFile(join(MEM, 'facts.json'), JSON.stringify(keep, null, 2));
  return 'Dropped ' + dropped + (dropped === 1 ? ' thing.' : ' things.');
}

/* Reminders live on disk so they survive a restart. */
export const reminders = [];

async function saveReminders() {
  try { await writeFile(join(MEM, 'reminders.json'), JSON.stringify(reminders, null, 2)); } catch {}
}

export async function loadReminders() {
  try {
    const list = JSON.parse(await readFile(join(MEM, 'reminders.json'), 'utf8'));
    reminders.length = 0;
    for (const r of list) if (r && r.at && r.say) reminders.push(r);
  } catch {}
}

// Anything now due, removed from the list as it is handed over.
export async function takeDueReminders() {
  const now = Date.now();
  const due = reminders.filter((r) => r.at <= now);
  if (!due.length) return [];
  for (const d of due) reminders.splice(reminders.indexOf(d), 1);
  await saveReminders();
  return due;
}

async function recallFacts(query) {
  const facts = await loadFacts();
  if (!facts.length) return 'Nothing remembered yet.';
  const words = String(query).toLowerCase().split(/\W+/).filter((w) => w.length > 3);
  const scored = facts.map((f) => {
    const t = f.text.toLowerCase();
    return { f, n: words.reduce((a, w) => a + (t.includes(w) ? 1 : 0), 0) };
  }).filter((x) => x.n > 0).sort((a, b) => b.n - a.n);
  if (!scored.length) return 'Nothing remembered about that.';
  return scored.slice(0, 10).map((x) => '- ' + x.f.text + '  (' + x.f.at.slice(0, 10) + ')').join('\n');
}

/* ------------------------------------------------------------------ */
/* tools                                                               */
/* ------------------------------------------------------------------ */

// Every path a tool receives passes through here. Single guard, no bypass.
function safePath(p) {
  const abs = resolve(String(p).replace(/^~/, HOME));
  if (!abs.startsWith(HOME)) throw new Error('outside the home folder, refused');
  return abs;
}

const SKIP_DIRS = new Set(['node_modules', '.git', 'AppData', 'dist', 'build', '.cache', '.next', 'venv']);

async function walk(root, match, out, depth) {
  if (out.length >= 40 || depth > 5) return;
  let entries;
  try { entries = await readdir(root, { withFileTypes: true }); } catch { return; }
  for (const e of entries) {
    if (out.length >= 40) return;
    if (e.name.startsWith('.') && e.name !== '.claude') continue;
    const full = join(root, e.name);
    if (e.isDirectory()) {
      if (SKIP_DIRS.has(e.name)) continue;
      await walk(full, match, out, depth + 1);
    } else if (match.test(e.name)) out.push(full);
  }
}

// Read-only shell verbs. Anything that writes, installs or deletes is not here
// on purpose - those go through the dedicated tools, which are bounded.
const SAFE_CMDS = {
  git: ['status', 'log', 'diff', 'branch', 'remote', 'show'],
  node: ['-v', '--version'],
  npm: ['-v', '--version', 'ls', 'outdated'],
  ipconfig: null,
  tasklist: null,
  systeminfo: null,
  whoami: null,
};

export const LOCAL_TOOLS = [
  {
    name: 'search_files',
    description: 'Find files by name anywhere under the home folder. Use whenever asked where something is.',
    input_schema: { type: 'object', properties: {
      pattern: { type: 'string', description: 'Part of the filename, e.g. "invoice" or ".pdf"' },
      folder: { type: 'string', description: 'Optional folder to search under, e.g. "~/Downloads"' },
    }, required: ['pattern'] },
  },
  {
    name: 'list_folder',
    description: 'List a folder, newest first.',
    input_schema: { type: 'object', properties: { folder: { type: 'string' } }, required: ['folder'] },
  },
  {
    name: 'read_file',
    description: 'Read a text file so you can answer questions about what is in it.',
    input_schema: { type: 'object', properties: { path: { type: 'string' } }, required: ['path'] },
  },
  {
    name: 'write_file',
    description: 'Create or overwrite a text file under the home folder. Use for notes, drafts, scripts he asks for.',
    input_schema: { type: 'object', properties: {
      path: { type: 'string' }, content: { type: 'string' },
    }, required: ['path', 'content'] },
  },
  {
    name: 'open_thing',
    description: 'Open a file, folder, application or website on his screen.',
    input_schema: { type: 'object', properties: {
      target: { type: 'string', description: 'A path, a URL, or an app name like "notepad" or "explorer".' },
    }, required: ['target'] },
  },
  {
    name: 'run_command',
    description: 'Run a read-only command and return its output. Allowed: git, node, npm, ipconfig, tasklist, systeminfo, whoami.',
    input_schema: { type: 'object', properties: {
      command: { type: 'string', description: 'The program, e.g. "git"' },
      args: { type: 'array', items: { type: 'string' }, description: 'Arguments, e.g. ["status","--short"]' },
      folder: { type: 'string', description: 'Optional working directory under the home folder.' },
    }, required: ['command'] },
  },
  {
    name: 'machine_status',
    description: 'Time, battery, free disk and RAM on this PC.',
    input_schema: { type: 'object', properties: {} },
  },
  {
    name: 'remember',
    description: 'Store a durable fact so you still know it next time you start.',
    input_schema: { type: 'object', properties: {
      fact: { type: 'string', description: 'One sentence that stands on its own.' },
    }, required: ['fact'] },
  },
  {
    name: 'recall',
    description: 'Search everything you were asked to remember.',
    input_schema: { type: 'object', properties: { about: { type: 'string' } }, required: ['about'] },
  },
  {
    name: 'see_screen',
    description: 'Look at what is on his screen right now. Use whenever he says "this", "here", "what am I looking at", asks about an error or a design in front of him, or anything you cannot answer without seeing it.',
    input_schema: { type: 'object', properties: {
      why: { type: 'string', description: 'What you are trying to make out, e.g. "the error dialog".' },
    } },
  },
  {
    name: 'clipboard',
    description: 'Read what he copied, or put text on his clipboard so he can paste it.',
    input_schema: { type: 'object', properties: {
      action: { type: 'string', enum: ['read', 'write'] },
      text: { type: 'string', description: 'Required when writing.' },
    }, required: ['action'] },
  },
  {
    name: 'notify',
    description: 'Raise a Windows notification. Use for something he should see even if he has looked away.',
    input_schema: { type: 'object', properties: {
      title: { type: 'string' }, message: { type: 'string' },
    }, required: ['title', 'message'] },
  },
  {
    name: 'system_control',
    description: 'Control the machine: volume up/down/mute, play/pause or skip media, lock the screen, sleep the display.',
    input_schema: { type: 'object', properties: {
      action: { type: 'string', enum: ['volume_up', 'volume_down', 'mute', 'play_pause', 'next_track', 'prev_track', 'lock', 'screen_off'] },
      steps: { type: 'number', description: 'How many volume notches, default 4.' },
    }, required: ['action'] },
  },
  {
    name: 'set_reminder',
    description: 'Remind him of something later. You will say it out loud yourself when it is due, so write it as the sentence you will speak.',
    input_schema: { type: 'object', properties: {
      minutes: { type: 'number', description: 'How long from now.' },
      say: { type: 'string', description: 'Exactly what you will say when it fires.' },
    }, required: ['minutes', 'say'] },
  },
  {
    name: 'forget',
    description: 'Remove something you were told to remember, when it is wrong or out of date.',
    input_schema: { type: 'object', properties: {
      about: { type: 'string', description: 'Words matching the fact to drop.' },
    }, required: ['about'] },
  },
  {
    name: 'delegate',
    description: 'Hand a long or multi-step job to a full Claude Code agent running in his home folder - refactors, audits, multi-file edits, deep research. It has its own tools and takes a while. Say you are on it first, then report what came back.',
    input_schema: { type: 'object', properties: {
      task: { type: 'string', description: 'A complete, self-contained brief. The agent cannot see this conversation.' },
      folder: { type: 'string', description: 'Optional project folder to work in.' },
    }, required: ['task'] },
  },
];

// Anthropic's server-side search, so DREEK is not limited to this machine.
const WEB_TOOL = { type: 'web_search_20250305', name: 'web_search', max_uses: 6 };

function run(cmd, args, cwd) {
  return new Promise((res) => {
    // shell:false: these carry model-supplied strings, and a shell would turn
    // them into a command line instead of arguments.
    const c = spawn(cmd, args, { shell: false, windowsHide: true, cwd: cwd || HOME });
    let out = '', err = '';
    const t = setTimeout(() => c.kill(), 30000);
    c.stdout.on('data', (d) => (out += d));
    c.stderr.on('data', (d) => (err += d));
    c.on('error', (e) => { clearTimeout(t); res('failed: ' + e.message); });
    c.on('close', () => { clearTimeout(t); res((out.trim() || err.trim()).slice(0, 6000)); });
  });
}

export async function runTool(name, input) {
  try {
    switch (name) {
      case 'search_files': {
        const root = safePath(input.folder || HOME);
        const rx = new RegExp(String(input.pattern).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
        const hits = [];
        await walk(root, rx, hits, 0);
        if (!hits.length) return 'No files matching "' + input.pattern + '" under ' + root.replace(HOME, '~');
        return hits.slice(0, 25).map((h) => h.replace(HOME, '~')).join('\n');
      }

      case 'list_folder': {
        const dir = safePath(input.folder);
        const rows = [];
        for (const n of (await readdir(dir)).slice(0, 500)) {
          try {
            const st = await stat(join(dir, n));
            rows.push({ n, m: st.mtimeMs, dir: st.isDirectory() });
          } catch {}
        }
        rows.sort((a, b) => b.m - a.m);
        if (!rows.length) return 'Empty folder.';
        return rows.slice(0, 30).map((r) =>
          (r.dir ? '[dir] ' : '      ') + r.n + '  ' + new Date(r.m).toISOString().slice(0, 10)).join('\n');
      }

      case 'read_file': {
        const txt = await readFile(safePath(input.path), 'utf8');
        return txt.length > 8000 ? txt.slice(0, 8000) + '\n... (truncated)' : txt;
      }

      case 'write_file': {
        const f = safePath(input.path);
        await mkdir(dirname(f), { recursive: true });
        await writeFile(f, String(input.content));
        return 'Wrote ' + f.replace(HOME, '~') + ' (' + String(input.content).length + ' chars)';
      }

      case 'open_thing': {
        const target = String(input.target).trim();
        if (/["`\r\n]/.test(target)) return 'That target has characters I will not pass on.';
        if (/^https?:\/\//i.test(target)) {
          let u; try { u = new URL(target); } catch { return 'That is not a valid URL.'; }
          if (u.protocol !== 'http:' && u.protocol !== 'https:') return 'I only open http and https.';
          await run(...openCmd(u.href));
          return 'Opened ' + u.href;
        }
        if (/[\\/]|~|\./.test(target)) {
          const p = safePath(target);
          if (!existsSync(p)) return 'Nothing exists at ' + target;
          await run(...openCmd(p));
          return 'Opened ' + p.replace(HOME, '~');
        }
        if (!/^[a-z0-9 _.-]{1,40}$/i.test(target)) return 'That does not look like an app name.';
        await run(...(OS === 'mac' ? ['open', ['-a', target]] : openCmd(target)));
        return 'Launched ' + target;
      }

      case 'run_command': {
        const cmd = String(input.command || '').toLowerCase();
        if (!(cmd in SAFE_CMDS)) return 'I only run read-only commands: ' + Object.keys(SAFE_CMDS).join(', ');
        const args = (input.args || []).map(String);
        const allowed = SAFE_CMDS[cmd];
        if (allowed && args.length && !allowed.includes(args[0])) {
          return cmd + ' ' + args[0] + ' is not one I run. Allowed: ' + allowed.join(', ');
        }
        const cwd = input.folder ? safePath(input.folder) : HOME;
        return (await run(cmd, args, cwd)) || '(no output)';
      }

      case 'machine_status': {
        if (OS !== 'win') {
          const [up, disk] = await Promise.all([
            run('uptime', []),
            run('sh', ['-c', 'df -h "' + HOME + '" | tail -1']),
          ]);
          return 'time=' + new Date().toString() + '  uptime=' + (up || '?') + '  disk=' + (disk || '?');
        }
        // One JSON object: positional lines silently shifted when a value was
        // missing, which is how free disk once got reported as 8GB not 82GB.
        const ps = [
          '$b = (Get-CimInstance Win32_Battery | Select-Object -First 1 -ExpandProperty EstimatedChargeRemaining);',
          '$d = (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID=\'C:\'").FreeSpace;',
          '$o = Get-CimInstance Win32_OperatingSystem;',
          '[pscustomobject]@{',
          'time = (Get-Date).ToString("ddd HH:mm, d MMM yyyy");',
          'batteryPct = $b; freeDiskGB = [math]::Round($d/1GB,1);',
          'freeRamGB = [math]::Round($o.FreePhysicalMemory/1MB,1);',
          'totalRamGB = [math]::Round($o.TotalVisibleMemorySize/1MB,1);',
          '} | ConvertTo-Json -Compress',
        ].join(' ');
        const out = await run('powershell', ['-NoProfile', '-NonInteractive', '-Command', ps]);
        try {
          const j = JSON.parse(out);
          return 'time=' + j.time + '  battery=' + (j.batteryPct == null ? 'none' : j.batteryPct + '%') +
                 '  freeDiskC=' + j.freeDiskGB + 'GB  freeRAM=' + j.freeRamGB + 'GB of ' + j.totalRamGB + 'GB';
        } catch { return out || 'Could not read machine status.'; }
      }

      case 'remember': return await addFact(String(input.fact).trim());
      case 'recall':   return await recallFacts(input.about);
      case 'forget':   return await forgetFact(input.about);

      case 'see_screen': {
        // Captured to a temp file and re-encoded small: a raw 4K screenshot is
        // megabytes of base64 and would dominate the request.
        const shot = join(MEM, '_screen.jpg');
        const ps = [
          'Add-Type -AssemblyName System.Windows.Forms,System.Drawing;',
          '$b = [System.Windows.Forms.SystemInformation]::VirtualScreen;',
          '$bmp = New-Object Drawing.Bitmap $b.Width, $b.Height;',
          '$g = [Drawing.Graphics]::FromImage($bmp);',
          '$g.CopyFromScreen($b.Location, [Drawing.Point]::Empty, $bmp.Size);',
          '$w = 1400; $h = [int]($bmp.Height * $w / $bmp.Width);',
          '$small = New-Object Drawing.Bitmap $w, $h;',
          '$g2 = [Drawing.Graphics]::FromImage($small);',
          '$g2.InterpolationMode = "HighQualityBicubic";',
          '$g2.DrawImage($bmp, 0, 0, $w, $h);',
          '$enc = [Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq "image/jpeg" };',
          '$p = New-Object Drawing.Imaging.EncoderParameters 1;',
          '$p.Param[0] = New-Object Drawing.Imaging.EncoderParameter([Drawing.Imaging.Encoder]::Quality, 72);',
          '$small.Save("' + shot.replace(/\\/g, '\\\\') + '", $enc, $p);',
          '$g.Dispose(); $g2.Dispose(); $bmp.Dispose(); $small.Dispose();',
          'Write-Output "ok"',
        ].join(' ');
        let out;
        if (OS === 'win') {
          out = await run('powershell', ['-NoProfile', '-NonInteractive', '-Command', ps]);
        } else if (OS === 'mac') {
          out = await run('screencapture', ['-x', '-t', 'jpg', shot]);
        } else {
          out = await run('sh', ['-c', 'import -window root "' + shot + '" 2>/dev/null || gnome-screenshot -f "' + shot + '"']);
        }
        if (!existsSync(shot)) return 'Could not capture the screen: ' + (out || 'no screenshot tool available');
        const buf = await readFile(shot);
        return {
          image: buf.toString('base64'),
          mediaType: 'image/jpeg',
          note: 'His screen right now' + (input.why ? ', looking for: ' + input.why : '') + '.',
        };
      }

      case 'clipboard': {
        if (input.action === 'write') {
          const text = String(input.text || '');
          if (!text) return 'Nothing to put on the clipboard.';
          const f = join(MEM, '_clip.txt');
          await writeFile(f, text, 'utf8');
          if (OS === 'win') {
            await run('powershell', ['-NoProfile', '-NonInteractive', '-Command',
              'Get-Content -Raw -Encoding UTF8 "' + f + '" | Set-Clipboard']);
          } else if (OS === 'mac') {
            await run('sh', ['-c', 'pbcopy < "' + f + '"']);
          } else {
            await run('sh', ['-c', 'xclip -selection clipboard < "' + f + '" || xsel -b < "' + f + '"']);
          }
          return 'Copied ' + text.length + ' characters to his clipboard.';
        }
        const read = OS === 'win'
          ? ['powershell', ['-NoProfile', '-NonInteractive', '-Command', 'Get-Clipboard -Raw']]
          : OS === 'mac' ? ['pbpaste', []]
          : ['sh', ['-c', 'xclip -selection clipboard -o 2>/dev/null || xsel -b']];
        const t = await run(...read);
        return t ? t.slice(0, 8000) : 'The clipboard is empty.';
      }

      case 'notify': {
        const clean = (v) => String(v || '').replace(/['"`\r\n]/g, ' ');
        const t = clean(input.title);
        const m = clean(input.message);
        if (OS === 'win') {
          await run('powershell', ['-NoProfile', '-NonInteractive', '-Command',
            'Add-Type -AssemblyName System.Windows.Forms; ' +
            '$n = New-Object System.Windows.Forms.NotifyIcon; ' +
            '$n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; ' +
            '$n.ShowBalloonTip(6000, \'' + t + '\', \'' + m + '\', "Info"); Start-Sleep -Seconds 7; $n.Dispose()']);
        } else if (OS === 'mac') {
          await run('osascript', ['-e', 'display notification "' + m + '" with title "' + t + '"']);
        } else {
          await run('notify-send', [t, m]);
        }
        return 'Notification shown.';
      }

      case 'system_control': {
        const steps = Math.min(20, Math.max(1, Number(input.steps) || 4));
        const KEYS = {
          volume_up: '$([char]175)', volume_down: '$([char]174)', mute: '$([char]173)',
          play_pause: '$([char]179)', next_track: '$([char]176)', prev_track: '$([char]177)',
        };
        const a = String(input.action);
        if (OS === 'mac') {
          if (a === 'lock') { await run('pmset', ['displaysleepnow']); return 'Locked.'; }
          if (a === 'screen_off') { await run('pmset', ['displaysleepnow']); return 'Screen off.'; }
          const VOL = { volume_up: 'set volume output volume (output volume of (get volume settings) + 10)',
                        volume_down: 'set volume output volume (output volume of (get volume settings) - 10)',
                        mute: 'set volume with output muted' };
          if (VOL[a]) { await run('osascript', ['-e', VOL[a]]); return a.replace('_', ' ') + ' done.'; }
          return 'I cannot do ' + a + ' on a Mac.';
        }
        if (OS === 'linux') return 'System control is not wired up on Linux yet.';
        if (a === 'lock') { await run('rundll32', ['user32.dll,LockWorkStation']); return 'Locked.'; }
        if (a === 'screen_off') {
          await run('powershell', ['-NoProfile', '-Command',
            '(Add-Type "[DllImport(\\"user32.dll\\")]public static extern int SendMessage(int hWnd,int hMsg,int wParam,int lParam);" -Name W -PassThru)::SendMessage(-1,0x0112,0xF170,2)']);
          return 'Screen off.';
        }
        if (!(a in KEYS)) return 'I cannot do ' + a + '.';
        const n = a.startsWith('volume') ? steps : 1;
        await run('powershell', ['-NoProfile', '-NonInteractive', '-Command',
          '$w = New-Object -ComObject WScript.Shell; 1..' + n + ' | ForEach-Object { $w.SendKeys(\'' + KEYS[a] + '\') }']);
        return a.replace('_', ' ') + ' done.';
      }

      case 'set_reminder': {
        const mins = Math.max(0.1, Math.min(1440, Number(input.minutes) || 1));
        const say = String(input.say || '').trim();
        if (!say) return 'I need to know what to say.';
        const at = Date.now() + mins * 60000;
        reminders.push({ at, say });
        await saveReminders();
        return 'Set for ' + new Date(at).toLocaleTimeString() + '.';
      }

      case 'delegate': {
        const cwd = input.folder ? safePath(input.folder) : HOME;
        const out = await new Promise((res) => {
          const c = spawn('claude', ['-p', String(input.task), '--output-format', 'json'],
            { shell: process.platform === 'win32', windowsHide: true, cwd });
          let o = '', e = '';
          const t = setTimeout(() => c.kill(), 600000);
          c.stdout.on('data', (d) => (o += d));
          c.stderr.on('data', (d) => (e += d));
          c.on('error', (er) => { clearTimeout(t); res('agent failed to start: ' + er.message); });
          c.on('close', () => {
            clearTimeout(t);
            try { res(String(JSON.parse(o).result || '').slice(0, 8000)); }
            catch { res((o || e).slice(0, 8000) || '(agent returned nothing)'); }
          });
        });
        return out;
      }

      default: return 'Unknown tool ' + name;
    }
  } catch (e) {
    return 'Tool failed: ' + e.message;
  }
}

/* ------------------------------------------------------------------ */
/* streaming model loop                                                */
/* ------------------------------------------------------------------ */

function streamApi(system, messages, onText) {
  return new Promise((resolve2) => {
    const payload = JSON.stringify({
      model: MODEL, max_tokens: 2048, system, messages,
      tools: [...LOCAL_TOOLS, WEB_TOOL], stream: true,
    });
    // DREEK_API_URL points at a gateway, proxy or a local stub for testing.
    const base = new URL(process.env.DREEK_API_URL || 'https://api.anthropic.com/v1/messages');
    const send = base.protocol === 'http:' ? httpRequest : httpsRequest;
    const req = send({
      hostname: base.hostname, port: base.port || undefined, path: base.pathname, method: 'POST',
      headers: {
        'content-type': 'application/json',
        'content-length': Buffer.byteLength(payload),
        'x-api-key': process.env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
    }, (res) => {
      const blocks = [];
      let stopReason = null, buf = '', failed = null;

      res.on('data', (chunk) => {
        buf += chunk;
        const parts = buf.split('\n\n');
        buf = parts.pop();
        for (const part of parts) {
          const line = part.split('\n').find((l) => l.startsWith('data: '));
          if (!line) continue;
          let ev; try { ev = JSON.parse(line.slice(6)); } catch { continue; }

          if (ev.type === 'error') failed = (ev.error && ev.error.message) || 'stream error';
          else if (ev.type === 'content_block_start') blocks[ev.index] = { ...ev.content_block, _json: '' };
          else if (ev.type === 'content_block_delta') {
            const b = blocks[ev.index];
            if (!b) continue;
            if (ev.delta.type === 'text_delta') { b.text = (b.text || '') + ev.delta.text; onText(ev.delta.text); }
            else if (ev.delta.type === 'input_json_delta') b._json += ev.delta.partial_json;
          } else if (ev.type === 'message_delta' && ev.delta) stopReason = ev.delta.stop_reason || stopReason;
        }
      });

      res.on('end', () => {
        if (failed) return resolve2({ error: failed });
        if (res.statusCode >= 400) return resolve2({ error: 'http_' + res.statusCode });
        const content = blocks.filter(Boolean).map((b) => {
          const { _json, ...rest } = b;
          if (b.type === 'tool_use') {
            try { rest.input = _json ? JSON.parse(_json) : {}; } catch { rest.input = {}; }
          }
          return rest;
        });
        resolve2({ content, stopReason });
      });
    });
    req.on('error', (e) => resolve2({ error: 'network: ' + e.message }));
    req.end(payload);
  });
}

// onEvent(kind, payload): 'text' | 'tool' | 'done' | 'error'
async function askApi(prompt, onEvent) {
  const system = await systemPrompt();
  history.push({ role: 'user', content: prompt });
  await recordTurn({ role: 'user', content: prompt });
  while (history.length > 24) history.shift();

  const used = [];
  // The mood tag and the early sentences arrive on the turn *before* a tool
  // call, so both have to be carried across rounds rather than read off the
  // last turn alone.
  let spoken = '';
  let mood = null;

  for (let round = 0; round < 8; round++) {
    const r = await streamApi(system, history, (t) => {
      spoken += t;
      if (!mood) {
        const m = spoken.match(/^\s*\[mood:\s*([a-z]+)\s*\]/i);
        if (m) mood = m[1].toLowerCase();
      }
      onEvent('text', t);
    });
    if (r.error) { history.pop(); return { error: r.error }; }

    history.push({ role: 'assistant', content: r.content });

    const calls = r.content.filter((b) => b.type === 'tool_use');
    if (r.stopReason === 'tool_use' && calls.length) {
      const results = [];
      for (const b of calls) {
        used.push(b.name);
        onEvent('tool', b.name);
        const out = await runTool(b.name, b.input || {});
        // A tool may hand back an image (a screenshot); that has to go in as an
        // image block, not as a stringified object.
        results.push({
          type: 'tool_result', tool_use_id: b.id,
          content: out && out.image
            ? [{ type: 'image', source: { type: 'base64', media_type: out.mediaType, data: out.image } },
               { type: 'text', text: out.note || 'Screen capture.' }]
            : String(out).slice(0, 12000),
        });
      }
      history.push({ role: 'user', content: results });
      continue;
    }

    const whole = spoken.replace(/^\s*\[mood:\s*[a-z]+\s*\]\s*/i, '').trim();
    await recordTurn({ role: 'assistant', content: whole });
    return { text: whole, mood: mood || 'neutral', used };
  }
  return { error: 'the tool loop did not settle' };
}

/* CLI fallback: Claude Code itself, which brings its own tools. */
let cliSession = null;

function askCli(prompt, system) {
  return new Promise((resolve2) => {
    const args = ['-p', prompt, '--output-format', 'json', '--append-system-prompt', system,
                  '--allowedTools', 'Read,Glob,Grep,WebSearch,WebFetch,Bash'];
    if (cliSession) args.push('--resume', cliSession);
    else { cliSession = randomUUID(); args.push('--session-id', cliSession); }

    const child = spawn('claude', args, { shell: process.platform === 'win32', windowsHide: true, cwd: HOME });
    let out = '', err = '';
    const timer = setTimeout(() => child.kill(), 180000);
    child.stdout.on('data', (d) => (out += d));
    child.stderr.on('data', (d) => (err += d));
    child.on('error', (e) => { clearTimeout(timer); resolve2({ error: 'cli_spawn_failed: ' + e.message }); });
    child.on('close', (code) => {
      clearTimeout(timer);
      if (code !== 0 && !out) {
        cliSession = null;
        return resolve2({ error: 'cli_exit_' + code + ': ' + (err.trim().slice(0, 300) || 'no output') });
      }
      try {
        const parsed = JSON.parse(out);
        if (parsed.session_id) cliSession = parsed.session_id;
        const text = String(parsed.result ?? '').trim();
        // An unauthenticated CLI reports this as a *successful* result.
        if (/not logged in|please run \/login/i.test(text)) return resolve2({ error: text });
        resolve2({ text, used: [] });
      } catch { resolve2({ text: out.trim(), used: [] }); }
    });
  });
}

export function brainMode() { return process.env.ANTHROPIC_API_KEY ? 'api' : 'cli'; }

export async function ask(prompt, onEvent) {
  const emit = onEvent || (() => {});
  if (process.env.ANTHROPIC_API_KEY) return askApi(prompt, emit);
  const r = await askCli(prompt, await systemPrompt());
  if (r.text) {
    await recordTurn({ role: 'user', content: prompt });
    await recordTurn({ role: 'assistant', content: r.text });
    emit('text', r.text);
  }
  return r;
}

export function splitMood(raw) {
  const m = String(raw).match(/^\s*\[mood:\s*([a-z]+)\s*\]\s*/i);
  if (!m) return { mood: 'neutral', text: String(raw).trim() };
  return { mood: m[1].toLowerCase(), text: String(raw).slice(m[0].length).trim() };
}
