# Miolingo UI Testing Checklist

Use this as a prompt or reference when running a browser-based test session with Claude.
Cover every section before writing the report. Tick items off as you go.

---

## Widget State Testing Rule

> For any interactive element with multiple states (toggle, checkbox, radio button, dropdown, selector), test **ALL** states — not just the default.
>
> - **Binary widgets** (on/off, enabled/disabled, checked/unchecked): test both states in every session
> - **Multi-value selectors** (dropdowns, radio groups): test at least 2 distinct values, including one non-default
> - **Why this matters:** an untested state is an untested feature. The CCS framework's port-matching is designed to catch exactly this — but only if the widget is actually clicked.
> - **Grounding:** ISTQB State Transition Testing (Foundation Level, chapter 4); Milner's CCS port matching (already in this project)
>
> *Known miss from v7.1.3 testing:* CCS Testing toggle (enabled/disabled) was never clicked.

---

## Pre-test
- [ ] Note app version (sidebar title, e.g. "Miolingo v7.1.3")
- [ ] Note active TTS engine (sidebar: Text-to-Speech Engine)
- [ ] Note active target language (sidebar: Target Language)
- [ ] Confirm login successful (user shown in sidebar)
- [ ] Count and record any warning banners visible on load (yellow/orange boxes)

---

## Quick Practice tab

### Free text entry
- [ ] Enter a single word → TTS audio player appears and plays
- [ ] Enter a multi-word phrase → same checks
- [ ] Check input field border state after submission (should not be red for valid input)
- [ ] Check translation is shown (if source ≠ target language)
- [ ] Check IPA is shown (if IPA enabled)

### Recording
- [ ] Click the microphone/record button → recording starts (icon changes)
- [ ] Stop recording → user audio player appears
- [ ] Check score is displayed after recording
- [ ] Check recognised text is displayed and free of trailing punctuation

### Load Practice Materials — Built-in Library
- [ ] Expand the "Load Practice Materials" section
- [ ] Select "Built-in Library"
- [ ] Change Category dropdown → file list updates
- [ ] Change File dropdown → item count and preview update
- [ ] Expand "Preview first 3 items" → shows correctly
- [ ] Click "Load This File" → Previous/Next buttons become active

### Load Practice Materials — Upload File
- [ ] Select "Upload File" option
- [ ] Attempt to upload a `.txt` file

### Navigation (after loading a file)
- [ ] Click Next → phrase advances
- [ ] Click Previous → phrase retreats
- [ ] Verify Previous is disabled at first phrase
- [ ] Verify Next is disabled at last phrase

### Sidebar settings affecting Quick Practice
- [ ] Toggle "Slow speech" → re-generate audio and confirm duration changes
- [ ] Switch TTS engine → confirm audio is regenerated

---

## Story Reader tab

### Scene selection
- [ ] Open "Select a scene to read" dropdown
- [ ] Check **all** scene names for missing accented characters (e.g. é, ã, ô, ç)
- [ ] Note which scenes are affected

### Reading modes
- [ ] **Full Story** — select and scroll; check accents in body text
- [ ] **Scene by Scene** — select and scroll; check accents in body text
- [ ] **Practice Mode** — select and check that phrase-by-phrase navigation works

### Display options
- [ ] Toggle "Show English translations" → translations appear/disappear
- [ ] Toggle "Show IPA" → IPA appears/disappears

### Navigation (Scene by Scene / Practice Mode)
- [ ] Previous / Next scene navigation works
- [ ] Audio playback available per phrase (if expected)

---

## Statistics tab

- [ ] Confirm summary metrics are shown (Total Practices, Total Perfect, Overall Avg, Recent Avg)
- [ ] Check whether **charts or graphs** are rendered (bar chart, trend line, etc.)
- [ ] Check whether **per-language breakdown** is shown
- [ ] Check whether **date range filter** is available

---

## History tab

- [ ] Expand at least 3 sessions
- [ ] Check session with **exactly 1 practice** — confirm text reads "1 practice" not "1 practices"
- [ ] Check "Recognised" text field for **trailing punctuation** (e.g. "obrigada!" — should be "obrigada")
- [ ] Scroll to bottom — confirm all sessions load correctly

---

## Sidebar

### Connection Info (dev panel — note, do not re-report known items)
- [ ] Expand Connection Info
- [ ] Note: SQL connection string, MySQL ID and tunnel info are **intentional** in test mode — do not report as Critical security bug
- [ ] Check "Reconnect" button is present (expected)

### Language settings
- [ ] Change **Source Language** → confirm the UI updates
- [ ] Change **Target Language** → confirm the tab heading, TTS, and materials update
- [ ] Click **Switch translation direction** → Source and Target values swap AND direction label updates
- [ ] Click **Switch translation direction** again → returns to original direction (round-trip test)

### TTS settings
- [ ] Change TTS Engine (if multiple options available) → confirm new audio is generated with changed voice
- [ ] Toggle Slow speech **on** → audio duration increases
- [ ] Toggle Slow speech **off** → audio duration returns to normal

### Scoring Algorithm
- [ ] Open Scoring Algorithm dropdown → confirm options are visible (e.g. edit_distance)
- [ ] Select a non-default algorithm if available → note for comparison; revert after

### Audio Processing
- [ ] Confirm Silence Trim Threshold slider is present and draggable
- [ ] Toggle **Use WAV audio format** on → confirm no error
- [ ] Toggle **Use WAV audio format** off → confirm no error (round-trip)
- [ ] Click **Save Settings** → confirm no error displayed

### CCS Testing (dev panel)
- [ ] Scroll to bottom of sidebar — confirm 🧪 CCS Testing section is present
- [ ] Click to **enable** CCS Testing → confirm validation controls appear in sidebar (Current State, port matching display)
- [ ] Verify "Current State" display shows Mode, Visible Elements, Capabilities
- [ ] Click **✅ Matches** → confirm it registers
- [ ] Click **❌ Mismatch** → confirm notes field appears and accepts text
- [ ] Click to **disable** CCS Testing → confirm validation controls disappear
- [ ] Confirm normal app functionality is unaffected after disabling

---

## Cross-cutting checks

- [ ] Count total warning/info banners on the page — note exact text and quantity of each
- [ ] Reload the page (after noting current count) — check whether banners duplicate
- [ ] Note any **red-bordered input fields** that have no accompanying error message
- [ ] Check whether internal state messages appear (e.g. "State changed: …") — note as Warning, not Bug, given debug mode
- [ ] Check page title in browser tab matches expected content

---

## Report format reminder

Each issue: **Type** (Warning | Bug | Missing Feature) + **Severity** (Critical | High | Medium | Low)

In debug mode, lower severity of debug-message leakage by one level vs production.

```
### ISSUE-N [Type] [Severity] — Short title

**Steps to reproduce:**
1.
2.

**Expected:** ...
**Actual:** ...
**Notes:** ...
```
