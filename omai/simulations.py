"""The simulation layer: a whole run as content-addressed, gated evidence.

A simulation record is the shareable unit of a computation: the recipe that was
asked (map identity + material + conditions + params), the execution that ran
it (code, version, container digest, runner, wall time, seeds), a manifest of
the artifacts it wrote (path, bytes, sha256, role), and the run's results (the
instances it produced, as backref slugs or inline stubs). It is the structural
sibling of the value, configuration, and spectrum records: evidence that lives
in ``docs/data/simulations/<slug>.json``, never on the map page itself.

Identity (the content-addressing rule, this module's protocol commitment):

    record_id = sha256 of the canonical JSON of exactly the CLAIM: the triple
    (recipe, execution, artifacts), where each artifact entry is exactly
    {path, bytes, sha256, role} and carries NO url. Location is deliberately
    out of the hash. The bytes are identified by their sha256; WHERE they can
    be fetched (an R2 bucket, a Zenodo DOI, a mirror) is a mutable resolver
    layer stored in a ``mirrors`` field OUTSIDE the hashed claim. Moving bytes,
    renaming a bucket, or adding a mirror therefore never re-mints the record
    and never orphans a backref: a record whose bytes moved is stale, not
    wrong. This is the configurations precedent (hash the standardized cell,
    not wherever the CIF happens to live) applied to a whole run.

    ``results`` is also outside the hashed claim: a result instance carries the
    record id as its ``simulation`` backref, so it cannot sit inside the payload
    that mints that id (a circular reference), and bundling or re-bundling the
    instances a run produced must not disturb the run's identity.

Canonicalization (the configurations precedent, verbatim): sorted keys, compact
separators, and an explicit float rule. Every float inside ``conditions`` and
``params`` (at any nesting depth) is rounded to :data:`FLOAT_DECIMALS` decimals
before hashing, so refetch-level numerical noise in a shared recipe collapses to
one identity while physically distinct runs stay apart; booleans and integers
are preserved exactly. The rounding rule covers conditions and params ONLY: a
float anywhere else in the claim (a fractional ``wall_time_s`` in execution)
enters the hash exactly as canonical JSON serializes it, unrounded, so ``4210``
and ``4210.0`` are different claims; write execution values the way they are
meant to be compared. The canonical blob is
``json.dumps(claim, sort_keys=True, separators=(",", ":"))`` and the id is its
sha256; this rule is a protocol commitment, not an implementation detail.

Validation (gate-shaped, cheap, deterministic): the recipe's node resolves
against the live map by BOTH id and content uid (the instances node-pin
discipline: a stale pin is a mismatch, not a silent pass); the execution block
is an object naming the ``code`` that ran; a named configuration
uid exists under ``docs/data/configurations/``; every manifest entry is
well-formed (sha256 a 64-hex string, bytes a positive int, role non-empty); and
any bundled result instance passes the existing instance checks (the same
required keys as ``build_instances``, ``conditions`` included) and carries a
``simulation`` backref equal to the record id. A result given as a backref slug
is accepted bare by the writer (results sit outside the hashed claim and may be
appended after the instance lands), but at bundle time the slug must resolve:
the named file exists under ``docs/data/instances/`` and backrefs the record.
``build_instances`` closes the loop in the other direction, refusing an
instance whose ``simulation`` backref matches no committed record, so neither
side of the citation can dangle in the commons.

Verification (a report, NEVER a gate): :func:`verify_simulation` checks the
mirrors for reachability and checksum match when URLs are present and returns a
dated report. A record whose bytes moved or whose mirror is down is stale, not
invalid; the map owns identity and checksums, object storage owns the bytes.

This module also carries the import/verify half: the bridge from a hosted
bundle (an MCG-style ``manifest.json`` describing a run) to a verified
SimulationRecord. :func:`record_from_bundle` maps a host bundle onto the
record shape and mints the same content-addressed id, refusing an
unverifiable bundle whose artifacts lack a sha256 or role; :func:`verify_bundle_bytes`
reports (never gates) whether each artifact's bytes match its checksum when
they are locally or fetchably reachable.

Bridge entry points: :func:`record_simulation` (write one record, idempotent on
identical content, refusing a silent overwrite on different content, the
``record_instance`` discipline), :func:`record_from_bundle` (build a canonical
record from a host bundle manifest), :func:`verify_simulation` (the dated
reachability report over a record's mirrors), and :func:`verify_bundle_bytes`
(the dated byte-vs-checksum report over local files or a fetcher). Bundling
into ``docs/data/simulations.json`` lives in :mod:`omai.map_data`
(``build_simulations``), mirroring the other record kinds.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SIM_DIR = _REPO_ROOT / "docs" / "data" / "simulations"
_CONFIG_DIR = _REPO_ROOT / "docs" / "data" / "configurations"

# Decimals every float in conditions/params is rounded to before hashing. Six
# collapses refetch-level noise in a shared recipe (e.g. a temperature written
# 300.0000001) to one identity while keeping physically distinct runs apart. The
# configurations layer rounds coordinates to 5; recipe conditions are physical
# scalars, not fractional coordinates, so 6 is the resolution here.
FLOAT_DECIMALS = 6

# A sha256 hex digest: 64 lowercase hex characters. Manifest entries and result
# backrefs are checked against this shape (a hex64), never guessed.
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

__all__ = [
    "SimulationError",
    "canonical_id",
    "committed_ids",
    "record_simulation",
    "record_from_bundle",
    "verify_simulation",
    "verify_bundle_bytes",
    "slugify",
]


class SimulationError(Exception):
    """A simulation record failed validation, or could not be written."""


def slugify(text: str) -> str:
    """Lowercase, non-alphanumerics to single hyphens, trimmed."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


