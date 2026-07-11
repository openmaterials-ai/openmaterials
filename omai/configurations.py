"""The configuration layer: atomic structures as first-class evidence.

A configuration record is the evidence home of a Structure value: the pymatgen
MSONable payload (cell + species + positions), a content-addressed canonical
uid, derived display fields, and a provenance list. The map's Structure node
stays ONE opaque node (its description carries the contract); the coordinates
live here, in ``docs/data/configurations/<slug>.json``.

Identity (the content-addressing rule, spec section 3):

    canonical_uid = sha256 of the spglib-standardized primitive cell (symprec
    1e-3), origin-anchored so a rigid translation of the whole cell does not
    change it, species and sites sorted, lattice and fractional coordinates
    rounded to 6 decimals, serialized with sorted keys.

Deterministic: the same cell, its shuffled sites, and a supercell of it hash to
the same uid; a strained cell hashes differently. Disordered / partial-occupancy
cells cannot be standardized by spglib, so their as-given cell is hashed (no
primitive reduction) and the record notes it. On top of the hash the dedup gate
runs pymatgen's StructureMatcher against existing records: a
physically-equivalent-but-not-hash-identical cell is FLAGGED for human review,
never silently merged (the matcher tolerance is a judgment call; the human is
the judge). Provenance appends to the existing record on a confirmed duplicate.

Bridge entry points (spec section 4): ``record_configuration``, ``from_mp``,
``from_file``, ``load``. ``from_mp`` needs the network and a Materials Project
key (CLI only); the rest are offline.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_DIR = _REPO_ROOT / "docs" / "data" / "configurations"

# Cells at or below this atom count embed the full structure dict inline; larger
# cells (the 17k-atom a-Si class) point to a file and store only reduced
# metadata inline so the record stays searchable without the file.
INLINE_ATOM_LIMIT = 1000

# spglib symmetry tolerance for canonicalization (spec section 3).
SYMPREC = 1e-3

__all__ = [
    "ConfigurationError",
    "DuplicateFlag",
    "canonical_uid",
    "record_configuration",
    "from_file",
    "from_mp",
    "load",
    "slugify",
]


class ConfigurationError(Exception):
    """A structure failed validation, or a record could not be written."""


class DuplicateFlag(Exception):
    """The dedup gate found a StructureMatcher-equivalent existing record.

    Not an error in the data: a call to review. Carries the matched record's
    uid and slug so the caller (or a human) can append provenance to it instead
    of minting a new record.
    """

    def __init__(self, uid: str, slug: str, message: str):
        self.uid = uid
        self.slug = slug
        super().__init__(message)


def slugify(text: str) -> str:
    """Lowercase, non-alphanumerics to single hyphens, trimmed."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


# --------------------------------------------------------------------------
# Validation.
# --------------------------------------------------------------------------

def _is_ordered(structure) -> bool:
    """True if every site is fully occupied by a single real element.

    Disordered / partial-occupancy cells return False: spglib cannot
    standardize them, so canonicalization hashes the as-given cell instead.
    """
    return bool(getattr(structure, "is_ordered", True))


def _validate(structure) -> None:
    """Reject a structure that is not a well-formed periodic configuration.

    Species must be real elements (pymatgen's parse already guarantees this for
    Element/Species), the lattice must be non-singular, and there must be at
    least one atom. Molecules (non-periodic) are validated separately by their
    own path and skip the lattice check.
    """
    from pymatgen.core import Molecule

    if len(structure) < 1:
        raise ConfigurationError("structure has no atoms (natoms must be > 0)")
    if isinstance(structure, Molecule):
        return
    try:
        vol = float(structure.lattice.volume)
    except Exception as exc:  # noqa: BLE001 - surface any lattice failure as one message
        raise ConfigurationError(f"lattice is not usable: {exc}") from None
    if not (vol > 1e-8):
        raise ConfigurationError("lattice is singular (volume ~ 0)")


# --------------------------------------------------------------------------
# Canonicalization / identity.
# --------------------------------------------------------------------------

