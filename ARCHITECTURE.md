# How DREEK is put together

Written so someone - or another model - can pick this up cold. No build step, no
framework, no dependencies. Plain ES modules on both sides.

```
server.mjs        HTTP + SSE. Serves public/ and fronts the brain.
brain.mjs         Identity, memory, tools, and the streaming model loop.
profile.md        Who the user is. Read fresh on every question. Gitignored.
memory/           Runtime state. Gitignored.
  facts.json          durable facts, written by the remember tool
  conversation.jsonl  every plain turn; last 24 reloaded on start
  reminders.json      pending reminders, survive a restart
public/
  index.html      Markup and the early error handler.
  dreek.js        The renderer. Owns the canvas, exports setMood/setLevel/setSpectrum.
  app.js          Mic, speech recognition, wake word, TTS, and brain calls.
  style.css
```

## Request flow

1. `app.js` collects speech (or typed text) and POSTs to `/api/stream`.
2. `server.mjs` calls `ask()` and forwards each event as SSE:
   `text` per token, `tool` per tool call, then `done` or `error`.
3. `brain.mjs` streams from the model, runs any tools, feeds the results back,
   and loops up to 8 rounds.
4. `app.js` splits arriving text at sentence ends and queues each sentence for
   speech, so DREEK talks while the rest is still being written.

`/api/ask` is the same thing without streaming, used as a fallback and by the
CLI path. `/api/events` is the reverse direction: the server pushes `say` events
when a reminder comes due, so DREEK can start a conversation.

## Two brains

`brainMode()` picks based on `ANTHROPIC_API_KEY`:

- **api** - streams from the Messages API with the full local tool set plus
  Anthropic's server-side `web_search`. This is the good path.
- **cli** - spawns `claude -p`, which brings its own tools but cannot stream and
  cannot take images. Needs `claude setup-token` once.

`DREEK_API_URL` redirects the API path at a gateway, proxy, or a local stub.
The stub is how the streaming tool loop is tested without spending a key: emit
Anthropic-shaped SSE frames and point `DREEK_API_URL` at it.

## Tools

Defined in `LOCAL_TOOLS`, dispatched by `runTool(name, input)`. A tool returns a
string, or `{ image, mediaType, note }` when it hands back a picture - the loop
turns that into an image block so the model can actually look at it.

Two invariants, both load-bearing:

- **`safePath()` guards every path.** It resolves `~`, then refuses anything
  that escapes the home folder. There is no second path check anywhere; do not
  add a tool that bypasses it.
- **`run()` spawns with `shell: false`.** Tool inputs are model-supplied. With a
  shell they would be concatenated into a command line, which is an injection.
  Anything OS-specific goes through the `OS` switch at the top of the file.

## The renderer

`dreek.js` holds ~11,000 particles in one flat array. Each has a target; each
frame it moves toward it. Groups: `SKIN NECK SHOULDER FILAMENT RIDGE MOTE WING`.
Static groups have fixed targets computed once in `buildFigure()`; `SKIN`,
`RIDGE` and `WING` recompute theirs every frame from the audio spectrum.

The head is `SKIN`: a cloud of ~22,000 specks scattered by rejection sampling
against `face-data.js`, which holds a 220x300 8-bit luminance map of the
portrait as base64 raw bytes - no image decoder, no network fetch. It is their
DENSITY that carries the tone: many where the face is lit, almost none in
shadow, so the head simply thins out into the star field at its edges.

Every speck is the same kind of dust and drifts on its own small orbit. That
distinction is the whole point - a grid of differently sized dots is a halftone
print of a photograph, which is what this deliberately is not. Sound widens the
orbits and pushes the cloud outward from the centre of the face.

The map is feathered to black on an ellipse; without that the crop rectangle
shows as a hard edge down one side. The acceptance exponent (`lum ** 1.75`)
sets the contrast: raise it and only the highlights survive, lower it and the
features wash out into noise.

To use a different portrait, regenerate `face-data.js`: blur out any existing
print screen first (it moires against this grid), downsample to ~220x300 grey,
feather the edges, then base64 the raw bytes.

Things that were learned the hard way and are easy to break again:

- The damped spring `v = (v + e*k) * 0.72` is only stable while `2.57*k < 1`.
  The skin uses direct easing instead, because it needs to track faster than
  that allows - with momentum the dots overshoot and smear the face.
- Sprites are a solid core plus a halo. A pure radial gradient at 1-2px radius
  throws away nearly all its energy and the whole figure reads as haze.
- Wing angles must not carry the side, or one wing lifts while the other drops.
- Keep `requestAnimationFrame(frame)` exactly as it is. A `setTimeout` fallback
  was tried and silently killed the loop.

`?debug` draws the geometry guides. `?settle=400` advances the simulation 400
fixed ticks before the first paint, which is how to inspect the resting figure
anywhere `requestAnimationFrame` is throttled.

## The microphone

`getUserMedia` is blocked outright inside embedded viewers - the Claude Code
browser pane, most in-app webviews. No page-side permission can grant it. When
the mic is refused, `app.js` says so and offers **Open in a real browser**,
which asks the server to launch Edge or Chrome as a frameless app window. The
server can do what the page cannot.

## Adding a tool

1. Append a definition to `LOCAL_TOOLS` in `brain.mjs`. Write the description
   for the model, not for a human: say when to reach for it.
2. Add a `case` to `runTool`. Route paths through `safePath`, commands through
   `run`, and anything OS-specific through the `OS` switch.
3. Add a friendly phrase to `TOOL_WORDS` in `app.js` so the HUD can say what it
   is doing.
