# Per-skill encoding procedure

This document is the Plan 2 template. For every record in
`omai/materials/skills_catalog.json`, follow these seven steps to produce the
four artifacts that connect it to the operator/representation/instance layers.
The worked example is `mat-diffusion-analysis`: nodes in
`omai/materials/operator/nodes.py` (`DIFFUSIVITY_STATE`, `ACTIVATION_ENERGY`),
edges in `omai/materials/operator/edges.py` (`contract_diffusivity`,
`fit_arrhenius`), and the representation spec in
`omai/materials/representation/mat_diffusion_analysis.py`.

To read example values from catalog records you must have the AtomisticSkills
repository cloned locally (it is gitignored: never commit it). The path is
referenced by the `ref` field inside each `example_instances` entry.


## Step 1: Produced-quantity nodes

For each entry in the record's `produces` list, determine whether an equivalent
node already exists. Two nodes are equivalent when they share the same physical
dimension and the same index set (and the same gauge: `observable` vs
`hidden`).

Check `omai/thermal_transport/operator/nodes.py` first, then
`omai/materials/operator/nodes.py`.

If an equivalent node already exists, reuse it by importing it from the file
where it lives.

If no equivalent exists, add an `ObservableSpace` (gauge `observable`) or a
`Space` subclass (gauge `hidden`) in `omai/materials/operator/nodes.py`, and
add it to the module-level `NODES` tuple. Each node takes a `fields` tuple of
one or more `Field(symbol, dimension, indices=())` items. If the physical
dimension of the new field is not yet in `omai/operator/dimensions.py`, add a
new `Dimension` constant there and include it in the `DIMENSIONS` dict.

Example: `mat-diffusion-analysis` produces `diffusivity` (dimension
`DIFFUSIVITY = Dimension("diffusivity")`, no indices) and `activation_energy`
(dimension `ENERGY`, already present). Both were new nodes, so
`DIFFUSIVITY_STATE` and `ACTIVATION_ENERGY` were added to
`omai/materials/operator/nodes.py`, and `DIFFUSIVITY` was added to
`omai/operator/dimensions.py` with an entry in `DIMENSIONS`.

The two catalog entries `mean_square_displacement` and
`room_temperature_conductivity` were intentionally not promoted to new
nodes at this stage; they remain catalog-only until a future skill explicitly
needs them in the operator graph.


## Step 2: Consumed-quantity inputs

For each entry in the record's `consumes` list, resolve it to an existing node.

Check `omai/materials/operator/shared_primitives.py` first. That module
re-exports leaf nodes from `omai/thermal_transport/operator/nodes.py`
(`TEMPERATURE_STATE` as `TEMPERATURE`, `MEAN_SQUARED_DISPLACEMENT`,
`TRAJECTORY`, `POTENTIAL`) and also defines `STRUCTURE` (the opaque crystal
structure leaf used by most mat-* skills). Import the matching primitive from
`shared_primitives` in the edges file for the new skill.

If a consumed quantity is genuinely new and will be shared by multiple future
skills, add a new `ObservableSpace` to `shared_primitives.py` and append it to
`SHARED_PRIMITIVES`. If it is unique to this skill and has already been added
as a produced node in step 1, reference that node directly.

Example: `mat-diffusion-analysis` consumes `md_trajectory` (mapped to
`MEAN_SQUARED_DISPLACEMENT`, which is imported from `shared_primitives`) and
`temperature` (mapped to `TEMPERATURE`, also from `shared_primitives`).


## Step 3: Operator edges

Add one `Operator` instance per operation in
`omai/materials/operator/edges.py` (importing from
`omai.operator.operator`). Append every new operator to the module-level
`EDGES` tuple.

Attach a `sympy.Eq` as the `formula` when `operation.closed_form` in the
catalog record is a concrete algebraic expression. For procedural operations
(regression fits, ML inference, iterative solvers) also attach a sympy `Eq`
showing the governing relation, but set
`is_executable_in_sympy_override=False` to indicate that sympy cannot evaluate
it directly.

Example: `contract_diffusivity` carries a closed-form sympy `Eq` for the
Einstein relation `D = slope(MSD(t)) / (2 d)`. `fit_arrhenius` carries the
Arrhenius equation as a sympy `Eq` but sets
`is_executable_in_sympy_override=False` because the activation energy is
extracted by a weighted regression over multiple temperature points, not by
algebraic inversion of a single equation.

