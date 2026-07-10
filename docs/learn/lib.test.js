const test = require('node:test');
const assert = require('node:assert');
const L = require('./lib.js');

test('validateExtraction drops a value-instance with no quote', () => {
  const raw = { coverage: ['Temperature'],
    value_instances: [
      { node_id: 'ThermalConductivity[transport_model=wigner]', material: 'Si',
        conditions: '300K', value: 166, units: 'W/m/K', quote: 'kappa = 166 W/m/K', page: 4 },
      { node_id: 'Temperature', material: 'Si', conditions: '', value: 300, units: 'K',
        quote: '', page: 1 }
    ], formulas: [], novel_quantities: [] };
  const known = new Set(['Temperature', 'ThermalConductivity[transport_model=wigner]']);
  const v = L.validateExtraction(raw, known);
  assert.strictEqual(v.value_instances.length, 1);
  assert.strictEqual(v.value_instances[0].value, 166);
  assert.deepStrictEqual(v.warnings.length >= 1, true);
});

test('validateExtraction marks an unknown node_id as novel', () => {
  const raw = { coverage: [], value_instances: [
    { node_id: 'NotARealNode', material: 'Si', conditions: '', value: 1, units: 'x',
      quote: 'x = 1', page: 1 }], formulas: [], novel_quantities: [] };
  const v = L.validateExtraction(raw, new Set(['Temperature']));
  assert.strictEqual(v.value_instances[0].node_id, null);
  assert.strictEqual(v.value_instances[0].novel, true);
});

test('toInstances emits the commons instance JSON shape', () => {
  const confirmed = [{ node_id: 'ThermalConductivity[transport_model=wigner]', material: 'Si',
    conditions: '300K', value: 166, units: 'W/m/K', uncertainty: null,
    quote: 'kappa = 166 W/m/K', page: 4, source_ref: 'esfarjani-2011' }];
  const recs = L.toInstances(confirmed);
  assert.strictEqual(recs.length, 1);
  const r = recs[0];
  assert.deepStrictEqual(Object.keys(r).sort(),
    ['conditions','material','source','units','uncertainty','value','variable'].sort());
  assert.strictEqual(r.variable, 'ThermalConductivity[transport_model=wigner]');
  assert.strictEqual(r.source.kind, 'measurement');
  assert.strictEqual(r.source.ref, 'esfarjani-2011');
});

test('aggregateCoverage unions touched nodes and counts instances per node', () => {
  const papers = [
    { coverage: ['A','B'], value_instances: [{node_id:'A'},{node_id:'A'}] },
    { coverage: ['B','C'], value_instances: [{node_id:'C'}] }
  ];
  const agg = L.aggregateCoverage(papers);
  assert.deepStrictEqual([...agg.touched].sort(), ['A','B','C']);
  assert.strictEqual(agg.instanceCount['A'], 2);
  assert.strictEqual(agg.instanceCount['C'], 1);
});

test('buildInstance emits the exact committed instance schema key set', () => {
  const vi = { node_id: 'ThermalConductivity[transport_model=wigner]', material: 'Si',
    conditions: '277 K', value: 166, units: 'W/m/K', uncertainty: null,
    quote: 'Considering the extrapolated value to be 166 W/mK', page: 8, kind: 'measurement' };
  const inst = L.buildInstance(vi, { title: 'Heat transport in silicon', ref: 'esfarjani-2011' });
  assert.deepStrictEqual(Object.keys(inst).sort(),
    ['conditions', 'material', 'source', 'units', 'uncertainty', 'value', 'variable'].sort());
  assert.deepStrictEqual(Object.keys(inst.source).sort(),
    ['detail', 'kind', 'ref'].sort());
  assert.strictEqual(inst.variable, 'ThermalConductivity[transport_model=wigner]');
  assert.strictEqual(inst.source.kind, 'measurement');
  assert.strictEqual(inst.source.ref, 'paper:esfarjani-2011');
  assert.ok(inst.source.detail.indexOf('(p. 8)') !== -1);
  assert.ok(inst.source.detail.indexOf('Heat transport in silicon') !== -1);
});

test('buildInstance defaults source.kind to simulation when unspecified', () => {
  const vi = { node_id: 'Temperature', material: 'Si', conditions: '', value: 300,
    units: 'K', uncertainty: null, quote: 'T = 300 K', page: 1 };
  const inst = L.buildInstance(vi, { title: 'Some paper', ref: 'some-paper' });
  assert.strictEqual(inst.source.kind, 'simulation');
});

test('instanceSlug yields a valid lowercase material-variable-source slug', () => {
  const inst = { variable: 'ThermalConductivity[transport_model=wigner]', material: 'Si',
    source: { ref: 'paper:esfarjani-2011' } };
  const slug = L.instanceSlug(inst);
  assert.strictEqual(slug, 'si-thermalconductivity-esfarjani-2011');
  assert.match(slug, /^[a-z0-9]+(-[a-z0-9]+)*$/);
});

test('demo fixture passes validateExtraction against the catalog', () => {
  const fs = require('node:fs');
  const fixture = JSON.parse(fs.readFileSync(__dirname + '/demo/esfarjani-si.json', 'utf8'));
  const catalog = JSON.parse(fs.readFileSync(__dirname + '/../data/catalog.json', 'utf8'));
  const known = new Set(catalog.map(function (c) { return c.id; }));
  const v = L.validateExtraction(fixture.extraction, known);
  assert.strictEqual(v.value_instances.length, 1);
  assert.strictEqual(v.value_instances[0].node_id, 'ThermalConductivity[transport_model=wigner]');
  assert.strictEqual(typeof v.value_instances[0].value, 'number');
});
