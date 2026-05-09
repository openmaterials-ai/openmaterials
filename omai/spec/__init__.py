"""omai.spec — symbolic adapter conformance for the substrate.

Substrate-level declarations of what each adapter (kaldo, phono3py, ...)
computes: which units it emits, which conventions it uses, which Brillouin-zone
summation strategy it follows. The substrate uses these to predict cross-adapter
conversion factors and surface mismatches at spec-load time, before any run.

See docs/symbolic_substrate.tex (Principles 2, 6, 7 and "Observable extraction
and comparison protocols") for the architectural motivation.
"""

from .core import (
    AdapterSpec,
    Operation,
    cross_adapter_convention_match,
    cross_adapter_total_factor,
    cross_adapter_unit_factor,
    output_convention_factor,
)
from .operations import COMPUTE_HEAT_CAPACITY, COMPUTE_SCATTERING_RATES
from .units import conversion_factor

__all__ = [
    "AdapterSpec",
    "COMPUTE_HEAT_CAPACITY",
    "COMPUTE_SCATTERING_RATES",
    "Operation",
    "conversion_factor",
    "cross_adapter_convention_match",
    "cross_adapter_total_factor",
    "cross_adapter_unit_factor",
    "output_convention_factor",
]
