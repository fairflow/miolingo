# Miolingo, Part 2: A Technical Case Study in AI‑Assisted Web Development

Miolingo was not built by a non‑technical founder clicking around a no‑code tool, nor by an expert full‑stack engineer at the top of their game. It was built by a human developer with strong core software and theoretical grounding, working closely with an LLM (Claude Sonnet 4.5) that supplied most of the hands‑on implementation detail.

On the human side, there was long‑term experience with:

- General software design and testing, including finite state machines and agent‑based (CCS‑style) interaction patterns.
- Programming in several languages (including Python), and a solid understanding of algorithms, data structures, and testing frameworks.
- Relational modelling and SQL, enough to reason about schemas, constraints, and indexing.
- UX design and interface work built up over years of user‑facing projects.
- Core developer tooling: Git and GitHub (branches, merges, conflict resolution), shell scripting, SSH tunnelling, Markdown and text‑based documentation workflows.

However, that knowledge was unevenly distributed when it came to the specific web‑app stack used for Miolingo. The developer had never used Streamlit before, had limited practical experience wiring SSH tunnels from a cloud app to a hosted MySQL instance, and had not previously turned formal CCS‑style models into an automated test harness for a speech‑driven web app.

This is where Claude Sonnet 4.5 complemented the human: the model could rapidly generate idiomatic Python and Streamlit code, glue together Whisper, eSpeak NG, Google Cloud TTS, MySQL and Argon2id, and when neither partner knew the exact incantation, it could fill gaps by pulling patterns from documentation.

In the CCS/agent‑based testing work, the human supplied a theoretical model of two interacting agents (roughly “user” and “system”), and Claude turned this into a concrete Python harness that drove the Miolingo UI and checked invariants over state transitions. Whether or not that approach ultimately becomes Miolingo’s long‑term testing backbone, it is already a strong example of theory‑driven human input plus high‑throughput machine implementation.

Across the whole 80‑hour, sixteen‑day arc, the division of labour stayed consistent: the human decided what to build and why, and whether it made sense; Claude decided how to express it in code right now, translating ideas about states, agents, workflows, and security into running software.


## Choosing and wiring the stack

Miolingo’s final architecture weaves together at least nine subsystems: Streamlit for the UI, MySQL on your hosting provider, SSH tunnelling for secure DB access, Argon2id for password hashing, Whisper and wav2vec2 for ASR, eSpeak NG and Google Cloud TTS for synthetic speech, ffmpeg/`soundfile` for audio handling, and a CCS‑inspired test harness for UI behaviour.[file:60][file:69]

Streamlit was chosen not because it is the most powerful web framework, but because it minimises the distance between a Python script and a shareable app. Claude took care of the specifics—`st.set_page_config`, layout primitives, `st.audio_input`, caching—while you focused on flows and feedback that would make sense to pronunciation learners.[file:60][file:1]

On the persistence side, your initial file‑based JSON histories worked for a single user, but as soon as you introduced accounts and multi‑device usage, a relational database became the obvious fit. You repurposed the MySQL/MariaDB instance bundled with your Krystal hosting rather than adopting Supabase or a more opinionated BaaS, keeping control and costs modest.[file:60][file:69]

## Speech stack and TTS evolution

On the speech side, Miolingo is deliberately redundant: Whisper provides general ASR, wav2vec2‑large‑xlsr‑53‑portuguese offers a Brazilian‑tuned alternative, eSpeak NG generates phoneme strings and IPA, and Google Cloud TTS plus gTTS plus eSpeak form a three‑tier fallback chain for target audio.[file:60][file:69][file:1]

Originally, eSpeak NG served both as phoneme engine and synthesiser, which was technically elegant but aurally harsh. You then added gTTS for more natural speech but hit rate limits and reliability issues, prompting a further step to integrate Google Cloud TTS via REST with an API key header, while retaining gTTS and eSpeak as backstops when the primary service is unavailable.[file:69][file:60]

A critical refinement was switching eSpeak from direct playback to using `--stdout` so that WAV data could be captured as bytes and fed into Streamlit’s audio widget. This small change turned uncontrolled bursts of synthetic speech into deliberate, user‑triggered playback, bringing the UX into line with the rest of the app.[file:60]

## MySQL, SSH tunnels, and Streamlit reruns

The database layer lives in `appmysql.py`, an 800‑line module that Claude generated once you agreed on a schema and security posture.[file:60][file:69] It implements everything from `create_user` and `authenticate_user` (with Argon2id) to `create_session`, `validate_session`, `save_user_setting`, `save_practice`, `get_user_progress`, `check_rate_limit`, and `log_activity`.

Because Streamlit reruns scripts on every interaction, SSH tunnelling could not be handled naïvely. Early attempts that started a tunnel at import time either leaked connections or raised “already started” errors as Streamlit re‑executed the top level.[file:60][file:69] After several iterations, you and Claude moved the tunnel into `st.session_state`, combined with health checks so that one tunnel instance could be reused safely across reruns.[file:60][file:69]

This pattern—containing complexity inside a dedicated module and surfacing a clean function API to the UI layer—helped keep `app.py` from becoming unmanageable, and made it easier to reason about bugs like `2013 (HY000) Lost connection to MySQL server during query` without trawling the entire codebase.[file:60]

## CCS‑inspired testing

Miolingo’s CCS‑style testing framework models the app as two interacting agents exchanging actions over a set of traces, rather than as a bag of isolated functions.[file:60] In practice, you wrote high‑level scenarios such as “login → change settings → start practice → verify history updated”, and Claude translated these into Python classes and helpers that could drive the UI and check invariants.

This harness is not yet a full CI suite, but even in its current form it illustrates how theoretical models from concurrency and process calculi can inform testing of rich, stateful web apps. Instead of only asserting that `save_practice()` writes a row, you can specify that certain sequences of user actions must always lead to particular visible states in the interface and underlying database.[file:60]

## Where Claude excelled vs where human judgment was critical

Claude excelled wherever you could specify an interface and desired behaviour: it wrote `appmysql.py` from a schema description, implemented `applanguagematerials.py` from an integration plan, wired in Google Cloud TTS once you described the desired fallback behaviour, and produced substantial documentation such as `SECURITYHARDENING.md` and `MULTIUSERIMPLEMENTATIONPLAN.md` with very little human drafting.[file:60][file:69]

Human judgment was most critical around trade‑offs and failure modes. You chose self‑hosted MySQL over Supabase to avoid lock‑in and control costs, insisted on retaining wav2vec2 despite memory pressure, rejected captchas as bad UX, and spotted cases where a superficially plausible change (like `git clean -fdX` or a function refactor) would quietly introduce risk or regressions.[file:60][file:69]

From a technical perspective, Miolingo shows that AI can readily act as the implementation engine for a non‑trivial stack, but it still needs a human architect and tester to define what “good” looks like and to keep it away from the sharp edges of deployment, data loss, and security.
