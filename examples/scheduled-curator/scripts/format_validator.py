#!/usr/bin/env python3
"""
Deterministic post-draft formatter and validator.

Dispatched directly by the publish stage (§3 Scripts vehicle). No model judgment
during execution: same input, same output, same exit code.

Usage:
    python3 format_validator.py --in <draft.md> --out <draft.formatted.md>

Exit code 0: the input satisfies the format rules declared below and the output
            file has been written in canonical form.
Exit code 1: the input violates a format rule. A human-readable diagnostic is
            printed to stderr. The orchestrator's post-check treats non-zero
            exit as a signal failure (§5 corollary (c)).

Format rules checked (representative, not exhaustive; real pipelines would
tailor this to the release domain):

- Line 1 is a level-1 heading: "# <item_id>".
- Lines 2-3 contain "**Category:** <value>" then a blank line.
- Body is at least one non-blank paragraph.
- The file ends with a "**Sources:**" section with at least one bullet.
- No trailing whitespace on any line.
- Trailing newline at end of file.
"""

import argparse
import re
import sys
from pathlib import Path


HEADING_RE = re.compile(r"^# [A-Za-z0-9_\-]+$")
CATEGORY_RE = re.compile(r"^\*\*Category:\*\* \S.*$")
SOURCES_HEADER = "**Sources:**"


def fail(message: str) -> None:
    print(f"format_validator: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="inp", required=True)
    parser.add_argument("--out", dest="outp", required=True)
    args = parser.parse_args()

    src = Path(args.inp)
    if not src.exists():
        fail(f"input file not found: {src}")

    lines = src.read_text(encoding="utf-8").splitlines()
    if len(lines) < 6:
        fail(f"input too short: {len(lines)} lines (need at least 6)")

    if not HEADING_RE.match(lines[0]):
        fail(f"line 1 is not a valid heading: {lines[0]!r}")

    if not CATEGORY_RE.match(lines[1]):
        fail(f"line 2 is not a valid Category line: {lines[1]!r}")

    if lines[2].strip() != "":
        fail(f"line 3 must be blank: {lines[2]!r}")

    try:
        sources_idx = next(i for i, ln in enumerate(lines) if ln.strip() == SOURCES_HEADER)
    except StopIteration:
        fail("missing **Sources:** section")

    body = lines[3:sources_idx]
    if not any(ln.strip() for ln in body):
        fail("body is empty between Category and Sources")

    source_bullets = [ln for ln in lines[sources_idx + 1:] if ln.strip().startswith("- ")]
    if not source_bullets:
        fail("Sources section has no bullet entries")

    for i, ln in enumerate(lines, start=1):
        if ln != ln.rstrip():
            fail(f"trailing whitespace on line {i}")

    canonical = "\n".join(lines) + "\n"
    Path(args.outp).write_text(canonical, encoding="utf-8")
    sys.exit(0)


if __name__ == "__main__":
    main()
