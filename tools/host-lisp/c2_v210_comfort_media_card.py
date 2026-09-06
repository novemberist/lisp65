#!/usr/bin/env python3
"""Build the v2.1 Comfort medium from one delivered product generation.

The four Comfort objects remain byte-identical to their sealed v2.0 freight.
The only added object is the product-bound private `%ide-line-net-depth`
implementation.  It stays anonymous and `%repl-step` reaches it through a
same-image entry reference.  This avoids both historical failure modes: an
unresolved anonymous-only callee and a second editor generation (`v16core`).
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0 as B  # noqa: E402
import bytecode_p0_compiler as C  # noqa: E402
import bytecode_p0_stdlib as STD  # noqa: E402
import c2_full_emission as F  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_packed_medium_transitive_closure as CLOSURE  # noqa: E402
import c2_product_session_host as SESSION_HOST  # noqa: E402
import c2_v17_comfort_phase1b_acceptance_media as V17  # noqa: E402
import c2_v200_comfort_return_materialization_repair as OLD  # noqa: E402
import c2_link95_world_bound_media as PAIR  # noqa: E402
import evidence_era as ERA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
PLAN = ROOT / "docs/planning/2.6-correctness-and-build-integrity-work-plan.md"
PLAN_HEADER = "## Owner acceptance — block 2.6 closed; v2.1 opens — 2026-09-04"
BUILD = ROOT / "build/v2.1/comfort-media-card-r2"
MANIFEST = BUILD / "repl-comfort.manifest.json"
BLOB = BUILD / "repl-comfort.blob.bin"
ARTIFACT = BUILD / "repl-comfort.l65s"
INDEX = BUILD / "l65index"
MEDIUM = BUILD / "lisp65-v2.1-comfort.d81"
HOST_BUILD = BUILD / "host-execution"
RECEIPT = ARCH / "v2.1-comfort-media-card-r2-receipt.json"
REPORT = ROOT / "docs/planning/v2.1-comfort-media-card-r2-report.md"

PREDECESSOR_COMFORT = (
    ROOT / "build/c2.3/v2.0-comfort-return-card/library/"
    "repl-comfort.manifest.json"
)
PRODUCT_PREFLIGHT = ROOT / (
    "build/2.6/card6-small-hardening-dma-tuple-repair-product-r3-preflight/"
    "setup-owned/static-plane/narrow-static"
)
PRODUCT_MANIFEST = PRODUCT_PREFLIGHT / "product/substitution-artifacts.json"
PRODUCT_C2D = PRODUCT_PREFLIGHT / "v6-semantics/initial.c2d-v6.bin"
PRODUCT_CODE = PRODUCT_PREFLIGHT / "v6-semantics/bank2-static-code.bin"
PRODUCT_ELF = ROOT / (
    "build/2.6/card6-small-hardening-dma-tuple-repair-product-r3/wplto/"
    "lisp65-c2-substitution-linked.prg.elf"
)
PRODUCT_DWX_RECEIPT = ARCH / (
    "block-2.6-card6-small-hardening-dma-tuple-repair-dwx-r3.json"
)
PRODUCT_D81 = ROOT / (
    "build/2.6/card6-small-hardening-dma-tuple-repair-dwx-r3/media/"
    "shared-system/lisp65-product.d81"
)
COMFORT_SUITE = ROOT / "tests/bytecode/libs/p0-repl-comfort.json"

PRODUCT_BUILD_ID = 0x4A1713AB
SUPPORT_NAME = "%ide-line-net-depth"
COMFORT_NAMES = ("%repl-read", "%repl-prompt", "%repl-step", "repl")
FORMAT = "lisp65-v2.1-comfort-media-card-v1"
STATUS = "PASS: V2.1 COMFORT MEDIUM READY FOR DWX PREFILTER"


class CardError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CardError(message)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"JSON absent: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"artifact absent: {path}")
    raw = path.read_bytes()
    try:
        name = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        name = path.resolve().as_posix()
    return {"path": name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def write(path: Path, value: dict[str, Any] | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(value) if isinstance(value, dict) else value
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
    temporary.replace(path)


def owner_authority() -> dict[str, Any]:
    text = PLAN.read_text(encoding="utf-8")
    require(text.count(PLAN_HEADER) == 1, "v2.1 owner authority drift")
    section = PLAN_HEADER + text.split(PLAN_HEADER, 1)[1]
    section = section.split("\n## ", 1)[0].rstrip() + "\n"
    folded = " ".join(section.lower().replace("`", "").replace("*", "").split())
    for token in ("comfort media card", "no v16core", "transitive closure",
                  "generation-coherence", "%ide-line-net-depth",
                  "dwx prefilter", "one bounded repair round"):
        require(token in folded, f"v2.1 owner token absent: {token}")
    raw = section.encode()
    return {"path": PLAN.relative_to(ROOT).as_posix(), "section": PLAN_HEADER,
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "right": "artifact-only Comfort media card; zero product links"}


def product_identity() -> dict[str, Any]:
    product = load(PRODUCT_MANIFEST)
    dwx = load(PRODUCT_DWX_RECEIPT)
    product_binding = dwx["medium"]
    require(product.get("product_build_id_u32") == PRODUCT_BUILD_ID
            and product.get("images") == 6 and product.get("entries") == 760
            and PRODUCT_C2D.read_bytes()[44:48]
                == PRODUCT_BUILD_ID.to_bytes(4, "little")
            and len(PRODUCT_CODE.read_bytes()) == 47795
            and product_binding == bind(PRODUCT_D81)
            and bind(PRODUCT_ELF)["sha256"]
                == "f02d6997e33ae6c1059be1a9f81711d219f430c26e3144772124fd9a979366cf",
            "Block 2.6 product-world identity drift")
    return {"substitution_artifacts": bind(PRODUCT_MANIFEST),
            "C2D": bind(PRODUCT_C2D), "static_code": bind(PRODUCT_CODE),
            "ELF": bind(PRODUCT_ELF), "product_D81": bind(PRODUCT_D81),
            "build_id": f"0x{PRODUCT_BUILD_ID:08x}",
            "entries": product["entries"], "code_bytes": 47795}


def product_manifests() -> list[Path]:
    product = load(PRODUCT_MANIFEST)
    paths: list[Path] = []
    for row in product["manifests"]:
        path = Path(row["path"])
        if not path.is_absolute():
            path = ROOT / path
        require(bind(path) == row, f"product manifest binding drift: {path}")
        paths.append(path)
    require(len(paths) == 6, "product manifest population drift")
    return paths


def product_ide_manifest() -> Path:
    matches = []
    for path in product_manifests():
        value = load(path)
        names = {row.get("name") for row in value.get("entries", [])}
        if SUPPORT_NAME in names:
            matches.append(path)
    require(len(matches) == 1, "product-bound scanner owner is not unique")
    return matches[0]


def _blob_path(manifest_path: Path, value: dict[str, Any]) -> Path:
    raw = Path(value["blob"])
    candidates = [raw] if raw.is_absolute() else [ROOT / raw, manifest_path.parent / raw]
    found = [path for path in candidates if path.is_file()]
    require(len(found) == 1, f"manifest blob path is not unique: {manifest_path}")
    return found[0]


def _selected_support() -> tuple[dict[str, Any], dict[str, Any], bytes]:
    path = product_ide_manifest()
    value = load(path)
    rows = [row for row in value["entries"] if row.get("name") == SUPPORT_NAME]
    require(len(rows) == 1, "product-bound scanner object is not unique")
    entry = deepcopy(rows[0])
    first, count = int(entry["lit_first"]), int(entry["lit_count"])
    order = value["literal_index"][first:first + count]
    require(entry.get("anonymous") is True and int(entry["length"]) == 101
            and int(entry["blob_offset"]) == 0 and count == 1
            and order == [0]
            and value["literal_nodes"][0].get("kind") == 8
            and int(value["literal_nodes"][0].get("first")) == 0,
            "product-bound scanner generation shape drift")
    blob = _blob_path(path, value).read_bytes()
    raw = blob[int(entry["blob_offset"]):int(entry["blob_offset"]) + int(entry["length"])]
    require(len(raw) == 101, "product-bound scanner object extent drift")
    return value, entry, raw


def composed_value(comfort_path: Path | None = None) -> tuple[dict[str, Any], bytes]:
    ide, support, support_raw = _selected_support()
    selected = comfort_path or PREDECESSOR_COMFORT
    comfort = load(selected)
    comfort_blob = _blob_path(selected, comfort).read_bytes()
    require(tuple(comfort["functions"]) == COMFORT_NAMES
            and comfort["code_bytes"] == len(comfort_blob)
            and (comfort_path is not None or len(comfort_blob) == 815),
            "sealed Comfort freight drift")

    support["blob_offset"] = 0
    support["lit_first"] = 0
    entries = [support]
    for source in comfort["entries"]:
        row = deepcopy(source)
        row["blob_offset"] = int(row["blob_offset"]) + len(support_raw)
        row["lit_first"] = int(row["lit_first"]) + 1
        entries.append(row)

    nodes = [deepcopy(ide["literal_nodes"][0])]
    for source in comfort["literal_nodes"]:
        row = deepcopy(source)
        kind = int(row["kind"])
        if kind == 4 and row.get("name") == SUPPORT_NAME:
            row = {"count": 0, "first": 0, "kind": 8,
                   "name": None, "value": 0}
        elif kind == 8:
            row["first"] = int(row["first"]) + 1
        elif kind in (5, 6):
            row["first"] = int(row["first"]) + 1
        nodes.append(row)
    order = [0] + [int(node) + 1 for node in comfort["literal_index"]]
    patches = [{"blob_offset": int(row["blob_offset"]), "node": int(row["node"])}
               for row in ide["literal_patches"]
               if int(row["blob_offset"]) < len(support_raw)]
    require(patches == [{"blob_offset": 7, "node": 0}],
            "product-bound scanner patch population drift")
    patches.extend({"blob_offset": int(row["blob_offset"]) + len(support_raw),
                    "node": int(row["node"]) + 1}
                   for row in comfort["literal_patches"])
    blob = support_raw + comfort_blob
    value = {
        "format": "lisp65-bytecode-p0-artifacts-v1",
        "abi_profile": "dialect-v2", "artifact_role": "disk-lib",
        "name": "repl-comfort", "d81_name": "REPL",
        "base_addr": "0x000000", "blob": BLOB.relative_to(ROOT).as_posix(),
        "blob_sha256": hashlib.sha256(blob).hexdigest(),
        "code_bytes": len(blob), "entries": entries,
        "functions": [SUPPORT_NAME, *COMFORT_NAMES],
        "exports": list(COMFORT_NAMES),
        "provides": ["repl-comfort"], "requires": ["core"],
        "late_bound_exports": list(comfort.get("late_bound_exports", [])),
        "override_exports": [], "literal_nodes": nodes,
        "literal_index": order, "literal_patches": patches,
        "literal_format": comfort.get("literal_format"),
        "strict_arity": True,
        "composition": {
            "support": ("anonymous product-bound private object reached by "
                        "same-image entry reference"),
            "comfort": ("four sealed objects, byte-identical" if comfort_path is None
                        else "explicit repair successor; per-object attribution required"),
            "v16core": False,
        },
    }
    require(len(blob) == len(support_raw) + len(comfort_blob) and len(entries) == 5
            and len(nodes) == len(order) == len(patches)
            and (comfort_path is not None or (len(blob) == 916 and len(nodes) == 43)),
            "composed Comfort manifest cardinality drift")
    return value, blob


def materialize() -> dict[str, Any]:
    value, blob = composed_value()
    write(BLOB, blob)
    write(MANIFEST, value)
    image = F.emit_image("repl-comfort", "repl", MANIFEST)
    require(len(image.code) == 916 and len(image.manifest["entries"]) == 5,
            "composed Comfort image emission drift")
    return {"manifest": bind(MANIFEST), "blob": bind(BLOB),
            "normalized_code_sha256": hashlib.sha256(image.code).hexdigest(),
            "objects": [row["name"] for row in image.manifest["entries"]],
            "object_count": 5, "code_bytes": len(image.code),
            "resolutions": len(image.descriptors)}


def generation_coherence(packed_artifact: bytes | None = None) -> dict[str, Any]:
    candidate = F.emit_image("repl-comfort", "repl", MANIFEST)
    ide_path = product_ide_manifest()
    ide = F.emit_image("ide", "ide", ide_path)
    comfort = F.emit_image("sealed-comfort", "repl", PREDECESSOR_COMFORT)
    support_entry = next(row for row in load(ide_path)["entries"]
                         if row["name"] == SUPPORT_NAME)
    start, size = int(support_entry["blob_offset"]), int(support_entry["length"])
    support_expected = ide.code[start:start + size]
    support_actual = candidate.code[:size]
    comfort_actual = candidate.code[size:]
    failures = []
    if support_actual != support_expected:
        failures.append("support-object-differs-from-product-bound-generation")
    if comfort_actual != comfort.code:
        failures.append("sealed-comfort-object-generation-changed")
    if packed_artifact is not None:
        expected = V17.LIBMEDIA.measured(
            ("repl-comfort", "repl", "repl", MANIFEST, ()),
            (1, 1), PRODUCT_BUILD_ID)[1]
        if packed_artifact != expected:
            failures.append("packed-artifact-differs-from-materialized-generation")
    require(not failures, f"Comfort generation coherence red: {failures}")

    live_path = ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"
    live = F.emit_image("live-ide", "ide", live_path)
    live_entry = next(row for row in load(live_path)["entries"]
                      if row["name"] == SUPPORT_NAME)
    live_raw = live.code[int(live_entry["blob_offset"]):
                         int(live_entry["blob_offset"]) + int(live_entry["length"])]
    require(len(live_raw) == 142 and live_raw != support_expected,
            "mixed scanner-generation mutation did not differ")
    comfort_mutant = bytearray(comfort_actual)
    comfort_mutant[-1] ^= 1
    require(bytes(comfort_mutant) != comfort.code,
            "changed Comfort byte mutation did not differ")
    return {
        "status": "PASS: PACKED COMFORT GENERATION COHERENT",
        "product_bound_support_manifest": bind(ide_path),
        "support": {"name": SUPPORT_NAME, "bytes": size,
                    "sha256": hashlib.sha256(support_actual).hexdigest(),
                    "equals_product_private_object": True},
        "sealed_comfort": {"manifest": bind(PREDECESSOR_COMFORT),
                           "objects": list(COMFORT_NAMES),
                           "bytes": len(comfort_actual),
                           "sha256": hashlib.sha256(comfort_actual).hexdigest(),
                           "equals_sealed_generation": True},
        "packed_artifact_checked": packed_artifact is not None,
        "mutations_rejected": ["live-142-byte-scanner-generation",
                               "changed-sealed-comfort-object-byte"],
        "failures": [],
    }


def closure_gate() -> dict[str, Any]:
    predecessor = CLOSURE.derive(PRODUCT_MANIFEST, [PREDECESSOR_COMFORT])
    require(predecessor["status"] == "FIRST RED"
            and len(predecessor["failures"]) == 1
            and predecessor["failures"][0]["caller"] == "%repl-step"
            and predecessor["failures"][0]["target"] == SUPPORT_NAME
            and predecessor["failures"][0]["classification"] == "anonymous-only",
            "sealed Comfort anonymous-only positive control drift")
    successor = CLOSURE.derive(PRODUCT_MANIFEST, [MANIFEST])
    CLOSURE.require_closed(successor)
    require(successor["object_count"] == 765
            and successor["duplicate_public_owners"] == []
            and successor["failures"] == [],
            "successor product/Comfort closure drift")
    return {"status": "PASS: PACKED PRODUCT/COMFORT TRANSITIVE CLOSURE",
            "positive_control": {
                "status": predecessor["status"],
                "edge": "%repl-step -> %ide-line-net-depth",
                "classification": "anonymous-only"},
            "successor": successor,
            "mutations_rejected": CLOSURE.mutation_tests()}


def _c1541(image: Path, *arguments: str) -> None:
    tool = shutil.which("c1541")
    require(tool is not None, "c1541 is unavailable")
    result = subprocess.run([tool, str(image), *arguments], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)
    require(result.returncode == 0, "c1541 failed:\n" + result.stdout)


def build_medium() -> dict[str, Any]:
    shutil.copyfile(PRODUCT_D81, MEDIUM)
    spec = ("repl-comfort", "repl", "repl", MANIFEST, ())
    placeholder, artifact = V17.LIBMEDIA.measured(spec, (1, 1), PRODUCT_BUILD_ID)
    write(ARTIFACT, artifact)
    seed = BUILD / "l65index.seed"
    write(seed, V17.LIBMEDIA.L65I.encode_index([placeholder]))
    before = V17.LIBMEDIA.L65I.D81.visible_files(PRODUCT_D81.read_bytes())
    require(b"L65INDEX" not in before and b"REPL-COMFORT" not in before,
            "source product already owns Comfort library files")
    _c1541(MEDIUM, "-write", str(seed), "l65index")
    _c1541(MEDIUM, "-write", str(ARTIFACT), "repl-comfort")
    locator = V17.LIBMEDIA.L65I.d81_locators(MEDIUM)["repl-comfort"]
    row, located = V17.LIBMEDIA.measured(spec, locator, PRODUCT_BUILD_ID)
    require(located == artifact, "Comfort artifact changed with D81 locator")
    write(INDEX, V17.LIBMEDIA.L65I.encode_index([row]))
    _c1541(MEDIUM, "-delete", "l65index")
    _c1541(MEDIUM, "-write", str(INDEX), "l65index")
    seed.unlink()
    after = V17.LIBMEDIA.L65I.D81.visible_files(MEDIUM.read_bytes())
    added = {name: raw for name, raw in after.items() if name not in before}
    require(all(after.get(name) == raw for name, raw in before.items())
            and added == {b"L65INDEX": INDEX.read_bytes(),
                          b"REPL-COMFORT": artifact},
            "combined medium changed product files or packed library bytes")
    decoded = V17.LIBMEDIA.L65I.decode_index(
        INDEX.read_bytes(), {"repl-comfort": artifact},
        artifact_build_id=PRODUCT_BUILD_ID)
    contract = V17.LIBMEDIA.resolver_contract(decoded, "repl-comfort")
    product_id, c2d = PAIR.product_world(MEDIUM)
    require(product_id == PRODUCT_BUILD_ID and len(decoded) == 1
            and decoded[0]["dependencies"] == []
            and contract["actual_resolver_order"] == [0]
            and "V16CORE" not in after,
            "combined Comfort medium identity drift")
    return {"source_product": bind(PRODUCT_D81), "medium": bind(MEDIUM),
            "product_files_unchanged": len(before),
            "added_files": ["L65INDEX", "REPL-COMFORT"],
            "index": bind(INDEX), "artifact": bind(ARTIFACT),
            "artifact_locator": {"track": locator[0], "sector": locator[1]},
            "index_rows": decoded, "resolver_contract": contract,
            "mounted_C2D_sha256": hashlib.sha256(c2d).hexdigest(),
            "product_build_id": f"0x{product_id:08x}",
            "v16core_present": False}


def geometry() -> dict[str, int]:
    raw = PRODUCT_C2D.read_bytes()
    u16 = lambda at: int.from_bytes(raw[at:at + 2], "little")
    value = {"generation": u16(10), "images": u16(12),
             "entries": u16(16), "resolutions": u16(20),
             "roots": u16(24), "code_bytes": len(PRODUCT_CODE.read_bytes()),
             "immutable_images": u16(38),
             "catalog_crc32": int.from_bytes(raw[40:44], "little"),
             "build_id": int.from_bytes(raw[44:48], "little")}
    require(value["generation"] == 1 and value["images"] == 6
            and value["entries"] == 760 and value["code_bytes"] == 47795
            and value["build_id"] == PRODUCT_BUILD_ID,
            "current product geometry drift")
    return value


def product_host(out: Path) -> SESSION_HOST.ProductSessionHost:
    host = SESSION_HOST.ProductSessionHost(geometry(), out)
    c2d, code = PRODUCT_C2D.read_bytes(), PRODUCT_CODE.read_bytes()
    host.plane.c2d[:] = c2d
    host.plane.code[:len(code)] = code
    loaded = 0
    for path in product_manifests():
        manifest = load(path)
        blob = _blob_path(path, manifest).read_bytes()
        require(hashlib.sha256(blob).hexdigest() == manifest["blob_sha256"],
                f"product manifest blob drift: {path}")
        patches = {int(item["blob_offset"]): int(item["node"])
                   for item in manifest["literal_patches"]}
        for entry in manifest["entries"]:
            code_object = STD._patched_code_from_manifest_entry(
                host.heap, manifest, blob, entry, patches)
            symbol = host.heap.intern(entry["name"])
            host.directory[symbol] = code_object
            host.code_names[id(code_object)] = entry["name"]
            loaded += 1
    require(loaded == 760, "current product host population drift")
    return host


def append_manifest(host: SESSION_HOST.ProductSessionHost) -> dict[str, int]:
    image = F.emit_image("repl-comfort", "repl", MANIFEST)
    entry_base, resolution_base = host.plane.entries, host.plane.resolutions
    before = {"entries": host.plane.entries, "resolutions": host.plane.resolutions,
              "roots": host.plane.roots, "code_bytes": host.plane.code_low}
    for local, entry in enumerate(image.manifest["entries"]):
        _raw, symbol = host._sync_symbol(entry["name"])
        host.ordinal_to_symbol[entry_base + local] = symbol
        host.raw_to_host[SESSION_HOST.mk_bcode(entry_base + local)] = symbol
    V6.append_image(host.plane, image, transient=False,
                    direct_resolver=host._resolve_direct(image))
    host._bind_image_objects(image, resolution_base, entry_base)
    for local, entry in enumerate(image.manifest["entries"]):
        snapshot = host.snapshot_entry(entry_base + local)
        symbol = host.heap.intern(entry["name"])
        host.directory[symbol] = snapshot["code"]
        host.code_names[id(snapshot["code"])] = entry["name"]
    after = {"entries": host.plane.entries, "resolutions": host.plane.resolutions,
             "roots": host.plane.roots, "code_bytes": host.plane.code_low}
    require(after["entries"] - before["entries"] == 5
            and after["code_bytes"] - before["code_bytes"] == len(image.code),
            "host Comfort append geometry drift")
    return {"before": before, "after": after}


def execute_case(host: SESSION_HOST.ProductSessionHost,
                 case: dict[str, Any], ordinal: int) -> dict[str, Any]:
    suite = load(COMFORT_SUITE)
    heap, directory = host.heap.clone(), dict(host.directory)
    entry = f"%v210-comfort-case-{ordinal}"
    compiled, code, helpers = C.compile_top_form_with_helpers(
        ["defun", entry, [], C.parse_one(case["expr"])], heap,
        strict_arity=True, abi_profile="dialect-v2", prebuilt_primitives=True)
    require(compiled == entry, "Comfort case compiler identity drift")
    for helper_name, helper_code in helpers:
        directory[heap.intern(helper_name)] = helper_code
    directory[heap.intern(entry)] = code
    trace = SESSION_HOST.Trace()
    vm = B.P0VM(heap=heap, directory=directory, trace=trace,
                code_names=host.code_names,
                max_steps=case.get("max_steps", 100000), max_call_args=12,
                key_events=case.get("key_events"), private_key_event_modes=True,
                memory_read_sequences={0xFF83: [0] * 4096},
                abi_profile="dialect-v2", abi_ledger=host.ledger)
    result = vm.run(code, [])
    text = heap.obj_to_text(result)
    require(text == case["expect"], f"{case['name']}: result drift: {text}")
    observation = STD._validate_case_io(
        case, vm, "v2.1-product-plus-packed-comfort", "materialized",
        suite.get("ignored_output_codes", []))
    return {"name": case["name"], "result": text, "steps": vm.steps,
            "observation": observation, "last_calls": trace.calls[-4:]}


def host_execution() -> dict[str, Any]:
    host = product_host(HOST_BUILD)
    appended = append_manifest(host)
    cases = [execute_case(host, case, ordinal)
             for ordinal, case in enumerate(load(COMFORT_SUITE)["cases"])]
    require(len(cases) == 9, "sealed Comfort case population drift")
    return {"status": "PASS: NINE SEALED COMFORT CASES ON CURRENT WORLD",
            "case_count": len(cases), "append": appended, "cases": cases}


def validate(value: dict[str, Any]) -> None:
    require(value.get("format") == FORMAT and value.get("status") == STATUS
            and value.get("accounting") == {"WPLTO_runs": 0,
                "product_links": 0, "product_bytes_changed": 0,
                "media_builds": 1, "DWX_runs": 0, "device_contacts": 0}
            and value["materialization"]["objects"]
                == [SUPPORT_NAME, *COMFORT_NAMES]
            and value["materialization"]["code_bytes"] == 916
            and value["closure"]["successor"]["status"] == "PASS"
            and value["generation_coherence"]["failures"] == []
            and value["generation_coherence"]["packed_artifact_checked"] is True
            and value["host_execution"]["case_count"] == 9
            and value["medium"]["v16core_present"] is False
            and value["medium"]["added_files"] == ["L65INDEX", "REPL-COMFORT"],
            "v2.1 Comfort media card semantic wall red")


def report(value: dict[str, Any]) -> str:
    closure = value["closure"]["successor"]
    host = value["host_execution"]
    medium = value["medium"]
    return f"""# v2.1 Comfort media card

