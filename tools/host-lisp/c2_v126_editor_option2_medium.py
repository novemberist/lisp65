#!/usr/bin/env python3
"""Build and prove the pre-staged v1.2.6 editor diagnostic medium.

The medium is the byte-exact Link-83 product D81 plus one source file.  Loading
that file follows the normal device source loader and reconstructs the logical
state that the historical typed route produced, while preserving the two
helper definitions as separate persistent Session appends.

This proof is deliberately host-only.  C2J, phase-owner and ``mem_oom`` are
also required as live target readbacks immediately before the workload; the
host receipt never substitutes a modeled value for those physical witnesses.
"""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
sys.path.insert(0, str(HOST))

import bytecode_p0_compiler as COMPILER  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_product_session_host as SESSION  # noqa: E402
import c2_v124_require_prior_append_h1 as D81  # noqa: E402
import c2_v126_editor_stall_device as LEGACY  # noqa: E402


COMMISSION = ROOT / "docs/planning/c2.2-v1.2.6-editor-option1-contact-review.md"
MANIFEST = ROOT / "build/c2.2/v1.2.6-candidate-media/candidate-manifest.json"
PRODUCT_D81 = ROOT / "build/c2.2/v1.2.6-candidate-media/lisp65-product.d81"
STATIC_C2D = ROOT / (
    "build/c2.2/v1.2.6-candidate-product-link83/final/"
    "fresh-c2-lite-prelink-gates/v6-semantics/initial.c2d-v6.bin")
STATIC_CODE = ROOT / (
    "build/c2.2/v1.2.6-candidate-product-link83/final/"
    "fresh-c2-lite-prelink-gates/v6-semantics/bank2-static-code.bin")
SOURCE = ROOT / "tests/bytecode/dialect-v2/fixtures/v126-editor-option2.lisp"
IDE_MANIFEST = ROOT / "build/bytecode/dialect-v2/libs/ide.manifest.json"
DIALECT_SURFACE = ROOT / "config/dialect-v2-surface.json"
OUT = ROOT / "build/c2.2/v1.2.6-editor-option2"
MEDIUM = OUT / "lisp65-product-option2.d81"
HOST_OUT = OUT / "host-equivalence"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-v1.2.6-editor-option2-equivalence-receipt.json")
C1541 = Path("/usr/bin/c1541")
REMOTE_SOURCE_NAME = "v126diag"
FORMAT = "lisp65-c2.2-v1.2.6-editor-option2-equivalence-v2"

SCRATCH = "a" * 32 + "bc"
LEGACY_HELPER = LEGACY.ORIGINAL_HELPER
CORRECTED_HELPER = LEGACY.CORRECTED_HELPER
IDE_LOAD = '(load-lib "ide")'
SCRATCH_SETUP = (
    '(set(quote ide-buffers)(list(cons "scratch"'
    f'(list "scratch" nil(list "{SCRATCH}")(cons 0 34)'
    'nil t 1105 nil nil))))')
MEASURE3_SETUP = (
    '(progn(setq b(%ib "scratch"(symbol-value(quote ide-buffers))))'
    '(set(quote ide-buffers)(cons(cons "measure3"'
    '(list "measure3" nil(list "")(cons 0 0)nil nil 1105 nil nil))'
    '(symbol-value(quote ide-buffers))))t)')


class Option2Error(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise Option2Error(message)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"authority absent: {path}")
    data = path.read_bytes()
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(data),
        "sha256": sha_bytes(data),
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def u16(data: bytes, at: int) -> int:
    require(0 <= at <= len(data) - 2, "truncated u16")
    return struct.unpack_from("<H", data, at)[0]


def u32(data: bytes, at: int) -> int:
    require(0 <= at <= len(data) - 4, "truncated u32")
    return struct.unpack_from("<I", data, at)[0]


