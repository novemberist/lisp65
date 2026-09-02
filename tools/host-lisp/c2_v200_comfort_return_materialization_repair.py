#!/usr/bin/env python3
"""Repair the v2.0 Comfort media's era-crossed editor materialization."""

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
import c2_product_session_host as SESSION_HOST  # noqa: E402
import c2_v17_comfort_phase1b_acceptance_media as V17  # noqa: E402
import c2_v200_comfort_return_card as CARD  # noqa: E402
import c2_v200_comfort_return_media as BASE  # noqa: E402
import c2_v200_symbol22_build_id_rebind as R4  # noqa: E402
import c2_v200_symbol22_build_id_device_media as R4_MEDIA  # noqa: E402


ARCH = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
BUILD = ROOT / "build/c2.3/v2.0-comfort-return-materialization-repair"
PRODUCT = BUILD / "shared-system/lisp65-product.d81"
LIBRARY = BUILD / "library"
LIBRARY_D81 = LIBRARY / "lisp65-library.d81"
INDEX = LIBRARY / "l65index"
SUPPORT = BUILD / "support/v16core"
SUPPORT_SUITE = BUILD / "support/v16core-suite.json"
COMFORT_MANIFEST = CARD.LIBRARY.with_suffix(".manifest.json")
HISTORICAL_SUPPORT = BASE.V16_MANIFEST
STATIC_MANIFEST = R4.CANDIDATE_MANIFEST
STATIC_ROOT = STATIC_MANIFEST.parents[1]
C2D = STATIC_ROOT / "v6-semantics/initial.c2d-v6.bin"
CODE = STATIC_ROOT / "v6-semantics/bank2-static-code.bin"
RECEIPT = ARCH / (
    "c2.3-v2.0-comfort-return-materialization-repair-receipt.json")
REPORT = ROOT / "docs/planning/v2.0.0-comfort-return-materialization-repair-report.md"
SESSION_CONFIG = ROOT / "config/c2-v200-comfort-return-device-session-r1.json"
PRODUCT_REMOTE = "V20CFR2P.D81"
LIBRARY_REMOTE = "V20CFR2L.D81"
FORMAT = "lisp65-c2-v200-comfort-return-materialization-repair-v1"
SESSION_FORMAT = "lisp65-c2-v200-comfort-return-device-session-v2"
STATUS = "PASS: V2.0 COMFORT MATERIALIZATION REPAIR READY"
FIRST_RED = "FIRST RED: PACKED EDITOR SUPPORT OMITTED LIVE %RL-POLL OWNER"
BASE_SUITE = ROOT / "tests/bytecode/libs/p0-v160-comfort-device-delta.json"
COMFORT_SUITE = ROOT / "tests/bytecode/libs/p0-repl-comfort.json"
EVIDENCE_SEAL_COMMIT = "92f40af3bcde7482f2f745281589182d0901fd9e"


