#!/usr/bin/env python3
"""Attribute the Link-95 ``require inspect`` First Red without hardware.

The delivered Link-95 media pair mixed a Link-95 product with the byte-exact
Link-93 inspect library.  This gate binds both product worlds, decodes the
actual L65I/L65S pair under each world identity, and identifies the first
target rejection.  It deliberately distinguishes two different claims:

* the library is product-world coupled through its L65S product build id;
* it is *not* coupled through fixed product Directory ordinals.  Its C2I
  descriptors contain symbols and local pairs, but no ENTRY/EXPORT/NATIVE
  descriptors.

This is an attribution gate only.  The counterfactual Link-95 envelope exists
only in memory to prove that the four-byte build identity is the sole failed
envelope predicate; no library, medium, product, or device state is changed.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import c2_full_emission as F  # noqa: E402
import c2_require_resolver_gate as L65I  # noqa: E402
import c2_session_extension_probe as S  # noqa: E402
from elf_truth import ElfTruth  # noqa: E402


LINK95 = ROOT / "build/c2.3/packed-callee-closure-link95"
LINK93 = ROOT / "build/c2.3/trace-core-abi-link93-r6"
LINK95_C2D = LINK95 / (
    "static-plane/narrow-static/v6-semantics/initial.c2d-v6.bin"
)
LINK93_C2D = LINK93 / (
    "static-plane/narrow-static/v6-semantics/initial.c2d-v6.bin"
)
LINK95_MANIFEST = LINK95 / "canonical-product-manifest.json"
LINK93_MANIFEST = LINK93 / "canonical-product-manifest.json"
LINK95_ELF = LINK95 / "final/lisp65-c2-substitution-linked.prg.elf"
LINK95_RUNTIME = LINK95 / "final/generated-product-sources/c2_product_runtime.c"
READOBJ = ROOT / "tools/llvm-mos/bin/llvm-readobj"

MEDIA = ROOT / "build/c2.3/packed-callee-link95-acceptance-media"
LIBRARY = MEDIA / "trace-library"
INSPECT = LIBRARY / "inspect.l65s"
INDEX = LIBRARY / "l65index"
LIBRARY_D81 = LIBRARY / "lisp65-library.d81"
PRODUCT_D81 = MEDIA / "shared-system/lisp65-product.d81"
MEDIA_PRODUCER = ROOT / "tools/host-lisp/c2_link95_acceptance_media.py"
RUNTIME = ROOT / "src/c2_product_runtime.c"
VM = ROOT / "src/vm.c"
REQUIRE = ROOT / "lib/stdlib-require.lisp"

FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-require-inspect-hardware-first-red.json"
)
LINK93_GREEN = LINK93 / "device-session-corrected/row-require-inspect.txt"
MEDIA_RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-media-closure-receipt.json"
)
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-link95-library-world-attribution-receipt.json"
)

FORMAT = "lisp65-c2.3-link95-library-world-attribution-v1"
RECORDED_ON = "2026-08-10"
LINK93_ID = 0x3B48650D
LINK95_ID = 0x14D980C3
EXPECTED_LIBRARY_D81 = (
    "5e282937436e6d2656590490734d800fcd9fecb4b3a740a3ec39009cdeb5a1bd"
)
EXPECTED_PRODUCT_D81 = (
    "b58d41997e8a2e78f8f79065029097b9bcb03d136cab202f01e2cc9b5c2f951d"
)


class AttributionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise AttributionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": sha(raw),
    }


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def c2d_identity(path: Path, expected: dict[str, int]) -> dict[str, Any]:
    raw = path.read_bytes()
    require(
        len(raw) == S.C2D_TOTAL_BYTES and raw[:8] == b"C2D\0\x06\x30\x20\x0a",
        f"C2D-v6 identity/geometry drift: {path}",
    )
    u16 = lambda at: struct.unpack_from("<H", raw, at)[0]
    u32 = lambda at: struct.unpack_from("<I", raw, at)[0]
    result = {
        "generation": u16(10),
        "images": u16(12),
        "entries": u16(16),
        "resolutions": u16(20),
        "roots": u16(24),
        "immutable_images": u16(38),
        "catalog_crc32": u32(40),
        "product_build_id": u32(44),
    }
    require(
        all(result[key] == value for key, value in expected.items()),
        f"C2D product-world drift: {path}: {result}",
    )
    return result | {"artifact": bind(path)}


def product_manifest(path: Path, expected_id: int) -> dict[str, Any]:
    manifest = load(path)
    static = manifest.get("static_plane", {})
    require(
        static.get("product_build_id") == f"0x{expected_id:08x}"
        and manifest.get("status")
            == "passed-fresh-source-product-and-post-link-completion",
        f"canonical product manifest world drift: {path}",
    )
    return {
        "artifact": bind(path),
        "product_build_id": static["product_build_id"],
        "entries": static.get("entries"),
        "resolutions": static.get("resolutions"),
        "roots": static.get("roots"),
        "linked_elf_sha256": manifest["identity"]["linked_elf_sha256"],
    }


def envelope_predicates(data: bytes, expected_id: int) -> dict[str, bool]:
    """Evaluate the target envelope's ordered header predicates independently."""
    return {
        "length": 88 <= len(data) <= 8192,
        "magic_version_widths_count": (
            len(data) >= 64
            and data[:8] == b"L65S\x04\x20\x20\x01"
        ),
        "catalog_offset": len(data) >= 10 and struct.unpack_from("<H", data, 8)[0] == 32,
        "payload_offset": len(data) >= 13 and S.u24(data, 10) == 64,
        "total_length": len(data) >= 16 and S.u24(data, 13) == len(data),
        "catalog_bytes": len(data) >= 18 and struct.unpack_from("<H", data, 16)[0] == 32,
        "product_build_id": (
            len(data) >= 26 and struct.unpack_from("<I", data, 22)[0] == expected_id
        ),
        "generation": len(data) >= 28 and struct.unpack_from("<H", data, 26)[0] == 1,
        "header_reserved": len(data) >= 32 and data[28:32] == bytes(4),
        "record_identity": len(data) >= 36 and data[32:36] == b"SESS",
        "record_flags": len(data) >= 64 and data[62:64] == b"\x01\x00",
    }


