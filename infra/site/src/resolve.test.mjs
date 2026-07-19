// node --test infra/site/src/resolve.test.mjs
// Exercises the permalink logic against the REAL committed projection, so a
// schema drift in instances.json fails here before it fails at the edge.
import test from "node:test";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { parseHash, parsePrefix, resolveId, resolvePrefix, permalinkHTML, notFoundHTML, ambiguousHTML, humanProperty, parseLPath, entriesBySource, entrySourceRef, sourceListingHTML, sourceMismatchHTML } from "./resolve.js";

const here = dirname(fileURLToPath(import.meta.url));
const instances = JSON.parse(
  readFileSync(join(here, "..", "..", "..", "docs", "data", "instances.json"), "utf8")
);

test("every committed entry resolves by its own id", () => {
  assert.ok(instances.length > 0);
  for (const entry of instances) {
    assert.match(entry.id, /^[0-9a-f]{64}$/, "projection entry lacks a canonical id");
    const r = resolveId(instances, entry.id);
    assert.ok(r.ok && r.entry === entry);
  }
});

test("parseHash accepts 64-hex only", () => {
  const good = instances[0].id;
  assert.strictEqual(parseHash(good), good);
  assert.strictEqual(parseHash(good.toUpperCase()), good);
  assert.strictEqual(parseHash(" " + good + " "), good);
  for (const bad of ["", null, "abc", good.slice(0, 63), good + "0", "g".repeat(64)]) {
    assert.strictEqual(parseHash(bad), null, String(bad));
  }
});

test("an unknown well-formed hash does not resolve and the empty state names it", () => {
  const ghost = "0".repeat(64);
  assert.strictEqual(resolveId(instances, ghost).ok, false);
  const page = notFoundHTML(ghost, "https://openmaterials.ai");
  assert.ok(page.includes(ghost), "empty state must name the hash verbatim");
  assert.ok(!page.includes("og:title"), "empty state carries no fabricated card");
});

test("the permalink shell carries real OG metadata and redirects to the datasheet", () => {
  const entry = instances.find((e) => e.variable && e.value != null) || instances[0];
  const page = permalinkHTML(entry, "https://openmaterials.ai");
  assert.ok(page.includes('property="og:title"'));
  assert.ok(page.includes(entry.id.slice(0, 12)), "description cites the id prefix");
  assert.ok(page.includes(`/play/#id=${entry.id}`), "redirect targets the one renderer");
  assert.ok(String(page.match(/og:description[^>]*/)).length > 0);
  if (entry.value != null) assert.ok(page.includes(String(entry.value)), "the committed value is on the card");
});

test("humanProperty reads the node spelling", () => {
  assert.strictEqual(humanProperty("ThermalConductivity[bte_solver=rta]"), "Thermal conductivity");
  assert.strictEqual(humanProperty("MassDensity"), "Mass density");
});

test("prefixes resolve git-style at the edge: unique, ambiguous, none", () => {
  const full = instances[0].id;
  assert.strictEqual(parsePrefix(full.slice(0, 12)), full.slice(0, 12));
  assert.strictEqual(parsePrefix(full.slice(0, 7)), null, "below the 8-char floor");
  const r = resolvePrefix(instances, full.slice(0, 12));
  assert.ok(r.ok && r.entry.id === full);
  assert.strictEqual(resolvePrefix(instances, "0".repeat(12)).ok, false);
  const shared = instances.find((a) =>
    instances.some((b) => b !== a && b.id.slice(0, 8) === a.id.slice(0, 8)));
  if (shared) {
    const amb = resolvePrefix(instances, shared.id.slice(0, 8));
    assert.ok(!amb.ok && Array.isArray(amb.ambiguous) && amb.ambiguous.length > 1);
    const page = ambiguousHTML(shared.id.slice(0, 8), amb.ambiguous, "https://openmaterials.ai");
    for (const id of amb.ambiguous) assert.ok(page.includes(id.slice(0, 12)));
  }
});

test("source-first paths parse and resolve: listing, pair, mismatch honesty", () => {
  const withSrc = instances.find((e) => e.source && /^[a-z][a-z0-9+.-]*:/.test(e.source.ref || ""));
  assert.ok(withSrc, "corpus has at least one scheme-sourced value");
  const ref = withSrc.source.ref;
  // path forms
  assert.deepStrictEqual(parseLPath(withSrc.id), { hash: withSrc.id });
  assert.deepStrictEqual(parseLPath(ref), { ref });
  assert.deepStrictEqual(parseLPath(`${ref}/${withSrc.id.slice(0, 12)}`),
    { ref, hash: withSrc.id.slice(0, 12) });
  assert.strictEqual(parseLPath("no-scheme-here"), null);
  // a DOI-style ref with a slash keeps the whole ref together
  assert.deepStrictEqual(parseLPath("doi:10.1063/5.0020443"), { ref: "doi:10.1063/5.0020443" });
  assert.deepStrictEqual(parseLPath(`doi:10.1063/5.0020443/${"a".repeat(12)}`),
    { ref: "doi:10.1063/5.0020443", hash: "a".repeat(12) });
  // the family listing carries every member and no one else's
  const family = entriesBySource(instances, ref);
  assert.ok(family.length >= 1 && family.every((e) => e.source.ref === ref));
  const page = sourceListingHTML(ref, family, "https://openmaterials.ai");
  for (const e of family) assert.ok(page.includes(e.id.slice(0, 12)));
  assert.ok(page.includes(`${family.length} committed value`));
  // the honesty gate: a claimed namespace that is not the id's own refuses
  const other = instances.find((e) => entrySourceRef(e) !== ref);
  if (other) {
    const mism = sourceMismatchHTML(ref, other, "https://openmaterials.ai");
    assert.ok(mism.includes(other.id.slice(0, 12)));
    assert.ok(mism.includes("does not belong"));
  }
});
