# Miolingo, Part 1: How a Human–AI Pair Built a Multi‑Language Pronunciation Trainer

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


## From local phoneme toy to learner‑ready tool

The Miolingo story begins in the terminal, not the browser. The very first prototype was a local “phoneme toy” that let you type a phrase, record yourself, and compare your pronunciation to an eSpeak NG reference using IPA, with practice history saved in JSON files like `practiceconfig.json` and `practicehistory.json`.[file:60] At this stage everything was command‑line driven: a single Python script recorded audio, called Whisper and `espeak` via subprocess, and printed scores and IPA strings back to the console.[file:60]

Very early on, you pushed beyond hard‑coded examples by introducing language materials as plain text files—word and phrase lists grouped into levels A–D—and asking Claude to write scripts that would normalise case, deduplicate items, and report counts per level.[file:60] One memorable sequence has you running `head -20 words-A/words-01.txt` and pointing out duplicate entries like “Bien” vs “bien”, after which Claude produced a cleaner file where everything was lower‑case and sorted and reported “Level A 74→69 words, 5 duplicates removed” along with similar clean‑ups for the other levels.[file:60]

This pattern—human sets the structure and correctness criterion, AI performs the bulk transformation—repeats throughout the project. The once‑messy wordlists evolve into regular three‑column files (word, translation, `ipa`) ready for automation and later integration into the app.[file:60]

## Crossing into Streamlit and the browser

Once the local practice tool felt solid, you wanted something a real learner could use without touching the terminal, and Streamlit became the vehicle for that transition.[file:60][file:1] Despite your lack of prior experience with Streamlit, its “script‑to‑app” model mapped well onto the existing Python code, and Claude generated a first‑cut `app.py` that wrapped the recording and scoring pipeline in a simple UI: text input, a “Listen first” button, an audio recorder, and a score read‑out.[file:60]

Conceptually, the CLI version looked like a loop of `input → record → analyse → print`, while the first Streamlit draft used `st.text_input`, `st.audio_input` and `st.metric` to surface the same pipeline in a browser.[file:60] This was the second major turning point: from a tool that required reading Python and running commands to something you could put in front of a motivated learner and reasonably expect them to figure out.[file:1]

The “Listen first → Record → Check score and IPA → Replay what you and the model heard” loop emerged here as Miolingo’s core UX pattern, later formalised in the docs and refined in the interface layout.[file:1]

## Six languages and hundreds of items

With a working Portuguese prototype in hand, you widened the scope: Miolingo should serve learners of Portuguese, French, Italian, German, Dutch, and Spanish, not just one language.[file:1] This created two demands: a scalable content pipeline to generate and maintain word/phrase lists per language, and UI affordances for switching between languages and dialects without confusion.[file:60]

The French vocabulary build‑out is a good example of this phase. You asked Claude to convert four French wordlist levels (A–D) into a structured format with translations and IPA, mirroring the phrase files, and to do it in one pass instead of manual editing.[file:60] Claude responded with a script that called Google Translate for glosses and eSpeak NG for IPA, after which you fixed an environment bug where `espeak` initially could not find its data directory inside the venv.[file:60]

Before that script, files had inconsistent casing, missing translations, and literal `ipa` placeholders. Afterward, they became neat matrices of entries like `bonjour  hello  bɔ̃.ʒuʁ`, created in minutes rather than hours.[file:60] The same pattern was then generalised into `populatelanguagematerials.py`, which could take base phrase sets and produce per‑language directories like `pt/phrases-A/phr-01.txt` and `pt/words-A/words-01.txt` with all the right columns filled in.[file:60]

## Built‑in materials and the “18‑minute feature”

Once language content existed on disk, it was natural to want an in‑app “library” rather than forcing every user to upload their own files.[file:1] You asked Claude to propose an integration design, which led to a detailed `LANGUAGEMATERIALSINTEGRATIONPLAN.md` describing how `languagematerials/` should be scanned, how users would browse content, and what metadata to show.[file:60]

On the strength of that plan, you gave a focused prompt: create a feature branch, implement the integration, wire it into the main UI, add tests, and bump the version.[file:60] Claude then produced `applanguagematerials.py`, added a “Built‑in library” tab in `app.py`, ran tests, committed, and tagged `v1.2.0` in roughly eighteen minutes of machine time plus your review.[file:60]

This is the feature you both later described as the “18‑minute sprint”: something that, done manually, could easily have taken two or three days of careful coding and testing, compressed into a single short session where the limiting factor was prompt clarity rather than typing speed.[file:60]

## Hardening and deployment

The final act of the development story is about making Miolingo safe and persistent for real users. Once you realised it might actually see wider use, JSON files were no longer enough; you needed a proper multi‑user architecture with per‑user settings and progress, backed by a managed database that would survive Streamlit Cloud restarts.[file:60][file:69]

Together you chose MySQL on your existing host, designed a six‑table schema (`users`, `sessions`, `usersettings`, `userprogress`, `ratelimits`, `activitylog`), and had Claude capture it in `deployschema.py` plus a long `appmysql.py` module that encapsulated all database operations.[file:60][file:69] On top of this, you added authentication and session management in the UI, designed Argon2id‑based password hashing, and wired everything into Streamlit’s secrets system and an SSH tunnel to Krystal.[file:60][file:69]

By the time you tagged later versions, Miolingo had grown into a production‑ready, multi‑user, cloud‑deployed pronunciation training app under `miolingo.io`, but it still bore the shape of its origins: a local phoneme practice script, expanded and hardened through eighty hours of sustained human–AI collaboration.[file:60][file:1]
