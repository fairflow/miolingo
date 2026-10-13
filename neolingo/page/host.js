// The real host's own script: window.NeolingoHost = { record, speak, lists }.
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
            var blob = wav16(resample(chunks, total, rate));
            fetch('take', { method: 'POST', headers: { 'Content-Type': 'audio/wav' }, body: blob })
              .then(function (r) { return r.json(); })
              .then(function (j) {
                if (!j.take) throw new Error(j.err || 'the host refused the recording');
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
  var player = null, playerUrl = null;
  function stopPlayer() {
    if (player) { try { player.pause(); } catch (e) {} player = null; }
    if (playerUrl) { URL.revokeObjectURL(playerUrl); playerUrl = null; }
  }
  function speak(text, variant, slow) {
    stopPlayer();
    var url = 'speak?text=' + encodeURIComponent(text) + '&variant=' + encodeURIComponent(variant || 'fr-fr') + '&slow=' + (slow ? 'true' : 'false');
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('the host could not make the speech');
      return r.blob();
    }).then(function (blob) {
      stopPlayer();
      var u = playerUrl = URL.createObjectURL(blob), a = player = new Audio(u);
      return new Promise(function (resolve, reject) {
        a.onended = function () { if (player === a) stopPlayer(); resolve(); };
        a.onerror = function () { if (player === a) stopPlayer(); reject(new Error('the browser could not play the speech')); };
        var p = a.play(); if (p && p.catch) p.catch(reject);
      });
    });
  }

  // ---- lists() ----
  function lists() { return fetch('lists').then(function (r) { return r.json(); }); }

  window.NeolingoHost = { record: record, speak: speak, lists: lists, _wav16: wav16, _resample: resample };
})();
