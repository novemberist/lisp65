#!/usr/bin/env python3
"""Prepare and qualify the Link-57 C4 destructive-restage fixture."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/c2-destructive-restage-contract.json"
ADDENDUM = ROOT / "docs/planning/c2.2-destructive-restage-addendum.md"
MATRIX = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-full-matrix-link57-review-receipt.json"
)
STRUCTURAL = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json"
)
DEPLOYMENT = (
    ROOT / "build/c2.2/hardware-presmoke-link57-keymap-nullary/deployment.json"
)
PRODUCT_DIR = (
    ROOT / "build/c2.2/substitution/"
    "product-link-57-keymap-nullary-fast-path2"
)
ELF = PRODUCT_DIR / "lisp65-c2-substitution-linked.prg.elf"
NM = ROOT / "tools/llvm-mos/bin/llvm-nm"
DEFAULT_OUT = ROOT / "build/c2.2/destructive-restage-link57"
RECEIPT = (
    ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link57-destructive-restage-contract-probe-receipt.json"
)
RUNNER = ROOT / "scripts/c2-link57-destructive-restage-hw.sh"

C2D_BASE = 0x00050000
C2D_BYTES = 33840
C2D_REGION_BYTES = 50816
C2J_OFFSET = 50752
C2J_BYTES = 64
BOOTSTRAP_SCRATCH_BASE = 0x00058500
BOOTSTRAP_SCRATCH_OFFSET = BOOTSTRAP_SCRATCH_BASE - C2D_BASE
BOOTSTRAP_SCRATCH_BYTES = 3285
BOOTSTRAP_SCRATCH_END = BOOTSTRAP_SCRATCH_OFFSET + BOOTSTRAP_SCRATCH_BYTES
BANK2_BASE = 0x00020000
BANK3_BASE = 0x00030000
SESSION_ATTIC_SENTINEL = 0x084FFF80
EXPECTED_PRODUCT_SHA = (
    "7d568ceb7edab95a237ff3079fcf689768373a9ea48a5a43f355f6275ddc5df8"
)


class ContractError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def regular(path: Path, label: str = "input") -> bytes:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ContractError(f"missing {label}: {path}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ContractError(f"{label} must be a regular symlink-free file: {path}")
    return path.read_bytes()


def load_json(path: Path, label: str = "JSON") -> dict[str, Any]:
    try:
        value = json.loads(regular(path, label).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid {label}: {path}: {exc}") from exc
    require(isinstance(value, dict), f"{label} root is not an object")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(regular(path, "hash input"))


def bind(path: Path) -> dict[str, Any]:
    data = regular(path, "bound artifact")
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def u16(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def p16(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<H", data, offset, value)


def p32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def deployment_inputs() -> tuple[dict[str, Any], Path, Path, Path, Path]:
    deployment = load_json(DEPLOYMENT, "Link-57 deployment")
    product_row = deployment.get("product", {})
    require(
        product_row.get("sha256") == EXPECTED_PRODUCT_SHA,
        "Link-57 deployment product identity drift",
    )
    product = ROOT / str(product_row.get("path"))
    require(sha(product) == EXPECTED_PRODUCT_SHA, "Link-57 product bytes drift")
    rows = deployment.get("preloads")
    require(isinstance(rows, list) and len(rows) == 6, "deployment preload set drift")
    by_address = {int(row["address"], 0): row for row in rows}
    require(C2D_BASE in by_address, "deployment has no Bank-5 C2D preload")
    c2d_row = by_address[C2D_BASE]
    require(
        c2d_row.get("bytes") == C2D_BYTES,
        "ordinary Link-57 pre-smoke no longer has the expected short C2D prefix",
    )
    c2d = ROOT / str(c2d_row["path"])
    bank2 = (
        PRODUCT_DIR / "fresh-c2-lite-prelink-gates/v6-semantics/"
        "bank2-static-code.bin"
    )
    bootstrap_row = by_address[BOOTSTRAP_SCRATCH_BASE]
    require(
        bootstrap_row.get("bytes") == BOOTSTRAP_SCRATCH_BYTES,
        "Boot-overlay scratch size drift",
    )
    bootstrap = ROOT / str(bootstrap_row["path"])
    session_row = by_address[0x08000000]
    # The Session family lives at Attic 0x08000000 in the deployment; it is
    # the exact content later staged into physical Bank 3.
    require(
        int(session_row["address"], 0) == 0x08000000,
        "Session-family deployment address drift",
    )
    session = ROOT / str(session_row["path"])
    require(len(regular(c2d, "canonical C2D")) == C2D_BYTES, "C2D size drift")
    require(sha(c2d) == c2d_row["sha256"], "C2D binding drift")
    require(
        len(regular(bank2, "canonical Bank-2 plane")) == 34542,
        "Link-57 canonical Bank-2 size drift",
    )
    require(
        len(regular(session, "canonical Session family")) == 65438,
        "Link-57 Session-family size drift",
    )
    require(
        len(regular(bootstrap, "authenticated Boot-overlay scratch"))
        == BOOTSTRAP_SCRATCH_BYTES,
        "Boot-overlay artifact size drift",
    )
    require(
        sha(bootstrap) == bootstrap_row["sha256"],
        "Boot-overlay artifact binding drift",
    )
    return deployment, c2d, bank2, session, bootstrap


def elf_symbols() -> dict[str, dict[str, int]]:
    wanted = {
        "c2_ready": 1,
        "c2_runtime": 46,
        "rtov_family": 1,
        "rtov_family_generation": 2,
        "rtov_island_state": 1,
    }
    try:
        result = subprocess.run(
            [str(NM), "-S", "--defined-only", str(ELF)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise ContractError(f"llvm-nm failed: {detail.strip()}") from exc
    require(not result.stderr, f"llvm-nm diagnostic: {result.stderr.strip()}")
    found: dict[str, dict[str, int]] = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) < 4 or fields[-1] not in wanted:
            continue
        name = fields[-1]
        require(name not in found, f"duplicate ELF symbol: {name}")
        found[name] = {"address": int(fields[0], 16), "bytes": int(fields[1], 16)}
    require(set(found) == set(wanted), f"missing ELF state symbols: {sorted(set(wanted)-set(found))}")
    for name, size in wanted.items():
        require(found[name]["bytes"] == size, f"{name} size drift")
    require(
        found["c2_ready"]["address"] == 0x008C
        and found["c2_runtime"]["address"] == 0xC084
        and found["rtov_family"]["address"] == 0x0079
        and found["rtov_family_generation"]["address"] == 0xBFA9
        and found["rtov_island_state"]["address"] == 0x007A,
        "Link-57 volatile publication geometry drift",
    )
    return found


def active_journal(canonical: bytes) -> bytes:
    journal = bytearray(C2J_BYTES)
    journal[:4] = b"C2J\0"
    journal[4] = 1
    journal[5] = 1
    journal[6] = 0
    journal[7] = 0
    generation = u16(canonical, 10)
    images = u16(canonical, 12)
    entries = u16(canonical, 16)
    resolutions = u16(canonical, 20)
    roots = u16(canonical, 24)
    p16(journal, 8, generation)
    p16(journal, 10, images)
    p16(journal, 12, entries)
    p16(journal, 14, resolutions)
    p16(journal, 16, roots)
    p16(journal, 18, images + 1)
    p16(journal, 20, entries + 1)
    p16(journal, 22, resolutions)
    p16(journal, 24, roots)
    p16(journal, 26, 1)
    p16(journal, 28, 0)
    p16(journal, 30, 0)
    p32(journal, 32, 0)
    p16(journal, 36, 119)
    p16(journal, 38, 4096)
    p32(journal, 60, zlib.crc32(journal[:60]) & 0xFFFFFFFF)
    return bytes(journal)


def suffix_pattern(length: int) -> bytes:
    return bytes(((index * 73 + 0xC4) ^ (index >> 3)) & 0xFF for index in range(length))


def stale_sentinel() -> bytes:
    label = b"C2-C4-STALE-SESSION-ATTIC-UNREACHABLE\0"
    return (label + suffix_pattern(64))[:64]


def poison(seed: int) -> bytes:
    return bytes(((index * 29 + seed) ^ (index >> 1)) & 0xFF for index in range(256))


def validate_repair(repair: bytes, canonical: bytes) -> None:
    require(len(repair) == C2D_REGION_BYTES, "repair image is not 50,816 bytes")
    require(repair[:C2D_BYTES] == canonical, "repair prefix differs from canonical C2D")
    require(
        repair[C2D_BYTES:] == bytes(C2D_REGION_BYTES - C2D_BYTES),
        "repair suffix is not completely zero",
    )
    require(repair[C2J_OFFSET:] == bytes(C2J_BYTES), "repair leaves a nonzero C2J")


def validate_destructive(destructive: bytes, canonical: bytes, journal: bytes) -> None:
    require(len(destructive) == C2D_REGION_BYTES, "destructive image size drift")
    expected_prefix = bytearray(canonical)
    p16(expected_prefix, 10, 2)
    require(
        destructive[:C2D_BYTES] == bytes(expected_prefix),
        "destructive active prefix differs outside the generation field",
    )
    require(u16(destructive, 10) == 2, "destructive header is not generation 2")
    require(
        destructive[C2D_BYTES:C2J_OFFSET]
        == suffix_pattern(C2J_OFFSET - C2D_BYTES),
        "destructive inactive suffix drift",
    )
    require(destructive[C2J_OFFSET:] == journal, "destructive C2J drift")
    require(journal[:4] == b"C2J\0" and journal[4:6] == b"\x01\x01", "C2J identity drift")
    require(
        struct.unpack_from("<I", journal, 60)[0]
        == zlib.crc32(journal[:60]) & 0xFFFFFFFF,
        "C2J is not CRC-valid",
    )


def validate_manifest(value: dict[str, Any], canonical: bytes) -> None:
    require(value.get("format") == "lisp65-c2-destructive-restage-fixture-v1", "fixture format drift")
    require(value.get("status") == "host-qualified-hardware-not-run", "fixture status drift")
    require(value.get("product", {}).get("sha256") == EXPECTED_PRODUCT_SHA, "fixture product drift")
    reset = value.get("bank5_reset_domain", {})
    require(
        reset.get("physical_base") == C2D_BASE
        and reset.get("canonical_prefix_bytes") == C2D_BYTES
        and reset.get("region_bytes") == C2D_REGION_BYTES
        and reset.get("unwind_offset") == C2J_OFFSET,
        "fixture Bank-5 geometry drift",
    )
    scratch = reset.get("authenticated_bootstrap_scratch", {})
    require(
        scratch.get("physical_base") == BOOTSTRAP_SCRATCH_BASE
        and scratch.get("offset") == BOOTSTRAP_SCRATCH_OFFSET
        and scratch.get("bytes") == BOOTSTRAP_SCRATCH_BYTES
        and scratch.get("end_offset_exclusive") == BOOTSTRAP_SCRATCH_END,
        "fixture Boot-overlay scratch geometry drift",
    )
    require(
        BOOTSTRAP_SCRATCH_OFFSET >= C2D_BYTES
        and BOOTSTRAP_SCRATCH_END <= C2J_OFFSET,
        "authenticated Boot-overlay scratch overlaps active C2D or C2J",
    )
    require(
        value.get("hardware_sequence", {}).get("same_product_identity") is True
        and value.get("hardware_sequence", {}).get("product_links") == 0
        and value.get("hardware_sequence", {}).get("hardware_runs") == 1,
        "fixture execution-accounting drift",
    )
    require(
        value.get("ordinary_presmoke_gap", {}).get("unstaged_survivor_bytes")
        == C2D_REGION_BYTES - C2D_BYTES,
        "ordinary pre-smoke survivor-gap attribution drift",
    )
    expected_symbols = {
        "c2_ready": (0x008C, 1),
        "c2_runtime": (0xC084, 46),
        "rtov_family": (0x0079, 1),
        "rtov_family_generation": (0xBFA9, 2),
        "rtov_island_state": (0x007A, 1),
    }
    state_symbols = value.get("state_symbols", {})
    require(
        set(state_symbols) == set(expected_symbols),
        "fixture observation-symbol inventory drift",
    )
    for name, (address, size) in expected_symbols.items():
        require(
            state_symbols[name].get("address") == address
            and state_symbols[name].get("bytes") == size,
            f"fixture observation-symbol geometry drift: {name}",
        )
    require(u16(canonical, 10) == 1, "canonical generation is not one")


def mutation_suite(
    repair: bytes,
    destructive: bytes,
    canonical: bytes,
    journal: bytes,
    manifest: dict[str, Any],
) -> dict[str, str]:
    rejected: dict[str, str] = {}

    def reject(name: str, operation: Any) -> None:
        try:
            operation()
        except ContractError:
            rejected[name] = "rejected"
        else:
            raise ContractError(f"mutation unexpectedly accepted: {name}")

    reject("repair-short-prefix-only", lambda: validate_repair(repair[:C2D_BYTES], canonical))
    bad = bytearray(repair)
    bad[100] ^= 1
    reject("repair-canonical-prefix-bitflip", lambda: validate_repair(bytes(bad), canonical))
    bad = bytearray(repair)
    bad[C2D_BYTES] = 1
    reject("repair-nonzero-inactive-suffix", lambda: validate_repair(bytes(bad), canonical))
    bad = bytearray(repair)
    bad[C2J_OFFSET + 63] = 1
    reject("repair-nonzero-C2J", lambda: validate_repair(bytes(bad), canonical))
    bad = bytearray(destructive)
    p16(bad, 10, 1)
    reject(
        "destructive-generation-not-torn",
        lambda: validate_destructive(bytes(bad), canonical, journal),
    )
    bad_journal = bytearray(journal)
    bad_journal[0] ^= 1
    bad = bytearray(destructive)
    bad[C2J_OFFSET:] = bad_journal
    reject(
        "destructive-journal-wrong-magic",
        lambda: validate_destructive(bytes(bad), canonical, journal),
    )
    bad_journal = bytearray(journal)
    bad_journal[60] ^= 1
    bad = bytearray(destructive)
    bad[C2J_OFFSET:] = bad_journal
    reject(
        "destructive-journal-wrong-CRC",
        lambda: validate_destructive(bytes(bad), canonical, journal),
    )
    bad_manifest = copy.deepcopy(manifest)
    bad_manifest["bank5_reset_domain"]["region_bytes"] = C2D_REGION_BYTES - 1
    reject("reset-domain-shortened", lambda: validate_manifest(bad_manifest, canonical))
    bad_manifest = copy.deepcopy(manifest)
    bad_manifest["hardware_sequence"]["same_product_identity"] = False
    reject("different-product-identity", lambda: validate_manifest(bad_manifest, canonical))
    bad_manifest = copy.deepcopy(manifest)
    bad_manifest["ordinary_presmoke_gap"]["unstaged_survivor_bytes"] = 0
    reject("short-preload-gap-hidden", lambda: validate_manifest(bad_manifest, canonical))
    bad_manifest = copy.deepcopy(manifest)
    bad_manifest["bank5_reset_domain"]["authenticated_bootstrap_scratch"]["offset"] = C2D_BYTES - 1
    reject("bootstrap-scratch-overlaps-active-c2d", lambda: validate_manifest(bad_manifest, canonical))
    bad_manifest = copy.deepcopy(manifest)
    bad_manifest["bank5_reset_domain"]["authenticated_bootstrap_scratch"]["offset"] = C2J_OFFSET
    reject("bootstrap-scratch-overlaps-c2j", lambda: validate_manifest(bad_manifest, canonical))
    bad_manifest = copy.deepcopy(manifest)
    del bad_manifest["state_symbols"]["c2_runtime"]
    reject("observation-symbol-c2-runtime-missing", lambda: validate_manifest(bad_manifest, canonical))
    require(len(rejected) == 13, "mutation count drift")
    return rejected


def prepare(out: Path) -> dict[str, Any]:
    deployment, c2d_path, bank2_path, session_path, bootstrap_path = deployment_inputs()
    symbols = elf_symbols()
    canonical = regular(c2d_path, "canonical C2D")
    repair = canonical + bytes(C2D_REGION_BYTES - C2D_BYTES)
    journal = active_journal(canonical)
    destructive = bytearray(repair)
    p16(destructive, 10, 2)
    destructive[C2D_BYTES:C2J_OFFSET] = suffix_pattern(C2J_OFFSET - C2D_BYTES)
    destructive[C2J_OFFSET:] = journal
    sentinel = stale_sentinel()
    artifacts = {
        "bank5-repair-50816.bin": repair,
        "bank5-destructive-50816.bin": bytes(destructive),
        "active-predecessor-c2j.bin": journal,
        "zero-c2j.bin": bytes(C2J_BYTES),
        "stale-session-attic-sentinel.bin": sentinel,
        "poison-bank2-prefix.bin": poison(0x22),
        "poison-bank3-prefix.bin": poison(0x33),
        "stale-c2-ready.bin": b"\x01",
        "stale-rtov-family.bin": b"\x02",
        "stale-rtov-family-generation.bin": b"\x01\x00",
        "stale-rtov-island-state.bin": b"\x02",
    }
    out.mkdir(parents=True, exist_ok=True)
    for name, data in artifacts.items():
        write_atomic(out / name, data)

    normal_preloads = [
        row for row in deployment["preloads"] if int(row["address"], 0) != C2D_BASE
    ]
    manifest: dict[str, Any] = {
        "format": "lisp65-c2-destructive-restage-fixture-v1",
        "status": "host-qualified-hardware-not-run",
        "product": deployment["product"],
        "authority": {
            "contract": bind(CONTRACT),
            "addendum": bind(ADDENDUM),
            "reviewed_matrix": bind(MATRIX),
            "link57_structural": bind(STRUCTURAL),
            "link57_deployment": bind(DEPLOYMENT),
            "link57_elf": bind(ELF),
            "driver": bind(Path(__file__)),
            "hardware_runner": bind(RUNNER),
        },
        "bank5_reset_domain": {
            "physical_base": C2D_BASE,
            "canonical_prefix_bytes": C2D_BYTES,
            "region_bytes": C2D_REGION_BYTES,
            "unwind_offset": C2J_OFFSET,
            "unwind_bytes": C2J_BYTES,
            "canonical_source": bind(c2d_path),
            "repair": bind(out / "bank5-repair-50816.bin"),
            "destructive": bind(out / "bank5-destructive-50816.bin"),
            "authenticated_bootstrap_scratch": {
                "physical_base": BOOTSTRAP_SCRATCH_BASE,
                "offset": BOOTSTRAP_SCRATCH_OFFSET,
                "bytes": BOOTSTRAP_SCRATCH_BYTES,
                "end_offset_exclusive": BOOTSTRAP_SCRATCH_END,
                "artifact": bind(bootstrap_path),
                "write_order": "after-complete-reset-readback-before-execution",
            },
            "active_predecessor_journal": {
                "generation": u16(journal, 8),
                "old_counts": {
                    "images": u16(journal, 10),
                    "entries": u16(journal, 12),
                    "resolutions": u16(journal, 14),
                    "roots": u16(journal, 16),
                },
                "crc32": f"0x{struct.unpack_from('<I', journal, 60)[0]:08x}",
            },
        },
        "state_symbols": symbols,
        "volatile_tuple": {
            name: {
                **symbols[name],
                "patch": bind(out / patch),
            }
            for name, patch in (
                ("c2_ready", "stale-c2-ready.bin"),
                ("rtov_family", "stale-rtov-family.bin"),
                ("rtov_family_generation", "stale-rtov-family-generation.bin"),
                ("rtov_island_state", "stale-rtov-island-state.bin"),
            )
        },
        "stale_session_attic": {
            "physical_address": SESSION_ATTIC_SENTINEL,
            "artifact": bind(out / "stale-session-attic-sentinel.bin"),
            "postcondition": "byte-identical-but-unreachable",
        },
        "chip_planes": {
            "bank2": {
                "physical_base": BANK2_BASE,
                "poison": bind(out / "poison-bank2-prefix.bin"),
                "canonical": bind(bank2_path),
            },
            "bank3": {
                "physical_base": BANK3_BASE,
                "poison": bind(out / "poison-bank3-prefix.bin"),
                "canonical": bind(session_path),
            },
        },
        "normal_immutable_preloads_without_c2d": normal_preloads,
        "ordinary_presmoke_gap": {
            "ordinary_c2d_upload_bytes": C2D_BYTES,
            "required_cold_reset_domain_bytes": C2D_REGION_BYTES,
            "unstaged_survivor_bytes": C2D_REGION_BYTES - C2D_BYTES,
            "finding": (
                "the ordinary receipt-less pre-smoke uploads only the canonical "
                "prefix; C4 uses and requires the complete reset image so a "
                "surviving predecessor C2J cannot escape restage"
            ),
        },
        "hardware_sequence": {
            "same_product_identity": True,
            "negative_then_repair": True,
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 1,
            "promotion": "forbidden",
        },
        "expected_negative": {
            "c2_ready": 0,
            "session_family_published": False,
            "c2_runtime_error": 1,
            "pending_error_code": "0x25 LISP65_ERR_STDLIB_PROFILED_PRELOAD",
            "screen": "E25",
        },
        "expected_repair_preappend": {
            "c2_ready": 1,
            "family": 2,
            "generation": 1,
            "island_state": 2,
            "c2j": "all-zero",
            "header_counts": {
                "images": u16(canonical, 12),
                "entries": u16(canonical, 16),
                "resolutions": u16(canonical, 20),
                "roots": u16(canonical, 24),
            },
        },
        "manual_tail": {
            "stale_form": "(%c4-stale)",
            "stale_required_prefix": "*** vm: undefined function",
            "stale_detail_claim": "none",
            "definition": "(defun %c4fresh () 't)",
            "call": "(%c4fresh)",
            "definition_expected": "%c4fresh",
            "call_expected_case_insensitive": "t",
        },
    }
    validate_repair(repair, canonical)
    validate_destructive(bytes(destructive), canonical, journal)
    validate_manifest(manifest, canonical)
    mutations = mutation_suite(repair, bytes(destructive), canonical, journal, manifest)
    manifest["mutations"] = mutations
    manifest_path = out / "fixture.json"
    write_atomic(
        manifest_path,
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    receipt = {
        "format": "lisp65-c2-destructive-restage-contract-probe-v1",
        "recorded_on": "2026-07-23",
        "status": "passed-contract-and-host-fixture-hardware-not-run",
        "row": "C4",
        "product_identity": {
            "link": 57,
            "sha256": EXPECTED_PRODUCT_SHA,
        },
        "contract": bind(CONTRACT),
        "addendum": bind(ADDENDUM),
        "fixture": bind(manifest_path),
        "artifacts": {name: bind(out / name) for name in sorted(artifacts)},
        "source_truth": {
            "reset_survival": "Bank5-and-Attic-survive; Bank2/3-destroyed",
            "repair_span": "[0,50816)",
            "canonical_prefix": "[0,33840)",
            "zero_suffix_at-reset-write": "[33840,50816)",
            "authenticated_bootstrap_scratch_after-reset": "[34048,37333)",
            "c2j": "[50752,50816)-zero-before-ready-and-first-append",
            "session_attic": "survives-physically-but-no-active-record-reaches-it",
        },
        "ordinary_presmoke_gap": manifest["ordinary_presmoke_gap"],
        "mutations": mutations,
        "execution_accounting": {
            "product_bytes_changed": 0,
            "product_links": 0,
            "compiler_runs": 0,
            "hardware_runs": 0,
            "promotion_claim": "none",
            "acceptance_claim": "none",
        },
        "next_gate": (
            "one same-identity operator-assisted hardware run containing "
            "the fail-closed destructive branch and the full repair branch"
        ),
        "value_string": (
            "C4-contract=PASS mutations=13/13 reset-span=50816 "
            "prefix=33840 boot-scratch=3285 c2j=64zero stale-attic=unreachable "
            "link57=same hardware=not-run acceptance=blocked"
        ),
    }
    write_atomic(
        RECEIPT,
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return receipt


def check_binding(row: dict[str, Any]) -> Path:
    path = ROOT / str(row.get("path"))
    data = regular(path, "fixture binding")
    require(len(data) == row.get("bytes"), f"binding size drift: {path}")
    require(sha_bytes(data) == row.get("sha256"), f"binding SHA drift: {path}")
    return path


def verify_manifest_bindings(manifest: dict[str, Any]) -> None:
    for row in manifest["authority"].values():
        check_binding(row)
    reset = manifest["bank5_reset_domain"]
    for key in ("canonical_source", "repair", "destructive"):
        check_binding(reset[key])
    check_binding(reset["authenticated_bootstrap_scratch"]["artifact"])
    for row in manifest["volatile_tuple"].values():
        check_binding(row["patch"])
    check_binding(manifest["stale_session_attic"]["artifact"])
    for plane in manifest["chip_planes"].values():
        check_binding(plane["poison"])
        check_binding(plane["canonical"])
    for row in manifest["normal_immutable_preloads_without_c2d"]:
        check_binding(row)


def verify(out: Path) -> dict[str, Any]:
    receipt = load_json(RECEIPT, "C4 host receipt")
    require(
        receipt.get("status") == "passed-contract-and-host-fixture-hardware-not-run",
        "C4 host receipt is not passed",
    )
    manifest_path = check_binding(receipt["fixture"])
    manifest = load_json(manifest_path, "C4 fixture")
    _deployment, c2d_path, _bank2, _session, _bootstrap = deployment_inputs()
    canonical = regular(c2d_path, "canonical C2D")
    repair = regular(out / "bank5-repair-50816.bin", "repair image")
    destructive = regular(out / "bank5-destructive-50816.bin", "destructive image")
    journal = destructive[C2J_OFFSET:]
    validate_repair(repair, canonical)
    validate_destructive(destructive, canonical, journal)
    validate_manifest(manifest, canonical)
    verify_manifest_bindings(manifest)
    for row in receipt["artifacts"].values():
        check_binding(row)
    require(receipt.get("mutations") == manifest.get("mutations"), "mutation binding drift")
    return manifest


def memory(path: Path, size: int, label: str) -> bytes:
    data = regular(path, label)
    require(len(data) == size, f"{label} size: expected {size}, got {len(data)}")
    return data


def observe_negative(out: Path, bank0: Path, bank5: Path, sentinel_path: Path) -> dict[str, Any]:
    manifest = verify(out)
    low = memory(bank0, 65536, "negative Bank-0 capture")
    c2d = memory(bank5, C2D_REGION_BYTES, "negative Bank-5 capture")
    sentinel = memory(sentinel_path, 64, "negative Attic sentinel")
    symbols = {name: row["address"] for name, row in manifest["state_symbols"].items()}
    runtime = symbols["c2_runtime"]
    require(low[symbols["c2_ready"]] == 0, "negative branch published READY")
    require(low[symbols["rtov_family"]] != 2, "negative branch published Session family")
    require(low[runtime + 44] == 1, "negative branch did not retain C2_STREAM_ERR_IO")
    require(u16(c2d, 10) == 2, "negative branch lost the torn generation")
    require(c2d[C2J_OFFSET:C2J_OFFSET + 4] == b"C2J\0", "negative branch guessed C2J cleanup")
    require(
        sentinel == regular(out / "stale-session-attic-sentinel.bin", "sentinel authority"),
        "negative branch changed the stale Attic sentinel",
    )
    value = {
        "status": "passed-memory-fail-closed-screen-confirmation-pending",
        "c2_ready": 0,
        "family": low[symbols["rtov_family"]],
        "c2_runtime": {
            "phase": low[runtime + 42],
            "error": low[runtime + 44],
            "generation": u16(low, runtime + 10),
        },
        "bank5_header_generation": u16(c2d, 10),
        "c2j_magic_retained": True,
        "stale_attic_sentinel_retained": True,
        "screen_observation": {
            "expected": "E25",
            "operator_confirmed": False,
        },
        "captures": {
            "bank0": bind(bank0),
            "bank5": bind(bank5),
            "sentinel": bind(sentinel_path),
        },
    }
    write_atomic(
        out / "negative-observation.json",
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return value


def confirm_negative(out: Path, *, screen_confirmed: bool) -> dict[str, Any]:
    verify(out)
    require(screen_confirmed, "negative screen observation was not confirmed")
    path = out / "negative-observation.json"
    value = load_json(path, "negative observation")
    require(
        value.get("status")
        == "passed-memory-fail-closed-screen-confirmation-pending",
        "negative observation is not awaiting screen confirmation",
    )
    require(
        value.get("c2_ready") == 0
        and value.get("c2_runtime", {}).get("error") == 1
        and value.get("c2j_magic_retained") is True,
        "negative memory evidence drift before screen confirmation",
    )
    value["status"] = "passed-fail-closed-negative"
    value["screen_observation"]["operator_confirmed"] = True
    write_atomic(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return value


def observe_repair(
    out: Path,
    bank0: Path,
    bank2_path: Path,
    bank3_path: Path,
    bank5_path: Path,
    sentinel_path: Path,
) -> dict[str, Any]:
    manifest = verify(out)
    low = memory(bank0, 65536, "repair Bank-0 capture")
    bank2 = memory(bank2_path, 65536, "repair Bank-2 capture")
    bank3 = memory(bank3_path, 65536, "repair Bank-3 capture")
    c2d = memory(bank5_path, C2D_REGION_BYTES, "repair Bank-5 capture")
    sentinel = memory(sentinel_path, 64, "repair Attic sentinel")
    symbols = {name: row["address"] for name, row in manifest["state_symbols"].items()}
    runtime = symbols["c2_runtime"]
    expected = manifest["expected_repair_preappend"]
    require(low[symbols["c2_ready"]] == 1, "repair branch did not publish READY")
    require(low[symbols["rtov_family"]] == 2, "repair branch did not publish Session family")
    require(u16(low, symbols["rtov_family_generation"]) == 1, "repair family generation drift")
    require(low[symbols["rtov_island_state"]] == 2, "repair Island is not READY")
    require(u16(low, runtime + 10) == 1 and low[runtime + 44] == 0, "repair C2 runtime state drift")
    require(u16(c2d, 8) == 4096, "repair did not publish the inactive transient watermark")
    require(u16(c2d, 10) == 1, "repair C2D generation drift")
    for name, offset in (("images", 12), ("entries", 16), ("resolutions", 20), ("roots", 24)):
        require(u16(c2d, offset) == expected["header_counts"][name], f"repair {name} count drift")
    require(c2d[C2J_OFFSET:] == bytes(C2J_BYTES), "repair C2J is nonzero before append")
    bank2_authority = check_binding(manifest["chip_planes"]["bank2"]["canonical"])
    bank3_authority = check_binding(manifest["chip_planes"]["bank3"]["canonical"])
    require(
        bank2[:bank2_authority.stat().st_size] == regular(bank2_authority),
        "repair Bank-2 target identity mismatch",
    )
    require(
        bank3[:bank3_authority.stat().st_size] == regular(bank3_authority),
        "repair Bank-3 target identity mismatch",
    )
    require(
        sentinel == regular(out / "stale-session-attic-sentinel.bin"),
        "repair erased or changed the stale Attic sentinel",
    )
    images = u16(c2d, 12)
    images_offset = u16(c2d, 28)
    require(
        all(c2d[images_offset + image * 32] == 0 for image in range(images)),
        "repair published a Session-Attic image record",
    )
    value = {
        "status": "passed-complete-repair-before-first-append",
        "c2_ready": 1,
        "family": 2,
        "generation": 1,
        "island_state": 2,
        "header_counts": expected["header_counts"],
        "c2j_zero": True,
        "bank2_target_exact": True,
        "bank3_target_exact": True,
        "stale_attic_sentinel": "byte-identical-and-unreachable",
        "captures": {
            "bank0": bind(bank0),
            "bank2": bind(bank2_path),
            "bank3": bind(bank3_path),
            "bank5": bind(bank5_path),
            "sentinel": bind(sentinel_path),
        },
    }
    write_atomic(
        out / "repair-observation.json",
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return value


def observe_final(
    out: Path,
    bank0: Path,
    bank5_path: Path,
    *,
    stale_output: str,
    definition_output: str,
    call_output: str,
) -> dict[str, Any]:
    manifest = verify(out)
    require(
        stale_output.startswith("*** vm: undefined function"),
        "stale-name observation did not report undefined function",
    )
    require(
        definition_output == "%c4fresh",
        "fresh definition did not echo %c4fresh",
    )
    require(
        call_output.casefold() == "t",
        "fresh call did not return t",
    )
    negative = load_json(out / "negative-observation.json", "negative observation")
    repair = load_json(out / "repair-observation.json", "repair observation")
    low = memory(bank0, 65536, "final Bank-0 capture")
    c2d = memory(bank5_path, C2D_REGION_BYTES, "final Bank-5 capture")
    symbols = {name: row["address"] for name, row in manifest["state_symbols"].items()}
    baseline = manifest["expected_repair_preappend"]["header_counts"]
    require(low[symbols["c2_ready"]] == 1, "fresh append lost READY")
    require(c2d[C2J_OFFSET:] == bytes(C2J_BYTES), "fresh append left C2J nonzero")
    require(u16(c2d, 12) == baseline["images"] + 1, "fresh append image count drift")
    require(u16(c2d, 16) == baseline["entries"] + 1, "fresh append entry count drift")
    value = {
        "format": "lisp65-c2-destructive-restage-hardware-receipt-v1",
        "recorded_on": "2026-07-23",
        "status": "passed-same-identity-destructive-restage-and-repair",
        "row": "C4",
        "product_identity": manifest["product"],
        "host_contract_receipt": bind(RECEIPT),
        "negative": negative,
        "repair_preappend": repair,
        "manual_observations": {
            "stale_form": {
                "input": "(%c4-stale)",
                "observed": stale_output,
                "required_prefix": "*** vm: undefined function",
                "detail_claim": "none",
                "operator_confirmed": True,
            },
            "fresh_definition": {
                "input": "(defun %c4fresh () 't)",
                "observed": definition_output,
                "operator_confirmed": True,
            },
            "fresh_call": {
                "input": "(%c4fresh)",
                "observed": call_output,
                "operator_confirmed": True,
            },
        },
        "final": {
            "ready": 1,
            "c2j_zero": True,
            "header_counts": {
                "images": u16(c2d, 12),
                "entries": u16(c2d, 16),
                "resolutions": u16(c2d, 20),
                "roots": u16(c2d, 24),
            },
            "captures": {"bank0": bind(bank0), "bank5": bind(bank5_path)},
        },
        "claim_limit": (
            "Closes matrix row C4 for the exact Link-57 identity. "
            "It is not promotion and does not start R4/R5/R6/G5/G6."
        ),
        "value_string": (
            "C4=PASS link57=same torn-generation=reject-before-ready "
            "repair-span=50816 c2j=zero stale-attic=unreachable "
            "fresh-append=pass acceptance-chain=still-blocked-by-other-open-rows"
        ),
    }
    hardware_receipt = (
        ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
        "c2.2-product-link57-destructive-restage-hardware-receipt.json"
    )
    write_atomic(
        hardware_receipt,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "prepare",
            "verify",
            "observe-negative",
            "confirm-negative",
            "observe-repair",
            "observe-final",
        ),
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--bank0", type=Path)
    parser.add_argument("--bank2", type=Path)
    parser.add_argument("--bank3", type=Path)
    parser.add_argument("--bank5", type=Path)
    parser.add_argument("--sentinel", type=Path)
    parser.add_argument("--stale-output", default="")
    parser.add_argument("--definition-output", default="")
    parser.add_argument("--call-output", default="")
    parser.add_argument("--confirm-negative-screen", action="store_true")
    args = parser.parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    def rooted(path: Path | None) -> Path | None:
        if path is None or path.is_absolute():
            return path
        return ROOT / path

    bank0 = rooted(args.bank0)
    bank2 = rooted(args.bank2)
    bank3 = rooted(args.bank3)
    bank5 = rooted(args.bank5)
    sentinel = rooted(args.sentinel)
    try:
        if args.action == "prepare":
            value = prepare(out)
        elif args.action == "verify":
            value = verify(out)
        elif args.action == "observe-negative":
            require(bank0 is not None and bank5 is not None and sentinel is not None, "negative observation paths missing")
            value = observe_negative(out, bank0, bank5, sentinel)
        elif args.action == "confirm-negative":
            value = confirm_negative(
                out,
                screen_confirmed=args.confirm_negative_screen,
            )
        elif args.action == "observe-repair":
            require(
                all(path is not None for path in (bank0, bank2, bank3, bank5, sentinel)),
                "repair observation paths missing",
            )
            value = observe_repair(out, bank0, bank2, bank3, bank5, sentinel)  # type: ignore[arg-type]
        else:
            require(bank0 is not None and bank5 is not None, "final observation paths missing")
            value = observe_final(
                out,
                bank0,
                bank5,
                stale_output=args.stale_output,
                definition_output=args.definition_output,
                call_output=args.call_output,
            )
    except ContractError as exc:
        parser.error(str(exc))
    status = value.get("status", "ok") if isinstance(value, dict) else "ok"
    print(f"c2-destructive-restage-{args.action}: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
