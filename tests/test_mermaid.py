"""Mermaid export: sub-maps renderable in any markdown viewer."""
import pytest

from omai.mermaid import (
    mermaid_from_edges, mermaid_from_proposal, mermaid_from_view, mermaid_lineage,
)


def test_edges_render_with_quoted_labels_and_types():
    out = mermaid_from_edges([
        ["Frequency", "compute_dos", "PhononDOS"],
        ["ThermalConductivity[bte_solver=direct_inverse]",
         "resolve_thermal_conductivity", "ThermalConductivity"],
    ])
    assert out.startswith("flowchart LR")
    # labeled node ids are sanitized but the visible label is the real id
    assert '["ThermalConductivity[bte_solver=direct_inverse]"]' in out
    assert ":::observable" in out
    assert '-- "compute dos" -->' in out
    assert "classDef observable" in out


def test_lineage_walks_upstream_and_caps_honestly():
    out = mermaid_lineage("PhononDOS")
    assert "compute dos" in out and "Frequency" in out
    # a deep node hits the cap and SAYS so
    deep = mermaid_lineage("ZT", max_edges=5)
    assert "truncated at 5 edges" in deep
    with pytest.raises(ValueError):
        mermaid_lineage("NotANode")


def test_view_and_proposal_shapes():
    v = mermaid_from_view({"v": "8aea09f90c24", "e": [["Frequency", "compute_dos", "PhononDOS"]]})
    assert "map view (8aea09f90c24)" in v
    p = mermaid_from_proposal({"paper": "X", "claims": [
        {"node_id": "PhononDOS", "validation": {"survives": True}}]})
    assert "compute dos" in p and "title: X" in p
