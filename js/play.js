/* Fox Lessons — playable instruments (guitar, bass, drums, piano).
   No samples, no libraries: strings are Karplus-Strong physical models,
   drums are synthesized from oscillators and shaped noise, keys are a
   two-op FM tine. Everything hangs off one master chain feeding an
   analyser, and window.__foxAudio exposes level()/pitch01() so the
   cymatics canvas in base.html can answer what gets played.
   Progressive: the whole section is display:none without the .js flag,
   and this file no-ops without Web Audio. First tap is the audio gesture. */
(function () {
  'use strict';
  var strip = document.querySelector('[data-play]');
  if (!strip) return;
  var AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return;

  var actx = null, master = null, analyser = null, tbuf = null, noiseBuf = null;
  var lastFreq = 0, lastFreqAt = 0;

  function ensureCtx() {
    if (!actx) {
      actx = new AC();
      master = actx.createGain();
      master.gain.value = 0.9;
      analyser = actx.createAnalyser();
      analyser.fftSize = 512;
      tbuf = new Uint8Array(analyser.fftSize);
      master.connect(analyser);
      analyser.connect(actx.destination);
    }
    if (actx.state === 'suspended') actx.resume();
    return actx;
  }

  function noteOn(freq) { lastFreq = freq; lastFreqAt = performance.now(); }

  // Bridge for the cymatics ground: RMS level plus a rough log-pitch of the
  // last note, decaying so the plate settles after the sound does.
  window.__foxAudio = {
    level: function () {
      if (!analyser) return 0;
      analyser.getByteTimeDomainData(tbuf);
      var s = 0, n = 0;
      for (var i = 0; i < tbuf.length; i += 4) { var v = (tbuf[i] - 128) / 128; s += v * v; n++; }
      return Math.min(1, Math.sqrt(s / n) * 3.2);
    },
    pitch01: function () {
      if (!lastFreq) return 0;
      var age = (performance.now() - lastFreqAt) / 1000;
      var d = Math.max(0, 1 - age * 0.45);
      var p = Math.log(lastFreq / 40) / Math.log(1000 / 40);
      return Math.max(0, Math.min(1, p)) * d;
    }
  };

  function noise() {
    if (!noiseBuf) {
      var sr = actx.sampleRate, len = sr;
      noiseBuf = actx.createBuffer(1, len, sr);
      var d = noiseBuf.getChannelData(0);
      for (var i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    }
    var src = actx.createBufferSource();
    src.buffer = noiseBuf;
    src.loop = true;
    src.loopStart = 0; src.loopEnd = 1;
    return src;
  }

  /* ---- Karplus-Strong plucked string (guitar + bass) ---- */
  function pluck(freq, decay, bright, gain, pan, dur) {
    var ctx = ensureCtx(), sr = ctx.sampleRate;
    var N = Math.round(sr / freq), len = Math.round(sr * dur);
    var data = new Float32Array(len);
    var prev = 0;
    for (var i = 0; i < N; i++) {                    // pick: lowpassed noise burst
      var w = Math.random() * 2 - 1;
      prev = prev + (w - prev) * (0.3 + 0.65 * bright);
      data[i] = prev;
    }
    for (var k = N; k < len; k++) data[k] = decay * 0.5 * (data[k - N] + data[k - N + 1]);
    var b = ctx.createBuffer(1, len, sr);
    b.getChannelData(0).set(data);
    var src = ctx.createBufferSource(); src.buffer = b;
    var g = ctx.createGain(); g.gain.value = gain;
    src.connect(g);
    if (ctx.createStereoPanner) {
      var p = ctx.createStereoPanner(); p.pan.value = pan;
      g.connect(p); p.connect(master);
    } else { g.connect(master); }
    src.start();
    noteOn(freq);
  }

  /* ---- drum voices ---- */
  var drums = {
    kick: function (t) {
      var o = actx.createOscillator(), g = actx.createGain();
      o.frequency.setValueAtTime(155, t);
      o.frequency.exponentialRampToValueAtTime(44, t + 0.12);
      g.gain.setValueAtTime(1.0, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.42);
      o.connect(g); g.connect(master); o.start(t); o.stop(t + 0.45);
      noteOn(60);
    },
    snare: function (t) {
      var n = noise(), bp = actx.createBiquadFilter(), g = actx.createGain();
      bp.type = 'bandpass'; bp.frequency.value = 1800; bp.Q.value = 0.9;
      g.gain.setValueAtTime(0.7, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.19);
      n.connect(bp); bp.connect(g); g.connect(master); n.start(t); n.stop(t + 0.2);
      var o = actx.createOscillator(), og = actx.createGain();
      o.type = 'triangle'; o.frequency.value = 187;
      og.gain.setValueAtTime(0.5, t);
      og.gain.exponentialRampToValueAtTime(0.001, t + 0.08);
      o.connect(og); og.connect(master); o.start(t); o.stop(t + 0.1);
      noteOn(190);
    },
    hat: function (t) {
      var n = noise(), hp = actx.createBiquadFilter(), g = actx.createGain();
      hp.type = 'highpass'; hp.frequency.value = 7200;
      g.gain.setValueAtTime(0.35, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.06);
      n.connect(hp); hp.connect(g); g.connect(master); n.start(t); n.stop(t + 0.08);
      noteOn(900);
    },
    crash: function (t) {
      var n = noise(), hp = actx.createBiquadFilter(), g = actx.createGain();
      hp.type = 'highpass'; hp.frequency.value = 4600;
      g.gain.setValueAtTime(0.5, t);
      g.gain.exponentialRampToValueAtTime(0.001, t + 1.3);
      n.connect(hp); hp.connect(g); g.connect(master); n.start(t); n.stop(t + 1.35);
      [521, 843].forEach(function (f) {
        var o = actx.createOscillator(), og = actx.createGain(), ohp = actx.createBiquadFilter();
        o.type = 'square'; o.frequency.value = f;
        ohp.type = 'highpass'; ohp.frequency.value = 3800;
        og.gain.setValueAtTime(0.12, t);
        og.gain.exponentialRampToValueAtTime(0.001, t + 0.7);
        o.connect(ohp); ohp.connect(og); og.connect(master); o.start(t); o.stop(t + 0.75);
      });
      noteOn(600);
    }
  };

  /* ---- FM tine keys (piano) ---- */
  function key(freq) {
    var ctx = ensureCtx(), t = ctx.currentTime;
    var car = ctx.createOscillator(), mod = ctx.createOscillator();
    car.frequency.value = freq; mod.frequency.value = freq;
    var mg = ctx.createGain();
    mg.gain.setValueAtTime(freq * 2.1, t);
    mg.gain.exponentialRampToValueAtTime(1, t + 0.35);
    mod.connect(mg); mg.connect(car.frequency);
    var g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.45, t + 0.005);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 1.5);
    car.connect(g); g.connect(master);
    car.start(t); mod.start(t); car.stop(t + 1.55); mod.stop(t + 1.55);
    noteOn(freq);
  }

  /* ---- visual feedback ---- */
  function flash(el, cls, ms) {
    el.classList.remove(cls);
    void el.offsetWidth;                             // restart the animation
    el.classList.add(cls);
    clearTimeout(el._ft);
    el._ft = setTimeout(function () { el.classList.remove(cls); }, ms);
  }

  function fireString(el) {
    pluck(+el.dataset.freq, +el.dataset.decay, +el.dataset.bright,
          +el.dataset.gain, +el.dataset.pan || 0, +el.dataset.dur || 2.5);
    flash(el, 'ringing', 500);
  }
  function firePad(el) { ensureCtx(); drums[el.dataset.hit](actx.currentTime); flash(el, 'hit', 180); }
  function fireKey(el) { key(+el.dataset.freq); flash(el, 'down', 180); }

  /* ---- pointer wiring ---- */
  var stringsBox = strip.querySelector('.play-strings');
  if (stringsBox) {
    var down = false, lastEl = null;
    function strumAt(e) {
      var el = document.elementFromPoint(e.clientX, e.clientY);
      el = el && el.closest && el.closest('.pstring');
      if (el && el !== lastEl) { lastEl = el; fireString(el); }
    }
    stringsBox.addEventListener('pointerdown', function (e) {
      down = true; lastEl = null; strumAt(e); e.preventDefault();
    });
    stringsBox.addEventListener('pointermove', function (e) { if (down) strumAt(e); });
    window.addEventListener('pointerup', function () { down = false; lastEl = null; });
    // click still lands for keyboard activation (Enter / Space on the buttons)
    stringsBox.addEventListener('click', function (e) {
      var el = e.target.closest && e.target.closest('.pstring');
      if (el && e.detail === 0) fireString(el);      // keyboard-originated only
    });
  }
  strip.querySelectorAll('.ppad').forEach(function (el) {
    el.addEventListener('click', function () { firePad(el); });
  });
  strip.querySelectorAll('.pkey').forEach(function (el) {
    el.addEventListener('pointerdown', function (e) { fireKey(el); e.preventDefault(); });
    el.addEventListener('click', function (e) { if (e.detail === 0) fireKey(el); });
  });

  /* ---- computer-keyboard wiring, only while the strip is on screen ---- */
  var onScreen = false;
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      onScreen = entries[0].isIntersecting;
    }, { threshold: 0.15 }).observe(strip);
  } else { onScreen = true; }

  var strings = Array.prototype.slice.call(strip.querySelectorAll('.pstring'));
  var padByKey = {};
  strip.querySelectorAll('.ppad').forEach(function (el, i) {
    padByKey[(el.dataset.key || '').toLowerCase()] = el;
    padByKey[String(i + 1)] = el;
  });
  var keyByChar = {};
  strip.querySelectorAll('.pkey').forEach(function (el) {
    if (el.dataset.key) keyByChar[el.dataset.key.toLowerCase()] = el;
  });

  window.addEventListener('keydown', function (e) {
    if (!onScreen || e.repeat || e.metaKey || e.ctrlKey || e.altKey) return;
    var tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    var ch = e.key.toLowerCase();
    if (strings.length) {
      var idx = parseInt(ch, 10) - 1;
      if (idx >= 0 && idx < strings.length) { fireString(strings[idx]); return; }
    }
    if (padByKey[ch]) { firePad(padByKey[ch]); return; }
    if (keyByChar[ch]) { fireKey(keyByChar[ch]); }
  });
})();
