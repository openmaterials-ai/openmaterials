"""Operator-representation boundary behavioural tests (full operator layer).

This file exercises the *contract* at the operator/representation boundary
across every ``SpaceRepresentationSpec`` discoverable in the four adapter modules
``omai.thermal_transport.representation.{kaldo,phono3py,phonopy,shengbte}``.

Four families of checks (each parametrized over discovered specs):

  3B.1: Round-trip identity --
      ``to_representation(to_operator(m), spec).data == m.data`` for every
      spec that declares ``observable_units`` for at least one field. Specs
      that don't declare units (scaffolding states such as BareDM, TEMPERATURE,
      FC2/FC3) are SKIPPED — they intentionally cannot be canonicalised.

  3B.2: ``compare_operators`` over every cross-adapter pair --
      For every state with >=2 adapter specs, call
      ``compare_operators(spec_a, spec_b)`` for each unordered pair and
      assert the result has the expected shape.

  3B.3: ``compare_representations`` on identical / factor-related /
      adversarial pairs -- for every state with >=2 specs that both
      declare units, verify identical / factor-related / adversarial
      numerical comparisons return the expected status.

  3B.4: Helpful KeyError path -- for a spec that omits ``observable_units``,
      verify ``to_operator`` raises ``KeyError`` whose message names both
      the spec's ``representation_name`` and the field name.

Discovery mirrors ``omai.map_data.build_codes``: walk
the adapter sub-package, import each module, and collect every
``SpaceRepresentationSpec`` instance via attribute introspection.
"""

from __future__ import annotations

import importlib
import itertools
import pkgutil
from dataclasses import dataclass

import numpy as np
import pytest

import omai.thermal_transport.representation as _representation_pkg
from omai.operator.space import HiddenSpace, ObservableSpace
from omai.representation import Representation, compare
from omai.representation.adapter import (
    SpaceRepresentationSpec,
    operator_to_representation,
    representation_to_operator,
)
from omai.representation.compare import (
    OperatorComparisonResult,
    compare_operators,
    to_operator,
    to_representation,
)
from omai.representation.units import UNITS


# A dimension has a "registered canonical unit" iff at least one Unit in the
# global registry is tagged with that dimension. The framework's
# canonicalisation pipeline cannot fire for fields on dimensions without one
# (e.g. ENERGY, LENGTH, OPAQUE), so those specs are out of scope for the
# round-trip and helpful-KeyError tests regardless of whether they declare
# observable_units.
def _dimension_has_registered_unit(dimension) -> bool:
    return any(u.dimension == dimension for u in UNITS.values())


# ---------------------------------------------------------------------------
# Spec discovery (mirrors omai.map_data.build_codes)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DiscoveredSpec:
    """A SpaceRepresentationSpec located via discovery, with provenance for ids."""

    module: str  # e.g. "kaldo"
    attr: str  # module-level attribute name, e.g. "KALDO_LINEWIDTH"
    spec: SpaceRepresentationSpec

    @property
    def state_name(self) -> str:
        return self.spec.space.name

    @property
    def representation_name(self) -> str:
        return self.spec.representation_name


def _discover_specs() -> list[_DiscoveredSpec]:
    """All ``SpaceRepresentationSpec`` instances across the four adapter modules."""
    found: list[_DiscoveredSpec] = []
    for info in sorted(pkgutil.iter_modules(_representation_pkg.__path__)):
        if info.name.startswith("_"):
            continue
        mod = importlib.import_module(
            f"omai.thermal_transport.representation.{info.name}"
        )
        for attr in sorted(dir(mod)):
            if attr.startswith("_"):
                continue
            obj = getattr(mod, attr)
            if isinstance(obj, SpaceRepresentationSpec):
                found.append(_DiscoveredSpec(module=info.name, attr=attr, spec=obj))
    return found


_ALL_SPECS: tuple[_DiscoveredSpec, ...] = tuple(_discover_specs())


def _specs_by_state() -> dict[str, list[_DiscoveredSpec]]:
    grouped: dict[str, list[_DiscoveredSpec]] = {}
    for ds in _ALL_SPECS:
        grouped.setdefault(ds.state_name, []).append(ds)
    return grouped


_SPECS_BY_STATE: dict[str, list[_DiscoveredSpec]] = _specs_by_state()


