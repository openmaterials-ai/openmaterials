/* ============================================================================
   openmaterials shared chrome. No build step, no dependencies.
   A page opts in by placing empty mount points anywhere in its body:
       <div data-site-header></div>
       <div data-site-footer></div>
   and loading this script (path-relative), e.g. <script src="../assets/site.js">.

   All links are resolved relative to the assets/ directory (derived from this
   script's own src), so the same file works from any page depth. The footer's
   trust mark is read at runtime from data/version.json.
   ============================================================================ */
(function () {
  'use strict';

  // ---- resolve paths relative to this script (assets/site.js) --------------
  var self = document.currentScript;
  if (!self) {
    var ss = document.getElementsByTagName('script');
    self = ss[ss.length - 1];
  }
  // assetsBase ends with ".../assets/"; siteBase is its parent (".../docs/").
  var assetsBase = new URL('.', self.src).href;          // .../assets/
  var siteBase = new URL('..', assetsBase).href;         // .../ (docs root)

  function site(p) { return new URL(p, siteBase).href; }
  function asset(p) { return new URL(p, assetsBase).href; }

  var REPO = 'https://github.com/gbarbalinardo/openmaterials';

  // The brand mark (a tiny DAG), inline so it needs no extra request.
  var MARK =
    '<svg class="om-mark om-mark-svg" width="24" height="24" viewBox="0 0 64 64" aria-hidden="true">' +
    '<rect width="64" height="64" rx="15" fill="#4f46e5"/>' +
    '<g stroke="#fff" stroke-width="3.4" stroke-linecap="round" fill="none" opacity="0.92">' +
    '<line x1="19" y1="20" x2="41" y2="32"/><line x1="41" y1="32" x2="19" y2="45"/></g>' +
    '<g fill="#fff"><circle cx="19" cy="20" r="6.2"/><circle cx="41" cy="32" r="6.2"/>' +
    '<circle cx="19" cy="45" r="6.2"/></g></svg>';

  // Nav items: [label, href, matchPrefix, isExternal]
  var NAV = [
    ['Map', site('map/'), 'map/', false],
    ['Pipeline', site('pipeline.html'), 'pipeline.html', false],
    ['Learn', site('learn/'), 'learn/', false],
    ['Document', site('openmaterials.pdf'), 'openmaterials.pdf', false],
    ['GitHub', REPO, null, true]
  ];

  // Which page are we on, relative to the site root (e.g. "map/", "index.html").
  function currentRel() {
    var here = window.location.href;
    if (here.indexOf(siteBase) === 0) {
      var rel = here.slice(siteBase.length);
      // strip query/hash
      rel = rel.split('#')[0].split('?')[0];
      return rel;
    }
    return '';
  }

  function buildHeader() {
    var rel = currentRel();
    var links = NAV.map(function (n) {
      var label = n[0], href = n[1], prefix = n[2], ext = n[3];
      var cls = 'om-nav-link';
      if (ext) cls += ' om-ext';
      var active = '';
      if (prefix && rel.indexOf(prefix) === 0) active = ' active';
      var attrs = ext ? ' target="_blank" rel="noopener"' : '';
      var aria = active ? ' aria-current="page"' : '';
      return '<a class="' + cls + active + '" href="' + href + '"' + attrs + aria + '>' + label + '</a>';
    }).join('');
    return (
      '<header class="om-header">' +
      '<a class="om-brand" href="' + site('index.html') + '" aria-label="openmaterials home">' +
      MARK + '<span>openmaterials<b>.ai</b></span></a>' +
      '<nav class="om-nav" aria-label="Primary">' + links + '</nav>' +
      '</header>'
    );
  }

  function buildFooter() {
    return (
      '<footer class="om-footer">' +
      '<div class="om-footer-cols">' +
      '<div><h4>openmaterials</h4>' +
      '<p class="om-desc">A versioned map of physics: typed quantities as nodes, executable formulas as edges, every element content-addressed.</p></div>' +
      '<div><h4>Explore</h4><ul>' +
      '<li><a href="' + site('map/') + '">The map</a></li>' +
      '<li><a href="' + site('openmaterials.pdf') + '">The document (PDF)</a></li>' +
      '<li><a href="' + site('map-lab/') + '">Labs</a></li>' +
      '<li><a href="' + REPO + '" target="_blank" rel="noopener">GitHub</a></li>' +
      '</ul></div>' +
      '<div><h4>Trust mark</h4>' +
      '<div class="om-trust" id="om-trust">' +
      '<div class="om-trust-row"><span class="om-trust-k">genesis</span><span class="om-trust-v" id="om-genesis">e6e8044e9203</span></div>' +
      '<div class="om-trust-row"><span class="om-trust-k">version</span><span class="om-trust-v" id="om-version">loading…</span></div>' +
      '</div></div>' +
      '</div>' +
      '<div class="om-smallprint">openmaterials: a versioned map of physics.</div>' +
      '</footer>'
    );
  }

  function mount() {
    var h = document.querySelector('[data-site-header]');
    if (h) h.innerHTML = buildHeader();
    var f = document.querySelector('[data-site-footer]');
    if (f) {
      f.innerHTML = buildFooter();
      loadTrust();
    }
  }

  // Trust mark: read genesis + version from data/version.json at runtime.
  function loadTrust() {
    fetch(site('data/version.json'))
      .then(function (r) { return r.json(); })
      .then(function (v) {
        if (!v) return;
        var gEl = document.getElementById('om-genesis');
        var vEl = document.getElementById('om-version');
        if (gEl && v.genesis) {
          gEl.textContent = ('' + v.genesis).slice(0, 12);
          gEl.title = 'genesis ' + v.genesis;
        }
        if (vEl && v.version) {
          vEl.textContent = ('' + v.version).slice(0, 12);
          vEl.title = 'store head ' + v.version;
        } else if (vEl) {
          vEl.textContent = 'unversioned';
        }
      })
      .catch(function () {
        var vEl = document.getElementById('om-version');
        if (vEl) vEl.textContent = 'unversioned';
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }

  // expose for pages (e.g. the map) that build a compact header variant.
  window.OMChrome = { site: site, asset: asset, mark: MARK, repo: REPO, nav: NAV };
})();
