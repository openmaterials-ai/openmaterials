# The format object is now a lineage. This shim keeps old imports and the old
# recipe vocabulary working during the MaterialsCodeGraph transition and will
# be removed.
from omai.lineages import *
from omai.lineages import LineageError, lineage_id

recipe_id = lineage_id
SimulationError = LineageError
