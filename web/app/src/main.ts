import { mount } from 'svelte';
import App from './ui/App.svelte';
import { initTabSync } from './store/prefs.svelte.js';
import './ui/app.css';

initTabSync();

const app = mount(App, { target: document.getElementById('app')! });

export default app;
