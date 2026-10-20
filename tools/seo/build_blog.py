#!/usr/bin/env python3
"""Builds the website blog from tools/seo/posts/*.md.

What: writes website/blog/index.html, website/blog/<slug>.html, website/blog/feed.xml and website/blog/posts.json,
      and (idempotently) adds a "Blog" link to the top bar and footer of index.html, library.html and extensions.html.
      The header and footer on blog pages are copied from index.html at build time, so the blog never drifts from the site.
Why:  one source (the Markdown posts) feeds the site, the RSS feed, the sitemap and llms.txt (via gen_seo.py) and every syndication target.
Usage: python3 tools/seo/build_blog.py            (then python3 tools/website/gen_seo.py for sitemap and llms.txt)
       python3 tools/seo/build_blog.py --drafts   (also render drafts, for local preview)
Exit codes: 0 written, 1 a post is missing required front matter.
"""
from __future__ import annotations
import argparse, html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import BASE, BLOG, WEB, load_posts, render_md

e = html.escape
CATS = {"product": "Product", "creative": "Creative", "engineering": "Engineering"}
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "art", "icons", "src")
CHIP_ICON = {"all": "grid-dots", "product": "cube", "creative": "pencil", "engineering": "mod-matrix"}


def brand_icon(name, cls="chip-ic"):
    """Brand glyph from art/icons/src, inlined so controls need no extra network request."""
    svg = open(os.path.join(ICON_DIR, name + "-20.svg"), encoding="utf-8").read().strip()
    return svg.replace("<svg ", f'<svg class="{cls}" aria-hidden="true" ', 1).replace("\n", "")


def chip_icon(key):
    """Brand glyph from art/icons/src, inlined so the chip needs no request."""
    return brand_icon(CHIP_ICON[key], "chip-ic")

REQUIRED = ("title", "description", "date")


def read(name):
    return open(os.path.join(WEB, name), encoding="utf-8").read()


def rebase(fragment):
    """Make a root-relative fragment from index.html work one folder down (blog/)."""
    def fix(m):
        attr, val = m.group(1), m.group(2)
        if val.startswith(("http://", "https://", "mailto:", "../", "data:")):
            return m.group(0)
        if val.startswith("#"):
            val = "index.html" + val
        return f'{attr}="../{val}"'
    return re.sub(r'\b(href|src)="([^"]*)"', fix, fragment)


def chrome():
    idx = read("index.html")
    header = re.search(r'<header class="site-header".*?</header>', idx, re.S).group(0)
    footer = re.search(r'<footer class="site-footer">.*?</footer>', idx, re.S).group(0)
    header = rebase(header)
    header = re.sub(r'<a href="../blog/">Blog</a>', '<a href="../blog/" aria-current="page">Blog</a>', header)
    return header, rebase(footer)


def ensure_nav():
    """Add the Blog link to the top bar and footer of the hand-written pages (safe to run twice)."""
    for name in ("index.html", "library.html", "extensions.html"):
        p = os.path.join(WEB, name)
        s = open(p, encoding="utf-8").read()
        if 'href="blog/"' in s:
            continue
        s2 = re.sub(r'(\n\s*)(<a href="extensions\.html"[^>]*>Extensions</a>)', r'\1\2\1<a href="blog/">Blog</a>', s, count=1)
        if s2 == s:
            s2 = re.sub(r'(\n\s*)(<a href="library\.html"[^>]*>Library</a>)', r'\1\2\1<a href="blog/">Blog</a>', s, count=1)
        if name == "index.html":
            s2 = re.sub(r'(\n\s*)(<a href="artworks\.html">Art Gallery</a>\n\s*<a href="#listen">)', r'\1<a href="blog/">Blog</a>\1\2', s2, count=1)
        if s2 != s:
            open(p, "w", encoding="utf-8").write(s2)
            print("nav: added Blog to", name)


def thumb(img, width):
    """A WebP copy of a local blog image, `width` px wide, written to website/assets/thumbs/. Returns the site path,
    or the original when it is remote, already small, or Pillow is missing. Social cards keep using the original."""
    if not img or img.startswith("http"):
        return img
    src = os.path.join(WEB, img.lstrip("/"))
    name = os.path.splitext(os.path.basename(img))[0]
    rel = "assets/thumbs/%s-%d.webp" % (name, width)
    dst = os.path.join(WEB, rel)
    try:
        from PIL import Image
        if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with Image.open(src) as im:
                if im.width <= width:
                    return img
                im.convert("RGB").resize((width, round(im.height * width / im.width)), Image.LANCZOS).save(dst, "WEBP", quality=82, method=6)
        return rel
    except (ImportError, OSError):
        return img