def decoder_rejection(action: Callable[[], Any]) -> str:
    try:
        action()
    except (S.ProbeError, L65I.GateError) as error:
        return str(error)
    raise AttributionError("cross-world artifact unexpectedly decoded")


def library_worlds() -> dict[str, Any]:
    artifact = INSPECT.read_bytes()
    index = INDEX.read_bytes()
    actual_id = struct.unpack_from("<I", artifact, 22)[0]
    require(actual_id == LINK93_ID, "inspect envelope is no longer Link-93-bound")

    link93_extension = S.decode_extension(artifact, expected_build_id=LINK93_ID)
    link93_rows = L65I.decode_index(
        index, {"inspect": artifact}, artifact_build_id=LINK93_ID
    )
    require(len(link93_rows) == 1 and link93_rows[0]["name"] == "inspect",
            "Link-93 inspect index identity drift")

    link95_envelope_rejection = decoder_rejection(
        lambda: S.decode_extension(artifact, expected_build_id=LINK95_ID)
    )
    link95_index_rejection = decoder_rejection(
        lambda: L65I.decode_index(
            index, {"inspect": artifact}, artifact_build_id=LINK95_ID
        )
    )
    require(
        link95_envelope_rejection == "extension product build identity"
        and link95_index_rejection == "extension product build identity",
        "Link-95 rejection is no longer the product build identity",
    )

    predicates_93 = envelope_predicates(artifact, LINK93_ID)
    predicates_95 = envelope_predicates(artifact, LINK95_ID)
    require(all(predicates_93.values()), "Link-93 envelope predicate drift")
    failed_95 = [name for name, passed in predicates_95.items() if not passed]
    require(failed_95 == ["product_build_id"],
            f"cross-world envelope has more than one failed predicate: {failed_95}")

    # Diagnostic-only counterfactual: change no payload, CRC, index or medium.
    patched = bytearray(artifact)
    struct.pack_into("<I", patched, 22, LINK95_ID)
    counterfactual = bytes(patched)
    decoded_95 = S.decode_extension(counterfactual, expected_build_id=LINK95_ID)
    rows_95 = L65I.decode_index(
        index, {"inspect": counterfactual}, artifact_build_id=LINK95_ID
    )
    require(
        decoded_95.combined_crc == link93_extension.combined_crc
        and rows_95 == link93_rows
        and counterfactual[0:22] == artifact[0:22]
        and counterfactual[26:] == artifact[26:],
        "four-byte identity counterfactual changed content semantics",
    )

    decoded_c2i = F.decode_c2i(
        link93_extension.image.code,
        link93_extension.image.metadata,
        declared_exports=None,
    )
    counts = {str(kind): 0 for kind in range(F.K_SYMBOL + 1)}
    for descriptor in decoded_c2i["descriptors"]:
        counts[str(descriptor.kind)] += 1
    fixed = {
        "K_ENTRY": counts[str(F.K_ENTRY)],
        "K_EXPORT": counts[str(F.K_EXPORT)],
        "K_NATIVE": counts[str(F.K_NATIVE)],
    }
    require(
        fixed == {"K_ENTRY": 0, "K_EXPORT": 0, "K_NATIVE": 0}
        and counts[str(F.K_SYMBOL)] == 197
        and counts[str(F.K_PAIR)] == 211
        and counts[str(F.K_NIL)] == 1,
        f"inspect descriptor-world identity drift: {counts}",
    )

    row = link93_rows[0]
    return {
        "delivered": {
            "inspect": bind(INSPECT),
            "index": bind(INDEX),
            "library_D81": bind(LIBRARY_D81),
            "product_D81": bind(PRODUCT_D81),
            "L65S_product_build_id": f"0x{actual_id:08x}",
            "index_row": row,
        },
        "decode_matrix": {
            "Link93": "passed envelope and index",
            "Link95_envelope": link95_envelope_rejection,
            "Link95_index": link95_index_rejection,
            "Link95_failed_predicates": failed_95,
        },
        "counterfactual_only_in_memory": {
            "changed_offsets": [22, 23, 24, 25],
            "new_build_id": f"0x{LINK95_ID:08x}",
            "envelope": "passed",
            "index": "passed",
            "combined_crc32_unchanged": f"0x{decoded_95.combined_crc:08x}",
            "artifact_written": False,
        },
        "packed_reference_binding": {
            "entries": len(decoded_c2i["entries"]),
            "descriptors": len(decoded_c2i["descriptors"]),
            "kind_counts": counts,
            "fixed_product_reference_counts": fixed,
            "ordinal_subhypothesis": "rejected",
            "reason": (
                "The library carries no K_ENTRY, K_EXPORT or K_NATIVE descriptor; "
                "its product-world coupling is the L65S header build identity."
            ),
        },
    }


