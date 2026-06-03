(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — Practice Session, RECOVERED (UI-first, stubbed)
   ---------------------------------------------------------------------
   Per SPEC-RECOVERY.md. Recovered from the Streamlit source
   (src/ui/practice_tab.py, src/ui/quick_practice_tab.py, src/app.py),
   NOT invented. See spec/docs/practice-session-recovery.md.

   FORM: compact guarded-choice. A port is one summand of a variadic
   choice. Guards use the 2-arg conditional sugar if[c, P] (= if[c,P,nil],
   from discipline.wl). Where two COMPLEMENTARY guards carry DISJOINT
   actions, they are merged by the law
       if[c, A] + if[!c, B] == if[c, A, B]
   into one proper two-armed if (both branches real) — here for `rec`.
   Independent per-port guards (next/prev/capture) stay one-armed; the
   empty/non-empty split keeps its shared ports out front (no duplication).
   No `afforded` (readiness is analysis-only: readyPorts[state]); `view`
   kept. LOAD ORDER: RCA_core.wl, discipline.wl, then this.

   STATE: PS[phrases, pos, rec, res]
     phrases : queue (list)        pos : index (int)
     rec : none | recorded[audio]  res : none | scored[r]

   READY SETS (analysis; readyPorts, not declared):
     PS[{},      _,_,_]            : view, load_material, open_practice, goPractice
     PS[ne,p,none,    none]        : + clear_material, select_item,
                                       recording_made, next†, prev‡
     PS[ne,p,recorded,none]        : + attempt_made, clear_recording
     PS[ne,p,recorded,scored]      : + capture_vocab
       † next iff pos < Length-1   ‡ prev iff pos > 0

   MU-TERM VIEW: buildSystem[call["PS", phrases, pos, rec, res]].
   ===================================================================== *)


(* --- top: always-on view/load + the two CargoHold-pull entries; domain ports
   only when non-empty (shared-port split → one-armed if, no duplication).

   PS reads the store ITSELF now (no pushed snapshot). Two entries reach it:
     • open_practice  — the VISIBLE quick-practice entry (a parameter-less input,
       the user opening the practice-from-vocab picker), then chRead the store and
       choose load_vocab / load_filtered (PSBrowse).
     • goPractice     — the vocab-tab "Practise these" SIGNAL from VS, carrying the
       FILTER only (not the entries); PS pulls the collection fresh and shapes it.
   Both keep their VISIBLE input first (open_practice / goPractice), so the chRead
   is the SECOND action — PS stays visibly-guarded (no initial τ), weak bisim a
   congruence. chRead/goPractice are restricted → τ in mioCore. --- *)
defineAgent["PS", {phrases, pos, rec, res},
  choice[
    precede[label["view", param[sessionView[phrases, pos, rec, res]]],
      call["PS", phrases, pos, rec, res]],
    precede[coLabel["load_material", binding[ps]],
      call["PS", ps, 0, none, none]],
    (* PULL (quick_practice "Load vocabulary"/"Load filtered", quick_practice_tab.py):
       visible open_practice → read CargoHold → PSBrowse picks what to load. *)
    precede[coLabel["open_practice"],
      precede[coLabel["chRead", binding[es]],
        call["PSBrowse", es]]],
    (* SIGNAL (vocab-tab "Practise these"): VS sends goPractice!(filter) — the
       filter only. PS pulls the collection FRESH (chRead) and shapes it with that
       filter. No cached snapshot crosses the boundary — single source of truth
       (ARCHITECTURE.md "Borrowed vs owned data"). *)
    precede[coLabel["goPractice", binding[filter]],
      precede[coLabel["chRead", binding[es]],
        call["PS", practiseList[es, filter], 0, none, none]]],
    if[Length[phrases] > 0,
      call["PSActive", phrases, pos, rec, res]]]]


(* --- after open_practice + chRead: choose what to load from the store.
   load_vocab = the whole collection; load_filtered(q) = the subset. Both shape
   via practiseList (vocab.py:644) into the practice phrase queue. The es read here
   is FRESH (pull-on-use); the loaded queue is a deliberate session snapshot the
   user then practices through (next/prev/record/score). --- *)
defineAgent["PSBrowse", {es},
  choice[
    (* @src quick_practice_tab.py:178 ("Load vocabulary (N)") *)
    precede[coLabel["load_vocab"],
      call["PS", practiseList[es, none], 0, none, none]],
    (* @src quick_practice_tab.py:184 ("Load filtered (N)") *)
    precede[coLabel["load_filtered", binding[q]],
      call["PS", practiseList[es, filterBy[q]], 0, none, none]]]]


(* --- domain ports for a non-empty queue --- *)
defineAgent["PSActive", {phrases, pos, rec, res},
  choice[
    precede[coLabel["clear_material"],
      call["PS", {}, 0, none, none]],
    precede[coLabel["select_item", binding[i]],
      call["PS", phrases, i, none, none]],
    (* two-armed: no recording -> record; recording present -> check / remove *)
    if[rec === none,
      precede[coLabel["recording_made", binding[audio]],
        call["PS", phrases, pos, recorded[audio], none]],
      choice[
        (* BORROWED DATA: scoring's ASR (recognisePhonemes) needs the target
           language, which Helm OWNS. So attempt_made PULLS the (source, target)
           pair fresh as a PREFIX \[LongDash] langRead?(lp), restricted to Helm's
           langRead! in mioCore (an internal tau). No cached language => no
           staleness. See ARCHITECTURE.md "Borrowed vs owned data". The pair is
           passed into evaluate, which uses the target code for the ASR. *)
        precede[coLabel["attempt_made"],
          precede[coLabel["langRead", binding[lp]],
            call["PS", phrases, pos, rec,
              scored[evaluate[targetOf[phrases, pos], rec, lp]]]]],
        precede[coLabel["clear_recording"],
          call["PS", phrases, pos, none, none]]]],
    if[pos < Length[phrases] - 1,
      precede[coLabel["next_item_requested"],
        call["PS", phrases, pos + 1, none, none]]],
    if[pos > 0,
      precede[coLabel["prev_item_requested"],
        call["PS", phrases, pos - 1, none, none]]],
    (* capture_vocab relays to VocabStore on vAdd (restricted in MioCore).
       NB — modelling artifact, NOT a behaviour to implement: this is a precede
       chain capture_vocab . vAdd! . PS, so between the capture and the vAdd
       emit, PS is mid-handoff and offers no `view` (the pSView panel momentarily
       disappears in the simulator until the vAdd tau fires). An L3 implementation
       must treat capture-and-relay as ATOMIC — no view flicker. The split exists
       only because CCS makes the synchronous handoff explicit as two events. *)
    if[res =!= none,
      precede[coLabel["capture_vocab", binding[word]],
        precede[label["vAdd", param[word]],
          call["PS", phrases, pos, rec, res]]]]]]