def head(title, desc, url, image, extra="", kind="website", depth="../"):
    img = image if image.startswith("http") else BASE + image.lstrip("/")
    return f"""<!DOCTYPE html>
<html lang="en" data-mode="paper">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <meta name="theme-color" content="#FBFAF6">
  <script>window.INFINITE_DEFAULT_MODE = 'paper';</script>
  <script src="{depth}theme.js?v=2"></script>
  <title>{e(title)}</title>
  <meta name="description" content="{e(desc)}">
  <link rel="canonical" href="{url}">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(desc)}">
  <meta property="og:image" content="{e(img)}">
  <meta property="og:url" content="{url}">
  <meta property="og:type" content="{kind}">
  <meta property="og:site_name" content="Infinite">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{e(title)}">
  <meta name="twitter:description" content="{e(desc)}">
  <meta name="twitter:image" content="{e(img)}">
  <link rel="alternate" type="application/rss+xml" href="{BASE}blog/feed.xml" title="Infinite blog">
  <link rel="alternate" type="text/plain" href="{depth}llms.txt" title="Plain-text summary for language models">
  <link rel="icon" href="{depth}assets/favicon.svg" type="image/svg+xml">
  <link rel="icon" href="{depth}assets/favicon-32.png" sizes="32x32">
  <link rel="apple-touch-icon" href="{depth}assets/apple-touch-icon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&family=Geist:wght@400;500;600;700;800&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{depth}brand.css?v=e96b24bf">
  <link rel="stylesheet" href="{depth}style.css?v=dba6d460">
  <link rel="stylesheet" href="{depth}glass.css?v=c25dae44">
  <link rel="stylesheet" href="{depth}blog.css?v=df40576c">
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-ZC4TYX1WCL"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-ZC4TYX1WCL');
  </script>
{extra}</head>
"""


def ld(obj):
    return '  <script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + "</script>\n"


def fmt_date(d):
    import datetime
    try:
        return datetime.date.fromisoformat(d).strftime("%-d %B %Y")
    except Exception:
        return d


def fmt_short_date(d):
    import datetime
    try:
        return datetime.date.fromisoformat(d).strftime("%-d %b %Y")
    except Exception:
        return d


def card(p, i):
    img = p.get("image", "")
    media_img = (f'<img src="../{e(thumb(img, 720))}" alt="" loading="lazy" decoding="async" width="720" height="450">' if img and not img.startswith("http")
                 else f'<img src="{e(img)}" alt="" loading="lazy" width="1200" height="675">' if img
                 else '<div class="post-media-empty" aria-hidden="true"><span>infinite</span></div>')
    cat_label = e(CATS.get(p['category'], p['category'].capitalize()))
    date_short = e(fmt_short_date(p['date']))
    read_label = f"{p['minutes']} min read"
    open_ic = '<svg class="expand-ic" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6.5 13.5 13.5 6.5M8 6.5h5.5V12"/></svg>'
    return f"""        <article class="post-card" data-cat="{e(p['category'])}" data-title="{e(p['title'])}" data-cat-label="{cat_label}" data-date="{date_short}" data-read="{read_label}" style="--i:{i}">
          <a class="post-link" href="{p['slug']}.html">
            <div class="post-media">
              {media_img}
              <div class="post-media-hud">
                <span class="post-expand-pill" aria-hidden="true">{open_ic}</span>
              </div>
            </div>
            <div class="post-body">
              <h2>{e(p['title'])}</h2>
              <p class="post-desc">{e(p['description'])}</p>
              <div class="post-meta-foot">
                <span class="post-foot-date">{date_short}</span>
                <span class="post-foot-read"><i class="read-dot" aria-hidden="true"></i>{read_label}</span>
              </div>
            </div>
          </a>
        </article>"""