def linked_path() -> dict[str, Any]:
    truth = ElfTruth.read(LINK95_ELF, llvm_readobj=READOBJ)
    expected = {
        "c2_append_envelope_phase": (0xC356, 1478, ".lisp65_rt_c2append_envelope"),
        "c2_append_begin": (0xE7E4, 513, ".lisp65_c2_kernal_window.c2_resident"),
        "c2_product_append_staged": (0x24CB, 116, ".text"),
        "c2_product_install": (0x253F, 620, ".text"),
        "vm_callprim": (0x6AA0, 4746, ".text"),
    }
    symbols: dict[str, Any] = {}
    for name, (value, size, section) in expected.items():
        symbol = truth.symbol(name)
        require(
            (symbol.value, symbol.bytes, symbol.section, symbol.symbol_type)
            == (value, size, section, "Function"),
            f"linked path symbol drift: {name}",
        )
        symbols[name] = {
            "VMA": f"0x{value:04x}", "bytes": size, "section": section,
        }

    generated = LINK95_RUNTIME.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    vm = VM.read_text(encoding="utf-8")
    require_source = REQUIRE.read_text(encoding="utf-8")
    producer = MEDIA_PRODUCER.read_text(encoding="utf-8")
    require(
        "c2_stage_u32(22u) != (uint32_t)LISP65_C2_PRODUCT_BUILD_ID" in generated
        and "c2_stage_u32(22u) != (uint32_t)LISP65_C2_PRODUCT_BUILD_ID" in runtime,
        "linked envelope build-id guard absent",
    )
    require(
        generated.index("c2_stage_u32(22u)")
        < generated.index("c2_stage_crc(32u, 32u)"),
        "product build-id guard no longer precedes CRC/content validation",
    )
    require(
        "return staged && c2_product_append_staged(staged) ? vm_t : NIL;" in vm
        and "(%disk-load-lib (nth 2 row) (nth 3 row))" in require_source,
        "delivered require -> disk stage -> append seam drift",
    )
    require(
        "SOURCE_LIBRARY = ROOT /" in producer
        and "trace-core-abi-link93-r6/trace-acceptance-media/trace-library" in producer
        and "shutil.copytree(SOURCE_LIBRARY, LIBRARY)" in producer
        and "byte-identical to Link 93" in producer,
        "Link-95 media producer no longer proves the cross-world copy",
    )
    return {
        "ELF": bind(LINK95_ELF),
        "generated_runtime": bind(LINK95_RUNTIME),
        "symbols": symbols,
        "ordered_first_edge": (
            "%disk-load-lib stages inspect.l65s; c2_product_append_staged enters "
            "c2_append_envelope_phase; the offset-22 product-build-id predicate "
            "rejects before CRC, metadata, descriptors, publication or trace code."
        ),
        "visible_error_limit": (
            "The exact first loader divergence is attributed. The surrounding "
            "transient install/rollback path exposes VM_BADOPCODE on hardware, "
            "but this desk gate does not claim a new inner status-propagation trace."
        ),
    }


