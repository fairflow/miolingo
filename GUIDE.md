# Getting Started

Miolingo is a pronunciation trainer: you get a word, phrase, or story line in
one of seven languages, record yourself saying it, and get phoneme-level
feedback on what you actually said versus the target pronunciation.

There are two ways to run it, because the project is mid-migration from one
to the other (see [DEVELOPMENT.md](DEVELOPMENT.md) for why). Pick one.

## Option A — the Streamlit app (the current production app)

This is what's actually deployed and in use today.

**Try it without installing anything:** the app is deployed at
[miolingo3.streamlit.app](https://miolingo3.streamlit.app) and
[miolingo.io](https://miolingo.io).

**To run it locally:**

Prerequisites:
- Python 3.8+ (3.10+ recommended)
- eSpeak NG (`brew install espeak-ng` or `port install espeak-ng`) — used for
  text-to-speech and for generating the reference IPA transcription
- ffmpeg — audio format conversion
- portaudio — audio recording
- a MySQL database (local or remote) — accounts, progress, vocab

```bash
git clone https://github.com/fairflow/miolingo.git
cd miolingo

./configure                    # checks Python version, creates venv/, checks for espeak-ng
source venv/bin/activate
make install                   # pip install -r requirements.txt

cp .streamlit/secrets_template.toml .streamlit/secrets.toml
# edit .streamlit/secrets.toml: DB credentials, TTS/translation API keys if you want those

make run                       # streamlit run src/app.py --server.port 8501
```

Open `http://localhost:8501`. You can use the app as a guest (no account,
nothing saved) or register a username/password to keep history and vocab
across sessions.

There's also an admin dashboard (`make run-admin`, port 8505) for monitoring
usage, users, and API cost — not needed to use the app itself.

Full walkthrough of the UI: [docs/app-docs/USER_GUIDE.md](docs/app-docs/USER_GUIDE.md).

## Option B — the web port (in-progress rewrite, local-only)

`web/` is a from-scratch rewrite as a local-first single-page app (Svelte 5 +
TypeScript in the browser, no account/login, all data in IndexedDB) talking
to a small Python backend that does the actual phonetics work. It has no
database, no auth, and isn't deployed anywhere — it's a working local build
you run from a checkout, currently the most actively developed part of the
codebase.

Prerequisites: the same Python stack as above (the backend imports directly
from `src/`), plus Node.js for the frontend.

```bash
cd web/app && npm install                         # once
pip install -r web/oracle/requirements.txt         # once, into the repo's venv

cd web && make dev
```

This starts two processes: Vite serving the SPA on `:8330` and a FastAPI
sidecar (the "oracle") on `:8331` doing espeak/Whisper/scoring work. Vite
proxies `/api` and `/materials` through to the oracle so the browser only
ever talks to one origin. Open `http://localhost:8330`.

`make serve` instead builds the SPA and serves it from the oracle process
directly on `:8331` — closer to how it'd look self-hosted.

See [web/README.md](web/README.md) and [web/docs/DESIGN.md](web/docs/DESIGN.md)
for what's implemented so far (practice loop, vocab, story reader, stats —
see the M1–M8 milestones in `web/docs/DESIGN.md`).

## What you'll actually do in either version

1. Pick your source language (what you speak) and target language (what
   you're learning).
2. Pick a practice mode: single words, phrases, short conversations, or a
   story.
3. Read the target text and its IPA transcription, optionally play the
   reference audio (TTS).
4. Record yourself saying it.
5. Get back: what the speech recognizer heard, the IPA for both the target
   and what you said, a similarity score, and which specific phones you got
   wrong.

See [MANUAL.md](MANUAL.md) for how the scoring actually works and what each
feature does.