def build_index(posts, header, footer):
    items = "\n".join(card(p, i) for i, p in enumerate(posts))
    ic_chev = brand_icon("chevron-down", "select-chev")
    filter_opts = (
        f'<button type="button" class="blog-opt" role="option" aria-selected="true" data-filter="all" data-label="All">{chip_icon("all")}<span>All</span></button>'
        + "".join(
            f'<button type="button" class="blog-opt" role="option" aria-selected="false" data-filter="{k}" data-label="{e(v)}">{chip_icon(k)}<span>{e(v)}</span></button>'
            for k, v in CATS.items() if any(p["category"] == k for p in posts)
        )
    )
    ic_shuffle = brand_icon("loop", "chip-ic")
    ic_fan = brand_icon("library", "chip-ic")
    ic_stack = brand_icon("arrange", "chip-ic")
    ic_grid = brand_icon("grid-dots", "chip-ic")
    ic_prev = brand_icon("chevron-right", "deck-arrow-ic is-prev")
    ic_next = brand_icon("chevron-right", "deck-arrow-ic")
    blog_ld = {"@context": "https://schema.org", "@type": "Blog", "name": "Infinite blog", "url": BASE + "blog/",
               "description": "Notes on building and using Infinite, the free open-source DAW for visuals, music and code.",
               "publisher": {"@type": "Person", "name": "Naman Soni", "url": "https://github.com/n1m21n"},
               "blogPost": [{"@type": "BlogPosting", "headline": p["title"], "url": p["url"], "datePublished": p["date"]} for p in posts]}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Infinite", "item": BASE}, {"@type": "ListItem", "position": 2, "name": "Blog", "item": BASE + "blog/"}]}
    s = head("Infinite blog: audio-reactive visuals, node-based music and code",
             "Notes on building and using Infinite, the free open-source DAW for visuals, music and code on one canvas. Tutorials, engineering write-ups and ideas.",
             BASE + "blog/", "assets/og-image.jpg", ld(blog_ld) + ld(crumbs))
    s += f"""<body class="blog-page blog-index">
  {header}

  <main>
    <section class="section blog-hero">
      <div class="container">
        <div class="blog-head-bar">
          <h1 class="slab">Practice notes.</h1>

          <div class="blog-toolbar">
            <div class="blog-filter" id="blog-filter">
              <button type="button" class="blog-select" id="blog-select" aria-haspopup="listbox" aria-expanded="false" aria-label="Filter by category">
                <span class="blog-select-ic" id="blog-select-ic">{chip_icon("all")}</span>
                <span class="blog-select-val" id="blog-select-val">All</span>
                {ic_chev}
              </button>
              <div class="blog-menu" id="blog-menu" role="listbox" aria-label="Category" hidden>
                {filter_opts}
              </div>
            </div>

            <div class="blog-deck-tools" role="group" aria-label="Deck layout and shuffle">
              <button type="button" class="chip chip-icon-only chip-action" data-deck-shuffle aria-label="Shuffle deck" title="Shuffle">{ic_shuffle}</button>
              <div class="deck-view-switch" role="group" aria-label="Card arrangement">
                <button type="button" class="view-pill is-on" data-deck-view="fan" aria-pressed="true" aria-label="Book view" title="Book">{ic_fan}</button>
                <button type="button" class="view-pill" data-deck-view="stack" aria-pressed="false" aria-label="Stack view" title="Stack">{ic_stack}</button>
                <button type="button" class="view-pill" data-deck-view="grid" aria-pressed="false" aria-label="Grid view" title="Grid">{ic_grid}</button>
              </div>
            </div>
          </div>
        </div>

        <div class="blog-book-stage" id="blog-book-stage" data-deck-mode="fan" aria-roledescription="carousel" aria-label="Infinite blog card book">
          <div class="post-grid" id="post-grid">
{items}
          </div>

          <div class="deck-hud-wrap" id="deck-hud-wrap">
            <div class="deck-hud-pill">
              <button type="button" class="deck-nav-btn" data-deck-prev aria-label="Previous card" title="Previous (←)">
                {ic_prev}
              </button>
              <div class="deck-hud-info" aria-live="polite" aria-atomic="true">
                <img src="../assets/icon-96.png" alt="" class="deck-hud-avatar" width="36" height="36" decoding="async">
                <div class="deck-hud-text">
                  <span class="deck-hud-title" id="deck-hud-title">{e(posts[0]['title']) if posts else 'Infinite Blog'}</span>
                  <span class="deck-hud-meta" id="deck-hud-meta">{e(fmt_short_date(posts[0]['date'])) if posts else ''} · {posts[0]['minutes'] if posts else 0} min read</span>
                </div>
              </div>
              <div class="deck-hud-right">
                <button type="button" class="deck-icon-btn" data-deck-shuffle aria-label="Reshuffle deck" title="Shuffle (R)">
                  {ic_shuffle}
                </button>
                <button type="button" class="deck-nav-btn" data-deck-next aria-label="Next card" title="Next (→)">
                  {ic_next}
                </button>
              </div>
            </div>
            <div class="deck-progress-row">
              <div class="deck-progress-dots" id="deck-progress-dots" role="tablist" aria-label="Jump to note"></div>
            </div>
          </div>
        </div>

        <p class="blog-empty" id="blog-empty" hidden>No posts in this group yet.</p>
        <p class="blog-feed"><a href="feed.xml">RSS feed</a></p>
      </div>
    </section>
  </main>

  {footer}
  <script src="../site.js?v=9" defer></script>
  <script>
    (function () {{
      var stage = document.getElementById('blog-book-stage');
      var grid = document.getElementById('post-grid');
      var hudWrap = document.getElementById('deck-hud-wrap');
      var hudTitle = document.getElementById('deck-hud-title');
      var hudMeta = document.getElementById('deck-hud-meta');
      var dotsWrap = document.getElementById('deck-progress-dots');
      var empty = document.getElementById('blog-empty');
      var filterWrap = document.getElementById('blog-filter');
      var filterBtn = document.getElementById('blog-select');
      var filterMenu = document.getElementById('blog-menu');
      var filterVal = document.getElementById('blog-select-val');
      var filterIc = document.getElementById('blog-select-ic');
      if (!stage || !grid) return;

      var allCards = Array.prototype.slice.call(grid.querySelectorAll('.post-card'));
      var visibleCards = allCards.slice();
      var currentFilter = 'all';
      var params = new URLSearchParams(window.location.search);
      var qView = params.get('view');
      var mode = (qView === 'stack' || qView === 'grid' || qView === 'fan') ? qView : 'fan';
      var qTheme = params.get('mode');
      if (qTheme === 'midnight' || qTheme === 'paper' || qTheme === 'mist') {{
        document.documentElement.setAttribute('data-mode', qTheme);
      }}
      if (mode !== 'fan') {{
        document.querySelectorAll('[data-deck-view]').forEach(function (b) {{
          var on = b.getAttribute('data-deck-view') === mode;
          b.classList.toggle('is-on', on);
          b.setAttribute('aria-pressed', on ? 'true' : 'false');
        }});
      }}
      var activeIdx = 0;
      var dragOffset = 0;
      var isDragging = false;
      var dragMoved = false;
      var startX = 0, startY = 0, lastX = 0, lastT = 0, vx = 0;
      var wheelAccum = 0, wheelLock = 0;
      var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      function mod(n, m) {{ return m > 0 ? ((n % m) + m) % m : 0; }}

      function circularDelta(idx, center, total) {{
        if (total <= 1) return 0;
        var d = idx - center;
        var half = total / 2;
        while (d > half) d -= total;
        while (d <= -half) d += total;
        return d;
      }}

      function shuffleArray(arr) {{
        for (var i = arr.length - 1; i > 0; i--) {{
          var j = Math.floor(Math.random() * (i + 1));
          var tmp = arr[i];
          arr[i] = arr[j];
          arr[j] = tmp;
        }}
        return arr;
      }}

      function rebuildVisible() {{
        visibleCards = [];
        allCards.forEach(function (card) {{
          var show = currentFilter === 'all' || card.getAttribute('data-cat') === currentFilter;
          card.hidden = !show;
          if (show) {{
            visibleCards.push(card);
          }}
        }});
        empty.hidden = visibleCards.length > 0;
        stage.hidden = visibleCards.length === 0;
        activeIdx = mod(activeIdx, visibleCards.length);
        buildDots();
      }}

      function buildDots() {{
        if (!dotsWrap) return;
        dotsWrap.innerHTML = '';
        var total = visibleCards.length;
        for (var i = 0; i < total; i++) {{
          (function (idx) {{
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'deck-dot' + (idx === activeIdx ? ' is-on' : '');
            b.setAttribute('aria-label', 'Jump to note');
            b.addEventListener('click', function () {{ goTo(idx); }});
            dotsWrap.appendChild(b);
          }})(i);
        }}
      }}

      function updateHud() {{
        var total = visibleCards.length;
        if (!total) return;
        var c = visibleCards[mod(activeIdx, total)];
        if (hudTitle) hudTitle.textContent = c.getAttribute('data-title') || '';
        if (hudMeta) {{
          var dt = c.getAttribute('data-date') || '';
          var rd = c.getAttribute('data-read') || '';
          hudMeta.textContent = dt + ' · ' + rd;
        }}
        if (dotsWrap) {{
          var dots = dotsWrap.children;
          for (var i = 0; i < dots.length; i++) {{
            dots[i].classList.toggle('is-on', i === mod(activeIdx, total));
          }}
        }}
      }}

      function layoutDeck(animate) {{
        var total = visibleCards.length;
        stage.setAttribute('data-deck-mode', mode);
        if (hudWrap) hudWrap.hidden = (mode === 'grid' || total === 0);

        if (mode === 'grid' || !total) {{
          allCards.forEach(function (card) {{
            card.style.transform = '';
            card.style.opacity = '';
            card.style.zIndex = '';
            card.style.pointerEvents = '';
            card.removeAttribute('data-slot');
          }});
          updateHud();
          return;
        }}

        var isMobile = window.innerWidth < 680;
        var isTablet = window.innerWidth >= 680 && window.innerWidth < 1040;
        var center = activeIdx - dragOffset;

        visibleCards.forEach(function (card, idx) {{
          var d = circularDelta(idx, center, total);
          var abs = Math.abs(d);
          var sign = d < 0 ? -1 : (d > 0 ? 1 : 0);
          var prevD = typeof card._lastD === 'number' ? card._lastD : d;
          card._lastD = d;

          var wrapped = Math.abs(prevD - d) > 3.2;
          if (!animate || wrapped || reduceMotion) {{
            card.style.transition = 'none';
          }} else {{
            card.style.transition = '';
          }}

          var tx = 0, ty = 0, tz = 0, rx = 0, ry = 0, rz = 0, sc = 1, op = 1;

          if (mode === 'stack') {{
            /* Ref 3 & Ref 4: 3D Diagonal Glass Plate Rack */
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
          }} else {{
            /* Ref 5 & Ref 2: Spatial Book Fan + Liquid Glass Gallery */
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
          }}

          var dim = Math.min(0.55, Math.max(0, (abs - 0.15) * 0.18));
          card.style.setProperty('--card-dim', dim.toFixed(3));
          card.style.transform = 'translate3d(' + tx.toFixed(1) + 'px,' + ty.toFixed(1) + 'px,' + tz.toFixed(1) + 'px) rotateX(' + rx.toFixed(2) + 'deg) rotateY(' + ry.toFixed(2) + 'deg) rotateZ(' + rz.toFixed(2) + 'deg) scale(' + sc.toFixed(3) + ')';
          card.style.opacity = op.toFixed(3);
          card.style.zIndex = String(Math.max(1, Math.round(100 - abs * 20)));
          card.style.pointerEvents = op < 0.15 ? 'none' : 'auto';

          var slot = abs < 0.35 ? 'active' : (abs < 1.35 ? 'near' : (abs < 2.45 ? 'mid' : 'far'));
          card.setAttribute('data-slot', slot);
          card.setAttribute('aria-hidden', abs > 3.1 ? 'true' : 'false');
          if (abs <= 3.2) {{
            var im = card.querySelector('img[loading="lazy"]');
            if (im) im.setAttribute('loading', 'eager');
          }}
        }});

        updateHud();
      }}

      function stepBy(delta) {{
        var total = visibleCards.length;
        if (!total) return;
        activeIdx = mod(activeIdx + delta, total);
        dragOffset = 0;
        layoutDeck(true);
      }}

      function goTo(targetIdx) {{
        var total = visibleCards.length;
        if (!total) return;
        activeIdx = mod(targetIdx, total);
        dragOffset = 0;
        layoutDeck(true);
      }}

      function reshuffleDeck(withPulse) {{
        shuffleArray(allCards);
        allCards.forEach(function (c) {{ grid.appendChild(c); c._lastD = undefined; }});
        activeIdx = 0;
        dragOffset = 0;
        rebuildVisible();
        if (withPulse && !reduceMotion) {{
          stage.classList.add('is-shuffling');
          setTimeout(function () {{ stage.classList.remove('is-shuffling'); }}, 460);
        }}
        layoutDeck(true);
      }}

      /* Reshuffle on every visit */
      reshuffleDeck(false);

      /* Filter dropdown */
      function setFilterOpen(open) {{
        if (!filterMenu || !filterBtn) return;
        filterMenu.hidden = !open;
        filterBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      }}
      if (filterBtn && filterMenu) {{
        filterBtn.addEventListener('click', function (e) {{
          e.stopPropagation();
          setFilterOpen(filterMenu.hidden);
        }});
        var filterOpts = filterMenu.querySelectorAll('.blog-opt');
        filterOpts.forEach(function (opt) {{
          opt.addEventListener('click', function () {{
            currentFilter = opt.getAttribute('data-filter') || 'all';
            filterOpts.forEach(function (x) {{ x.setAttribute('aria-selected', x === opt ? 'true' : 'false'); }});
            if (filterVal) filterVal.textContent = opt.getAttribute('data-label') || 'All';
            var svg = opt.querySelector('svg');
            if (filterIc && svg) filterIc.innerHTML = svg.outerHTML;
            setFilterOpen(false);
            activeIdx = 0;
            dragOffset = 0;
            rebuildVisible();
            layoutDeck(true);
          }});
        }});
        document.addEventListener('click', function (e) {{
          if (filterWrap && !filterWrap.contains(e.target)) setFilterOpen(false);
        }});
        document.addEventListener('keydown', function (e) {{
          if (e.key === 'Escape') setFilterOpen(false);
        }});
      }}

      /* View mode switch (Book Fan / 3D Stack / Grid) */
      var viewPills = document.querySelectorAll('[data-deck-view]');
      viewPills.forEach(function (btn) {{
        btn.addEventListener('click', function () {{
          mode = btn.getAttribute('data-deck-view') || 'fan';
          viewPills.forEach(function (b) {{
            var on = b === btn;
            b.classList.toggle('is-on', on);
            b.setAttribute('aria-pressed', on ? 'true' : 'false');
          }});
          allCards.forEach(function (c) {{ c._lastD = undefined; }});
          layoutDeck(true);
        }});
      }});

      /* Shuffle & Prev / Next buttons */
      document.querySelectorAll('[data-deck-shuffle]').forEach(function (btn) {{
        btn.addEventListener('click', function () {{ reshuffleDeck(true); }});
      }});
      document.querySelectorAll('[data-deck-prev]').forEach(function (btn) {{
        btn.addEventListener('click', function () {{ stepBy(-1); }});
      }});
      document.querySelectorAll('[data-deck-next]').forEach(function (btn) {{
        btn.addEventListener('click', function () {{ stepBy(1); }});
      }});

      /* Click a side card in the 3D book to flip to it; click the center card to open the article */
      allCards.forEach(function (card) {{
        var link = card.querySelector('.post-link');
        if (!link) return;
        link.addEventListener('click', function (e) {{
          if (mode === 'grid') return;
          if (dragMoved) {{
            e.preventDefault();
            return;
          }}
          var idx = visibleCards.indexOf(card);
          if (idx === -1) return;
          var d = circularDelta(idx, activeIdx, visibleCards.length);
          if (Math.abs(d) > 0.25) {{
            e.preventDefault();
            stepBy(Math.round(d));
          }}
        }});
      }});

      /* Pointer / Touch drag gestures on desktop & mobile */
      grid.addEventListener('pointerdown', function (e) {{
        if (mode === 'grid' || visibleCards.length <= 1) return;
        if (e.pointerType === 'mouse' && e.button !== 0) return;
        isDragging = true;
        dragMoved = false;
        startX = lastX = e.clientX;
        startY = e.clientY;
        lastT = performance.now();
        vx = 0;
        stage.classList.add('is-dragging');
      }}, {{ passive: true }});

      window.addEventListener('pointermove', function (e) {{
        if (!isDragging || mode === 'grid') return;
        var dx = e.clientX - startX;
        var dy = e.clientY - startY;
        if (!dragMoved && Math.abs(dy) > Math.abs(dx) * 1.25 && Math.abs(dy) > 12) {{
          isDragging = false;
          stage.classList.remove('is-dragging');
          dragOffset = 0;
          layoutDeck(true);
          return;
        }}
        if (Math.hypot(dx, dy) > 8) dragMoved = true;
        var now = performance.now();
        var dt = Math.max(1, now - lastT);
        vx = (e.clientX - lastX) / dt;
        lastX = e.clientX;
        lastT = now;

        var stepPx = window.innerWidth < 680 ? 150 : 230;
        dragOffset = Math.max(-2.5, Math.min(2.5, dx / stepPx));
        layoutDeck(false);
      }}, {{ passive: true }});

      function endDrag() {{
        if (!isDragging) return;
        isDragging = false;
        stage.classList.remove('is-dragging');
        var flick = -dragOffset - vx * 0.28;
        var steps = 0;
        if (Math.abs(flick) > 0.24) {{
          steps = Math.round(flick);
          if (steps === 0) steps = flick > 0 ? 1 : -1;
          steps = Math.max(-3, Math.min(3, steps));
        }}
        activeIdx = mod(activeIdx + steps, visibleCards.length);
        dragOffset = 0;
        layoutDeck(true);
        setTimeout(function () {{ dragMoved = false; }}, 40);
      }}

      window.addEventListener('pointerup', endDrag, {{ passive: true }});
      window.addEventListener('pointercancel', endDrag, {{ passive: true }});

      /* Trackpad two-finger swipe & wheel riffle */
      grid.addEventListener('wheel', function (e) {{
        if (mode === 'grid' || visibleCards.length <= 1) return;
        var isHoriz = Math.abs(e.deltaX) > Math.abs(e.deltaY) * 0.85;
        if (!isHoriz && !e.shiftKey) return;
        e.preventDefault();
        var now = performance.now();
        if (now - wheelLock < 188) return;
        var delta = Math.abs(e.deltaX) >= Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
        wheelAccum += delta;
        if (Math.abs(wheelAccum) > 28) {{
          stepBy(wheelAccum > 0 ? 1 : -1);
          wheelAccum = 0;
          wheelLock = now;
        }}
      }}, {{ passive: false }});

      /* Keyboard navigation (← → to flip, R to reshuffle) */
      window.addEventListener('keydown', function (e) {{
        if (mode === 'grid' || e.defaultPrevented) return;
        var tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
        if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
        if (e.key === 'ArrowRight') {{ e.preventDefault(); stepBy(1); }}
        else if (e.key === 'ArrowLeft') {{ e.preventDefault(); stepBy(-1); }}
        else if ((e.key === 'r' || e.key === 'R') && !e.metaKey && !e.ctrlKey && !e.altKey) {{ reshuffleDeck(true); }}
      }});

      window.addEventListener('resize', function () {{ layoutDeck(false); }});
    }})();
  </script>
</body>
</html>
"""
    open(os.path.join(BLOG, "index.html"), "w", encoding="utf-8").write(s)


