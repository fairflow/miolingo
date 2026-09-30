<script lang="ts">
  // The current target: text + reference IPA + TTS playback + queue nav.
  // Renders ONLY the psView projection; enablement only from the ready set.
  import { model } from '../../app/model.svelte.js';
  import * as ps from '../../domain/practiceSession.js';

  const view = $derived(ps.psView(model.ps));
  const ready = $derived(ps.psReady(model.ps));

  let playing = $state(false);
  let ttsError = $state<string | null>(null);

  async function speak(): Promise<void> {
    const item = view.item;
    if (item === null || playing) return;
    ttsError = null;
    playing = true;
    try {
      const blob = await model.speak(item.text);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        playing = false;
      };
      await audio.play();
    } catch (e: unknown) {
      ttsError = `TTS unavailable: ${String(e)}`;
      playing = false;
    }
  }
</script>

{#if view.item !== null}
  <div class="phrase card">
    <div class="nav">
      <button onclick={() => model.prev()} disabled={!ready.canPrev}>←</button>
      <span class="muted">{view.pos + 1} / {view.total}</span>
      <button onclick={() => model.next()} disabled={!ready.canNext}>→</button>
    </div>
    <p class="target">{view.item.text}</p>
    {#if view.item.ipa !== ''}
      <p class="ipa">[{view.item.ipa}]</p>
    {/if}
    {#if view.item.translation !== ''}
      <p class="muted">{view.item.translation}</p>
    {/if}
    <button onclick={speak} disabled={playing}>🔊 Listen</button>
    {#if ttsError !== null}
      <span class="muted">{ttsError}</span>
    {/if}
  </div>
{/if}

<style>
  .phrase {
    margin: 1rem 0;
  }

  .nav {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }

  .target {
    font-size: 1.6rem;
    font-weight: 600;
    margin: 0.25rem 0;
  }

  .ipa {
    color: var(--accent);
    margin: 0.1rem 0 0.4rem;
  }
</style>
