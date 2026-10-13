// The real host's own script: window.NeolingoHost = { record, speak, lists, wordLists, playTake, showTake, judgeResult }.
// record(session): Web Audio capture -> 16 kHz mono 16-bit WAV built here (no MediaRecorder, no ffmpeg) -> POST take.
(function () {
  'use strict';
  var TARGET_RATE = 16000, MAX_SECONDS = 30;
  var active = null;

  // ---- WAV ----
  function resample(chunks, total, rate) {
    var all = new Float32Array(total), o = 0, i;
    for (i = 0; i < chunks.length; i++) { all.set(chunks[i], o); o += chunks[i].length; }
    if (rate === TARGET_RATE) return all;
    var ratio = rate / TARGET_RATE, n = Math.floor(all.length / ratio), out = new Float32Array(n);
    for (i = 0; i < n; i++) {                       // box filter: the mean of the input samples this output sample covers
      var a = Math.floor(i * ratio), b = Math.max(a + 1, Math.min(all.length, Math.floor((i + 1) * ratio))), s = 0;
      for (var k = a; k < b; k++) s += all[k];
      out[i] = s / (b - a);
    }
    return out;
  }
  function wav16(samples) {
    var buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
    function str(o, s) { for (var i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); }
    str(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, TARGET_RATE, true); v.setUint32(28, TARGET_RATE * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    str(36, 'data'); v.setUint32(40, samples.length * 2, true);
    for (var i = 0; i < samples.length; i++) {
      var x = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(44 + i * 2, x < 0 ? x * 0x8000 : x * 0x7fff, true);
    }
    return new Blob([buf], { type: 'audio/wav' });
  }

  // ---- the recorder's controls ----
  function panel() {
    var host = document.getElementById('recorder'), own = !host;
    if (own) {
      host = document.createElement('div');
      host.style.cssText = 'position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:9999;background:#fff;' +
        'color:#111;border:1px solid #888;border-radius:10px;padding:10px 14px;box-shadow:0 2px 12px rgba(0,0,0,.3);' +
        'font:15px system-ui,sans-serif;min-width:260px;max-width:92vw';
      document.body.appendChild(host);
    }
    host.innerHTML = '';
    var line = document.createElement('div'), time = document.createElement('span'), msg = document.createElement('span'),
        bar = document.createElement('div'), fill = document.createElement('div'), row = document.createElement('div'),
        stop = document.createElement('button'), cancel = document.createElement('button');
    line.style.cssText = 'display:flex;justify-content:space-between;margin-bottom:6px';
    bar.style.cssText = 'height:10px;background:#ddd;border-radius:5px;overflow:hidden';
    fill.style.cssText = 'height:100%;width:0;background:#2a9d4a';
    row.style.cssText = 'display:flex;gap:8px;margin-top:8px';
    stop.textContent = 'Stop'; cancel.textContent = 'Cancel'; stop.type = cancel.type = 'button';
    stop.style.cssText = cancel.style.cssText = 'font:inherit;padding:6px 14px;flex:1';
    msg.textContent = 'Recording…'; time.textContent = '0.0 s';
    line.appendChild(msg); line.appendChild(time); bar.appendChild(fill);
    row.appendChild(stop); row.appendChild(cancel);
    [line, bar, row].forEach(function (e) { host.appendChild(e); });
    return {
      level: function (x) { fill.style.width = Math.min(100, Math.round(x * 100)) + '%'; fill.style.background = x > 0.9 ? '#c33' : '#2a9d4a'; },
      time: function (s) { time.textContent = s.toFixed(1) + ' s'; },
      say: function (t) { msg.textContent = t; },
      busy: function () { stop.disabled = cancel.disabled = true; },
      onStop: function (f) { stop.onclick = f; }, onCancel: function (f) { cancel.onclick = f; },
      close: function (delay) {
        setTimeout(function () { if (own) { if (host.parentNode) host.parentNode.removeChild(host); } else host.innerHTML = ''; }, delay || 0);
      }
    };
  }

  // ---- record(session) ----
  function record(session) {
    if (active) return Promise.reject(new Error('already recording'));
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      var m = 'The microphone needs a secure page (https, or http://127.0.0.1).';
      alert(m); return Promise.reject(new Error(m));
    }
    var AC = window.AudioContext || window.webkitAudioContext;
    var ctx = new AC();                                  // made in the click, so that iOS lets it run
    if (ctx.resume) ctx.resume();
    var ui = panel(); ui.say('Waiting for the microphone…');
    active = true;
    return navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: true, channelCount: 1 } })
      .then(function (stream) {
        return new Promise(function (resolve, reject) {
          var chunks = [], total = 0, t0 = Date.now(), done = false, ticker;
          var src = ctx.createMediaStreamSource(stream), proc = ctx.createScriptProcessor(4096, 1, 1), mute = ctx.createGain();
          mute.gain.value = 0;
          proc.onaudioprocess = function (e) {
            if (done) return;
            var d = e.inputBuffer.getChannelData(0), c = new Float32Array(d), s = 0, i;
            chunks.push(c); total += c.length;
            for (i = 0; i < c.length; i++) s += c[i] * c[i];
            ui.level(Math.min(1, Math.sqrt(s / c.length) * 4));
          };
          src.connect(proc); proc.connect(mute); mute.connect(ctx.destination);
          function release() {
            done = true; clearInterval(ticker); active = null;
            try { proc.disconnect(); src.disconnect(); } catch (e) {}
            stream.getTracks().forEach(function (t) { t.stop(); });
            try { ctx.close(); } catch (e) {}
          }
          function finish() {
            if (done) return;
            var rate = ctx.sampleRate; release(); ui.busy(); ui.say('Uploading…');
            var pcm = resample(chunks, total, rate), blob = wav16(pcm);
            fetch('take', { method: 'POST', headers: { 'Content-Type': 'audio/wav' }, body: blob })
              .then(function (r) { return r.json(); })
              .then(function (j) {
                if (!j.take) throw new Error(j.err || 'the host refused the recording');
                seedTake(j.take, pcm, TARGET_RATE);              // the picture then needs no fetch
                ui.say('Recorded.'); ui.close(400); resolve(j.take);
              })
              .catch(function (e) { ui.say('Upload failed: ' + e.message); ui.close(2500); reject(e); });
          }
          function cancel() { if (done) return; release(); ui.say('Cancelled.'); ui.close(300); reject(new Error('cancelled')); }
          ui.say('Recording… press Stop when done');
          ui.onStop(finish); ui.onCancel(cancel);
          ticker = setInterval(function () {
            var s = (Date.now() - t0) / 1000; ui.time(s);
            if (s >= MAX_SECONDS) finish();
          }, 100);
        });
      }, function (e) {
        active = null; try { ctx.close(); } catch (x) {}
        ui.say('No microphone: ' + (e && e.message ? e.message : e)); ui.close(3000);
        throw e;
      });
  }

  // ---- speak(text, variant, slow) ----
  // The host answers with whatever the speech engine makes (audio/mpeg from gTTS, audio/wav from say or espeak): the
  // reply is fetched as a blob and played by an Audio element on a blob URL, which takes either content type.
  var player = null, playerUrl = null, playerDone = null, playGen = 0;
  function stopPlayer() {
    if (player) { try { player.pause(); } catch (e) {} player = null; }
    if (playerUrl) { URL.revokeObjectURL(playerUrl); playerUrl = null; }
    if (playerDone) { var f = playerDone; playerDone = null; f(); }      // a stopped play counts as finished
  }
  // Plays the blob at `url` (fetched from the host); a later call, or stopPlayer, stops this one and resolves it.
  function playUrl(url, failMsg) {
    stopPlayer();
    var gen = ++playGen;
    return fetch(url).then(function (r) {
      if (!r.ok) {                                          // the host's reason, when it gave one ({"err": ...})
        var j = typeof r.json === 'function' ? r.json() : Promise.resolve({});
        return Promise.resolve(j).catch(function () { return {}; }).then(function (b) { throw new Error((b && b.err) || failMsg); });
      }
      return r.blob();
    }).then(function (blob) {
      if (gen !== playGen) return;                          // another play began while this was being fetched
      stopPlayer();
      var u = playerUrl = URL.createObjectURL(blob), a = player = new Audio(u);
      return new Promise(function (resolve, reject) {
        playerDone = resolve;
        a.onended = function () { if (player === a) stopPlayer(); resolve(); };
        a.onerror = function () { if (player === a) stopPlayer(); reject(new Error('the browser could not play the sound')); };
        var p = a.play(); if (p && p.catch) p.catch(function (e) { if (player === a) stopPlayer(); reject(e); });
      });
    });
  }
  function speak(text, variant, slow) {
    return playUrl('speak?text=' + encodeURIComponent(text) + '&variant=' + encodeURIComponent(variant || 'fr-fr') + '&slow=' + (slow ? 'true' : 'false'),
      'the host could not make the speech');
  }

  // ---- playTake(take) ----
  function takeUrl(take) { return 'take/' + encodeURIComponent(take) + '.wav'; }
  function playTake(take) { return playUrl(takeUrl(take), 'the host does not hold that recording'); }

  // ---- the waveform: parse the WAV here (16-bit PCM, the header wav16 writes), min/max per column, cached by token ----
  function parseWav(buf) {
    var v = new DataView(buf), n = v.byteLength, o = 12, rate = 0, ch = 1, bits = 16, dataAt = -1, dataLen = 0;
    if (n < 12 || v.getUint32(0) !== 0x52494646 || v.getUint32(8) !== 0x57415645) throw new Error('not a WAV file');
    while (o + 8 <= n) {                                   // walk the chunks: espeak and others may add some before 'data'
      var id = v.getUint32(o), len = v.getUint32(o + 4, true);
      if (id === 0x666d7420 && o + 24 <= n) { ch = v.getUint16(o + 10, true); rate = v.getUint32(o + 12, true); bits = v.getUint16(o + 22, true); }
      else if (id === 0x64617461) { dataAt = o + 8; dataLen = Math.min(len, n - dataAt); break; }
      o += 8 + len + (len & 1);
    }
    if (dataAt < 0 || !rate || bits !== 16 || ch < 1) throw new Error('unsupported WAV');
    var count = Math.floor(dataLen / (2 * ch)), out = new Float32Array(count);
    for (var i = 0; i < count; i++) out[i] = v.getInt16(dataAt + i * 2 * ch, true) / 32768;       // first channel
    return { rate: rate, samples: out };
  }
  var BINS = 1024;
  // min and max of the samples in each of `bins` equal parts (a part with no sample gets 0, 0)
  function peaks(samples, bins) {
    var mn = new Float32Array(bins), mx = new Float32Array(bins), n = samples.length;
    for (var b = 0; b < bins; b++) {
      var a = Math.floor(b * n / bins), e = Math.max(a + 1, Math.floor((b + 1) * n / bins)), lo = 0, hi = 0;
      if (a < n) { lo = hi = samples[a]; for (var i = a + 1; i < e && i < n; i++) { var x = samples[i]; if (x < lo) lo = x; if (x > hi) hi = x; } }
      mn[b] = lo; mx[b] = hi;
    }
    return { min: mn, max: mx };
  }
  // the same, for `cols` columns, from peaks already made (min of mins, max of maxes)
  function reduce(p, cols) {
    var bins = p.min.length, mn = new Float32Array(cols), mx = new Float32Array(cols);
    for (var c = 0; c < cols; c++) {
      var a = Math.floor(c * bins / cols), e = Math.max(a + 1, Math.floor((c + 1) * bins / cols)), lo = p.min[a], hi = p.max[a];
      for (var i = a + 1; i < e && i < bins; i++) { if (p.min[i] < lo) lo = p.min[i]; if (p.max[i] > hi) hi = p.max[i]; }
      mn[c] = lo; mx[c] = hi;
    }
    return { min: mn, max: mx };
  }
  function summary(samples, rate) { var p = peaks(samples, BINS); p.seconds = samples.length / rate; return p; }

  var takeCache = {}, takeOrder = [], CACHE_MAX = 40;      // token -> peaks (ready) or a Promise of them; never the samples
  function remember(token, value) {
    if (!(token in takeCache)) { takeOrder.push(token); if (takeOrder.length > CACHE_MAX) delete takeCache[takeOrder.shift()]; }
    takeCache[token] = value;
  }
  function seedTake(token, samples, rate) { try { remember(token, summary(samples, rate)); } catch (e) {} }

  var W = 280, H = 48;
  function draw(box, p) {
    box.innerHTML = '';
    var dpr = window.devicePixelRatio || 1, cv = document.createElement('canvas'), colour = 'currentColor';
    try { colour = getComputedStyle(box).color || colour; } catch (e) {}
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    cv.style.cssText = 'width:' + W + 'px;height:' + H + 'px;vertical-align:middle';
    cv.setAttribute('role', 'img'); cv.setAttribute('aria-label', 'Waveform of the recording, ' + p.seconds.toFixed(1) + ' seconds');
    var g = cv.getContext('2d');
    if (g) {
      var cols = cv.width, q = reduce(p, cols), mid = cv.height / 2, half = mid - 1.5 * dpr, i;
      g.strokeStyle = g.fillStyle = colour;
      g.globalAlpha = 0.25; g.lineWidth = Math.max(1, dpr);
      g.beginPath();                                       // full scale: a peak that reaches these lines is clipped
      g.moveTo(0, mid - half); g.lineTo(cols, mid - half); g.moveTo(0, mid + half); g.lineTo(cols, mid + half); g.stroke();
      g.globalAlpha = 1;
      for (i = 0; i < cols; i++) {
        var top = mid - Math.max(-1, Math.min(1, q.max[i])) * half, bot = mid - Math.max(-1, Math.min(1, q.min[i])) * half;
        g.fillRect(i, top, 1, Math.max(1, bot - top));
      }
    }
    var t = document.createElement('span');
    t.textContent = ' ' + p.seconds.toFixed(1) + ' s'; t.style.cssText = 'margin-left:.5em;font-size:.9em;opacity:.8';
    box.appendChild(cv); box.appendChild(t);
  }
  function showTake(take, element) {
    try {
      if (!element || !take) return;
      var c = takeCache[take];
      if (c && !c.then) { draw(element, c); return; }      // cached: drawn at once
      if (!c) {
        c = fetch(takeUrl(take)).then(function (r) {
          if (!r.ok) throw new Error('no such take');
          return r.arrayBuffer();
        }).then(function (b) { var w = parseWav(b); return summary(w.samples, w.rate); });
        remember(take, c);
        c.then(function (p) { remember(take, p); }, function () { if (takeCache[take] === c) delete takeCache[take]; });
      }
      c.then(function (p) { try { draw(element, p); } catch (e) {} }, function () {});
    } catch (e) {}
  }

  // ---- judgeResult(take, element): "Was this result fair?" (a test tool; the host's NEOLINGO_JUDGING=0 turns it off) ----
  // The page calls this again with a NEW empty element at every redraw: the judgement held is cached by token, so a redraw
  // shows it at once.  A tap is stored at once (POST judge) and marks the button; tapping the marked one again leaves it.
  var VERDICTS = [['fair', 'Fair'], ['harsh', 'Too harsh'], ['generous', 'Too generous']];
  var judgeCache = {}, judgeOrder = [], judgingP = null;     // token -> {verdict, note} (ready) or a Promise of it
  function judgingOn() {                                    // a Promise<boolean>, asked once: GET version says "judging"
    if (!judgingP) {
      judgingP = fetch('version').then(function (r) { return r.json(); }).then(function (v) { return v.judging !== false; },
                                                                            function () { return false; });
    }
    return judgingP;
  }
  function rememberJudgement(token, value) {
    if (!(token in judgeCache)) { judgeOrder.push(token); if (judgeOrder.length > 200) delete judgeCache[judgeOrder.shift()]; }
    judgeCache[token] = value;
  }
  function tint(colour) {                                   // 'rgb(r, g, b)' -> the same at 18% opacity, or ''
    var m = /^rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/.exec(colour || '');
    return m ? 'rgba(' + m[1] + ',' + m[2] + ',' + m[3] + ',0.18)' : '';
  }
  function drawJudge(take, element, j) {
    element.innerHTML = '';
    var colour = '', tinted = '';
    try { colour = getComputedStyle(element).color || ''; tinted = tint(colour); } catch (e) {}
    var state = { verdict: (j && j.verdict) || null, note: (j && j.note) || '' };
    var box = document.createElement('div');
    box.style.cssText = 'margin-top:.6em;font-size:.9em;line-height:1.4';
    var q = document.createElement('div'); q.textContent = 'Was this result fair?'; q.style.cssText = 'opacity:.85;margin-bottom:.3em';
    var row = document.createElement('div'); row.style.cssText = 'display:flex;flex-wrap:wrap;gap:.4em;align-items:center';
    var msg = document.createElement('div'); msg.style.cssText = 'font-size:.9em;margin-top:.3em;min-height:1.2em';
    var shown = document.createElement('div'); shown.style.cssText = 'font-style:italic;margin-top:.3em;word-break:break-word';
    var field = document.createElement('div'), input = null;
    var buttons = {};
    function say(t) { msg.textContent = t || ''; }
    function showNote() { shown.textContent = state.note ? '“' + state.note + '”' : ''; }
    function mark() {
      VERDICTS.forEach(function (v) {
        var on = state.verdict === v[0], b = buttons[v[0]];
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
        b.textContent = (on ? '✓ ' : '') + v[1];
        b.style.fontWeight = on ? '600' : 'normal';
        b.style.borderWidth = on ? '2px' : '1px';
        b.style.background = on && tinted ? tinted : 'transparent';
      });
    }
    function store(verdict, note, previous) {                // optimistic: marked at once, put back if the host refuses
      state.verdict = verdict; state.note = note; mark(); showNote(); say('');
      rememberJudgement(take, { verdict: verdict, note: note });
      var body = { take: take, verdict: verdict }; if (note) body.note = note;
      try {
        fetch('judge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
          .then(function (r) { if (!r.ok) throw new Error('refused'); }).then(null, function () {
            state.verdict = previous.verdict; state.note = previous.note;
            rememberJudgement(take, previous.verdict ? previous : {});
            mark(); showNote(); say('Not saved: the host did not take it.');
          });
      } catch (e) { say('Not saved.'); }
    }
    function btn(label) {
      var b = document.createElement('button');
      b.type = 'button'; b.textContent = label;
      b.style.cssText = 'font:inherit;color:inherit;background:transparent;border:1px solid ' + (colour || 'currentColor') +
        ';border-radius:.4em;padding:.35em .7em;min-height:40px;cursor:pointer';
      return b;
    }
    VERDICTS.forEach(function (v) {
      var b = btn(v[1]); buttons[v[0]] = b;
      b.onclick = function () {
        try {
          if (state.verdict === v[0]) return;               // the marked one again: leave it
          store(v[0], input ? input.value.trim() : state.note, { verdict: state.verdict, note: state.note });
        } catch (e) {}
      };
      row.appendChild(b);
    });
    var link = document.createElement('button');
    link.type = 'button'; link.textContent = 'note';
    link.style.cssText = 'font:inherit;color:inherit;background:none;border:0;padding:.5em .3em;min-height:40px;text-decoration:underline;cursor:pointer;opacity:.85';
    link.onclick = function () {
      try {
        if (input) { input.focus(); return; }
        input = document.createElement('input'); input.type = 'text'; input.maxLength = 500; input.value = state.note;
        input.setAttribute('aria-label', 'Note on this result');
        input.style.cssText = 'font:inherit;color:inherit;background:transparent;border:1px solid ' + (colour || 'currentColor') +
          ';border-radius:.4em;padding:.35em .5em;min-height:40px;flex:1 1 12em;min-width:0;box-sizing:border-box';
        var save = btn('Save');
        save.onclick = function () {
          try {
            if (!state.verdict) { say('Choose Fair, Too harsh or Too generous first; the note goes with it.'); return; }
            store(state.verdict, input.value.trim(), { verdict: state.verdict, note: state.note });
          } catch (e) {}
        };
        field.style.cssText = 'display:flex;flex-wrap:wrap;gap:.4em;margin-top:.4em';
        field.appendChild(input); field.appendChild(save);
        input.focus();
      } catch (e) {}
    };
    row.appendChild(link);
    mark(); showNote();
    box.appendChild(q); box.appendChild(row); box.appendChild(shown); box.appendChild(field); box.appendChild(msg);
    element.appendChild(box);
  }
  function judgeResult(take, element) {
    try {
      if (!element || !take) return;
      judgingOn().then(function (on) {
        if (!on) return;                                    // judging is off: the element stays empty
        var c = judgeCache[take];
        if (c && !c.then) { drawJudge(take, element, c); return; }
        if (!c) {
          c = fetch('judgement?take=' + encodeURIComponent(take)).then(function (r) { return r.ok ? r.json() : {}; })
            .then(function (j) { return j || {}; }, function () { return {}; });
          rememberJudgement(take, c);
          c.then(function (j) { if (judgeCache[take] === c) rememberJudgement(take, j); });
        }
        c.then(function (j) { drawJudge(take, element, j); });
      }).then(null, function () {});
    } catch (e) {}
  }

  // ---- lists() ----
  function lists() { return fetch('lists').then(function (r) { return r.json(); }); }

  // ---- wordLists() ----   [{name, lang, words:[text, ...]}]: the lists offered under "Upload a list of words"
  function wordLists() { return fetch('wordlists').then(function (r) { if (!r.ok) throw new Error('no word lists'); return r.json(); }); }

  window.NeolingoHost = { record: record, speak: speak, lists: lists, wordLists: wordLists, playTake: playTake, showTake: showTake, judgeResult: judgeResult,
                          _wav16: wav16, _resample: resample, _parseWav: parseWav, _peaks: peaks, _reduce: reduce };
})();
