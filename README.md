# DREEK

A spoken assistant with a face. Everything on screen is generated from about
10,000 particles a frame - the head contour, the concentric face rings, the
neck, shoulders and the spectrum terrain. There is no photograph anywhere.

## Run it from a clone

    git clone https://github.com/rajbhanderi107-droid/dreek.git
    cd dreek
    cp profile.example.md profile.md      # then edit it as yourself
    node server.mjs

No dependencies, no build step - plain ES modules, Node 20 or newer. Runs on
Windows, macOS and Linux; the tools that touch the OS pick the right command per
platform, and say so plainly where something is not wired up yet.

See ARCHITECTURE.md before changing anything - it records the traps.

## Run

    node server.mjs

Or double-click `start-dreek.bat`, which opens it in Edge as a frameless app
window (Edge is preferred - its online neural voices sound far better than the
bundled robotic ones).

## Brain

DREEK needs one of these, or it will tell you it is not authenticated:

- `claude setup-token` once in a terminal - uses your Claude subscription, and
  DREEK gets Claude Code's own read and web tools; or
- `set ANTHROPIC_API_KEY=...` before starting - talks to the API directly and
  uses DREEK's own tool set below. Pick a model with `DREEK_MODEL`
  (default `claude-sonnet-5`).

## What it can actually do

With an API key it has real tools, not just conversation:

| tool | what it does |
|---|---|
| `search_files` | finds files by name anywhere under your home folder |
| `list_folder` | lists a folder, newest first |
| `read_file` | reads a text file to answer questions about it |
| `write_file` | creates or overwrites a file - notes, drafts, scripts |
| `open_thing` | opens a file, folder, app or website on your screen |
| `run_command` | runs read-only commands: git, node, npm, ipconfig, tasklist, systeminfo, whoami |
| `machine_status` | time, battery, free disk and RAM |
| `remember` / `recall` | stores and searches durable facts about you |
| `delegate` | hands a long job to a full Claude Code agent in your home folder |
| `web_search` | Anthropic's server-side search, so it is not limited to this machine |
| `see_screen` | takes a screenshot and looks at it - ask about "this" or an error in front of you |
| `clipboard` | reads what you copied, or puts text there to paste |
| `notify` | raises a Windows notification |
| `system_control` | volume, mute, play/pause, next/previous track, lock, screen off |
| `set_reminder` | says something out loud later, unprompted, and survives a restart |
| `forget` | drops a fact that is wrong or out of date |

It chains them freely - search, then read, then open - and answers out loud while
the rest is still being written, sentence by sentence.

Every path is confined to your home folder, and commands are spawned without a
shell, so a filename or URL can never turn into a command.

## Memory

- `profile.md` - who you are. Read fresh on every question, so edits apply
  without restarting.
- `memory/facts.json` - things you told it to remember.
- `memory/conversation.jsonl` - full history; the last 24 turns are reloaded on
  start, so it wakes up knowing what you were talking about.

## The microphone

`getUserMedia` is blocked outright inside embedded viewers such as the Claude
Code browser pane - no page-side permission can grant it there. If the mic is
refused, DREEK now says so plainly and shows **Open in a real browser**, which
asks the server to launch Edge or Chrome as a frameless app window. The mic
works there. `start-dreek.bat` does the same thing from the start.

## Talking to it

Press **Enable microphone**, then say **"Dreek…"** followed by what you want.
It wakes on its name, answers aloud, and goes back to sleep after a quiet spell.
Turn the wake word off to have it listen continuously. Talking over it stops it
mid-sentence, and so does Escape. Typing does exactly the same thing.

English, Hindi and Gujarati are selectable; it replies in whichever you use.

## Debug flags

- `?debug` - geometry guides and a stats line.
- `?settle=400` - advance the simulation 400 fixed ticks before the first paint.
  Use this wherever `requestAnimationFrame` is throttled and the field would
  otherwise never converge.
- `DREEK_API_URL` - point the brain at a gateway, proxy, or a local stub. The
  stub is how the streaming tool loop is tested without spending a key.
