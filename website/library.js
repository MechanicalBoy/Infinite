(function () {
  var stage = document.getElementById('lib-stage'),
      grid = document.getElementById('grid'),
      chipsEl = document.getElementById('chips'),
      emptyEl = document.getElementById('empty'),
      viewEl = document.getElementById('view'),
      hudWrap = document.getElementById('lib-hud-wrap'),
      hudCatIc = document.getElementById('lib-hud-cat-ic'),
      hudTitle = document.getElementById('lib-hud-title'),
      hudMeta = document.getElementById('lib-hud-meta'),
      hudCopy = document.getElementById('lib-hud-copy'),
      hudDl = document.getElementById('lib-hud-dl'),
      dotsWrap = document.getElementById('lib-dots');

  if (!stage || !grid) return;

  var IC_COPY = '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="7.5" y="7.5" width="9" height="9" rx="2"/><path d="M4.5 12.5V5.5A2 2 0 0 1 6.5 3.5h7"/></svg>';
  var IC_CHECK = '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4.5 10.5 8.2 14.2 15.5 6.5"/></svg>';
  var IC_DL = '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 3.5v9.5m0 0-3.5-3.5M10 13l3.5-3.5M4 16.5h12"/></svg>';
  var IC_OPEN = '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6.5 13.5 13.5 6.5M8 6.5h5.5V12"/></svg>';
  var IC_CHEV = '<svg class="select-chev" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 8l4 4 4-4"/></svg>';

  var CAT_ICONS = {
    'All': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="5.4" cy="5.4" r="1.1" fill="currentColor" stroke="none"/><circle cx="10" cy="5.4" r="1.1" fill="currentColor" stroke="none"/><circle cx="14.6" cy="5.4" r="1.1" fill="currentColor" stroke="none"/><circle cx="5.4" cy="10" r="1.1" fill="currentColor" stroke="none"/><circle cx="10" cy="10" r="1.1" fill="currentColor" stroke="none"/><circle cx="14.6" cy="10" r="1.1" fill="currentColor" stroke="none"/><circle cx="5.4" cy="14.6" r="1.1" fill="currentColor" stroke="none"/><circle cx="10" cy="14.6" r="1.1" fill="currentColor" stroke="none"/><circle cx="14.6" cy="14.6" r="1.1" fill="currentColor" stroke="none"/></svg>',
    'Templates': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="3.5" width="9" height="9" rx="2"/><rect x="7.5" y="7.5" width="9" height="9" rx="2"/></svg>',
    'Community': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="10" cy="10" r="7.2"/><circle cx="10" cy="10" r="2.5"/><circle cx="10" cy="10" r="0.9" fill="currentColor" stroke="none"/><path d="M5.2 12.4A5.4 5.4 0 0 0 7.6 14.8"/><path d="M14.8 7.6A5.4 5.4 0 0 0 12.4 5.2"/></svg>',
    'Pixel': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 3 11.7 8.3 17 10 11.7 11.7 10 17 8.3 11.7 3 10 8.3 8.3Z"/></svg>',
    'Audio FX': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 8v4M7 5v10M10 3v14M13 6v8M16 8.5v3"/></svg>',
    'Audio Effects': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 8v4M7 5v10M10 3v14M13 6v8M16 8.5v3"/></svg>',
    'Synths': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="14" height="10" rx="2"/><path d="M7.7 5v10M12.3 5v10"/></svg>',
    'Notes': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8.5 14.5V4.5l7-1.5v10"/><circle cx="6.5" cy="14.5" r="2" fill="currentColor" stroke="none"/><circle cx="13.5" cy="13" r="2" fill="currentColor" stroke="none"/></svg>',
    'Sketch': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 4.5H5.5A1.5 1.5 0 0 0 4 6v8.5A1.5 1.5 0 0 0 5.5 16H14a1.5 1.5 0 0 0 1.5-1.5V11"/><path d="M15.2 3.8a1.4 1.4 0 0 1 1 2.4L9.4 13l-2.6.7.7-2.6 6.8-6.8a1.4 1.4 0 0 1 .9-.5Z"/></svg>',
    'Sketch 3D': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 3.2 16.2 6.7V13.4L10 16.9 3.8 13.4V6.7Z"/><path d="M3.8 6.7 10 10.05 16.2 6.7M10 10.05V16.9"/></svg>',
    'AI Skills': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="14" height="14" rx="2"/><path d="M3 10h14M10 3v14"/><circle cx="6.5" cy="6.5" r="1.4" fill="currentColor" stroke="none"/><circle cx="13.5" cy="13.5" r="1.4" fill="currentColor" stroke="none"/></svg>',
    'Extensions': '<svg class="lib-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.2 10c1.8-5.5 3.2-5.5 4.4 0s2.8 5.5 4.4 0 3.2-5.5 4.4 0"/></svg>'
  };

  var CATS = ['Templates', 'Community', 'Pixel', 'Audio FX', 'Synths', 'Notes', 'Sketch', 'AI Skills', 'Extensions'];
  var COLOUR = {
    'Templates': 'var(--accent)',
    'Pixel': 'var(--accent)',
    'Audio FX': 'var(--cat-synths)',
    'Audio Effects': 'var(--cat-synths)',
    'Synths': 'var(--cat-3d)',
    'Notes': 'var(--cat-modulators)',
    'Sketch': 'var(--signal)',
    'Sketch 3D': 'var(--cat-3d)',
    'Community': 'var(--signal)',
    'AI Skills': 'var(--signal)',
    'Extensions': 'var(--cat-prediction)'
  };

  var items = [];
  var allCards = [];
  var visibleCards = [];
  var activeFilter = 'All';
  var activeIdx = 0;
  var dragOffset = 0;
  var isDragging = false;
  var dragMoved = false;
  var startX = 0, startY = 0, lastX = 0, lastT = 0, vx = 0;
  var wheelAccum = 0, wheelLock = 0;
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var params = new URLSearchParams(window.location.search);
  var qView = params.get('view');
  var mode = (qView === 'stack' || qView === 'grid' || qView === 'fan') ? qView : 'fan';
  var qTheme = params.get('mode');
  if (qTheme === 'midnight' || qTheme === 'paper' || qTheme === 'mist') {
    document.documentElement.setAttribute('data-mode', qTheme);
  }

  function esc(s) {
    return String(s || '').replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function normCat(cat) {
    if (!cat) return 'Pixel';
    if (cat === 'Audio Effects') return 'Audio FX';
    if (cat === 'Sketch 3D') return 'Sketch';
    return cat;
  }

  function catIcon(cat) {
    return CAT_ICONS[cat] || CAT_ICONS[normCat(cat)] || CAT_ICONS['Pixel'];
  }

  function mod(n, m) { return m > 0 ? ((n % m) + m) % m : 0; }

  function circularDelta(idx, center, total) {
    if (total <= 1) return 0;
    var d = idx - center;
    var half = total / 2;
    while (d > half) d -= total;
    while (d <= -half) d += total;
    return d;
  }

  function card(it, i) {
    var rawCat = it.category || 'Pixel';
    var cat = normCat(rawCat);
    var hasCopy = !(it.kind === 'Template' || it.kind === 'Patch' || it.kind === 'Skill' || it.kind === 'Extension');
    var isExt = it.kind === 'Extension';
    var detailHref = 'library/' + esc(it.id) + '.html';

    return '<article class="lib-card" data-cat="' + esc(cat) + '" data-raw-cat="' + esc(rawCat) + '" data-name="' + esc(it.name) + '" data-file="' + esc(it.file) + '" data-has-copy="' + (hasCopy ? '1' : '0') + '" data-ext="' + (isExt ? '1' : '0') + '" style="--cat:' + (COLOUR[rawCat] || COLOUR[cat] || 'var(--accent)') + '; --i:' + Math.min(i, 8) + '">' +
      '<div class="lib-card-shell">' +
        '<div class="lib-card-media">' +
          '<a class="lib-media-link" href="' + detailHref + '" tabindex="-1" aria-hidden="true">' +
            '<img data-src="' + esc(it.preview) + '" alt="" decoding="async" width="720" height="450">' +
          '</a>' +
          '<div class="lib-media-hud">' +
            '<a class="lib-open-pill" href="' + detailHref + '" aria-label="Open ' + esc(it.name) + '" title="Open">' + IC_OPEN + '</a>' +
          '</div>' +
        '</div>' +
        '<div class="lib-card-foot">' +
          '<a class="lib-card-id" href="' + detailHref + '">' +
            '<span class="lib-cat-badge" title="' + esc(rawCat) + '">' + catIcon(rawCat) + '</span>' +
            '<h2 class="lib-card-title">' + esc(it.name) + '</h2>' +
          '</a>' +
          '<div class="lib-acts">' +
            (hasCopy ? '<button class="lib-act-btn lib-copy" type="button" data-file="' + esc(it.file) + '" aria-label="Copy code for ' + esc(it.name) + '" title="Copy code">' + IC_COPY + '</button>' : '') +
            (isExt
              ? '<a class="lib-act-btn lib-dl" href="' + esc(it.file) + '" aria-label="Install ' + esc(it.name) + '" title="Install">' + IC_OPEN + '</a>'
              : '<a class="lib-act-btn lib-dl" href="' + esc(it.file) + '" download aria-label="Download ' + esc(it.name) + '" title="Download">' + IC_DL + '</a>') +
          '</div>' +
        '</div>' +
      '</div>' +
    '</article>';
  }

  function renderDropdown() {
    var cs = ['All'].concat(CATS);
    chipsEl.innerHTML =
      '<button class="lib-select" type="button" aria-haspopup="listbox" aria-expanded="false" aria-label="Filter by category">' +
        '<span class="lib-select-ic">' + catIcon(activeFilter) + '</span>' +
        '<span class="lib-select-val">' + esc(activeFilter) + '</span>' +
        IC_CHEV +
      '</button>' +
      '<div class="lib-menu" role="listbox" aria-label="Category" hidden>' +
        cs.map(function (c) {
          return '<button class="lib-opt" type="button" role="option" aria-selected="' + (c === activeFilter) + '" data-f="' + esc(c) + '">' +
            catIcon(c) +
            '<span>' + esc(c) + '</span>' +
          '</button>';
        }).join('') +
      '</div>';
  }

  function setMenuOpen(open) {
    var m = chipsEl.querySelector('.lib-menu'),
        t = chipsEl.querySelector('.lib-select');
    if (!m || !t) return;
    m.hidden = !open;
    t.setAttribute('aria-expanded', String(open));
  }

  function buildDots() {
    if (!dotsWrap) return;
    dotsWrap.innerHTML = '';
    var total = visibleCards.length;
    if (!total) return;
    var maxDots = Math.min(total, 16);
    for (var i = 0; i < maxDots; i++) {
      (function (slotIdx) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'lib-dot';
        b.setAttribute('aria-label', 'Jump to item');
        b.addEventListener('click', function () {
          var target = Math.round((slotIdx / Math.max(1, maxDots - 1)) * (total - 1));
          goTo(target);
        });
        dotsWrap.appendChild(b);
      })(i);
    }
  }

  function updateHud() {
    var total = visibleCards.length;
    if (!total) return;
    var curIdx = mod(activeIdx, total);
    var c = visibleCards[curIdx];
    var rawCat = c.getAttribute('data-raw-cat') || 'Pixel';
    var name = c.getAttribute('data-name') || '';
    var file = c.getAttribute('data-file') || '';
    var hasCopy = c.getAttribute('data-has-copy') === '1';
    var isExt = c.getAttribute('data-ext') === '1';

    if (hudCatIc) hudCatIc.innerHTML = catIcon(rawCat);
    if (hudTitle) hudTitle.textContent = name;
    if (hudMeta) hudMeta.textContent = rawCat;
    if (hudCopy) {
      hudCopy.hidden = !hasCopy;
      hudCopy.setAttribute('data-file', file);
      hudCopy.setAttribute('aria-label', 'Copy code for ' + name);
    }
    if (hudDl) {
      hudDl.href = file;
      if (isExt) {
        hudDl.removeAttribute('download');
        hudDl.setAttribute('aria-label', 'Install ' + name);
      } else {
        hudDl.setAttribute('download', '');
        hudDl.setAttribute('aria-label', 'Download ' + name);
      }
    }
    if (dotsWrap && dotsWrap.children.length) {
      var dots = dotsWrap.children;
      var activeDot = dots.length <= 1 ? 0 : Math.round((curIdx / Math.max(1, total - 1)) * (dots.length - 1));
      for (var i = 0; i < dots.length; i++) {
        dots[i].classList.toggle('is-on', i === activeDot);
      }
    }
  }

  function rebuildVisible() {
    visibleCards = [];
    allCards.forEach(function (c) {
      var show = activeFilter === 'All' || c.getAttribute('data-cat') === activeFilter;
      c.hidden = !show;
      if (show) visibleCards.push(c);
    });
    emptyEl.hidden = visibleCards.length > 0;
    stage.hidden = visibleCards.length === 0;
    activeIdx = mod(activeIdx, visibleCards.length);

    var valEl = chipsEl.querySelector('.lib-select-val');
    var icEl = chipsEl.querySelector('.lib-select-ic');
    if (valEl) valEl.textContent = activeFilter;
    if (icEl) icEl.innerHTML = catIcon(activeFilter);
    Array.prototype.forEach.call(chipsEl.querySelectorAll('.lib-opt'), function (opt) {
      opt.setAttribute('aria-selected', String(opt.getAttribute('data-f') === activeFilter));
    });

    buildDots();
  }

  function layoutDeck(animate) {
    var total = visibleCards.length;
    stage.setAttribute('data-deck-mode', mode);
    if (hudWrap) hudWrap.hidden = (mode === 'grid' || total === 0);

    if (mode === 'grid' || !total) {
      allCards.forEach(function (c) {
        c.style.transform = '';
        c.style.opacity = '';
        c.style.zIndex = '';
        c.style.pointerEvents = '';
        c.removeAttribute('data-slot');
        c.removeAttribute('aria-hidden');
        var im = c.querySelector('img[data-src]');
        if (im) { im.src = im.getAttribute('data-src'); im.removeAttribute('data-src'); }
      });
      updateHud();
      return;
    }

    var isMobile = window.innerWidth < 680;
    var isTablet = window.innerWidth >= 680 && window.innerWidth < 1040;
    var center = activeIdx - dragOffset;

    visibleCards.forEach(function (c, idx) {
      var d = circularDelta(idx, center, total);
      var abs = Math.abs(d);
      var sign = d < 0 ? -1 : (d > 0 ? 1 : 0);
      var prevD = typeof c._lastD === 'number' ? c._lastD : d;
      c._lastD = d;

      var wrapped = Math.abs(prevD - d) > 3.2;
      if (!animate || wrapped || reduceMotion) {
        c.style.transition = 'none';
      } else {
        c.style.transition = '';
      }

      var tx = 0, ty = 0, tz = 0, rx = 0, ry = 0, rz = 0, sc = 1, op = 1;

      if (mode === 'stack') {
        var stepX = isMobile ? 64 : (isTablet ? 98 : 126);
        var stepY = isMobile ? -18 : -26;
        var focus = Math.max(0, 1 - abs);
        tx = d * stepX + (d > 0 ? (1 - focus) * 28 : (d < 0 ? -(1 - focus) * 28 : 0));
        ty = d * stepY + focus * 10;
        tz = focus * 52 - abs * (isMobile ? 84 : 108);
        ry = -6 * focus + (1 - focus) * -22;
        rx = 2 * focus + (1 - focus) * 6;
        rz = -d * 0.8;
        sc = Math.max(0.74, 1.02 * focus + (1 - focus) * (1 - abs * 0.055));
        op = abs > 3.2 ? 0 : (abs > 2.5 ? Math.max(0, (3.2 - abs) / 0.7) : 1);
      } else {
        var firstStep = isMobile ? 96 : (isTablet ? 168 : 218);
        var tailStep = isMobile ? 48 : (isTablet ? 88 : 118);
        var spread = Math.min(abs, 1) * firstStep + Math.max(0, abs - 1) * tailStep;
        tx = sign * spread;
        ty = Math.pow(abs, 1.3) * (isMobile ? 9 : 14);
        tz = -abs * (isMobile ? 86 : 116);
        ry = -sign * Math.min(abs * (isMobile ? 13 : 16), 34);
        rz = d * (isMobile ? 1.5 : 2.0);
        sc = Math.max(0.74, 1 - abs * 0.065);
        op = abs > 3.2 ? 0 : (abs > 2.5 ? Math.max(0, (3.2 - abs) / 0.7) : 1);
      }

      var dim = Math.min(0.55, Math.max(0, (abs - 0.15) * 0.18));
      c.style.setProperty('--card-dim', dim.toFixed(3));
      c.style.transform = 'translate3d(' + tx.toFixed(1) + 'px,' + ty.toFixed(1) + 'px,' + tz.toFixed(1) + 'px) rotateX(' + rx.toFixed(2) + 'deg) rotateY(' + ry.toFixed(2) + 'deg) rotateZ(' + rz.toFixed(2) + 'deg) scale(' + sc.toFixed(3) + ')';
      c.style.opacity = op.toFixed(3);
      c.style.zIndex = String(Math.max(1, Math.round(100 - abs * 20)));
      c.style.pointerEvents = op < 0.15 ? 'none' : 'auto';

      var slot = abs < 0.35 ? 'active' : (abs < 1.35 ? 'near' : (abs < 2.45 ? 'mid' : 'far'));
      c.setAttribute('data-slot', slot);
      c.setAttribute('aria-hidden', abs > 3.1 ? 'true' : 'false');
      if (abs <= 4.2) {
        var im = c.querySelector('img[data-src]');
        if (im) { im.src = im.getAttribute('data-src'); im.removeAttribute('data-src'); }
      }
    });

    updateHud();
  }

  function stepBy(delta) {
    var total = visibleCards.length;
    if (!total) return;
    activeIdx = mod(activeIdx + delta, total);
    dragOffset = 0;
    layoutDeck(true);
  }

  function goTo(targetIdx) {
    var total = visibleCards.length;
    if (!total) return;
    activeIdx = mod(targetIdx, total);
    dragOffset = 0;
    layoutDeck(true);
  }

  function reshuffleDeck(withPulse) {
    for (var i = allCards.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = allCards[i];
      allCards[i] = allCards[j];
      allCards[j] = tmp;
    }
    allCards.forEach(function (c) { grid.appendChild(c); c._lastD = undefined; });
    activeIdx = 0;
    dragOffset = 0;
    rebuildVisible();
    if (withPulse && !reduceMotion) {
      stage.classList.add('is-shuffling');
      setTimeout(function () { stage.classList.remove('is-shuffling'); }, 460);
    }
    layoutDeck(true);
  }

  function copyDeviceCode(btn) {
    var file = btn.getAttribute('data-file');
    if (!file) return;
    fetch(file).then(function (r) { return r.text(); }).then(function (txt) {
      if (/\.field$/.test(file)) {
        try { txt = JSON.parse(txt).device.code; } catch (x) {}
      }
      return navigator.clipboard.writeText(txt);
    }).then(function () {
      btn.classList.add('done');
      btn.innerHTML = IC_CHECK;
      setTimeout(function () {
        btn.classList.remove('done');
        btn.innerHTML = IC_COPY;
      }, 1400);
    }).catch(function () {});
  }

  /* View switcher (Book / Stack / Grid) */
  if (viewEl) {
    Array.prototype.forEach.call(viewEl.querySelectorAll('[data-view]'), function (btn) {
      var on = btn.getAttribute('data-view') === mode;
      btn.classList.toggle('is-on', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      btn.addEventListener('click', function () {
        mode = btn.getAttribute('data-view') || 'fan';
        Array.prototype.forEach.call(viewEl.querySelectorAll('[data-view]'), function (b) {
          var isSel = b === btn;
          b.classList.toggle('is-on', isSel);
          b.setAttribute('aria-pressed', isSel ? 'true' : 'false');
        });
        allCards.forEach(function (c) { c._lastD = undefined; });
        layoutDeck(true);
      });
    });
  }

  /* Category dropdown events */
  chipsEl.addEventListener('click', function (e) {
    if (e.target.closest('.lib-select')) {
      var m = chipsEl.querySelector('.lib-menu');
      if (m) setMenuOpen(m.hidden);
      return;
    }
    var b = e.target.closest('.lib-opt');
    if (!b) return;
    activeFilter = b.getAttribute('data-f') || 'All';
    setMenuOpen(false);
    activeIdx = 0;
    dragOffset = 0;
    rebuildVisible();
    layoutDeck(true);
  });
  document.addEventListener('click', function (e) {
    if (!chipsEl.contains(e.target)) setMenuOpen(false);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') setMenuOpen(false);
  });

  /* Shuffle & Prev / Next buttons */
  document.querySelectorAll('[data-lib-shuffle]').forEach(function (btn) {
    btn.addEventListener('click', function () { reshuffleDeck(true); });
  });
  document.querySelectorAll('[data-lib-prev]').forEach(function (btn) {
    btn.addEventListener('click', function () { stepBy(-1); });
  });
  document.querySelectorAll('[data-lib-next]').forEach(function (btn) {
    btn.addEventListener('click', function () { stepBy(1); });
  });
  if (hudCopy) {
    hudCopy.addEventListener('click', function () { copyDeviceCode(hudCopy); });
  }

  /* Pointer / Touch drag gestures */
  grid.addEventListener('pointerdown', function (e) {
    if (mode === 'grid' || visibleCards.length <= 1) return;
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    if (e.target.closest('.lib-act-btn')) return;
    isDragging = true;
    dragMoved = false;
    startX = lastX = e.clientX;
    startY = e.clientY;
    lastT = performance.now();
    vx = 0;
    stage.classList.add('is-dragging');
  }, { passive: true });

  window.addEventListener('pointermove', function (e) {
    if (!isDragging || mode === 'grid') return;
    var dx = e.clientX - startX;
    var dy = e.clientY - startY;
    if (!dragMoved && Math.abs(dy) > Math.abs(dx) * 1.25 && Math.abs(dy) > 12) {
      isDragging = false;
      stage.classList.remove('is-dragging');
      dragOffset = 0;
      layoutDeck(true);
      return;
    }
    if (Math.hypot(dx, dy) > 8) dragMoved = true;
    var now = performance.now();
    var dt = Math.max(1, now - lastT);
    vx = (e.clientX - lastX) / dt;
    lastX = e.clientX;
    lastT = now;

    var stepPx = window.innerWidth < 680 ? 150 : 230;
    dragOffset = Math.max(-2.5, Math.min(2.5, dx / stepPx));
    layoutDeck(false);
  }, { passive: true });

  function endDrag() {
    if (!isDragging) return;
    isDragging = false;
    stage.classList.remove('is-dragging');
    var flick = -dragOffset - vx * 0.28;
    var steps = 0;
    if (Math.abs(flick) > 0.24) {
      steps = Math.round(flick);
      if (steps === 0) steps = flick > 0 ? 1 : -1;
      steps = Math.max(-3, Math.min(3, steps));
    }
    activeIdx = mod(activeIdx + steps, visibleCards.length);
    dragOffset = 0;
    layoutDeck(true);
    setTimeout(function () { dragMoved = false; }, 40);
  }

  window.addEventListener('pointerup', endDrag, { passive: true });
  window.addEventListener('pointercancel', endDrag, { passive: true });

  /* Trackpad two-finger swipe & wheel riffle */
  grid.addEventListener('wheel', function (e) {
    if (mode === 'grid' || visibleCards.length <= 1) return;
    var isHoriz = Math.abs(e.deltaX) > Math.abs(e.deltaY) * 0.85;
    if (!isHoriz && !e.shiftKey) return;
    e.preventDefault();
    var now = performance.now();
    if (now - wheelLock < 188) return;
    var delta = Math.abs(e.deltaX) >= Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
    wheelAccum += delta;
    if (Math.abs(wheelAccum) > 28) {
      stepBy(wheelAccum > 0 ? 1 : -1);
      wheelAccum = 0;
      wheelLock = now;
    }
  }, { passive: false });

  /* Keyboard navigation */
  window.addEventListener('keydown', function (e) {
    if (mode === 'grid' || e.defaultPrevented) return;
    var tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    if (e.key === 'ArrowRight') { e.preventDefault(); stepBy(1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); stepBy(-1); }
    else if ((e.key === 'r' || e.key === 'R') && !e.metaKey && !e.ctrlKey && !e.altKey) { reshuffleDeck(true); }
  });

  window.addEventListener('resize', function () { layoutDeck(false); });

  renderDropdown();

  /* Load catalog & initialize shuffled deck */
  Promise.all([
    fetch('assets/library/index.json?v=4').then(function (r) { return r.json(); }),
    fetch('assets/templates/index.json?v=3').then(function (r) { return r.json(); }).catch(function () { return { items: [] }; }),
    fetch('assets/community/index.json?v=2').then(function (r) { return r.json(); }).catch(function () { return { items: [] }; }),
    fetch('assets/skills/index.json?v=2').then(function (r) { return r.json(); }).catch(function () { return { items: [] }; }),
    fetch('assets/extensions/index.json?v=1').then(function (r) { return r.json(); }).catch(function () { return { items: [] }; })
  ]).then(function (all) {
    items = all[1].items.concat(all[2].items, all[3].items, all[4].items, all[0].items);
    for (var i = items.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1)), t = items[i];
      items[i] = items[j];
      items[j] = t;
    }
    grid.innerHTML = items.map(card).join('');
    allCards = Array.prototype.slice.call(grid.querySelectorAll('.lib-card'));
    renderDropdown();

    grid.addEventListener('click', function (e) {
      var copyBtn = e.target.closest('.lib-copy');
      if (copyBtn) {
        e.preventDefault();
        e.stopPropagation();
        copyDeviceCode(copyBtn);
        return;
      }
      var dlBtn = e.target.closest('.lib-dl');
      if (dlBtn) {
        if (dragMoved) { e.preventDefault(); return; }
        e.stopPropagation();
        return;
      }
      var cardEl = e.target.closest('.lib-card');
      if (!cardEl) return;
      if (mode !== 'grid') {
        if (dragMoved) {
          e.preventDefault();
          return;
        }
        var idx = visibleCards.indexOf(cardEl);
        if (idx !== -1) {
          var d = circularDelta(idx, activeIdx, visibleCards.length);
          if (Math.abs(d) > 0.25) {
            e.preventDefault();
            stepBy(Math.round(d));
          }
        }
      }
    });

    rebuildVisible();
    layoutDeck(true);
  }).catch(function () {
    emptyEl.hidden = false;
    emptyEl.textContent = 'Could not load the library.';
  });
})();
