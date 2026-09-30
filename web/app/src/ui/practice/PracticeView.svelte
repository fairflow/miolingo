<script lang="ts">
  import { model } from '../../app/model.svelte.js';
  import * as ps from '../../domain/practiceSession.js';
  import MaterialPicker from './MaterialPicker.svelte';
  import PhraseCard from './PhraseCard.svelte';
  import Recorder from '../shared/Recorder.svelte';
  import ScorePanel from '../shared/ScorePanel.svelte';

  const view = $derived(ps.psView(model.ps));
  const ready = $derived(ps.psReady(model.ps));
</script>

<section>
  <MaterialPicker />
  {#if view.total === 0}
    <p class="muted">Load a material set above, then record yourself saying each phrase.</p>
  {:else}
    <PhraseCard />
    <Recorder
      canRecord={ready.canRecord}
      canClear={ready.canClearRecording}
      busy={model.scoring}
      onBlob={(b) => void model.recordingMade(b)}
      onClear={() => model.clearRecording()}
    />
    <ScorePanel res={view.score !== null ? model.lastAttempt : null} error={model.error} />
  {/if}
</section>