# ---------------------------------------------------------------------------
# Parametrize helpers
# ---------------------------------------------------------------------------


def _round_trip_params() -> list[tuple[_DiscoveredSpec, str]]:
    """One (spec, field) entry per declared (observable_units) field.

    Specs that declare *no* observable_units appear once with field=None so
    they emit a pytest.skip explaining why.
    """
    out: list[tuple[_DiscoveredSpec, str | None]] = []
    for ds in _ALL_SPECS:
        if not ds.spec.observable_units:
            out.append((ds, None))
            continue
        for field_name in ds.spec.observable_units.keys():
            out.append((ds, field_name))
    return out


def _round_trip_id(value: tuple[_DiscoveredSpec, str | None]) -> str:
    ds, field = value
    if field is None:
        return f"{ds.attr}[no-units]"
    return f"{ds.attr}[{field}]"


def _cross_adapter_pairs() -> list[tuple[str, _DiscoveredSpec, _DiscoveredSpec]]:
    """Every unordered cross-adapter pair, grouped by state."""
    pairs: list[tuple[str, _DiscoveredSpec, _DiscoveredSpec]] = []
    for state_name, specs in _SPECS_BY_STATE.items():
        if len(specs) < 2:
            continue
        for a, b in itertools.combinations(specs, 2):
            pairs.append((state_name, a, b))
    return pairs


def _cross_adapter_pair_id(
    value: tuple[str, _DiscoveredSpec, _DiscoveredSpec]
) -> str:
    state_name, a, b = value
    return f"{state_name}::{a.representation_name}-vs-{b.representation_name}"


def _cross_adapter_pairs_with_units() -> list[
    tuple[str, _DiscoveredSpec, _DiscoveredSpec, str]
]:
    """Cross-adapter pairs where *both* specs declare units for a shared field
    AND the field's dimension has a registered canonical unit AND both
    declared units are themselves in the UNITS registry.

    Pairs that fall outside this filter cannot be canonicalised (the
    framework raises ``KeyError`` from the unit lookup), so they're not
    candidates for ``compare_representations`` — they would not exercise
    the numerical comparison the test is designed to verify.
    """
    out: list[tuple[str, _DiscoveredSpec, _DiscoveredSpec, str]] = []
    for state_name, a, b in _cross_adapter_pairs():
        common_fields = (
            set(a.spec.observable_units) & set(b.spec.observable_units)
        )
        for field_name in sorted(common_fields):
            ua = a.spec.observable_units[field_name]
            ub = b.spec.observable_units[field_name]
            if ua not in UNITS or ub not in UNITS:
                continue
            field = a.spec.space.field(field_name)
            if not _dimension_has_registered_unit(field.dimension):
                continue
            out.append((state_name, a, b, field_name))
    return out


def _pair_with_field_id(
    value: tuple[str, _DiscoveredSpec, _DiscoveredSpec, str]
) -> str:
    state_name, a, b, field = value
    return f"{state_name}::{a.representation_name}-vs-{b.representation_name}::{field}"


# A small synthetic array. Shape (3,) is broadly compatible with the float
# scaling that to_operator / to_representation does — it never inspects the
# state's index signature numerically, only the unit + convention factors.
def _synthetic_data() -> np.ndarray:
    return np.array([1.0, 2.0, 3.0])


