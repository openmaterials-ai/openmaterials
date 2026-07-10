// Pure, DOM-free logic for the Learn-a-paper view. Shared by the browser and Node tests.
(function (root) {
  'use strict';

  function validateExtraction(raw, knownIds) {
    const warnings = [];
    raw = raw || {};
    const coverage = Array.isArray(raw.coverage) ? raw.coverage.filter(function (id) {
      const ok = knownIds.has(id); if (!ok) warnings.push('coverage names unknown node: ' + id);
      return ok;
    }) : [];
    const value_instances = (Array.isArray(raw.value_instances) ? raw.value_instances : [])
      .filter(function (vi) {
        if (!vi || typeof vi.quote !== 'string' || vi.quote.trim() === '') {
          warnings.push('dropped a value with no quote: ' + JSON.stringify(vi && vi.value));
          return false;
        }
        if (typeof vi.value !== 'number' || !isFinite(vi.value)) {
          warnings.push('dropped a non-numeric value');
          return false;
        }
        return true;
      })
      .map(function (vi) {
        const known = vi.node_id && knownIds.has(vi.node_id);
        return {
          node_id: known ? vi.node_id : null,
          novel: !known,
          material: vi.material || '',
          conditions: vi.conditions || '',
          value: vi.value,
          units: vi.units || '',
          uncertainty: (typeof vi.uncertainty === 'number') ? vi.uncertainty : null,
          quote: vi.quote.trim(),
          page: (typeof vi.page === 'number') ? vi.page : null
        };
      });
    const novel_quantities = Array.isArray(raw.novel_quantities) ? raw.novel_quantities : [];
    return { coverage: coverage, value_instances: value_instances,
             novel_quantities: novel_quantities, warnings: warnings };
  }

  function toInstances(confirmed) {
    return confirmed.map(function (c) {
      return {
        variable: c.node_id,
        material: c.material || '',
        conditions: c.conditions || {},
        value: c.value,
        units: c.units || '',
        uncertainty: (typeof c.uncertainty === 'number') ? c.uncertainty : null,
        source: { kind: 'measurement', ref: c.source_ref || '',
                  detail: c.quote ? ('quoted: ' + c.quote) : '' }
      };
    });
  }

  function slugify(s) {
    return String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }

  // Build a single contributable instance record matching the committed
  // docs/data/instances schema exactly:
  // {variable, material, conditions, value, units, uncertainty, source{kind, ref, detail}}
  // `vi` is a validated value-instance (node_id, material, conditions, value,
  // units, uncertainty, quote, page); `paper` is {title, ref, kind?}.
  function buildInstance(vi, paper) {
    paper = paper || {};
    const title = paper.title || '';
    const paperSlug = paper.ref || slugify(title);
    const kind = paper.kind === 'measurement' ? 'measurement'
      : (paper.kind === 'simulation' ? 'simulation'
        : (vi && vi.kind === 'measurement' ? 'measurement' : 'simulation'));
    let detail = (vi && vi.quote) ? String(vi.quote) : '';
    if (vi && (vi.page !== null && vi.page !== undefined && vi.page !== '')) {
      detail += ' (p. ' + vi.page + ')';
    }
    if (title) detail += (detail ? ' ' : '') + title;
    return {
      variable: vi.node_id,
      material: vi.material || '',
      conditions: vi.conditions || '',
      value: vi.value,
      units: vi.units || '',
      uncertainty: (typeof vi.uncertainty === 'number') ? vi.uncertainty : null,
      source: {
        kind: kind,
        ref: 'paper:' + paperSlug,
        detail: detail
      }
    };
  }

  // Filename slug for a contributable instance: material-variable-source hints,
  // lowercase, matching the docs/data/instances naming convention.
  function instanceSlug(inst) {
    inst = inst || {};
    const variable = (inst.variable || '').replace(/\[.*$/, '');
    const paperSlug = (inst.source && inst.source.ref) ? inst.source.ref.replace(/^paper:/, '') : '';
    return slugify([inst.material, variable, paperSlug].filter(Boolean).join('-'));
  }

  function aggregateCoverage(papers) {
    const touched = new Set();
    const instanceCount = {};
    (papers || []).forEach(function (p) {
      (p.coverage || []).forEach(function (id) { touched.add(id); });
      (p.value_instances || []).forEach(function (vi) {
        if (vi && vi.node_id) {
          touched.add(vi.node_id);
          instanceCount[vi.node_id] = (instanceCount[vi.node_id] || 0) + 1;
        }
      });
    });
    return { touched: touched, instanceCount: instanceCount };
  }

  const api = { validateExtraction: validateExtraction, toInstances: toInstances,
                aggregateCoverage: aggregateCoverage, slugify: slugify,
                buildInstance: buildInstance, instanceSlug: instanceSlug };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.LearnLib = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
