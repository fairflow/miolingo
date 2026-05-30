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
     - RECORD then CHECK are two steps: Check/Remove are available only
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

   RECOVERED READY SETS (analysis only; not explicit channels in the process):
     PS[{},      _,_,_ ]            NoMaterial : load_material
     PS[ne, p, none,    none   ]    Prompting  : +clear_material,
                                      recording_made, select, next†, prev‡
     PS[ne, p, recorded,none   ]    Recorded   : +attempt_made,
                                      clear_recording, select, next†, prev‡
     PS[ne, p, recorded,scored ]    Evaluated  : +attempt_made,
                                      clear_recording, capture_vocab,
                                      select, next†, prev‡
       † next available iff pos < Length-1   ‡ prev available iff pos > 0
   ===================================================================== *)


(* --- top level: view + always-on load + dispatch to active --- *)
defineAgent["PS", {phrases, pos, rec, res},
  if[Length[phrases] == 0,
    choice[
      precede[label["view", param[sessionView[phrases, pos, rec, res]]],
        call["PS", phrases, pos, rec, res]],
      choice[
        precede[coLabel["load_material", binding[ps]],
          call["PS", ps, 0, none, none]],
        (* CROSS-COMPONENT (composition refinement): receive a phrase list
           relayed from VocabStore's "Practise these" on internal channel
           pLoad. Restricted in the MioCore composition. *)
        precede[coLabel["pLoad", binding[ps]],
          call["PS", ps, 0, none, none]]]],
    choice[
      precede[label["view", param[sessionView[phrases, pos, rec, res]]],
        call["PS", phrases, pos, rec, res]],
      choice[
        precede[coLabel["load_material", binding[ps]],
          call["PS", ps, 0, none, none]],
        choice[
          (* CROSS-COMPONENT (composition refinement): receive a phrase list
             relayed from VocabStore's "Practise these" on internal channel
             pLoad. Restricted in the MioCore composition. *)
          precede[coLabel["pLoad", binding[ps]],
            call["PS", ps, 0, none, none]],
          call["PSActive", phrases, pos, rec, res]]])])]


(* --- the domain ports, reached only with a non-empty queue.
   Presented in guard-partitioned normal form: no afforded channel, and
   no degenerate if[guard, P, nil] branches in the written spec. *)
