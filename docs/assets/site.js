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

  var REPO = 'https://github.com/openmaterials-ai/openmaterials';

  // Nav items: [label, href, matchPrefix, isExternal]. The GitHub item is an
  // icon-less text link "Source".
  var NAV = [
    ['Map', site('map/'), 'map/', false],
    ['Guide', site('guide/'), 'guide/', false],
    ['Play', site('play/'), 'play/', false],
    ['Learn', site('learn/'), 'learn/', false],
    ['Document', site('document/'), 'document/', false],
    ['Source', REPO, null, true]
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
      var active = '';
      if (prefix && rel.indexOf(prefix) === 0) active = ' active';
      var attrs = ext ? ' target="_blank" rel="noopener"' : '';
      var aria = active ? ' aria-current="page"' : '';
      return '<a class="' + cls + active + '" href="' + href + '"' + attrs + aria + '>' + label + '</a>';
    }).join('');
    // Wordmark in Source Serif 4 with a 6px indigo brand node after it; no ".ai".
    return (
      '<header class="om-header">' +
      '<a class="om-brand" href="' + site('index.html') + '" aria-label="openmaterials home">' +
      '<img class="om-mark" src="' + new URL('logo.svg', assetsBase).href + '" alt="" width="22" height="22">' +
      '<span>openmaterials.ai</span></a>' +
      '<span class="om-beta" title="Beta: the map and its schema are still growing. Every committed value is content-addressed, so its identifier stays resolvable across versions.">beta</span>' +
      '<nav class="om-nav" aria-label="Primary">' + links + '</nav>' +
      '</header>'
    );
  }

  function buildFooter() {
    var year = new Date().getFullYear();
    return (
      '<footer class="om-footer">' +
      '<div class="om-footer-cols">' +
      '<div><h4>About</h4>' +
      '<p class="om-desc">A versioned map of physics: typed quantities as nodes, executable formulas as edges, every element content-addressed.</p></div>' +
      '<div><h4>Explore</h4><ul>' +
      '<li><a href="' + site('map/') + '">The map</a></li>' +
      '<li><a href="' + site('openmaterials.pdf') + '">The document (PDF)</a></li>' +
      '<li><a href="' + site('map-lab/') + '">Labs</a></li>' +
      '<li><a href="' + REPO + '" target="_blank" rel="noopener">Source</a></li>' +
      '</ul></div>' +
      '<div><h4>Trust mark</h4>' +
      '<div class="om-trust" id="om-trust">' +
      '<div class="om-trust-row"><span class="om-trust-k">genesis</span><span class="om-trust-v" id="om-genesis" role="button" tabindex="0" title="click to copy">e6e8044e9203</span></div>' +
      '<div class="om-trust-row"><span class="om-trust-k">version</span><span class="om-trust-v" id="om-version" role="button" tabindex="0" title="click to copy">loading…</span></div>' +
      '</div></div>' +
      '</div>' +
      '<div class="om-smallprint">openmaterials.ai, a versioned map of physics. ' +
      'Map data CC BY 4.0, stewarded by the OpenMaterials-AI initiative; interfaces by Da Vinci Labs. <span class="om-ver">' + year + '</span></div>' +
      '</footer>'
    );
  }

  // Copy a trust-mark hash to the clipboard on click, with a brief confirm tint.
  function wireCopy(el) {
    if (!el) return;
    function doCopy() {
      var full = el.dataset.full || el.textContent;
      var done = function () {
        el.classList.add('copied');
        setTimeout(function () { el.classList.remove('copied'); }, 1100);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(full).then(done, function () {});
      } else {
        try {
          var ta = document.createElement('textarea');
          ta.value = full; document.body.appendChild(ta); ta.select();
          document.execCommand('copy'); document.body.removeChild(ta); done();
        } catch (e) { /* clipboard unavailable */ }
      }
    }
    el.addEventListener('click', doCopy);
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); doCopy(); }
    });
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
    var gEl = document.getElementById('om-genesis');
    var vEl = document.getElementById('om-version');
    if (gEl) { gEl.dataset.full = gEl.textContent; wireCopy(gEl); }
    if (vEl) wireCopy(vEl);
    fetch(site('data/version.json'))
      .then(function (r) { return r.json(); })
      .then(function (v) {
        if (!v) return;
        if (gEl && v.genesis) {
          gEl.textContent = ('' + v.genesis).slice(0, 12);
          gEl.dataset.full = '' + v.genesis;
          gEl.title = 'genesis ' + v.genesis + ' (click to copy)';
        }
        if (v.version) bustDocumentLinks('' + v.version);
        if (vEl && v.version) {
          vEl.textContent = ('' + v.version).slice(0, 12);
          vEl.dataset.full = '' + v.version;
          vEl.title = 'store head ' + v.version + ' (click to copy)';
        } else if (vEl) {
          vEl.textContent = 'unversioned';
        }
      })
      .catch(function () {
        if (vEl) vEl.textContent = 'unversioned';
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }

  // The PDF sits behind a long edge cache; stamping the live version onto
  // Document links makes every new map version fetch a fresh copy.
  function bustDocumentLinks(v) {
    if (!v) return;
    var links = document.querySelectorAll('a[href$="openmaterials.pdf"]');
    for (var i = 0; i < links.length; i++) {
      links[i].href = links[i].href + '?v=' + v.slice(0, 12);
    }
  }

})();
