// node --test docs/lean/roadmap/lib.test.js
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const { parseRoadmap, domainLabel, DIFFICULTIES } = require("./lib.js");

const published = JSON.parse(fs.readFileSync(
  path.join(__dirname, "..", "..", "data", "lean_roadmap.json"), "utf8"));

test("published roadmap parses and is internally consistent", () => {
  const r = parseRoadmap(published);
  assert.ok(r.total > 0);
  const sum = DIFFICULTIES.reduce((a, d) => a + r.counts[d], 0);
  assert.strictEqual(sum, r.total);
  assert.ok(r.proven > 0);
  assert.ok(r.version.length > 0);
});

test("every row carries a nonempty reason", () => {
  for (const row of published.rows) {
    assert.ok(typeof row.reason === "string" && row.reason.length > 0,
      row.op + " has no reason");
  }
});

test("proven rows are marked provable or trivial, never hard or na", () => {
  for (const row of published.rows) {
    if (row.proven) assert.ok(["easy", "trivial"].includes(row.difficulty),
      row.op + " is proven but rated " + row.difficulty);
  }
});

test("parseRoadmap rejects a corrupted document", () => {
  assert.throws(() => parseRoadmap({ rows: [{ op: "x", domain: "d", difficulty: "impossible" }] }));
  assert.throws(() => parseRoadmap({}));
  const bad = JSON.parse(JSON.stringify(published));
  bad.counts.hard += 1;
  assert.throws(() => parseRoadmap(bad));
});

test("domainLabel prettifies", () => {
  assert.strictEqual(domainLabel("thermal_transport"), "Thermal transport");
  assert.strictEqual(domainLabel("mechanics"), "Mechanics");
});