# --------------------------------------------------------------------------
# Canonicalization / identity.
# --------------------------------------------------------------------------

def _round_floats(obj):
    """Recursively round every float to FLOAT_DECIMALS; leave all else intact.

    Booleans are left exactly (a bool is an int in Python, never a float here);
    integers pass through; dict keys are preserved. This normalizes the only
    floats in a claim, which live in conditions and params, so that a shared
    recipe carrying refetch-level float noise collapses to one identity.
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        return round(obj, FLOAT_DECIMALS)
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v) for v in obj]
    return obj


def _manifest_entry(art: dict) -> dict:
    """The hashed view of one artifact: exactly {path, bytes, sha256, role}.

    Any ``url`` (or other resolver key) on the input is dropped here: location
    never enters identity. The four kept keys are the claim about the bytes.
    """
    return {
        "path": art.get("path"),
        "bytes": art.get("bytes"),
        "sha256": art.get("sha256"),
        "role": art.get("role"),
    }


def _claim(recipe: dict, execution: dict, artifacts: list[dict]) -> dict:
    """The canonical claim the record id hashes over: (recipe, execution,
    artifacts), with conditions/params float-normalized and every artifact
    reduced to its location-free manifest entry.
    """
    normalized_recipe = dict(recipe)
    if "conditions" in normalized_recipe:
        normalized_recipe["conditions"] = _round_floats(normalized_recipe["conditions"])
    if "params" in normalized_recipe:
        normalized_recipe["params"] = _round_floats(normalized_recipe["params"])
    return {
        "recipe": normalized_recipe,
        "execution": execution,
        "artifacts": [_manifest_entry(a) for a in artifacts],
    }


def canonical_id(recipe: dict, execution: dict, artifacts: list[dict]) -> str:
    """The content-addressed id of a simulation: sha256 of the canonical claim.

    Hashes exactly (recipe, execution, artifacts-without-urls). Two runs with
    the same recipe, execution, and artifact checksums mint the same id no
    matter where the bytes are hosted; a different recipe, code, or checksum
    mints a different id.
    """
    blob = json.dumps(_claim(recipe, execution, artifacts),
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Validation (the cheap, deterministic gate).
# --------------------------------------------------------------------------

def _validate_manifest(artifacts, *, where: str) -> None:
    """Every manifest entry is well-formed: sha256 hex64, bytes positive int,
    role non-empty, path non-empty. Malformed bytes are a data error, not a
    reachability question (that is verify's job).
    """
    if not isinstance(artifacts, list):
        raise SimulationError(f"{where}: artifacts must be a list")
    for i, art in enumerate(artifacts):
        if not isinstance(art, dict):
            raise SimulationError(f"{where}: artifact {i} must be an object")
        path = art.get("path")
        if not isinstance(path, str) or not path:
            raise SimulationError(f"{where}: artifact {i} path must be a non-empty string")
        nbytes = art.get("bytes")
        if isinstance(nbytes, bool) or not isinstance(nbytes, int) or nbytes <= 0:
            raise SimulationError(
                f"{where}: artifact {i} bytes must be a positive integer")
        sha = art.get("sha256")
        if not isinstance(sha, str) or not _SHA256_RE.match(sha):
            raise SimulationError(
                f"{where}: artifact {i} sha256 must be a 64-hex-character string")
        role = art.get("role")
        if not isinstance(role, str) or not role:
            raise SimulationError(f"{where}: artifact {i} role must be non-empty")


def _validate_execution(execution, *, where: str) -> None:
    """The execution block is well-formed: an object naming the code that ran.

    The block is the record's "what ran" claim (code, version, container
    digest, runner, wall time, seeds); everything in it is optional EXCEPT that
    the block is an object and ``code`` is a non-empty string. A run
    necessarily ran some code; a record whose execution is null, a bare string,
    or an empty object is degenerate and fails here, the manifest gate's
    well-formedness bar applied to the execution claim.
    """
    if not isinstance(execution, dict):
        raise SimulationError(f"{where}: execution must be an object")
    code = execution.get("code")
    if not isinstance(code, str) or not code:
        raise SimulationError(
            f"{where}: execution.code must be a non-empty string (the code "
            f"that ran)")


def _validate_recipe_node(recipe, name_to_uid, *, where: str) -> None:
    """The recipe's node resolves against the live map by id AND uid pin.

    ``recipe.node`` is the map node id; ``recipe.node_uid`` (when the record
    carries one, the pin) must equal the live content uid of that id. A stale
    pin is a mismatch that fails the gate, never a silent pass: the instances
    node-pin discipline, applied to the recipe's node.
    """
    if not isinstance(recipe, dict):
        raise SimulationError(f"{where}: recipe must be an object")
    node = recipe.get("node")
    if not isinstance(node, str) or node not in name_to_uid:
        raise SimulationError(f"{where}: recipe.node {node!r} is not a live map node")
    pin = recipe.get("node_uid")
    if pin is not None and pin != name_to_uid[node]:
        raise SimulationError(
            f"{where}: recipe.node_uid pin {str(pin)[:12]} does not match the "
            f"live uid {name_to_uid[node][:12]} of node {node!r}")


def _validate_configuration(recipe, *, config_dir: Path, where: str) -> None:
    """A named configuration uid exists under docs/data/configurations/.

    The configuration is optional (a bare material name is legitimate); when
    the recipe pins one, it must resolve to a committed configuration record.
    """
    material = recipe.get("material") or {}
    uid = material.get("configuration") if isinstance(material, dict) else None
    if uid is None:
        return
    # A recipe may carry the uid bare or as "sha256:<uid>"; accept both.
    wanted = uid.split(":", 1)[1] if isinstance(uid, str) and uid.startswith("sha256:") else uid
    if config_dir.exists():
        for path in config_dir.glob("*.json"):
            try:
                rec = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if rec.get("canonical", {}).get("uid") == wanted:
                return
    raise SimulationError(
        f"{where}: configuration {str(wanted)[:12]} is not a committed "
        f"configuration record under {config_dir.name}/")


def _validate_results(results, record_id, name_to_uid, *, where: str,
                      instances_dir: Path | None = None) -> None:
    """Bundled result instances pass the existing instance checks and backref
    this record. A result may be a bare backref slug (a string, pointing at an
    already-committed instance file) or an inline instance stub (a dict). An
    inline stub is held to the instance contract (the same required keys as
    ``build_instances``, ``conditions`` included) AND must carry
    ``simulation == record_id``: the run owns the values it produced. A slug is
    accepted bare by the writer (results sit outside the hashed claim and may
    be appended after the instance lands); when ``instances_dir`` is given (the
    bundler), the slug must resolve to a committed instance file that backrefs
    this record.
    """
    if results is None:
        return
    if not isinstance(results, list):
        raise SimulationError(f"{where}: results must be a list")
    for i, res in enumerate(results):
        if isinstance(res, str):
            # A backref slug: a pointer to a committed instance file.
            if not res:
                raise SimulationError(f"{where}: result {i} backref slug is empty")
            if instances_dir is not None:
                inst_path = Path(instances_dir) / f"{res}.json"
                if not inst_path.exists():
                    raise SimulationError(
                        f"{where}: result {i} slug {res!r} has no committed "
                        f"instance file under {Path(instances_dir).name}/")
                try:
                    inst = json.loads(inst_path.read_text())
                except (json.JSONDecodeError, OSError) as exc:
                    raise SimulationError(
                        f"{where}: result {i} instance {res}.json is "
                        f"unreadable: {exc}")
                if inst.get("simulation") != record_id:
                    raise SimulationError(
                        f"{where}: result {i} instance {res!r} does not "
                        f"backref this record (simulation "
                        f"{str(inst.get('simulation'))[:12]} != {record_id[:12]})")
            continue
        if not isinstance(res, dict):
            raise SimulationError(
                f"{where}: result {i} must be a backref slug or an instance stub")
        for key in ("variable", "material", "conditions", "value", "units", "source"):
            if key not in res:
                raise SimulationError(f"{where}: result {i} instance stub missing {key!r}")
        if res.get("source", {}).get("kind") not in ("simulation", "measurement"):
            raise SimulationError(
                f"{where}: result {i} source.kind must be simulation|measurement")
        if res["variable"] not in name_to_uid:
            raise SimulationError(
                f"{where}: result {i} unknown variable {res['variable']!r}")
        if res.get("simulation") != record_id:
            raise SimulationError(
                f"{where}: result {i} simulation backref "
                f"{str(res.get('simulation'))[:12]} does not equal the record id "
                f"{record_id[:12]}")


def _validate(record: dict, *, name_to_uid: dict, config_dir: Path, where: str,
              instances_dir: Path | None = None) -> str:
    """Validate a whole simulation record and return its (recomputed) id.

    Checks required top-level keys, recomputes and pins the id from the claim,
    then runs the execution, recipe-node, configuration, manifest, and results
    gates. ``instances_dir`` turns on slug resolution for results (the bundler
    passes it; the writer leaves it None, since a slug may name an instance
    that lands after the record does).
    """
    for key in ("recipe", "execution", "artifacts"):
        if key not in record:
            raise SimulationError(f"{where}: missing '{key}'")
    recipe = record["recipe"]
    execution = record["execution"]
    artifacts = record["artifacts"]

    _validate_manifest(artifacts, where=where)
    _validate_execution(execution, where=where)
    record_id = canonical_id(recipe, execution, artifacts)
    stated = record.get("id")
    if stated is not None and stated != record_id:
        raise SimulationError(
            f"{where}: stated id {str(stated)[:12]} does not match the id "
            f"recomputed from the claim {record_id[:12]} "
            f"(location must be out of the hash; put urls in 'mirrors')")

    _validate_recipe_node(recipe, name_to_uid, where=where)
    _validate_configuration(recipe, config_dir=config_dir, where=where)
    _validate_results(record.get("results"), record_id, name_to_uid, where=where,
                      instances_dir=instances_dir)
    return record_id


# --------------------------------------------------------------------------
# The record.
# --------------------------------------------------------------------------

def record_simulation(*, recipe, execution, artifacts, results=None, mirrors=None,
                      domains=None, sim_dir=None, name_to_uid=None):
    """Validate and write a simulation record to ``docs/data/simulations/``.

    Parameters
    ----------
    recipe : dict
        The asked computation: ``node`` (map id), optional ``node_uid`` pin,
        ``material`` ({name, optional configuration uid}), ``conditions``,
        ``params``.
    execution : dict
        What ran: ``code`` (codes rail; required, a non-empty string),
        ``code_version``, ``container_digest`` (the per-run image digest),
        ``runner``, ``wall_time_s``, ``seeds``.
    artifacts : list[dict]
        The manifest: each entry ``{path, bytes, sha256, role}``. Any ``url`` on
        an entry is dropped from the hashed claim (location is not identity) and
        preserved only if it is also declared in ``mirrors``.
    results : list | None
        The run's instances as backref slugs (strings) or inline stubs (dicts
        carrying ``simulation == <this record id>``). Outside the hashed claim.
        A slug is accepted bare here (its instance may land after the record
        does); the bundler resolves it against docs/data/instances/ and
        requires the instance to backref this record.
    mirrors : dict | None
        The mutable resolver layer, keyed by artifact path -> {url, ...} (or any
        location metadata). Outside the hashed claim: moving bytes never
        re-mints the id.
    domains : tuple | None
        Domains to resolve the recipe node and result variables against
        (default: the live map).
    sim_dir : Path | None
        Override the default docs/data/simulations directory (tests).
    name_to_uid : dict | None
        Precomputed node-id -> uid map (tests); built from ``domains`` if omitted.

    Returns
    -------
    Path
        The written record's path. Idempotent on identical content (the same
        path back); a different record for the same slug gets a numeric suffix
        rather than silently overwriting (the record_instance discipline).

    Raises
    ------
    SimulationError
        On any validation failure.
    """
    if name_to_uid is None:
        from omai.map_data import _domains, build_graph_dict
        doms = domains if domains is not None else _domains()
        name_to_uid = {n["id"]: n["uid"] for n in build_graph_dict(doms)["nodes"]}

    where = recipe.get("node", "<simulation>") if isinstance(recipe, dict) else "<simulation>"
    _validate_manifest(artifacts, where=where)
    record_id = canonical_id(recipe, execution, artifacts)

    record = {
        "id": record_id,
        "recipe": recipe,
        "execution": execution,
        # The manifest as stored: the hashed four keys, plus a url pulled from
        # mirrors when one is declared for that path (a convenience mirror of
        # the resolver layer; the hash never sees it).
        "artifacts": [_stored_artifact(a, mirrors) for a in artifacts],
    }
    if results is not None:
        record["results"] = results
    if mirrors is not None:
        record["mirrors"] = mirrors

    # Full validation on the assembled record (id pin, node pin, configuration,
    # results) before anything touches disk.
    _validate(record, name_to_uid=name_to_uid,
              config_dir=_CONFIG_DIR, where=where)

    sim_dir = Path(sim_dir) if sim_dir else _SIM_DIR
    sim_dir.mkdir(parents=True, exist_ok=True)
    # Filename = short id prefix + material/node slug, mirroring instances/.
    material = recipe.get("material") or {}
    label = material.get("name") if isinstance(material, dict) else None
    base = slugify(f"{record_id[:8]}-{label or ''}-{recipe.get('node', '')}") or record_id[:12]
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    path = sim_dir / f"{base}.json"
    n = 1
    while path.exists() and path.read_text() != payload:
        n += 1
        path = sim_dir / f"{base}-{n}.json"
    path.write_text(payload)
    return path


def _stored_artifact(art: dict, mirrors) -> dict:
    """The on-disk artifact row: the four hashed keys, plus a url mirrored from
    the resolver layer for that path when one is declared. The url is a
    convenience for a consumer reading the record; it is NOT part of identity
    (canonical_id ignores it) and its authority is the ``mirrors`` field.
    """
    row = _manifest_entry(art)
    if isinstance(mirrors, dict):
        loc = mirrors.get(art.get("path"))
        if isinstance(loc, dict) and "url" in loc:
            row["url"] = loc["url"]
        elif isinstance(loc, str):
            row["url"] = loc
    return row


def committed_ids(sim_dir: Path | None = None) -> set[str]:
    """The record ids of every committed simulation under docs/data/simulations/.

    The membership set for the instance-side backref gate: an instance whose
    ``simulation`` field names an id absent from this set cites a run the
    commons does not hold, and ``build_instances`` refuses it. An unreadable
    file contributes nothing (the bundler's own pass reports it).
    """
    sim_dir = Path(sim_dir) if sim_dir else _SIM_DIR
    ids: set[str] = set()
    if not sim_dir.exists():
        return ids
    for path in sorted(sim_dir.glob("*.json")):
        try:
            rec = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        rid = rec.get("id")
        if isinstance(rid, str):
            ids.add(rid)
    return ids


# --------------------------------------------------------------------------
# Import (the reciprocal of a host's export): a hosted bundle -> a record.
# --------------------------------------------------------------------------

# The map-recipe keys a bundle spec may carry. A spec that names them lifts
# them into the recipe (the asked computation); a spec that does not is kept
# verbatim under recipe.spec and its missing node is left for validation to
# report, never invented here.
_RECIPE_SPEC_KEYS = ("node", "node_uid", "material", "conditions", "params")


def _wall_time_s(started, finished):
    """Seconds between two ISO-8601 timestamps, or None when either is absent
    or unparseable. Derived, never guessed: a bundle whose timestamps do not
    parse simply carries no wall time rather than a fabricated one.
    """
    if not isinstance(started, str) or not isinstance(finished, str):
        return None
    from datetime import datetime
    try:
        a = datetime.fromisoformat(started)
        b = datetime.fromisoformat(finished)
    except ValueError:
        return None
    return (b - a).total_seconds()


def _recipe_from_bundle(manifest: dict) -> dict:
    """The asked computation, lifted from the bundle's template + spec.

    The bundle's ``template`` is the code family that ran; it is kept on the
    recipe as ``template`` and (below) mirrored into ``execution.code``. The
    ``spec`` is the input the host was given. If the spec names any map-recipe
    key (``node``, ``material``, ``conditions``, ``params``, or a ``node_uid``
    pin), those are lifted onto the recipe so validation can resolve the node
    against the live map; the spec itself is always kept under ``recipe.spec``
    so nothing the host asked is dropped. A spec that names NO node leaves
    ``recipe.node`` absent: the writer never invents a node id, and
    :func:`_validate` reports the gap (the honesty rule, a bundle without a
    resolvable map node is recorded but flagged).
    """
    template = manifest.get("template")
    spec = manifest.get("spec")
    recipe: dict = {"template": template, "spec": spec}
    if isinstance(spec, dict):
        for key in _RECIPE_SPEC_KEYS:
            if key in spec:
                recipe[key] = spec[key]
    return recipe


def _execution_from_bundle(manifest: dict) -> dict:
    """The "what ran" claim, mapped from the bundle's run metadata.

    ``code`` is the bundle's explicit ``code`` field when present, else its
    ``template`` (the code family a host run is filed under); a run necessarily
    ran some code, and :func:`_validate_execution` refuses a block that names
    none. The run's timing (``started_at``, ``finished_at``, ``current_stage``)
    is mapped straight onto the execution block; ``wall_time_s`` is derived from
    finished-minus-started only when both are parseable ISO timestamps, else
    omitted (never guessed). The platform ``kind`` rides along as provenance.
    """
    code = manifest.get("code") or manifest.get("template")
    execution: dict = {"code": code}
    for src, dst in (("started_at", "started_at"),
                     ("finished_at", "finished_at"),
                     ("current_stage", "current_stage"),
                     ("kind", "kind"),
                     ("code_version", "code_version"),
                     ("container_digest", "container_digest"),
                     ("runner", "runner")):
        if manifest.get(src) is not None:
            execution[dst] = manifest[src]
    wall = _wall_time_s(manifest.get("started_at"), manifest.get("finished_at"))
    if wall is not None:
        execution["wall_time_s"] = wall
    return execution


def _bundle_artifacts(manifest: dict, *, where: str) -> list[dict]:
    """The bundle's artifacts, each reduced to the hashed {path, bytes, sha256,
    role}. An entry missing ``sha256`` or ``role`` (an OLD MCG export, emitted
    before the companion PR that adds them) is REFUSED: the verifier will not
    mint a record with a null checksum it cannot ever check, so it names the
    missing field and tells the caller the host must emit sha256+role. This is
    exactly why the MCG export PR exists; an unverifiable bundle is an error,
    not a record.
    """
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise SimulationError(f"{where}: bundle 'artifacts' must be a list")
    out: list[dict] = []
    for i, art in enumerate(artifacts):
        if not isinstance(art, dict):
            raise SimulationError(f"{where}: bundle artifact {i} must be an object")
        if art.get("sha256") is None:
            raise SimulationError(
                f"{where}: bundle artifact {i} ({art.get('path')!r}) has no "
                f"'sha256'; the host must emit a sha256 for every artifact "
                f"(an unverifiable bundle cannot become a record). Re-export "
                f"with the sha256+role manifest.")
        if art.get("role") is None:
            raise SimulationError(
                f"{where}: bundle artifact {i} ({art.get('path')!r}) has no "
                f"'role'; the host must emit a role for every artifact "
                f"(result, trajectory, log, ...). Re-export with the "
                f"sha256+role manifest.")
        out.append(_manifest_entry(art))
    return out


def record_from_bundle(manifest: dict, *, mirrors: dict | None = None,
                       name_to_uid=None) -> dict:
    """Build a canonical SimulationRecord from a host bundle manifest.

    The reciprocal of a host's export: takes an MCG-style bundle manifest (keys
    ``name``, ``kind``, ``template``, ``spec``, ``outputs``, ``artifacts``,
    ``started_at``, ``finished_at``, ``current_stage``) and returns a record in
    the same shape :func:`record_simulation` produces, minting the same
    content-addressed id (:func:`canonical_id` over recipe + execution +
    artifacts-without-urls).

    The mapping (honest, never inventing what the bundle did not carry):

    - ``recipe`` comes from ``template`` + ``spec`` (:func:`_recipe_from_bundle`).
      If the spec names a map ``node`` (and optionally ``material``,
      ``conditions``, ``params``, a ``node_uid`` pin), those are lifted so the
      recipe resolves against the live map; the spec is always kept verbatim
      under ``recipe.spec``. A spec that names no node yields a record with
      ``recipe.node`` ABSENT, which :func:`_validate` reports rather than the
      writer guessing a node id.
    - ``execution`` comes from ``template`` (or an explicit ``code``) plus the
      run's ``started_at`` / ``finished_at`` / ``current_stage``;
      ``wall_time_s`` is derived only when both timestamps parse as ISO, else
      omitted (:func:`_execution_from_bundle`).
    - ``artifacts`` are the bundle's manifest entries, each passed through
      :func:`_manifest_entry` so only ``{path, bytes, sha256, role}`` enters the
      hash. A bundle artifact lacking ``sha256`` or ``role`` (an old export)
      raises :class:`SimulationError` naming the field: the verifier refuses an
      unverifiable bundle rather than record a null checksum.
    - ``mirrors`` (optional) is the resolver layer (where the bytes are hosted),
      stored OUTSIDE the hashed claim exactly like :func:`record_simulation`.
    - ``outputs`` (the bundle's headline result JSON) rides along as
      provenance OUTSIDE the hashed claim: it is what the run produced, not the
      recipe it was asked, so it never enters the recipe identity; and it is raw
      stage JSON, not a validated instance stub, so it is not filed under
      ``results`` (which the record reserves for backref slugs and instance
      stubs). ``name`` and ``kind`` likewise ride as provenance.

    Parameters
    ----------
    manifest : dict
        The host bundle manifest (the MCG export shape).
    mirrors : dict | None
        The optional resolver layer, keyed by artifact path -> {url, ...}.
        Outside the hashed claim: adding or moving a url never re-mints the id.
    name_to_uid : dict | None
        Precomputed node-id -> uid map (tests); built from the live map if
        omitted. Only consulted to attach a live ``node_uid`` pin when the spec
        named a node but no pin; NEVER used to invent a node the spec omitted.

    Returns
    -------
    dict
        The full record dict (``id``, ``recipe``, ``execution``, ``artifacts``,
        plus ``mirrors`` / ``outputs`` / ``name`` / ``kind`` when present), in
        the same shape :func:`record_simulation` writes.

    Raises
    ------
    SimulationError
        If a bundle artifact lacks a sha256 or a role (an unverifiable bundle).
    """
    if not isinstance(manifest, dict):
        raise SimulationError("bundle manifest must be an object")
    where = manifest.get("name") or manifest.get("template") or "<bundle>"

    recipe = _recipe_from_bundle(manifest)
    execution = _execution_from_bundle(manifest)
    artifacts = _bundle_artifacts(manifest, where=where)

    # Attach the live uid pin ONLY when the spec named a node but carried no
    # pin: pin what the map currently says, so a later validation is a real
    # match, never a silent pass. A spec that named no node stays unpinned and
    # unresolved on purpose (validation reports it).
    node = recipe.get("node")
    if isinstance(node, str) and recipe.get("node_uid") is None:
        if name_to_uid is None:
            from omai.map_data import _domains, build_graph_dict
            name_to_uid = {n["id"]: n["uid"]
                           for n in build_graph_dict(_domains())["nodes"]}
        if node in name_to_uid:
            recipe["node_uid"] = name_to_uid[node]

    record_id = canonical_id(recipe, execution, artifacts)
    record: dict = {
        "id": record_id,
        "recipe": recipe,
        "execution": execution,
        # The stored manifest: the four hashed keys, plus a url mirrored from
        # the resolver layer when one is declared (the hash never sees it).
        "artifacts": [_stored_artifact(a, mirrors) for a in artifacts],
    }
    if mirrors is not None:
        record["mirrors"] = mirrors
    # Provenance carried outside the hashed claim (like mirrors): what the run
    # produced and how the host labeled it, never part of the recipe identity.
    if manifest.get("outputs") is not None:
        record["outputs"] = manifest["outputs"]
    if manifest.get("name") is not None:
        record["name"] = manifest["name"]
    if manifest.get("kind") is not None:
        record["kind"] = manifest["kind"]
    return record


# --------------------------------------------------------------------------
# Verification (a dated report, NEVER a gate).
# --------------------------------------------------------------------------

def verify_simulation(record: dict, *, fetcher=None, today=None) -> dict:
    """A dated reachability/checksum report for a record's mirrors.

    For every artifact that has a resolvable url (in ``mirrors`` or mirrored on
    the artifact row), fetch it and compare the sha256 of the bytes to the
    manifest. Returns a report, never raises on a miss and never gates: a record
    whose bytes moved is STALE, not wrong.

    ``fetcher`` is a callable ``url -> bytes`` (injected; the tests and any
    offline caller pass a fake). When omitted, no network is attempted and every
    url-bearing artifact is reported ``unreachable`` with reason
    ``no fetcher``: the report still dates and enumerates, it just cannot check.

    Report shape::

        {"id": <record id>, "date": "YYYY-MM-DD", "checked": [
            {"path", "role", "url", "status", ...}, ...]}

    where ``status`` is ``ok`` (fetched, sha256 matches), ``mismatch`` (fetched,
    sha256 differs: reports expected/actual), ``unreachable`` (fetch failed or
    no url), or ``no-url`` (the artifact declares no location to check).
    """
    stamp = (today or date.today()).isoformat()
    artifacts = record.get("artifacts", []) or []
    mirrors = record.get("mirrors", {}) or {}
    checked: list[dict] = []
    for art in artifacts:
        path = art.get("path")
        role = art.get("role")
        loc = mirrors.get(path) if isinstance(mirrors, dict) else None
        url = None
        if isinstance(loc, dict):
            url = loc.get("url")
        elif isinstance(loc, str):
            url = loc
        if url is None:
            url = art.get("url")

        entry = {"path": path, "role": role, "url": url}
        if url is None:
            entry["status"] = "no-url"
            checked.append(entry)
            continue
        if fetcher is None:
            entry["status"] = "unreachable"
            entry["reason"] = "no fetcher"
            checked.append(entry)
            continue
        try:
            blob = fetcher(url)
        except Exception as exc:  # noqa: BLE001 - any fetch failure is unreachable, not raised
            entry["status"] = "unreachable"
            entry["reason"] = str(exc)
            checked.append(entry)
            continue
        actual = hashlib.sha256(blob).hexdigest()
        if actual == art.get("sha256"):
            entry["status"] = "ok"
        else:
            entry["status"] = "mismatch"
            entry["expected"] = art.get("sha256")
            entry["actual"] = actual
        checked.append(entry)
    return {"id": record.get("id"), "date": stamp, "checked": checked}


def verify_bundle_bytes(record: dict, artifact_dir=None, fetcher=None, *,
                        today=None) -> dict:
    """A dated byte-vs-checksum report for an imported record's artifacts.

    The import-side companion of :func:`verify_simulation`: where that reports
    the reachability of a record's mirrors, this checks each artifact's actual
    bytes against its manifest sha256 when the bytes are reachable. Same
    contract, verbatim: a REPORT, never a gate, and it NEVER raises on a
    mismatch or a miss. A record whose local bytes were tampered or whose
    hosted bytes moved is surfaced (``mismatch`` / ``unchecked``), never thrown.

    For each artifact, in order:

    - if ``artifact_dir`` is given and ``artifact_dir/path`` exists, the local
      file is hashed and compared: ``ok`` on match, ``mismatch`` on differ;
    - else if a ``fetcher`` (``url -> bytes``) is given and the record has a
      mirror url (or an on-row url) for that path, the bytes are fetched and
      compared (a fetch failure is ``unchecked``, reason the error);
    - else the artifact is ``unchecked`` with reason ``bytes not reachable``.

    ``artifact_dir`` wins over ``fetcher`` when both can reach a path: a local
    copy is the cheaper, authoritative check. Paths are joined POSIX-style under
    ``artifact_dir`` (the bundle stores bundle-relative paths, e.g.
    ``results/summary.json``), never escaping the directory.

    Report shape::

        {"id": <record id>, "date": "YYYY-MM-DD",
         "checked": [{"path", "role", "status", ...}, ...],
         "summary": {"ok": n, "mismatch": n, "unchecked": n}}

    where ``status`` is ``ok`` (bytes hash to the manifest sha256),
    ``mismatch`` (bytes differ: reports expected/actual), or ``unchecked``
    (bytes not reachable, or a fetch failed: reports a reason).
    """
    stamp = (today or date.today()).isoformat()
    artifacts = record.get("artifacts", []) or []
    mirrors = record.get("mirrors", {}) or {}
    base = Path(artifact_dir) if artifact_dir is not None else None
    checked: list[dict] = []
    summary = {"ok": 0, "mismatch": 0, "unchecked": 0}
    for art in artifacts:
        path = art.get("path")
        role = art.get("role")
        expected = art.get("sha256")
        entry = {"path": path, "role": role}

        blob = None
        source = None
        # 1) Local file under artifact_dir wins: cheapest, authoritative.
        if base is not None and isinstance(path, str):
            local = base / path
            if local.is_file():
                try:
                    blob = local.read_bytes()
                    source = "local"
                except OSError as exc:
                    entry["status"] = "unchecked"
                    entry["reason"] = f"local read failed: {exc}"
                    summary["unchecked"] += 1
                    checked.append(entry)
                    continue
        # 2) Else fetch the mirror url, if a fetcher and a url are both present.
        if blob is None and fetcher is not None:
            loc = mirrors.get(path) if isinstance(mirrors, dict) else None
            url = None
            if isinstance(loc, dict):
                url = loc.get("url")
            elif isinstance(loc, str):
                url = loc
            if url is None:
                url = art.get("url")
            if url is not None:
                try:
                    blob = fetcher(url)
                    source = url
                except Exception as exc:  # noqa: BLE001 - a fetch miss is unchecked, not raised
                    entry["status"] = "unchecked"
                    entry["reason"] = f"fetch failed: {exc}"
                    summary["unchecked"] += 1
                    checked.append(entry)
                    continue

        if blob is None:
            entry["status"] = "unchecked"
            entry["reason"] = "bytes not reachable"
            summary["unchecked"] += 1
            checked.append(entry)
            continue

        entry["source"] = source
        actual = hashlib.sha256(blob).hexdigest()
        if actual == expected:
            entry["status"] = "ok"
            summary["ok"] += 1
        else:
            entry["status"] = "mismatch"
            entry["expected"] = expected
            entry["actual"] = actual
            summary["mismatch"] += 1
        checked.append(entry)
    return {"id": record.get("id"), "date": stamp, "checked": checked,
            "summary": summary}
