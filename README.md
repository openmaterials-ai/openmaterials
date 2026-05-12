# openmaterials-ai

A operator substrate for computational materials science workflows. Workflows are
directed acyclic graphs of typed *abstract physics states* (witnesses) connected by
*operator operations*, with concrete numerical results expressed as *materializations*
in a chosen discretization scheme.

See `docs/symbolic_substrate.pdf` for the architectural design document.

## Repository layout

```
openmaterials-ai/
  docs/        # design doc (LaTeX/PDF)
  omai/        # Python package
    abstract/  # types for abstract states and operations
    numeric/   # types for materializations and discretization schemes
    adapters/  # per-code adapters (kaldo, phonopy, phono3py)
  tests/       # pytest suite
```

## Status

Phase 1 in progress. Stubbed upstream of `Potential`; vocabulary of operations grows
incrementally as kaldo and phonopy materializations are mapped.

