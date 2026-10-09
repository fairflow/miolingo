<script lang="ts">
  // The Helm agent's tab: renders helmView, drives set_* ports through the
  // domain transitions (guards structural: speed only for espeak, model size
  // only for whisper). Persisted via model.setHelm → Dexie settings.
  import { model } from '../../app/model.svelte.js';
  import * as helm from '../../domain/helm.js';
  import { health } from '../../oracle/client.js';
  import type { OracleHealth } from '../../oracle/types.js';
  import type { TTSKind, WhisperModel } from '../../domain/types.js';
  import { setTheme, theme } from '../../store/prefs.svelte.js';

  const view = $derived(helm.helmView(model.helm));

  const SOURCES = ['English', 'French', 'German', 'Spanish', 'Italian', 'Dutch', 'Portuguese'];
  const TARGETS = ['fr', 'pt', 'pt-br', 'de', 'es', 'it', 'nl', 'ru', 'en'];
  const TTS_ENGINES: TTSKind[] = ['google_cloud', 'gtts', 'espeak'];
  const WHISPER_MODELS: WhisperModel[] = ['tiny', 'base', 'small', 'medium', 'large'];

  let info = $state<OracleHealth | null>(null);
  $effect(() => {
    health().then(
      (h) => (info = h),
      () => (info = null),
    );
  });
</script>

<section class="card">
  <h2>⚙️ Helm</h2>
  <p class="muted">Direction: {view.source} → {view.language}</p>

  <label>
    Source (native) language
    <select
      value={view.source}
      onchange={(e) => model.setHelm(helm.setSource(model.helm, e.currentTarget.value))}
    >
      {#each SOURCES as s (s)}<option value={s}>{s}</option>{/each}
    </select>
  </label>

  <label>
    Target language
    <select
      value={view.target}
      onchange={(e) => model.setHelm(helm.setTarget(model.helm, e.currentTarget.value))}
    >
      {#each TARGETS as t (t)}
        <option value={t}>{helm.trainingNameOf(t)} ({t})</option>
      {/each}
    </select>
  </label>

  <label>
    TTS engine
    <select
      value={view.tts}
      onchange={(e) => model.setHelm(helm.setTTS(model.helm, e.currentTarget.value as TTSKind))}
    >
      {#each TTS_ENGINES as t (t)}<option value={t}>{t}</option>{/each}
    </select>
  </label>

  {#if view.showsSpeed}
    <label>
      eSpeak speed: {view.speed} wpm
      <input
        type="range"
        min="80"
        max="450"
        value={view.speed}
        onchange={(e) => model.setHelm(helm.setSpeed(model.helm, Number(e.currentTarget.value)))}
      />
    </label>
  {/if}

  {#if view.showsAsrModel}
    <label>
      Whisper model
      <select
        value={view.asrModel}
        onchange={(e) =>
          model.setHelm(helm.setAsrModel(model.helm, e.currentTarget.value as WhisperModel))}
      >
        {#each WHISPER_MODELS as m (m)}<option value={m}>{m}</option>{/each}
      </select>
    </label>
  {/if}

  <label>
    Theme
    <select
      value={theme.value}
      onchange={(e) => setTheme(e.currentTarget.value as 'dark' | 'light')}
    >
      <option value="dark">dark</option>
      <option value="light">light</option>
    </select>
  </label>

  {#if info !== null}
    <p class="muted small">
      Oracle: espeak {info.espeak ?? 'missing'} · A2P specialists for
      {info.a2p_langs.join(', ')} · whisper
      {info.whisper.loaded ? `${info.whisper.model} loaded` : 'loads on first attempt'}
    </p>
  {:else}
    <p class="muted small">Oracle unreachable — scoring and materials unavailable.</p>
  {/if}
</section>

<style>
  label {
    display: block;
    margin: 0.7rem 0;
    max-width: 22rem;
  }

  select,
  input[type='range'] {
    display: block;
    width: 100%;
    margin-top: 0.25rem;
    font: inherit;
    color: inherit;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.35rem;
  }

  .small {
    font-size: 0.8rem;
  }
</style>
