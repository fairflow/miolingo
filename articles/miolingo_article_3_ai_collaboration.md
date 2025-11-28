# Miolingo, Part 3: What 80 Hours of Pair Programming with an LLM Actually Looked Like

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


## Prompt patterns that worked

Certain prompt shapes stand out across the Miolingo transcript. The most productive were concrete, bounded tasks that specified both the goal and the constraints, such as “read these docs, propose an integration plan, then implement it on a feature branch and update the changelog.”[file:60]

The built‑in materials browser is a textbook example. You first asked Claude to analyse the existing `languagematerials/` directory and propose how users should browse content; Claude replied with `LANGUAGEMATERIALSINTEGRATIONPLAN.md`, a multi‑step design document.[file:60] Only once that existed did you prompt it to implement the plan in `applanguagematerials.py`, integrate into `app.py`, write tests, and bump the version—work it completed in under twenty minutes.[file:60]

By contrast, under‑specified debugging prompts like “the SSH tunnel doesn’t work” led to thrashing: speculative changes to ports, bind addresses, and secrets until you narrowed the focus with full tracebacks and exact code snippets. That shift—from vague complaints to tightly scoped, example‑driven prompts—marked a turning point in how effective Claude could be as a collaborator.[file:60][file:69]

## How mistakes surfaced and were corrected

Claude’s mistakes tended to fall into three buckets: environment assumptions, API over‑confidence, and incomplete refactors.[file:60]

Environment issues included running `pip install` outside the venv, suggesting `git clean -fdX` in a repository where the active `venv` was untracked, and repeatedly using `espeak-ng` as a binary name when only `espeak` existed.[file:60] You caught these by running the commands, observing failures or unintended consequences, and then issuing precise corrections—“we must remember to enter the venv,” “it’s `espeak`, not `espeak-ng`, can we make a checklist because you keep forgetting.”[file:60]

API over‑confidence showed up in the Google Cloud TTS integration, where Claude initially claimed API keys could be used with the Python client library. After multiple failed attempts and a careful reading of the docs, you forced a pivot to using the REST API with `X-goog-api-key` headers, which finally worked.[file:69][file:60]

Incomplete refactors were most obvious in function signature changes: updating a definition like `generate_target_audio` without fixing all call‑sites produced runtime errors that only surfaced during manual testing.[file:60] In response, you asked not only for code fixes but also for post‑mortems that captured the failure mode and recommended process changes, such as adding static type checking and more disciplined search‑and‑replace when refactoring.[file:60]

## Steering strategies that mattered

Three steering strategies were especially important: clarifying identity, setting constraints, and asking for meta‑artefacts.

Clarifying identity—correcting the “non‑programmer” label and explaining your experience teaching Python and working with formal models—changed how Claude wrote explanations and summaries, avoiding oversimplification and aligning better with your real skill level.[file:60]

Constraint setting kept Claude from optimising the wrong things. You explicitly banned captchas, insisted on keeping wav2vec2 despite memory concerns, and required that authentication and SQL live in a separate `appmysql.py`, which prevented a drift toward an unmaintainable `app.py` monolith.[file:60][file:69]

Meta‑requests—prompts for implementation plans, post‑mortems, and checklists—turned one‑off fixes into reusable process. Documents like `MULTIUSERIMPLEMENTATIONPLAN.md`, `SECURITYHARDENING.md`, and `PROJECTSTATS.md` all arose from you asking for structured reflections rather than just immediate patches.[file:60]

## What this says about AI pair programming

Miolingo portrays Claude not as an autocomplete engine, but as a very fast, broadly knowledgeable, sometimes forgetful senior junior developer. It excelled at implementing well‑specified features, generating boilerplate, turning theoretical ideas (like CCS‑style testing) into concrete harnesses, and drafting substantial documentation on demand.[file:60]

Your role was that of architect, product owner, and QA lead: defining goals and constraints, catching incorrect or risky suggestions, deciding how to resolve trade‑offs, and insisting on tests and post‑mortems when things broke.[file:60][file:69] The 4–6× productivity gain Miolingo achieved depends on that combination: Claude’s throughput plus your judgment.

The logs make it clear that AI pair programming does not remove the need for programming literacy; instead, it raises the ceiling on what a single literate developer can ship in a limited time, provided they are willing to treat the model as a powerful but imperfect collaborator rather than an infallible oracle.
