// =====================================================================
// AppModel — the composition root (Swift AppModel analogue). Thin runes
// container: ALL domain logic lives in src/domain/*; this class only wires
// the spec's restricted τ channels as direct calls between $state slices:
//   goPractice  : Vocab signals → PS pulls the collection fresh
//   vocabRead   : reading this.entries at point of use (never cached)
//   vocabUpsert : capture/add writes the table (+ write-through to Dexie)
//   langRead    : borrowing this.helm at point of use (never cached)
// =====================================================================

import * as ps from '../domain/practiceSession.js';
import * as helmFns from '../domain/helm.js';
import * as vocabFns from '../domain/vocabFunctions.js';
import { phrasesFor, type UnifiedDoc } from '../domain/materials.js';
import type { AlignOp, Capture, Phrase, Score, VocabEntry } from '../domain/types.js';
import { attempt, fetchMaterial, tts } from '../oracle/client.js';
import type { AttemptChannel, AttemptResponse } from '../oracle/types.js';
import { db, loadHelm, saveHelm, type VocabRow } from '../store/db.js';

const OP_TO_ALIGN: Record<string, AlignOp> = {
  match: 'equal',
  substitute: 'sub',
  insert: 'ins',
  delete: 'del',
};

/** Project the primary oracle channel into the spec's Score shape. */
export function channelToScore(res: AttemptResponse, ch: AttemptChannel): Score {
  return {
    exactMatch: ch.exact,
    similarity: ch.similarity ?? 0,
    distance: ch.distance ?? 0,
    user: ch.ipa,
    target: res.target_ipa,
    alignment: ch.ops.map((o) => ({
      op: OP_TO_ALIGN[o.kind] ?? 'sub',
      target: o.target,
      user: o.user,
    })),
  };
}

function isSingleWord(text: string): boolean {
  return !/\s/.test(text.trim());
}

const nowIso = (): string => new Date().toISOString();

export class AppModel {
  ps = $state<ps.PS>(ps.initialPS);
  helm = $state<helmFns.Helm>(helmFns.defaultHelm);
  /** VocabTable's owned store for the CURRENT target language (vocabRead
   * reads this fresh; rows carry lang + wall-clock beyond the domain entry). */
  entries = $state<VocabRow[]>([]);
  /** The full dual-channel result of the last scored attempt (display only;
   * lifecycle slaved to ps.res — see #sync). */
  lastAttempt = $state<AttemptResponse | null>(null);
  scoring = $state(false);
  error = $state<string | null>(null);

  async hydrate(): Promise<void> {
    this.helm = await loadHelm(helmFns.defaultHelm);
    await this.reloadEntries();
  }

  async reloadEntries(): Promise<void> {
    try {
      this.entries = await db.vocab.where('lang').equals(this.helm.target).toArray();
    } catch {
      this.entries = [];
    }
  }

