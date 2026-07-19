// The openmaterials site Worker. The static site (docs/) is served as edge
// assets untouched; this script runs only for the routes named in
// wrangler.jsonc run_worker_first:
//
//   GET /healthz        liveness + the published map/lineage version
//   GET /l/<64-hex>     canonical permalink: resolve a lineage id against the
//                       committed projection, serve OG metadata, redirect to
//                       the playground datasheet. Honest 404/400 otherwise.
//
// The Worker holds no state and no secrets: instances.json and version.json
// are read from the same assets every browser reads, so the resolver can
// never disagree with the site.

import { parseHash, resolveId, permalinkHTML, notFoundHTML } from "./resolve.js";

async function assetJSON(env, request, path) {
  const url = new URL(request.url);
  url.pathname = path;
  url.search = "";
  const res = await env.ASSETS.fetch(new Request(url, { method: "GET" }));
  if (!res.ok) throw new Error(`asset ${path}: ${res.status}`);
  return res.json();
}

const html = (body, status) =>
  new Response(body, {
    status,
    headers: { "content-type": "text/html; charset=utf-8" },
  });

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/healthz") {
      try {
        const v = await assetJSON(env, request, "/data/version.json");
        return Response.json({ ok: true, version: v.version || null });
      } catch (e) {
        return Response.json({ ok: false }, { status: 500 });
      }
    }

    if (url.pathname.startsWith("/l/")) {
      const hash = parseHash(url.pathname.slice(3).replace(/\/$/, ""));
      if (!hash) {
        return html("<!doctype html><p>Malformed id: a permalink is /l/&lt;64-hex sha256&gt;.</p>", 400);
      }
      let instances;
      try {
        instances = await assetJSON(env, request, "/data/instances.json");
      } catch (e) {
        return html("<!doctype html><p>The instance projection is unavailable.</p>", 503);
      }
      const r = resolveId(instances, hash);
      return r.ok
        ? html(permalinkHTML(r.entry, url.origin), 200)
        : html(notFoundHTML(hash, url.origin), 404);
    }

    // Everything else is the static site, exactly as GitHub Pages serves it.
    return env.ASSETS.fetch(request);
  },
};
