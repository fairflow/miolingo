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
const judgements = {}, posts = [];                     // what the fake host holds for judge / judgement
let judging = true, failPost = false, jfetches = 0;
function makeHost() {
  const win = {
    devicePixelRatio: 2, AudioContext: function () {},
    getComputedStyle: () => ({ color: 'rgb(1, 2, 3)' }),
  };
  const ctx = { window: win, document: { createElement: el, getElementById: () => null, body: el('body') }, navigator: {}, console,
    getComputedStyle: win.getComputedStyle, Float32Array, Int16Array, DataView, ArrayBuffer, Blob, Promise, Math, Date, setTimeout, clearInterval, JSON,
    URL: { createObjectURL: () => 'blob:x', revokeObjectURL() {} },
    fetch: (url, opt) => {
      if (url === 'version') return Promise.resolve({ ok: true, json: () => Promise.resolve({ judging }) });
      if (url.startsWith('judgement?take=')) { jfetches++; return Promise.resolve({ ok: true, json: () => Promise.resolve(judgements[url.split('=')[1]] || {}) }); }
      if (url === 'judge') {
        const b = JSON.parse(opt.body); posts.push(b);
        if (failPost) return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
        judgements[b.take] = { verdict: b.verdict, note: b.note }; return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }
      fetches++; return Promise.resolve({ ok: /^take\/t[0-9a-f]+\.wav$/.test(url), arrayBuffer: () => Promise.resolve(wavBytes) });
    } };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'page', 'host.js'), 'utf8'), ctx);
  return win;
}
const H = makeHost().NeolingoHost;

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

  // judgeResult: drawn from a per-token cache, the chosen button marked, a tap stored at once
  const flush = () => new Promise(r => setTimeout(r, 20));
  const texts = e => { const o = []; (function w(x) { if (x.textContent) o.push(x.textContent); (x.children || []).forEach(w); })(e); return o; };
  const find = (e, t) => { let r = null; (function w(x) { if (!r && x.textContent === t) r = x; (x.children || []).forEach(w); })(e); return r; };
  const marked = e => { const o = []; (function w(x) { if (x.attrs && x.attrs['aria-pressed'] === 'true') o.push(x.textContent); (x.children || []).forEach(w); })(e); return o; };
  const T = 't4444444444444444';
  const j1 = el('div'); H.judgeResult(T, j1); await flush();
  assert(texts(j1).includes('Was this result fair?'));
  for (const b of ['Fair', 'Too harsh', 'Too generous', 'note']) assert(find(j1, b), b + ' is drawn');
  assert.deepStrictEqual(marked(j1), []);
  console.log('  ok   judgeResult: the question, three buttons and a note link; nothing marked yet');
  find(j1, 'Too harsh').onclick(); await flush();
  assert.deepStrictEqual(posts, [{ take: T, verdict: 'harsh' }]);
  assert.deepStrictEqual(marked(j1), ['\u2713 Too harsh']);
  find(j1, '\u2713 Too harsh').onclick(); await flush();
  assert.strictEqual(posts.length, 1, 'the marked one again leaves it: no new POST');
  console.log('  ok   a tap POSTs at once and marks the button; tapping the marked one again does nothing');
  const j2 = el('div'); H.judgeResult(T, j2); await flush();
  assert.deepStrictEqual(marked(j2), ['\u2713 Too harsh']);
  assert.strictEqual(jfetches, 1, 'one GET judgement for the token');
  console.log('  ok   a redraw with a NEW element shows the judgement held, from the cache (one GET judgement)');
  find(j2, 'note').onclick();
  const nf = (function f(x) { let r = null; (function w(y) { if (y.tag === 'input') r = y; (y.children || []).forEach(w); })(x); return r; })(j2);
  assert(nf, 'the note field opens'); nf.value = ' too strict on the vowel ';
  find(j2, 'Save').onclick(); await flush();
  assert.deepStrictEqual(posts[1], { take: T, verdict: 'harsh', note: 'too strict on the vowel' });
  assert(texts(j2).some(t => t.includes('too strict on the vowel')), 'the note is shown');
  const j3 = el('div'); H.judgeResult(T, j3); await flush();
  assert(texts(j3).some(t => t.includes('too strict on the vowel')), 'and in a redraw');
  console.log('  ok   a note is saved with the verdict, shown, and shown again after a redraw');
  // a token already judged on the host is fetched and shown; a note before any verdict is not stored
  judgements['t5555555555555555'] = { verdict: 'generous', note: 'earlier' };
  const j4 = el('div'); H.judgeResult('t5555555555555555', j4); await flush();
  assert.deepStrictEqual(marked(j4), ['\u2713 Too generous']);
  const j5 = el('div'); H.judgeResult('t6666666666666666', j5); await flush();
  find(j5, 'note').onclick(); find(j5, 'Save').onclick(); await flush();
  assert.strictEqual(posts.length, 2, 'no verdict, no POST');
  // a refused POST puts the mark back and never throws
  failPost = true; find(j5, 'Fair').onclick(); await flush();
  assert.deepStrictEqual(marked(j5), [], 'refused: not marked'); failPost = false;
  H.judgeResult(null, null); H.judgeResult('t7777777777777777', null); H.judgeResult('bad token', el('div')); await flush();
  console.log('  ok   earlier judgements are fetched; a failed POST is undone; bad arguments throw nothing');
  // judging switched off by the host: the element stays empty
  judging = false;
  const off = makeHost().NeolingoHost, j6 = el('div'); off.judgeResult(T, j6); await flush();
  assert.strictEqual(j6.children.length, 0);
  console.log('  ok   with judging off (version says so) the element stays empty');
  console.log('host.js checks passed');
})().catch(e => { console.error('FAIL', e); process.exit(1); });
