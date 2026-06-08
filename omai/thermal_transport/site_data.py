"""Build the static data files the openmaterials.ai site reads:
graph.json (variables + formulas, from the operator layer) and
instances.json (bundled from docs/data/instances/*.json)."""
from __future__ import annotations

import json
from pathlib import Path

import sympy as sp

from omai.operator.space import ObservableSpace
from omai.thermal_transport.operator import EDGES, NODES

_DOCS = Path(__file__).resolve().parents[2] / "docs"

# Canonical LaTeX symbol per variable (consistent symbolic names, not words).
# Matches the IndexedBase symbols the operator-layer formulas are written in.
SYMBOLS = {
    "Potential": r"V",
    "Temperature": r"T",
    "BornCharges": r"Z^{*}",
    "DielectricTensor": r"\varepsilon_{\infty}",
    "IsotopeAbundances": r"g_{\mathrm{iso}}",
    "Trajectory": r"\mathbf{r}(t)",
    "ForceConstants[order=2]": r"\Phi^{(2)}",
    "ForceConstants[order=3]": r"\Phi^{(3)}",
    "HeatCurrent": r"\mathbf{J}",
    "BareDynamicalMatrix": r"D^{0}",
    "MeanSquaredDisplacement": r"\langle u^{2}\rangle",
    "VelocityAutocorrelation": r"\langle v(0)v(t)\rangle",
    "DynamicalMatrix": r"D",
    "HeatCurrentACF": r"\langle JJ\rangle",
    "PhononDOS": r"g(\omega)",
    "ThermalConductivity[transport_model=hnemd]": r"\kappa_{\mathrm{hnemd}}",
    "ThermalConductivity[transport_model=nemd]": r"\kappa_{\mathrm{nemd}}",
    "Eigenvectors": r"e",
    "Frequency": r"\omega",
    "ThermalConductivity[transport_model=green_kubo]": r"\kappa_{\mathrm{gk}}",
    "GroupVelocity": r"v",
    "Linewidth[channel=anharmonic_3ph]": r"\Gamma_{\mathrm{3ph}}",
    "Linewidth[channel=isotope]": r"\Gamma_{\mathrm{iso}}",
    "Entropy": r"S",
    "Gruneisen": r"\gamma",
    "HeatCapacity": r"c",
    "HelmholtzFreeEnergy": r"F",
    "InternalEnergy": r"E",
    "PhaseSpace3Phonon": r"P_{3}",
    "Linewidth[channel=boundary]": r"\Gamma_{\mathrm{bnd}}",
    "MolarEntropy": r"S_{\mathrm{m}}",
    "MolarHeatCapacity": r"C_{\mathrm{m}}",
    "MolarHelmholtzFreeEnergy": r"F_{\mathrm{m}}",
    "MolarInternalEnergy": r"E_{\mathrm{m}}",
    "VolumetricHeatCapacity": r"C_{V}",
    "Linewidth[channel=total]": r"\Gamma",
    "MeanFreeDisplacement[bte_solver=rta]": r"\lambda_{\mathrm{rta}}",
    "ThermalConductivity[transport_model=qhgk]": r"\kappa_{\mathrm{qhgk}}",
    "MeanFreeDisplacement[bte_solver=direct_inverse]": r"\lambda_{\mathrm{dinv}}",
    "ThermalConductivity[transport_model=wigner_coherences]": r"\kappa_{\mathrm{coh}}",
    "ThermalConductivity[bte_solver=rta]": r"\kappa^{\mathrm{rta}}",
    "CumulativeKappa[wrt=mfp]": r"\kappa^{\mathrm{cum}}_{\lambda}",
    "CumulativeKappa[wrt=omega]": r"\kappa^{\mathrm{cum}}_{\omega}",
    "ThermalConductivity[bte_solver=direct_inverse]": r"\kappa^{\mathrm{dinv}}",
    "ThermalConductivity[transport_model=wigner_populations]": r"\kappa_{\mathrm{pop}}",
    "ThermalConductivity[transport_model=wigner]": r"\kappa",
}


def _layers() -> dict[str, int]:
    producer = {}
    for op in EDGES:
        for out in op.outputs:
            producer[out.name] = op
    cache: dict[str, int] = {}

    def layer_of(name: str) -> int:
        if name in cache:
            return cache[name]
        op = producer.get(name)
        if op is None or not getattr(op, "inputs", None):
            cache[name] = 0
            return 0
        cache[name] = 1 + max(layer_of(i.name) for i in op.inputs)
        return cache[name]

    for s in NODES:
        layer_of(s.name)
    return cache


def build_graph_dict() -> dict:
    layers = _layers()
    target_formula: dict[str, str] = {}
    for op in EDGES:
        try:
            latex = sp.latex(op.formula) if getattr(op, "formula", None) is not None else None
        except Exception:
            latex = None
        for o in op.outputs:
            if latex and o.name not in target_formula:
                target_formula[o.name] = latex
    nodes = [
        {
            "id": s.name,
            "type": "observable" if isinstance(s, ObservableSpace) else "hidden",
            "layer": layers.get(s.name, 0),
            "kind": "symbolic",
            "symbol": SYMBOLS.get(s.name, s.name),
            "formula": target_formula.get(s.name),
        }
        for s in NODES
    ]
    links = []
    for op in EDGES:
        for i in op.inputs:
            for o in op.outputs:
                links.append({"source": i.name, "target": o.name, "op": op.name})
    return {"nodes": nodes, "links": links}


def write_graph(path: Path | None = None) -> Path:
    path = path or (_DOCS / "data" / "graph.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_graph_dict()))
    return path


def build_instances(instances_dir: Path | None = None) -> list[dict]:
    instances_dir = instances_dir or (_DOCS / "data" / "instances")
    out = []
    for f in sorted(instances_dir.glob("*.json")):
        rec = json.loads(f.read_text())
        for key in ("variable", "material", "conditions", "value", "units", "source"):
            if key not in rec:
                raise ValueError(f"{f.name}: missing '{key}'")
        if rec["source"].get("kind") not in ("simulation", "measurement"):
            raise ValueError(f"{f.name}: source.kind must be simulation|measurement")
        out.append(rec)
    return out


def write_instances(path: Path | None = None) -> Path:
    path = path or (_DOCS / "data" / "instances.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_instances()))
    return path


if __name__ == "__main__":
    g = write_graph()
    i = write_instances()
    print(f"wrote {g}\nwrote {i}")