def geometry() -> dict[str, int]:
    c2d = STATIC_C2D.read_bytes()
    code = STATIC_CODE.read_bytes()
    require(c2d[:4] == b"C2D\0", "Link-83 C2D magic drift")
    value = {
        "generation": u16(c2d, 10),
        "images": u16(c2d, 12),
        "entries": u16(c2d, 16),
        "resolutions": u16(c2d, 20),
        "roots": u16(c2d, 24),
        "code_bytes": len(code),
        "immutable_images": u16(c2d, 38),
        "catalog_crc32": u32(c2d, 40),
        "build_id": u32(c2d, 44),
    }
    require(
        value["generation"] == 1
        and value["images"] == value["immutable_images"] == 6
        and value["entries"] == 750
        and value["code_bytes"] == 45063,
        "Link-83 base geometry drift",
    )
    return value


def build_medium() -> dict[str, Any]:
    require(C1541.is_file(), "c1541 absent")
    require(PRODUCT_D81.is_file() and SOURCE.is_file(), "medium input absent")
    OUT.mkdir(parents=True, exist_ok=True)
    MEDIUM.unlink(missing_ok=True)
    shutil.copyfile(PRODUCT_D81, MEDIUM)
    MEDIUM.chmod(0o644)
    executed = subprocess.run(
        [str(C1541), str(MEDIUM), "-write", str(SOURCE),
         f"{REMOTE_SOURCE_NAME},s"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(executed.returncode == 0, "c1541 source injection failed: " + executed.stdout)
    MEDIUM.chmod(0o444)
    original = D81.visible_files(PRODUCT_D81)
    diagnostic = D81.visible_files(MEDIUM)
    require(
        set(diagnostic) == set(original) | {REMOTE_SOURCE_NAME},
        "diagnostic D81 inventory is not product plus one source",
    )
    comparisons = []
    for name in sorted(original):
        require(diagnostic[name] == original[name], f"product D81 payload drift: {name}")
        comparisons.append({
            "name": name,
            "bytes": len(original[name]),
            "sha256": sha_bytes(original[name]),
            "comparison": "byteidentical",
        })
    require(
        diagnostic[REMOTE_SOURCE_NAME] == SOURCE.read_bytes(),
        "diagnostic source payload drift",
    )
    return {
        "product_payloads": comparisons,
        "added_source": {
            "name": REMOTE_SOURCE_NAME,
            **bind(SOURCE),
        },
        "c1541_stdout_sha256": sha_bytes(executed.stdout.encode()),
    }


def normalized_form(value: Any) -> Any:
    if isinstance(value, COMPILER.StringLit):
        return {"string": value.value}
    if isinstance(value, list):
        return [normalized_form(item) for item in value]
    return value


def expected_source_forms() -> list[Any]:
    text = SOURCE.read_text(encoding="utf-8")
    forms = COMPILER.parse_all(text)
    require(len(forms) == 5, "diagnostic source must contain exactly five forms")
    require(
        forms[0] == COMPILER.parse_one(IDE_LOAD)
        and forms[1] == COMPILER.parse_one(SCRATCH_SETUP)
        and forms[2] == COMPILER.parse_one(LEGACY_HELPER)
        and forms[3] == COMPILER.parse_one(CORRECTED_HELPER),
        "diagnostic setup/helper prefix drift",
    )
    require(
        forms[4] == COMPILER.parse_one(MEASURE3_SETUP),
        "diagnostic measure3 setup drift",
    )
    strings = [
        item.value
        for form in forms
        for item in walk(form)
        if isinstance(item, COMPILER.StringLit)
    ]
    require(strings.count(SCRATCH) == 1, "scratch payload is not bound once")
    require(strings.count("scratch") == 3 and strings.count("measure3") == 2,
            "diagnostic buffer names drift")
    return forms


def call_heads(value: Any) -> set[str]:
    if not isinstance(value, list) or not value:
        return set()
    head = value[0]
    result = {head} if isinstance(head, str) else set()
    if head == "quote":
        return result
    for item in value[1:]:
        result.update(call_heads(item))
    return result


def packaged_setup_surface_gate(forms: list[Any]) -> dict[str, Any]:
    """Bind setup calls to the public/product-callable packaged surface.

    Directory-only IDE entries are callable from other entries in the same
    carrier through ordinal references.  They are deliberately not published
    as symbolic Session functions.  The target First Red demonstrated that a
    source fixture cannot treat their mere presence in ``entries`` as an
    externally callable API.
    """
    ide = load_json(IDE_MANIFEST)
    surface = load_json(DIALECT_SURFACE)
    public = {
        row["name"] for row in surface["definitions"]
        if row.get("visibility") == "public"
    }
    packaged = {
        row["name"] for row in ide["entries"] if not row["anonymous"]
    }
    anonymous = {
        row["name"] for row in ide["entries"] if row["anonymous"]
    }
    # Forms 2/3 are the historical helper definitions.  Form 2 is overwritten
    # before invocation; form 3 publishes %ib and is then the sole Session-local
    # call used by form 4.  Only forms 0/1/4 execute during source loading.
    executed_heads = set().union(*(call_heads(forms[index]) for index in (0, 1, 4)))
    syntax = {"progn", "quote", "setq"}
    session_local = {"%ib"}
    external = executed_heads - syntax - session_local
    require(
        external <= public,
        "diagnostic source calls a non-public external symbol: "
        + ", ".join(sorted(external - public)),
    )
    require("ide" in public and "ide" in packaged,
            "device launch entry ide is not publicly packaged")
    require(
        {"%ide-store-buffer", "%ide-buffers-find"} <= anonymous
        and not {"%ide-store-buffer", "%ide-buffers-find"} & packaged,
        "bound IDE directory-only visibility drift",
    )
    require(
        not ({"%ide-store-buffer", "%ide-buffers-find"} & executed_heads),
        "diagnostic setup crosses a private IDE carrier boundary",
    )
    return {
        "status": "passed-bound-public-call-surface",
        "executed_setup_call_heads": sorted(executed_heads),
        "external_public_calls": sorted(external),
        "session_local_calls": sorted(session_local & executed_heads),
        "device_launch": "ide",
        "directory_only_rejected": [
            "%ide-buffers-find", "%ide-store-buffer"],
        "bound_ide_manifest": bind(IDE_MANIFEST),
        "dialect_surface": bind(DIALECT_SURFACE),
    }


def walk(value: Any) -> list[Any]:
    result = [value]
    if isinstance(value, list):
        for item in value:
            result += walk(item)
    return result


def plane_spans(host: SESSION.ProductSessionHost, base: dict[str, int]) -> dict[str, Any]:
    image_start = V6.C2D_IMAGES_OFFSET + base["images"] * V6.C2D_IMAGE_BYTES
    entry_start = V6.C2D_ENTRIES_OFFSET + base["entries"] * V6.C2D_ENTRY_BYTES
    resolution_start = V6.C2D_RESOLUTIONS_OFFSET + base["resolutions"] * 2
    root_start = V6.C2D_ROOTS_OFFSET + base["roots"] * 2
    spans = {
        "images": bytes(host.plane.c2d[
            image_start:V6.C2D_IMAGES_OFFSET + host.plane.images * V6.C2D_IMAGE_BYTES]),
        "entries": bytes(host.plane.c2d[
            entry_start:V6.C2D_ENTRIES_OFFSET + host.plane.entries * V6.C2D_ENTRY_BYTES]),
        "resolutions": bytes(host.plane.c2d[
            resolution_start:V6.C2D_RESOLUTIONS_OFFSET + host.plane.resolutions * 2]),
        "roots": bytes(host.plane.c2d[
            root_start:V6.C2D_ROOTS_OFFSET + host.plane.roots * 2]),
        "code": bytes(host.plane.code[base["code_bytes"]:host.plane.code_low]),
    }
    return {
        name: {"bytes": len(data), "sha256": sha_bytes(data)}
        for name, data in spans.items()
    } | {"_raw": spans}


def append_route(label: str, definitions: list[str]) -> dict[str, Any]:
    base = geometry()
    host = SESSION.ProductSessionHost(base, HOST_OUT / label)
    rows = [host.append_definition(source, "%ib") for source in definitions]
    require(
        [row["handle"] for row in rows] == [base["entries"], base["entries"] + 1]
        and [row["image_slot"] for row in rows] == [base["images"], base["images"] + 1],
        f"{label}: helper definitions are not two ordered Session appends",
    )
    spans = plane_spans(host, base)
    return {
        "rows": rows,
        "symbols": host.symbols.rows(),
        "spans": {name: value for name, value in spans.items() if name != "_raw"},
        "raw": spans["_raw"],
        "terminal_geometry": {
            "images": host.plane.images,
            "entries": host.plane.entries,
            "resolutions": host.plane.resolutions,
            "roots": host.plane.roots,
            "code_bytes": host.plane.code_low,
        },
    }


def buffer_graph() -> dict[str, Any]:
    scratch = {
        "name": "scratch", "lines": [SCRATCH], "point": [0, 34],
        "file_name": None, "mark": None, "modified": True,
        "mode": 1105, "locals": None, "diagnostics": None,
    }
    measure3 = {
        "name": "measure3", "lines": [""], "point": [0, 0],
        "file_name": None, "mark": None, "modified": False,
        "mode": 1105, "locals": None, "diagnostics": None,
    }
    roots = {
        "ide-buffers": [
            ["measure3", measure3], ["scratch", scratch],
        ],
        "b": scratch,
    }
    strings = sorted({
        "measure3", "scratch", "", SCRATCH,
    })
    return {
        "roots": roots,
        "reachable_string_arena_view": strings,
        "claim": (
            "logical reachable root/string view; raw allocation addresses are "
            "deliberately not claimed equivalent across construction histories"),
    }


def decode_buffer_form(value: Any) -> dict[str, Any]:
    require(
        isinstance(value, list) and len(value) == 10 and value[0] == "list",
        "diagnostic buffer constructor is not an exact nine-field list",
    )
    name, file_name, lines, point, mark, modified, mode, locals_, diagnostics = value[1:]
    require(isinstance(name, COMPILER.StringLit), "buffer name is not a string")
    require(
        isinstance(lines, list) and len(lines) == 2 and lines[0] == "list"
        and isinstance(lines[1], COMPILER.StringLit),
        "buffer lines are not an exact one-line list",
    )
    require(
        isinstance(point, list) and point[0] == "cons" and len(point) == 3
        and all(isinstance(item, int) for item in point[1:]),
        "buffer point is not an exact pair",
    )
    require(
        file_name == mark == locals_ == diagnostics == "nil"
        and modified in ("nil", "t") and mode == 1105,
        "buffer non-line field shape drift",
    )
    return {
        "name": name.value,
        "lines": [lines[1].value],
        "point": point[1:],
        "file_name": None,
        "mark": None,
        "modified": modified == "t",
        "mode": mode,
        "locals": None,
        "diagnostics": None,
    }


def source_buffer_graph(forms: list[Any]) -> dict[str, Any]:
    scratch_set = forms[1]
    require(
        scratch_set[:2] == ["set", ["quote", "ide-buffers"]]
        and scratch_set[2][0] == "list"
        and scratch_set[2][1][0] == "cons"
        and scratch_set[2][1][1] == COMPILER.StringLit("scratch"),
        "scratch root construction shape drift",
    )
    scratch = decode_buffer_form(scratch_set[2][1][2])
    final = forms[4]
    expected_b = COMPILER.parse_one(
        '(setq b(%ib "scratch"(symbol-value(quote ide-buffers))))')
    require(final[0] == "progn" and final[1] == expected_b and final[-1] == "t",
            "scratch binding sequence drift")
    measure_set = final[2]
    require(
        measure_set[:2] == ["set", ["quote", "ide-buffers"]]
        and measure_set[2][0] == "cons"
        and measure_set[2][1][0] == "cons"
        and measure_set[2][1][1] == COMPILER.StringLit("measure3")
        and measure_set[2][2] == ["symbol-value", ["quote", "ide-buffers"]],
        "measure3 root construction shape drift",
    )
    measure3 = decode_buffer_form(measure_set[2][1][2])
    derived = buffer_graph()
    derived["roots"] = {
        "ide-buffers": [["measure3", measure3], ["scratch", scratch]],
        "b": scratch,
    }
    require(derived == buffer_graph(), "source-derived logical buffer graph drift")
    return derived


def reject(label: str, operation: Callable[[], None]) -> str:
    try:
        operation()
    except Option2Error:
        return label
    raise Option2Error(f"negative fixture accepted: {label}")


def prove() -> dict[str, Any]:
    manifest = load_json(MANIFEST)
    require(manifest["artifact_count"] == 19, "candidate role count drift")
    for row in manifest["artifacts"]:
        path = ROOT / row["path"]
        require(
            path.is_file()
            and path.stat().st_size == row["bytes"]
            and sha_bytes(path.read_bytes()) == row["sha256"],
            f"candidate role binding drift: {row['role']}",
        )
    forms = expected_source_forms()
    call_surface = packaged_setup_surface_gate(forms)
    media = build_medium()
    base = geometry()
    historical = append_route(
        "historical", [LEGACY_HELPER, CORRECTED_HELPER])
    diagnostic = append_route(
        "diagnostic", [
            SOURCE.read_text(encoding="utf-8").splitlines()[2],
            SOURCE.read_text(encoding="utf-8").splitlines()[3],
        ])
    for name in ("images", "entries", "resolutions", "roots", "code"):
        require(
            historical["raw"][name] == diagnostic["raw"][name],
            f"historical/diagnostic C2D prefix differs: {name}",
        )
    require(
        historical["terminal_geometry"] == diagnostic["terminal_geometry"],
        "terminal Session geometry differs",
    )
    require(
        [(row["target_symbol"], row["target_symbol_index"])
         for row in historical["rows"]]
        == [(row["target_symbol"], row["target_symbol_index"])
            for row in diagnostic["rows"]],
        "helper directory identities differ",
    )
    graph = source_buffer_graph(forms)
    handoff_contract = {
        "host": {
            "append_operations_completed": 2,
            "modeled_C2J": "CLEAR after each atomic append",
            "modeled_phase_owner": "NONE after each atomic append",
            "modeled_mem_oom": 0,
        },
        "device_required_before_first_measurement_key": {
            "C2J": "64 zero bytes at 0x0005c640",
            "phase_owner": "NONE from linked ELF symbol",
            "mem_oom": 0,
            "buffer_and_arena_root_view": "live memory equals bound logical graph",
        },
        "authority_boundary": (
            "target state is not claimed by the host model; the device runner "
            "must read and reject before input"),
    }
    workload = {
        "setup": [
            f'(load "{REMOTE_SOURCE_NAME}")', '(ide "measure3")'],
        "measurement": {
            "keys": 56, "payload": "a", "injection_width": 1,
            "ack": "live ide-buffers fill after every key",
            "per_key_breakpoints": 0,
            "on_first_failed_fill": ["D60A", "D619", "gc_runs", "PC"],
            "CPU_halts": 1,
        },
    }
    mutations: list[str] = []

    def private_ide_setup_call() -> None:
        mutated = list(forms)
        mutated[1] = COMPILER.parse_one(
            '(%ide-store-buffer(ide-make-buffer "scratch"(list "")))')
        packaged_setup_surface_gate(mutated)
    mutations.append(reject("directory-only-IDE-call", private_ide_setup_call))

    def changed_product() -> None:
        changed = bytearray(D81.visible_files(PRODUCT_D81)["code.bin"])
        changed[0] ^= 1
        require(bytes(changed) == D81.visible_files(MEDIUM)["code.bin"],
                "changed product payload accepted")
    mutations.append(reject("product-payload-bit", changed_product))

    def reversed_helpers() -> None:
        route = append_route("mutation-reversed", [CORRECTED_HELPER, LEGACY_HELPER])
        require(route["raw"]["code"] == historical["raw"]["code"],
                "reordered helper prefix accepted")
    mutations.append(reject("helper-order", reversed_helpers))

    def scratch_character() -> None:
        mutated = json.loads(json.dumps(graph))
        mutated["roots"]["b"]["lines"][0] = SCRATCH[:-1] + "d"
        require(mutated == graph, "scratch character mutation accepted")
    mutations.append(reject("scratch-character", scratch_character))

    def scratch_point() -> None:
        mutated = json.loads(json.dumps(graph))
        mutated["roots"]["b"]["point"] = [0, 33]
        require(mutated == graph, "scratch point mutation accepted")
    mutations.append(reject("scratch-point", scratch_point))

    def dirty_transaction() -> None:
        state = {"C2J": "ACTIVE", "phase_owner": "APPEND", "mem_oom": 1}
        require(
            state == {"C2J": "CLEAR", "phase_owner": "NONE", "mem_oom": 0},
            "dirty handoff accepted")
    mutations.append(reject("dirty-handoff", dirty_transaction))

    def bulk_input() -> None:
        mutated = json.loads(json.dumps(workload))
        mutated["measurement"]["injection_width"] = 10
        require(mutated == workload, "bulk measurement input accepted")
    mutations.append(reject("bulk-input", bulk_input))

    def per_key_breakpoint() -> None:
        mutated = json.loads(json.dumps(workload))
        mutated["measurement"]["per_key_breakpoints"] = 56
        require(mutated == workload, "per-key breakpoint plan accepted")
    mutations.append(reject("per-key-breakpoints", per_key_breakpoint))

    result = {
        "format": FORMAT,
        "recorded_on": date.today().isoformat(),
        "status": "passed-five-option2-equivalence-obligations",
        "candidate": {
            "link": 83,
            "manifest": bind(MANIFEST),
            "artifact_set_sha256": manifest["artifact_set_sha256"],
            "media_product_build_id": manifest["product_build_id"],
            "profile_build_id": manifest["profile_build_id"],
            "roles": [
                {key: row[key] for key in ("role", "bytes", "sha256")}
                for row in manifest["artifacts"]
            ],
            "base_geometry": base,
            "resident_product_and_all_19_roles_changed": 0,
        },
        "diagnostic_medium": {
            "medium": bind(MEDIUM),
            "base_product_medium": bind(PRODUCT_D81),
            "inventory": media,
            "classification": "non-promotable-product-D81-plus-one-source",
        },
        "source": {
            "fixture": bind(SOURCE),
            "remote_name": REMOTE_SOURCE_NAME,
            "forms": [normalized_form(form) for form in forms],
            "packaged_call_surface": call_surface,
        },
        "persistent_prefix_equivalence": {
            "historical": {
                key: value for key, value in historical.items() if key != "raw"
            },
            "diagnostic": {
                key: value for key, value in diagnostic.items() if key != "raw"
            },
            "comparison": "byteidentical appended C2D/code spans and identities",
        },
        "handoff_logical_state": graph,
        "transaction_handoff": handoff_contract,
        "device_workload_contract": workload,
        "mutations_rejected": mutations,
        "execution_witness": {
            "forms_parsed": len(forms),
            "separate_session_appends_per_route": 2,
            "routes_compared": 2,
            "D81_product_payloads_compared": len(media["product_payloads"]),
            "mutations": len(mutations),
        },
        "authority": {
            "commission": bind(COMMISSION),
            "driver": bind(Path(__file__).resolve()),
            "session_host": bind(ROOT / "tools/host-lisp/c2_product_session_host.py"),
            "candidate_C2D": bind(STATIC_C2D),
            "candidate_code": bind(STATIC_CODE),
        },
        "claim_limit": (
            "Host proof of product/media identity, ordered persistent-prefix "
            "equivalence and logical reachable handoff state. Physical C2J, "
            "phase-owner, mem_oom and target heap/string view remain mandatory "
            "live preconditions before the authorized device workload."),
    }
    write_json(RECEIPT, result)
    return result


def check() -> dict[str, Any]:
    value = load_json(RECEIPT)
    require(value["format"] == FORMAT, "receipt format drift")
    require(value["status"] == "passed-five-option2-equivalence-obligations",
            "Option-2 proof is not green")
    for row in value["authority"].values():
        path = ROOT / row["path"]
        require(bind(path) == row, f"receipt authority drift: {path}")
    require(bind(MEDIUM) == value["diagnostic_medium"]["medium"],
            "diagnostic medium drift")
    require(len(value["mutations_rejected"]) == 8, "mutation count drift")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args()
    result = prove() if args.command == "build" else check()
    witness = result["execution_witness"]
    print(
        "c2-v126-editor-option2-medium: PASS "
        f"payloads={witness['D81_product_payloads_compared']} "
        f"appends={witness['separate_session_appends_per_route']}x"
        f"{witness['routes_compared']} mutations={witness['mutations']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        Option2Error, SESSION.SessionHostError, OSError, ValueError,
        KeyError, json.JSONDecodeError, subprocess.SubprocessError,
    ) as error:
        print("c2-v126-editor-option2-medium: FIRST RED: " + str(error))
        raise SystemExit(2)