defineAgent["PSActive", {phrases, pos, rec, res},
  if[rec === none,
    if[pos < Length[phrases] - 1,
      if[pos > 0,
        choice[
          precede[coLabel["clear_material"],
            call["PS", {}, 0, none, none]],
          choice[
            precede[coLabel["recording_made", binding[audio]],
              call["PS", phrases, pos, recorded[audio], none]],
            choice[
              precede[coLabel["next_item_requested"],
                call["PS", phrases, pos + 1, none, none]],
              choice[
                precede[coLabel["prev_item_requested"],
                  call["PS", phrases, pos - 1, none, none]],
                precede[coLabel["select_item", binding[i]],
                  call["PS", phrases, i, none, none]]]]]],
        choice[
          precede[coLabel["clear_material"],
            call["PS", {}, 0, none, none]],
          choice[
            precede[coLabel["recording_made", binding[audio]],
              call["PS", phrases, pos, recorded[audio], none]],
            choice[
              precede[coLabel["next_item_requested"],
                call["PS", phrases, pos + 1, none, none]],
              precede[coLabel["select_item", binding[i]],
                call["PS", phrases, i, none, none]]]]],
      if[pos > 0,
        choice[
          precede[coLabel["clear_material"],
            call["PS", {}, 0, none, none]],
          choice[
            precede[coLabel["recording_made", binding[audio]],
              call["PS", phrases, pos, recorded[audio], none]],
            choice[
              precede[coLabel["prev_item_requested"],
                call["PS", phrases, pos - 1, none, none]],
              precede[coLabel["select_item", binding[i]],
                call["PS", phrases, i, none, none]]]]],
        choice[
          precede[coLabel["clear_material"],
            call["PS", {}, 0, none, none]],
          choice[
            precede[coLabel["recording_made", binding[audio]],
              call["PS", phrases, pos, recorded[audio], none]],
            precede[coLabel["select_item", binding[i]],
              call["PS", phrases, i, none, none]]]])),
    if[res === none,
      if[pos < Length[phrases] - 1,
        if[pos > 0,
          choice[
            precede[coLabel["clear_material"],
              call["PS", {}, 0, none, none]],
            choice[
              precede[coLabel["attempt_made"],
                call["PS", phrases, pos, rec,
                  scored[evaluate[targetOf[phrases, pos], rec]]]],
              choice[
                precede[coLabel["clear_recording"],
                  call["PS", phrases, pos, none, none]],
                choice[
                  precede[coLabel["next_item_requested"],
                    call["PS", phrases, pos + 1, none, none]],
                  choice[
                    precede[coLabel["prev_item_requested"],
                      call["PS", phrases, pos - 1, none, none]],
                    precede[coLabel["select_item", binding[i]],
                      call["PS", phrases, i, none, none]]]]]],
          choice[
            precede[coLabel["clear_material"],
              call["PS", {}, 0, none, none]],
            choice[
              precede[coLabel["attempt_made"],
                call["PS", phrases, pos, rec,
                  scored[evaluate[targetOf[phrases, pos], rec]]]],
              choice[
                precede[coLabel["clear_recording"],
                  call["PS", phrases, pos, none, none]],
                choice[
                  precede[coLabel["next_item_requested"],
                    call["PS", phrases, pos + 1, none, none]],
                  precede[coLabel["select_item", binding[i]],
                    call["PS", phrases, i, none, none]]]]]),
        if[pos > 0,
          choice[
            precede[coLabel["clear_material"],
              call["PS", {}, 0, none, none]],
            choice[
              precede[coLabel["attempt_made"],
                call["PS", phrases, pos, rec,
                  scored[evaluate[targetOf[phrases, pos], rec]]]],
              choice[
                precede[coLabel["clear_recording"],
                  call["PS", phrases, pos, none, none]],
                choice[
                  precede[coLabel["prev_item_requested"],
                    call["PS", phrases, pos - 1, none, none]],
                  precede[coLabel["select_item", binding[i]],
                    call["PS", phrases, i, none, none]]]]]),
          choice[
            precede[coLabel["clear_material"],
              call["PS", {}, 0, none, none]],
            choice[
              precede[coLabel["attempt_made"],
                call["PS", phrases, pos, rec,
                  scored[evaluate[targetOf[phrases, pos], rec]]]],
              choice[
                precede[coLabel["clear_recording"],
                  call["PS", phrases, pos, none, none]],
                precede[coLabel["select_item", binding[i]],
                  call["PS", phrases, i, none, none]]]]])),
      if[pos < Length[phrases] - 1,
        if[pos > 0,
          choice[
            precede[coLabel["clear_material"],
              call["PS", {}, 0, none, none]],
            choice[
              precede[coLabel["attempt_made"],
                call["PS", phrases, pos, rec,
                  scored[evaluate[targetOf[phrases, pos], rec]]]],
              choice[
                precede[coLabel["clear_recording"],
                  call["PS", phrases, pos, none, none]],
                choice[
                  precede[coLabel["capture_vocab", binding[word]],
                    precede[label["vAdd", param[word]],
                      call["PS", phrases, pos, rec, res]]],
                  choice[
                    precede[coLabel["next_item_requested"],
                      call["PS", phrases, pos + 1, none, none]],
                    choice[
                      precede[coLabel["prev_item_requested"],
                        call["PS", phrases, pos - 1, none, none]],
                      precede[coLabel["select_item", binding[i]],
                        call["PS", phrases, i, none, none]]]]]]],
          choice[
            precede[coLabel["clear_material"],
              call["PS", {}, 0, none, none]],
            choice[
              precede[coLabel["attempt_made"],
                call["PS", phrases, pos, rec,
                  scored[evaluate[targetOf[phrases, pos], rec]]]],
              choice[
                precede[coLabel["clear_recording"],
                  call["PS", phrases, pos, none, none]],
                choice[
                  precede[coLabel["capture_vocab", binding[word]],
                    precede[label["vAdd", param[word]],
                      call["PS", phrases, pos, rec, res]]],
                  choice[
                    precede[coLabel["next_item_requested"],
                      call["PS", phrases, pos + 1, none, none]],
                    precede[coLabel["select_item", binding[i]],
                      call["PS", phrases, i, none, none]]]]]]),
        if[pos > 0,
          choice[
            precede[coLabel["clear_material"],
              call["PS", {}, 0, none, none]],
            choice[
              precede[coLabel["attempt_made"],
                call["PS", phrases, pos, rec,
                  scored[evaluate[targetOf[phrases, pos], rec]]]],
              choice[
                precede[coLabel["clear_recording"],
                  call["PS", phrases, pos, none, none]],
                choice[
                  precede[coLabel["capture_vocab", binding[word]],
                    precede[label["vAdd", param[word]],
                      call["PS", phrases, pos, rec, res]]],
                  choice[
                    precede[coLabel["prev_item_requested"],
                      call["PS", phrases, pos - 1, none, none]],
                    precede[coLabel["select_item", binding[i]],
                      call["PS", phrases, i, none, none]]]]]]),
          choice[
            precede[coLabel["clear_material"],
              call["PS", {}, 0, none, none]],
            choice[
              precede[coLabel["attempt_made"],
                call["PS", phrases, pos, rec,
                  scored[evaluate[targetOf[phrases, pos], rec]]]],
              choice[
                precede[coLabel["clear_recording"],
                  call["PS", phrases, pos, none, none]],
                choice[
                  precede[coLabel["capture_vocab", binding[word]],
                    precede[label["vAdd", param[word]],
                      call["PS", phrases, pos, rec, res]]],
                  precede[coLabel["select_item", binding[i]],
                    call["PS", phrases, i, none, none]]]]]))))]
