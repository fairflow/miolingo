<script lang="ts">
  // StoryReader: ONE narrative position (scene, pos); the three modes are
  // affordances over it — switching modes PRESERVES your place (the spec's
  // deliberate fix over the Streamlit app's two independent loops).
  import { model } from '../../app/model.svelte.js';
  import * as story from '../../domain/storyReader.js';
  import type { ReadingMode } from '../../domain/types.js';
  import Recorder from '../shared/Recorder.svelte';
  import ScorePanel from '../shared/ScorePanel.svelte';

  const view = $derived(story.storyView(model.storyReader, model.storyLib));
  const canCapture = $derived(story.captureWord(model.storyReader, model.storyLib) !== null);

  const MODES: { value: ReadingMode; label: string }[] = [
    { value: 'full', label: '📜 Full scene' },
    { value: 'browse', label: '🔎 Phrase by phrase' },
    { value: 'practice', label: '🎯 Practice' },
  ];

  $effect(() => {
    if (model.storyScenes.length === 0 && !model.storyLoading) void model.loadStory();
  });

  let playing = $state(false);
  async function speak(text: string): Promise<void> {
    if (playing) return;
    playing = true;
    try {
      const url = URL.createObjectURL(await model.speak(text));
      const audio = new Audio(url);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        playing = false;
      };
      await audio.play();
    } catch {
      playing = false;
    }
  }
</script>

<section>
  {#if model.storyLoading}
    <p class="muted">Loading story scenes…</p>
  {:else if model.storyScenes.length === 0}
    <p class="muted">
      No story scenes available for “{model.helm.target}” (or the oracle is offline).
    </p>
  {:else}
    <div class="bar">
      <label
        >Scene
        <select
          value={view.scene}
          onchange={(e) => model.selectScene(Number(e.currentTarget.value))}
        >
          {#each model.storyScenes as _, i (i)}
            <option value={i}>Scene {i + 1}</option>
          {/each}
        </select>
      </label>
      <nav class="modes">
        {#each MODES as m (m.value)}
          <button class:active={view.mode === m.value} onclick={() => model.setStoryMode(m.value)}>
            {m.label}
          </button>
        {/each}
      </nav>
    </div>

    {#if view.mode === 'full'}
      <div class="card prose">
        {#each view.phrases as p, i (i)}
          <button
            class="inline"
            class:current={i === view.pos}
            onclick={() => model.storySelectItem(i)}
            title={p.translation}>{p.text}</button
          >
        {/each}
      </div>
      <p class="muted">Click a sentence to set your place — it follows you across modes.</p>
    {:else if view.item !== null}
      <div class="card">
        <div class="nav">
          <button onclick={() => model.storyPrev()} disabled={view.pos <= 0}>←</button>
          <span class="muted">{view.pos + 1} / {view.count}</span>
          <button onclick={() => model.storyNext()} disabled={view.pos >= view.count - 1}>→</button>
        </div>
        <p class="target">{view.item.text}</p>
        {#if view.item.ipa !== ''}<p class="ipa">[{view.item.ipa}]</p>{/if}
        {#if view.item.translation !== ''}<p class="muted">{view.item.translation}</p>{/if}
        <button onclick={() => view.item !== null && speak(view.item.text)} disabled={playing}>
          🔊 Listen
        </button>
        {#if view.mode === 'practice'}
          <div class="practice">
            <Recorder
              canRecord={!view.hasRecording}
              canClear={view.hasRecording}
              busy={model.scoring}
              onBlob={(b) => void model.storyRecordingMade(b)}
              onClear={() => model.storyClearRecording()}
            />
            <ScorePanel
              res={view.score !== null ? model.lastStoryAttempt : null}
              error={model.error}
            />
            {#if canCapture}
              <button onclick={() => model.storyCapture()}>📚 Capture to vocabulary</button>
            {/if}
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</section>

<style>
  .bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin-bottom: 0.9rem;
  }

  .modes {
    display: flex;
    gap: 0.4rem;
  }

  .modes button.active {
    border-color: var(--accent);
    color: var(--accent);
  }

  label {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  select {
    font: inherit;
    color: inherit;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.3rem;
  }

  .prose {
    line-height: 2;
  }

  .prose .inline {
    border: none;
    background: none;
    padding: 0 0.15rem;
    font-size: 1.05rem;
    line-height: inherit;
  }

  .prose .inline.current {
    background: color-mix(in srgb, var(--accent) 22%, transparent);
    border-radius: 4px;
  }

  .nav {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }

  .target {
    font-size: 1.5rem;
    font-weight: 600;
    margin: 0.25rem 0;
  }

  .ipa {
    color: var(--accent);
    margin: 0.1rem 0 0.4rem;
  }

  .practice {
    margin-top: 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    align-items: flex-start;
  }
</style>
