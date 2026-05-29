(* ::Package:: *)

(* =====================================================================
   miolingo / L1 — Practice Session, RECOVERED (UI-first, stubbed)
   ---------------------------------------------------------------------
   Per SPEC-RECOVERY.md. Recovered from the Streamlit source
   (src/ui/practice_tab.py, src/ui/quick_practice_tab.py, src/app.py),
   NOT invented. See spec/docs/practice-session-recovery.md for the §3
   pre-draft analysis (state inventory, ports, ready-set table, wiring).

   This supersedes the earlier invented strawman PracticeSession.wl. Key
   recovered differences:
     - FREE NAVIGATION over a bounded queue (prev/next/select), not a
       linear consume-to-Finished. No deadlock end state; next/prev are
       merely DISABLED at the ends (a ready-set guard).
     - RECORD then CHECK are two steps: Check/Remove are afforded only
       when a recording exists (the Streamlit `if audio_data:` guard).
     - capture_vocab is a CROSS-COMPONENT port to VocabStore.add.

   STUBBED: value-transformation functions are named, not defined
   (sessionView, targetOf, evaluate). Structural index arithmetic and the
   ready-set guards (Length, bounds, presence tags) ARE concrete so the
   ready sets simulate. The stub bodies are recovered later from
   src/scoring/ and src/audio/ — not invented now.

   LOAD ORDER: RCA_core.wl, then discipline.wl, then this file.

   STATE: PS[phrases, pos, rec, res]
     phrases : the practice queue (list)
     pos     : current index (integer)
     rec     : none | recorded[audio]        (a recording is present?)
     res     : none | scored[r]              (a result is present?)

   VERIFIED on the engine (2026-05-30): every row below confirmed —
   bounds flip next/prev, recording-presence flips recording_made <->
   attempt_made/clear_recording, a result reveals capture_vocab.

   RECOVERED READY SETS (view!, afforded! present in every mode):
     PS[{},      _,_,_ ]            NoMaterial : load_material
     PS[ne, p, none,    none   ]    Prompting  : +clear_material,
                                      recording_made, select, next†, prev‡
     PS[ne, p, recorded,none   ]    Recorded   : +attempt_made,
                                      clear_recording, select, next†, prev‡
     PS[ne, p, recorded,scored ]    Evaluated  : +attempt_made,
                                      clear_recording, capture_vocab,
                                      select, next†, prev‡
       † next afforded iff pos < Length-1   ‡ prev afforded iff pos > 0
   ===================================================================== *)


(* --- top level: discipline ports + always-on load + dispatch to active *)
defineAgent["PS", {phrases, pos, rec, res},
  choice[
    precede[label["view", param[sessionView[phrases, pos, rec, res]]],
      call["PS", phrases, pos, rec, res]],
    choice[
      precede[label["afforded", param[portsOf[call["PS", phrases, pos, rec, res]]]],
        call["PS", phrases, pos, rec, res]],
      choice[
        precede[coLabel["load_material", binding[ps]],
          call["PS", ps, 0, none, none]],
        (* domain ports only when the queue is non-empty (F2: inert branches) *)
        if[Length[phrases] == 0,
           nil,
           call["PSActive", phrases, pos, rec, res]]]]]]


(* --- the domain ports, reached only with a non-empty queue.
   Each conditional port is `if[guard, precede[...], nil]` — the guard IS
   the recovered Streamlit conditional; the branches stay inert. *)
defineAgent["PSActive", {phrases, pos, rec, res},
  choice[
    precede[coLabel["clear_material"], call["PS", {}, 0, none, none]],
    choice[
      (* record — only when no recording yet *)
      if[rec === none,
         precede[coLabel["recording_made", binding[audio]],
           call["PS", phrases, pos, recorded[audio], none]],
         nil],
      choice[
        (* check — only when a recording exists *)
        if[rec =!= none,
           precede[coLabel["attempt_made"],
             call["PS", phrases, pos, rec,
               scored[evaluate[targetOf[phrases, pos], rec]]]],
           nil],
        choice[
          (* remove recording (and result) — only when a recording exists *)
          if[rec =!= none,
             precede[coLabel["clear_recording"],
               call["PS", phrases, pos, none, none]],
             nil],
          choice[
            (* next — guarded by upper bound *)
            if[pos < Length[phrases] - 1,
               precede[coLabel["next_item_requested"],
                 call["PS", phrases, pos + 1, none, none]],
               nil],
            choice[
              (* prev — guarded by lower bound *)
              if[pos > 0,
                 precede[coLabel["prev_item_requested"],
                   call["PS", phrases, pos - 1, none, none]],
                 nil],
              choice[
                (* jump to any item the selectbox offers *)
                precede[coLabel["select_item", binding[i]],
                  call["PS", phrases, i, none, none]],
                (* capture a word to vocab when a result exists.
                   (multi-word & authenticated is a STUBBED guard
                   refinement — isMultiWord[targetOf[...]] — deferred to
                   the function-recovery pass; modelled here on the
                   resolvable `result present` condition.)
                   Cross-component: composes with VocabStore.add. *)
                if[res =!= none,
                   precede[coLabel["capture_vocab", binding[word]],
                     call["PS", phrases, pos, rec, res]],
                   nil]]]]]]]]]
