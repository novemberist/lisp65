#!/usr/bin/env python3
"""Build the host-only v1.11 compiler-locality candidate carrier."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_product_compiler_tier as BASE  # noqa: E402


FORMAT = "lisp65-c2-v111-compiler-locality-tier-generator-v1"
CANDIDATE_SOURCE = "lib/dialect-v2/lcc-locality-candidate.lisp"
PRIVATE_INLINE = (
    "%lcc-emit-local",
    "%lcc-st",
    "%lcc-lits",
    "%lcc-max",
    "%lcc-v2-nargs",
    "%lcc-v2-optional",
    "%lcc-v2-rest",
    "%lcc-rev",
    "%lcc-v2-max0",
    "%lcc-v2-param-p",
)


class CandidateTierError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _equivalence_cases() -> list[dict[str, str]]:
    return [
        {
            "name": "carrier-local-emit-equivalence-empty",
            "expr": (
                "(%lcc-equal "
                "(%lcc-emit (%lcc-cs (cons nil 0) nil 0 nil) 42) "
                "(%lcc-emit-local (%lcc-cs (cons nil 0) nil 0 nil) 42))"
            ),
            "expect": "t",
        },
        {
            "name": "carrier-local-emit-equivalence-nonempty",
            "expr": (
                "(%lcc-equal "
                "(%lcc-emit (%lcc-cs (cons (cons 1 nil) 1) nil 3 nil) 42) "
                "(%lcc-emit-local "
                "(%lcc-cs (cons (cons 1 nil) 1) nil 3 nil) 42))"
            ),
            "expect": "t",
        },
        {
            "name": "carrier-local-emit-equivalence-full-state",
            "expr": (
                "(%lcc-equal "
                "(%lcc-emit (%lcc-cs (cons (cons 1 (cons 2 nil)) 2) "
                "(cons 7 nil) 5 nil) 42) "
                "(%lcc-emit-local "
                "(%lcc-cs (cons (cons 1 (cons 2 nil)) 2) "
                "(cons 7 nil) 5 nil) 42))"
            ),
            "expect": "t",
        },
    ]


def generate(out: Path) -> dict:
    """Reuse the product generator without changing its live source inputs."""
    original_sources = BASE.SOURCES
    try:
        BASE.SOURCES = (*original_sources, CANDIDATE_SOURCE)
        report = BASE.generate(out)
    finally:
        BASE.SOURCES = original_sources

    suite = json.loads(out.read_text(encoding="utf-8"))
    suite["name"] = "c2-v111-compiler-locality-candidate"
    suite["description"] = (
        "Host-only v1.11 compiler-locality candidate; delivery remains behind "
        "the next ordinary release block."
    )
    suite["private_inline_functions"] = list(PRIVATE_INLINE)
    suite["min_private_inline_functions"] = len(PRIVATE_INLINE)
    suite["cases"].extend(_equivalence_cases())
    data = _canonical(suite)
    out.write_bytes(data)

    report["format"] = FORMAT
    report["candidate_overlay"] = CANDIDATE_SOURCE
    report["base_generator"] = "tools/host-lisp/c2_product_compiler_tier.py"
    report["private_inline_functions"] = list(PRIVATE_INLINE)
    report["outputs"][-1] = {
        "path": out.resolve().relative_to(ROOT.resolve()).as_posix(),
        "sha256": _sha(data),
    }
    return report


def selftest() -> None:
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v111-tier-", dir=ROOT / "build") as raw:
        out = Path(raw) / "suite.json"
        first = generate(out)
        first_files = {
            path.relative_to(Path(raw)).as_posix(): _sha(path.read_bytes())
            for path in Path(raw).rglob("*") if path.is_file()
        }
        second = generate(out)
        second_files = {
            path.relative_to(Path(raw)).as_posix(): _sha(path.read_bytes())
            for path in Path(raw).rglob("*") if path.is_file()
        }
        if first != second or first_files != second_files:
            raise CandidateTierError("candidate tier generation is not deterministic")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=(
        ROOT / "build/post-promotion/v111/candidate/compiler-tier/suite.json"
    ))
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
            print("c2-v111-compiler-tier: SELFTEST PASS")
            return 0
        report = generate(args.out)
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_bytes(_canonical(report))
    except (CandidateTierError, BASE.C2CompilerTierError, OSError, ValueError) as error:
        print(f"c2-v111-compiler-tier: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "c2-v111-compiler-tier: PASS "
        f"functions={report['functions']} suite={report['suite']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
