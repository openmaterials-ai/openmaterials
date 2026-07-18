// Pure parsing/counting logic for the formalization roadmap page.
// DOM-free so node:test can exercise it directly (same pattern as ../lib.js).

const DIFFICULTIES = ["easy", "trivial", "hard", "na"];

const DIFF_LABEL = {
  easy: "Provable",
  trivial: "Trivial",
  hard: "Needs analysis",
  na: "Nothing to prove",
};

// Validate the published roadmap and derive everything the page renders.
// Throws on a malformed document so the page shows one honest error line
// instead of a half-rendered table.
function parseRoadmap(doc) {
  if (!doc || !Array.isArray(doc.rows)) throw new Error("roadmap: missing rows");
  const counts = { easy: 0, trivial: 0, hard: 0, na: 0 };
  const domains = new Map();
  let proven = 0;
  for (const r of doc.rows) {
    if (!DIFFICULTIES.includes(r.difficulty)) {
      throw new Error("roadmap: unknown difficulty " + r.difficulty);
    }
    if (typeof r.op !== "string" || typeof r.domain !== "string") {
      throw new Error("roadmap: row missing op/domain");
    }
    counts[r.difficulty] += 1;
    if (r.proven) proven += 1;
    if (!domains.has(r.domain)) domains.set(r.domain, []);
    domains.get(r.domain).push(r);
  }
  for (const d of DIFFICULTIES) {
    if (doc.counts && doc.counts[d] !== undefined && doc.counts[d] !== counts[d]) {
      throw new Error("roadmap: published count for " + d + " disagrees with rows");
    }
  }
  if (doc.proven !== undefined && doc.proven !== proven) {
    throw new Error("roadmap: published proven count disagrees with rows");
  }
  return {
    version: doc.version || "unknown",
    total: doc.rows.length,
    counts,
    proven,
    domains,
  };
}

// "thermal_transport" -> "Thermal transport"
function domainLabel(name) {
  const s = String(name).replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

if (typeof module !== "undefined") {
  module.exports = { parseRoadmap, domainLabel, DIFF_LABEL, DIFFICULTIES };
}
