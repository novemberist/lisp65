#!/usr/bin/env python3
"""Pack-independent verifier for global dialect-v2 Workbench G5 receipts.

The verifier deliberately knows nothing about the internal CP5 candidate.  A
native receipt is accepted only when it binds the sealed R4 product identity,
the global candidate manifest, the requested case/cycle and every raw input.
Semantic checks are reconstructed from the raw logs and D81 images.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
RECEIPT_FORMAT = "lisp65-dialect-v2-workbench-native-receipt-v1"
NEGATIVE_FORMAT = "lisp65-dialect-v2-workbench-verifier-negative-proof-v1"

EXPECTED = {
    "workbench-persistence": {
        "bam-alloc": ("r5-global-g5-workbench-bam-alloc", "pass"),
        "bam-read": ("r5-global-g5-workbench-bam-read", "pass"),
        "chain-write": ("r5-global-g5-workbench-chain-write", "pass"),
        "dir-write": ("r5-global-g5-workbench-dir-write", "pass"),
        "save-new": ("r5-global-g5-workbench-save-new", "pass"),
        "save-new-scan": ("r5-global-g5-workbench-save-new-scan", "pass"),
        "save-new-var": ("r5-global-g5-workbench-save-new-var", "pass"),
    },
    "workbench-ux": {
        "overlay-stack-guard": ("r5-global-g5-workbench-overlay-stack-guard", "pass"),
        "stdlib-runtime": ("r5-global-g5-workbench-stdlib-runtime", "pass"),
        "ux-complete": ("r5-global-g5-workbench-ux-complete", "pass"),
    },
}

EVIDENCE = {
    # BAM bytes are derived from the exact SHA-bound test medium.  A literal
    # free-count would silently bind this case to a historical D81 layout.
    "bam-read": {"media-d81": None, "sector-1": None, "sector-2": None},
    "bam-alloc": {"before-d81": None, "after-d81": None, "marker": "bam alloc pass 4/4"},
    "chain-write": {
        "before-d81": None, "after-d81": None,
        "marker": "chain write pass 7/7", "run": "737",
    },
    "dir-write": {
        "before-d81": None, "after-d81": None,
        "marker": "dir write pass 11/11", "run": "767",
    },
    "save-new": {
        "before-d81": None, "after-d81": None,
        "marker": "save new pass 5/5", "run": "797",
    },
    "save-new-scan": {
        "before-d81": None, "after-d81": None,
        "marker": "save new pass 5/5", "run": "797",
    },
    "save-new-var": {
        "before-d81": None, "after-d81": None,
        "marker": "save new pass 5/5", "run": "907",
    },
    "overlay-stack-guard": {"ship-receipt": None, "arith": "42", "reader-recovery": "42"},
    "stdlib-runtime": {"result": "42"},
    "ux-complete": {
        "persistence": "((\"(defun ap6-persisted () 612)\") 612 (\"(defun ap6-b () 613)\") 613)",
        "some": "3", "every": "t", "mx-eval-buffer": "42",
    },
}


class VerifyError(RuntimeError):
    pass


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise VerifyError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise VerifyError(f"{label} must be a regular non-symlink file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerifyError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerifyError(f"{label} must be an object")
    return value


def exact(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise VerifyError(f"{label} keys drift: {actual}")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def lower_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise VerifyError(f"{label} must be a lowercase SHA-256")
    return value


def evidence_file(receipt: Path, value: Any, digest: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise VerifyError(f"{label}.path must be receipt-relative")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        raise VerifyError(f"{label}.path escapes the receipt directory")
    path = (receipt.parent / Path(*pure.parts)).resolve()
    try:
        path.relative_to(receipt.parent.resolve())
    except ValueError as exc:
        raise VerifyError(f"{label}.path escapes the receipt directory") from exc
    if path.is_symlink() or not path.is_file():
        raise VerifyError(f"{label} is not a regular file")
    if sha(path) != lower_sha(digest, f"{label}.sha256"):
        raise VerifyError(f"{label} SHA binding drift")
    return path


def verify_attempts(value: Any, case_id: str) -> None:
    if not isinstance(value, list) or len(value) not in (1, 2):
        raise VerifyError(f"{case_id} must record one or two attempts")
    for index, raw in enumerate(value, 1):
        attempt = exact(
            raw,
            {
                "index", "outcome", "semantic_execution", "media_content_mutation",
                "evidence_directory", "throwaway_media",
            },
            f"{case_id} attempt {index}",
        )
        if attempt["index"] != index or not isinstance(attempt["evidence_directory"], str):
            raise VerifyError(f"{case_id} attempt numbering/evidence drift")
    if len(value) == 1:
        if value[0]["outcome"] != "pass" or value[0]["semantic_execution"] is not True:
            raise VerifyError(f"{case_id} single attempt is not a semantic pass")
        return
    first, second = value
    if first != {
        "index": 1,
        "outcome": "transport-failure-before-semantic-execution",
        "semantic_execution": False,
        "media_content_mutation": False,
        "evidence_directory": first["evidence_directory"],
        "throwaway_media": True,
    }:
        raise VerifyError(f"{case_id} retry exceeds transport-only policy")
    if (
        second["outcome"] != "pass"
        or second["semantic_execution"] is not True
        or second["evidence_directory"] == first["evidence_directory"]
        or second["throwaway_media"] is not True
    ):
        raise VerifyError(f"{case_id} retry did not use fresh passing evidence/media")


def run_oracle(command: list[str], label: str) -> None:
    completed = subprocess.run(
        command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise VerifyError(f"{label} failed: {detail}")


def bam_read_oracles(path: Path) -> dict[str, str]:
    data = path.read_bytes()
    expected_size = 80 * 40 * 256
    if len(data) != expected_size:
        raise VerifyError(f"BAM-read medium size {len(data)} != {expected_size}")

    def byte(sector: int, offset: int) -> int:
        base = (((40 - 1) * 40) + sector) * 256
        return data[base + offset]

    return {
        "sector-1": f"(t {byte(1, 0)} {byte(1, 1)} {byte(1, 16)} {byte(1, 250)})",
        "sector-2": f"(t {byte(2, 0)} {byte(2, 1)} {byte(2, 16)} {byte(2, 40)})",
    }


def verify_bam_read(files: dict[str, Path], expected_media_sha256: str | None) -> None:
    media = files["media-d81"]
    if expected_media_sha256 is not None and sha(media) != lower_sha(
        expected_media_sha256, "Workbench test-medium SHA"
    ):
        raise VerifyError("BAM-read medium is outside the candidate test closure")
    run_oracle(
        [sys.executable, "tools/host-lisp/d81_bam_sanity.py", str(media)],
        "BAM-read source-medium sanity",
    )
    for role, marker in bam_read_oracles(media).items():
        text = files[role].read_text(encoding="utf-8", errors="replace")
        if marker not in text:
            raise VerifyError(f"evidence {role} lacks media-bound oracle {marker!r}")


def verify_d81(case_id: str, files: dict[str, Path]) -> None:
    if case_id not in {
        "bam-alloc", "chain-write", "dir-write", "save-new", "save-new-scan", "save-new-var",
    }:
        return
    before, after = str(files["before-d81"]), str(files["after-d81"])
    py = sys.executable
    if case_id == "bam-alloc":
        command = [py, "tools/host-lisp/d81_bam_alloc_diff.py", before, after, "--track", "45", "--sector", "8"]
    elif case_id == "chain-write":
        command = [
            py, "tools/host-lisp/d81_chain_write_diff.py", before, after,
            "--source", "tests/disk/m3-chain-source.lisp", "--track", "45",
            "--first-sector", "8", "--second-sector", "9",
        ]
    elif case_id == "dir-write":
        command = [
            py, "tools/host-lisp/d81_dir_write_diff.py", before, after,
            "--source", "tests/disk/m4-dir-source.lisp", "--name", "m4src",
            "--track", "45", "--first-sector", "8", "--second-sector", "9",
            "--dir-track", "40", "--dir-sector", "4", "--dir-entry", "2",
        ]
    elif case_id in ("save-new", "save-new-scan"):
        first, second, name = (("27", "28", "m5src") if case_id == "save-new" else ("28", "29", "m6src"))
        command = [
            py, "tools/host-lisp/d81_dir_write_diff.py", before, after,
            "--source", "tests/disk/m5-new-source.lisp", "--name", name,
            "--track", "45", "--first-sector", first, "--second-sector", second,
            "--dir-track", "40", "--dir-sector", "4", "--dir-entry", "3",
        ]
    else:
        command = [
            py, "tools/host-lisp/d81_save_new_diff.py", before, after,
            "--source", "tests/disk/m7-var-source.lisp", "--name", "m7src",
            "--dir-track", "40", "--dir-sector", "4", "--dir-entry", "3",
        ]
    run_oracle(command, f"{case_id} independent D81 oracle")


def verify_receipt(
    receipt_path: Path,
    *,
    target: str,
    result: str,
    cycle_id: str,
    candidate_manifest_sha256: str,
    product_artifact_set_sha256: str | None,
    build_id: int,
    workbench_test_media_sha256: str | None = None,
) -> dict[str, Any]:
    receipt_path = receipt_path.resolve()
    receipt = load(receipt_path, "global Workbench G5 native receipt")
    exact(
        receipt,
        {
            "format", "profile", "product_artifact_set_sha256", "candidate_manifest_sha256",
            "build_id", "case_id", "target", "expected", "result", "cycle_id",
            "attempts", "evidence",
        },
        "global Workbench G5 native receipt",
    )
    if receipt["format"] != RECEIPT_FORMAT or receipt["profile"] != "dialect-v2":
        raise VerifyError("native receipt format/profile drift")
    case_key = receipt["case_id"]
    if not isinstance(case_key, str) or "/" not in case_key:
        raise VerifyError("native receipt case id drift")
    domain, case_id = case_key.split("/", 1)
    if domain not in EXPECTED or case_id not in EXPECTED[domain]:
        raise VerifyError("native receipt case is outside the global matrix")
    expected_target, expected_result = EXPECTED[domain][case_id]
    receipt_product_sha = lower_sha(receipt["product_artifact_set_sha256"], "receipt product artifact set")
    expected_product_sha = (
        receipt_product_sha if product_artifact_set_sha256 is None
        else lower_sha(product_artifact_set_sha256, "product artifact set")
    )
    if (
        receipt_product_sha != expected_product_sha
        or receipt["candidate_manifest_sha256"] != lower_sha(candidate_manifest_sha256, "candidate manifest")
        or receipt["build_id"] != build_id
        or receipt["target"] != target
        or receipt["target"] != expected_target
        or receipt["expected"] != expected_result
        or receipt["result"] != result
        or receipt["result"] != expected_result
        or receipt["cycle_id"] != cycle_id
        or not SAFE_ID.fullmatch(cycle_id)
    ):
        raise VerifyError("native receipt identity/result binding drift")
    verify_attempts(receipt["attempts"], case_key)
    required = EVIDENCE[case_id]
    if not isinstance(receipt["evidence"], list):
        raise VerifyError("native receipt evidence must be a list")
    files: dict[str, Path] = {}
    for index, raw in enumerate(receipt["evidence"]):
        item = exact(raw, {"role", "path", "sha256"}, f"evidence[{index}]")
        role = item["role"]
        if role in files or role not in required:
            raise VerifyError(f"evidence role duplicate/foreign: {role}")
        files[role] = evidence_file(receipt_path, item["path"], item["sha256"], f"evidence {role}")
    if tuple(files) != tuple(required):
        raise VerifyError("native receipt evidence coverage/order drift")
    for role, marker in required.items():
        if marker is not None:
            text = files[role].read_text(encoding="utf-8", errors="replace")
            if marker not in text:
                raise VerifyError(f"evidence {role} lacks oracle {marker!r}")
    if case_id == "bam-read":
        verify_bam_read(files, workbench_test_media_sha256)
    if case_id == "overlay-stack-guard":
        ship = load(files["ship-receipt"], "Workbench Ship readback receipt")
        if ship.get("schema") != "lisp65-hw-ship-memory-receipt-v2" or ship.get("dry_run") is not False:
            raise VerifyError("overlay stack guard lacks live Ship readback")
    verify_d81(case_id, files)
    return receipt


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")


def fixture_receipt(
    root: Path,
    domain: str,
    case_id: str,
    product_sha: str,
    candidate_sha: str,
    build_id: int,
) -> tuple[Path, dict[str, Any]]:
    target, expected = EXPECTED[domain][case_id]
    evidence = []
    markers = EVIDENCE[case_id]
    if case_id == "bam-read":
        media = bytearray(80 * 40 * 256)
        bam_sector_1 = (((40 - 1) * 40 + 1) * 256)
        bam_sector_2 = (((40 - 1) * 40 + 2) * 256)
        media[bam_sector_1 : bam_sector_1 + 2] = bytes((40, 2))
        media[bam_sector_2 : bam_sector_2 + 2] = bytes((0, 255))
        for track in range(1, 81):
            bam_sector = 1 if track <= 40 else 2
            index = track - 1 if track <= 40 else track - 41
            entry = (((40 - 1) * 40 + bam_sector) * 256) + 16 + 6 * index
            media[entry] = 40
            media[entry + 1 : entry + 6] = b"\xff" * 5
        media_path = root / "media-d81.d81"
        media_path.write_bytes(media)
        dynamic = bam_read_oracles(media_path)
    else:
        media_path = None
        dynamic = {}
    for role, marker in markers.items():
        path = media_path if role == "media-d81" else root / f"{role}.txt"
        if role != "media-d81":
            path.write_text((marker or dynamic.get(role) or "fixture") + "\n", encoding="utf-8")
        assert path is not None
        evidence.append({"role": role, "path": path.name, "sha256": sha(path)})
    value = {
        "format": RECEIPT_FORMAT,
        "profile": "dialect-v2",
        "product_artifact_set_sha256": product_sha,
        "candidate_manifest_sha256": candidate_sha,
        "build_id": build_id,
        "case_id": f"{domain}/{case_id}",
        "target": target,
        "expected": expected,
        "result": expected,
        "cycle_id": f"negative-proof-{domain}",
        "attempts": [{
            "index": 1, "outcome": "pass", "semantic_execution": True,
            "media_content_mutation": domain == "workbench-persistence",
            "evidence_directory": ".", "throwaway_media": domain == "workbench-persistence",
        }],
        "evidence": evidence,
    }
    receipt = root / "receipt.json"
    write_json(receipt, value)
    return receipt, value


def negative_proof(product_sha: str, candidate_sha: str, build_id: int) -> dict[str, Any]:
    domains = []
    cases = {"workbench-persistence": "bam-read", "workbench-ux": "stdlib-runtime"}
    with tempfile.TemporaryDirectory(prefix="lisp65-r5-workbench-negative-") as raw:
        base = Path(raw)
        for domain, case_id in cases.items():
            root = base / domain
            root.mkdir()
            receipt_path, pristine = fixture_receipt(root, domain, case_id, product_sha, candidate_sha, build_id)
            target, result = EXPECTED[domain][case_id]

            def attempt() -> str:
                try:
                    verify_receipt(
                        receipt_path, target=target, result=result,
                        cycle_id=f"negative-proof-{domain}",
                        candidate_manifest_sha256=candidate_sha,
                        product_artifact_set_sha256=product_sha, build_id=build_id,
                    )
                except VerifyError as exc:
                    return str(exc)
                raise VerifyError(f"negative proof mutation was accepted: {domain}")

            verify_receipt(
                receipt_path, target=target, result=result,
                cycle_id=f"negative-proof-{domain}",
                candidate_manifest_sha256=candidate_sha,
                product_artifact_set_sha256=product_sha, build_id=build_id,
            )
            mutations = []

            artifact = root / pristine["evidence"][0]["path"]
            original = artifact.read_bytes()
            artifact.write_bytes(original + b"tamper\n")
            diagnostic = attempt()
            mutations.append({"id": "artifact-bytes", "result": "rejected", "diagnostic_sha256": sha_bytes(diagnostic.encode())})
            artifact.write_bytes(original)

            altered = deepcopy(pristine)
            protocol_index = next(
                index for index, row in enumerate(pristine["evidence"])
                if row["role"] != "media-d81"
            )
            protocol = root / pristine["evidence"][protocol_index]["path"]
            protocol_original = protocol.read_bytes()
            protocol.write_text("oracle removed\n", encoding="utf-8")
            altered["evidence"][protocol_index]["sha256"] = sha(protocol)
            write_json(receipt_path, altered)
            diagnostic = attempt()
            mutations.append({"id": "raw-oracle", "result": "rejected", "diagnostic_sha256": sha_bytes(diagnostic.encode())})
            protocol.write_bytes(protocol_original)

            altered = deepcopy(pristine)
            altered["product_artifact_set_sha256"] = "0" * 64
            write_json(receipt_path, altered)
            diagnostic = attempt()
            mutations.append({"id": "product-identity", "result": "rejected", "diagnostic_sha256": sha_bytes(diagnostic.encode())})

            domains.append({
                "id": domain, "fixture_case": case_id, "baseline": "accepted",
                "mutations": mutations,
            })
    return {
        "format": NEGATIVE_FORMAT,
        "version": 1,
        "verifier_sha256": sha(Path(__file__)),
        "product_artifact_set_sha256": product_sha,
        "candidate_manifest_sha256": candidate_sha,
        "domains": domains,
        "result": "passed",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--receipt", type=Path, required=True)
    verify.add_argument("--target", required=True)
    verify.add_argument("--result", required=True)
    verify.add_argument("--cycle-id", required=True)
    verify.add_argument("--candidate-manifest-sha256", required=True)
    # The promotion wrapper already binds the candidate manifest SHA. Direct
    # R5 verification additionally passes the sealed product set explicitly.
    verify.add_argument("--product-artifact-set-sha256")
    verify.add_argument("--workbench-test-media-sha256")
    verify.add_argument("--build-id", type=int, required=True)
    negative = sub.add_parser("negative-proof")
    negative.add_argument("--product-artifact-set-sha256", required=True)
    negative.add_argument("--candidate-manifest-sha256", required=True)
    negative.add_argument("--build-id", type=int, required=True)
    negative.add_argument("--out", type=Path, required=True)
    sub.add_parser("selftest")
    args = parser.parse_args()
    try:
        if args.command == "verify":
            value = verify_receipt(
                args.receipt, target=args.target, result=args.result, cycle_id=args.cycle_id,
                candidate_manifest_sha256=args.candidate_manifest_sha256,
                product_artifact_set_sha256=args.product_artifact_set_sha256,
                build_id=args.build_id,
                workbench_test_media_sha256=args.workbench_test_media_sha256,
            )
            print(f"dialect-v2 Workbench G5 verifier: PASS case={value['case_id']}")
        else:
            if args.command == "selftest":
                product_sha, candidate_sha, build_id = "1" * 64, "2" * 64, 0xFA377C50
                value = negative_proof(product_sha, candidate_sha, build_id)
                print(f"dialect-v2 Workbench G5 verifier selftest: PASS domains={len(value['domains'])} mutations=6")
            else:
                product_sha = lower_sha(args.product_artifact_set_sha256, "product artifact set")
                candidate_sha = lower_sha(args.candidate_manifest_sha256, "candidate manifest")
                value = negative_proof(product_sha, candidate_sha, args.build_id)
                write_json(args.out, value)
                print(f"dialect-v2 Workbench G5 negative proof: PASS domains={len(value['domains'])} mutations=6")
    except (VerifyError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"dialect-v2 Workbench G5 verifier: FAIL: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
