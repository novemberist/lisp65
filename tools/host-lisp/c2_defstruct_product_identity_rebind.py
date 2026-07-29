#!/usr/bin/env python3
"""Re-emit Link-71 defstruct media with the canonical product build identity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_defstruct_foundations_gate as FOUNDATION  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402


OLD_BUILD = ROOT / "build/post-promotion/defstruct-v1/foundations"
BUILD = ROOT / (
    "build/post-promotion/link71-defstruct-product-identity-media-rebind")
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
NOTE = ROOT / "docs/planning/c2.2-defstruct-product-identity-rebind.md"
LINK_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-product-link71-defstruct-header-crc-domain-structural-receipt.json")
WPLTO_RAW = ROOT / (
    "build/post-promotion/link71-defstruct-header-crc-domain/"
    "receipts/wplto-raw.json")
SUBSTITUTION = ROOT / (
    "build/post-promotion/link71-defstruct-header-crc-domain/"
    "static-plane/narrow-static/product/substitution-artifacts.json")
LINK_ELF = ROOT / (
    "build/post-promotion/link71-defstruct-header-crc-domain/"
    "final/lisp65-c2-substitution-linked.prg.elf")
PRE_ROLLBACK = ROOT / (
    "tests/fixtures/c2-migration-evidence/"
    "c2.2-link71-pre-rollback-hold-v3-mount-preserved-"
    "nonpromotable-receipt.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-link71-defstruct-product-identity-media-rebind-receipt.json")


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


def main() -> int:
    try:
        require(not RECEIPT.exists(), "identity-rebind receipt is one-shot")
        profile = load(PROFILE)
        link = load(LINK_RECEIPT)
        wplto = load(WPLTO_RAW)
        substitution = load(SUBSTITUTION)
        pre_rollback = load(PRE_ROLLBACK)
        product_build_id = int(profile["product_build_id"], 0)
        require(
            0 < product_build_id <= 0xFFFFFFFF
            and int(
                wplto["canonical_artifact_profile_gate"][
                    "c2d_product_build_id"], 0) == product_build_id
            and substitution["product_build_id_u32"] == product_build_id
            and int(substitution["product_build_id_hex"], 0)
                == product_build_id,
            "canonical profile/WPLTO/static-plane build identity drift")
        require(
            link["status"].startswith("passed-Link71-")
            and link["ELF"]["sha256"] == bind(LINK_ELF)["sha256"],
            "Link-71 product/ELF authority drift")
        require(
            pre_rollback["status"]
                == "ready-mount-reset-before-product-load-nonpromotable"
            and pre_rollback["promotable"] is False,
            "pre-rollback mounted-media witness drift")

        BUILD.mkdir(parents=True, exist_ok=True)
        manifests = (
            ("place", "place", "place",
             OLD_BUILD / "place.manifest.json", ()),
            ("defstruct", "defstruct", "dfstrct",
             OLD_BUILD / "defstruct.manifest.json", (0,)),
        )
        placeholder: list[dict[str, Any]] = []
        artifacts: dict[str, bytes] = {}
        paths: list[tuple[Path, str]] = []
        byte_deltas: dict[str, list[int]] = {}
        identity_negatives: dict[str, str] = {}
        for number, (name, image_key, shelf_name, manifest,
                     dependencies) in enumerate(manifests):
            row, artifact = FOUNDATION.measured_row(
                name, image_key, shelf_name, manifest, dependencies,
                1, number + 1, product_build_id=product_build_id)
            old = (OLD_BUILD / f"{name}.l65s").read_bytes()
            require(len(old) == len(artifact), f"{name} width drift")
            delta = [
                offset for offset, (before, after)
                in enumerate(zip(old, artifact)) if before != after]
            require(delta == [22, 23, 24, 25],
                    f"{name} changed outside build identity: {delta}")
            require(
                struct.unpack_from("<I", old, 22)[0]
                    == L65I.S.PROBE_BUILD_ID
                and struct.unpack_from("<I", artifact, 22)[0]
                    == product_build_id,
                f"{name} old/new build identity drift")
            identity_negatives[f"{name}-old-private"] = rejected(
                f"{name}-old-private",
                lambda data=old: L65I.S.decode_extension(
                    data, expected_build_id=product_build_id))
            identity_negatives[f"{name}-new-as-probe"] = rejected(
                f"{name}-new-as-probe",
                lambda data=artifact: L65I.S.decode_extension(data))
            for byte_index in range(4):
                candidate = bytearray(artifact)
                candidate[22 + byte_index] ^= 1
                identity_negatives[f"{name}-identity-byte-{byte_index}"] = (
                    rejected(
                        f"{name}-identity-byte-{byte_index}",
                        lambda data=bytes(candidate):
                            L65I.S.decode_extension(
                                data, expected_build_id=product_build_id)))
            placeholder.append(row)
            artifacts[name] = artifact
            path = BUILD / f"{name}.l65s"
            path.write_bytes(artifact)
            paths.append((path, name))
            byte_deltas[name] = delta

        seed_index = BUILD / "l65index.seed"
        seed_index.write_bytes(L65I.encode_index(placeholder))
        seed_d81 = BUILD / "require-defstruct.seed.d81"
        L65I.build_d81(seed_d81, seed_index, paths)
        locators = L65I.d81_locators(seed_d81)
        rows: list[dict[str, Any]] = []
        for name, image_key, shelf_name, manifest, dependencies in manifests:
            require(name in locators, f"locator absent: {name}")
            row, artifact = FOUNDATION.measured_row(
                name, image_key, shelf_name, manifest, dependencies,
                *locators[name], product_build_id=product_build_id)
            require(artifact == artifacts[name], f"{name} emission drift")
            rows.append(row)
        index = L65I.encode_index(rows)
        index_path = BUILD / "l65index"
        index_path.write_bytes(index)
        require(index == (OLD_BUILD / "l65index").read_bytes(),
                "L65I changed despite identity-only envelope rebind")
        decoded = L65I.decode_index(
            index, artifacts, artifact_build_id=product_build_id)
        require(
            L65I.resolve(decoded, "defstruct", 7, [], L65I.CAPACITY)
                == [0, 1],
            "canonical dependency resolution drift")
        mutations = L65I.mutation_gate(
            index, artifacts, artifact_build_id=product_build_id)

        d81 = BUILD / "require-defstruct-product-bound.d81"
        L65I.build_d81(d81, index_path, paths)
        require(L65I.d81_locators(d81) == locators,
                "final D81 locator drift")
        visible = L65I.D81.visible_files(d81.read_bytes())
        require(
            visible[b"L65INDEX"] == index
            and visible[b"PLACE"] == artifacts["place"]
            and visible[b"DEFSTRUCT"] == artifacts["defstruct"],
            "final D81 visible-file truth drift")
        old_d81 = (OLD_BUILD / "require-defstruct.d81").read_bytes()
        new_d81 = d81.read_bytes()
        require(len(old_d81) == len(new_d81), "D81 image width drift")
        d81_delta = [
            offset for offset, (before, after)
            in enumerate(zip(old_d81, new_d81)) if before != after]
        require(len(d81_delta) == 8,
                f"D81 changed outside two build identities: {d81_delta}")

        source = (
            ROOT / "tools/host-lisp/c2_defstruct_foundations_gate.py"
        ).read_text(encoding="utf-8")
        extension_source = (
            ROOT / "tools/host-lisp/c2_session_extension_probe.py"
        ).read_text(encoding="utf-8")
        runtime = (ROOT / "src/c2_product_runtime.c").read_text(
            encoding="utf-8")
        require(
            'PRODUCT_PROFILE = ROOT / "config/c2-l-full-product-profile.json"'
                in source
            and "product_build_id=product_build_id" in source
            and "build_id: int = PROBE_BUILD_ID" in extension_source
            and "expected_build_id: int = PROBE_BUILD_ID" in extension_source
            and "c2_stage_u32(22u) != "
                "(uint32_t)LISP65_C2_PRODUCT_BUILD_ID" in runtime,
            "permanent product-identity source gate drift")

        value = {
            "format":
                "lisp65-c2.2-link71-defstruct-product-identity-rebind-v1",
            "recorded_on": "2026-07-27",
            "status":
                "passed-canonical-product-identity-media-rebind-host-gate",
            "promotable": False,
            "product_bytes_delta": 0,
            "product_links": 0,
            "hardware_runs": 0,
            "first_red": {
                "primary_slot": 23,
                "mounted_artifact_bytes": 1925,
                "record_copy_reached": False,
                "artifact_build_id":
                    f"0x{L65I.S.PROBE_BUILD_ID:08x}",
                "linked_expected_build_id":
                    f"0x{product_build_id:08x}",
                "cause":
                    "product emitter and host decoder shared the private "
                    "PROBE_BUILD_ID instead of consuming canonical profile",
            },
            "correction": {
                "format": "L65S-v4 unchanged",
                "changed_header_offsets": [22, 23, 24, 25],
                "byte_deltas": byte_deltas,
                "code_metadata_records_and_CRCs": "byte-identical",
                "L65I": "byte-identical",
                "canonical_product_build_id":
                    f"0x{product_build_id:08x}",
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
                "WPLTO_build_id":
                    wplto["canonical_artifact_profile_gate"][
                        "c2d_product_build_id"],
                "static_plane_build_id":
                    substitution["product_build_id_hex"],
                "runtime_check":
                    "c2_stage_u32(22) equals "
                    "LISP65_C2_PRODUCT_BUILD_ID",
            },
            "authority": {
                "profile": bind(PROFILE),
                "contract_note": bind(NOTE),
                "link_receipt": bind(LINK_RECEIPT),
                "WPLTO": bind(WPLTO_RAW),
                "static_plane": bind(SUBSTITUTION),
                "pre_rollback_witness": bind(PRE_ROLLBACK),
                "driver": bind(Path(__file__).resolve()),
            },
            "next_gate":
                "artifact-side Link-71 hardware replay with the newly named "
                "product-bound D81; no successor product link required",
            "claim_limit":
                "Host/media identity correction only; no hardware require or "
                "defstruct runtime claim.",
        }
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(
            "c2-defstruct-product-identity-rebind: PASS "
            f"build-id=0x{product_build_id:08x} "
            f"identity-negatives={len(identity_negatives)} "
            f"index-mutations={len(mutations)}")
        return 0
    except (
        OSError, ValueError, KeyError, json.JSONDecodeError, RebindError,
        FOUNDATION.FoundationError, L65I.GateError, L65I.S.ProbeError,
    ) as error:
        print(
            "c2-defstruct-product-identity-rebind: FIRST RED: " + str(error),
            file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