# ---------------------------------------------------------------------------
# 3B.1: Round-trip identity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case", _round_trip_params(), ids=_round_trip_id
)
def test_round_trip_through_operator_form_is_identity(
    case: tuple[_DiscoveredSpec, str | None],
) -> None:
    """to_representation(to_operator(m), spec).data ≈ m.data (round-trip).

    Specs without observable_units cannot be canonicalised; we skip those
    rather than treat them as failures — the framework explicitly supports
    scaffolding specs that don't claim a unit.

    A handful of states have ``Dimension``s with no registered unit in the
    global ``UNITS`` registry (e.g. ENERGY, LENGTH). Adapter specs *can*
    declare units on those fields, but the canonical-unit lookup fails — so
    the round trip itself is not exercisable until those dimensions get unit
    entries. Skip those too, with a reason that points at the missing entry.
    """
    ds, field_name = case
    if field_name is None:
        pytest.skip(
            f"{ds.attr} declares no observable_units; canonicalisation is "
            f"intentionally unsupported for scaffolding specs."
        )
    declared_unit = ds.spec.observable_units[field_name]
    if declared_unit not in UNITS:
        pytest.skip(
            f"{ds.attr} declares unit {declared_unit!r} which is not in the "
            f"UNITS registry; cannot exercise round-trip."
        )
    field = ds.spec.space.field(field_name)
    if not _dimension_has_registered_unit(field.dimension):
        pytest.skip(
            f"dimension {field.dimension.name!r} on state "
            f"{ds.spec.space.name!r} has no registered canonical unit; "
            f"round-trip not exercisable."
        )
    data = _synthetic_data()
    m = Representation(
        space_adapter_spec=ds.spec,
        observable_name=field_name,
        data=data,
    )
    m_op = to_operator(m)
    assert m_op.is_operator is True
    m_round = to_representation(m_op, ds.spec)
    assert m_round.is_operator is False
    np.testing.assert_allclose(
        m_round.data, data, rtol=1e-12, atol=0.0,
        err_msg=(
            f"round-trip changed data for spec {ds.attr} field {field_name!r}: "
            f"{m_round.data} != {data}"
        ),
    )


# ---------------------------------------------------------------------------
# 3B.2: compare_operators over every cross-adapter pair
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case", _cross_adapter_pairs(), ids=_cross_adapter_pair_id
)
def test_compare_operators_returns_structured_result(
    case: tuple[str, _DiscoveredSpec, _DiscoveredSpec],
) -> None:
    """compare_operators(spec_a, spec_b) returns an OperatorComparisonResult
    with a consistent (same_operator, mismatches) shape.

    Either ``same_operator=True`` with an empty mismatch tuple, or
    ``same_operator=False`` with at least one stringy mismatch entry.
    """
    _, a, b = case
    result = compare_operators(a.spec, b.spec)
    assert isinstance(result, OperatorComparisonResult)
    assert isinstance(result.same_operator, bool)
    assert isinstance(result.mismatches, tuple)
    if result.same_operator:
        assert result.mismatches == ()
    else:
        assert len(result.mismatches) >= 1
        for entry in result.mismatches:
            assert isinstance(entry, str)
            assert entry  # non-empty
    # The summary helper should always produce a non-empty string.
    assert isinstance(result.summary(), str)
    assert result.summary()


# ---------------------------------------------------------------------------
# 3B.3: compare_representations on identical / factor-related / adversarial
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case",
    _cross_adapter_pairs_with_units(),
    ids=_pair_with_field_id,
)
def test_compare_representations_identical_pair(
    case: tuple[str, _DiscoveredSpec, _DiscoveredSpec, str],
) -> None:
    """Identical data wrapped twice with the same spec compares cleanly.

    ObservableSpace per-element → EXPECTED_AGREE.
    HiddenSpace per-element → NOT_COMPARABLE (matrix-element gauge dependence).
    """
    _, a, _b, field_name = case
    data = np.array([1.0, 2.0, 3.0])
    m_a = Representation(
        space_adapter_spec=a.spec, observable_name=field_name, data=data
    )
    m_a2 = Representation(
        space_adapter_spec=a.spec, observable_name=field_name, data=data
    )
    r = compare(m_a, m_a2, rtol=1e-9)
    if isinstance(a.spec.space, HiddenSpace):
        assert r.not_comparable is True
        assert r.status == "NOT_COMPARABLE"
    else:
        assert isinstance(a.spec.space, ObservableSpace)
        assert r.agreed is True
        assert r.status == "EXPECTED_AGREE"
        assert r.max_relative_residual == 0.0


@pytest.mark.parametrize(
    "case",
    _cross_adapter_pairs_with_units(),
    ids=_pair_with_field_id,
)
def test_compare_representations_factor_related_pair(
    case: tuple[str, _DiscoveredSpec, _DiscoveredSpec, str],
) -> None:
    """data_b = data_a × inter_representation_factor(a, b, field) compares as
    matching: ObservableSpace → EXPECTED_AGREE, HiddenSpace → NOT_COMPARABLE.

    Both yield ``agreed=True`` (the data are numerically equal once
    canonicalised); the operator-layer status flag differs because HiddenStates
    cannot make a per-element verdict.
    """
    _, a, b, field_name = case
    factor = (
        operator_to_representation(b.spec, field_name)
        * representation_to_operator(a.spec, field_name)
    )
    data_a = np.array([1.0, 2.0, 3.0])
    data_b = data_a * factor
    m_a = Representation(
        space_adapter_spec=a.spec, observable_name=field_name, data=data_a
    )
    m_b = Representation(
        space_adapter_spec=b.spec, observable_name=field_name, data=data_b
    )
    r = compare(m_a, m_b, rtol=1e-9)
    assert r.agreed is True
    if isinstance(a.spec.space, HiddenSpace):
        assert r.status == "NOT_COMPARABLE"
    else:
        assert r.status == "EXPECTED_AGREE"


