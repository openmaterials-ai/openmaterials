r"""Citation and license credits for every code rail on the openmaterials map.

Giuseppe's rule: every code we represent MUST be cited (a paper / DOI) and MUST
carry its license. A rail that appears on the map without both is a bug, not a
gap: the enforcement test (tests/test_code_credits.py) fails when a discovered
representation_name has no CODE_CREDITS entry, when its citation or license is
empty, or when its license is "UNKNOWN" without an explicit ALLOWED_UNKNOWN
waiver. Future rails cannot land uncredited.

THE SOURCING BAR (how each field below was obtained):

  * License: read from the ACTUAL license text, not memory. Preference order:
    (1) the LICENSE / COPYING file in the vendored clone at the repo root
    (kaldo/, lammps/, q-e/, phonopy/, phono3py/, shengbte/, AtomisticSkills/);
    (2) the package METADATA in an installed distribution or a downloaded wheel
    / sdist (pip show, or the wheels under /tmp/*src unzipped during the scans);
    (3) the project's GitHub LICENSE fetched over the network. Each entry records
    the SPDX-style short name plus a `license_source` note saying WHERE it was
    read. Proprietary codes (ORCA, VASP) carry their real commercial / academic
    terms, not an open license.

  * Citation: the code's own "how to cite" / CITATION.cff / README citation
    section FIRST (kaldo, LAMMPS, phonopy, phono3py, AtomisticSkills were read
    this way); otherwise the canonical method paper every practitioner cites,
    verified against a fetch of the project's citation page. DOIs are recorded
    only when verified; an unverifiable reference keeps doi=None with a note.

  * The mat-* skill rails (mat-elasticity, mat-diffusion-analysis,
    mat-equation-of-state, mat-surface-adsorption) are AtomisticSkills skills:
    they cite the AtomisticSkills paper (arXiv:2605.24002) and carry its MIT
    license (AtomisticSkills/LICENSE). The underlying-code rails they drive
    (mace, matgl, fairchem, ...) cite THAT code's own method paper.

Schema per rail (keyed by representation_name):

    {
      "citation": str,          # one-line human-readable reference
      "doi": str | None,        # verified DOI, else None with a note in citation
      "license": str,           # SPDX-style short name, or a proprietary term
      "license_source": str,    # where the license was read (file / metadata)
      "url": str | None,        # project home / repo
    }
"""

from __future__ import annotations

