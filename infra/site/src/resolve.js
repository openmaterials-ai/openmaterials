// Pure logic for the /l/<id> permalink route: DOM-free and fetch-free so
// node:test exercises it against the real committed instances.json. The
// Worker (index.js) supplies the data; nothing here fabricates a record.

const SHA256_RE = /^[0-9a-f]{64}$/;
// A short id is a PREFIX of the full sha256, git-style: at least 8 hex chars
// so a handle is never guessy, displayed at 12 (the UI's prefix convention).
const PREFIX_MIN = 8;
const PREFIX_RE = new RegExp(`^[0-9a-f]{${PREFIX_MIN},64}$`);

// Validate and normalize a candidate hash from the path. Returns the
// lowercase hash or null when malformed (a malformed hash is rejected
// before any data is fetched).
function parseHash(segment) {
  const h = String(segment == null ? "" : segment).trim().toLowerCase();
  return SHA256_RE.test(h) ? h : null;
}

// Validate a full id OR a short prefix (>= PREFIX_MIN hex chars).
function parsePrefix(segment) {
  const h = String(segment == null ? "" : segment).trim().toLowerCase();
  return PREFIX_RE.test(h) ? h : null;
}

// Find the flat projection entry whose canonical id equals the hash.
// {ok: true, entry} or {ok: false}. Never invents an entry.
function resolveId(instances, hash) {
  const list = Array.isArray(instances) ? instances : [];
  for (const entry of list) {
    if (entry && entry.id === hash) return { ok: true, entry };
  }
  return { ok: false };
}

// Resolve a full id or prefix against the projection, git-style.
// {ok: true, entry} on a unique match; {ok: false, ambiguous: [ids...]} when
// the prefix names several (honesty over guessing); {ok: false} on none.
function resolvePrefix(instances, prefix) {
  const list = Array.isArray(instances) ? instances : [];
  const matches = [];
  for (const entry of list) {
    if (entry && typeof entry.id === "string" && entry.id.startsWith(prefix)) {
      matches.push(entry);
      if (matches.length > 8) break;
    }
  }
  if (matches.length === 1) return { ok: true, entry: matches[0] };
  if (matches.length > 1) return { ok: false, ambiguous: matches.map((e) => e.id) };
  return { ok: false };
}

const esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]
  );

