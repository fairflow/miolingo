# Miolingo Development: A Detailed Chronicle

## Authorship

This was essentially written by Claude Sonnet 4.5, with contractions and corrections by the developer, Matthew Fairtlough (aka fairflow).

## Introduction

This document contains extensive information about the Miolingo app development history, drawn from the complete development transcript. This includes all commands, corrections, tags, and comments showing how the app unfolded through the collaboration between developer and LLM—the missteps, mistakes, and leaps forward.

The main repository is at [https://github.com/fairflow/miolingo](https://github.com/fairflow/miolingo) with documentation in the `docs/` directory.

## Analysis

We examine four key aspects of the development process [^1][^2]:

1. **Development Story**: Chronological narrative identifying initial vision, major features, key challenges, and the role Claude played at each stage
2. **Technical Insights**: Technology choices, technical challenges, code architecture evolution, and where AI vs human expertise was critical
3. **AI Collaboration Insights**: Interaction patterns, prompt effectiveness, mistake patterns, and steering techniques
4. **Efficiency Analysis**: Time quantification, AI speedups, areas where AI didn't help, and comparison to traditional development

### Development Story

#### Initial vision and first prototypes

The project began from a very concrete learning goal: build a pronunciation trainer that gives **objective, phoneme-level feedback** rather than the vague “correct/incorrect” feedback of mainstream apps.[^2][^1]
The earliest phase was a local practice app built around eSpeak NG and a simple workflow: load word/phrase lists, record audio, run phoneme comparison, and store results in JSON files like `practiceconfig.json` and `practicehistory.json`.[^2]

From there the vision shifted from a single-language, developer-only tool into something a motivated learner could use daily with minimal setup.[^2]
The Streamlit-based Miolingo UI emerged as the natural next step: turn the CLI-style practice tooling into a browser app with buttons, lists of words/phrases, and clear “Listen → Record → Check” flows.[^1][^2]

#### Major features in chronological sequence

1. **Core pronunciation workflow (single language)**
    - Basic “enter phrase, record audio, compare to target” pipeline with Whisper recognition and eSpeak NG phoneme analysis.[^2]
    - Early UX: minimal UI, robotic eSpeak audio, but already demonstrated that similarity scoring and IPA feedback could work in real time.[^2]
2. **Curated materials and history for the local practice app**
    - Word and phrase lists organized into levels (A–D), with duplicates cleaned, case normalized, and counts reported (e.g., “Level A 74→69 words, 5 duplicates removed”).[^2]
    - This structure was later discarded as automated level analysis proved unsatisfactory
    - Data files plus comments and tags embedded into the practice pipeline so that every attempt could be logged and later reviewed.[^2]
3. **Transition to Miolingo web app (Streamlit)**
    - Core page with a standard pattern: “Enter or pick phrase → Listen to target → Record → See score and IPA comparison → Replay your audio and what ASR heard.”[^1][^2]
    - Real-time similarity scores and visual IPA feedback became central, replacing the text-heavy console outputs of the earlier tool.[^1][^2]
4. **“Listen First” and guided workflow UX**
    - A specific “Listen First” button was added to encourage learners to hear the Google TTS version **before** recording, to anchor target pronunciation.[^2]
    - The transcript describes a “standard workflow” section explicitly teaching: click Listen First → record → check pronunciation → replay both target and recognized speech.[^2]
5. **Six-language expansion and content build-out**
    - Languages: Portuguese (Brazilian), French, Italian, German, Dutch, Spanish were added with curated word/phrase sets and stories for contextual practice.[^1][^2]
    - The transcript shows bulk generation and cleaning of hundreds of items (e.g., 628 French and 255 Portuguese entries, with IPA and translations).[^2]
6. **Better audio: Google Cloud TTS + fallback chain**
    - Early versions relied on eSpeak NG for both target and phoneme-level feedback, resulting in robotic target audio.[^2]
    - A pivotal turning point was adding Google Cloud TTS for “natural-sounding” target speech, with gTTS and eSpeak NG as fallback options to handle rate limits or outages.[^3][^2]
7. **Production deployment: MySQL, SSH tunnel, multi-user plan**
    - Once it felt like "this might take off", the design pivoted from a single-user, file-based app to a multi-user architecture using MySQL on an external host accessed via an SSH tunnel.[^2]
    - The transcript outlines detailed work on encrypted tunnels, database schemas for users and progress, and a staged plan to add authentication, rate limiting, and admin tools.[^2]
8. **Refinement: progress tracking, built-in materials, and docs**
    - Per-user, per-language progress tracking and dashboards were planned and partially implemented so learners could see how their scores evolved.[^1]
    - A “built-in materials library” was added surprisingly quickly, wiring language folders of texts into the app with metadata and filters so users can pick curated content.[^2]
    - Extensive documentation (app guides, quick-starts, summaries) was generated to make Miolingo approachable without handholding.[^2]

#### Five–seven key challenges and how they were overcome

1. **Audio quality vs technical phoneme accuracy**
    - Problem: eSpeak NG was great for phoneme-level detail but unpleasant as a learning audio source.[^2]
    - Solution: Split roles—Google Cloud TTS for natural target audio, eSpeak NG retained underneath for IPA and phoneme comparison, creating a layered feedback system.[^3][^2]
2. **Whisper hallucinations and short-word recognition**
    - Problem: Whisper would hallucinate content with silence (e.g., isso being decoded as something closer to “Jesus”) or garbled syllables like “p,easy toU”.[^2]
    - Solution: Introduced better recording guidance, shorter durations for single words, moderated trimming of silence, temperature tuning, and tests with dedicated scripts (e.g., `testisso.py`) to enforce tight timing.[^2]
3. **SSH tunnel lifecycle in Streamlit**
    - Problem: Streamlit reruns the entire script on each interaction, causing tunnels to be repeatedly opened, left dangling, or reported as “already started.”[^2]
    - Solution: Iterative debugging led to using `st.session_state` plus explicit “is active?” checks so the tunnel survives UI reruns without spawning duplicates.[^2]
4. **Streamlit Cloud’s ephemeral filesystem and database choice**
    - Problem: Local SQLite would be wiped on each deployment restart; storing user data on the Streamlit instance wasn’t viable.[^2]
    - Solution: Move to remote MySQL hosted on Krystal and reach it via SSH tunnel, voluntarily accepting extra network complexity for persistence and control.[^3][^2]
5. **Function signature refactors and missing call-site updates**
    - Problem: Changing a function like `generate_target_audio` without updating all callers caused runtime errors, which the LLM did not catch.[^2]
    - Solution: Human spotted the errors via test runs and pushed for a post-mortem that documented the failure mode and recommended static checks for future work.[^2]
6. **LLM forgetfulness under long context**
    - Problem: Over a 43,000-line log, the model repeatedly forgot details like “use `espeak`, not `espeak-ng`”, “activate the venv first”, and earlier utility scripts, leading to reinvention and corrections.[^2]
    - Solution: The developer started asking for explicit checklists, centralized docs, and repeated reminders to partially counteract the context-window amnesia.[^2]
7. **Response-time degradation**
    - Problem: As context grew from tens of thousands to over a million characters, each response started taking minutes, stalling development flow.[^2]
    - Solution: Work shifted towards larger, more self-contained tasks in each prompt (e.g., “implement this whole feature and describe tests”) to amortize the latency.[^2]

#### Claude’s role at each stage

- **Early local tool phase:** All Python code and scripts (practice app, filters, wordlist cleaning) were generated by Claude, while the human ran commands, validated outputs, and corrected mistakes.[^2]
- **Streamlit app inception:** Claude scaffolded the Streamlit UI, state handling, audio widgets, and basic layout; the human tweaked UX and validated that the flow felt pedagogically sound.[^1][^2]
- **Feature growth (multi-language, Listen First, built-in materials):** Claude wrote the the code and the large bulk of the documentation and performed content manipulation (creating cleaned text files, IPA-enriched resources), while the human chose language sets, curated materials, and tested language quality.[^2]
- **Infrastructure \& security:** Claude proposed and implemented Argon2id, SSH tunneling, and schema designs, with the human deciding on hosting provider, cost envelope, and acceptable complexity.[^3][^2]
- **Stabilization:** The human increasingly acted as QA lead and product owner—catching refactor bugs, noticing forgotten constraints, and insisting on coherent documentation and naming, while Claude iterated on fixes.[^2]

### Technical Insights

#### Major technology choices and rationale

1. **Streamlit as the web framework**
    - Rationale: Very fast to go from script to app, purely in Python, with built-in widgets for audio recording, forms, and layout.[^2]
    - Trade-off: Less control than a custom frontend, but speed and simplicity matched the “build a working tool quickly” goal.[^2]
2. **MySQL on external host (Krystal) + SSH tunnel**
    - Rationale: Avoid Streamlit’s ephemeral filesystem and vendor lock-in, and keep full control over schema, performance, and backups at a low monthly cost.[^3][^2]
    - Trade-off: Introduced complexity around SSH keys, tunnels, and connection pooling.[^2]
3. **Speech stack: Whisper + eSpeak NG + Google Cloud TTS**
    - Whisper: For multi-language ASR and text capture of user recordings.[^2]
    - eSpeak NG: To extract IPA/eIPA phonemes for both the target and recognized speech, supporting detailed segment-level comparison.[^2]
    - Google Cloud TTS: To provide natural target audio in each supported language, overcoming eSpeak’s robotic sound.[^3][^2]
4. **Authentication and security: custom scheme + Argon2id**
    - Rationale: Start with a simple but strong auth model (hashed passwords, sessions) rather than wiring in OAuth providers too early.[^2]
    - Argon2id chosen for password hashing strength and future-proofing against GPU attacks, as documented in the security notes.[^2]
5. **File-based content library plus generator scripts**
    - Language materials (words, phrases, stories) live as text files, with helper scripts to normalize, de-duplicate, and add IPA/translations.[^2]
    - This keeps content editing straightforward (just edit text), while allowing automatic ingestion into the app.[^2]

#### Three biggest technical challenges and detailed solutions

1. **SSH tunnel + Streamlit reruns**
    - Challenge: Each Streamlit interaction re-executes the script, so naive tunnel creation either leaked connections or errored on “already started.”[^2]
    - Approach:
        - Write small, standalone test scripts to open and close SSH tunnels outside Streamlit, validating keys and host config.[^2]
        - Introduce an application-level “connection manager” that uses `st.session_state` to persist a single tunnel instance, checking health before reuse.[^2]
    - Outcome: Stable, encrypted connection to MySQL that survives UI reruns without manual restarts.[^2]
2. **Short-word recognition and Whisper hallucinations**
    - Challenge: Very short items like isso were misrecognized due to silence padding and model biases, undermining pronunciation scoring.[^2]
    - Approach:
        - Create dedicated test harness scripts (e.g., `testisso.py`) with tuned recording durations and immediate speaking instructions.[^2]
        - In the app, shorten default recording windows for single words, and provide on-screen coaching (“press, speak immediately, stop”).[^2]
        - Experiment with Whisper parameters (e.g., temperature) and, when needed, treat suspicious transcriptions with caution in scoring.[^2]
    - Outcome: Dramatically fewer absurd recognitions and more reliable feedback for short items.[^2]
3. **Managing long-running, high-context development with an LLM**
    - Challenge: Over hundreds of turns, Claude forgot binary names, environment setup, and previously created utilities, and response times degraded.[^2]
    - Approach:
        - Push for explicit checklists (“remember: `espeak`, not `espeak-ng`; always activate venv”) and meta-instructions for future prompts.[^2]
        - Capture stable decisions (e.g., versioning conventions, file paths) into documentation files that could be re-pasted or referenced.[^2]
        - Shift to larger-grain tasks per prompt to make the minutes-long responses pay off.[^2]
    - Outcome: Still imperfect, but the project stayed on track despite growing friction from context limits.[^2]

#### Code architecture evolution

- **Phase 1: Single-file practice script**

    - A monolithic Python script handled recording, ASR, scoring, and history persistence in JSON, appropriate for a solo CLI tool.[^2]
- **Phase 2: Streamlit monolith with clustered functions**
    - The app logic was pulled into functions (e.g., for audio capture, scoring, display) but still largely in one file, with sections divided by UI panels.[^2]
- **Phase 3: Modularization around responsibilities**
    - Separate modules emerged for language materials, database access, SSH tunnels, and configuration, with the main Streamlit file orchestrating them.[^2]
    - This laid groundwork for future multi-user features by clearly separating per-user data from shared content.[^2]


#### Claude vs human: actionable insights for developers

- **Where Claude excelled**
    - Rapidly scaffolding new modules (e.g., language library integration) with sensible abstractions and docstrings.[^2]
    - Generating boilerplate and repetitive transformations for content files (cleaning, formatting, adding IPA placeholders).[^2]
    - Proposing strong defaults for security (Argon2id, tunnel encryption) that a non-specialist might not pick.[^2]
- **Where human expertise was critical**
    - Catching subtle refactor bugs (function signature mismatches) that slipped past the model.[^2]
    - Steering architecture choices (e.g., “own the MySQL DB on our host, don’t rely on Supabase”) and deciding acceptable complexity.[^3][^2]
    - Managing the LLM’s forgetfulness with checklists and reminders, and noticing when a “solution” was just reinventing previous work.[^2]
    - Providing pedagogical judgment about UI flows and content—what will actually help a learner pronounce better, not just what’s easy to implement.[^1][^2]

### AI Collaboration Insights

#### Prompt types that yielded the best results

- **Concrete, multi-step tasks**
    - Requests like “add a built-in materials library wired to these folders, and update the UI plus tests” produced cohesive changes because constraints and goals were clear.[^2]
- **Context-rich debugging prompts**
    - Pasting full tracebacks and a short summary (“this fails after X, I expected Y”) enabled Claude to suggest precise fixes rather than generic advice.[^2]
- **Meta-prompts about process**
    - Asking for post-mortems or checklists (“explain why this bug happened and how to prevent it next time”) generated reusable knowledge, not just one-off patches.[^2]


#### When Claude made mistakes and how they were caught

1. **Binary name and environment mishaps**
    - Before: Claude repeatedly proposed commands using `espeak-ng` or installed packages without activating the venv.[^2]
    - After: Human ran commands, saw “command not found” or wrong environment effects, and pushed back explicitly, forcing corrections and new habits.[^2]
2. **Function signature changes**
    - Before: Claude refactored a function’s arguments but forgot to update all callers, leading to runtime errors.[^2]
    - After: Human tests surfaced the error; a follow-up session produced a post-mortem and consistent refactor.[^2]
3. **Overconfident API assumptions**
    - Before: Claude insisted an API key could be used with the Google Cloud TTS client library.[^3][^2]
    - After: Actual attempts failed; documentation clarified that API keys weren’t supported with that client, prompting a switch to raw REST calls.[^3]
4. **Reinvented scripts**
    - Before: Utility scripts for version bumping or content generation were forgotten, and similar tools were written again.[^2]
    - After: Human recognized duplication and began asking for indexes or reminding Claude explicitly of previous tools.[^2]

#### How the developer steered Claude effectively

- **Firm but specific corrections**
    - Instead of vague “that’s wrong”, the developer said things like “it’s `espeak`, not `espeak-ng`, and we must remember the venv,” which updated not just the current answer but the pattern.[^2]
- **Clarifying identity and skill level**
    - Correcting the “non-programmer” assumption helped Claude adjust explanations and not oversimplify or misrepresent the developer’s background.[^2]
- **Requesting rationale and options, not just code**
    - Asking for trade-off analyses (e.g., Supabase vs self-hosted MySQL) got more thoughtful responses and let the human make informed decisions.[^3][^2]


#### What this reveals about effective AI pair programming

1. **AI is a fast, error-prone senior junior**
    - Capable of writing large amounts of code and documentation, but prone to confident mistakes and forgetfulness, requiring human oversight.[^2]
2. **Prompt design is part of the architecture**
    - Good prompts structured work into reviewable chunks, while vague prompts led to partial or misaligned implementations.[^2]
3. **Documentation and checklists are for the AI as much as for humans**
    - PROJECT_CHECKLIST-like prompts and persistent docs compensate for LLM amnesia over long sessions.[^2]
4. **The human is the safety net and product owner**
    - Catching refactors, aligning with user goals, and making architectural trade-offs are not things the model can safely own alone.[^2]

### Efficiency Analysis

#### Time breakdown (approximate)

Based on the transcript and later reflections, a reasonable breakdown of the ~80 hours is:[^2]

- Setup and initial local practice app: ~10–15 hours (environment, eSpeak NG, first CLI tool).[^2]
- Core Streamlit app and single-language workflow: ~15–20 hours.[^2]
- Multi-language expansion and content generation: ~10–15 hours.[^2]
- Infrastructure (MySQL, SSH tunnel, security): ~20 hours.[^3][^2]
- Debugging, polishing, documentation, and deployment: ~15–20 hours.[^2]


#### Where AI provided 2×, 5×, or 10× speedups

- **2×–3×:**
    - Routine debugging once a clear traceback was provided; Claude could propose plausible fixes faster than manually searching docs.[^2]
    - Writing detailed docs and guides, which are traditionally time-consuming for solo developers.[^2]
- **5×:**
    - Multi-language content restructuring: cleaning, reformatting, and generating IPA-enhanced lists across hundreds of entries.[^2]
    - Rapid refactors of the Streamlit UI when requirements changed (e.g., adding Listen First and results sections).[^2]
- **10×:**
    - Building the initial working app: going from zero to a usable pronunciation trainer in roughly a day of focused work, which would typically take weeks for a solo dev unfamiliar with the stack.[^2]
    - Implementing the built-in materials library in minutes instead of the days originally estimated for a human working alone.[^2]


#### Where AI didn’t help or slowed things down

- **Long-context forgetfulness**
    - Repeated corrections about the same issues (binary names, venv, scripts) turned into a tax on progress.[^2]
- **Response-time degradation**
    - Minutes-long responses near the end of the project meant each interaction had to be “worth it,” discouraging small, quick iterations.[^2]
- **Overconfident wrong turns**
    - Time spent trying API key auth with the wrong client library or relying on git revert in a dirty working tree would likely have been avoided by an experienced human in that niche.[^3][^2]


#### How long this might have taken traditionally

Given the final scope—Streamlit app, six languages, curated content, phoneme-level feedback, MySQL+SSH infrastructure, security, and docs—a conservative traditional estimate for a solo developer new to the stack would be:[^2]

- **Architecture and experimentation:** 2–3 weeks.[^2]
- **Core app and multi-language features:** 3–4 weeks.[^2]
- **Infrastructure and security:** 2–3 weeks.[^3][^2]
- **Debugging, polish, docs, and deployment:** 2–3 weeks.[^2]

That yields on the order of 9–13 weeks (roughly 360–520 hours) for a traditional effort, versus ~80 hours actually spent, implying a **4–6× effective speedup**, even after accounting for slowdowns from LLM forgetfulness and latency.[^2]

---

## Conclusion

This detailed chronicle captures the full arc of Miolingo's development—from initial concept to production deployment with six languages, multi-user support, and comprehensive documentation. Each of these four sections could be expanded into standalone articles with code snippets, screenshots, and specific examples from the Git history.

## References

[^1]: MIOLINGO_DESCRIPTION.md - Project description and overview
[^2]: miolingo-development-sonnet-45.md - Complete development transcript
[^3]: miolingo-google-cloud-manageme-6C3TjmzmSBSL.HD5EI8afw.md - Google Cloud TTS integration notes

