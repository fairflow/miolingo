<script lang="ts">
  import { TABS, TAB_LABELS } from '../store/tabs.js';
  import { ui, setTab } from '../store/prefs.svelte.js';
</script>

<nav>
  {#each TABS as tab (tab)}
    <button class:active={ui.tab === tab} onclick={() => setTab(tab)}>
      {TAB_LABELS[tab]}
    </button>
  {/each}
</nav>

<style>
  nav {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.5rem 0 1.25rem;
  }

  button.active {
    border-color: var(--accent);
    color: var(--accent);
  }
</style>
