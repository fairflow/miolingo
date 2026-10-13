// host.js, the parts that need no browser: the WAV encoder and parser, the peaks, and showTake's cache (with a small fake DOM).
//   node neolingo/tests/check_host_js.js
const vm = require('vm'), fs = require('fs'), path = require('path'), assert = require('assert');
let fetches = 0, wavBytes = null;
function el(tag) {
  const e = { tag, children: [], style: {}, attrs: {}, textContent: '', _html: '', calls: [] };
  e.appendChild = c => { e.children.push(c); return c; };
  e.setAttribute = (k, v) => { e.attrs[k] = v; };
  Object.defineProperty(e, 'innerHTML', { get: () => e._html, set: v => { e._html = v; e.children = []; } });
  e.getContext = () => new Proxy({}, { get: (t, k) => (k in t ? t[k] : (...a) => { e.calls.push([k, ...a]); }), set: (t, k, v) => { t[k] = v; return true; } });
  return e;
}
const win = {
  devicePixelRatio: 2, AudioContext: function () {},
  getComputedStyle: () => ({ color: 'rgb(1, 2, 3)' }),
};
const ctx = { window: win, document: { createElement: el, getElementById: () => null, body: el('body') }, navigator: {}, console,
  getComputedStyle: win.getComputedStyle, Float32Array, Int16Array, DataView, ArrayBuffer, Blob, Promise, Math, Date, setTimeout, clearInterval,
  URL: { createObjectURL: () => 'blob:x', revokeObjectURL() {} },
  fetch: url => { fetches++; return Promise.resolve({ ok: /^take\/t[0-9a-f]+\.wav$/.test(url), arrayBuffer: () => Promise.resolve(wavBytes) }); } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'page', 'host.js'), 'utf8'), ctx);
const H = win.NeolingoHost;

(async () => {
  // a synthetic recording: 1.5 s at 16 kHz, a sine ramping up, clipped in the last tenth
  const n = 24000, s = new Float32Array(n);
  for (let i = 0; i < n; i++) s[i] = (i > 0.9 * n ? 2 : 0.5 * i / n) * Math.sin(i / 7);
  const blob = H._wav16(s), buf = await new Response(blob).arrayBuffer();
  wavBytes = buf;
  const w = H._parseWav(buf);
  assert.strictEqual(w.rate, 16000); assert.strictEqual(w.samples.length, n);
  let err = 0; for (let i = 0; i < n; i++) err = Math.max(err, Math.abs(w.samples[i] - Math.max(-1, Math.min(1, s[i]))));
  assert(err < 1e-3, 'round trip error ' + err);
  console.log('  ok   wav16 -> parseWav round trip, max error', err.toExponential(1));
  assert.throws(() => H._parseWav(new ArrayBuffer(10)), /not a WAV/);
  console.log('  ok   a non-WAV is refused');
  const p = H._peaks(w.samples, 100);
  assert.strictEqual(p.min.length, 100);
  assert(p.max[99] > 0.99 && p.min[99] < -0.99, 'clipped end reaches full scale');
  assert(p.max[10] < 0.1 && p.max[10] > 0, 'quiet start is small');
  for (let i = 0; i < 100; i++) assert(p.min[i] <= p.max[i]);
  const r = H._reduce(H._peaks(w.samples, 1024), 50);
  assert(r.max[49] > 0.99 && r.min[49] < -0.99);
  console.log('  ok   peaks: min/max per column, clipping reaches +-1; reduce keeps extremes');
  const z = H._peaks(new Float32Array(0), 8); assert.strictEqual(z.max[3], 0);
  console.log('  ok   an empty recording gives flat peaks');

  // showTake: first call fetches, repeat calls with new elements draw from the cache without a fetch
  const e1 = el('div'); H.showTake('t0123456789abcdef', e1);
  await new Promise(r => setTimeout(r, 20));
  assert.strictEqual(fetches, 1); assert.strictEqual(e1.children.length, 2);
  assert.strictEqual(e1.children[1].textContent.trim(), '1.5 s');
  const cv = e1.children[0]; assert.strictEqual(cv.width, 560); assert.strictEqual(cv.height, 96);
  assert(cv.calls.some(c => c[0] === 'fillRect'));
  console.log('  ok   showTake: fetched once, canvas 560x96 at dpr 2, duration', e1.children[1].textContent.trim());
  const e2 = el('div'); H.showTake('t0123456789abcdef', e2);
  assert.strictEqual(e2.children.length, 2, 'drawn synchronously from the cache');
  assert.strictEqual(fetches, 1);
  console.log('  ok   a repeat call draws at once, no new fetch');
  // two calls before the first fetch finishes: one fetch
  const e3 = el('div'), e4 = el('div'); H.showTake('t1111111111111111', e3); H.showTake('t1111111111111111', e4);
  await new Promise(r => setTimeout(r, 20));
  assert.strictEqual(fetches, 2); assert(e3.children.length === 2 && e4.children.length === 2);
  console.log('  ok   concurrent calls share one fetch');
  // errors never escape
  H.showTake('bad/token', el('div')); H.showTake(null, null); H.showTake('t2222222222222222', null);
  wavBytes = new ArrayBuffer(5); H.showTake('t3333333333333333', el('div'));
  await new Promise(r => setTimeout(r, 20));
  console.log('  ok   unknown tokens, bad data and missing elements throw nothing');
  console.log('host.js checks passed');
})().catch(e => { console.error('FAIL', e); process.exit(1); });