def hardware_contrast() -> dict[str, Any]:
    first_red = load(FIRST_RED)
    green = LINK93_GREEN.read_text(encoding="utf-8")
    require(
        first_red.get("status")
            == "FIRST RED: physical require inspect returned VM_BADOPCODE before every trace row"
        and first_red["row"]["observed"] == "*** vm: bad bytecode"
        and first_red["row"]["returned_to_prompt"] is True,
        "Link-95 hardware First Red authority drift",
    )
    require(
        "(require (quote inspect))" in green
        and " t " in green
        and "*** vm:" not in green,
        "Link-93 exact-pair hardware control drift",
    )
    return {
        "Link93_exact_pair": {
            "postcondition": bind(LINK93_GREEN),
            "result": "require inspect -> t",
        },
        "Link95_cross_world_pair": {
            "first_red": bind(FIRST_RED),
            "result": "require inspect -> VM_BADOPCODE -> usable REPL",
        },
    }


def derive() -> dict[str, Any]:
    world93 = c2d_identity(
        LINK93_C2D,
        {"generation": 1, "images": 6, "entries": 748,
         "resolutions": 2913, "roots": 350, "immutable_images": 6,
         "product_build_id": LINK93_ID},
    )
    world95 = c2d_identity(
        LINK95_C2D,
        {"generation": 1, "images": 6, "entries": 753,
         "resolutions": 2920, "roots": 350, "immutable_images": 6,
         "product_build_id": LINK95_ID},
    )
    manifest93 = product_manifest(LINK93_MANIFEST, LINK93_ID)
    manifest95 = product_manifest(LINK95_MANIFEST, LINK95_ID)
    require(
        manifest93["linked_elf_sha256"]
            == "8cd0d41196effa2d119e662bd6631554113112efe254b0fa9b5068ae44a93a63"
        and manifest95["linked_elf_sha256"] == sha(LINK95_ELF.read_bytes()),
        "canonical ELF identity drift",
    )
    require(
        sha(LIBRARY_D81.read_bytes()) == EXPECTED_LIBRARY_D81
        and sha(PRODUCT_D81.read_bytes()) == EXPECTED_PRODUCT_D81,
        "delivered media identity drift",
    )
    media = load(MEDIA_RECEIPT)
    require(
        media.get("status") == "LINK95-HOST-AND-MEDIA-GREEN; HARDWARE-PENDING"
        and media["attempt_accounting"]["product_links"] == 0,
        "Link-95 media closure authority drift",
    )
    library = library_worlds()
    path = linked_path()
    hardware = hardware_contrast()
    return {
        "format": FORMAT,
        "recorded_on": RECORDED_ON,
        "status": "ATTRIBUTED: LINK93-BOUND-L65S-REJECTED-BY-LINK95-BUILD-ID-GUARD",
        "authority": {
            "commission": "d11dbf56",
            "first_red": bind(FIRST_RED),
            "media_closure": bind(MEDIA_RECEIPT),
            "gate": bind(Path(__file__).resolve()),
            "media_producer": bind(MEDIA_PRODUCER),
        },
        "product_worlds": {
            "Link93": {"C2D": world93, "manifest": manifest93},
            "Link95": {"C2D": world95, "manifest": manifest95},
        },
        "library_world_binding": library,
        "linked_require_path": path,
        "hardware_contrast": hardware,
        "attribution": {
            "mechanism": (
                "The Link-95 media producer copied the Link-93 inspect library "
                "byte-for-byte. Its L65S header therefore carries product build "
                "identity 0x3b48650d, while the linked Link-95 envelope guard "
                "requires 0x14d980c3. The target rejects at c2_append_envelope_phase "
                "before any packed reference, publication, trace or ABI operation."
            ),
            "first_divergent_edge": "L65S header offset 22 product-build-id guard",
            "pre_registered_ordinal_suspect": "rejected",
            "media_pair_rule": (
                "A product D81 and a library D81 form one world identity. A "
                "release closure must reject every library whose L65S build id "
                "does not equal the mounted product C2D build id."
            ),
        },
        "claim_limits": {
            "proved": [
                "the exact delivered pair is cross-world",
                "the first target rejection is the L65S product build identity",
                "all other envelope/index predicates pass in a non-writing counterfactual",
                "the inspect artifact contains no fixed product Directory/native ordinals",
                "the Link-93 exact pair required inspect successfully on hardware",
            ],
            "not_proved": [
                "a rebuilt Link-95 library or media pair",
                "a corrected hardware require row",
                "trace, untrace or defstruct behavior",
                "a new status-propagation claim beyond the bound first loader edge",
            ],
        },
        "execution_accounting": {
            "product_links": 0,
            "library_rebuilds": 0,
            "media_rebuilds": 0,
            "hardware_contacts": 0,
            "counterfactual_artifacts_written": 0,
        },
        "mutations": {
            "passed": 10,
            "total": 10,
            "cases": [
                "cross-world pair accepted",
                "product build-id guard omitted",
                "failed predicate widened beyond build id",
                "counterfactual changed payload bytes",
                "fixed ordinal coupling falsely claimed",
                "Link-95 library falsely labeled Link-95-bound",
                "Link-93 hardware control omitted",
                "Link-95 First Red omitted",
                "linked envelope symbol identity dimmed",
                "fix or device claim smuggled into attribution",
            ],
        },
        "next_step": (
            "Owner/reviewer disposition of a Link-95-world library rebuild and a "
            "permanent media-pair identity closure; this attribution authorizes neither."
        ),
    }


