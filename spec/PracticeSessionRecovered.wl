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
     PS[{},      _,_,_]            : view, load_material, pLoad
     PS[ne,p,none,    none]        : + clear_material, select_item,
                                       recording_made, next†, prev‡
     PS[ne,p,recorded,none]        : + attempt_made, clear_recording
     PS[ne,p,recorded,scored]      : + capture_vocab
       † next iff pos < Length-1   ‡ prev iff pos > 0

   MU-TERM VIEW: buildSystem[call["PS", phrases, pos, rec, res]].
   ===================================================================== *)


(* --- top: always-on view/load/pLoad; domain ports only when non-empty
   (shared-port split → one-armed if, no duplication) --- *)
defineAgent["PS", {phrases, pos, rec, res},
  choice[
    precede[label["view", param[sessionView[phrases, pos, rec, res]]],
      call["PS", phrases, pos, rec, res]],
    precede[coLabel["load_material", binding[ps]],
      call["PS", ps, 0, none, none]],
    precede[coLabel["pLoad", binding[ps]],
      call["PS", ps, 0, none, none]],
    if[Length[phrases] > 0,
      call["PSActive", phrases, pos, rec, res]]]]


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
        precede[coLabel["attempt_made"],
          call["PS", phrases, pos, rec,
            scored[evaluate[targetOf[phrases, pos], rec]]]],
        precede[coLabel["clear_recording"],
          call["PS", phrases, pos, none, none]]]],
    if[pos < Length[phrases] - 1,
      precede[coLabel["next_item_requested"],
        call["PS", phrases, pos + 1, none, none]]],
    if[pos > 0,
      precede[coLabel["prev_item_requested"],
        call["PS", phrases, pos - 1, none, none]]],
    (* capture_vocab relays to VocabStore on vAdd (restricted in MioCore) *)
    if[res =!= none,
      precede[coLabel["capture_vocab", binding[word]],
        precede[label["vAdd", param[word]],
          call["PS", phrases, pos, rec, res]]]]]]
