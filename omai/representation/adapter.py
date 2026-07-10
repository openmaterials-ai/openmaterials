"""Representation-layer adapter specs.

A `SpaceRepresentationSpec` declares one code's claim about a node (operator
`Space`):
  * the unit each observable is in (within that code's natural emission)
  * the normalization each observable is in (the definitional multiplicative
    choice — `Γ = 2 Im Σ` vs `Γ = Im Σ`, `eV/Å³` vs `eV/(Å²·nm)` — captured
    by name in the `normalizations.NORMALIZATIONS` registry)

An `OperatorRepresentationSpec` declares one code's claim about an edge
(operator `Operator`):
  * the unit each parameter is in (within that code's API surface)
  * the scheme overrides (algorithmic choices that change *what* is computed
    relative to the operator-canonical scheme)
  * the discretization choices the code makes (e.g., BZ summation strategy);
    these don't change *what* is computed, only *how*, so they live here
    rather than on the operator `Operator`.

Cross-adapter agreement is checked at the `Space` level (the observable layer,
per Principle 7). `Operator`-level adapter specs are diagnostic: they
describe how each code performs the operation; mismatches don't yield a
numerical conversion factor but flag where the codes do something
algorithmically different.

Unit × normalization composition
--------------------------------
The two primitive cross-form mappings are `representation_to_operator` and
its inverse `operator_to_representation`. Both compose a unit's
`to_operator` multiplier with the normalization's `to_operator` multiplier:

    operator_value = adapter_value · unit.to_operator · normalization.to_operator

Cross-adapter conversions (A → B for the same `Space`) are never primitive;
they are always the composition

    operator_to_representation(b, obs) · representation_to_operator(a, obs)

The operator layer is the unique hub of a star topology — adding adapter C
means declaring C ↔ operator only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from omai.operator.operator import Operator
from omai.operator.space import Space
from omai.representation.normalizations import NORMALIZATIONS
from omai.representation.units import UNITS


@dataclass(frozen=True)
class CanonicalAxis:
    """The canonical function-axis a spectrum-capable node's evidence is stored on.

    A spectrum record (docs/data/spectra/<slug>.json) is a function value(axis):
    an array of ordinates against a strictly monotonic axis. This declaration,
    carried on the node's representation spec, pins the canonical axis so the
    validation bridge (omai.map_data.record_spectrum) can check a submitted
    record's axis and value units against a fixed convention rather than against
    ad-hoc per-record choices.

      name              the axis label (e.g. "omega", "d_hkl").
      unit              the registered unit name the axis is stored in (its
                        Unit.dimension is the axis's dimension).
      value_unit        the registered unit the ordinates are in, or None when
                        the value normalization is open (e.g. a phonon DOS
                        density: states per THz per cell vs per formula unit
                        rides in the record's conditions, so no unit is pinned).
      required_conditions
                        conditions a served/derived axis needs but the canonical
                        axis does not (e.g. XRD radiation wavelength: the stored
                        d_hkl is wavelength-free, but a served 2theta axis
                        requires it). Free-form; recorded for discipline, not
                        enforced numerically this slice.
    """

    name: str
    unit: str
    value_unit: str | None = None
    required_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class SpaceRepresentationSpec:
    space: Space
    representation_name: str
    observable_units: dict[str, str] = field(default_factory=dict)
    observable_normalizations: dict[str, str] = field(default_factory=dict)
    # Per-field native API name in the code. Used by tooling (visualization,
    # docs) to surface what a user actually calls to get this space's data
    # in the code. Example: kaldo's Linewidth → {"Gamma": "Phonons.bandwidth"};
    # shengbte's Linewidth → {"Gamma": "BTE.w_anharmonic"}. May be empty for
    # adapters where the API name lives in prose `notes` instead.
    code_api: dict[str, str] = field(default_factory=dict)
    # Canonical function-axis declaration for a spectrum-capable node (the
    # spectrum layer). None for scalar nodes. A CanonicalAxis names the stored
    # axis (a registered unit + its dimension), the registered value unit the
    # spectrum's ordinates are in (or None when the value normalization is open
    # and rides in the record's conditions, e.g. a phonon DOS density), and any
    # conditions a served axis requires (e.g. XRD radiation wavelength). Read by
    # omai.map_data.record_spectrum to validate function-valued evidence; no new
    # operator node is minted (per the characterization verdicts).
    canonical_axis: "CanonicalAxis | None" = None
    notes: str = ""

    def declared_unit(self, observable_name: str) -> str:
        unit = self.observable_units.get(observable_name)
        if unit is not None:
            return unit
        # Canonical unit isn't declared at the operator level (the operator
        # layer is unit-free); the representation layer either declares a
        # unit or refuses to compare. Most scaffolding specs (Temperature,
        # FC2/FC3, DM, MFD, ...) intentionally omit units — they exist to
        # mark coverage on the DAG, not to support numerical comparison.
        raise KeyError(
            f"adapter {self.representation_name!r} has no unit declared for "
            f"observable {observable_name!r} of space {self.space.name!r} "
            f"— cannot canonicalise. Add an observable_units entry "
            f"({{'{observable_name}': '<unit_name>'}}) to its SpaceRepresentationSpec, "
            f"or operate on the canonical (operator-form) Representation."
        )


@dataclass(frozen=True)
class OperatorRepresentationSpec:
    operator: Operator
    representation_name: str
    parameter_units: dict[str, str] = field(default_factory=dict)
    scheme_overrides: dict[str, str] = field(default_factory=dict)
    discretization_choices: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def declared_parameter_unit(self, parameter_name: str) -> str:
        unit = self.parameter_units.get(parameter_name)
        if unit is None:
            raise KeyError(
                f"adapter {self.representation_name!r} did not declare a unit for "
                f"parameter {parameter_name!r} of operator {self.operator.name!r}"
            )
        return unit

    def declared_scheme(self, scheme_name: str) -> str:
        if scheme_name in self.scheme_overrides:
            return self.scheme_overrides[scheme_name]
        if scheme_name in self.operator.schemes:
            return self.operator.schemes[scheme_name]
        raise KeyError(
            f"operator {self.operator.name!r} declares no scheme {scheme_name!r}"
        )


# ---------------------------------------------------------------------------
# Cross-adapter helpers (space level)
# ---------------------------------------------------------------------------


def representation_to_operator(
    spec: SpaceRepresentationSpec, observable_name: str
) -> float:
    """Multiplier from this adapter's emitted value to operator-canonical form.

    The operator layer is unit-free at the *dimension* level but each
    `Unit` carries a `to_operator` factor that names the canonical
    numerical form for its dimension (linear_THz for FREQUENCY, J/K for
    ENERGY_PER_TEMPERATURE, W/(m·K) for THERMAL_CONDUCTIVITY, …).
    Independently each `Normalization` carries a `to_operator` factor that
    captures the adapter's definitional choice (`Γ = 2 Im Σ` vs canonical
    `Γ = Im Σ`; FC3 in `eV/(Å²·nm)` vs canonical `eV/Å³`). The combined
    multiplier is the product:

        operator_value = adapter_value · unit.to_operator · normalization.to_operator

    Together with `operator_to_representation`, this is the only primitive
    cross-form mapping. Cross-adapter A→B factors are *defined* as their
    composition; there is no direct A→B primitive in the framework.
    Adapters talk to each other only through the operator hub — a star
    topology, never a complete graph. Adding adapter C means declaring
    C↔operator only.
    """
    unit = UNITS[spec.declared_unit(observable_name)]
    normalization = NORMALIZATIONS[
        spec.observable_normalizations.get(observable_name, "canonical")
    ]
    return unit.to_operator * normalization.to_operator


def operator_to_representation(
    spec: SpaceRepresentationSpec, observable_name: str
) -> float:
    """Multiplier from operator-canonical form to this adapter's emitted value.

    Inverse of `representation_to_operator`:

        adapter_value = operator_value / (unit.to_operator · normalization.to_operator)
    """
    return 1.0 / representation_to_operator(spec, observable_name)


# ---------------------------------------------------------------------------
# Cross-adapter helpers (operator level — diagnostic only)
# ---------------------------------------------------------------------------


def _require_same_operator(
    a: OperatorRepresentationSpec, b: OperatorRepresentationSpec
) -> None:
    if a.operator != b.operator:
        raise ValueError(
            f"adapters wrap different operators: "
            f"{a.operator.name!r} vs {b.operator.name!r}"
        )


def representation_scheme_match(
    a: OperatorRepresentationSpec, b: OperatorRepresentationSpec, scheme_name: str
) -> tuple[bool, str]:
    """Whether two operator adapters agree on a scheme."""
    _require_same_operator(a, b)
    ca = a.declared_scheme(scheme_name)
    cb = b.declared_scheme(scheme_name)
    if ca == cb:
        return True, ""
    return False, (
        f"{a.representation_name} uses {scheme_name}={ca}; "
        f"{b.representation_name} uses {scheme_name}={cb}"
    )


def representation_discretization_match(
    a: OperatorRepresentationSpec, b: OperatorRepresentationSpec, choice_name: str
) -> tuple[bool, str]:
    """Whether two operator adapters agree on a discretization choice
    (e.g., BZ summation strategy)."""
    _require_same_operator(a, b)
    ca = a.discretization_choices.get(choice_name, "<unspecified>")
    cb = b.discretization_choices.get(choice_name, "<unspecified>")
    if ca == cb:
        return True, ""
    return False, (
        f"{a.representation_name} uses {choice_name}={ca}; "
        f"{b.representation_name} uses {choice_name}={cb}"
    )