def validate(value: dict[str, Any]) -> None:
    require(
        value.get("format") == FORMAT
        and value.get("status")
            == "ATTRIBUTED: LINK93-BOUND-L65S-REJECTED-BY-LINK95-BUILD-ID-GUARD",
        "attribution status drift",
    )
    worlds = value["product_worlds"]
    require(
        worlds["Link93"]["C2D"]["product_build_id"] == LINK93_ID
        and worlds["Link95"]["C2D"]["product_build_id"] == LINK95_ID,
        "product-world identity dimmed",
    )
    binding = value["library_world_binding"]
    matrix = binding["decode_matrix"]
    require(
        binding["delivered"]["L65S_product_build_id"] == "0x3b48650d"
        and matrix == {
            "Link93": "passed envelope and index",
            "Link95_envelope": "extension product build identity",
            "Link95_index": "extension product build identity",
            "Link95_failed_predicates": ["product_build_id"],
        },
        "cross-world rejection claim drift",
    )
    counter = binding["counterfactual_only_in_memory"]
    require(
        counter["changed_offsets"] == [22, 23, 24, 25]
        and counter["envelope"] == counter["index"] == "passed"
        and counter["artifact_written"] is False,
        "four-byte non-writing counterfactual dimmed",
    )
    fixed = binding["packed_reference_binding"]["fixed_product_reference_counts"]
    require(
        fixed == {"K_ENTRY": 0, "K_EXPORT": 0, "K_NATIVE": 0}
        and binding["packed_reference_binding"]["ordinal_subhypothesis"] == "rejected",
        "ordinal subhypothesis was not rejected",
    )
    path = value["linked_require_path"]
    require(
        path["symbols"]["c2_append_envelope_phase"] == {
            "VMA": "0xc356", "bytes": 1478,
            "section": ".lisp65_rt_c2append_envelope",
        }
        and "offset-22 product-build-id predicate" in path["ordered_first_edge"],
        "linked first-edge identity dimmed",
    )
    contrast = value["hardware_contrast"]
    require(
        contrast["Link93_exact_pair"]["result"] == "require inspect -> t"
        and contrast["Link95_cross_world_pair"]["result"]
            == "require inspect -> VM_BADOPCODE -> usable REPL",
        "hardware contrast dimmed",
    )
    require(
        value["execution_accounting"] == {
            "product_links": 0, "library_rebuilds": 0, "media_rebuilds": 0,
            "hardware_contacts": 0, "counterfactual_artifacts_written": 0,
        },
        "attribution performed or claimed an unauthorized mutation",
    )
    require(
        value["mutations"]["passed"] == value["mutations"]["total"] == 10,
        "mutation closure incomplete",
    )


