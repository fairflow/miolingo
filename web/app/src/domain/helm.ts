// =====================================================================
// Helm — spec/HelmRecovered.wl. Owns the session settings; everyone else
// BORROWS via langRead (fetch fresh at point of use, never cache).
// =====================================================================

import type { ASRKind, LangPair, TTSKind, WhisperModel } from './types.js';

export interface Helm {
  readonly source: string; // native language NAME, e.g. "English"
  readonly target: string; // target language CODE, e.g. "fr"
  readonly tts: TTSKind;
  readonly speed: number; // espeak wpm
  readonly asr: ASRKind;
  readonly asrModel: WhisperModel;
}

export const defaultHelm: Helm = {
  source: 'English',
  target: 'fr',
  tts: 'gtts',
  speed: 250,
  asr: 'whisper',
  asrModel: 'base',
};

export function setSource(h: Helm, s: string): Helm {
  return { ...h, source: s };
}

export function setTarget(h: Helm, t: string): Helm {
  return { ...h, target: t };
}

export function setTTS(h: Helm, e: TTSKind): Helm {
  return { ...h, tts: e };
}

// set_speed — guarded: only meaningful for espeak (the wpm slider guard)
export function setSpeed(h: Helm, w: number): Helm {
  return h.tts === 'espeak' ? { ...h, speed: w } : h;
}

export function setAsr(h: Helm, a: ASRKind): Helm {
  return { ...h, asr: a };
}

// set_asr_model — guarded: model size only for whisper
export function setAsrModel(h: Helm, m: WhisperModel): Helm {
  return h.asr === 'whisper' ? { ...h, asrModel: m } : h;
}

/** langRead — the pair Helm lends out; borrowers never cache it. */
export function langPair(h: Helm): LangPair {
  return { source: h.source, target: h.target };
}

export function showsSpeed(h: Helm): boolean {
  return h.tts === 'espeak';
}

export function showsAsrModel(h: Helm): boolean {
  return h.asr === 'whisper';
}

// --- helmView (HelmFunctions.wl) ---------------------------------------
// target code → full training name; unknown codes pass through. Extends the
// spec's map with the languages the web app's materials actually cover.
const TRAINING_NAMES: Readonly<Record<string, string>> = {
  en: 'English',
  fr: 'French',
  pt: 'Portuguese',
  'pt-br': 'Portuguese (Brazilian)',
  'pt-pt': 'Portuguese (European)',
  de: 'German',
  es: 'Spanish',
  it: 'Italian',
  nl: 'Dutch',
  ru: 'Russian',
};

export function trainingNameOf(code: string): string {
  return TRAINING_NAMES[code] ?? code;
}

export interface HelmView {
  readonly source: string;
  readonly target: string;
  readonly language: string; // trainingNameOf(target)
  readonly tts: TTSKind;
  readonly speed: number;
  readonly asr: ASRKind;
  readonly asrModel: WhisperModel;
  readonly showsSpeed: boolean;
  readonly showsAsrModel: boolean;
}

export function helmView(h: Helm): HelmView {
  return {
    source: h.source,
    target: h.target,
    language: trainingNameOf(h.target),
    tts: h.tts,
    speed: h.speed,
    asr: h.asr,
    asrModel: h.asrModel,
    showsSpeed: showsSpeed(h),
    showsAsrModel: showsAsrModel(h),
  };
}
