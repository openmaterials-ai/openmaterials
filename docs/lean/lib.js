// Pure, DOM-free logic for the verified-layer view. Shared by the browser and
// Node tests. Everything here parses the generated Lean text published in
// docs/data/lean.json; nothing fetches, nothing touches the DOM.
(function (root) {
  'use strict';

  // Split a string on a separator, but only at parenthesis depth zero, so
  // binder lists and product expressions survive intact.
  function splitTop(s, sep) {
    var parts = [], depth = 0, cur = '';
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      if (ch === '(' || ch === '⟨') depth++;
      else if (ch === ')' || ch === '⟩') depth--;
      if (ch === sep && depth === 0) { parts.push(cur); cur = ''; }
      else cur += ch;
    }
    parts.push(cur);
    return parts.map(function (p) { return p.trim(); }).filter(function (p) { return p !== ''; });
  }

  // A node's Lean definition, e.g.
  //   def CumulativeKappa_wrt_mfp : Dimension := <1, (-3 : Q), 1, 0, (-1 : Q)>
  // returns { leanName, exponents } with exponents as five plain strings in
  // physlib field order: length, time, mass, charge, temperature.
  function parseNodeDef(lean) {
    var name = (lean.match(/def\s+(\S+)\s*:/) || [])[1] || null;
    var tuple = lean.match(/⟨([\s\S]*)⟩/);
    var exponents = null;
    if (tuple) {
      exponents = splitTop(tuple[1], ',').map(function (part) {
        var m = part.match(/-?\d+(?:\s*\/\s*\d+)?/);
        return m ? m[0].replace(/\s+/g, '') : part;
      });
    }
    return { leanName: name, exponents: exponents };
  }

  // A theorem's pieces: its name, its binders (hypotheses), and its
  // conclusion (the statement between the top-level ':' and ':=').
  function parseTheorem(lean) {
    var name = (lean.match(/theorem\s+(\S+)/) || [])[1] || null;
    var proofIdx = lean.indexOf(':=');
    var head = proofIdx === -1 ? lean : lean.slice(0, proofIdx);
    var afterName = name ? head.slice(head.indexOf(name) + name.length) : head;
    // the goal separator is the first ':' at parenthesis depth zero
    var depth = 0, sepIdx = -1;
    for (var i = 0; i < afterName.length; i++) {
      var ch = afterName[i];
      if (ch === '(' || ch === '⟨') depth++;
      else if (ch === ')' || ch === '⟩') depth--;
      else if (ch === ':' && depth === 0) { sepIdx = i; break; }
    }
    var binders = sepIdx === -1 ? '' : afterName.slice(0, sepIdx).replace(/\s+/g, ' ').trim();
    var conclusion = sepIdx === -1 ? afterName.trim()
      : afterName.slice(sepIdx + 1).replace(/\s+/g, ' ').trim();
    return { name: name, binders: binders, conclusion: conclusion };
  }

  // An edge theorem, e.g. edge_compute_dos_to_PhononDOS with conclusion
  // "PhononDOS = Frequency". Returns the output's Lean name and the list of
  // input Lean names (the factors on the right-hand side).
  function parseEdge(lean) {
    var t = parseTheorem(lean);
    var eq = splitTop(t.conclusion, '=');
    var out = eq.length === 2 ? eq[0].trim() : ((t.name || '').match(/_to_(.+)$/) || [])[1] || null;
    var inputs = eq.length === 2 ? splitTop(eq[1], '*') : [];
    return { name: t.name, output: out, inputs: inputs, statement: t.conclusion };
  }

  // Reverse map from sanitized Lean names back to map node ids, built from
  // the nodes dict itself (key = map id, def name = Lean name).
  function leanNameIndex(nodes) {
    var idx = {};
    Object.keys(nodes || {}).forEach(function (id) {
      var n = parseNodeDef(nodes[id].lean || '');
      if (n.leanName) idx[n.leanName] = id;
    });
    return idx;
  }

  // Honest counts, straight from the published files; never hardcoded.
  function computeStats(lean, graph) {
    var stats = {
      nodes: Object.keys((lean && lean.nodes) || {}).length,
      edges: Object.keys((lean && lean.edges) || {}).length,
      identities: Object.keys((lean && lean.identities) || {}).length,
      version: (lean && lean.version) || null,
      graphNodes: null,
      graphOps: null
    };
    if (graph && Array.isArray(graph.nodes)) stats.graphNodes = graph.nodes.length;
    if (graph && Array.isArray(graph.links)) {
      var ops = {};
      graph.links.forEach(function (l) { if (l && l.op) ops[l.op] = 1; });
      stats.graphOps = Object.keys(ops).length;
    }
    return stats;
  }

  // The physlib crosswalk is optional and may not exist yet. Accept either a
  // flat { node_id: {...} } map or a { nodes: {...} } wrapper; return a plain
  // map of node id to entry object, and {} for anything unusable.
  function normalizeCrosswalk(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
    var src = (raw.nodes && typeof raw.nodes === 'object' && !Array.isArray(raw.nodes)) ? raw.nodes : raw;
    var out = {};
    Object.keys(src).forEach(function (k) {
      var v = src[k];
      if (v && typeof v === 'object' && !Array.isArray(v)) out[k] = v;
    });
    return out;
  }

  var api = {
    splitTop: splitTop,
    parseNodeDef: parseNodeDef,
    parseTheorem: parseTheorem,
    parseEdge: parseEdge,
    leanNameIndex: leanNameIndex,
    computeStats: computeStats,
    normalizeCrosswalk: normalizeCrosswalk
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.LeanLib = api;
})(typeof self !== 'undefined' ? self : this);
