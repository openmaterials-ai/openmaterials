"""Per-code adapter specs for the thermal-transport DAG.

Each submodule holds the StateAdapterSpec and OperationAdapterSpec instances
for one code (kaldo, phono3py, ...). All instances are constructed against
the shared abstract DAG in `omai.thermal_transport.symbolic`, so cross-code
agreement is checked at the substrate level (per Principle 7).

Re-exports the per-code spec instances for convenience; the canonical
location is the corresponding submodule (e.g.
`omai.thermal_transport.materialized.kaldo`).
"""

from omai.thermal_transport.materialized.kaldo import (
    KALDO_COMPUTE_HEAT_CAPACITY,
    KALDO_COMPUTE_LINEWIDTH,
    KALDO_FREQUENCY,
    KALDO_GROUP_VELOCITY,
    KALDO_HEAT_CAPACITY,
    KALDO_LINEWIDTH,
    KALDO_THERMAL_CONDUCTIVITY_DIRECT,
    KALDO_THERMAL_CONDUCTIVITY_RTA,
)
from omai.thermal_transport.materialized.phono3py import (
    PHONO3PY_COMPUTE_HEAT_CAPACITY,
    PHONO3PY_COMPUTE_LINEWIDTH,
    PHONO3PY_FREQUENCY,
    PHONO3PY_GROUP_VELOCITY,
    PHONO3PY_HEAT_CAPACITY,
    PHONO3PY_LINEWIDTH,
    PHONO3PY_THERMAL_CONDUCTIVITY_DIRECT,
    PHONO3PY_THERMAL_CONDUCTIVITY_RTA,
)

__all__ = [
    "KALDO_COMPUTE_HEAT_CAPACITY",
    "KALDO_COMPUTE_LINEWIDTH",
    "KALDO_FREQUENCY",
    "KALDO_GROUP_VELOCITY",
    "KALDO_HEAT_CAPACITY",
    "KALDO_LINEWIDTH",
    "KALDO_THERMAL_CONDUCTIVITY_DIRECT",
    "KALDO_THERMAL_CONDUCTIVITY_RTA",
    "PHONO3PY_COMPUTE_HEAT_CAPACITY",
    "PHONO3PY_COMPUTE_LINEWIDTH",
    "PHONO3PY_FREQUENCY",
    "PHONO3PY_GROUP_VELOCITY",
    "PHONO3PY_HEAT_CAPACITY",
    "PHONO3PY_LINEWIDTH",
    "PHONO3PY_THERMAL_CONDUCTIVITY_DIRECT",
    "PHONO3PY_THERMAL_CONDUCTIVITY_RTA",
]