def build_post(p, posts, header, footer):
    body_html, heads = render_md(p["body"])
    h2 = [h for h in heads if h[0] == 2]
    toc = ""
    if len(h2) >= 3:
        toc = '<details class="toc" open><summary class="mono">on this page</summary><ol>' + "".join(f'<li><a href="#{i}">{e(t)}</a></li>' for _, i, t in h2) + "</ol></details>"
    img = p.get("image", "")
    hero = (f'<figure class="post-hero"><img src="../{e(thumb(img, 1200))}" alt="{e(p.get("image_alt", p["title"]))}" width="1200" height="675" decoding="async"></figure>' if img and not img.startswith("http")
            else f'<figure class="post-hero"><img src="{e(img)}" alt="{e(p.get("image_alt", p["title"]))}" width="1200" height="675"></figure>' if img else "")
    related = [r for r in posts if r["slug"] != p["slug"]]
    related.sort(key=lambda r: (-(len(set(r["tags"]) & set(p["tags"]))), r["category"] != p["category"]))
    rel = "".join(f'<a class="rel-card" href="{r["slug"]}.html"><span class="mono">{e(CATS.get(r["category"], r["category"]))}</span><b>{e(r["title"])}</b></a>' for r in related[:3])
    rel_html = f'<section class="post-related" aria-label="More posts"><h2>Keep reading</h2><div class="rel-grid">{rel}</div></section>' if rel else ""
    art = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"], "description": p["description"],
           "datePublished": p["date"], "dateModified": p.get("updated", p["date"]), "mainEntityOfPage": p["url"], "url": p["url"],
           "image": [(img if img.startswith("http") else BASE + img) if img else BASE + "assets/og-image.jpg"],
           "author": {"@type": "Person", "name": "Naman Soni", "alternateName": "n1m21n", "url": "https://github.com/n1m21n"},
           "publisher": {"@type": "Organization", "name": "Infinite", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/icon.png"}},
           "keywords": ", ".join(p["tags"]), "wordCount": p["words"], "inLanguage": "en-GB",
           "isPartOf": {"@type": "Blog", "name": "Infinite blog", "url": BASE + "blog/"}}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Infinite", "item": BASE}, {"@type": "ListItem", "position": 2, "name": "Blog", "item": BASE + "blog/"},
        {"@type": "ListItem", "position": 3, "name": p["title"], "item": p["url"]}]}
    s = head(f"{p['title']} | Infinite", p["description"], p["url"], img or "assets/og-image.jpg", ld(art) + ld(crumbs), kind="article")
    s += f"""<body class="blog-page blog-post">
  {header}

  <main>
    <article class="post">
      <div class="container post-wrap">
        <nav class="crumbs mono" aria-label="Breadcrumb"><a href="../index.html">Infinite</a> / <a href="./">Blog</a></nav>
        <header class="post-head">
          <p class="post-kicker mono">{e(CATS.get(p['category'], p['category']))}</p>
          <h1>{e(p['title'])}</h1>
          <p class="post-lede">{e(p['description'])}</p>
          <p class="post-by"><img class="by-av" src="../assets/icon-96.png" alt="" width="40" height="40" decoding="async"><span class="by-text"><a href="https://github.com/n1m21n" rel="noopener">Naman Soni</a><span class="by-meta">{e(fmt_date(p['date']))} · {p['minutes']} min read{(' · updated ' + e(fmt_date(p['updated']))) if p.get('updated') else ''}</span></span></p>
        </header>
        {hero}
        {toc}
        <div class="prose">
{body_html}
        </div>
        <aside class="post-cta" aria-label="Try Infinite">
          <p class="hand">your turn</p>
          <h2>Make something with it</h2>
          <p>Infinite is free and open source for macOS, Windows and Linux. Start from a template in the Library, or read how the nodes fit together.</p>
          <p class="cta-row"><a class="btn btn-primary" href="../index.html#download">Download Infinite</a><a class="btn btn-ghost" href="../library.html">Browse the Library</a></p>
        </aside>
        {rel_html}
      </div>
    </article>
  </main>

  {footer}
  <script src="../site.js?v=9" defer></script>
</body>
</html>
"""
    open(os.path.join(BLOG, p["slug"] + ".html"), "w", encoding="utf-8").write(s)


