# Miolingo, Part 4: Efficiency, Logjams, and Designing a 25% Prompt Set

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


## Where the speedup came from

Miolingo’s own project stats describe a codebase with around 3,430 lines of application Python, 2,816 lines of documentation, and a total of 6,246 lines of AI‑generated material, built in roughly 80 hours over about sixteen days.[file:60] A realistic estimate for a solo human developer new to Streamlit, Whisper, SSH tunnelling, and MySQL‑over‑cloud would be on the order of 360–520 hours, putting the effective speedup somewhere between 4× and 6× overall.[file:60]

The biggest gains came from tasks combining repetition with clear structure. Scripts like `extractfrenchwords.py`, `populatefrenchtranslations.py`, and `populatelanguagematerials.py` turned hundreds of word and phrase entries into clean, IPA‑annotated, translation‑rich resources in minutes rather than days.[file:60] The built‑in materials browser, implemented from a written plan in roughly eighteen minutes, is another example of extreme compression where the bottleneck was no longer coding time but clarity of intent.[file:60]

Documentation benefited similarly: over 2,800 lines of guides, changelogs, and plans (for example `USERGUIDE.md`, `DEVELOPERGUIDE.md`, `TESTINGGUIDE.md`, `MULTIUSERIMPLEMENTATIONPLAN.md`) were generated largely on demand, addressing a part of development many projects neglect because it is so time‑consuming when done manually.[file:60]

## Where time was lost: logjams and friction

Miolingo’s logs also reveal clear sources of friction. Long‑context forgetfulness led to repeated corrections about the same issues—using `espeak` not `espeak-ng`, activating the venv before installing, remembering existing scripts instead of re‑writing them—and these repetitions accumulated into a real time cost.[file:60]

Response‑time degradation compounded the problem. Early in the project, responses took seconds; by the time the conversation grew past 40,000 lines, some replies took minutes, forcing you to batch work into larger prompts and endure idle periods while the model processed enormous context windows.[file:60]

Under‑specified debugging prompts and over‑confident advice about commands and APIs—such as `git clean -fdX` in a repo with an important untracked `venv`, or using an authentication mode the Google Cloud TTS client did not support—also caused avoidable detours.[file:60][file:69]

Seen in this light, part of Miolingo’s 80‑hour budget was spent not just on building features, but on learning how Claude behaves under long‑running load: what it forgets, how it handles partial information, and where its suggestions intersect dangerously with tools like git and the shell.[file:60]

## Designing a 25% prompt set for v2

Your idea for Miolingo v2 is to keep the same or greater functional scope while cutting prompt volume to perhaps a quarter of what you used the first time. The project history suggests three artefacts that would make this realistic: a `PROJECT_CHECKLIST.md` of non‑negotiables, a `SCRIPTS_INDEX.md` of existing utilities, and a stable prompt library for recurring operations.[file:60]

`PROJECT_CHECKLIST.md` would encode all the hard‑won “never again” lessons: always activate the venv; never use `git clean -fdX` without a dry‑run and careful review; know the exact `espeak` binary name and path; understand which dialect codes are valid for each engine; and document where secrets and keys live.[file:60]

`SCRIPTS_INDEX.md` would list every helper script—`deployschema.py`, `testkrystalconnection.py`, `fillipatags.py`, `populate...` tools—along with a one‑line description and invocation pattern, so future prompts can say “use `fillipatags.py` as per `SCRIPTS_INDEX.md`” instead of accidentally requesting a reinvention.[file:60]

A small library of reusable prompt templates—for “write an implementation plan,” “implement this plan in code and tests,” “perform a post‑mortem and update the checklist,” and “extend the CCS test harness for this scenario”—would further reduce future prompts to short references plus deltas, rather than lengthy explanations repeated across sessions.[file:60]

If Miolingo v1’s 43,000‑line conversation is treated as a learning trace, Miolingo v2’s could be a distillation: fewer, more structured interactions grounded in documents you already know you need. The same architecture and feature set could likely be reproduced with 20–25% of the conversational footprint, because so many of the logjams you hit—forgetfulness, environment drift, over‑long context—are now known quantities you can proactively mitigate.

## Concluding reflections

Miolingo demonstrates that AI‑assisted development can raise a single developer’s throughput by a factor of four to six for a non‑trivial web app, provided they bring solid conceptual understanding and are prepared to manage the model’s limitations.[file:60][file:1] The next iteration need not repeat the same mistakes at the same cost: by externalising lessons into checklists, indexes, and prompt patterns, you can treat Miolingo v1 as the expensive training run and Miolingo v2 as the streamlined, higher‑leverage sequel.
