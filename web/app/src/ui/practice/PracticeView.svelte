<script lang="ts">
  import { model } from '../../app/model.svelte.js';
  import * as ps from '../../domain/practiceSession.js';
  import MaterialPicker from './MaterialPicker.svelte';
  import PhraseCard from './PhraseCard.svelte';
  import Recorder from './Recorder.svelte';
  import ScorePanel from './ScorePanel.svelte';

  const view = $derived(ps.psView(model.ps));
</script>

<section>
  <MaterialPicker />
  {#if view.total === 0}
    <p class="muted">Load a material set above, then record yourself saying each phrase.</p>
  {:else}
    <PhraseCard />
    <Recorder />
    <ScorePanel />
  {/if}
</section>
