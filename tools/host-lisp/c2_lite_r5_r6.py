#!/usr/bin/env python3
"""Rebind the hardware-tested C2-lite R5 successor and package exact R6 bytes."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/host-lisp/c2_lite_r5_r6.py"
OFFLINE = ROOT / "tools/host-lisp/c2_lite_r6_offline.py"
CONTRACT = ROOT / "config/c2-lite-acceptance-chain.json"
OLD_R5 = ROOT / "build/c2.2/acceptance/r5/r5-preflight-receipt.json"
G5 = (
    ROOT
    / "build/c2.2/acceptance/g5/replay-v11-hybrid-dma/session-01"
    / "g5-hardware-receipt.json"
)
R5_OUT = ROOT / "build/c2.2/acceptance/r5-successor-v11"
R5_PRODUCT = R5_OUT / "product"
R5_RECEIPT = R5_OUT / "r5-successor-rebind-receipt.json"
R6_OUT = ROOT / "build/c2.2/acceptance/r6-successor-v11"
R6_SHIP = R6_OUT / "ship"
R6_RECEIPT = R6_OUT / "r6-packaging-receipt.json"
ROLE_COUNT = 19
R5_ACCEPTED_STATUSES = {"passed-successor-rebind"}
R5_PROOF_NAME = "historical-r5-preflight-receipt.json"
R5_PACKAGE_CLAIM = "passed-successor-rebind"
R5_DESCRIPTION = "fresh-G5-tested R5 successor"
R5_MAPPING = "all-19-R5-successor-roles-exactly-once"
R6_ID = "R6-from-R5-successor-v11"
R6_RECEIPT_ID = "R6-from-tested-R5-successor-v11"
RECORDED_ON = "2026-07-27"
CHANGED_ROLES = {
    "cold-stager", "product-d81", "product-mount-descriptor",
}
CHAIN = (
    (
        "v3", "normal-dma-repack-v3", "g5-repack-receipt.json",
    ),
    (
        "v4", "normal-dma-repack-v4", "g5-repack-receipt.json",
    ),
    (
        "v5", "normal-dma-repack-v5", "g5-repack-receipt.json",
    ),
    (
        "v6", "normal-dma-repack-v6", "g5-repack-receipt.json",
    ),
    (
        "v7", "normal-dma-repack-v7", "g5-repack-receipt.json",
    ),
    (
        "v8", "rom-write-enable-repack-v8",
        "g5-rom-write-enable-repack-receipt.json",
    ),
    (
        "v9", "entry-bound-repack-v9",
        "g5-entry-bound-repack-receipt.json",
    ),
    (
        "v10", "handoff-completion-repack-v10",
        "g5-handoff-completion-repack-receipt.json",
    ),
    (
        "v11", "hybrid-dma-repack-v11",
        "g5-hybrid-dma-repack-receipt.json",
    ),
)


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path: Path, label: str) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"{label} is missing")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=strict_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RebindError(f"cannot read {label}: {error}") from error
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("ascii")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"missing authority: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def relative(value: str, label: str) -> PurePosixPath:
    path = PurePosixPath(value)
    require(
        value and not path.is_absolute() and path.as_posix() == value
        and ".." not in path.parts,
        f"{label} is not a canonical relative path",
    )
    return path


def artifact_set_sha(rows: list[dict[str, Any]]) -> str:
    identity = [
        {key: row[key] for key in ("role", "name", "bytes", "sha256")}
        for row in sorted(rows, key=lambda row: (row["role"], row["name"]))
    ]
    return sha_bytes(json.dumps(
        identity, sort_keys=True, separators=(",", ":"),
    ).encode())


def role_map(rows: Any, label: str) -> dict[str, dict[str, Any]]:
    require(isinstance(rows, list) and len(rows) == ROLE_COUNT,
            f"{label} must enumerate 19 roles")
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        require(
            isinstance(row, dict)
            and isinstance(row.get("role"), str)
            and isinstance(row.get("name"), str)
            and type(row.get("bytes")) is int
            and isinstance(row.get("sha256"), str)
            and len(row["sha256"]) == 64,
            f"{label} row {index} malformed",
        )
        require(row["role"] not in result, f"{label} repeats {row['role']}")
        result[row["role"]] = row
    return result


def verify_row_bytes(row: dict[str, Any], path_key: str, label: str) -> None:
    value = row.get(path_key)
    require(isinstance(value, str), f"{label} lacks {path_key}")
    path = ROOT / Path(*relative(value, f"{label} {path_key}").parts)
    require(
        path.is_file() and not path.is_symlink()
        and path.stat().st_size == row["bytes"]
        and sha(path) == row["sha256"],
        f"{label} byte binding drift",
    )


def receipt_manifest_binding(
    receipt: dict[str, Any], manifest_path: Path, label: str,
) -> None:
    binding = receipt.get("media_manifest")
    if not isinstance(binding, dict):
        candidate = receipt.get("candidate")
        binding = candidate.get("manifest") if isinstance(candidate, dict) else None
    require(isinstance(binding, dict), f"{label} does not bind its manifest")
    expected = bind(manifest_path)
    require(
        binding.get("path") == expected["path"]
        and binding.get("bytes") == expected["bytes"]
        and binding.get("sha256") == expected["sha256"],
        f"{label} manifest binding drift",
    )


def transition(
    predecessor: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    require(set(predecessor) == set(current), "transition role closure drift")
    changed = []
    unchanged = []
    for role in sorted(current):
        left = predecessor[role]
        right = current[role]
        if any(left.get(key) != right.get(key)
               for key in ("name", "bytes", "sha256")):
            changed.append(role)
        else:
            unchanged.append(role)
    return changed, unchanged


def chain_state() -> tuple[
    dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any],
]:
    contract = load(CONTRACT, "C2-lite acceptance contract")
    roles = contract.get("artifact_roles")
    require(
        contract.get("format") == "lisp65-c2-lite-acceptance-chain-v1"
        and contract.get("status") == "owner-authorized"
        and isinstance(roles, list) and len(roles) == ROLE_COUNT
        and contract.get("R6", {}).get("artifact_mapping")
        == "all-19-R5-roles-exactly-once",
        "C2-lite acceptance contract drift",
    )
    old = load(OLD_R5, "historical R5 receipt")
    old_rows = role_map(old.get("materialized_artifacts"), "historical R5")
    require(
        set(old_rows) == set(roles)
        and artifact_set_sha(list(old_rows.values()))
        == old.get("artifact_set_sha256"),
        "historical R5 artifact identity drift",
    )
    for role, row in old_rows.items():
        verify_row_bytes(row, "materialized_path", f"historical R5 {role}")

    predecessor = old_rows
    transitions: list[dict[str, Any]] = []
    final_manifest: dict[str, Any] | None = None
    final_rows: dict[str, dict[str, Any]] | None = None
    g5_root = ROOT / "build/c2.2/acceptance/g5"
    for version, directory, receipt_name in CHAIN:
        step_root = g5_root / directory
        manifest_path = step_root / "candidate-manifest.json"
        receipt_path = step_root / receipt_name
        manifest = load(manifest_path, f"{version} candidate manifest")
        receipt = load(receipt_path, f"{version} repack receipt")
        rows = role_map(manifest.get("artifacts"), f"{version} manifest")
        require(set(rows) == set(roles), f"{version} role inventory drift")
        require(
            artifact_set_sha(list(rows.values()))
            == manifest.get("artifact_set_sha256"),
            f"{version} artifact-set identity drift",
        )
        for role, row in rows.items():
            verify_row_bytes(row, "path", f"{version} {role}")
        receipt_manifest_binding(receipt, manifest_path, f"{version} receipt")
        require(
            str(receipt.get("status", "")).startswith("passed-host-repack"),
            f"{version} receipt is not a passed host repack",
        )
        changed, unchanged = transition(predecessor, rows)
        require(
            set(changed).issubset(CHANGED_ROLES),
            f"{version} changed a product role: {changed}",
        )
        transitions.append({
            "version": version,
            "predecessor": (
                "historical-R5" if version == "v3"
                else CHAIN[len(transitions) - 1][0]
            ),
            "candidate_manifest": bind(manifest_path),
            "repack_receipt": bind(receipt_path),
            "artifact_set_sha256": manifest["artifact_set_sha256"],
            "changed_roles": changed,
            "unchanged_roles": len(unchanged),
            "status": "passed-receipt-bound-transition",
        })
        predecessor = rows
        final_manifest = manifest
        final_rows = rows

    require(final_manifest is not None and final_rows is not None,
            "empty successor chain")
    changed, unchanged = transition(old_rows, final_rows)
    require(
        set(changed) == CHANGED_ROLES and len(unchanged) == 16,
        "historical R5 to tested successor is not exact 3/16",
    )
    g5 = load(G5, "fresh G5 hardware receipt")
    require(
        g5.get("status") == "passed-fresh-nine-case-G5"
        and g5.get("result") == "passed"
        and g5.get("product", {}).get("artifact_set_sha256")
        == final_manifest["artifact_set_sha256"]
        and g5.get("product", {}).get("product_d81", {}).get("sha256")
        == final_rows["product-d81"]["sha256"],
        "fresh G5 does not bind the final successor set",
    )
    return old, g5, transitions, final_manifest


def rebind() -> dict[str, Any]:
    old, g5, transitions, final = chain_state()
    rows = role_map(final["artifacts"], "final v11 manifest")
    if R5_OUT.exists():
        shutil.rmtree(R5_OUT)
    R5_PRODUCT.mkdir(parents=True)
    materialized: list[dict[str, Any]] = []
    roles = load(CONTRACT, "C2-lite acceptance contract")["artifact_roles"]
    for index, role in enumerate(roles):
        row = rows[role]
        source = ROOT / Path(*relative(row["path"], f"{role} source").parts)
        output = R5_PRODUCT / f"{index:02d}-{row['name']}"
        shutil.copyfile(source, output)
        os.chmod(output, 0o644)
        require(
            output.stat().st_size == row["bytes"] and sha(output) == row["sha256"],
            f"R5 successor materialization drift: {role}",
        )
        materialized.append({
            **{key: row[key] for key in ("role", "name", "bytes", "sha256")},
            "source_path": row["path"],
            "materialized_path": output.relative_to(ROOT).as_posix(),
        })

    old_map = role_map(old["materialized_artifacts"], "historical R5")
    final_map = role_map(materialized, "R5 successor")
    changed, unchanged = transition(old_map, final_map)
    receipt = {
        "format": "lisp65-c2-lite-R5-successor-rebind-receipt-v1",
        "version": 1,
        "id": "R5-successor-v11-tested-media-rebind",
        "status": "passed-successor-rebind",
        "recorded_on": "2026-07-27",
        "authority": {
            "acceptance_contract": bind(CONTRACT),
            "historical_R5": bind(OLD_R5),
            "fresh_G5": bind(G5),
            "final_v11_manifest": bind(
                ROOT
                / "build/c2.2/acceptance/g5/hybrid-dma-repack-v11"
                / "candidate-manifest.json"
            ),
        },
        "historical_identity": {
            "artifact_set_sha256": old["artifact_set_sha256"],
            "status": "retained-immutable-history-not-renamed",
        },
        "successor_identity": {
            "artifact_count": ROLE_COUNT,
            "artifact_set_sha256": final["artifact_set_sha256"],
            "product_build_id": final["product_build_id"],
            "profile_build_id": final["profile_build_id"],
            "materialized_artifacts": materialized,
        },
        "receipt_chain": {
            "first": "historical-R5",
            "last": "v11",
            "transition_count": len(transitions),
            "transitions": transitions,
            "status": "passed-complete-v3-through-v11",
        },
        "role_delta": {
            "changed_roles": changed,
            "changed_role_count": len(changed),
            "unchanged_roles": unchanged,
            "unchanged_role_count": len(unchanged),
            "link66_roles_byteidentical": {
                role: final_map[role]["sha256"]
                for role in (
                    "linked-product-elf", "c2-resident-prg",
                    "c2-bank2-static-code-plane", "c2d-v6-code-plane",
                    "c2-two-record-boot-stage",
                    "c2-session-family-region-0",
                    "c2-session-family-region-1", "c2-kernal-window",
                )
            },
        },
        "claims": {
            "R5": "passed-successor-rebind-to-hardware-tested-set",
            "G5": "passed-fresh-nine-case-G5",
            "R6": "not-run",
            "G6": "not-run",
            "release": "not-release-capable",
        },
        "execution_accounting": {
            "product_builds": 0,
            "product_links": 0,
            "product_byte_changes": 0,
            "hardware_runs": 0,
        },
        "claim_limit": (
            "Names the tested R5 successor through the complete receipt chain. "
            "R6 packaging, G6 and release remain unclaimed."
        ),
        "result": "passed",
    }
    write(R5_RECEIPT, receipt)
    print(
        "c2-lite R5 SUCCESSOR REBIND PASS "
        f"chain={len(transitions)} changed=3 unchanged=16 "
        f"set={final['artifact_set_sha256']}"
    )
    return receipt


def ship_path(index: int, row: dict[str, Any]) -> str:
    role = row["role"]
    if role == "product-d81":
        return "media/lisp65-product.d81"
    if role == "work-d81":
        return "media/lisp65-work.d81"
    if role == "product-mount-descriptor":
        return "media/lisp65-product.mount.json"
    if role == "linked-product-elf":
        return "proof/product/lisp65-c2-lite-product.elf"
    return f"components/{index:02d}-{row['name']}"


def file_inventory(root: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise RebindError(f"R6 package contains symlink: {path}")
        if path.is_file() and path != root / "manifest.json":
            result.append({
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha(path),
                "mode": f"0{stat.S_IMODE(path.stat().st_mode):03o}",
            })
    return result


def package_set_sha(rows: list[dict[str, Any]]) -> str:
    identity = [
        {key: row[key] for key in ("path", "bytes", "sha256", "mode")}
        for row in sorted(rows, key=lambda row: row["path"])
    ]
    return sha_bytes(json.dumps(
        identity, sort_keys=True, separators=(",", ":"),
    ).encode())


def copy_bound(source: Path, output: Path, mode: int = 0o444) -> None:
    require(source.is_file() and not source.is_symlink(), f"missing source: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    require(not output.exists(), f"duplicate R6 output: {output}")
    shutil.copyfile(source, output)
    os.chmod(output, mode)


def build_ship(root: Path, r5: dict[str, Any]) -> dict[str, Any]:
    require(not root.exists(), f"R6 output already exists: {root}")
    root.mkdir(parents=True)
    rows = r5["successor_identity"]["materialized_artifacts"]
    require(len(rows) == ROLE_COUNT, "R5 successor role count drift")
    shipped = []
    for index, row in enumerate(rows):
        destination = ship_path(index, row)
        source = ROOT / Path(*relative(
            row["materialized_path"], f"{row['role']} materialization",
        ).parts)
        output = root / Path(*relative(destination, "R6 ship path").parts)
        mode = 0o644 if row["role"] == "work-d81" else 0o444
        copy_bound(source, output, mode)
        require(sha(output) == row["sha256"], f"R6 byte drift: {row['role']}")
        shipped.append({
            **{key: row[key] for key in ("role", "name", "bytes", "sha256")},
            "ship_path": destination,
            "mode": f"0{mode:03o}",
        })

    copy_bound(OFFLINE, root / "verify.py", 0o555)
    copy_bound(CONTRACT, root / "proof/acceptance-contract.json")
    copy_bound(R5_RECEIPT, root / "proof/r5-successor-rebind-receipt.json")
    copy_bound(G5, root / "proof/g5-hardware-receipt.json")
    copy_bound(OLD_R5, root / f"proof/{R5_PROOF_NAME}")
    for version, directory, receipt_name in CHAIN:
        source_root = ROOT / "build/c2.2/acceptance/g5" / directory
        copy_bound(
            source_root / "candidate-manifest.json",
            root / f"proof/rebind-chain/{version}-candidate-manifest.json",
        )
        copy_bound(
            source_root / receipt_name,
            root / f"proof/rebind-chain/{version}-repack-receipt.json",
        )
    readme = (
        "LISP65 C2-LITE R6 CANDIDATE\n"
        "============================\n\n"
        f"This package contains exactly the 19 roles of the {R5_DESCRIPTION}.\n"
        f"Artifact set: {r5['successor_identity']['artifact_set_sha256']}\n"
        "G5: PASSED (fresh nine-case hardware run)\n"
        "G6: NOT RUN\n"
        "RELEASE: NO\n\n"
        "Run `python3 verify.py` before using the package.\n"
    ).encode("ascii")
    readme_path = root / "README-FIRST.txt"
    readme_path.write_bytes(readme)
    os.chmod(readme_path, 0o444)
    inventory = file_inventory(root)
    manifest = {
        "format": "lisp65-c2-lite-R6-package-v1",
        "version": 1,
        "id": R6_ID,
        "status": "passed-transform-and-package-only",
        "recorded_on": RECORDED_ON,
        "authority": {
            "R5_successor_receipt": bind(R5_RECEIPT),
            "fresh_G5_receipt": bind(G5),
            "acceptance_contract": bind(CONTRACT),
        },
        "product": {
            "artifact_count": ROLE_COUNT,
            "artifact_set_sha256": r5["successor_identity"]["artifact_set_sha256"],
            "product_build_id": r5["successor_identity"]["product_build_id"],
            "profile_build_id": r5["successor_identity"]["profile_build_id"],
            "artifacts": shipped,
            "mapping": R5_MAPPING,
            "product_bytes": "byteidentical-to-R5-successor",
        },
        "media": {
            "product": next(row for row in shipped if row["role"] == "product-d81"),
            "work": next(row for row in shipped if row["role"] == "work-d81"),
            "mount": next(
                row for row in shipped
                if row["role"] == "product-mount-descriptor"
            ),
        },
        "files": inventory,
        "package_set_sha256": package_set_sha(inventory),
        "execution_accounting": {
            "product_builds": 0,
            "product_links": 0,
            "product_byte_changes": 0,
            "hardware_runs": 0,
        },
        "claims": {
            "R5": R5_PACKAGE_CLAIM,
            "G5": "passed-fresh-nine-case-G5",
            "R6": "passed-exact-19-role-package",
            "G6": "not-run",
            "release": "not-release-capable",
        },
        "claim_limit": (
            "Self-verifying R6 package only. G6 hardware and release remain "
            "unclaimed."
        ),
        "result": "passed",
    }
    write(root / "manifest.json", manifest)
    return manifest


def run_offline(root: Path) -> str:
    completed = subprocess.run(
        [sys.executable, "verify.py"], cwd=root,
        env={
            "PATH": os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
        },
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=False,
    )
    require(completed.returncode == 0,
            f"R6 offline verification failed: {completed.stdout}")
    return completed.stdout.strip()


def package() -> dict[str, Any]:
    require(R5_RECEIPT.is_file(), "R5 successor receipt is missing")
    r5 = load(R5_RECEIPT, "R5 successor receipt")
    require(
        r5.get("status") in R5_ACCEPTED_STATUSES
        and r5.get("result") == "passed",
        "R5 successor is not passed",
    )
    if R6_OUT.exists():
        shutil.rmtree(R6_OUT)
    R6_OUT.mkdir(parents=True)
    with tempfile.TemporaryDirectory(
        prefix="c2-lite-r6-double-pack-", dir=R6_OUT,
    ) as temporary:
        first = Path(temporary) / "first"
        second = Path(temporary) / "second"
        first_manifest = build_ship(first, r5)
        second_manifest = build_ship(second, r5)
        require(
            canonical(first_manifest) == canonical(second_manifest),
            "R6 double-pack manifest drift",
        )
        first_files = {
            row["path"]: (row["bytes"], row["sha256"], row["mode"])
            for row in file_inventory(first)
        }
        second_files = {
            row["path"]: (row["bytes"], row["sha256"], row["mode"])
            for row in file_inventory(second)
        }
        require(first_files == second_files, "R6 double-pack byte drift")
        shutil.copytree(first, R6_SHIP)

    offline_output = run_offline(R6_SHIP)
    manifest_path = R6_SHIP / "manifest.json"
    manifest = load(manifest_path, "R6 manifest")

    rejected = []
    with tempfile.TemporaryDirectory(prefix="c2-lite-r6-mutations-") as temporary:
        root = Path(temporary)
        for name, mutate in (
            (
                "product-byte",
                lambda p: p.write_bytes(bytes([p.read_bytes()[0] ^ 1])
                                        + p.read_bytes()[1:]),
            ),
            (
                "manifest-artifact-set",
                lambda p: p.write_text(
                    p.read_text().replace(
                        manifest["product"]["artifact_set_sha256"],
                        "0" * 64, 1,
                    ),
                    encoding="ascii",
                ),
            ),
            (
                "role-drop",
                lambda p: p.write_text(
                    json.dumps(
                        {
                            **load(p, "mutated manifest"),
                            "product": {
                                **load(p, "mutated manifest")["product"],
                                "artifacts": load(
                                    p, "mutated manifest",
                                )["product"]["artifacts"][:-1],
                            },
                        },
                        indent=2, sort_keys=True,
                    ) + "\n",
                    encoding="ascii",
                ),
            ),
        ):
            target = root / name
            shutil.copytree(R6_SHIP, target)
            path = (
                target / "media/lisp65-product.d81"
                if name == "product-byte" else target / "manifest.json"
            )
            os.chmod(path, 0o644)
            mutate(path)
            completed = subprocess.run(
                [sys.executable, "verify.py"], cwd=target,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, check=False,
            )
            require(completed.returncode != 0,
                    f"R6 mutation survived: {name}")
            rejected.append(name)

    receipt = {
        "format": "lisp65-c2-lite-R6-packaging-receipt-v1",
        "version": 1,
        "id": R6_RECEIPT_ID,
        "status": "passed-R6-package",
        "recorded_on": RECORDED_ON,
        "authority": {
            "R5_successor_receipt": bind(R5_RECEIPT),
            "fresh_G5_receipt": bind(G5),
            "R6_manifest": bind(manifest_path),
            "packer": bind(TOOL),
            "offline_verifier": bind(OFFLINE),
        },
        "product_artifact_set_sha256": manifest["product"]["artifact_set_sha256"],
        "artifact_count": ROLE_COUNT,
        "mapping": R5_MAPPING,
        "package_set_sha256": manifest["package_set_sha256"],
        "double_pack": "passed-byteidentical",
        "offline_verification": {
            "status": "passed",
            "output": offline_output,
            "mutations_rejected": rejected,
            "mutation_count": len(rejected),
        },
        "execution_accounting": {
            "product_builds": 0,
            "product_links": 0,
            "product_byte_changes": 0,
            "hardware_runs": 0,
        },
        "claims": manifest["claims"],
        "result": "passed",
    }
    write(R6_RECEIPT, receipt)
    print(
        "c2-lite R6 PACKAGE PASS "
        f"roles=19 mutations={len(rejected)} "
        f"set={manifest['product']['artifact_set_sha256']} "
        f"package={manifest['package_set_sha256']}"
    )
    return receipt


def verify() -> None:
    old_r5_sha = sha(OLD_R5)
    r5 = rebind()
    require(sha(OLD_R5) == old_r5_sha, "historical R5 was modified")
    r6 = package()
    require(
        r6["product_artifact_set_sha256"]
        == r5["successor_identity"]["artifact_set_sha256"],
        "R5 successor/R6 identity mismatch",
    )
    print("c2-lite R5 SUCCESSOR + R6 VERIFY PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("rebind", "package", "verify"),
    )
    arguments = parser.parse_args()
    try:
        if arguments.command == "rebind":
            rebind()
        elif arguments.command == "package":
            package()
        else:
            verify()
    except RebindError as error:
        raise SystemExit(f"c2-lite R5/R6: FAIL: {error}") from error


if __name__ == "__main__":
    main()
