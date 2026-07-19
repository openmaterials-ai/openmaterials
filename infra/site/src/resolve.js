// Pure logic for the /l/<id> permalink route: DOM-free and fetch-free so
// node:test exercises it against the real committed instances.json. The
// Worker (index.js) supplies the data; nothing here fabricates a record.

const SHA256_RE = /^[0-9a-f]{64}$/;

// Validate and normalize a candidate hash from the path. Returns the
// lowercase hash or null when malformed (a malformed hash is rejected
// before any data is fetched).
function parseHash(segment) {
  const h = String(segment == null ? "" : segment).trim().toLowerCase();
  return SHA256_RE.test(h) ? h : null;
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

export { parseHash, resolveId, permalinkHTML, notFoundHTML, humanProperty };
