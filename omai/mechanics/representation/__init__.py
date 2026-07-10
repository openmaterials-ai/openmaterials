"""Per-code adapter specs for the mechanics domain.

Each submodule holds the SpaceRepresentationSpec / OperatorRepresentationSpec
instances for one code or skill, constructed against the shared operator DAG in
`omai.mechanics.operator` so cross-code agreement is checked at the operator
level (per Principle 7):

  * `lammps`: the examples/ELASTIC finite-strain workflow (ElasticConstants,
    the finite-strain operator spec) and compute pressure (Pressure).
  * `mat_elasticity`: the mat-elasticity AtomisticSkills skill (the elastic
    tensor, the two Voigt-Reuss-Hill moduli, Young's modulus in GPa, and the
    Poisson ratio).
  * `pymatgen`: pymatgen 2025.6.14's ElasticTensor family (the tensor and
    VRH moduli in native eV/A^3, y_mod in SI Pa, homogeneous_poisson), with
    the 160x and 1e9 unit traps recorded.
  * `mat_equation_of_state`: the mat-equation-of-state skill (matcalc EOSCalc
    Birch-Murnaghan bulk modulus, GPa), the Pattern C alternative producer of
    BulkModulus (a second estimator distinct from the elastic-tensor VRH
    route); anchored in the matcalc/ASE scan. matcalc is the driver, recorded
    in notes (no separate matcalc rail, the atomate2 ruling).
"""
