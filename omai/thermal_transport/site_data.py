"""Build the static data files the openmaterials.ai site reads:
graph.json (variables + formulas, from the operator layer) and
instances.json (bundled from docs/data/instances/*.json)."""
from __future__ import annotations

import json
from pathlib import Path

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


def build_graph_dict() -> dict:
    from omai import map_data
    from omai.thermal_transport.domain import THERMAL_TRANSPORT
    return map_data.build_graph_dict((THERMAL_TRANSPORT,))


def write_graph(path: Path | None = None) -> Path:
    path = path or (_DOCS / "data" / "graph.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_graph_dict()))
    return path


def build_instances(instances_dir: Path | None = None) -> list[dict]:
    from omai import map_data
    return map_data.build_instances(instances_dir)


def write_instances(path: Path | None = None) -> Path:
    path = path or (_DOCS / "data" / "instances.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_instances()))
    return path


def record_instance(
    *, variable, material, value, units, source_kind, source_ref,
    conditions=None, uncertainty=None, detail=None, instances_dir=None,
):
    """Append one real value of a variable to the database as an instance file.

    This is the bridge a code (or a paper) calls to attach a value: pass the
    variable it computed/measured, the value and units, and the source. The value
    must be real; nothing here invents data.
    """
    from omai import map_data
    from omai.thermal_transport.domain import THERMAL_TRANSPORT
    return map_data.record_instance(
        domains=(THERMAL_TRANSPORT,), variable=variable, material=material,
        value=value, units=units, source_kind=source_kind, source_ref=source_ref,
        conditions=conditions, uncertainty=uncertainty, detail=detail,
        instances_dir=instances_dir)


def build_codes() -> dict:
    """Per-code adapter coverage: {code: {variable: {"api": ..., "unit": ...}}}.

    Walks the representation adapters and reports, for each code, which operator
    variables it maps and the code's native API name + emitted unit for each. This
    is the mapping work each code did onto the shared layer.
    """
    from omai import map_data
    from omai.thermal_transport.domain import THERMAL_TRANSPORT
    return map_data.build_codes((THERMAL_TRANSPORT,))


def write_codes(path: Path | None = None) -> Path:
    path = path or (_DOCS / "data" / "codes.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_codes()))
    return path


if __name__ == "__main__":
    print("omai.thermal_transport.site_data writes thermal-only data and is deprecated; "
          "use `python -m omai.map_data` for the unified map.")
    from omai import map_data
    print("wrote", map_data.write_graph())
    print("wrote", map_data.write_instances())
    print("wrote", map_data.write_codes())
