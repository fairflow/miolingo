# Phrase Selector State Management Fix

**Branch:** `fix/phrase-selector-state`  
**Version:** 7.1.2-fix-phrase-selector  
**Date:** 2 January 2026  
**Status:** ✅ Tested and validated

## Problem Statement

The Quick Practice tab's phrase navigation was experiencing state management conflicts:

1. **Tab-switch position loss**: Navigating to phrase 5, switching to Statistics tab, then back to Quick Practice would reset position to 0
2. **Streamlit dual management warning**: Error message "either let streamlit manage this state component or manage it ourselves; not both"
3. **Widget/button desync**: Next/Previous buttons and dropdown selector weren't staying synchronized
4. **Edit mode concerns**: Position preservation when entering/exiting edit mode

## Root Cause Analysis

### The Dual Management Conflict

The original code used a single key `current_phrase_index` for both:

- **Widget binding**: `st.selectbox(..., key="current_phrase_index")`  
- **Manual state updates**: `st.session_state.current_phrase_index = new_value`

Streamlit's session state model treats keys bound to widgets (via `key=` parameter) as **widget-owned**. When application code also writes to these keys, it creates a conflict - two different parts of the system trying to manage the same state.

### Why Position Was Lost on Tab Switch

The original code had per-tab initialization:

```python
if 'current_phrase_index' not in st.session_state:
    st.session_state.current_phrase_index = 0
```

This check would pass on first entry to the tab, but the dual management conflict meant the state could become inconsistent, leading to unexpected resets.

## Solution Architecture

### Two-Key State Pattern

We separated concerns into two distinct keys:

1. **`qp_phrase_position`** (App State)
   - Owned by application logic
   - Persists across all tab switches
   - Initialized once at app startup
   - Source of truth for current phrase position

2. **`phrase_selector_widget`** (Widget State)  
   - Owned by Streamlit's widget system
   - Only exists when Quick Practice tab is active
   - Bound to selectbox via `key=` parameter
   - Synchronized to app state via callback

### Synchronization Flow

```seq
User selects from dropdown
       ↓
Streamlit updates phrase_selector_widget (automatic)
       ↓
on_change callback fires
       ↓
Callback copies widget value → qp_phrase_position (app state)
       ↓
Log entry added for diagnostics
```

```seq
User clicks Next/Previous button
       ↓
Button handler updates qp_phrase_position (app state)
       ↓
Button handler updates phrase_selector_widget (for sync)
       ↓
Streamlit reruns
       ↓
Selectbox reads from qp_phrase_position via index parameter
       ↓
Dropdown displays correct position
```

## Implementation Details

### 1. Global State Initialization (Lines 1095-1102)

```python
# Initialize at app startup - survives ALL reruns and tab switches
if 'qp_phrase_position' not in st.session_state:
    st.session_state.qp_phrase_position = 0
if 'state_change_log' not in st.session_state:
    st.session_state.state_change_log = []
```

**Why this works**: Session state is a persistent dictionary that survives across reruns. By initializing once at the top level, we ensure the key exists before any tab code runs and never gets reset.

### 2. Selectbox Two-Key Pattern (Lines 3619-3647)

```python
def on_phrase_select():
    """Callback when user selects from dropdown - sync widget → app state"""
    old_pos = st.session_state.qp_phrase_position
    new_pos = st.session_state.phrase_selector_widget
    st.session_state.qp_phrase_position = new_pos
    st.session_state.state_change_log.append(
        f"Dropdown: {old_pos} → {new_pos}"
    )

current_phrase_index = st.selectbox(
    label="Select phrase:",
    options=range(len(phrase_list)),
    format_func=lambda i: f"{i+1}. {phrase_display[:50]}...",
    index=st.session_state.qp_phrase_position,  # READ from app state
    key="phrase_selector_widget",                # WRITE to widget state
    on_change=on_phrase_select                   # SYNC back to app state
)
```

**Key insight**: The `index=` parameter tells Streamlit what to display, reading from our app state. The `key=` parameter tells Streamlit where to write user changes. The `on_change=` callback bridges the gap.

### 3. Navigation Button Synchronization (Lines 3593-3611)

```python
if st.button("⬅️ Previous"):
    if st.session_state.qp_phrase_position > 0:
        st.session_state.qp_phrase_position -= 1
        st.session_state.phrase_selector_widget = st.session_state.qp_phrase_position
        st.session_state.state_change_log.append(f"Prev button: {old} → {new}")
        st.rerun()
```

**Why update both**: When buttons change position, we must update both the app state (so our logic knows) AND the widget state (so the dropdown UI reflects the change on next rerun).

### 4. Material Loading Reset (Lines 3237, 3473, 3542)

```python
# When loading new material or clearing, reset BOTH states
st.session_state.qp_phrase_position = 0
st.session_state.phrase_selector_widget = 0
st.session_state.state_change_log.append("Load builtin: Reset position to 0")
```

**Why reset both**: Ensures dropdown starts at position 0 when new content loads, keeping widget and app state synchronized.

### 5. Diagnostic Infrastructure (Lines 3668-3697)

A collapsible expander displays:

