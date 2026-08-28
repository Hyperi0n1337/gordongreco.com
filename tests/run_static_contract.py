#!/usr/bin/env python3
"""Run the stdlib-only website contract without requiring pytest at build time."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import test_site_static as contract  # noqa: E402


def main() -> int:
    tests = [
        (name, fn)
        for name, fn in inspect.getmembers(contract, inspect.isfunction)
        if name.startswith("test_")
    ]
    failures: list[tuple[str, BaseException]] = []
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except BaseException as exc:  # preserve assertion context in build logs
            failures.append((name, exc))
            print(f"FAIL {name}: {exc}", file=sys.stderr)
    print(f"Static contract: {len(tests) - len(failures)}/{len(tests)} passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