// "ThermalConductivity[bte_solver=rta]" -> "Thermal conductivity"
function humanProperty(variable) {
  const base = String(variable || "").replace(/\[.*$/, "");
  const words = base.replace(/([a-z0-9])([A-Z])/g, "$1 $2").toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

// The server-rendered shell for a resolved permalink: real OG metadata so
// the link unfurls with the value it names, then an immediate client
// redirect to the playground datasheet (the one renderer; this shell never
// duplicates it). Everything shown comes from the committed entry.
function permalinkHTML(entry, origin) {
  const prop = humanProperty(entry.variable);
  const mat = entry.material ? ` of ${entry.material}` : "";
  const title = `${prop}${mat}`;
  const value =
    entry.value != null ? `${entry.value}${entry.units ? " " + entry.units : ""}` : "";
  const src = entry.source && entry.source.ref ? String(entry.source.ref) : "";
  const desc =
    `${value ? value + ". " : ""}Committed lineage ${entry.id.slice(0, 12)}` +
    `${src ? ", source " + src : ""}, on the openmaterials map.`;
  const target = `${origin}/play/#id=${entry.id}`;
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${esc(title)}</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="openmaterials.ai">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
<meta name="twitter:card" content="summary">
<link rel="canonical" href="${esc(origin)}/l/${entry.id}">
<meta http-equiv="refresh" content="0;url=${esc(target)}">
</head>
<body>
<p>${esc(title)}: ${esc(desc)}</p>
<p><a href="${esc(target)}">Open the datasheet</a></p>
<script>location.replace(${JSON.stringify(target)});</script>
</body>
</html>
`;
}

// The honest empty state: names the hash verbatim, links to the map,
// fabricates nothing.
function notFoundHTML(hash, origin) {
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>No committed value</title></head>
<body>
<p>No committed value carries the id <code>${esc(hash)}</code> on this map
version. The id may belong to a value not yet committed, or to a different
map.</p>
<p><a href="${esc(origin)}/map/">Open the map</a></p>
</body>
</html>
`;
}

// The honest fork for an ambiguous prefix: name every match, pick nothing.
function ambiguousHTML(prefix, ids, origin) {
  const rows = ids
    .map((id) => `<li><a href="${esc(origin)}/l/${esc(id)}"><code>${esc(id.slice(0, 12))}</code></a></li>`)
    .join("");
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Ambiguous id</title></head>
<body>
<p>The prefix <code>${esc(prefix)}</code> names more than one committed value:</p>
<ul>${rows}</ul>
</body>
</html>
`;
}

export {
  parseHash, parsePrefix, resolveId, resolvePrefix,
  permalinkHTML, notFoundHTML, ambiguousHTML, humanProperty, PREFIX_MIN,
};

// ---- source-first identifiers (the paper goes first in the URL) ----------
// /l/<scheme:ref> lists a source's committed values; /l/<scheme:ref>/<hash
// prefix> names one value WITH a mechanical consistency check: the visible
// namespace must match the id's own in-hash source, so a speaking identifier
// can never lie. Bare /l/<hash> stays the canonical form (values without an
// in-hash source have no namespace to speak).
const SOURCE_REF_RE = /^[a-z][a-z0-9+.-]*:.+$/;

// Split the path after /l/ into {hash} | {ref} | {ref, hash} | null.
// A DOI ref may itself contain slashes, so the hash is only split off when
// the LAST segment parses as one and the rest still parses as a ref.
function parseLPath(rest) {
  const p = String(rest == null ? "" : rest).replace(/\/$/, "");
  const bare = parsePrefix(p);
  if (bare) return { hash: bare };
  if (!p.includes("/")) return SOURCE_REF_RE.test(p) ? { ref: p } : null;
  const i = p.lastIndexOf("/");
  const head = p.slice(0, i), tail = parsePrefix(p.slice(i + 1));
  if (tail && SOURCE_REF_RE.test(head)) return { ref: head, hash: tail };
  return SOURCE_REF_RE.test(p) ? { ref: p } : null;
}

const entrySourceRef = (e) =>
  e && e.source && typeof e.source.ref === "string" && SOURCE_REF_RE.test(e.source.ref)
    ? e.source.ref : null;

function entriesBySource(instances, ref) {
  return (Array.isArray(instances) ? instances : []).filter((e) => entrySourceRef(e) === ref);
}

// The source page: one paper's (or dataset's) committed family, each value a
// short-id row. Built only from the committed projection.
function sourceListingHTML(ref, entries, origin) {
  const n = entries.length;
  const rows = entries.map((e) => {
    const short = e.id.slice(0, 12);
    const label = `${humanProperty(e.variable)}${e.material ? " of " + e.material : ""}`;
    const val = e.value != null ? ` : ${e.value}${e.units ? " " + e.units : ""}` : "";
    return `<li><a href="${esc(origin)}/l/${short}"><code>${short}</code></a> ${esc(label)}${esc(val)}</li>`;
  }).join("");
  const title = `${ref}`;
  const desc = `${n} committed value${n === 1 ? "" : "s"} from ${ref} on the openmaterials map.`;
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${esc(title)}</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="openmaterials.ai">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
<meta name="twitter:card" content="summary">
<link rel="canonical" href="${esc(origin)}/l/${esc(ref)}">
</head>
<body>
<p>${esc(desc)}</p>
<ul>${rows}</ul>
<p><a href="${esc(origin)}/experiment/#ref=${esc(ref)}">Open this source on the experiments page</a></p>
</body>
</html>
`;
}

function sourceEmptyHTML(ref, origin) {
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>No committed values</title></head>
<body>
<p>No committed value carries the source <code>${esc(ref)}</code> on this map
version.</p>
<p><a href="${esc(origin)}/map/">Open the map</a></p>
</body>
</html>
`;
}

// The honesty gate for the speaking form: the namespace in the URL must be
// the id's own in-hash source.
function sourceMismatchHTML(claimedRef, entry, origin) {
  const actual = entrySourceRef(entry);
  return `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Source mismatch</title></head>
<body>
<p>The value <code>${esc(entry.id.slice(0, 12))}</code> does not belong to
<code>${esc(claimedRef)}</code>${actual ? `; its committed source is <code>${esc(actual)}</code>` : `; it carries no in-hash source`}.
The canonical link is <a href="${esc(origin)}/l/${esc(entry.id)}">${esc(origin)}/l/${esc(entry.id.slice(0, 12))}</a>.</p>
</body>
</html>
`;
}

export { parseLPath, entriesBySource, entrySourceRef, sourceListingHTML, sourceEmptyHTML, sourceMismatchHTML };