- Current values of both state keys
- Active tab and edit mode status
- Last 10 state changes with sources (dropdown, button, load, etc.)

**Purpose**: Validates that state persists across tab switches by showing no unexpected re-initialization in the change log.

## How Each Design Consideration Is Addressed

### ✅ Tab-Switch State Preservation

**Solution**: Global initialization + persistent app state

- `qp_phrase_position` initialized once at app startup
- Never reset by tab-switching code
- Survives in session_state dictionary across all reruns
- **Test Result**: Position 5 → switch tabs → return → still at position 5 ✅

### ✅ Dual Management Warning Eliminated

**Solution**: Separated widget ownership from app logic

- Widget only manages `phrase_selector_widget` key
- App logic only manages `qp_phrase_position` key
- Synchronization via explicit callbacks, not implicit conflict
- **Test Result**: No Streamlit warnings in console ✅

### ✅ Next/Prev Button Sync with Dropdown

**Solution**: Dual state update pattern

- Buttons update both `qp_phrase_position` AND `phrase_selector_widget`
- Dropdown reads from `qp_phrase_position` via `index=`
- After rerun, dropdown displays correct position
- **Test Result**: Button clicks update dropdown immediately ✅

### ✅ Edit Mode Position Preservation

**Solution**: Orthogonal state management

- Edit mode sets `st.session_state.edit_mode = True`
- Position state (`qp_phrase_position`) remains untouched
- On return to guided mode, selectbox reads from unchanged position
- **Test Result**: Enter edit at phrase 3 → exit → still at phrase 3 ✅

### ✅ Material Loading Reset Behavior

**Solution**: Explicit dual reset on load operations

- Built-in file load, upload, and clear all reset both states to 0
- Diagnostic log confirms reset action
- **Test Result**: Load new file → position resets to 0 ✅

## Testing Validation

All test scenarios passed:

| Test Case | Expected Behavior | Result |
|-----------|-------------------|--------|
| Navigate to phrase 5, switch to Statistics tab, return | Position stays at 5 | ✅ Pass |
| Click Next button 3 times | Dropdown advances through phrases 1→2→3 | ✅ Pass |
| Click Previous button | Dropdown moves back, position decrements | ✅ Pass |
| Select phrase 7 from dropdown | Next/Prev buttons respect new position | ✅ Pass |
| Navigate to phrase 3, enter edit mode, exit | Returns to phrase 3 in guided mode | ✅ Pass |
| Load new material file | Position resets to 0, dropdown shows first phrase | ✅ Pass |
| Check diagnostic log after tab switch | No unexpected re-initialization entries | ✅ Pass |

## Technical Insights

### Why Session State Persists Across Tabs

Streamlit's session state is a **per-user, per-session dictionary** that exists for the entire browser session. Tab switches cause:

- Widget destruction (dropdown disappears when not rendered)
- Widget recreation (dropdown reappears when tab becomes active)

But session state keys persist regardless. The two-key pattern exploits this: app state stays alive even when widget state temporarily doesn't exist.

### Why Callbacks Are Necessary

Streamlit processes widgets before running remaining script code. Without a callback:

```python
# Widget updates phrase_selector_widget (happens first)
# Script code reads it (happens later, after rerun)
```

With callback:

```python
# Widget updates phrase_selector_widget
# Callback immediately runs, copying to qp_phrase_position
# Rest of script sees updated app state
```

This ensures synchronization happens in the same rerun cycle.

## Code Locations

- **Global init**: Lines 1095-1102
- **Tab-specific reference**: Lines 3547-3567
- **Previous button**: Lines 3593-3603
- **Next button**: Lines 3604-3611
- **Selectbox + callback**: Lines 3619-3647
- **Diagnostics**: Lines 3668-3697
- **Material load (builtin)**: Line 3237
- **Material load (upload)**: Line 3473
- **Material clear**: Line 3542

## Commit Message

```git
Fix Quick Practice phrase selector state management

Resolves dual state management conflict causing position loss on tab
switches. Implements two-key pattern separating app state from widget
state with explicit synchronization.

Changes:
- Split current_phrase_index into qp_phrase_position (app) and 
  phrase_selector_widget (widget) keys
- Move initialization to global app startup (survives tab switches)
- Add on_change callback to sync dropdown selections to app state
- Update navigation buttons to maintain both states in sync
- Add diagnostic expander showing state values and change log

Tested:
✅ Position persists across tab switches
✅ Next/Prev buttons sync with dropdown
✅ Edit mode preserves position on return
✅ Material loading resets position correctly
✅ No Streamlit dual management warnings

Technical details in docs/dev-docs/PHRASE_SELECTOR_STATE_FIX.md
```

## Future Considerations

This pattern can be applied to other state management scenarios where:

- Widgets need to both display and modify complex app state
- State must survive navigation or tab switches
- Synchronization between UI and logic is critical

The diagnostic infrastructure can be kept (collapsed by default) or removed for production, depending on ongoing debugging needs.

---

**Author**: GitHub Copilot (Claude Sonnet 4.5)  
**Reviewer**: Matthew Fairtlough  
**Documentation**: This file
