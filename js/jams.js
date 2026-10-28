/* Jams directory (/jams/): tonight first, the hub filters, the map.
   Progressive enhancement only. Every card ships in the static HTML,
   grouped Monday first; with JavaScript off the whole list reads, the
   filter bar stays hidden and the map shows its one-line fallback. */
(function () {
  'use strict';

  var DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
  var GROUPS = ['day', 'type', 'genre', 'area', 'skill'];
  var TOGGLES = ['houseband', 'gear', 'songlist', 'allages'];
  var LEAFLET = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/';
  var LEAFLET_JS_SRI = 'sha384-cxOPjt7s7Iz04uaHJceBmS+qpjv2JkIHNVcuOrM+YHwZOmJGBXI00mdUXEq65HTH';
  var LEAFLET_CSS_SRI = 'sha384-sHL9NAb7lN7rfvG5lfHpm643Xkcjzp4jFvuavGOndn6pjVqS6ny56CAt3nsEVT4H';
  var DAY_MS = 86400000;

  var list = document.getElementById('jams-list');
  if (!list) return;

  // "Tonight" is the weekday in Denver, whatever zone the visitor is in.
  var TODAY = (function () {
    try {
      var name = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Denver', weekday: 'short' }).format(new Date());
      var key = name.slice(0, 3).toLowerCase();
      if (DAY_KEYS.indexOf(key) >= 0) return key;
    } catch (e) { /* fall through to the device clock */ }
    return DAY_KEYS[(new Date().getDay() + 6) % 7];
  })();

  // Visible card ids after filtering; null means every card.
  var visibleSlugs = null;

  markNextDates();
  moveTonightUp();
  if (document.getElementById('jams-filters')) initFilters();
  initMap();

  function toArray(nodes) { return Array.prototype.slice.call(nodes); }

  // Next dates. These must give the same answer as next_occurrence() in
  // _src/lib/jams.py, which dates the structured data. Days are whole UTC
  // day numbers, so clock changes never shift a date.
  function denverToday() {
    try {
      var parts = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'America/Denver', year: 'numeric', month: '2-digit', day: '2-digit'
      }).formatToParts(new Date());
      var get = function (type) {
        return parseInt(parts.filter(function (p) { return p.type === type; })[0].value, 10);
      };
      return Date.UTC(get('year'), get('month') - 1, get('day')) / DAY_MS;
    } catch (e) {
      var d = new Date();
      return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / DAY_MS;
    }
  }

  function weekdayOf(dn) { return (new Date(dn * DAY_MS).getUTCDay() + 6) % 7; }
  function monthOf(dn) { return new Date(dn * DAY_MS).getUTCMonth() + 1; }

  function parseISO(s) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || '');
    return m ? Date.UTC(+m[1], +m[2] - 1, +m[3]) / DAY_MS : null;
  }

  function nthWeekdayDates(y, m, dow, ns) {
    var first = Date.UTC(y, m - 1, 1) / DAY_MS;
    var d = first + (((dow - weekdayOf(first)) % 7) + 7) % 7;
    var days = [];
    while (monthOf(d) === m) { days.push(d); d += 7; }
    var out = [];
    ns.forEach(function (n) {
      if (n === -1) out.push(days[days.length - 1]);
      else if (n - 1 < days.length) out.push(days[n - 1]);
    });
    return out;
  }

  function nextOccurrence(dow, rule, knownISO, skip, today) {
    var i, d;
    if (rule === 'weekly' || rule === 'biweekly') {
      var first, step;
      if (rule === 'weekly') {
        first = today + (((dow - weekdayOf(today)) % 7) + 7) % 7;
        step = 7;
      } else {
        var known = parseISO(knownISO);
        if (known === null || weekdayOf(known) !== dow) return null;
        first = known - 14 * Math.floor((known - today) / 14);
        step = 14;
      }
      for (i = 0; i < 60; i++) {
        d = first + step * i;
        if (skip.indexOf(monthOf(d)) < 0) return d;
      }
      return null;
    }
    if (rule === 'last' || rule.indexOf('nth:') === 0) {
      var ns = rule === 'last' ? [-1] : rule.slice(4).split(',').map(function (x) {
        return x === 'last' ? -1 : parseInt(x, 10);
      });
      var start = new Date(today * DAY_MS);
      var y = start.getUTCFullYear(), m = start.getUTCMonth() + 1;
      for (i = 0; i < 14; i++) {
        if (skip.indexOf(m) < 0) {
          var hits = nthWeekdayDates(y, m, dow, ns)
            .filter(function (x) { return x >= today; })
            .sort(function (a, b) { return a - b; });
          if (hits.length) return hits[0];
        }
        if (m === 12) { y += 1; m = 1; } else { m += 1; }
      }
    }
    return null;
  }

  function markNextDates() {
    var fmt;
    try {
      fmt = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', weekday: 'short', month: 'short', day: 'numeric' });
    } catch (e) { return; }
    var today = denverToday();
    var tpl = list.getAttribute('data-next') || '{date}';
    toArray(list.querySelectorAll('.jam-card[data-rule]')).forEach(function (card) {
      var line = card.querySelector('.jam-next');
      var dow = DAY_KEYS.indexOf(card.getAttribute('data-day'));
      if (!line || dow < 0) return;
      var skip = (card.getAttribute('data-skip') || '').split(',').filter(Boolean).map(Number);
      var next = nextOccurrence(dow, card.getAttribute('data-rule'), card.getAttribute('data-known'), skip, today);
      if (next === null) return;
      if (next === today || next === today + 1) {
        line.textContent = list.getAttribute(next === today ? 'data-tonight' : 'data-tomorrow');
        line.classList.add('jam-next--soon');
      } else {
        line.textContent = tpl.replace('{date}', fmt.format(new Date(next * DAY_MS)));
      }
      line.hidden = false;
    });
  }

  function moveTonightUp() {
    var group = list.querySelector('.jams-night[data-night="' + TODAY + '"]');
    if (group) {
      if (group !== list.firstElementChild) list.insertBefore(group, list.firstElementChild);
      var heading = group.querySelector('.jams-night__h');
      var label = list.getAttribute('data-tonight');
      if (heading && label) {
        var badge = document.createElement('span');
        badge.className = 'jams-tonight';
        badge.textContent = label;
        heading.appendChild(document.createTextNode(' '));
        heading.appendChild(badge);
      }
    }
    // A shared #slug link still lands on its card after the reorder.
    if (location.hash.length > 1) {
      var target = null;
      try { target = document.getElementById(decodeURIComponent(location.hash.slice(1))); } catch (e) { /* bad hash */ }
      if (target && list.contains(target)) {
        requestAnimationFrame(function () { target.scrollIntoView(); });
      }
    }
  }

  function initFilters() {
    var bar = document.getElementById('jams-filters');
    var cards = toArray(list.querySelectorAll('.jam-card'));
    var nights = toArray(list.querySelectorAll('.jams-night'));
    var chips = toArray(bar.querySelectorAll('[data-group]'));
    var barClear = bar.querySelector('.jams-clear');
    var count = document.getElementById('jams-count');
    var empty = document.getElementById('jams-empty');
    var skillNote = document.getElementById('jams-skillnote');
    var more = document.getElementById('jams-filters-more');
    var heading = document.getElementById('jams-filters-h');
    var known = {};
    var state = {};

    chips.forEach(function (chip) {
      var g = chip.getAttribute('data-group');
      (known[g] = known[g] || {})[chip.getAttribute('data-value')] = true;
    });

    function readURL() {
      var params = new URLSearchParams(location.search);
      GROUPS.forEach(function (g) {
        var raw = params.get(g);
        // Values with no matching button (a hand-edited link) are dropped,
        // so the pressed buttons and the count always agree.
        state[g] = raw ? raw.split(',').filter(function (v) { return known[g] && known[g][v]; }) : [];
      });
      TOGGLES.forEach(function (t) { state[t] = params.get(t) === '1'; });
    }

    function writeURL() {
      var params = new URLSearchParams(location.search);
      var parts = [];
      params.forEach(function (v, k) {
        if (GROUPS.indexOf(k) < 0 && TOGGLES.indexOf(k) < 0) {
          parts.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
        }
      });
      GROUPS.forEach(function (g) {
        if (state[g].length) parts.push(g + '=' + state[g].map(encodeURIComponent).join(','));
      });
      TOGGLES.forEach(function (t) { if (state[t]) parts.push(t + '=1'); });
      history.replaceState(null, '', location.pathname + (parts.length ? '?' + parts.join('&') : ''));
    }

    function anyActive() {
      return GROUPS.some(function (g) { return state[g].length > 0; }) ||
        TOGGLES.some(function (t) { return state[t]; });
    }

    function skillMatches(skill, bands) {
      if (skill === 'none') return false;
      var n = parseInt(skill, 10);
      return bands.some(function (b) {
        if (b === '1-2') return n <= 2;
        if (b === '3') return n === 3;
        return n >= 4;
      });
    }

    function matches(card) {
      var d = card.dataset;
      var days = state.day.map(function (v) { return v === 'tonight' ? TODAY : v; });
      if (days.length && days.indexOf(d.day) < 0) return false;
      if (state.type.length && state.type.indexOf(d.format) < 0) return false;
      if (state.genre.length) {
        var genres = (d.genres || '').split(' ');
        if (!state.genre.some(function (g) { return genres.indexOf(g) >= 0; })) return false;
      }
      if (state.area.length && state.area.indexOf(d.area) < 0) return false;
      if (state.skill.length && !skillMatches(d.skill, state.skill)) return false;
      return TOGGLES.every(function (t) { return !state[t] || d[t] === '1'; });
    }

    function apply() {
      var shown = [];
      cards.forEach(function (card) {
        var ok = matches(card);
        card.hidden = !ok;
        if (ok) shown.push(card.id);
      });
      nights.forEach(function (night) {
        var shownHere = night.querySelectorAll('.jam-card:not([hidden])').length;
        night.hidden = shownHere === 0;
        var label = night.querySelector('.jams-night__n');
        if (label) label.textContent = shownHere + ' ' + list.getAttribute(shownHere === 1 ? 'data-one' : 'data-many');
      });
      var n = shown.length;
      count.textContent = n + ' ' + count.getAttribute(n === 1 ? 'data-one' : 'data-many');
      empty.hidden = n > 0;
      skillNote.hidden = state.skill.length === 0;
      barClear.setAttribute('aria-disabled', anyActive() ? 'false' : 'true');
      chips.forEach(function (chip) {
        var g = chip.getAttribute('data-group');
        var on = TOGGLES.indexOf(g) >= 0 ? state[g] : state[g].indexOf(chip.getAttribute('data-value')) >= 0;
        chip.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      visibleSlugs = anyActive() ? shown : null;
      document.dispatchEvent(new CustomEvent('jams:filtered'));
    }

    function toggle(group, value) {
      if (TOGGLES.indexOf(group) >= 0) {
        state[group] = !state[group];
        return;
      }
      var i = state[group].indexOf(value);
      if (i >= 0) state[group].splice(i, 1);
      else state[group].push(value);
    }

    function clearAll() {
      GROUPS.forEach(function (g) { state[g] = []; });
      TOGGLES.forEach(function (t) { state[t] = false; });
    }

    bar.addEventListener('click', function (e) {
      var chip = e.target.closest('[data-group]');
      if (!chip) return;
      toggle(chip.getAttribute('data-group'), chip.getAttribute('data-value'));
      writeURL();
      apply();
    });

    toArray(document.querySelectorAll('[data-jams-clear]')).forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.getAttribute('aria-disabled') === 'true') return;
        clearAll();
        writeURL();
        apply();
        // The empty-state button disappears once the list is back; keep
        // keyboard focus somewhere sensible.
        if (!bar.contains(btn)) heading.focus();
      });
    });

    readURL();
    apply();
    var onlyTonight = state.day.length === 1 && state.day[0] === 'tonight' &&
      ['type', 'genre', 'area', 'skill'].every(function (g) { return !state[g].length; }) &&
      TOGGLES.every(function (t) { return !state[t]; });
    if (window.matchMedia('(min-width: 760px)').matches || (anyActive() && !onlyTonight)) {
      more.open = true;
    }
  }

  function initMap() {
    var box = document.getElementById('jams-map');
    var data = document.getElementById('jams-pins');
    if (!box || !data) return;
    var pins = [];
    try { pins = JSON.parse(data.textContent); } catch (e) { /* no pins */ }
    if (!pins.length) return;
    var errorLine = document.getElementById('jams-map-error');
    var started = false;

    function fail() {
      box.hidden = true;
      if (errorLine) errorLine.hidden = false;
    }

    function start() {
      if (started) return;
      started = true;
      var css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = LEAFLET + 'leaflet.css';
      css.integrity = LEAFLET_CSS_SRI;
      css.crossOrigin = 'anonymous';
      document.head.appendChild(css);
      var js = document.createElement('script');
      js.src = LEAFLET + 'leaflet.js';
      js.integrity = LEAFLET_JS_SRI;
      js.crossOrigin = 'anonymous';
      js.onload = function () {
        try { draw(window.L); } catch (e) { fail(); }
      };
      js.onerror = fail;
      document.head.appendChild(js);
    }

    // Load only once the map nears the viewport, so it never slows the list.
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        if (entries.some(function (en) { return en.isIntersecting; })) {
          io.disconnect();
          start();
        }
      }, { rootMargin: '400px 0px' });
      io.observe(box);
    } else {
      start();
    }

    function token(name, fallback) {
      var v = getComputedStyle(document.documentElement).getPropertyValue(name);
      return (v && v.trim()) || fallback;
    }

    function popup(nights) {
      var wrap = document.createElement('div');
      wrap.className = 'jams-pop';
      nights.forEach(function (p) {
        var item = document.createElement('p');
        var link = document.createElement('a');
        link.href = '#' + p.slug;
        link.textContent = p.name;
        var venue = document.createElement('span');
        venue.textContent = p.venue;
        var when = document.createElement('span');
        when.textContent = p.when;
        item.appendChild(link);
        item.appendChild(venue);
        item.appendChild(when);
        wrap.appendChild(item);
      });
      return wrap;
    }

    function draw(L) {
      var map = L.map(box, { scrollWheelZoom: false, zoomSnap: 0.25 }).setView([39.74, -104.99], 9);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(map);
      // Several nights can share a venue: one pin per spot, every night at
      // that spot in its popup.
      var spots = {};
      pins.forEach(function (p) {
        var key = p.lat.toFixed(5) + ',' + p.lng.toFixed(5);
        (spots[key] = spots[key] || { lat: p.lat, lng: p.lng, nights: [] }).nights.push(p);
      });
      var style = {
        radius: 7, weight: 2, fillOpacity: 0.9,
        color: token('--ink', '#0A0B0D'), fillColor: token('--accent-on-light', '#1F6FA8')
      };
      var layer = L.layerGroup().addTo(map);
      var all = Object.keys(spots).map(function (key) {
        var spot = spots[key];
        spot.marker = L.circleMarker([spot.lat, spot.lng], style);
        return spot;
      });
      function render() {
        layer.clearLayers();
        var keep = null;
        if (visibleSlugs) {
          keep = {};
          visibleSlugs.forEach(function (s) { keep[s] = true; });
        }
        var bounds = [];
        all.forEach(function (spot) {
          var nights = keep ? spot.nights.filter(function (p) { return keep[p.slug]; }) : spot.nights;
          if (!nights.length) return;
          spot.marker.bindPopup(popup(nights));
          layer.addLayer(spot.marker);
          bounds.push([spot.lat, spot.lng]);
        });
        if (bounds.length) map.fitBounds(bounds, { padding: [28, 28], maxZoom: 14 });
      }
      render();
      document.addEventListener('jams:filtered', render);
    }
  }
})();