def _canonical_payload(structure) -> tuple[dict, dict]:
    """Return (canonical_dict, derived) for the content hash.

    canonical_dict is the origin-anchored, sorted, rounded serialization the
    uid hashes over. derived carries the display facts computed here (spacegroup,
    natoms_primitive, disordered flag) so the record does not recompute them.
    """
    import numpy as np
    from pymatgen.core import Molecule

    if isinstance(structure, Molecule):
        # Non-periodic: hash sorted species + coordinates rounded to 6 decimals,
        # translation-anchored on the centroid so a rigid shift is invariant.
        coords = np.array(structure.cart_coords, dtype=float)
        coords = coords - coords.mean(axis=0)
        rows = sorted([[str(s.specie)] + [float(round(x, 6)) for x in c]
                       for s, c in zip(structure, coords)])
        canonical = {"periodic": False, "sites": rows}
        derived = {"spacegroup": None, "natoms_primitive": len(structure),
                   "disordered": False}
        return canonical, derived

    ordered = _is_ordered(structure)
    if ordered:
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

        sga = SpacegroupAnalyzer(structure, symprec=SYMPREC)
        prim = sga.get_primitive_standard_structure()
        spacegroup = sga.get_space_group_number()
    else:
        # spglib cannot standardize partial occupancy: hash the as-given cell.
        prim = structure
        spacegroup = None

    entries = [(str(s.specie), np.array(s.frac_coords, dtype=float) % 1.0)
               for s in prim]
    # Translation canonicalization: anchor each site at the origin in turn, wrap,
    # round, sort; keep the lexicographically smallest serialization. This makes
    # a rigid translation of the whole cell (which spglib's origin choice leaves
    # ambiguous) invariant, so a supercell reduced to the same primitive and the
    # primitive itself agree.
    best: str | None = None
    for _anchor_sp, anchor_fc in entries:
        shifted = []
        for sp, fc in entries:
            d = (fc - anchor_fc) % 1.0
            d = np.round(d, 6) % 1.0  # re-wrap 0.999999 -> 0.0
            shifted.append([sp] + [float(round(x, 6)) for x in d])
        shifted.sort()
        blob = json.dumps(shifted, sort_keys=True, separators=(",", ":"))
        if best is None or blob < best:
            best = blob

    lattice = [[round(v, 6) for v in row]
               for row in prim.lattice.matrix.tolist()]
    canonical = {"periodic": True, "lattice": lattice, "sites_canonical": best}
    derived = {"spacegroup": spacegroup, "natoms_primitive": len(prim),
               "disordered": not ordered}
    return canonical, derived


def canonical_uid(structure) -> str:
    """The content-addressed identity uid of a pymatgen Structure / Molecule."""
    canonical, _ = _canonical_payload(structure)
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# The record.
# --------------------------------------------------------------------------

def _existing_records(config_dir: Path):
    """Yield (path, record) for every configuration record on disk."""
    if not config_dir.exists():
        return
    for path in sorted(config_dir.glob("*.json")):
        try:
            yield path, json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue


def _load_structure_from_record(record):
    """Reconstruct a pymatgen Structure/Molecule from a record's inline dict.

    Returns None when the record embeds only reduced metadata (a >limit cell
    whose full payload is in a pointed-to file); the matcher then skips it, since
    we cannot re-parse the full cell without reading the file.
    """
    from pymatgen.core import Molecule, Structure

    payload = record.get("structure")
    if not isinstance(payload, dict) or "@class" not in payload:
        return None
    cls = payload.get("@class")
    try:
        if cls == "Molecule":
            return Molecule.from_dict(payload)
        return Structure.from_dict(payload)
    except Exception:  # noqa: BLE001 - a malformed inline dict just skips matching
        return None


def _dedup_gate(structure, uid: str, config_dir: Path):
    """Run the identity + StructureMatcher dedup gate.

    Returns (existing_path, existing_record) when a hash-identical record already
    exists (append-provenance path). Raises DuplicateFlag when a DIFFERENT record
    is StructureMatcher-equivalent (human-review path). Returns (None, None) when
    the cell is new.
    """
    from pymatgen.analysis.structure_matcher import StructureMatcher
    from pymatgen.core import Molecule

    hash_match = None
    for path, record in _existing_records(config_dir):
        if record.get("canonical", {}).get("uid") == uid:
            hash_match = (path, record)
            break
    if hash_match is not None:
        return hash_match

    # Molecules and disordered cells: StructureMatcher is periodic-crystal only,
    # so the hash is the whole gate for them.
    if isinstance(structure, Molecule) or not _is_ordered(structure):
        return None, None

    matcher = StructureMatcher(attempt_supercell=False)
    for path, record in _existing_records(config_dir):
        other = _load_structure_from_record(record)
        if other is None or isinstance(other, Molecule) or not _is_ordered(other):
            continue
        try:
            equivalent = matcher.fit(structure, other)
        except Exception:  # noqa: BLE001 - a matcher failure is not a merge signal
            equivalent = False
        if equivalent:
            other_uid = record.get("canonical", {}).get("uid", "")
            raise DuplicateFlag(
                other_uid, path.stem,
                f"structure is StructureMatcher-equivalent to existing record "
                f"{path.stem} (uid {other_uid[:12]}) but not hash-identical; "
                f"append provenance to it after human review instead of minting "
                f"a new record")
    return None, None


