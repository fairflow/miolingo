(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — Practice Session, RECOVERED (UI-first, stubbed)
   ---------------------------------------------------------------------
   Per SPEC-RECOVERY.md. Recovered from the Streamlit source
   (src/ui/practice_tab.py, src/ui/quick_practice_tab.py, src/app.py),
   NOT invented. See spec/docs/practice-session-recovery.md for the §3
   analysis.

   FORM: compact guarded-choice. Each port is ONE summand of a variadic
   choice, guarded by `when[g, ...]` where its availability is state-
   dependent. This is the single source of truth; the guard-partitioned
   ("outer-guard") normal form is a DERIVED view, obtainable by the
   rewrite laws (P+0=P; if[c,P,Q]+R = if[c,P+R,Q+R]) — not hand-authored.

   `afforded` is GONE: readiness is analysis-only, computed on the fly by
   readyPorts[state] (= First/@transNamed), never a channel in the process.
   `view` stays (a real output projection).

   Sugar (from discipline.wl): when[g,P] = if[g,P,nil]; variadic choice
   desugars to binary. LOAD ORDER: RCA_core.wl, discipline.wl, then this.

   STATE: PS[phrases, pos, rec, res]
     phrases : queue (list)        pos : index (int)
     rec : none | recorded[audio]  res : none | scored[r]

   READY SETS (analysis; computed by readyPorts, not declared):
     PS[{},      _,_,_]            : view, load_material, pLoad
     PS[ne,p,none,    none]        : + clear_material, select_item,
                                       recording_made, next†, prev‡
     PS[ne,p,recorded,none]        : + attempt_made, clear_recording
                                       (recording_made drops out)
     PS[ne,p,recorded,scored]      : + capture_vocab
       † next iff pos < Length-1   ‡ prev iff pos > 0

   MU-TERM VIEW: buildSystem[call["PS", phrases, pos, rec, res]] converts
   this equational form to a closed mu-term for navigation.
   ===================================================================== *)


(* --- top: view + always-on load/pLoad; domain ports only when non-empty.
   load_material is the user port; pLoad is the cross-component relay from
   VocabStore (restricted in MioCore). --- *)
defineAgent["PS", {phrases, pos, rec, res},
  choice[
    precede[label["view", param[sessionView[phrases, pos, rec, res]]],
      call["PS", phrases, pos, rec, res]],
    precede[coLabel["load_material", binding[ps]],
      call["PS", ps, 0, none, none]],
    precede[coLabel["pLoad", binding[ps]],
      call["PS", ps, 0, none, none]],
    when[Length[phrases] > 0,
      call["PSActive", phrases, pos, rec, res]]]]


(* --- domain ports for a non-empty queue, one guarded summand each --- *)
defineAgent["PSActive", {phrases, pos, rec, res},
  choice[
    precede[coLabel["clear_material"],
      call["PS", {}, 0, none, none]],
    precede[coLabel["select_item", binding[i]],
      call["PS", phrases, i, none, none]],
    when[rec === none,
      precede[coLabel["recording_made", binding[audio]],
        call["PS", phrases, pos, recorded[audio], none]]],
    when[rec =!= none,
      precede[coLabel["attempt_made"],
        call["PS", phrases, pos, rec,
          scored[evaluate[targetOf[phrases, pos], rec]]]]],
    when[rec =!= none,
      precede[coLabel["clear_recording"],
        call["PS", phrases, pos, none, none]]],
    when[pos < Length[phrases] - 1,
      precede[coLabel["next_item_requested"],
        call["PS", phrases, pos + 1, none, none]]],
    when[pos > 0,
      precede[coLabel["prev_item_requested"],
        call["PS", phrases, pos - 1, none, none]]],
    (* capture_vocab: relays to VocabStore on vAdd (restricted in MioCore) *)
    when[res =!= none,
      precede[coLabel["capture_vocab", binding[word]],
        precede[label["vAdd", param[word]],
          call["PS", phrases, pos, rec, res]]]]]]
