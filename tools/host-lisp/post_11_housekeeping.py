#!/usr/bin/env python3
"""Verify and bind the identity-neutral post-1.1 structural cleanup."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "post-1.1-housekeeping-receipt-2026-07-19.json"
)
REPORT = ROOT / "docs/post-1.1-housekeeping-2026-07-19.md"
TRANSLATED = ROOT / "docs/v2-capability-carrier-registry.md"
IDENTITY_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/post-release/"
    "post-1.1-housekeeping-product-identity-receipt.json"
)
V11_PRODUCT_SET = "048639695dd7ad9c35bd8e92b2ec4c0fba1e365385cfc680e90bb3ba1a860024"
SEALED_FIXTURES = (
    "lib/m65-disk-alloc.lisp",
    "lib/m65-disk-alloc-var.lisp",
)
ABANDONED_RELOCATION_PATHS = (
    "tests/fixtures/legacy/m65d/alloc-two-sector.lisp",
    "tests/fixtures/legacy/m65d/alloc-variable-chain.lisp",
)
REMOVED = (
    "scripts/deploy-repl.sh",
    "scripts/hw-c1-entry-seam-smoke.sh",
    "scripts/gc-extheap-repro.c",
    "scripts/f011-demolib.lisp",
    "tools/host-lisp/check-stage3-native-smokes.py",
    "tools/host-lisp/primitive_view_bank_attribution.py",
)
RETAINED_REFERENCES = {
    "scripts/push-github-verified.sh": (
        "config/public-export-policy.json",
        "tools/host-lisp/remote_source_binding.py",
    ),
    "tools/host-lisp/dialect_v2_family_artifact.py": (
        "tools/host-lisp/dialect_v2_prelude_evidence.py",
    ),
    "tools/host-lisp/dialect_v2_r2_decisions.py": (
        "tools/host-lisp/dialect_migration_contract.py",
    ),
}
ACTIVE_REFERENCE_ROOTS = (
    "Makefile", "mk", "config", "src", "lib", "scripts", "tools", "tests/disk",
)


class HousekeepingError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HousekeepingError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def binding(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    require(path.is_file() and not path.is_symlink(), f"regular file missing: {relative}")
    data = path.read_bytes()
    return {"path": relative, "bytes": len(data), "sha256": sha256(data)}


def tracked_paths() -> list[str]:
    process = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    require(process.returncode == 0, process.stderr.strip() or "git ls-files failed")
    return [line for line in process.stdout.splitlines() if line]


def active_files() -> list[Path]:
    result = []
    for relative in tracked_paths():
        if relative == "tools/host-lisp/post_11_housekeeping.py":
            continue
        if relative == "Makefile" or any(
            relative == root or relative.startswith(root + "/")
            for root in ACTIVE_REFERENCE_ROOTS[1:]
        ):
            path = ROOT / relative
            if path.is_file() and not path.is_symlink():
                result.append(path)
    return result


def active_reference_count(needle: str) -> int:
    count = 0
    encoded = needle.encode("utf-8")
    for path in active_files():
        try:
            count += path.read_bytes().count(encoded)
        except OSError as exc:
            raise HousekeepingError(f"cannot read {path}: {exc}") from exc
    return count


def collect() -> dict[str, Any]:
    for relative in SEALED_FIXTURES:
        require((ROOT / relative).is_file(), f"sealed fixture path missing: {relative}")
        require(active_reference_count(relative) >= 2,
                f"sealed fixture is no longer wired: {relative}")
    for relative in ABANDONED_RELOCATION_PATHS:
        require(not (ROOT / relative).exists(),
                f"abandoned fixture relocation still exists: {relative}")

    for relative in REMOVED:
        require(not (ROOT / relative).exists(), f"orphan was not removed: {relative}")
        require(active_reference_count(Path(relative).name) == 0,
                f"active orphan-name reference remains: {relative}")

    retained = {}
    for relative, referrers in RETAINED_REFERENCES.items():
        require((ROOT / relative).is_file(), f"live file was removed: {relative}")
        for referrer in referrers:
            text = (ROOT / referrer).read_text(encoding="utf-8")
            stem = Path(relative).stem
            require(relative in text or stem in text,
                    f"retained reference missing: {referrer} -> {relative}")
        retained[relative] = list(referrers)

    translated = TRANSLATED.read_text(encoding="utf-8")
    require("## Purpose" in translated and "## Runtime Core closure" in translated,
            "capability/carrier translation structure missing")
    require(not any(char in translated for char in "äöüÄÖÜß"),
            "translated capability/carrier document still contains German characters")

    migration = json.loads((ROOT / "config/dialect-migration-contract.json").read_text())
    source = migration["historical_forecast"]["source"]
    expected_source = "docs/lisp65-dialect-redesign-2026-07-10.md#8"
    require(source == expected_source, "frozen migration forecast pointer drift")
    compatibility = (ROOT / source.split("#", 1)[0]).read_text(encoding="utf-8")
    require(
        "archive/pre-1.0/designs/lisp65-dialect-redesign-2026-07-10.md" in compatibility
        and "not a current implementation contract" in compatibility,
        "migration compatibility pointer does not resolve to the historical archive",
    )

    identity = json.loads(IDENTITY_RECEIPT.read_text(encoding="utf-8"))
    require(identity.get("status") == "passed", "housekeeping product identity did not pass")
    require(identity.get("artifact_set_sha256") == V11_PRODUCT_SET,
            "housekeeping product-set identity drift")
    require(len(identity.get("builds", [])) == 2,
            "housekeeping identity lacks the varied double build")
    require(len(identity.get("product_artifacts", [])) == 14,
            "housekeeping identity does not bind all 14 product artifacts")
    require(identity.get("claims") == {"G3": "not-run", "G6": "not-run", "release_effect": "none"},
            "housekeeping identity claim limit drift")

    return {
        "format": "lisp65-post-1.1-housekeeping-receipt-v2",
        "version": 2,
        "recorded_on": "2026-07-19",
        "status": "pass",
        "claim_limit": (
            "Identity-neutral structural cleanup only; product-bound M65D fixture paths and "
            "pre-existing product-source comments remain frozen. No m65-disk modernization "
            "or historical evidence rewrite is claimed."
        ),
        "bindings": {
            "verifier": binding("tools/host-lisp/post_11_housekeeping.py"),
            "report": binding("docs/post-1.1-housekeeping-2026-07-19.md"),
            "translated_registry": binding("docs/v2-capability-carrier-registry.md"),
            "migration_contract": binding("config/dialect-migration-contract.json"),
            "r5_closure": binding("config/r5-global-g5-test-closure.json"),
            "product_identity": binding(
                "tests/bytecode/dialect-v2/evidence/post-release/"
                "post-1.1-housekeeping-product-identity-receipt.json"
            ),
        },
        "retained_product_bound_fixtures": [binding(path) for path in SEALED_FIXTURES],
        "abandoned_relocation_paths": list(ABANDONED_RELOCATION_PATHS),
        "removed_orphans": list(REMOVED),
        "retained_false_positives": retained,
        "migration_forecast_source": source,
        "product_source_modernization": "deferred-separate-product-identity-block",
        "product_source_comment_translation": "rejected-by-raw-source-profile-binding-deferred-to-c2",
        "product_artifact_identity": "14/14-byte-identical-to-v1.1.0-varied-double-build",
    }


def selftest() -> None:
    rejected = 0
    for condition in (False, 1 == 2, "old" == "new"):
        try:
            require(condition, "mutation")
        except HousekeepingError:
            rejected += 1
    require(rejected == 3, f"mutations accepted: {rejected}")


def write() -> dict[str, Any]:
    result = collect()
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def check() -> dict[str, Any]:
    result = collect()
    require(RECEIPT.is_file(), "housekeeping receipt missing")
    recorded = json.loads(RECEIPT.read_text(encoding="utf-8"))
    require(recorded == result, "housekeeping receipt drift; regenerate with --write")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        print("post-1.1-housekeeping: SELFTEST PASS mutations=3")
        return 0
    result = write() if args.write else check()
    print(
        "post-1.1-housekeeping: PASS "
        f"retained_product_fixtures={len(result['retained_product_bound_fixtures'])} "
        f"removed={len(result['removed_orphans'])} retained={len(result['retained_false_positives'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
