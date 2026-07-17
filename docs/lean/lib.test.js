const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const L = require('./lib.js');

test('parseNodeDef reads the Lean name and the five exponents', () => {
  const def = 'def CumulativeKappa_wrt_mfp : Dimension := ⟨1, (-3 : ℚ), 1, 0, (-1 : ℚ)⟩';
  const n = L.parseNodeDef(def);
  assert.strictEqual(n.leanName, 'CumulativeKappa_wrt_mfp');
  assert.deepStrictEqual(n.exponents, ['1', '-3', '1', '0', '-1']);
});

test('parseNodeDef keeps rational exponents as fractions', () => {
  const n = L.parseNodeDef('def X : Dimension := ⟨(1/2 : ℚ), 0, 0, 0, 0⟩');
  assert.deepStrictEqual(n.exponents, ['1/2', '0', '0', '0', '0']);
});

test('parseEdge splits an edge theorem into output and input factors', () => {
  const lean = 'theorem edge_apply_nac_correction_to_DynamicalMatrix :\n' +
    '  DynamicalMatrix = BareDynamicalMatrix * BornCharges * DielectricTensor := by\n' +
    '  apply Dimension.ext <;> simp [DynamicalMatrix]';
  const e = L.parseEdge(lean);
  assert.strictEqual(e.name, 'edge_apply_nac_correction_to_DynamicalMatrix');
  assert.strictEqual(e.output, 'DynamicalMatrix');
  assert.deepStrictEqual(e.inputs, ['BareDynamicalMatrix', 'BornCharges', 'DielectricTensor']);
  assert.strictEqual(e.statement,
    'DynamicalMatrix = BareDynamicalMatrix * BornCharges * DielectricTensor');
});

test('parseTheorem separates binders from the conclusion on an identity', () => {
  const lean = 'theorem identity_contract_zt (PF : ℝ) (S : ℝ) ' +
    '(h_PF : PF = (sigma_el * S ^ 2)) :\n' +
    '    (PF * T) / (kappa_tot) = (T * sigma_el * S ^ 2) / ((kappa + kappa_e)) := by subst h_PF';
  const t = L.parseTheorem(lean);
  assert.strictEqual(t.name, 'identity_contract_zt');
  assert.ok(t.binders.indexOf('(h_PF : PF = (sigma_el * S ^ 2))') !== -1);
  assert.strictEqual(t.conclusion,
    '(PF * T) / (kappa_tot) = (T * sigma_el * S ^ 2) / ((kappa + kappa_e))');
});

test('leanNameIndex maps sanitized Lean names back to map node ids', () => {
  const nodes = {
    'CumulativeKappa[wrt=mfp]': { lean: 'def CumulativeKappa_wrt_mfp : Dimension := ⟨1, 0, 0, 0, 0⟩' },
    'BandGap': { lean: 'def BandGap : Dimension := ⟨2, (-2 : ℚ), 1, 0, 0⟩' }
  };
  const idx = L.leanNameIndex(nodes);
  assert.strictEqual(idx['CumulativeKappa_wrt_mfp'], 'CumulativeKappa[wrt=mfp]');
  assert.strictEqual(idx['BandGap'], 'BandGap');
});

test('computeStats counts what the files hold, nothing more', () => {
  const s = L.computeStats(
    { version: 'abc', nodes: { A: {}, B: {} }, edges: { e: {} }, identities: {} },
    { nodes: [1, 2, 3], links: [{ op: 'x' }, { op: 'x' }, { op: 'y' }, {}] });
  assert.deepStrictEqual(s, {
    nodes: 2, edges: 1, identities: 0, version: 'abc', graphNodes: 3, graphOps: 2 });
});

test('normalizeCrosswalk tolerates absence and both plausible shapes', () => {
  assert.deepStrictEqual(L.normalizeCrosswalk(null), {});
  assert.deepStrictEqual(L.normalizeCrosswalk([1, 2]), {});
  assert.deepStrictEqual(L.normalizeCrosswalk({ BandGap: { physlib: 'X' } }),
    { BandGap: { physlib: 'X' } });
  assert.deepStrictEqual(L.normalizeCrosswalk({ nodes: { BandGap: { physlib: 'X' } } }),
    { BandGap: { physlib: 'X' } });
  assert.deepStrictEqual(L.normalizeCrosswalk({ version: 'v1', BandGap: { physlib: 'X' } }),
    { BandGap: { physlib: 'X' } });
});

test('the published lean.json parses whole: every node, edge, identity', () => {
  const lean = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'data', 'lean.json'), 'utf8'));
  const stats = L.computeStats(lean, null);
  assert.strictEqual(stats.nodes, Object.keys(lean.nodes).length);
  assert.strictEqual(stats.edges, Object.keys(lean.edges).length);
  assert.strictEqual(stats.identities, Object.keys(lean.identities).length);
  Object.keys(lean.nodes).forEach((id) => {
    const n = L.parseNodeDef(lean.nodes[id].lean);
    assert.ok(n.leanName, id + ' has a Lean name');
    assert.strictEqual(n.exponents.length, 5, id + ' has five exponents');
  });
  const idx = L.leanNameIndex(lean.nodes);
  Object.keys(lean.edges).forEach((op) => {
    const e = L.parseEdge(lean.edges[op].lean);
    assert.ok(e.output, op + ' has an output');
    assert.ok(e.inputs.length >= 1, op + ' has inputs');
    assert.ok(idx[e.output], op + ' output resolves to a map node id');
  });
  Object.keys(lean.identities).forEach((name) => {
    const t = L.parseTheorem(lean.identities[name].lean);
    assert.ok(t.conclusion.indexOf('=') !== -1, name + ' states an equation');
  });
});
