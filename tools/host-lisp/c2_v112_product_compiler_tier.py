#!/usr/bin/env python3
"""Materialize the v1.4 product compiler tier with the promoted locality overlay."""

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

import c2_v111_compiler_tier as V111  # noqa: E402


FORMAT = "lisp65-c2-v112-product-compiler-tier-generator-v1"
PROMOTED_SOURCE = "lib/dialect-v2/lcc-locality.lisp"


class ProductTierError(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def normalized_overlay(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith(";"))


def generate(out: Path) -> dict:
    candidate = ROOT / V111.CANDIDATE_SOURCE
    promoted = ROOT / PROMOTED_SOURCE
    if normalized_overlay(candidate) != normalized_overlay(promoted):
        raise ProductTierError("promoted locality forms differ from the accepted candidate")
    original = V111.CANDIDATE_SOURCE
    try:
        V111.CANDIDATE_SOURCE = PROMOTED_SOURCE
        report = V111.generate(out)
    finally:
        V111.CANDIDATE_SOURCE = original
    suite = json.loads(out.read_text(encoding="utf-8"))
    suite["name"] = "c2-v112-product-compiler-tier"
    suite["description"] = (
        "v1.4 product compiler tier: complete live profile plus the promoted "
        "v1.11 locality overlay; born-code semantics remain carrier-equivalent."
    )
    raw = canonical(suite)
    out.write_bytes(raw)
    report.update({
        "format": FORMAT,
        "accepted_candidate_overlay": V111.CANDIDATE_SOURCE,
        "promoted_overlay": PROMOTED_SOURCE,
        "normalized_overlay_sha256": sha(normalized_overlay(promoted).encode("utf-8")),
    })
    report["outputs"][-1] = {
        "path": out.resolve().relative_to(ROOT.resolve()).as_posix(),
        "sha256": sha(raw),
    }
    return report


def selftest() -> None:
    (ROOT / "build").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v112-tier-", dir=ROOT / "build") as raw:
        out = Path(raw) / "suite.json"
        first = generate(out)
        first_files = {
            path.relative_to(Path(raw)).as_posix(): sha(path.read_bytes())
            for path in Path(raw).rglob("*") if path.is_file()
        }
        second = generate(out)
        second_files = {
            path.relative_to(Path(raw)).as_posix(): sha(path.read_bytes())
            for path in Path(raw).rglob("*") if path.is_file()
        }
        if first != second or first_files != second_files:
            raise ProductTierError("v1.4 compiler tier generation is not deterministic")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=(
        ROOT / "build/post-promotion/v112/compiler-tier/suite.json"
    ))
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    try:
        if args.selftest:
            selftest()
            print("c2-v112-product-compiler-tier: SELFTEST PASS")
            return 0
        report = generate(args.out)
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_bytes(canonical(report))
    except (ProductTierError, V111.CandidateTierError, OSError, ValueError) as error:
        print(f"c2-v112-product-compiler-tier: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "c2-v112-product-compiler-tier: PASS "
        f"functions={report['functions']} suite={report['suite']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
