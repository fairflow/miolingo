<script lang="ts">
  import Tabs from './Tabs.svelte';
  import StatusBadge from './shared/StatusBadge.svelte';
  import PracticeView from './practice/PracticeView.svelte';
  import StoryView from './story/StoryView.svelte';
  import VocabView from './vocab/VocabView.svelte';
  import StatsView from './stats/StatsView.svelte';
  import HistoryView from './history/HistoryView.svelte';
  import HelmView from './helm/HelmView.svelte';
  import { ui } from '../store/prefs.svelte.js';
</script>

<main>
  <header>
    <h1>🗣️ Miolingo</h1>
    <StatusBadge />
  </header>
  <Tabs />

  {#if ui.tab === 'practice'}
    <PracticeView />
  {:else if ui.tab === 'story'}
    <StoryView />
  {:else if ui.tab === 'vocab'}
    <VocabView />
  {:else if ui.tab === 'stats'}
    <StatsView />
  {:else if ui.tab === 'history'}
    <HistoryView />
  {:else if ui.tab === 'helm'}
    <HelmView />
  {/if}
</main>

<style>
  header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
  }
</style>
