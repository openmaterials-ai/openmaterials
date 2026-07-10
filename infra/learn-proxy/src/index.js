/*
 * openmaterials-learn: the cost-gated Anthropic proxy for the Learn page.
 *
 * The browser never sees the API key. This Worker accepts the exact
 * messages.create body the Learn page builds (minus any key), enforces
 * the containment gates, injects the key from its secret, and relays to
 * api.anthropic.com.
 *
 * Gates, in order:
 *   1. CORS origin allowlist (ALLOWED_ORIGINS var).
 *   2. Shape: model allowlist, max_tokens cap, body-size cap.
 *   3. Per-IP daily request count (PER_IP_DAILY, KV, resets at UTC midnight).
 *   4. Global daily spend budget (DAILY_BUDGET_USD, KV): estimated from each
 *      response's usage at Opus 4.8 list prices; when the day's estimate
 *      exceeds the budget, requests get 429 budget_exhausted until tomorrow.
 *
 * KV is eventually consistent, so the gates are containment, not exact
 * accounting; a racing burst can overshoot by a request or two, never by
 * an unbounded amount.
 */

const MODEL_ALLOWLIST = ["claude-opus-4-8"];
const MAX_TOKENS_CAP = 4096;
const MAX_BODY_BYTES = 1_000_000;
/* Opus 4.8 list prices per token (USD): input $5/M, output $25/M. */
const IN_PRICE = 5 / 1e6;
const OUT_PRICE = 25 / 1e6;

function cors(origin, env) {
  const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim());
  const ok = allowed.includes(origin);
  return {
    "Access-Control-Allow-Origin": ok ? origin : allowed[0] || "",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "Vary": "Origin",
  };
}

function deny(status, type, message, headers) {
  return new Response(
    JSON.stringify({ type: "error", error: { type, message } }),
    { status, headers: { "content-type": "application/json", ...headers } },
  );
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const headers = cors(origin, env);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers });
    }
    if (request.method !== "POST") {
      return deny(405, "invalid_request_error", "POST only", headers);
    }
    const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim());
    if (!allowed.includes(origin)) {
      return deny(403, "permission_error", "origin not allowed", headers);
    }

    /* Gate 2: shape. */
    const raw = await request.text();
    if (raw.length > MAX_BODY_BYTES) {
      return deny(413, "request_too_large", "body exceeds the demo cap", headers);
    }
    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return deny(400, "invalid_request_error", "invalid JSON", headers);
    }
    if (!MODEL_ALLOWLIST.includes(body.model)) {
      return deny(400, "invalid_request_error", "model not allowed on the demo", headers);
    }
    if (!Number.isInteger(body.max_tokens) || body.max_tokens > MAX_TOKENS_CAP) {
      return deny(400, "invalid_request_error", "max_tokens exceeds the demo cap", headers);
    }
    if (body.stream) {
      return deny(400, "invalid_request_error", "streaming is not available on the demo", headers);
    }

    /* Gate 3: per-IP daily count. */
    const day = today();
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const ipKey = `ip:${day}:${ip}`;
    const ipCount = parseInt((await env.BUDGET.get(ipKey)) || "0", 10);
    const perIp = parseInt(env.PER_IP_DAILY || "5", 10);
    if (ipCount >= perIp) {
      return deny(429, "rate_limit_error",
        "daily demo limit reached for this address; try again tomorrow", headers);
    }

    /* Gate 4: global daily budget (checked before, charged after). */
    const spendKey = `spend:${day}`;
    const spent = parseFloat((await env.BUDGET.get(spendKey)) || "0");
    const budget = parseFloat(env.DAILY_BUDGET_USD || "5");
    if (spent >= budget) {
      return deny(429, "budget_exhausted",
        "the demo's daily budget is spent; try again tomorrow or run the map locally with your own key", headers);
    }

    /* Relay with the key injected server-side. */
    const upstream = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify(body),
    });

    const text = await upstream.text();

    /* Charge the gates from real usage on success. */
    if (upstream.ok) {
      try {
        const usage = JSON.parse(text).usage || {};
        const cost =
          (usage.input_tokens || 0) * IN_PRICE +
          (usage.cache_creation_input_tokens || 0) * IN_PRICE * 1.25 +
          (usage.cache_read_input_tokens || 0) * IN_PRICE * 0.1 +
          (usage.output_tokens || 0) * OUT_PRICE;
        await env.BUDGET.put(spendKey, String(spent + cost), { expirationTtl: 172800 });
        await env.BUDGET.put(ipKey, String(ipCount + 1), { expirationTtl: 172800 });
      } catch { /* accounting must never break the response */ }
    }

    return new Response(text, {
      status: upstream.status,
      headers: { "content-type": "application/json", ...headers },
    });
  },
};
