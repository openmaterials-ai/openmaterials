/* The in-page mirrors of two omdc distances, for the playground's
 * distance-between-papers tool. Same rules as the python package, stated by
 * their registry ids: comp@1 (Element Mover's Distance on the Pettifor
 * scale, 1D Wasserstein via CDFs) and curve@1 (symmetric relative L2 on the
 * shared x range, 256-point linear interpolation). Parity with omdc is
 * checked at build time; the Pettifor table below is pymatgen's
 * mendeleev_no, elements 1 through 103. */
(function () {
  'use strict';

  var MENDELEEV = {
    H: 103, He: 1, Li: 12, Be: 77, B: 86, C: 95, N: 100, O: 101, F: 102, Ne: 2,
    Na: 11, Mg: 73, Al: 80, Si: 85, P: 90, S: 94, Cl: 99, Ar: 3, K: 10, Ca: 16,
    Sc: 19, Ti: 51, V: 54, Cr: 57, Mn: 60, Fe: 61, Co: 64, Ni: 67, Cu: 72,
    Zn: 76, Ga: 81, Ge: 84, As: 89, Se: 93, Br: 98, Kr: 4, Rb: 9, Sr: 15,
    Y: 25, Zr: 49, Nb: 53, Mo: 56, Tc: 59, Ru: 62, Rh: 65, Pd: 69, Ag: 71,
    Cd: 75, In: 79, Sn: 83, Sb: 88, Te: 92, I: 97, Xe: 5, Cs: 8, Ba: 14,
    La: 33, Ce: 32, Pr: 31, Nd: 30, Pm: 29, Sm: 28, Eu: 18, Gd: 27, Tb: 26,
    Dy: 24, Ho: 23, Er: 22, Tm: 21, Yb: 17, Lu: 20, Hf: 50, Ta: 52, W: 55,
    Re: 58, Os: 63, Ir: 66, Pt: 68, Au: 70, Hg: 74, Tl: 78, Pb: 82, Bi: 87,
    Po: 91, At: 96, Rn: 6, Fr: 7, Ra: 13, Ac: 48, Th: 47, Pa: 46, U: 45,
    Np: 44, Pu: 43, Am: 42, Cm: 41, Bk: 40, Cf: 39, Es: 38, Fm: 37, Md: 36,
    No: 35, Lr: 34
  };

  // A material string parses to a composition only when every capitalized
  // word tokenizes fully into element symbols (SWCNT does not; a-Si gives
  // Si; Si0.5Ge0.5 gives both). Lowercase descriptor words are ignored.
  // Anything else returns null: no silent guessing.
  function parseFormula(material) {
    if (!material) return null;
    var words = String(material).split(/[^A-Za-z0-9.]+/).filter(Boolean);
    var comp = {};
    var found = false;
    for (var w = 0; w < words.length; w++) {
      var word = words[w];
      if (!/^[A-Z]/.test(word)) continue; // descriptor, not a formula word
      var re = /([A-Z][a-z]?)(\d*\.?\d*)/g;
      var consumed = 0;
      var local = {};
      var m;
      while ((m = re.exec(word)) !== null) {
        if (m.index !== consumed) break;
        if (!(m[1] in MENDELEEV)) { consumed = -1; break; }
        local[m[1]] = (local[m[1]] || 0) + (m[2] ? parseFloat(m[2]) : 1);
        consumed = m.index + m[0].length;
      }
      if (consumed !== word.length) return null; // a capitalized word failed: reject all
      for (var el in local) { comp[el] = (comp[el] || 0) + local[el]; found = true; }
    }
    return found ? comp : null;
  }

  function compElmd(compA, compB) {
    var axis = function (comp) {
      var total = 0;
      var el;
      for (el in comp) total += comp[el];
      var a = new Array(104).fill(0);
      for (el in comp) a[MENDELEEV[el]] += comp[el] / total;
      return a;
    };
    var pa = axis(compA);
    var pb = axis(compB);
    var cum = 0;
    var d = 0;
    for (var i = 0; i < 104; i++) { cum += pa[i] - pb[i]; d += Math.abs(cum); }
    return d;
  }

  function interp(x, xs, ys) {
    if (x <= xs[0]) return ys[0];
    if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
    var i = 1;
    while (xs[i] < x) i++;
    var t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
    return ys[i - 1] + t * (ys[i] - ys[i - 1]);
  }

  function sortedXY(xs, ys) {
    var idx = xs.map(function (_, i) { return i; }).sort(function (a, b) { return xs[a] - xs[b]; });
    return [idx.map(function (i) { return xs[i]; }), idx.map(function (i) { return ys[i]; })];
  }

  function curveRel(xa, ya, xb, yb) {
    var A = sortedXY(xa, ya);
    var B = sortedXY(xb, yb);
    var lo = Math.max(A[0][0], B[0][0]);
    var hi = Math.min(A[0][A[0].length - 1], B[0][B[0].length - 1]);
    if (!(lo < hi)) return null; // no shared x range
    var n = 256;
    var acc = 0;
    for (var i = 0; i < n; i++) {
      var x = lo + (hi - lo) * i / (n - 1);
      var fa = interp(x, A[0], A[1]);
      var fb = interp(x, B[0], B[1]);
      var scale = (Math.abs(fa) + Math.abs(fb)) / 2;
      if (scale === 0) scale = 1;
      var r = (fa - fb) / scale;
      acc += r * r;
    }
    return Math.sqrt(acc / n);
  }

  window.omdcJS = {
    ids: { comp: 'comp@1', curve: 'curve@1' },
    parseFormula: parseFormula,
    compElmd: compElmd,
    curveRel: curveRel
  };
})();
