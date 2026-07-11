"""CLI: python -m omai.paper_parser <pdf> [--apply --yes].

Default: run the pipeline and write a proposal file. --apply (only together with
--yes, after a human has reviewed the proposal) writes instances via the
record_instance bridge. The key is never printed; any error is redacted before
it reaches the terminal.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import run_pipeline
from .env import redact_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m omai.paper_parser",
        description="Parse a paper PDF into gated evidence proposals.")
    parser.add_argument("pdf", help="Path to the paper PDF.")
    parser.add_argument("--apply", action="store_true",
                        help="Write instances (requires --yes and human review).")
    parser.add_argument("--yes", action="store_true",
                        help="Confirm --apply; without it, --apply is refused.")
    parser.add_argument("--source-kind", default="measurement",
                        choices=["measurement", "simulation"],
                        help="source.kind for applied instances.")
    parser.add_argument("--map-version", default=None,
                        help="Map version to pin the proposal to.")
    parser.add_argument("--detect-passes", type=int, default=3,
                        help="Number of independent DETECT passes to union "
                             "(ensemble size; default 3).")
    args = parser.parse_args(argv)

    try:
        result = run_pipeline(args.pdf, map_version=args.map_version,
                              detect_passes=args.detect_passes)
    except Exception as exc:  # redact any key that leaked into the message
        print(redact_key(f"error: {exc}"), file=sys.stderr)
        return 1

    k = result.stage_kills
    ens = result.proposal.get("ensemble", {})
    print(f"proposal: {result.proposal_path}")
    print(f"ensemble: detect_passes={ens.get('detect_passes')} "
          f"per_pass_claim_counts={ens.get('per_pass_claim_counts')}")
    print(f"detected={k['detected']} survived_validation={k['survived_validation']} "
          f"duplicates={k['duplicates_flagged']} unmapped={k['unmapped']} "
          f"quote_killed={k['quote_killed']} review_killed={k['review_killed']}")
    print(f"tokens: {result.usage.as_dict()} "
          f"est_usd={result.usage.cost_estimate_usd()} "
          f"cache_read={result.cache_read_input_tokens}")

    if args.apply:
        if not args.yes:
            print("refusing --apply without --yes (human review required)",
                  file=sys.stderr)
            return 2
        from .propose import apply_proposal
        written = apply_proposal(result.proposal, source_kind=args.source_kind)
        print(f"applied {len(written)} instances")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
