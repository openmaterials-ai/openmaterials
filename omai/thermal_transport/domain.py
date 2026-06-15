"""The thermal-transport Domain descriptor."""
from __future__ import annotations

from omai.map_data import Domain
from omai.thermal_transport import representation as tt_rep
from omai.thermal_transport.operator import EDGES, NODES
from omai.thermal_transport.operator import edges as _edges
from omai.thermal_transport.site_data import SYMBOLS

THERMAL_TRANSPORT = Domain(
    name="thermal_transport",
    nodes=NODES,
    edges=EDGES,
    symbols=SYMBOLS,
    param_promotions=(
        ("CellVolume", r"V_{\mathrm{cell}}", _edges._V_cell),
        ("AtomicMass", r"M", _edges._M),
        ("AtomCount", r"N", _edges._N_atoms),
    ),
    representation_package=tt_rep,
)