class RepairError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise RepairError(message)


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
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def sealed_file(path: Path) -> bytes:
    return subprocess.run(
        ["git", "show", f"{EVIDENCE_SEAL_COMMIT}:"
         f"{path.relative_to(ROOT).as_posix()}"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout


def write(path: Path, value: dict[str, Any] | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(value) if isinstance(value, dict) else value
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
    temporary.replace(path)


def support_suite() -> tuple[dict[str, Any], dict[str, Any]]:
    resident, live = CARD.live_resident_spec(write_file=False)
    selected = list(live["selected_live_editor_functions"])
    suite = STD._read_suite(str(BASE_SUITE))
    suite["description"] = (
        "v2.0 current-product-world editor support for sealed Comfort")
    suite["functions"] = selected
    suite["allow_omitted_defuns"] = []
    suite["resident_suite"] = (
        "config/c2-v160-comfort-repl-device-resident.json")
    suite["tailcall_self"] = [
        name for name in resident.get("tailcall_self", []) if name in selected]
    for key in list(suite):
        if key.startswith("_"):
            del suite[key]
    require(len(selected) == 28 and "%rl-poll" in selected
            and suite["tailcall_self"]
                == ["%read-line-loop", "%ide-line-net-depth"],
            "live editor-support population drift")
    return suite, live


def build_support() -> dict[str, Any]:
    suite, live = support_suite()
    write(SUPPORT_SUITE, suite)
    result = STD.check_suite(str(BASE_SUITE), suite)
    STD.emit_artifacts(
        str(BASE_SUITE), suite, str(SUPPORT), artifact_role="disk-lib")
    manifest = load(SUPPORT.with_suffix(".manifest.json"))
    require(manifest["functions"] == suite["functions"]
            and manifest["provides"] == ["v16core"]
            and manifest["code_bytes"] == 4583
            and manifest["directory_bytes"] == 196
            and manifest["cost"]["largest_code_object_bytes"] == 253
            and manifest["cost"]["dir_slots"] == 28
            and result["cases"] == 1,
            "current-world editor support emission drift")
    return {"suite": bind(SUPPORT_SUITE),
            "manifest": bind(SUPPORT.with_suffix(".manifest.json")),
            "blob": bind(SUPPORT.with_suffix(".blob.bin")),
            "directory": bind(SUPPORT.with_suffix(".dir.bin")),
            "functions": manifest["functions"],
            "function_count": len(manifest["functions"]),
            "code_bytes": manifest["code_bytes"],
            "directory_bytes": manifest["directory_bytes"],
            "largest_code_object_bytes":
                manifest["cost"]["largest_code_object_bytes"],
            "source_world_case_steps": result["steps"],
            "authority": CARD.trimmed_live_authority(live)}


def geometry() -> dict[str, int]:
    raw = C2D.read_bytes()
    require(raw[:5] == b"C2D\0\x06" and len(raw) >= 48,
            "candidate C2D-v6 header drift")
    u16 = lambda at: int.from_bytes(raw[at:at + 2], "little")
    value = {"generation": u16(10), "images": u16(12),
        "entries": u16(16), "resolutions": u16(20), "roots": u16(24),
        "code_bytes": len(CODE.read_bytes()), "immutable_images": u16(38),
        "catalog_crc32": int.from_bytes(raw[40:44], "little"),
        "build_id": int.from_bytes(raw[44:48], "little")}
    require(value == {"generation": 1, "images": 6, "entries": 760,
                "resolutions": 3020, "roots": 378, "code_bytes": 47469,
                "immutable_images": 6, "catalog_crc32": 622299709,
                "build_id": BASE.PRODUCT_ID},
            "r4 static-plane geometry drift")
    return value


def product_host(out: Path) -> tuple[SESSION_HOST.ProductSessionHost, int]:
    host = SESSION_HOST.ProductSessionHost(geometry(), out)
    c2d, code = C2D.read_bytes(), CODE.read_bytes()
    host.plane.c2d[:] = c2d
    host.plane.code[:len(code)] = code
    loaded = 0
    for row in load(STATIC_MANIFEST)["manifests"]:
        manifest = load(ROOT / row["path"])
        blob = (ROOT / manifest["blob"]).read_bytes()
        require(hashlib.sha256(blob).hexdigest() == manifest["blob_sha256"],
                f"static manifest blob drift: {row['path']}")
        patches = {int(item["blob_offset"]): int(item["node"])
                   for item in manifest["literal_patches"]}
        for entry in manifest["entries"]:
            code_object = STD._patched_code_from_manifest_entry(
                host.heap, manifest, blob, entry, patches)
            symbol = host.heap.intern(entry["name"])
            host.directory[symbol] = code_object
            host.code_names[id(code_object)] = entry["name"]
            loaded += 1
    require(loaded == geometry()["entries"],
            "static product directory population drift")
    return host, loaded


def counters(host: SESSION_HOST.ProductSessionHost) -> dict[str, int]:
    return {"images": host.plane.images, "entries": host.plane.entries,
        "resolutions": host.plane.resolutions, "roots": host.plane.roots,
        "code_bytes": host.plane.code_low}


def append_manifest(host: SESSION_HOST.ProductSessionHost, path: Path,
                    label: str) -> dict[str, Any]:
    image = F.emit_image(label, label, path)
    before = counters(host)
    entry_base, resolution_base = host.plane.entries, host.plane.resolutions
    for local, entry in enumerate(image.manifest["entries"]):
        _raw, symbol = host._sync_symbol(entry["name"])
        host.ordinal_to_symbol[entry_base + local] = symbol
        host.raw_to_host[
            SESSION_HOST.mk_bcode(entry_base + local)] = symbol
    appended = V6.append_image(
        host.plane, image, transient=False,
        direct_resolver=host._resolve_direct(image))
    host._bind_image_objects(image, resolution_base, entry_base)
    for local, entry in enumerate(image.manifest["entries"]):
        snapshot = host.snapshot_entry(entry_base + local)
        symbol = host.heap.intern(entry["name"])
        host.directory[symbol] = snapshot["code"]
        host.code_names[id(snapshot["code"])] = entry["name"]
    return {"label": label, "manifest": bind(path), "before": before,
        "after": counters(host), "functions": len(image.manifest["entries"]),
        "handles": appended["handles"]}


def execute_case(host: SESSION_HOST.ProductSessionHost,
                 case: dict[str, Any], ordinal: int) -> dict[str, Any]:
    suite = load(COMFORT_SUITE)
    heap, directory = host.heap.clone(), dict(host.directory)
    entry = f"%materialized-comfort-case-{ordinal}"
    compiled, code, helpers = C.compile_top_form_with_helpers(
        ["defun", entry, [], C.parse_one(case["expr"])], heap,
        strict_arity=True, abi_profile="dialect-v2", prebuilt_primitives=True)
    require(compiled == entry, "materialized case compiler identity drift")
    for helper_name, helper_code in helpers:
        directory[heap.intern(helper_name)] = helper_code
    directory[heap.intern(entry)] = code
    trace = SESSION_HOST.Trace()
    vm = B.P0VM(
        heap=heap, directory=directory, trace=trace,
        code_names=host.code_names, max_steps=case.get("max_steps", 100000),
        max_call_args=12, key_events=case.get("key_events"),
        private_key_event_modes=True,
        memory_read_sequences={0xFF83: [0] * 4096},
        abi_profile="dialect-v2", abi_ledger=host.ledger)
    result = vm.run(code, [])
    text = heap.obj_to_text(result)
    require(text == case["expect"], f"{case['name']}: result drift")
    observation = STD._validate_case_io(
        case, vm, "product+packed-support+sealed-comfort",
        "materialized", suite.get("ignored_output_codes", []))
    return {"name": case["name"], "result": text, "steps": vm.steps,
            "observation": observation, "last_calls": trace.calls[-4:]}


def materialized_world_gate() -> dict[str, Any]:
    cases = load(COMFORT_SUITE)["cases"]
    with tempfile.TemporaryDirectory(
            prefix="c2-v200-comfort-materialized-", dir=ROOT / "build") as raw:
        out = Path(raw)
        good, static_entries = product_host(out / "good")
        support = append_manifest(
            good, SUPPORT.with_suffix(".manifest.json"), "v16core")
        comfort = append_manifest(good, COMFORT_MANIFEST, "repl-comfort")
        observations = [execute_case(good, case, ordinal)
                        for ordinal, case in enumerate(cases)]

        old, old_static_entries = product_host(out / "old")
        old_support = append_manifest(old, HISTORICAL_SUPPORT, "v16core")
        append_manifest(old, COMFORT_MANIFEST, "repl-comfort")
        try:
            execute_case(old, cases[0], 99)
        except B.VMError as error:
            missing = str(error)
            require("function not in directory: %rl-poll" in missing,
                    "historical packed-world mutation fell for wrong reason")
        else:
            raise RepairError("historical packed support unexpectedly survived")
    require(static_entries == old_static_entries == 760
            and support["after"] == {"images": 7, "entries": 788,
                "resolutions": 3162, "roots": 402, "code_bytes": 52052}
            and comfort["after"] == {"images": 8, "entries": 792,
                "resolutions": 3204, "roots": 410, "code_bytes": 52867}
            and len(observations) == 9,
            "materialized product/library geometry drift")
    return {"status": "PASS: ACTUAL PRODUCT AND PACKED SUPPORT EXECUTE COMFORT",
        "static_entries": static_entries, "support_append": support,
        "comfort_append": comfort, "cases": observations,
        "mutant": {"manifest": bind(HISTORICAL_SUPPORT),
            "functions": old_support["functions"],
            "result": missing,
            "meaning": ("the former media omitted the live %rl-poll owner even "
                        "though its current %read-line-loop consumed that name")}}


def capacity_gate() -> dict[str, Any]:
    card = load(CARD.RECEIPT)["capacity"]
    old = load(HISTORICAL_SUPPORT)
    new = load(SUPPORT.with_suffix(".manifest.json"))
    old_names, new_names = (set(item["cost"]["symbol_names"])
                            for item in (old, new))
    added = sorted(new_names - old_names)
    removed = sorted(old_names - new_names)
    added_bytes = sum(len(name.encode("ascii")) + 1 for name in added)
    require(len(added) == 17 and added_bytes == 181 and not removed
            and card["before_loading_comfort"]
                == {"symbol_slots": 110, "namepool_bytes": 1488}
            and card["new_namepool_bytes"] == 53,
            "successor support name-cost derivation drift")
    after_support = {"symbol_slots": 110 - len(added),
                     "namepool_bytes": 1488 - added_bytes}
    after_comfort = {"symbol_slots": after_support["symbol_slots"] - 5,
                     "namepool_bytes": after_support["namepool_bytes"] - 53}
    require(after_comfort == {"symbol_slots": 88, "namepool_bytes": 1254}
            and after_comfort["symbol_slots"] >= 32
            and after_comfort["namepool_bytes"] >= 384,
            "successor loaded-world projection crosses release floor")
    return {"origin": card["origin"],
        "historical_support": bind(HISTORICAL_SUPPORT),
        "successor_support": bind(SUPPORT.with_suffix(".manifest.json")),
        "added_names": added, "added_slots": len(added),
        "added_namepool_bytes": added_bytes,
        "after_support": after_support, "after_loading_comfort": after_comfort,
        "release_floor": {"symbol_slots": 32, "namepool_bytes": 384},
        "margin": {"symbol_slots": 56, "namepool_bytes": 870},
        "claim_limit": "host projection; loaded-world D5 remains a device row"}


def project_product() -> dict[str, Any]:
    source = BASE.SOURCE_PRODUCT
    require(bind(source)["sha256"] == BASE.PRODUCT_D81_SHA256,
            "qualified source product medium drift")
    PRODUCT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, PRODUCT)
    require(PRODUCT.read_bytes() == source.read_bytes(),
            "artifact-only product projection changed a byte")
    return {"source": bind(source), "projected": bind(PRODUCT),
            "operation": "byte-identical copy; no product build or link"}


def library_media() -> dict[str, Any]:
    specs = (
        ("v16core", "v16core", "v16core",
         SUPPORT.with_suffix(".manifest.json"), ()),
        ("repl-comfort", "repl", "repl", COMFORT_MANIFEST, (0,)),
    )
    LIBRARY.mkdir(parents=True, exist_ok=True)
    placeholder: list[dict[str, Any]] = []
    artifacts: dict[str, bytes] = {}
    paths: list[tuple[Path, str]] = []
    for ordinal, spec in enumerate(specs):
        row, artifact = V17.LIBMEDIA.measured(
            spec, (1, ordinal + 1), BASE.PRODUCT_ID)
        placeholder.append(row)
        artifacts[spec[0]] = artifact
        path = LIBRARY / f"{spec[0]}.l65s"
        path.write_bytes(artifact)
        paths.append((path, spec[0]))
    seed_index = LIBRARY / "l65index.seed"
    seed_index.write_bytes(V17.LIBMEDIA.L65I.encode_index(placeholder))
    seed = LIBRARY / "library.seed.d81"
    V17.LIBMEDIA.build_library_d81(seed, seed_index, paths)
    locators = V17.LIBMEDIA.L65I.d81_locators(seed)
    rows = []
    for spec in specs:
        row, artifact = V17.LIBMEDIA.measured(
            spec, locators[spec[0]], BASE.PRODUCT_ID)
        require(artifact == artifacts[spec[0]],
                f"library artifact changed with locator: {spec[0]}")
        rows.append(row)
    encoded = V17.LIBMEDIA.L65I.encode_index(rows)
    INDEX.write_bytes(encoded)
    decoded = V17.LIBMEDIA.L65I.decode_index(
        encoded, artifacts, artifact_build_id=BASE.PRODUCT_ID)
    V17.LIBMEDIA.build_library_d81(LIBRARY_D81, INDEX, paths)
    visible = V17.LIBMEDIA.L65I.D81.visible_files(LIBRARY_D81.read_bytes())
    require(visible == {b"L65INDEX": encoded,
                        **{name.upper().encode(): raw
                           for name, raw in artifacts.items()}},
            "replacement library visible-file truth drift")
    contracts = {name: V17.LIBMEDIA.resolver_contract(decoded, name)
                 for name in artifacts}
    require(contracts["repl-comfort"]["actual_resolver_order"] == [0, 1],
            "replacement Comfort dependency closure drift")
    mutant = deepcopy(decoded)
    mutant[1]["dependencies"] = []
    mutations = V17.LIBMEDIA.resolver_contract_mutation_gate(
        mutant, "repl-comfort")
    seed.unlink()
    seed_index.unlink()
    return {"D81": bind(LIBRARY_D81), "index": bind(INDEX),
        "artifacts": {name: bind(LIBRARY / f"{name}.l65s")
                      for name in artifacts},
        "manifests": {"v16core": bind(SUPPORT.with_suffix(".manifest.json")),
                      "repl-comfort": bind(COMFORT_MANIFEST)},
        "index_rows": decoded, "resolver_contracts": contracts,
        "resolver_mutations_rejected": mutations,
        "visible_files": sorted(name.decode() for name in visible)}


def pair_identity() -> dict[str, Any]:
    R4_MEDIA.configure()
    value = R4_MEDIA.BASE.MEDIA.PREP.PAIR.pair_identity(PRODUCT, LIBRARY_D81)
    require(value["result"] == "same-world-pair"
            and value["product_build_id"] == f"0x{BASE.PRODUCT_ID:08x}"
            and value["row_names"] == ["v16core", "repl-comfort"],
            "replacement product/library world mismatch")
    return value


def first_red() -> dict[str, Any]:
    old = load(BASE.RECEIPT)
    require(old["status"] == BASE.STATUS
            and old["library"]["manifests"]["v16core"]
                == bind(HISTORICAL_SUPPORT),
            "first-contact media authority drift")
    return {"status": FIRST_RED, "contact": 1,
        "product_readback_sha256": BASE.PRODUCT_D81_SHA256,
        "library_readback_sha256": old["library"]["D81"]["sha256"],
        "owner_observation": {
            "boot": "native REPL visible",
            "stimulus": "(require 'repl-comfort)",
            "result": "*** wrong argument count repeated in a loop",
            "accepted_groups": [], "device_resumed_after_failure": False},
        "classification": "daily-use blocker; one bounded repair round consumed",
        "host_attribution": {
            "actual_product_static_entries": 760,
            "packed_support_functions": 9,
            "current_read_line_loop_first_live_edge": "%rl-poll",
            "missing_owner": "%rl-poll",
            "mechanism": ("media reused the historical Block-3 v16core delta, "
                "whose omitted objects were resident only in its sealed era; "
                "the r4 product does not contain those owners"),
            "device_presentation": ("load failure entered the native "
                "wrong-argument-count recovery loop")}}


def session_config(capacity: dict[str, Any]) -> dict[str, Any]:
    session = deepcopy(load(BASE.SESSION))
    session["format"] = SESSION_FORMAT
    session["status"] = "READY: OWNER V2.0 COMFORT REPAIR CONTACT"
    session["media"] = {
        "product": {**bind(PRODUCT), "remote_name": PRODUCT_REMOTE},
        "library": {**bind(LIBRARY_D81), "remote_name": LIBRARY_REMOTE}}
    session["world"]["materialization_repair"] = {
        "path": RECEIPT.relative_to(ROOT).as_posix(), "status": STATUS}
    row = next(item for item in session["rows"] if item["id"] == "C1")
    row["actions"] = [
        "cold boot product and mount the prepared library physically",
        "at lisp65> submit (require 'v16core) as one form",
        "submit (require 'repl-comfort) as the next form, then submit (repl)",
        "at l65> submit one empty line; at lisp65> submit (repl) again"]
    row["expect"] = ["both require forms return t", "Comfort prompt is l65>",
        "empty balanced line returns to one native lisp65>",
        "second entry returns to l65>"]
    d5 = next(item for item in session["rows"] if item["id"] == "C7")
    d5["projection_only"] = {
        "free_symbol_slots": capacity["after_loading_comfort"]["symbol_slots"],
        "free_name_bytes": capacity["after_loading_comfort"]["namepool_bytes"]}
    session["decision_table"]["daily-use-blocker"] = (
        "repair contact red: bounded round exhausted; Comfort descopes")
    session["evidence_limit"] = (
        "one replacement contact after the first daily-use red; no second repair")
    return session


def validate(value: dict[str, Any]) -> None:
    session = value["session_value"]
    require(value["format"] == FORMAT and value["status"] == STATUS
            and value["accounting"] == {"WPLTO_runs": 0, "product_links": 0,
                "product_cards": 0, "repair_rounds": 1,
                "artifact_only_product_copies": 1,
                "library_media_builds": 1, "prior_device_contacts": 1,
                "replacement_device_contacts": 0}
            and value["support"]["function_count"] == 28
            and value["support"]["code_bytes"] == 4583
            and value["materialized_world"]["static_entries"] == 760
            and len(value["materialized_world"]["cases"]) == 9
            and "%rl-poll" in value["materialized_world"]["mutant"]["result"]
            and value["capacity"]["after_loading_comfort"]
                == {"symbol_slots": 88, "namepool_bytes": 1254}
            and value["product"]["source"]["sha256"]
                == value["product"]["projected"]["sha256"]
                == BASE.PRODUCT_D81_SHA256
            and value["same_world_pair"]["result"] == "same-world-pair"
            and session["format"] == SESSION_FORMAT
            and session["rows"][0]["actions"][1]
                == "at lisp65> submit (require 'v16core) as one form"
            and session["rows"][6]["projection_only"]
                == {"free_symbol_slots": 88, "free_name_bytes": 1254},
            "Comfort materialization-repair semantic wall red")


def report(value: dict[str, Any]) -> str:
    capacity = value["capacity"]
    return f"""# v2.0 Comfort materialization repair

Status: **{value['status']}**

## Device first red

The first contact reached the native prompt, then `(require 'repl-comfort)`
repeated `*** wrong argument count`.  No acceptance group passed.

The exact delivered product plus exact packed libraries reproduces the deeper
failure as `function not in directory: %rl-poll`.  The packaged `v16core` was
the historical nine-object Block-3 delta.  Its omission contract assumed that
19 successor editor/matcher objects were resident in that sealed product era;
the current r4 product contains none of those owners.  The card had exercised
a flattened live source directory, not product plus the artifacts later packed
onto the D81.

## One repair

The replacement support artifact is derived from the current live-owner
population and contains all 28 required editor/matcher objects.  It costs
{value['support']['code_bytes']} Bank-2 bytes; the largest object is
{value['support']['largest_code_object_bytes']} bytes.  Sealed Comfort remains
byte-identical.  Exact persistent append ends at 52,867 code bytes, and all
nine Comfort cases execute over the actual product + packed-support + Comfort
composition.

The sharp mutation repacks the former nine-object support and fails at
`%rl-poll`.  Thus a source-only or era-crossed directory cannot satisfy the
new materialization claim.

## Capacity and accounting

The successor support adds 17 names / 181 NUL-inclusive bytes relative to the
device-loaded predecessor.  After Comfort the projection is
{capacity['after_loading_comfort']['symbol_slots']} slots /
{capacity['after_loading_comfort']['namepool_bytes']} name bytes, leaving
{capacity['margin']['symbol_slots']} / {capacity['margin']['namepool_bytes']}
above the 32/384 floor.  Final D5 remains a device row.

No product source, product byte, WPLTO, or product link changed.  This consumes
the one bounded repair round and builds one replacement library medium.
"""


def derive() -> dict[str, Any]:
    support = build_support()
    materialized = materialized_world_gate()
    capacity = capacity_gate()
    product = project_product()
    library = library_media()
    same_world = pair_identity()
    value = {"format": FORMAT, "recorded_on": "2026-08-31",
        "status": STATUS,
        "authority": {"first_media": bind(BASE.RECEIPT),
            "first_session": bind(BASE.SESSION),
            "repair_right": ("the bound device decision table grants one "
                             "bounded repair round for a daily-use blocker")},
        "first_red": first_red(), "accepted_pair": BASE.accepted_pair(),
        "support": support, "sealed_comfort": bind(COMFORT_MANIFEST),
        "materialized_world": materialized, "capacity": capacity,
        "product": product, "library": library,
        "same_world_pair": same_world,
        "accounting": {"WPLTO_runs": 0, "product_links": 0,
            "product_cards": 0, "repair_rounds": 1,
            "artifact_only_product_copies": 1, "library_media_builds": 1,
            "prior_device_contacts": 1, "replacement_device_contacts": 0},
        "claim_limit": ("replacement media and one final Comfort contact; "
                        "no hardware acceptance, Block 3 or release claim")}
    session = session_config(capacity)
    write(SESSION_CONFIG, session)
    value["session"] = bind(SESSION_CONFIG)
    value["session_value"] = session
    write(RECEIPT, value)
    validate(value)
    write(REPORT, report(value).encode())
    return value


def build() -> None:
    require(not BUILD.exists() and not RECEIPT.exists()
            and not SESSION_CONFIG.exists() and not REPORT.exists(),
            "Comfort materialization repair is one-shot")
    value = derive()
    check()
    print("v2.0 Comfort materialization repair: BUILD PASS "
          f"product={value['product']['projected']['sha256']} "
          f"library={value['library']['D81']['sha256']} device=0")


def check() -> None:
    require(RECEIPT.is_file() and SESSION_CONFIG.is_file() and REPORT.is_file(),
            "Comfort materialization-repair outputs absent")
    value = load(RECEIPT)
    validate(value)
    require(bind(PRODUCT) == value["product"]["projected"]
            and bind(LIBRARY_D81) == value["library"]["D81"]
            and bind(SUPPORT.with_suffix(".manifest.json"))
                == value["support"]["manifest"]
            and bind(SESSION_CONFIG) == value["session"]
            and load(SESSION_CONFIG) == value["session_value"]
            and pair_identity() == value["same_world_pair"],
            "Comfort materialization-repair persisted world drift")
    print("v2.0 Comfort materialization repair: CHECK PASS cases=9 device=0")


def source_check() -> None:
    value = load(RECEIPT)
    validate(value)
    require(RECEIPT.read_bytes() == sealed_file(RECEIPT)
            and REPORT.read_bytes() == sealed_file(REPORT)
            and SESSION_CONFIG.read_bytes() == sealed_file(SESSION_CONFIG),
            "sealed Comfort materialization-repair evidence drift")
    print("v2.0 Comfort materialization repair: SOURCE CHECK PASS "
          "sealed-evidence-era cases=9")


def selftest() -> None:
    value = load(RECEIPT)
    mutations = {
        "packed-support-reverts-to-nine-objects": lambda row:
            row["support"].update(function_count=9),
        "materialized-poll-mutation-lost": lambda row:
            row["materialized_world"]["mutant"].update(result="pass"),
        "capacity-crosses-floor": lambda row:
            row["capacity"].update(after_loading_comfort={
                "symbol_slots": 31, "namepool_bytes": 1254}),
        "product-byte-drift": lambda row:
            row["product"]["projected"].update(sha256="0" * 64),
        "explicit-support-load-omitted": lambda row:
            row["session_value"]["rows"][0]["actions"].__setitem__(1, "skip"),
    }
    rejected = []
    for name, mutate in mutations.items():
        trial = deepcopy(value)
        mutate(trial)
        try:
            validate(trial)
        except RepairError:
            rejected.append(name)
    require(rejected == list(mutations),
            "Comfort materialization-repair mutation survived")
    print(f"v2.0 Comfort materialization repair: SELFTEST PASS "
          f"mutations={len(rejected)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "build", "check", "source-check", "selftest"))
    action = parser.parse_args().action
    {"build": build, "check": check, "source-check": source_check,
     "selftest": selftest}[action]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RepairError, OSError, ValueError, KeyError,
            json.JSONDecodeError, STD.StdlibCheckError,
            SESSION_HOST.SessionHostError) as error:
        print(f"v2.0 Comfort materialization repair: RED: {error}",
              file=sys.stderr)
        raise SystemExit(2)