def build_feed(posts):
    from email.utils import format_datetime
    import datetime
    def rfc(d):
        return format_datetime(datetime.datetime.fromisoformat(d).replace(hour=9, tzinfo=datetime.timezone.utc))
    items = "".join(f"""  <item><title>{e(p['title'])}</title><link>{p['url']}</link><guid isPermaLink="true">{p['url']}</guid>
    <pubDate>{rfc(p['date'])}</pubDate><category>{e(p['category'])}</category><description>{e(p['description'])}</description></item>
""" for p in posts)
    last = rfc(posts[0]["date"]) if posts else ""
    open(os.path.join(BLOG, "feed.xml"), "w", encoding="utf-8").write(f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
  <title>Infinite blog</title><link>{BASE}blog/</link><description>Notes on building and using Infinite, the free open-source DAW for visuals, music and code.</description>
  <language>en-gb</language><lastBuildDate>{last}</lastBuildDate><atom:link href="{BASE}blog/feed.xml" rel="self" type="application/rss+xml"/>
{items}</channel></rss>
""")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--drafts", action="store_true", help="also render drafts (local preview only; do not deploy)")
    a = ap.parse_args()
    posts = load_posts(include_drafts=a.drafts)
    for p in posts:
        miss = [k for k in REQUIRED if not p.get(k)]
        if miss:
            print(f"{p['slug']}: missing front matter {miss}"); sys.exit(1)
    os.makedirs(BLOG, exist_ok=True)
    for f in os.listdir(BLOG):
        if f.endswith(".html") or f in ("feed.xml", "posts.json"):
            os.remove(os.path.join(BLOG, f))
    ensure_nav()
    header, footer = chrome()
    build_index(posts, header, footer)
    for p in posts:
        build_post(p, posts, header, footer)
    build_feed(posts)
    json.dump([{"slug": p["slug"], "title": p["title"], "description": p["description"], "date": p["date"], "updated": p.get("updated", p["date"]),
                "category": p["category"], "url": p["url"]} for p in posts], open(os.path.join(BLOG, "posts.json"), "w"), indent=1)
    # the menu and footer come from one definition; this marks the current page in them
    import subprocess
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "website", "sync_chrome.py")], check=True)
    print(f"blog: {len(posts)} post(s) -> website/blog/")


if __name__ == "__main__":
    main()
