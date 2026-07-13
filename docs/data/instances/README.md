# Instances

An **instance** is one value of a variable, attached to the symbolic layer. Nothing
is seeded here with invented numbers; the store stays empty until real simulation or
measured values are appended.

To append one, add a JSON file (one record per file) and open a pull request:

```json
{
  "variable": "ThermalConductivity[transport_model=wigner]",
  "material": "Si",
  "conditions": {"T": 300},
  "value": 0.0,
  "units": "W/(m K)",
  "uncertainty": null,
  "source": {"kind": "simulation", "ref": "<code or paper>", "detail": "<method>"}
}
```

- `variable` must be an exact id from `../graph.json`.
- `source.kind` is `simulation` (numerical) or `measurement` (lab).

The build bundles every `*.json` here into `../instances.json`, which the map reads:

```bash
CUDA_VISIBLE_DEVICES="" PYTHONPATH=. python -m omai.map_data
```

## Your data stays yours

Appending an instance grants the map a non-exclusive CC BY 4.0 license to
redistribute the record with attribution, and nothing else: no copyright
assignment, no CLA, no claim on the simulation or experiment behind it. The
raw artifacts (trajectories, force sets, lab records) are never ingested;
the record carries a provenance reference and the artifacts stay wherever,
and however, you publish them. Anyone reusing map data must credit the map
version and, through its provenance, your source. The full statement is
GOVERNANCE.md, "Data ownership and fairness".
