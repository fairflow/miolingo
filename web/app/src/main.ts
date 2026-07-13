import { mount } from 'svelte';
import App from './ui/App.svelte';
import { initTabSync } from './store/prefs.svelte.js';
import { model } from './app/model.svelte.js';
import './ui/app.css';

initTabSync();
void model.hydrate(); // load persisted Helm + vocab; UI reacts as it lands
void navigator.storage?.persist?.(); // ask the browser not to evict our data

const app = mount(App, { target: document.getElementById('app')! });

export default app;