Status: **{value['status']}**

## Composition

The product is the byte-identical Block-2.6 r3 medium.  The only appended
library role is `repl-comfort`; `v16core` is absent.  Its five objects are the
four sealed Comfort objects (815 bytes, unchanged) plus the product-bound
101-byte private `%ide-line-net-depth` object, published in that same role.
The complete library code extent is **916 bytes**.

The old composition is the positive control: `%repl-step ->
%ide-line-net-depth` is classified `anonymous-only`.  The successor closes
**{closure['object_count']} objects / {closure['call_site_count']} calls** with
zero missing callees and zero duplicate public owners.  Packed generation
coherence proves the scanner byte-identical to the product's private object
and all four Comfort objects byte-identical to their sealed generation.  A
142-byte live scanner substitution and a changed Comfort byte both fall.

## Executed host world and medium

All **{host['case_count']}** sealed Comfort cases execute over the current
47,795-byte product plane plus the exact packed five-object image.  The D81
keeps every original product file byte-identical and adds only `L65INDEX` and
`REPL-COMFORT`.  Product build ID: `{medium['product_build_id']}`.  Medium
SHA-256: `{medium['medium']['sha256']}`.

No mapped cold placement is used, so the mapped-body abort prohibition is
vacuously preserved.  No WPLTO, product link or product byte was consumed.

