(* =====================================================================
   spec/paths.wl — single source of truth for load paths + engine version
   ---------------------------------------------------------------------
   Every test (.wls) and MiolingoSpec.wl Gets THIS FIRST, located relative
   to its own file (so it is correct in any worktree, with no hardcoded
   absolute path to update):

       (* a file IN spec/ *)
       Get[FileNameJoin[{DirectoryName[$InputFileName], "paths.wl"}]];

       (* a test in spec/tests/ *)
       Get[FileNameJoin[{ParentDirectory[DirectoryName[$InputFileName]],
                         "paths.wl"}]];

   It then provides:
     $specDir            this spec directory, derived from THIS file's own
                         location — never hardcode the spec path again
     $rca                the engine path: the $RCA_CORE env var if set,
                         else the canonical checkout. One place; override
                         via the environment (e.g. a different worktree)
     mioGet[file]        Get a spec file by name, relative to $specDir
     loadEngine[]        Get the engine AND assert the checkout is not
                         behind the version this spec requires — a loud
                         failure that replaces the old hand-rolled
                         worktree fallback
     loadRecoveredBase[] discipline.wl + the two Recovered agents, in load
                         order (the common base every consumer loads first)

   DIVERGENCE GUARD ($minEngineSha): the engine (RCA_core.wl) is co-developed
   in a SEPARATE repo. This records the oldest engine commit whose features
   this spec depends on; loadEngine[] aborts if the engine checkout does not
   contain it (instead of silently running against the wrong engine, or
   reaching sideways into a feature worktree as the tests used to). When you
   adopt new engine capability, bump this in the SAME spec PR that uses it —
   that one line is the shared coordinate between the two co-developed repos,
   so neither has to be branched in lockstep with the other.
   ===================================================================== *)

$specDir = DirectoryName[$InputFileName] <> "/";

$rca = With[{e = Environment["RCA_CORE"]},
  If[StringQ[e] && e =!= "", e,
     "/Users/matthew/Projects/private/Mathematica/RCA/RCA_core.wl"]];

(* Oldest engine commit this spec requires — PR #36 (walk + replayTrace),
   which descends from native guard/choice (#33), substVv guard-ground (#34)
   and transNamed[relabel] (#35). Bump when adopting newer engine capability. *)
$minEngineSha = "5bcc031";

mioGet::usage = "mioGet[\"file.wl\"] Gets a spec file by name, relative to $specDir (this spec directory, derived from paths.wl's own location).";
loadEngine::usage = "loadEngine[] Gets the RCA engine ($rca = $RCA_CORE env var, else the canonical checkout) AND asserts (git merge-base --is-ancestor) that the checkout contains $minEngineSha, aborting loudly on divergence. The shared coordinate between the spec and engine repos.";
loadRecoveredBase::usage = "loadRecoveredBase[] loads discipline.wl + the three recovered agents (PracticeSessionRecovered.wl, VocabStoreRecovered.wl, HelmRecovered.wl) in order — the common base every spec consumer loads first (MioCore composes all three).";

mioGet[file_String] := Get[$specDir <> file];

loadEngine[] := Module[{engineDir, res, exit},
  Quiet[Get[$rca]];
  engineDir = DirectoryName[$rca];
  res = RunProcess[{"git", "-C", engineDir,
                    "merge-base", "--is-ancestor", $minEngineSha, "HEAD"}];
  exit = res["ExitCode"];
  Which[
    exit === 0,
      Print["  engine OK: ", engineDir, " contains required ", $minEngineSha],
    exit === 1,
      (Print["*** ENGINE DIVERGENCE ***"];
       Print["    engine checkout at ", engineDir];
       Print["    does NOT contain required commit ", $minEngineSha,
             " (PR #36: walk/replayTrace)."];
       Print["    Update the engine checkout, or point $RCA_CORE at one that",
             " has it. Aborting."];
       Exit[1]),
    True,
      Print["  WARN: could not verify engine version (git exit ", exit, "): ",
            res["StandardError"], " — proceeding unchecked."]
  ]];

loadRecoveredBase[] := (
  mioGet["discipline.wl"];
  mioGet["PracticeSessionRecovered.wl"];
  mioGet["VocabStoreRecovered.wl"];
  mioGet["HelmRecovered.wl"]);   (* third recovered agent; MioCore composes it *)