@pytest.mark.parametrize(
    "case",
    _cross_adapter_pairs_with_units(),
    ids=_pair_with_field_id,
)
def test_compare_representations_adversarial_pair(
    case: tuple[str, _DiscoveredSpec, _DiscoveredSpec, str],
) -> None:
    """data_b = data_a × 2 × factor → numerical disagreement.

    For Observables we expect ``UNEXPECTED_DISAGREE`` (the operator layer
    predicts agreement, the data disagrees). For HiddenStates the per-element
    verdict is suppressed (NOT_COMPARABLE); residuals are still computed but
    no pass/fail is rendered.
    """
    _, a, b, field_name = case
    factor = (
        operator_to_representation(b.spec, field_name)
        * representation_to_operator(a.spec, field_name)
    )
    data_a = np.array([1.0, 2.0, 3.0])
    data_b = data_a * 2.0 * factor
    m_a = Representation(
        space_adapter_spec=a.spec, observable_name=field_name, data=data_a
    )
    m_b = Representation(
        space_adapter_spec=b.spec, observable_name=field_name, data=data_b
    )
    r = compare(m_a, m_b, rtol=1e-9)
    if isinstance(a.spec.space, HiddenSpace):
        assert r.status == "NOT_COMPARABLE"
        # Even though we report NOT_COMPARABLE, the residual is still nonzero.
        assert r.max_relative_residual > 0
    else:
        assert r.agreed is False
        assert r.status == "UNEXPECTED_DISAGREE"


# ---------------------------------------------------------------------------
# 3B.4: Helpful-KeyError path for specs that omit observable_units
# ---------------------------------------------------------------------------


def _unitless_specs_with_canonical_dim() -> list[_DiscoveredSpec]:
    """Specs that omit observable_units AND whose first field's dimension
    has a registered canonical unit.

    Restricting to dimensions with a canonical unit is what isolates the
    *helpful* (adapter-naming) KeyError code path in ``_spec_to_canonical_factor``
    from the framework-level "no unit registered for dimension" KeyError that
    fires for ENERGY / OPAQUE / TEMPERATURE / LENGTH fields. Both are valid
    KeyError paths, but only the former is the one this contract test is
    documenting.
    """
    out: list[_DiscoveredSpec] = []
    for ds in _ALL_SPECS:
        if ds.spec.observable_units:
            continue
        if not ds.spec.space.fields:
            continue
        first_field = ds.spec.space.fields[0]
        if not _dimension_has_registered_unit(first_field.dimension):
            continue
        out.append(ds)
    return out


@pytest.mark.parametrize(
    "ds", _unitless_specs_with_canonical_dim(), ids=lambda ds: ds.attr
)
def test_to_operator_raises_helpful_keyerror_for_unitless_specs(
    ds: _DiscoveredSpec,
) -> None:
    """A unitless spec cannot be canonicalised; ``to_operator`` must raise
    ``KeyError`` whose message names both the adapter and the field, so a
    user reading the traceback immediately knows what to add.
    """
    fields = ds.spec.space.fields
    assert fields, f"spec {ds.attr}: state has no fields, cannot test"
    field_name = fields[0].name
    m = Representation(
        space_adapter_spec=ds.spec,
        observable_name=field_name,
        data=np.array([1.0]),
    )
    with pytest.raises(KeyError) as excinfo:
        to_operator(m)
    msg = str(excinfo.value)
    assert ds.spec.representation_name in msg, (
        f"KeyError for {ds.attr} did not name the adapter "
        f"{ds.spec.representation_name!r}: {msg}"
    )
    assert field_name in msg, (
        f"KeyError for {ds.attr} did not name the field {field_name!r}: {msg}"
    )
