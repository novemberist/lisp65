#!/usr/bin/env python3
"""Bind the Link-93 trace core-ABI product, medium, and hardware handoff."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build/c2.3/trace-core-abi-link93-r6"
WPLTO = BUILD / "wplto"
FINAL = BUILD / "final"
MEDIA = BUILD / "trace-acceptance-media"
TRACE_LIBRARY = MEDIA / "trace-library"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-trace-core-abi-link93-receipt.json"
)
HOST_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-trace-core-abi-host-receipt.json"
)
CONTRACT = ROOT / "config/c2-trace-core-abi.json"
PLAN = ROOT / "docs/planning/trace-core-abi-work-plan.md"
VM = ROOT / "src/vm.c"
TRACE_SOURCE = ROOT / "lib/inspect-trace.lisp"
TRACE_SUITE = ROOT / "tests/bytecode/libs/p0-inspect-trace.json"
GATES = ROOT / "mk/gates.mk"
FORMAT = "lisp65-c2.3-trace-core-abi-link93-v1"
PRODUCT_SHA = "15c6e0817ae1a3ace7a3e4d576e3c238d268cbcf9c25e98842dd0b912b9d3f62"
PRODUCT_D81_SHA = "57afdf35587106ad4b813da2cfecf5220276863a939591c0667750e4e712b315"
LIBRARY_D81_SHA = "5e282937436e6d2656590490734d800fcd9fecb4b3a740a3ec39009cdeb5a1bd"
HISTORICAL_SOURCE_COMMIT = "efb30d48ab2454c5bd0b1117e4a6176a3227f51e"


class LinkError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise LinkError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def vm_callprim_rodata_bytes() -> int:
    map_text = (WPLTO / "lisp65-c2-substitution-linked.prg.map").read_text(
        encoding="utf-8"
    )
    rows = [line for line in map_text.splitlines()
            if "(.rodata.vm_callprim)" in line]
    require(len(rows) == 1, "vm_callprim immutable row is not unique")
    fields = rows[0].split()
    require(len(fields) >= 3 and re.fullmatch(r"[0-9a-fA-F]+", fields[2])
            is not None, "vm_callprim immutable row cannot be decoded")
    return int(fields[2], 16)


def source_bindings() -> dict[str, dict[str, Any]]:
    return {
        "contract": bind(CONTRACT),
        "plan": bind(PLAN),
        "target_VM": bind(VM),
        "trace_source": bind(TRACE_SOURCE),
        "trace_suite": bind(TRACE_SUITE),
        "host_receipt": bind(HOST_RECEIPT),
    }


def historical_source_bindings() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, path in {
        "contract": CONTRACT,
        "plan": PLAN,
        "target_VM": VM,
        "trace_source": TRACE_SOURCE,
        "trace_suite": TRACE_SUITE,
        "host_receipt": HOST_RECEIPT,
    }.items():
        relative = path.relative_to(ROOT).as_posix()
        raw = subprocess.run(
            ["git", "show", f"{HISTORICAL_SOURCE_COMMIT}:{relative}"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE,
        ).stdout
        result[name] = {
            "path": relative, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    return result


def derive() -> dict[str, Any]:
    host = load(HOST_RECEIPT)
    internal_path = BUILD / "receipts/wplto-internal.json"
    completion_path = BUILD / "receipts/artifact-completion.json"
    product_manifest_path = BUILD / "canonical-product-manifest.json"
    shared_manifest_path = MEDIA / "shared-system/candidate-manifest.json"
    inspect_manifest_path = ROOT / "build/c2.3/trace-core-abi/inspect.manifest.json"
    internal = load(internal_path)
    completion = load(completion_path)
    product_manifest = load(product_manifest_path)
    shared = load(shared_manifest_path)
    inspect = load(inspect_manifest_path)
    replacement = internal["fresh_replacement_gates"]
    walls = replacement["walls"]
    capacity = replacement["capacity"]
    entries = {row["name"] for row in inspect["entries"]}
    roles = {row["role"] for row in product_manifest["artifacts"]}
    require(
        host.get("status") == "host-green-link-pending"
        and internal.get("status")
            == "passed-new-c2-lite-real-abi-identity-hardware-not-run"
        and internal.get("execution_accounting", {}).get("product_closure_links") == 1
        and replacement.get("status") == "passed"
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54
        and walls["ordinary_bank0_bss_headroom_bytes"] >= 0
        and walls["fixed_hot_block_headroom_bytes"] >= 0
        and walls["resident_island_headroom_bytes"] >= 0,
        "Link-93 product geometry is not closed",
    )
    require(
        capacity.get("status")
            == "passed-current-v4-two-region-session-aggregate"
        and capacity.get("session_catalog_records") == 52
        and capacity.get("session_service_records") == 1
        and capacity.get("session_service_bytes") == 399
        and capacity.get("session_family_headroom_bytes") >= 0,
        "Link-93 Session family is not closed",
    )
    require(
        vm_callprim_rodata_bytes() == 168
        and completion.get("status")
            == "passed-no-relink-publish-last-artifact-completion"
        and completion.get("compiler_runs") == completion.get("linker_runs") == 0,
        "Link-93 completion grew immutable ABI data or relinked",
    )
    require(
        product_manifest.get("status")
            == "passed-fresh-source-product-and-post-link-completion"
        and product_manifest.get("artifact_count_before_media") == 14
        and len(roles) == 14
        and {"linked-product-elf", "c2-resident-prg", "c2d-v6-code-plane"}
            .issubset(roles),
        "Link-93 canonical product manifest is incomplete",
    )
    require(
        {"trace", "untrace", "%function-cell"}.issubset(entries)
        and inspect.get("artifact_role") == "disk-lib"
        and shared.get("status") == "passed-complete-C2-lite-two-media-product"
        and shared.get("artifact_count") == 19,
        "trace library or shared media closure is incomplete",
    )
    library_rows = {
        "D81": bind(TRACE_LIBRARY / "lisp65-library.d81"),
        "index": bind(TRACE_LIBRARY / "l65index"),
        "inspect": bind(TRACE_LIBRARY / "inspect.l65s"),
    }
    require(
        library_rows["D81"]["bytes"] == 819200
        and library_rows["index"]["bytes"] == 80
        and library_rows["inspect"]["bytes"] > 0,
        "trace acceptance library medium geometry drift",
    )
    return {
        "format": FORMAT,
        "recorded_on": "2026-08-09",
        "status": "LINK93-HOST-AND-MEDIA-GREEN; HARDWARE-PENDING",
        "source_bindings": source_bindings(),
        "attempt_accounting": {
            "rejected_seed_links": 2,
            "product_link_attempts": 3,
            "successful_product_links": 1,
            "hardware_runs": 0,
            "sealed_v1_4_artifacts_changed": 0,
            "notes": [
                "direct Prim-69 row rejected at the immutable E000 floor",
                "cold intern-service placement rejected at packed Session capacity",
                "unfactored resident carrier rejected at the 32-byte text wall",
                "shared resident symbol-domain predicate closes Link 93",
            ],
        },
        "link": {
            "number": 93,
            "target_placement": "existing-resident-prim20-dispatch-seam",
            "private_mode_marker": 69,
            "native_ID_added": False,
            "vm_callprim_rodata_bytes": 168,
            "walls": {
                key: walls[key] for key in (
                    "bank0_text_headroom_bytes",
                    "e000_headroom_bytes",
                    "ordinary_bank0_bss_headroom_bytes",
                    "fixed_hot_block_headroom_bytes",
                    "resident_island_headroom_bytes",
                )
            },
            "Session_capacity": {
                key: capacity[key] for key in (
                    "session_catalog_records", "session_service_records",
                    "session_service_bytes", "session_family_bytes",
                    "session_family_headroom_bytes",
                )
            },
            "internal": bind(internal_path),
            "completion": bind(completion_path),
            "canonical_manifest": bind(product_manifest_path),
            "product": bind(FINAL / "lisp65-c2-substitution-linked.prg"),
            "ELF": bind(FINAL / "lisp65-c2-substitution-linked.prg.elf"),
            "map": bind(FINAL / "lisp65-c2-substitution-linked.prg.map"),
            "resolved_profile": bind(FINAL / "resolved-profile.txt"),
        },
        "library": {
            "package": "inspect",
            "private_until_release_scope": True,
            "entries": sorted(entries),
            "manifest": bind(inspect_manifest_path),
            "medium": library_rows,
            "index_rows": 1,
            "index_mutations_rejected": 29,
        },
        "media": {
            "shared_manifest": bind(shared_manifest_path),
            "product_D81": bind(MEDIA / "shared-system/lisp65-product.d81"),
            "work_D81": bind(MEDIA / "shared-system/lisp65-work.d81"),
            "library_D81": library_rows["D81"],
            "shared_roles": 19,
            "readback": "passed",
        },
        "hardware_handoff": {
            "status": "prepared-not-run",
            "bundled_session_row": "core-ABI trace exact-restoration",
            "forms": [
                "(require (quote inspect))",
                "(defun trace-probe (x) (+ x 1))",
                "(trace trace-probe)",
                "(trace-probe 4)",
                "(untrace trace-probe)",
                "(trace-probe 4)",
            ],
            "expected": [
                "t", "trace-probe", "trace-probe",
                "trace-enter/trace-exit plus exact result 5",
                "trace-probe", "5 with no trace markers",
            ],
            "observation_policy": (
                "persistent-by-default: each mutating form runs quiet and is "
                "observed once by postcondition only"
            ),
        },
        "scope": {
            "release_claim": False,
            "public_surface_changed": False,
            "device_contact": False,
            "next_action": "bundled-device-session-then-v1.5-scope-halt",
        },
    }


def validate(value: dict[str, Any], *, verify_sources: bool) -> None:
    require(value.get("format") == FORMAT, "Link-93 receipt format drift")
    require(value.get("status")
            == "LINK93-HOST-AND-MEDIA-GREEN; HARDWARE-PENDING",
            "Link-93 host/media status dimmed")
    link = value["link"]
    walls = link["walls"]
    require(
        link["number"] == 93
        and link["native_ID_added"] is False
        and link["vm_callprim_rodata_bytes"] == 168
        and link["target_placement"] == "existing-resident-prim20-dispatch-seam"
        and walls["bank0_text_headroom_bytes"] >= 32
        and walls["e000_headroom_bytes"] >= 54,
        "Link-93 ABI/geometry claim dimmed",
    )
    attempts = value["attempt_accounting"]
    require(attempts.get("rejected_seed_links") == 2
            and attempts.get("product_link_attempts") == 3
            and attempts.get("successful_product_links") == 1
            and attempts.get("hardware_runs") == 0
            and attempts.get("sealed_v1_4_artifacts_changed") == 0,
            "Link-93 execution accounting drift")
    require(
        {"trace", "untrace", "%function-cell"}
            .issubset(set(value["library"]["entries"]))
        and value["library"]["private_until_release_scope"] is True
        and value["library"]["index_mutations_rejected"] == 29
        and value["media"]["shared_roles"] == 19
        and value["media"]["readback"] == "passed",
        "trace library/media claim dimmed",
    )
    require(link["product"] == {
        "path": "build/c2.3/trace-core-abi-link93-r6/final/"
                "lisp65-c2-substitution-linked.prg",
        "bytes": 41566,
        "sha256": PRODUCT_SHA,
    } and value["media"]["product_D81"] == {
        "path": "build/c2.3/trace-core-abi-link93-r6/"
                "trace-acceptance-media/shared-system/lisp65-product.d81",
        "bytes": 819200,
        "sha256": PRODUCT_D81_SHA,
    } and value["media"]["library_D81"] == {
        "path": "build/c2.3/trace-core-abi-link93-r6/"
                "trace-acceptance-media/trace-library/lisp65-library.d81",
        "bytes": 819200,
        "sha256": LIBRARY_D81_SHA,
    }, "Link-93 product/media identity drift")
    require(value["hardware_handoff"]["status"] == "prepared-not-run"
            and value["scope"] == {
                "release_claim": False,
                "public_surface_changed": False,
                "device_contact": False,
                "next_action": "bundled-device-session-then-v1.5-scope-halt",
            }, "Link-93 scope broadened")
    if verify_sources:
        require(value["source_bindings"] == historical_source_bindings(),
                "Link-93 historical source authority drift")


def rejected_mutations(base: dict[str, Any]) -> list[str]:
    mutations: dict[str, Callable[[dict[str, Any]], None]] = {
        "add-native-ID": lambda x: x["link"].update(native_ID_added=True),
        "grow-callprim-table": lambda x: x["link"].update(vm_callprim_rodata_bytes=170),
        "move-carrier-to-cold-service": lambda x: x["link"].update(
            target_placement="intern-Session-service"),
        "dim-text-wall": lambda x: x["link"]["walls"].update(
            bank0_text_headroom_bytes=31),
        "dim-E000-wall": lambda x: x["link"]["walls"].update(e000_headroom_bytes=53),
        "hide-link-attempt": lambda x: x["attempt_accounting"].update(
            product_link_attempts=2),
        "claim-hardware": lambda x: x["attempt_accounting"].update(hardware_runs=1),
        "drop-trace": lambda x: x["library"]["entries"].remove("trace"),
        "publish-library": lambda x: x["library"].update(
            private_until_release_scope=False),
        "dim-index-mutations": lambda x: x["library"].update(
            index_mutations_rejected=28),
        "drop-shared-role": lambda x: x["media"].update(shared_roles=18),
        "skip-readback": lambda x: x["media"].update(readback="not-run"),
        "replace-product-artifact": lambda x: x["link"]["product"].update(
            sha256="00" * 32),
        "replace-product-medium": lambda x: x["media"]["product_D81"].update(
            sha256="00" * 32),
        "replace-library-medium": lambda x: x["media"]["library_D81"].update(
            sha256="00" * 32),
        "claim-release": lambda x: x["scope"].update(release_claim=True),
        "claim-device": lambda x: x["scope"].update(device_contact=True),
    }
    rejected: list[str] = []
    for name, mutate in mutations.items():
        candidate = deepcopy(base)
        mutate(candidate)
        try:
            validate(candidate, verify_sources=False)
        except LinkError:
            rejected.append(name)
    require(len(rejected) == len(mutations),
            f"Link-93 receipt mutation survived: {sorted(set(mutations)-set(rejected))}")
    return rejected


def gate_wiring() -> None:
    text = GATES.read_text(encoding="utf-8")
    require(all(token in text for token in (
        "c2-trace-core-abi-link-selftest:",
        "python3 tools/host-lisp/c2_trace_core_abi_link.py selftest",
        "c2-trace-core-abi-link-check:",
        "python3 tools/host-lisp/c2_trace_core_abi_link.py check",
        "check-source: c2-trace-core-abi-link-selftest",
    )), "Link-93 permanent gate wiring absent")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "check", "selftest"))
    action = parser.parse_args().action
    if action == "record":
        value = derive()
        validate(value, verify_sources=True)
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_bytes(canonical(value))
        print(f"trace core-ABI Link 93: WROTE {RECEIPT.relative_to(ROOT)}")
        return 0
    value = load(RECEIPT)
    gate_wiring()
    validate(value, verify_sources=True)
    mutations = rejected_mutations(value)
    if action == "check":
        print(
            "trace core-ABI Link 93 check: PASS "
            "sealed-host/media-authority hardware-pending"
        )
    else:
        print(f"trace core-ABI Link 93 selftest: PASS mutations={len(mutations)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (LinkError, OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print(f"trace core-ABI Link 93: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
