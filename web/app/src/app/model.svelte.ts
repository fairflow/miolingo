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
import * as story from '../domain/storyReader.js';
import * as helmFns from '../domain/helm.js';
import * as vocabFns from '../domain/vocabFunctions.js';
import * as vocabTab from '../domain/vocab.js';
import { exportCsv, importOutcome } from '../domain/vocabImportExport.js';
import { phrasesFor, type UnifiedDoc } from '../domain/materials.js';
import type {
  AlignOp,
  Capture,
  ImportResult,
  Phrase,
  Score,
  VocabEntry,
} from '../domain/types.js';
import { attempt, fetchMaterial, materialsIndex, tts } from '../oracle/client.js';
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
  /** The Vocab TAB's UI params (sort/filter/editing) — the spec's Vocab
   * agent; the collection itself lives in `entries` (VocabTable). */
  vocab = $state<vocabTab.Vocab>(vocabTab.initialVocab);
  /** The full dual-channel result of the last scored attempt (display only;
   * lifecycle slaved to ps.res — see #sync). */
  lastAttempt = $state<AttemptResponse | null>(null);
  scoring = $state(false);
  error = $state<string | null>(null);

  // --- StoryReader slice (ONE narrative position; modes are affordances) --
  storyReader = $state<story.StoryReader>(story.initialStoryReader);
  /** Scenes for the current language, from unified stories (one file each). */
  storyScenes = $state<Phrase[][]>([]);
  storyLoading = $state(false);
  lastStoryAttempt = $state<AttemptResponse | null>(null);

  /** The story-content boundary: a StoryLibrary over the fetched scenes. */
  get storyLib(): story.StoryLibrary {
    const scenes = this.storyScenes;
    return {
      sceneCount: scenes.length,
      scene: (i: number) => scenes[i] ?? [],
    };
  }

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
      this.storyScenes = []; // story content is per language too
      this.#syncStory(story.initialStoryReader);
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

  /** Decorate domain entries with the row fields (lang, wall-clock), then
   * write the current language's table through to Dexie. Persisted rows drop
   * the in-memory domain ids (identity is [lang+word]; Dexie auto-assigns). */
  #setEntries(after: readonly VocabEntry[], touchedKey: string | null): void {
    const now = nowIso();
    this.entries = after.map((e) => {
      const row = e as VocabRow;
      return {
        ...row,
        lang: row.lang ?? this.helm.target,
        firstSeenAt: row.firstSeenAt ?? now,
        lastSeenAt: touchedKey !== null && e.word === touchedKey ? now : (row.lastSeenAt ?? now),
      };
    });
    const rows = ($state.snapshot(this.entries) as VocabRow[]).map(
      ({ id: _id, ...rest }) => rest,
    );
    void db
      .transaction('rw', db.vocab, async () => {
        await db.vocab.where('lang').equals(this.helm.target).delete();
        await db.vocab.bulkAdd(rows as VocabRow[]);
      })
      .catch(() => {
        /* persistence is write-through best-effort; the in-memory table rules */
      });
  }

  /** capture_vocab · vocabUpsert — ATOMIC: one synchronous state write, then
   * write-through persistence. The PS slice is untouched (no view flicker). */
  captureVocab(w: Capture | string): void {
    const key = typeof w === 'string' ? w : w.word;
    const norm = vocabFns.validateWord(key);
    this.#setEntries(vocabFns.addEntry(this.entries, w), norm?.key ?? null);
  }

  // --- Vocab tab (external channels + table write-throughs) --------------
  setVocabSort(s: vocabTab.Vocab['sort']): void {
    this.vocab = vocabTab.setSort(this.vocab, s);
  }

  setVocabFilter(q: string | null): void {
    this.vocab = vocabTab.setFilter(this.vocab, q);
  }

  beginEdit(id: number): void {
    this.vocab = vocabTab.beginEdit(this.vocab, id);
  }

  cancelEdit(): void {
    this.vocab = vocabTab.cancelEdit(this.vocab);
  }

  removeEntry(id: number): void {
    this.#setEntries(vocabFns.deleteFrom(this.entries, id), null);
  }

  amendEntry(id: number, fields: Readonly<Record<string, string>>): void {
    this.#setEntries(vocabFns.updateEntry(this.entries, id, fields), null);
    this.vocab = vocabTab.endEdit(this.vocab);
  }

  amendNotes(id: number, notes: string | null): void {
    this.#setEntries(vocabFns.updateNotesIn(this.entries, id, notes), null);
  }

  /** import_bulk — header target-guarded against the borrowed language. */
  importBulk(contents: string): ImportResult {
    const { entries, result } = importOutcome(this.entries, {
      contents,
      expectedTarget: this.helm.target,
    });
    if (result.kind === 'ok') this.#setEntries(entries, null);
    return result;
  }

  exportCsvString(): string {
    return exportCsv(this.entries);
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

  // --- StoryReader channels ------------------------------------------------
  async loadStory(): Promise<void> {
    this.storyLoading = true;
    try {
      const idx = await materialsIndex();
      const sceneFiles = idx.files
        .filter((f) => f.kind === 'stories')
        .sort((a, b) => (a.path < b.path ? -1 : 1));
      const source = helmFns.codeOfName(this.helm.source); // langRead
      const docs = await Promise.all(
        sceneFiles.map((f) => fetchMaterial<UnifiedDoc>(f.path)),
      );
      this.storyScenes = docs
        .map((d) => phrasesFor(d, this.helm.target, source))
        .filter((scene) => scene.length > 0);
      this.#syncStory(story.initialStoryReader); // fresh narrative position
    } catch {
      this.storyScenes = [];
    } finally {
      this.storyLoading = false;
    }
  }

  #syncStory(next: story.StoryReader): void {
    this.storyReader = next;
    if (next.res === null) this.lastStoryAttempt = null;
  }

  setStoryMode(m: story.StoryReader['mode']): void {
    this.#syncStory(story.setMode(this.storyReader, m)); // preserves (scene,pos)
  }

  selectScene(s: number): void {
    this.#syncStory(story.selectScene(this.storyReader, s)); // resets pos
  }

  storySelectItem(i: number): void {
    this.#syncStory(story.selectItem(this.storyReader, this.storyLib, i));
  }

  storyNext(): void {
    this.#syncStory(story.next(this.storyReader, this.storyLib));
  }

  storyPrev(): void {
    this.#syncStory(story.prev(this.storyReader));
  }

  storyClearRecording(): void {
    this.#syncStory(story.clearRecording(this.storyReader));
  }

  /** Story practice: the SAME loop as PSActive, over the scene's phrases,
   * logging origin 'story' and capturing to the same VocabTable store. */
  async storyRecordingMade(audio: Blob): Promise<void> {
    const lib = this.storyLib;
    const held = story.recordingMade(this.storyReader, audio);
    if (held === this.storyReader) return; // guarded (mode/dup)
    this.#syncStory(held);
    this.scoring = true;
    this.error = null;
    try {
      const target = story.phrasesOf(held, lib)[held.pos];
      const res = await attempt({
        audio,
        target: target?.text ?? '',
        lang: this.helm.target, // langRead
        algorithm: 'weighted_phone',
        whisperModel: this.helm.asrModel,
      });
      this.lastStoryAttempt = res;
      this.storyReader = story.attemptMade(
        this.storyReader,
        channelToScore(res, res.comprehensibility),
      );
      await this.#logAttempt(res, 'story');
      if (res.comprehensibility.exact && isSingleWord(res.target)) {
        this.captureVocab({
          word: res.target,
          translation: target?.translation ?? null,
          ipa: res.target_ipa,
          sourceName: 'story',
        });
      }
    } catch (e: unknown) {
      this.error = String(e);
      this.#syncStory(story.clearRecording(this.storyReader));
    } finally {
      this.scoring = false;
    }
  }

  /** story_capture_vocab — gated on a score by the domain. */
  storyCapture(): void {
    const w = story.captureWord(this.storyReader, this.storyLib);
    if (w !== null) {
      const item = story.phrasesOf(this.storyReader, this.storyLib)[this.storyReader.pos];
      this.captureVocab({
        word: w,
        translation: item?.translation ?? null,
        ipa: item?.ipa ?? null,
        sourceName: 'story',
      });
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
