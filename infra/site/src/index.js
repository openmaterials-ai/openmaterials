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
import {
  MINTS_PER_DAY, randomCode, parseCode, validateMintBody,
  shortlinkHTML, shortlinkNotFoundHTML,
} from "./shortlinks.js";

// Origins allowed to mint (the read side is public by design). localhost
// covers wrangler dev and the docs http.server used by tests.
const MINT_ORIGINS = [
  "https://openmaterials.ai",
  "https://openmaterials-site.giuseppe-barbalinardo.workers.dev",
];
const isMintOrigin = (o) =>
  !!o && (MINT_ORIGINS.includes(o) || /^http:\/\/localhost(:\d+)?$/.test(o));

const corsHeaders = (origin) => ({
  "access-control-allow-origin": origin,
  "access-control-allow-methods": "POST, OPTIONS",
  "access-control-allow-headers": "content-type",
});

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

    if (url.pathname === "/s" || url.pathname.startsWith("/s/")) {
      return handleShortlink(request, env, url);
    }

    // Everything else is the static site, exactly as GitHub Pages serves it.
    return env.ASSETS.fetch(request);
  },
};

// The short-link store: the one write surface. POST /s mints (rate-limited,
// validated, public-by-construction); GET /s/<code> serves the crawlable
// shell; GET /s/<code>/raw serves the stored envelope JSON with open CORS
// (a minted payload is public data; the code is the only handle).
async function handleShortlink(request, env, url) {
  const origin = request.headers.get("origin");

  if (request.method === "OPTIONS" && url.pathname === "/s") {
    return isMintOrigin(origin)
      ? new Response(null, { status: 204, headers: corsHeaders(origin) })
      : new Response(null, { status: 403 });
  }

  if (request.method === "POST" && url.pathname === "/s") {
    if (!isMintOrigin(origin)) {
      return Response.json({ error: "origin not allowed to mint" }, { status: 403 });
    }
    const ip = request.headers.get("cf-connecting-ip") || "unknown";
    const day = new Date().toISOString().slice(0, 10);
    const rlKey = `rl:${day}:${ip}`;
    const used = parseInt((await env.SHORTLINKS.get(rlKey)) || "0", 10);
    if (used >= MINTS_PER_DAY) {
      return Response.json({ error: "daily mint limit reached" },
        { status: 429, headers: corsHeaders(origin) });
    }
    const body = await request.text();
    const v = validateMintBody(body);
    if (!v.ok) {
      return Response.json({ error: v.error }, { status: 400, headers: corsHeaders(origin) });
    }
    let code = null;
    for (let attempt = 0; attempt < 5 && !code; attempt++) {
      const bytes = new Uint8Array(9);
      crypto.getRandomValues(bytes);
      const candidate = randomCode(bytes);
      if (!(await env.SHORTLINKS.get(`s:${candidate}`))) code = candidate;
    }
    if (!code) return Response.json({ error: "could not allocate a code" },
      { status: 503, headers: corsHeaders(origin) });
    await env.SHORTLINKS.put(`s:${code}`, v.bytes,
      { metadata: { created: new Date().toISOString(), members: v.envelope.lineages.length } });
    await env.SHORTLINKS.put(rlKey, String(used + 1), { expirationTtl: 172800 });
    return Response.json({ code, url: `${url.origin}/s/${code}` },
      { status: 201, headers: corsHeaders(origin) });
  }

  if (request.method === "GET") {
    const raw = url.pathname.endsWith("/raw");
    const seg = url.pathname.slice(3).replace(/\/raw$/, "").replace(/\/$/, "");
    const code = parseCode(seg);
    if (!code) return html("<!doctype html><p>Malformed short code.</p>", 400);
    const stored = await env.SHORTLINKS.get(`s:${code}`);
    if (stored == null) {
      return raw
        ? Response.json({ error: "not found" },
            { status: 404, headers: { "access-control-allow-origin": "*" } })
        : html(shortlinkNotFoundHTML(code, url.origin), 404);
    }
    if (raw) {
      return new Response(stored, {
        headers: {
          "content-type": "application/json",
          "access-control-allow-origin": "*",
          "cache-control": "public, max-age=31536000, immutable",
        },
      });
    }
    return html(shortlinkHTML(JSON.parse(stored), code, url.origin), 200);
  }

  return new Response("method not allowed", { status: 405 });
}