Register every symbol the new formulas reference in
`omai/materials/operator/vocabulary.py`: the per-node sympy base names via
`register_space_symbols` (keyed by node name) and any bare fit constants
(like `d` or `D_0`) via `register_formula_constants`. `validate_dag` flags
unregistered symbols as "not derivable from inputs", and
`tests/test_unified_validation.py` enforces a clean unified map, so a
missing registration fails the suite.


## Step 4: Representation spec

Create `omai/materials/representation/<module_name>.py` where `<module_name>`
is the catalog skill name with hyphens replaced by underscores (e.g.
`mat_diffusion_analysis`). The file must define one
`SpaceRepresentationSpec` per produced node that has a counterpart in the
operator graph (step 1 nodes only; skip catalog-only quantities).

Each spec takes:
- `space`: the node object from step 1.
- `representation_name`: the catalog skill name with hyphens, exactly as it
  appears in the catalog (e.g. `"mat-diffusion-analysis"`).
- `observable_units`: a dict mapping field symbol to a display unit string
  (e.g. `{"D": "cm^2/s"}`). These strings are consumed by `build_codes` as
  display labels; they are not registered in `omai/representation/units.py`
  unless a numerical unit-conversion test actually requires a registered `Unit`
  object for that dimension.
- `code_api`: a dict mapping field symbol to the path of the script or entry
  point that computes it (e.g. `{"D": "scripts/analyze_diffusion.py"}`).
- `notes`: a short free-text description of the computational method.

Do not register new entries in `omai/representation/units.py` for display-only
units. The `units.py` registry is for the executor and comparison layers, which
need `conversion_factor` between registered units. Adding `cm^2/s` or `eV` to
the registry is only necessary when a test exercises `conversion_factor` or
`dimension_si_scale` for those units.

Example: `mat_diffusion_analysis.py` defines `DIFFUSION_DIFFUSIVITY` (for
`DIFFUSIVITY_STATE`) and `DIFFUSION_ACTIVATION` (for `ACTIVATION_ENERGY`),
both with `representation_name="mat-diffusion-analysis"`. No new entries were
added to `omai/representation/units.py`.


## Step 5: Instance records

For each value in the catalog record's `example_instances` list, call
`omai.map_data.record_instance` with `domains=map_data.DOMAINS`. Pass only
real numbers from the catalog: never invent or interpolate values. If the
record has no numeric `example_instances`, skip this step.

The `variable` argument must match the `name` of a node in the operator graph
(the `id` field as returned by `build_graph_dict`). The `source_ref` string
becomes part of the output filename; keep it short and descriptive.

Call `record_instance` from a script or a one-off Python session; the call
writes a JSON file under `docs/data/instances/`.

Example: the LGPS activation energy (0.152 eV) from the catalog was written as
`docs/data/instances/lgps-activationenergy-atomisticskills-mat-diffusion-analysis-lgps.json`
with `variable="ActivationEnergy"`, `source_kind="simulation"`, and
`conditions={"T_range": "600-1000K", "potential": "MatPES-r2SCAN"}`.
The room-temperature conductivity (91.44 mS/cm) was not recorded because
`RoomTemperatureConductivity` is a catalog-only quantity with no operator node.


## Step 6: SYMBOLS entry

Add the LaTeX symbol for each new operator-graph node to the `SYMBOLS` dict in
`omai/materials/domain.py`. The key is the node's `name` string; the value is
the LaTeX symbol used in graph visualizations and the site deck.

Example: after adding `DIFFUSIVITY_STATE` and `ACTIVATION_ENERGY`, the dict
received `"Diffusivity": r"D"` and `"ActivationEnergy": r"E_a"`. Add a node's
symbol only once the node actually enters the graph (i.e. an edge in `EDGES`
produces or consumes it); `STRUCTURE` is defined in `shared_primitives` but
stays out of `SYMBOLS` until the first skill wires an edge to it.


## Step 7: Regenerate and test

After completing steps 1 through 6, regenerate the site data files and run the
test suite:

```
PYTHONPATH=. python -m omai.map_data
python -m pytest tests/test_materials_data.py
```

`python -m omai.map_data` rewrites `docs/data/graph.json`,
`docs/data/instances.json`, and `docs/data/codes.json`. Commit the updated
HTML alongside any content changes (see the `feedback_regenerate_dag_html.md`
memory note for the visualize script).

The test suite checks that all domain imports succeed, that the new nodes and
edges appear in the unified graph, that the representation spec is discoverable
via `build_codes`, and that `record_instance` validates the variable name
against the live node set.
