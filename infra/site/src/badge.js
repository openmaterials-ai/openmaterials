// The openmaterials version badge, rendered by the Worker for any pinned
// map version: GET /badge/<hash>.svg (8 to 64 hex chars, shown at 12).
//
// MUST stay byte-identical with omai/badge.py badge_svg() for the same
// hash: tests/test_badge.py pins the parity. The width table is shared
// verbatim; textLength pins rendering, so only parity matters.

const WIDTHS = {
  o: 6.9, p: 6.9, e: 6.6, n: 6.9, m: 10.6, a: 6.6, t: 4.6,
  r: 4.8, i: 3.2, l: 3.2, s: 5.9,
  0: 6.9, 1: 6.9, 2: 6.9, 3: 6.9, 4: 6.9, 5: 6.9, 6: 6.9,
  7: 6.9, 8: 6.9, 9: 6.9, b: 6.9, c: 6.0, d: 6.9, f: 3.7,
};
const FALLBACK = 7.0;
const LABEL = 'openmaterials';
const LEFT_BG = '#555';
const RIGHT_BG = '#4f46e5';

const MARK =
  '<g transform="translate(5,3) scale(0.875)">' +
  '<rect width="16" height="16" rx="4" fill="#4f46e5"/>' +
  '<path d="M4 4.5 L8 7.5 L4 10.5" stroke="#ffffff" stroke-width="1.6" ' +
  'fill="none" stroke-linecap="round" stroke-linejoin="round"/>' +
  '<circle cx="11" cy="8" r="2.6" fill="#ffffff"/>' +
  '<circle cx="11" cy="8" r="1.1" fill="#4f46e5"/>' +
  '</g>';

function textWidth(s) {
  let w = 0;
  for (const c of s) w += (c in WIDTHS ? WIDTHS[c] : FALLBACK);
  return Math.round(w * 10) / 10;
}

// python str() of a float prints 79.0 as "79.0" but round() of an int-valued
// expression yields an int ("79"); mirror by formatting: integers bare,
// tenths kept otherwise. Both sides produce widths in tenths, so this is
// exact, not floating-point luck.
function num(x) {
  const r = Math.round(x * 10) / 10;
  return Number.isInteger(r) ? String(r) : String(r);
}

export function badgeSVG(version) {
  const v = String(version).slice(0, 12);
  const lw = textWidth(LABEL);
  const rw = textWidth(v);
  const left = Math.round(5 + 14 + 4 + lw + 6);
  const right = Math.round(6 + rw + 6);
  const total = left + right;
  const lx = Math.round((23 + lw / 2) * 10) / 10;
  const rx = Math.round((left + right / 2) * 10) / 10;
  return (
    '<svg xmlns="http://www.w3.org/2000/svg" width="' + total +
    '" height="20" role="img" aria-label="' + LABEL + ': ' + v + '">' +
    '<title>' + LABEL + ' map version ' + v + '</title>' +
    '<linearGradient id="s" x2="0" y2="100%">' +
    '<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>' +
    '<stop offset="1" stop-opacity=".1"/></linearGradient>' +
    '<clipPath id="r"><rect width="' + total +
    '" height="20" rx="3" fill="#fff"/></clipPath>' +
    '<g clip-path="url(#r)">' +
    '<rect width="' + left + '" height="20" fill="' + LEFT_BG + '"/>' +
    '<rect x="' + left + '" width="' + right +
    '" height="20" fill="' + RIGHT_BG + '"/>' +
    '<rect width="' + total + '" height="20" fill="url(#s)"/></g>' +
    MARK +
    '<g fill="#fff" text-anchor="middle" ' +
    'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">' +
    '<text x="' + lx + '" y="15" fill="#010101" fill-opacity=".3" ' +
    'textLength="' + lw + '">' + LABEL + '</text>' +
    '<text x="' + lx + '" y="14" textLength="' + lw + '">' + LABEL + '</text>' +
    '<text x="' + rx + '" y="15" fill="#010101" fill-opacity=".3" ' +
    'textLength="' + rw + '">' + v + '</text>' +
    '<text x="' + rx + '" y="14" textLength="' + rw + '">' + v + '</text></g></svg>'
  );
}

export const BADGE_PATH_RE = /^\/badge\/([0-9a-f]{8,64})\.svg$/;