def expect(label: str, action: Callable[[], Any], rejected: dict[str, str]) -> None:
    try:
        action()
    except (AttributionError, KeyError, TypeError) as error:
        rejected[label] = str(error)
        return
    raise AttributionError(f"mutation survived: {label}")


def selftest(base: dict[str, Any]) -> dict[str, str]:
    rejected: dict[str, str] = {}

    def mutate(label: str, fn: Callable[[dict[str, Any]], None]) -> None:
        candidate = deepcopy(base)
        fn(candidate)
        expect(label, lambda: validate(candidate), rejected)

    mutate("cross-world-accepted", lambda x: x["library_world_binding"]["decode_matrix"].update(
        {"Link95_envelope": "passed"}))
    candidate = deepcopy(base)
    candidate["linked_require_path"]["ordered_first_edge"] = "CRC first"
    expect("guard-omitted", lambda: validate(candidate), rejected)
    mutate("predicate-widened", lambda x: x["library_world_binding"]["decode_matrix"]
           ["Link95_failed_predicates"].append("record_identity"))
    mutate("counterfactual-payload", lambda x: x["library_world_binding"]
           ["counterfactual_only_in_memory"]["changed_offsets"].append(64))
    mutate("false-ordinal", lambda x: x["library_world_binding"]
           ["packed_reference_binding"]["fixed_product_reference_counts"].update(
               {"K_ENTRY": 1}))
    mutate("false-world-label", lambda x: x["library_world_binding"]["delivered"].update(
        {"L65S_product_build_id": "0x14d980c3"}))
    mutate("control-omitted", lambda x: x["hardware_contrast"].pop("Link93_exact_pair"))
    mutate("first-red-omitted", lambda x: x["hardware_contrast"].pop("Link95_cross_world_pair"))
    mutate("ELF-symbol-dimmed", lambda x: x["linked_require_path"]["symbols"]
           ["c2_append_envelope_phase"].update({"VMA": "0xc357"}))
    mutate("fix-claim-smuggled", lambda x: x["execution_accounting"].update(
        {"library_rebuilds": 1}))
    require(len(rejected) == 10, f"mutation accounting drift: {rejected}")
    return rejected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("write", "check", "selftest"))
    args = parser.parse_args()
    try:
        current = derive()
        validate(current)
        rejected = selftest(current)
        if args.mode == "write":
            write_json(RECEIPT, current)
        elif args.mode == "check":
            require(load(RECEIPT) == current, "persisted attribution receipt drift")
        print(
            "c2-link95-library-world-attribution: PASS "
            f"mode={args.mode} mutations={len(rejected)}/10"
        )
        return 0
    except (AttributionError, S.ProbeError, L65I.GateError, OSError) as error:
        print(f"c2-link95-library-world-attribution: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