  /** Keep lastAttempt's lifecycle slaved to ps.res (one source of gating). */
  #sync(next: ps.PS): void {
    this.ps = next;
    if (next.res === null) this.lastAttempt = null;
  }

  // --- Helm (set_* ports; persisted as a settings row) ------------------
  async setHelm(next: helmFns.Helm): Promise<void> {
    const langChanged = next.target !== this.helm.target;
    this.helm = next;
    await saveHelm($state.snapshot(this.helm) as helmFns.Helm);
    if (langChanged) {
      this.#sync(ps.clearMaterial(this.ps)); // stale-language queue is meaningless
      await this.reloadEntries();
    }
  }

  // --- PS external channels ---------------------------------------------
  loadMaterial(phrases: readonly Phrase[]): void {
    this.#sync(ps.load(this.ps, phrases));
  }

  async loadMaterialFile(path: string): Promise<void> {
    const doc = await fetchMaterial<UnifiedDoc>(path);
    // langRead: borrow source/target fresh from Helm at point of use.
    const source = helmFns.codeOfName(this.helm.source);
    this.loadMaterial(phrasesFor(doc, this.helm.target, source));
  }

  /** goPractice: Vocab signals with a filter; PS pulls the collection fresh
   * via vocabRead (this.entries) — no snapshot crosses the boundary. */
  practiseVocab(filter: string | null = null): void {
    this.loadMaterial(vocabFns.practiseList(this.entries, filter));
  }

  select(i: number): void {
    this.#sync(ps.select(this.ps, i));
  }

  next(): void {
    this.#sync(ps.next(this.ps));
  }

  prev(): void {
    this.#sync(ps.prev(this.ps));
  }

  clearRecording(): void {
    this.#sync(ps.clearRecording(this.ps));
  }

  /** recording_made → attempt_made: hold the take, one oracle round trip,
   * then score + log + auto-capture (perfect single words, as the app). */
  async recordingMade(audio: Blob): Promise<void> {
    if (this.ps.rec !== null) return; // spec guard: re-record requires clear
    this.#sync(ps.recordingMade(this.ps, audio));
    this.scoring = true;
    this.error = null;
    try {
      const res = await attempt({
        audio,
        target: ps.targetText(this.ps),
        lang: this.helm.target, // langRead — never cached in PS
        algorithm: 'weighted_phone',
        whisperModel: this.helm.asrModel,
      });
      this.lastAttempt = res;
      this.ps = ps.attemptMade(this.ps, channelToScore(res, res.comprehensibility));
      await this.#logAttempt(res, 'quick');
      if (res.comprehensibility.exact && isSingleWord(res.target)) {
        const item = ps.currentItem(this.ps);
        this.captureVocab({
          word: res.target,
          translation: item?.translation ?? null,
          ipa: res.target_ipa,
          sourceName: 'practice',
        });
      }
    } catch (e: unknown) {
      this.error = String(e);
      this.#sync(ps.clearRecording(this.ps)); // failed attempt → re-record
    } finally {
      this.scoring = false;
    }
  }

  /** capture_vocab · vocabUpsert — ATOMIC: one synchronous state write, then
   * write-through persistence. The PS slice is untouched (no view flicker). */
  captureVocab(w: Capture | string): void {
    const before = this.entries;
    const after = vocabFns.addEntry(before, w) as VocabEntry[];
    const now = nowIso();
    const key = typeof w === 'string' ? w : w.word;
    const norm = vocabFns.validateWord(key);
    this.entries = after.map((e) => {
      const row = e as VocabRow;
      const touched = norm !== null && e.word === norm.key;
      return {
        ...row,
        lang: row.lang ?? this.helm.target,
        firstSeenAt: row.firstSeenAt ?? now,
        lastSeenAt: touched ? now : (row.lastSeenAt ?? now),
      };
    });
    void db.vocab.bulkPut($state.snapshot(this.entries) as VocabRow[]).catch(() => {
      /* persistence is write-through best-effort; the in-memory table rules */
    });
  }

  async #logAttempt(res: AttemptResponse, origin: 'quick' | 'story' | 'vocab'): Promise<void> {
    try {
      await db.practiceLog.add({
        lang: this.helm.target,
        date: nowIso(),
        target: res.target,
        recognized: res.recognized_text,
        targetIpa: res.target_ipa,
        algorithm: res.algorithm,
        compIpa: res.comprehensibility.ipa,
        compSimilarity: res.comprehensibility.similarity,
        accIpa: res.accuracy.ipa,
        accSimilarity: res.accuracy.similarity,
        perfect: res.comprehensibility.exact,
        similarity: res.comprehensibility.similarity ?? 0,
        origin,
      });
    } catch {
      /* logging must never break the practice loop */
    }
  }

  // --- TTS (Speaker oracle) ----------------------------------------------
  async speak(text: string): Promise<Blob> {
    const engine = this.helm.tts;
    return tts(text, this.helm.target, {
      engine,
      speed: this.helm.speed,
    });
  }
}

export const model = new AppModel();
