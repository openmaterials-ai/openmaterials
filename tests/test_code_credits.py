"""Enforcement: every code rail on the map is cited and licensed.

Giuseppe's rule: every code we represent must carry a citation (paper / DOI)
and its license. This test is the "remember" mechanism. It discovers every
rail actually present on the map (every representation_name that build_codes
emits) and fails if any rail lacks a CODE_CREDITS entry, has an empty citation
or license, or carries license "UNKNOWN" without an explicit waiver below.
A future rail therefore cannot land uncredited: adding an adapter without a
credits entry breaks this test.
"""

from omai.map_data import DOMAINS, build_codes
from omai.representation.credits import CODE_CREDITS, PER_NODE_CREDITS

# Rails permitted to carry an UNKNOWN license, each with a written reason.
# Empty today: honest UNKNOWN is allowed, but only with a recorded justification.
ALLOWED_UNKNOWN: dict[str, str] = {
    # "some-rail": "reason the license genuinely cannot be determined",
}


def _rails() -> set[str]:
    return set(build_codes(DOMAINS).keys())


def test_every_rail_has_a_credits_entry():
    missing = sorted(_rails() - set(CODE_CREDITS))
    assert not missing, (
        f"code rails on the map with no CODE_CREDITS entry: {missing}. "
        "Every code we represent must be cited and licensed "
        "(omai/representation/credits.py)."
    )


def test_citation_and_license_non_empty():
    problems = []
    for rail in sorted(_rails()):
        cr = CODE_CREDITS.get(rail)
        if cr is None:
            continue  # covered by test_every_rail_has_a_credits_entry
        if not (cr.get("citation") or "").strip():
            problems.append(f"{rail}: empty citation")
        if not (cr.get("license") or "").strip():
            problems.append(f"{rail}: empty license")
    assert not problems, "; ".join(problems)


def test_license_not_unknown_unless_waived():
    offenders = []
    for rail in sorted(_rails()):
        cr = CODE_CREDITS.get(rail)
        if cr is None:
            continue
        if cr.get("license") == "UNKNOWN" and rail not in ALLOWED_UNKNOWN:
            offenders.append(rail)
    assert not offenders, (
        f"rails with UNKNOWN license and no ALLOWED_UNKNOWN waiver: {offenders}"
    )


def test_credits_flow_into_codes_json():
    codes = build_codes(DOMAINS)
    for rail, spaces in codes.items():
        for space, entry in spaces.items():
            cr = PER_NODE_CREDITS.get((rail, space), CODE_CREDITS[rail])
            assert entry["license"] == cr["license"], (rail, space)
            assert entry["citation"] == cr["citation"], (rail, space)
            assert entry["license"] != "UNKNOWN", (rail, space)


def test_license_source_recorded():
    # The sourcing bar: every license must say where it was read.
    for rail, cr in CODE_CREDITS.items():
        assert (cr.get("license_source") or "").strip(), rail


def test_per_node_overrides_point_at_real_rails():
    """An override must name a (rail, node) pair actually on the map, and
    meet the same completeness bar as a code-level credit. A stale override
    (the rail moved or the node renamed) is a bug, not dead weight."""
    codes = build_codes(DOMAINS)
    problems = []
    for (rail, node), cr in PER_NODE_CREDITS.items():
        if rail not in codes:
            problems.append(f"({rail}, {node}): rail not on the map")
            continue
        if node not in codes[rail]:
            problems.append(f"({rail}, {node}): node not served by this rail")
        if not (cr.get("citation") or "").strip():
            problems.append(f"({rail}, {node}): empty citation")
        if not (cr.get("license") or "").strip():
            problems.append(f"({rail}, {node}): empty license")
        if not (cr.get("license_source") or "").strip():
            problems.append(f"({rail}, {node}): empty license_source")
    assert not problems, "; ".join(problems)


def test_overrides_reach_the_emitted_data():
    """build_codes must actually apply the per-node override: the emitted
    entry carries the override's citation, doi, license, and url, not the
    code-level ones."""
    codes = build_codes(DOMAINS)
    for (rail, node), cr in PER_NODE_CREDITS.items():
        entry = codes.get(rail, {}).get(node)
        assert entry is not None, (rail, node)
        for field in ("citation", "doi", "license", "url"):
            assert entry[field] == cr.get(field), (
                f"({rail}, {node}) field {field} does not carry the override")


def test_mcg_method_rails_cite_their_methods():
    """The rails that run GFN2-xTB cite it; the composite rails keep the
    effective-medium papers. One code, honestly different methods."""
    codes = build_codes(DOMAINS)
    mcg = codes["materialscodegraph"]
    assert "GFN2-xTB" in mcg["MolarHeatCapacity"]["citation"]
    assert "GFN2-xTB" in mcg["ReactionEnergy"]["citation"]
    assert "10.1021/acs.jctc.8b01176" == mcg["ReactionEnergy"]["doi"]
    for node, e in mcg.items():
        if node in ("MolarHeatCapacity", "ReactionEnergy"):
            continue
        assert "Nan" in e["citation"], node
