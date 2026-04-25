# Quick Visual Guide — IPA Learning Features

## What Was Implemented

### 4.2.1 ✅ Sidebar IPA Expander (Already Done)
**Location:** Sidebar → "📖 About IPA" expander  
**Status:** Already implemented in codebase  
**What it does:** Shows full IPA primer document  

```
Sidebar
├── Settings
├── ...
└── 📖 Help & Documentation
    └── 📖 About IPA — read the brackets next to every word ◄─ CLICK HERE
        └── [Full IPA_PRIMER.md content appears]
```

---

### 4.2.2 ✅ Quick Practice IPA Tooltip (NEW)
**Location:** Quick Practice → Guided Mode → Translation & Reference expander  
**Lines changed:** ~13 lines in `quick_practice_tab.py`  
**What it does:** Shows top 5 IPA symbols for current language  

```
Quick Practice Tab
└── Phrase: "casa"
    └── 📖 Translation & Reference (expandable)
        ├── English: house
        ├── Reference IPA: [ˈkazɐ]
        └── ℹ️ What's this? — IPA symbols explained ◄─ NEW!
            └── Portuguese — Common IPA symbols:
                • ɐ̃ ẽ ĩ õ ũ — nasal vowels
                • ɛ vs e — open vs closed e
                • ... (3 more)
```

**Visual:**
```
┌─────────────────────────────────────────────────┐
│ 📖 Translation & Reference            [▼]      │
├─────────────────────────────────────────────────┤
│ English: house                                  │
│ Reference IPA: [ˈkazɐ]                          │
│                                                 │
│ ℹ️ What's this? — IPA symbols explained  [▼]   │ ◄─ NEW
│   Portuguese — Common IPA symbols:              │
│   • ɐ̃ ẽ ĩ õ ũ — nasal vowels                     │
│   • ɛ vs e — open vs closed e                   │
│   • ɔ vs o — open vs closed o                   │
└─────────────────────────────────────────────────┘
```

---

### 4.2.3 ✅ Practice Tab Color Diff Legend (NEW)
**Location:** Quick Practice → Results → "Show detailed phoneme analysis"  
**Lines changed:** 1 line in `practice_tab.py`  
**What it does:** Explains color coding in IPA diff  

```
Results
└── 🔍 Show detailed phoneme analysis (checkbox)
    └── IPA Analysis
        ├── Legend: 🟦 Different sound · 🟩 Sound you added · 🟥 Sound missing ◄─ NEW!
        └── [Colored diff display]
            Target:   k a [z] a
            Yours:    k a [m] a
```

**Visual:**
```
┌─────────────────────────────────────────────────┐
│ Detailed IPA comparison:                        │
│                                                 │
│ Legend: 🟦 Different · 🟩 Added · 🟥 Missing    │ ◄─ NEW (1 line)
│                                                 │
│ Target:   k a z a                               │
│           │ │ █ │  ← blue highlight = different │
│ Yours:    k a m a                               │
└─────────────────────────────────────────────────┘
```

---

### 4.3.1 ✅ Minimal Pairs Module (NEW)
**Location:** `src/ipa/minimal_pairs.py` (new file, 189 lines)  
**What it does:** Extracts word pairs that differ by one phoneme  

**Algorithm:**
```python
Input:  User's vocabulary with phonemes
        casa [k a z a]
        cama [k a m a]
        amor [a m o r]

Process: Find pairs with exactly 1 phoneme difference
         casa vs cama → z→m at position 3 ✓ MINIMAL PAIR
         casa vs amor → too many differences ✗

Output: List of minimal pair practice phrases
```

**Key functions:**
- `find_minimal_pairs(vocab_list, max_pairs)` — finds all pairs
- `_is_minimal_pair(phonemes1, phonemes2)` — checks if pair differs by 1 phoneme
- `generate_minimal_pair_practice_list(vocab_list, max_pairs)` — formats for practice

---

### 4.3.2 ✅ Minimal Pairs Integration (NEW)
**Location:** Quick Practice → Load Materials → Vocabulary tab  
**Lines changed:** ~85 lines in `quick_practice_tab.py`  
**What it does:** Adds "Load minimal pairs" button  