CODE_CREDITS: dict[str, dict] = {
    # --- thermal transport ---------------------------------------------------
    "kaldo": {
        "citation": "G. Barbalinardo, Z. Chen, N. W. Lundgren, D. Donadio, "
        "Efficient anharmonic lattice dynamics calculations of thermal "
        "transport in crystalline and disordered solids, J. Appl. Phys. 128, "
        "135104 (2020)",
        "doi": "10.1063/5.0020443",
        "license": "BSD-3-Clause",
        "license_source": "kaldo/LICENSE (vendored clone)",
        "url": "https://github.com/nanotheorygroup/kaldo",
    },
    "mescal": {
        "citation": "G. Barbalinardo, D. Donadio, MESCAL: differentiable "
        "mode-matching phonon transport with machine-learned potentials "
        "(manuscript in preparation); validated against I. Duchemin, D. Donadio, "
        "Atomistic calculation of the thermal conductance of large scale "
        "bulk-nanowire junctions, Phys. Rev. B 84, 115423 (2011)",
        # Manuscript in preparation: no DOI yet. The validation reference (the
        # published coherent-transport results MESCAL reproduces) is the
        # Duchemin-Donadio 2011 paper, whose DOI is 10.1103/PhysRevB.84.115423.
        "doi": None,
        "license": "MIT",
        "license_source": "gbarbalinardo/mescal LICENSE (gh api "
        "repos/gbarbalinardo/mescal/license -> spdx_id MIT, verified 2026-07-13)",
        "url": "https://github.com/gbarbalinardo/mescal",
    },
    "shengbte": {
        "citation": "W. Li, J. Carrete, N. A. Katcho, N. Mingo, ShengBTE: A "
        "solver of the Boltzmann transport equation for phonons, Comput. Phys. "
        "Commun. 185, 1747 (2014)",
        "doi": "10.1016/j.cpc.2014.02.015",
        "license": "GPL-3.0",
        "license_source": "shengbte/LICENSE (vendored clone, GPL v3)",
        "url": "https://bitbucket.org/sousaw/shengbte",
    },
    "phonopy": {
        "citation": "A. Togo, L. Chaput, T. Tadano, I. Tanaka, Implementation "
        "strategies in phonopy and phono3py, J. Phys. Condens. Matter 35, "
        "353001 (2023)",
        "doi": "10.1088/1361-648X/acd831",
        "license": "BSD-3-Clause",
        "license_source": "phonopy/LICENSE (vendored clone); "
        "citation from phonopy/doc/citation.md",
        "url": "https://phonopy.github.io/phonopy/",
    },
    "phono3py": {
        "citation": "A. Togo, L. Chaput, I. Tanaka, Distributions of phonon "
        "lifetimes in Brillouin zones, Phys. Rev. B 91, 094306 (2015)",
        "doi": "10.1103/PhysRevB.91.094306",
        "license": "BSD-3-Clause",
        "license_source": "phono3py/LICENSE (vendored clone); "
        "citation from phono3py/doc/citation.md",
        "url": "https://phonopy.github.io/phono3py/",
    },
    "gpumd": {
        "citation": "Z. Fan, W. Chen, V. Vierimaa, A. Harju, Efficient molecular "
        "dynamics simulations with many-body potentials on graphics processing "
        "units, Comput. Phys. Commun. 218, 10 (2017)",
        "doi": "10.1016/j.cpc.2017.05.003",
        "license": "GPL-3.0",
        "license_source": "GPUMD GitHub LICENSE (WebFetch, GPL v3)",
        "url": "https://github.com/brucefan1983/GPUMD",
    },
    "lammps": {
        "citation": "A. P. Thompson, H. M. Aktulga, R. Berger, et al., LAMMPS - "
        "a flexible simulation tool for particle-based materials modeling at "
        "the atomic, meso, and continuum scales, Comput. Phys. Commun. 271, "
        "108171 (2022)",
        "doi": "10.1016/j.cpc.2021.108171",
        "license": "GPL-2.0",
        "license_source": "lammps/LICENSE (vendored clone, GPL v2); "
        "citation from lammps/CITATION.cff",
        "url": "https://www.lammps.org",
    },
    "i-pi": {
        "citation": "Y. Litman, V. Kapil, Y. M. Y. Feldman, et al., i-PI 3.0: "
        "a flexible and efficient framework for advanced atomistic simulations, "
        "J. Chem. Phys. 161, 062504 (2024)",
        "doi": "10.1063/5.0215869",
        "license": "GPL-2.0-or-later OR MIT (user's choice, dual license)",
        "license_source": "i-pi repo licenses/LICENSE.md (WebFetch, verified "
        "2026-07-11): 'i-PI is free software distributed under both the GPL and "
        "MIT licenses' (user's choice)",
        "url": "https://ipi-code.org",
    },
    "plumed": {
        "citation": "G. A. Tribello, M. Bonomi, D. Branduardi, C. Camilloni, "
        "G. Bussi, PLUMED 2: New feathers for an old bird, Comput. Phys. Commun. "
        "185, 604 (2014)",
        "doi": "10.1016/j.cpc.2013.09.018",
        "license": "LGPL-3.0",
        "license_source": "plumed2 repo COPYING.LESSER (GNU LGPL v3, 29 June "
        "2007; verified 2026-07-11 from the reviewed cookbook-audit table)",
        "url": "https://www.plumed.org",
    },
    # --- DFT ground state / periodic quantum chemistry -----------------------
    "qe": {
        "citation": "P. Giannozzi, S. Baroni, N. Bonini, et al., QUANTUM "
        "ESPRESSO: a modular and open-source software project for quantum "
        "simulations of materials, J. Phys. Condens. Matter 21, 395502 (2009)",
        "doi": "10.1088/0953-8984/21/39/395502",
        "license": "GPL-2.0",
        "license_source": "q-e/LICENSE (vendored clone, GPL v2)",
        "url": "https://www.quantum-espresso.org",
    },
    "vasp": {
        "citation": "G. Kresse, J. Furthmuller, Efficient iterative schemes for "
        "ab initio total-energy calculations using a plane-wave basis set, "
        "Phys. Rev. B 54, 11169 (1996)",
        "doi": "10.1103/PhysRevB.54.11169",
        "license": "Proprietary (VASP commercial license, vasp.at)",
        "license_source": "proprietary code, not vendored; terms per vasp.at "
        "(no open-source license file exists)",
        "url": "https://www.vasp.at",
    },
    # --- machine-learned interatomic potentials (driven via AtomisticSkills) -
    "mace": {
        "citation": "I. Batatia, D. P. Kovacs, G. N. C. Simm, C. Ortner, "
        "G. Csanyi, MACE: Higher order equivariant message passing neural "
        "networks for fast and accurate force fields, NeurIPS 35 (2022), "
        "arXiv:2206.07697",
        "doi": "10.48550/arXiv.2206.07697",
        "license": "MIT",
        "license_source": "mace-torch wheel METADATA "
        "(/tmp/mlipsrc/mace_torch-0.3.16-py3-none-any.whl)",
        "url": "https://github.com/ACEsuit/mace",
    },
    "matgl": {
        "citation": "C. Chen, S. P. Ong, A universal graph deep learning "
        "interatomic potential for the periodic table (M3GNet), Nat. Comput. "
        "Sci. 2, 718 (2022)",
        "doi": "10.1038/s43588-022-00349-3",
        "license": "BSD-3-Clause",
        "license_source": "matgl wheel METADATA "
        "(/tmp/mlipsrc/matgl-4.0.3-py3-none-any.whl)",
        "url": "https://github.com/materialsvirtuallab/matgl",
    },
    "fairchem": {
        "citation": "B. M. Wood, M. Dzamba, X. Fu, et al., UMA: A Family of "
        "Universal Models for Atoms (2025), arXiv:2506.23971",
        "doi": "10.48550/arXiv.2506.23971",
        "license": "MIT",
        "license_source": "fairchem-core wheel METADATA "
        "(/tmp/mlipsrc/fairchem_core-2.21.0-py3-none-any.whl)",
        "url": "https://github.com/facebookresearch/fairchem",
    },
    # --- electronic transport ------------------------------------------------
    "amset": {
        "citation": "A. M. Ganose, J. Park, A. Faghaninia, R. Woods-Robinson, "
        "K. A. Persson, A. Jain, Efficient calculation of carrier scattering "
        "rates from first principles, Nat. Commun. 12, 2222 (2021)",
        "doi": "10.1038/s41467-021-22440-5",
        "license": "BSD-3-Clause",
        "license_source": "amset wheel METADATA "
        "(/tmp/amsetsrc/amset-0.5.1-py3-none-any.whl, 'modified BSD')",
        "url": "https://github.com/hackingmaterials/amset",
    },
    # --- materials / structure & configuration -------------------------------
    "pymatgen": {
        "citation": "S. P. Ong, W. D. Richards, A. Jain, et al., Python "
        "Materials Genomics (pymatgen): A robust, open-source python library "
        "for materials analysis, Comput. Mater. Sci. 68, 314 (2013)",
        "doi": "10.1016/j.commatsci.2012.10.028",
        "license": "MIT",
        "license_source": "pymatgen pip metadata (pip show pymatgen, License: MIT)",
        "url": "https://pymatgen.org",
    },
    "mp-api": {
        "citation": "A. Jain, S. P. Ong, G. Hautier, et al., Commentary: The "
        "Materials Project: A materials genome approach to accelerating "
        "materials innovation, APL Mater. 1, 011002 (2013)",
        "doi": "10.1063/1.4812323",
        "license": "modified BSD (BSD-3-Clause)",
        "license_source": "mp-api pip metadata (pip show mp-api, License: modified BSD)",
        "url": "https://github.com/materialsproject/api",
    },
    "smol": {
        "citation": "L. Barroso-Luque, J. H. Yang, F. Xie, et al., smol: A Python "
        "package for cluster expansions and beyond, J. Open Source Softw. 7, "
        "4504 (2022)",
        "doi": "10.21105/joss.04504",
        "license": "BSD-3-Clause",
        "license_source": "smol sdist PKG-INFO / LICENSE "
        "(/tmp/cfgsrc/smol-0.5.7.tar.gz, BSD)",
        "url": "https://github.com/CederGroupHub/smol",
    },
    "pymatgen-analysis-diffusion": {
        "citation": "I.-H. Chu, Z. Deng, H. Nguyen, et al., pymatgen-analysis-"
        "diffusion (pymatgen-diffusion add-on); method: Z. Deng, Z. Zhu, "
        "I.-H. Chu, S. P. Ong, Data-driven first-principles methods for the "
        "study of ionic conductivity, Chem. Mater. 29, 281 (2017)",
        "doi": "10.1021/acs.chemmater.6b02648",
        "license": "BSD-3-Clause",
        "license_source": "pymatgen-analysis-diffusion wheel METADATA "
        "(/tmp/cfgsrc/pymatgen_analysis_diffusion-2025.11.15-py3-none-any.whl)",
        "url": "https://github.com/materialsvirtuallab/pymatgen-analysis-diffusion",
    },
    "rxn-network": {
        "citation": "M. J. McDermott, S. S. Dwaraknath, K. A. Persson, A "
        "graph-based network for predicting inorganic reaction pathways, "
        "Nat. Commun. 12, 3097 (2021)",
        "doi": "10.1038/s41467-021-23339-x",
        "license": "modified BSD (BSD-3-Clause)",
        "license_source": "reaction-network wheel METADATA "
        "(/tmp/cfgsrc/reaction_network-8.3.0-py3-none-any.whl, 'modified BSD')",
        "url": "https://github.com/GENESIS-EFRC/reaction-network",
    },
    "diffcsp": {
        "citation": "R. Jiao, W. Huang, P. Lin, J. Han, P. Chen, Y. Lu, Y. Liu, "
        "Crystal Structure Prediction by Joint Equivariant Diffusion (DiffCSP), "
        "NeurIPS 36 (2023), arXiv:2309.04475; space-group-constrained variant "
        "DiffCSP++ arXiv:2402.03992",
        "doi": "10.48550/arXiv.2309.04475",
        "license": "MIT",
        "license_source": "DiffCSP GitHub LICENSE (WebFetch)",
        "url": "https://github.com/jiaor17/DiffCSP",
    },
    "mattergen": {
        "citation": "C. Zeni, R. Pinsler, D. Zugner, et al., A generative model "
        "for inorganic materials design (MatterGen), Nature 639, 624 (2025)",
        "doi": "10.1038/s41586-025-08628-5",
        "license": "MIT",
        "license_source": "MatterGen GitHub LICENSE (WebFetch)",
        "url": "https://github.com/microsoft/mattergen",
    },
    # --- composites (effective medium) ---------------------------------------
    "materialscodegraph": {
        # The composite effective-conductivity tool implements two published,
        # validated formulas; the citation names both (the map author reproduced
        # the pinned 1.2452 W/(m K) reference independently against them).
        "citation": "C.-W. Nan, R. Birringer, D. R. Clarke, H. Gleiter, Effective "
        "thermal conductivity of particulate composites with interfacial thermal "
        "resistance, J. Appl. Phys. 81, 6692 (1997); spherical-limit cross-check "
        "D. P. H. Hasselman, L. F. Johnson, Effective thermal conductivity of "
        "composites with interfacial thermal barrier resistance, J. Compos. "
        "Mater. 21, 508 (1987)",
        "doi": "10.1063/1.365209",
        "license": "Apache-2.0",
        # materialscodegraph is a private Da Vinci Labs repository (the repo
        # metadata endpoint is not public); its committed LICENSE file reads
        # Apache License 2.0, read directly from the file over the API.
        "license_source": "materialscodegraph/materialscodegraph LICENSE (gh api "
        "repos/materialscodegraph/materialscodegraph/contents/LICENSE -> Apache "
        "License 2.0, spdx_id Apache-2.0; private Da Vinci Labs repo, verified "
        "2026-07-13)",
        "url": "https://github.com/materialscodegraph/materialscodegraph",
    },
    # --- thermochemistry -----------------------------------------------------
    "pycalphad": {
        "citation": "R. Otis, Z.-K. Liu, pycalphad: CALPHAD-based Computational "
        "Thermodynamics in Python, J. Open Res. Softw. 5, 1 (2017)",
        "doi": "10.5334/jors.140",
        "license": "MIT",
        "license_source": "pycalphad wheel METADATA "
        "(/tmp/pcsrc/pycalphad-0.11.2-cp312-...-macosx.whl)",
        "url": "https://pycalphad.org",
    },
    # --- molecular -----------------------------------------------------------
    "openmm": {
        "citation": "P. Eastman, J. Swails, J. D. Chodera, et al., OpenMM 7: "
        "Rapid development of high performance algorithms for molecular "
        "dynamics, PLoS Comput. Biol. 13, e1005659 (2017)",
        "doi": "10.1371/journal.pcbi.1005659",
        "license": "MIT (with LGPL parts)",
        "license_source": "OpenMM GitHub README (WebFetch): most source is "
        "MIT or LGPL; not vendored here",
        "url": "https://openmm.org",
    },
    "orca": {
        "citation": "F. Neese, Software update: The ORCA program system, "
        "Version 6.0, WIREs Comput. Mol. Sci. 15, e70019 (2025)",
        "doi": "10.1002/wcms.70019",
        "license": "Proprietary (ORCA: free for academic use; commercial "
        "license via FACCTs)",
        "license_source": "proprietary binary, not vendored; terms per "
        "orcaforum / FACCTs (no open-source license file exists)",
        "url": "https://www.faccts.de/orca/",
    },
    # --- AtomisticSkills skill rails (cite the AtomisticSkills paper) ---------
    "mat-elasticity": {
        "citation": "B. Deng, B. Li, M. Cox, et al., Harnessing AtomisticSkills "
        "for Agentic Atomistic Research (2025), arXiv:2605.24002 "
        "(mat-elasticity skill)",
        "doi": "10.48550/arXiv.2605.24002",
        "license": "MIT",
        "license_source": "AtomisticSkills/LICENSE (vendored clone, MIT); "
        "citation from AtomisticSkills/README.md",
        "url": "https://github.com/learningmatter-mit/AtomisticSkills",
    },
    "mat-diffusion-analysis": {
        "citation": "B. Deng, B. Li, M. Cox, et al., Harnessing AtomisticSkills "
        "for Agentic Atomistic Research (2025), arXiv:2605.24002 "
        "(mat-diffusion-analysis skill)",
        "doi": "10.48550/arXiv.2605.24002",
        "license": "MIT",
        "license_source": "AtomisticSkills/LICENSE (vendored clone, MIT); "
        "citation from AtomisticSkills/README.md",
        "url": "https://github.com/learningmatter-mit/AtomisticSkills",
    },
    "mat-equation-of-state": {
        "citation": "B. Deng, B. Li, M. Cox, et al., Harnessing AtomisticSkills "
        "for Agentic Atomistic Research (2025), arXiv:2605.24002 "
        "(mat-equation-of-state skill)",
        "doi": "10.48550/arXiv.2605.24002",
        "license": "MIT",
        "license_source": "AtomisticSkills/LICENSE (vendored clone, MIT); "
        "citation from AtomisticSkills/README.md",
        "url": "https://github.com/learningmatter-mit/AtomisticSkills",
    },
    "mat-surface-adsorption": {
        "citation": "B. Deng, B. Li, M. Cox, et al., Harnessing AtomisticSkills "
        "for Agentic Atomistic Research (2025), arXiv:2605.24002 "
        "(mat-surface-adsorption skill)",
        "doi": "10.48550/arXiv.2605.24002",
        "license": "MIT",
        "license_source": "AtomisticSkills/LICENSE (vendored clone, MIT); "
        "citation from AtomisticSkills/README.md",
        "url": "https://github.com/learningmatter-mit/AtomisticSkills",
    },
    # --- foundation library --------------------------------------------------
    "ase": {
        "citation": "A. H. Larsen, J. J. Mortensen, J. Blomqvist, et al., The "
        "atomic simulation environment - a Python library for working with "
        "atoms, J. Phys. Condens. Matter 29, 273002 (2017)",
        "doi": "10.1088/1361-648X/aa680e",
        "license": "LGPL-2.1-or-later",
        "license_source": "ase pip metadata "
        "(pip show ase, License-Expression: LGPL-2.1-or-later)",
        "url": "https://ase-lib.org",
    },
}
