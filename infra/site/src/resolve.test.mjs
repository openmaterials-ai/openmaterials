// node --test infra/site/src/resolve.test.mjs
// Exercises the permalink logic against the REAL committed projection, so a
// schema drift in instances.json fails here before it fails at the edge.
import test from "node:test";
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { parseHash, resolveId, permalinkHTML, notFoundHTML, humanProperty } from "./resolve.js";

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