## Next gate

The card is not hardware-ready yet.  Its next and mandatory step is the DWX
prefilter over this actually packed medium.  Only a green prefilter may
materialize the sealed seven-group owner session; the one feature repair
round remains unspent.
"""


def build() -> None:
    require(not BUILD.exists() and not RECEIPT.exists() and not REPORT.exists(),
            "v2.1 Comfort media card is one-shot")
    owner_authority()
    product = product_identity()
    materialized = materialize()
    closure = closure_gate()
    preliminary_generation = generation_coherence()
    medium = build_medium()
    packed = V17.LIBMEDIA.L65I.D81.visible_files(MEDIUM.read_bytes())[
        b"REPL-COMFORT"]
    generation = generation_coherence(packed)
    require(preliminary_generation["support"] == generation["support"]
            and preliminary_generation["sealed_comfort"]
                == generation["sealed_comfort"],
            "pre-pack/post-pack generation truth diverged")
    host = host_execution()
    value = {"format": FORMAT, "recorded_on": ERA.stable_recorded_on(RECEIPT),
             "status": STATUS, "authority": owner_authority(),
             "product": product, "materialization": materialized,
             "closure": closure, "generation_coherence": generation,
             "host_execution": host, "medium": medium,
             "accounting": {"WPLTO_runs": 0, "product_links": 0,
                 "product_bytes_changed": 0, "media_builds": 1,
                 "DWX_runs": 0, "device_contacts": 0},
             "next": "DWX prefilter over the actually packed medium"}
    validate(value)
    write(RECEIPT, value)
    write(REPORT, report(value).encode())
    check()
    print("v2.1 Comfort media card: BUILD PASS "
          f"objects={closure['successor']['object_count']} "
          f"calls={closure['successor']['call_site_count']} "
          f"host={host['case_count']}/9 DWX=next")


def check() -> None:
    value = load(RECEIPT)
    validate(value)
    expected, blob = composed_value()
    require(MANIFEST.read_bytes() == canonical(expected)
            and BLOB.read_bytes() == blob
            and value["authority"] == owner_authority()
            and value["product"] == product_identity()
            and value["materialization"]["manifest"] == bind(MANIFEST)
            and value["materialization"]["blob"] == bind(BLOB)
            and value["medium"]["medium"] == bind(MEDIUM)
            and value["medium"]["artifact"] == bind(ARTIFACT)
            and value["medium"]["index"] == bind(INDEX)
            and value["generation_coherence"]
                == generation_coherence(
                    V17.LIBMEDIA.L65I.D81.visible_files(MEDIUM.read_bytes())[
                        b"REPL-COMFORT"])
            and REPORT.read_text(encoding="utf-8") == report(value),
            "v2.1 Comfort persisted media-card drift")
    print("v2.1 Comfort media card: CHECK PASS host=9/9 DWX=next")


def selftest() -> None:
    value = load(RECEIPT)
    validate(value)
    mutations = {
        "reintroduce-v16core": lambda row: row["medium"].update(v16core_present=True),
        "drop-shared-scanner": lambda row: row["materialization"].update(
            objects=list(COMFORT_NAMES), object_count=4, code_bytes=815),
        "change-sealed-comfort": lambda row: row["generation_coherence"].update(
            failures=["sealed-comfort-object-generation-changed"]),
        "skip-packed-generation-check": lambda row: row["generation_coherence"].update(
            packed_artifact_checked=False),
        "reopen-callee": lambda row: row["closure"]["successor"].update(
            status="FIRST RED"),
        "claim-DWX-before-run": lambda row: row["accounting"].update(DWX_runs=1),
        "claim-product-link": lambda row: row["accounting"].update(product_links=1),
    }
    rejected = []
    for name, mutate in mutations.items():
        mutant = deepcopy(value)
        mutate(mutant)
        try:
            validate(mutant)
        except CardError:
            rejected.append(name)
    require(rejected == list(mutations), "Comfort media-card mutation survived")
    print(f"v2.1 Comfort media card: SELFTEST PASS mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "check", "selftest"))
    args = parser.parse_args()
    globals()[args.command.replace("-", "_")]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CardError, CLOSURE.ClosureError, F.FullError,
            B.DecodeError) as error:
        print(f"v2.1 Comfort media card: FIRST RED: {error}", file=sys.stderr)
        raise SystemExit(1)
