// node --test infra/site/src/shortlinks.test.mjs
// The short-link store's pure logic: mint validation, code discipline, and
// the crawlable shell. No KV, no fetch: the Worker supplies those.
import test from "node:test";
import assert from "node:assert";
import {
  CODE_ALPHABET, CODE_LEN, MAX_MEMBERS,
  randomCode, parseCode, validateMintBody, shortlinkHTML, shortlinkNotFoundHTML,
} from "./shortlinks.js";

const record = (name) => ({ id: "a".repeat(64), lineage: { node: "ThermalConductivity", material: name } });

test("codes: unambiguous alphabet, fixed length, strict parse", () => {
  assert.ok(!/[0OIl]/.test(CODE_ALPHABET), "ambiguous glyphs excluded");
  const bytes = new Uint8Array(CODE_LEN).map((_, i) => i * 37);
  const code = randomCode(bytes);
  assert.strictEqual(code.length, CODE_LEN);
  assert.strictEqual(parseCode(code), code);
  assert.strictEqual(parseCode(code.slice(1)), null);
  assert.strictEqual(parseCode(code + "!"), null);
  assert.strictEqual(parseCode(""), null);
});

test("mint: a bare record normalizes to a one-element envelope", () => {
  const v = validateMintBody(JSON.stringify(record("Si")));
  assert.ok(v.ok);
  assert.strictEqual(v.envelope.v, 1);
  assert.strictEqual(v.envelope.lineages.length, 1);
});

test("mint: a v1 envelope passes, the malformed shapes are refused", () => {
  const good = { v: 1, doc: { title: "T" }, lineages: [record("Si"), record("Ge")] };
  assert.ok(validateMintBody(JSON.stringify(good)).ok);
  for (const [bad, why] of [
    ["", "empty"],
    ["not json", "not JSON"],
    ["[1,2]", "array"],
    [JSON.stringify({ v: 2, lineages: [record("Si")] }), "unknown v"],
    [JSON.stringify({ v: 1, lineages: [] }), "empty envelope"],
    [JSON.stringify({ v: 1, lineages: [record("Si")], lineage: {} }), "both keys"],
    [JSON.stringify({ hello: "world" }), "neither"],
    [JSON.stringify({ v: 1, lineages: [{ id: "x" }] }), "member without lineage"],
    [JSON.stringify({ v: 1, lineages: Array.from({ length: MAX_MEMBERS + 1 }, () => record("Si")) }), "too many"],
  ]) {
    assert.strictEqual(validateMintBody(bad).ok, false, why);
  }
});

test("mint: the 64 KB cap holds", () => {
  const fat = { v: 1, lineages: [{ ...record("Si"), pad: "x".repeat(70 * 1024) }] };
  assert.strictEqual(validateMintBody(JSON.stringify(fat)).ok, false);
});

test("the shell carries the stored metadata and redirects into #s=", () => {
  const env = { v: 1, doc: { title: "CNT paper", source: "paper:cnt-2021-barbalinardo" }, lineages: [record("SWCNT"), record("SWCNT")] };
  const page = shortlinkHTML(env, "Abc123XYZ", "https://openmaterials.ai");
  assert.ok(page.includes('og:title" content="CNT paper"'));
  assert.ok(page.includes("2 lineages"));
  assert.ok(page.includes("paper:cnt-2021-barbalinardo"));
  assert.ok(page.includes("/play/#s=Abc123XYZ"));
  const anon = shortlinkHTML({ v: 1, lineages: [record("Si")] }, "Abc123XYZ", "https://openmaterials.ai");
  assert.ok(anon.includes("A shared set of lineages"), "no fabricated title");
  assert.ok(anon.includes("1 lineage,") || anon.includes("1 lineage"), "singular count");
});

test("the empty state names the code and fabricates nothing", () => {
  const page = shortlinkNotFoundHTML("Abc123XYZ", "https://openmaterials.ai");
  assert.ok(page.includes("Abc123XYZ"));
  assert.ok(!page.includes("og:title"));
});

test("escaping: hostile doc fields cannot break out of the shell", () => {
  const env = { v: 1, doc: { title: '<script>alert(1)</script>"' }, lineages: [record("Si")] };
  const page = shortlinkHTML(env, "Abc123XYZ", "https://openmaterials.ai");
  assert.ok(!page.includes("<script>alert"));
  assert.ok(page.includes("&lt;script&gt;"));
});
