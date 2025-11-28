# Miolingo Case Study: Shared Introduction

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