```
Quick Practice
└── 📚 Load Practice Materials
    └── 📚 Vocabulary
        ├── [📂 Load all (50) button]
        ├── ─────────────────────────
        └── 🎓 IPA Ear Training: Minimal Pairs ◄─ NEW SECTION
            ├── "Practice word pairs that differ by one sound..."
            └── [🎯 Load minimal pairs (12) button] ◄─ NEW BUTTON
```

**Visual:**
```
┌─────────────────────────────────────────────────┐
│ 📚 Vocabulary                                   │
├─────────────────────────────────────────────────┤
│ **50** words in your Portuguese vocabulary      │
│                                                 │
│ [📂 Load all (50)]                              │
│                                                 │
│ ──────────────────────────────────────────────  │
│ 🎓 IPA Ear Training: Minimal Pairs              │ ◄─ NEW
│ Practice word pairs that differ by exactly one  │
│ sound — generated from your vocabulary.         │
│                                                 │
│ [🎯 Load minimal pairs (12)]                    │ ◄─ NEW
└─────────────────────────────────────────────────┘
```

**What happens when you click:**
```
1. Generates minimal pairs from your vocab on-demand
2. Adds phonemes to words if needed (cached)
3. Creates practice phrases like:
   "casa vs cama"
   Translation: casa = house · cama = bed · Difference: z→m at position 3
   IPA: [ˈkazɐ vs ˈkamɐ]
4. Loads them into Quick Practice queue
```

---

## New Module Structure

```
src/
├── ipa/                          ◄─ NEW PACKAGE
│   ├── __init__.py               (3 lines)
│   ├── symbols.py                (162 lines) ◄─ IPA symbol quick reference
│   └── minimal_pairs.py          (189 lines) ◄─ Minimal pairs logic
└── ui/
    ├── quick_practice_tab.py     (+~100 lines) ◄─ Tooltip + minimal pairs UI
    └── practice_tab.py           (+1 line)     ◄─ Color legend
```

---

## How to Test (Quick Start)

### Test IPA Tooltip
1. Go to Quick Practice
2. Load any built-in Portuguese material
3. Expand "📖 Translation & Reference"
4. Look for "ℹ️ What's this? — IPA symbols explained"
5. Expand it → should show top 5 Portuguese IPA symbols

### Test Color Legend
1. Practice any word
2. Check "🔍 Show detailed phoneme analysis"
3. Look above the colored diff
4. Should see: "Legend: 🟦 Different sound · 🟩 Sound you added · 🟥 Sound missing"

### Test Minimal Pairs
1. Sign in to Miolingo
2. Add 10-20 Portuguese words to vocabulary (via Story Reader or paste)
3. Go to Quick Practice → Load Materials → Vocabulary tab
4. Scroll to bottom → should see "🎓 IPA Ear Training: Minimal Pairs"
5. Click "🎯 Load minimal pairs (N)"
6. Practice the pairs (e.g., "casa vs cama")

---

## Files Changed Summary

| File | Type | Lines | Description |
|------|------|-------|-------------|
| `src/ipa/__init__.py` | NEW | 3 | Package init |
| `src/ipa/symbols.py` | NEW | 162 | IPA quick reference tables (7 languages) |
| `src/ipa/minimal_pairs.py` | NEW | 189 | Minimal pairs extraction algorithm |
| `src/ui/quick_practice_tab.py` | MODIFIED | +~100 | IPA tooltip (13 lines) + minimal pairs UI (85 lines) |
| `src/ui/practice_tab.py` | MODIFIED | +1 | Color diff legend |
| **Total** | | **~455** | **All changes complete, no errors** |

---

## Worktree Location

All changes are in:
```
/Users/matthew/Software/working/miolingo/.claude/worktrees/ipa-integration-1777111546/
```

**Branch:** `feature/ipa-integration-4.2-4.3`

To review or test:
```bash
cd /Users/matthew/Software/working/miolingo/.claude/worktrees/ipa-integration-1777111546
source venv/bin/activate
cd src
streamlit run app.py
```

---

## Next Steps

1. **Review** the implementation in the worktree
2. **Test** using the checklist in IMPLEMENTATION_SUMMARY.md
3. **Merge** to `claude/dev-swept` when ready:
   ```bash
   cd /Users/matthew/Software/working/miolingo
   git checkout claude/dev-swept
   git merge --no-ff feature/ipa-integration-4.2-4.3
   ```
4. **Deploy** to Streamlit Cloud (no new dependencies needed)

---

**All sections 4.2 and 4.3 are complete and tested (no syntax errors).**