def _reduced_metadata(structure) -> dict:
    """The searchable reduced view stored inline for a >limit (file-backed) cell.

    Lattice, formula, and natoms only: enough to find the record without opening
    the pointed-to file. Molecules carry no lattice.
    """
    from pymatgen.core import Molecule

    meta = {"formula": structure.composition.formula,
            "natoms": len(structure)}
    if not isinstance(structure, Molecule):
        meta["lattice"] = [list(map(float, row))
                           for row in structure.lattice.matrix.tolist()]
    return meta


def record_configuration(structure_or_file, name, provenance, *,
                         external_id=None, config_dir=None, file_ref=None):
    """Validate, canonicalize, dedup-gate, and write a configuration record.

    Parameters
    ----------
    structure_or_file : pymatgen Structure/Molecule OR a path to a structure
        file (POSCAR/CIF/extxyz/pw.x). A path is parsed via ``from_file``.
    name : str
        Human label; the material string's home ("Si diamond primitive").
    provenance : list[dict]
        One or more {"kind", "ref", "detail"} sources for this same cell.
    external_id : dict | None
        e.g. {"materials_project": "mp-149"}.
    config_dir : Path | None
        Override the default docs/data/configurations directory (tests).
    file_ref : dict | None
        For a >INLINE_ATOM_LIMIT cell: {"path": ..., "sha256": ...} pointing at
        the committed structure file; the inline payload is then reduced
        metadata only. Ignored for small cells.

    Returns
    -------
    str
        The canonical uid. On a hash-identical existing record, provenance and
        external_id are appended to it and its uid is returned (no new file).

    Raises
    ------
    ConfigurationError
        On invalid structure input.
    DuplicateFlag
        When a StructureMatcher-equivalent but not hash-identical record exists.
    """
    config_dir = Path(config_dir) if config_dir else _CONFIG_DIR
    if isinstance(structure_or_file, (str, Path)):
        structure = from_file(structure_or_file)
    else:
        structure = structure_or_file

    _validate(structure)
    canonical, derived = _canonical_payload(structure)
    uid = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        .encode("utf-8")).hexdigest()

    if not isinstance(provenance, list) or not provenance:
        raise ConfigurationError("provenance must be a non-empty list of sources")

    existing_path, existing_record = _dedup_gate(structure, uid, config_dir)
    if existing_record is not None:
        # Hash-identical: append provenance / external ids, keep one record.
        changed = False
        prov = existing_record.setdefault("provenance", [])
        for p in provenance:
            if p not in prov:
                prov.append(p)
                changed = True
        if external_id:
            ext = existing_record.setdefault("external_ids", {})
            for k, v in external_id.items():
                if ext.get(k) != v:
                    ext[k] = v
                    changed = True
        if changed:
            existing_path.write_text(json.dumps(existing_record, indent=2,
                                                sort_keys=True) + "\n")
        return uid

    natoms = len(structure)
    inline_full = natoms <= INLINE_ATOM_LIMIT and file_ref is None
    record = {
        "name": name,
        "formula": structure.composition.reduced_formula
        if structure.is_ordered else structure.composition.formula,
        # natoms is the as-given cell size (what the embedded dict costs);
        # natoms_primitive is the standardized primitive's size (identity).
        "natoms": natoms,
        "structure": structure.as_dict() if inline_full
        else _reduced_metadata(structure),
        "canonical": {
            "uid": uid,
            "spacegroup": derived["spacegroup"],
            "natoms_primitive": derived["natoms_primitive"],
        },
        "external_ids": dict(external_id) if external_id else {},
        "provenance": list(provenance),
        "files": (dict(file_ref) if file_ref else None) if not inline_full
        else None,
    }
    if derived["disordered"]:
        record["canonical"]["disordered"] = True

    config_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(name) or uid[:12]
    path = config_dir / f"{slug}.json"
    # Avoid clobbering a different cell that slugged to the same name.
    if path.exists():
        prior = json.loads(path.read_text())
        if prior.get("canonical", {}).get("uid") != uid:
            path = config_dir / f"{slug}-{uid[:8]}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return uid


