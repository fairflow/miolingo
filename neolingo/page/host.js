// The real host's own script: window.NeolingoHost = { record, speak, lists, playTake, showTake }.
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
      if (!r.ok) throw new Error(failMsg);
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

  // ---- lists() ----
  function lists() { return fetch('lists').then(function (r) { return r.json(); }); }

  window.NeolingoHost = { record: record, speak: speak, lists: lists, playTake: playTake, showTake: showTake,
                          _wav16: wav16, _resample: resample, _parseWav: parseWav, _peaks: peaks, _reduce: reduce };
})();
