#!/usr/bin/env python3
"""Re-emit Link-71 defstruct media with the canonical SESS record identity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any
import zlib


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_foundations_gate as FOUNDATION  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402


OLD_BUILD = ROOT / (
    "build/post-promotion/link71-defstruct-product-identity-media-rebind")
BUILD = ROOT / (
    "build/post-promotion/link71-defstruct-session-record-identity-rebind")
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
NOTE = ROOT / (
    "docs/planning/c2.2-defstruct-session-record-identity-rebind.md")
CONTRACT = ROOT / "config/c2-session-extension-contract.json"
PRIOR_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link71-defstruct-product-identity-media-rebind-receipt.json")
HOLD_RECEIPT = ROOT / (
    "tests/fixtures/c2-migration-evidence/"
    "c2.2-link71-product-identity-pre-rollback-hold-"
    "nonpromotable-receipt.json")
HOLD = ROOT / (
    "build/post-promotion/link71-defstruct-product-identity-"
    "pre-rollback-hold-NONPROMOTABLE")
LINK_ELF = ROOT / (
    "build/post-promotion/link71-defstruct-header-crc-domain/"
    "final/lisp65-c2-substitution-linked.prg.elf")
RUNTIME = ROOT / (
    "build/post-promotion/link71-defstruct-header-crc-domain/"
    "wplto/generated-product-sources/c2_product_runtime.c")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link71-defstruct-session-record-identity-media-rebind-receipt.json")


class RebindError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RebindError(message)


def load(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"authority absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def rejected(label: str, action: Any) -> str:
    try:
        action()
    except (L65I.S.ProbeError, L65I.GateError) as error:
        return str(error)
    raise RebindError(f"mutation survived: {label}")


def capture_truth() -> dict[str, Any]:
    captures = []
    for index in range(1, 4):
        directory = HOLD / f"capture-{index}"
        captures.append({
            name: (directory / f"{name}.bin").read_bytes()
            for name in ("zero-page", "rtov-tail", "phase-scratch", "c2j")
        })
    for name in captures[0]:
        require(
            captures[0][name] == captures[1][name] == captures[2][name],
            f"pre-rollback {name} is not time-stable")
    phase = captures[0]["phase-scratch"]
    require(len(phase) == 304, "phase-scratch capture width")
    require(
        int.from_bytes(phase[50:52], "little") == 1925,
        "mounted PLACE length witness")
    require(
        phase[302:304] == bytes((23, 0x81)),
        "primary first-error stamp is not locked envelope slot 23")
    old_place = (OLD_BUILD / "place.l65s").read_bytes()
    require(
        phase[182:214] == old_place[32:64],
        "captured envelope record differs from mounted PLACE")
    require(
        phase[182:186] == b"plac"
        and phase[182:186] != L65I.S.SESSION_RECORD_ID[:4],
        "captured record does not expose the record-identity divergence")
    require(
        captures[0]["c2j"] == bytes(64),
        "envelope failure unexpectedly opened C2J")
    return {
        "primary_slot": 23,
        "primary_slot_name": "c2-append-envelope",
        "capture_count": 3,
        "captured_record_identity": phase[182:190].hex(),
        "linked_required_identity": L65I.S.SESSION_RECORD_ID[:4].decode(),
        "mounted_artifact_bytes": 1925,
        "C2J": "64 zero bytes",
        "phase_scratch": bind(HOLD / "capture-1/phase-scratch.bin"),
        "registers": bind(HOLD / "register-captures.json"),
        "held_bank5": bind(HOLD / "held-bank5.bin"),
    }


def main() -> int:
    try:
        require(not RECEIPT.exists(), "session-record receipt is one-shot")
        profile = load(PROFILE)
        contract = load(CONTRACT)
        prior = load(PRIOR_RECEIPT)
        product_build_id = int(profile["product_build_id"], 0)
        require(
            product_build_id == 0xF5FE97C0
            and prior["correction"]["canonical_product_build_id"]
                == f"0x{product_build_id:08x}",
            "canonical Link-71 product identity drift")
        require(
            contract["extension_envelope"]["record_identity"].startswith(
                "record bytes 0..3 are the fixed ASCII tag SESS")
            and prior["media"]["D81"]["sha256"] == bind(
                OLD_BUILD / "require-defstruct-product-bound.d81")["sha256"],
            "contract or predecessor media authority drift")
        runtime = RUNTIME.read_text(encoding="utf-8")
        require(
            "w->record[0] != 'S'" in runtime
            and "w->record[1] != 'E'" in runtime
            and "w->record[2] != 'S'" in runtime
            and "w->record[3] != 'S'" in runtime,
            "linked product SESS verifier drift")
        first_red = capture_truth()

        BUILD.mkdir(parents=True, exist_ok=True)
        manifests = (
            ("place", "place", "place",
             ROOT / "build/post-promotion/defstruct-v1/foundations/"
                    "place.manifest.json", ()),
            ("defstruct", "defstruct", "dfstrct",
             ROOT / "build/post-promotion/defstruct-v1/foundations/"
                    "defstruct.manifest.json", (0,)),
        )
        placeholder: list[dict[str, Any]] = []
        artifacts: dict[str, bytes] = {}
        paths: list[tuple[Path, str]] = []
        artifact_deltas: dict[str, list[int]] = {}
        identity_negatives: dict[str, str] = {}
        for number, (name, image_key, shelf_name, manifest,
                     dependencies) in enumerate(manifests):
            row, artifact = FOUNDATION.measured_row(
                name, image_key, shelf_name, manifest, dependencies,
                1, number + 1, product_build_id=product_build_id)
            old = (OLD_BUILD / f"{name}.l65s").read_bytes()
            require(
                len(old) == len(artifact)
                and artifact[32:40] == L65I.S.SESSION_RECORD_ID
                and artifact[64:] == old[64:]
                and artifact[22:26] == old[22:26],
                f"{name} changed outside record identity/catalog domain")
            delta = [
                offset for offset, (before, after)
                in enumerate(zip(old, artifact)) if before != after]
            require(
                set(delta) <= set(range(18, 22)) | set(range(32, 40))
                and set(range(18, 22)) <= set(delta)
                and any(offset < 36 for offset in delta if offset >= 32),
                f"{name} unexpected record rebind delta: {delta}")
            decoded = L65I.S.decode_extension(
                artifact, expected_build_id=product_build_id)
            candidate = bytearray(artifact)
            candidate[32] = ord("X")
            struct.pack_into(
                "<I", candidate, 18,
                zlib.crc32(candidate[32:64]) & 0xFFFFFFFF)
            identity_negatives[name] = rejected(
                f"{name}-record-identity",
                lambda data=bytes(candidate): L65I.S.decode_extension(
                    data, expected_build_id=product_build_id))
            require(
                decoded.combined_crc
                    == struct.unpack_from("<I", old, 58)[0],
                f"{name} combined identity drift")
            placeholder.append(row)
            artifacts[name] = artifact
            path = BUILD / f"{name}.l65s"
            path.write_bytes(artifact)
            paths.append((path, name))
            artifact_deltas[name] = delta

        seed_index = BUILD / "l65index.seed"
        seed_index.write_bytes(L65I.encode_index(placeholder))
        seed_d81 = BUILD / "require-defstruct.seed.d81"
        L65I.build_d81(seed_d81, seed_index, paths)
        locators = L65I.d81_locators(seed_d81)
        rows = []
        for name, image_key, shelf_name, manifest, dependencies in manifests:
            row, artifact = FOUNDATION.measured_row(
                name, image_key, shelf_name, manifest, dependencies,
                *locators[name], product_build_id=product_build_id)
            require(artifact == artifacts[name], f"{name} emission drift")
            rows.append(row)
        index = L65I.encode_index(rows)
        index_path = BUILD / "l65index"
        index_path.write_bytes(index)
        require(
            index == (OLD_BUILD / "l65index").read_bytes(),
            "L65I changed despite record-local identity removal")
        decoded_rows = L65I.decode_index(
            index, artifacts, artifact_build_id=product_build_id)
        require(
            L65I.resolve(decoded_rows, "defstruct", 7, [], L65I.CAPACITY)
                == [0, 1],
            "dependency resolution drift")
        mutations = L65I.mutation_gate(
            index, artifacts, artifact_build_id=product_build_id)

        d81 = BUILD / "require-defstruct-sess-bound.d81"
        L65I.build_d81(d81, index_path, paths)
        require(
            L65I.d81_locators(d81) == locators,
            "successor D81 locator drift")
        visible = L65I.D81.visible_files(d81.read_bytes())
        require(
            visible[b"L65INDEX"] == index
            and visible[b"PLACE"] == artifacts["place"]
            and visible[b"DEFSTRUCT"] == artifacts["defstruct"],
            "successor D81 visible-file truth drift")
        old_d81 = (OLD_BUILD / "require-defstruct-product-bound.d81").read_bytes()
        new_d81 = d81.read_bytes()
        d81_delta = [
            offset for offset, (before, after)
            in enumerate(zip(old_d81, new_d81)) if before != after]
        expected_changed = sum(len(value) for value in artifact_deltas.values())
        require(
            len(old_d81) == len(new_d81)
            and len(d81_delta) == expected_changed,
            "D81 changed outside the two artifact record domains")

        source = (
            ROOT / "tools/host-lisp/c2_session_extension_probe.py"
        ).read_text(encoding="utf-8")
        require(
        'SESSION_RECORD_ID = b"SESS\\0\\0\\0\\0"' in source
            and "candidate[32:40] = SESSION_RECORD_ID" in source
            and "record[:4] == SESSION_RECORD_ID[:4]" in source
            and '"session-record-identity"' in source,
            "permanent session-record emitter/decoder gate drift")

        value = {
            "format":
                "lisp65-c2.2-link71-defstruct-session-record-rebind-v1",
            "recorded_on": "2026-07-27",
            "status":
                "passed-canonical-SESS-media-rebind-host-gate",
            "promotable": False,
            "product_bytes_delta": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "first_red": first_red,
            "correction": {
                "format": "L65S-v4 unchanged",
                "record_identity": "SESS",
                "library_name_authority": "L65I-v1 only",
                "artifact_deltas": artifact_deltas,
                "code_and_C2I": "byte-identical",
                "per_region_and_combined_CRC32": "byte-identical",
                "catalog_CRC32": "recomputed over canonical SESS record",
                "artifact_widths": "byte-identical",
                "L65I": "byte-identical",
                "identity_negatives": identity_negatives,
                "index_mutations_rejected": len(mutations),
            },
            "media": {
                "locators": {
                    name: {"track": at[0], "sector": at[1]}
                    for name, at in locators.items()
                },
                "index": bind(index_path),
                "place": bind(BUILD / "place.l65s"),
                "defstruct": bind(BUILD / "defstruct.l65s"),
                "D81": bind(d81),
                "D81_changed_bytes": d81_delta,
            },
            "linked_consumer": {
                "ELF": bind(LINK_ELF),
                "required_record_identity": "SESS",
                "product_change": "none",
            },
            "authority": {
                "profile": bind(PROFILE),
                "contract": bind(CONTRACT),
                "contract_note": bind(NOTE),
                "predecessor": bind(PRIOR_RECEIPT),
                "diagnostic": bind(HOLD_RECEIPT),
                "driver": bind(Path(__file__).resolve()),
            },
            "next_gate":
                "artifact-side Link-71 replay with the SESS-bound D81; "
                "no successor product link required",
            "claim_limit":
                "Host/media correction only; no hardware require or "
                "defstruct runtime claim.",
        }
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(
            "c2-defstruct-session-record-identity-rebind: PASS "
            f"record=SESS index-mutations={len(mutations)} "
            f"d81-delta={len(d81_delta)}")
        return 0
    except (
        OSError, ValueError, KeyError, json.JSONDecodeError, RebindError,
        FOUNDATION.FoundationError, L65I.GateError, L65I.S.ProbeError,
    ) as error:
        print(
            "c2-defstruct-session-record-identity-rebind: FIRST RED: "
            + str(error),
            file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