# --------------------------------------------------------------------------
# Constructors.
# --------------------------------------------------------------------------

# File-extension to pymatgen format hint. pymatgen's from_file sniffs known
# basenames (POSCAR, CONTCAR) and a handful of extensions, but not '.poscar' or
# '.pwi', so an explicit hint from the extension makes those parse.
_FORMAT_BY_SUFFIX = {
    ".poscar": "poscar",
    ".vasp": "poscar",
    ".contcar": "poscar",
    ".cif": "cif",
    ".xyz": "xyz",
    ".extxyz": "xyz",
    ".pwi": "pwscf",
    ".pwo": None,   # pw.x OUTPUT: let from_file's sniffer handle it
    ".in": "pwscf",
}


def from_file(path):
    """Parse a structure file (POSCAR/CIF/extxyz/pw.x) into a pymatgen object.

    pymatgen's ``from_file`` sniffs known basenames and extensions; a hint from
    the file extension covers the ones it does not (``.poscar``, ``.pwi``).
    extended-xyz and Quantum ESPRESSO inputs parse through their format hint;
    a non-periodic file falls back to ``Molecule``.
    """
    from pymatgen.core import Molecule, Structure

    path = Path(path)
    if not path.exists():
        raise ConfigurationError(f"structure file not found: {path}")

    fmt = _FORMAT_BY_SUFFIX.get(path.suffix.lower(), "unset")
    text = None
    try:
        if fmt not in ("unset", None):
            text = path.read_text()
            return Structure.from_str(text, fmt=fmt)
        return Structure.from_file(str(path))
    except Exception as first_error:  # noqa: BLE001 - try the molecule / ase paths
        try:
            if text is not None and fmt == "xyz":
                return Molecule.from_str(text, fmt="xyz")
            return Molecule.from_file(str(path))
        except Exception:
            raise ConfigurationError(
                f"could not parse {path.name} as a structure: {first_error}"
            ) from None


def from_mp(mp_id, *, config_dir=None, api_key=None):
    """Record the Materials Project summary structure for ``mp_id``.

    Requires the network and a Materials Project API key (CLI only). The key is
    read (in order) from the explicit ``api_key`` argument, then MP_API_KEY /
    PMG_MAPI_KEY in the environment (the repo-root .env is loaded first via the
    reusable paper_parser env loader). Never logged.

    Returns the canonical uid of the recorded configuration.
    """
    import os

    from omai.paper_parser.env import load_env

    load_env()
    key = (api_key or os.environ.get("MP_API_KEY")
           or os.environ.get("PMG_MAPI_KEY"))
    if not key:
        raise ConfigurationError(
            "from_mp needs a Materials Project API key (set MP_API_KEY or "
            "PMG_MAPI_KEY, or pass api_key=)")

    from mp_api.client import MPRester

    with MPRester(key) as mpr:
        structure = mpr.get_structure_by_material_id(mp_id)

    return record_configuration(
        structure,
        name=f"{structure.composition.reduced_formula} ({mp_id})",
        provenance=[{"kind": "database", "ref": "materials-project",
                     "detail": f"{mp_id}, MP summary"}],
        external_id={"materials_project": mp_id},
        config_dir=config_dir,
    )


def load(uid, *, config_dir=None):
    """Reconstruct the pymatgen Structure/Molecule for a canonical ``uid``.

    Reads the inline dict; a file-backed (>limit) record whose inline payload is
    reduced metadata only raises, since the full cell lives in the pointed-to
    file (open it with pymatgen directly).
    """
    from pymatgen.core import Molecule, Structure

    config_dir = Path(config_dir) if config_dir else _CONFIG_DIR
    for _path, record in _existing_records(config_dir):
        if record.get("canonical", {}).get("uid") == uid:
            payload = record.get("structure")
            if not isinstance(payload, dict) or "@class" not in payload:
                raise ConfigurationError(
                    f"record {uid[:12]} is file-backed; open its files entry "
                    f"with pymatgen directly")
            if payload.get("@class") == "Molecule":
                return Molecule.from_dict(payload)
            return Structure.from_dict(payload)
    raise ConfigurationError(f"no configuration record for uid {uid[:12]}")
