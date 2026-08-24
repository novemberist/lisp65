#!/usr/bin/env python3
"""Materialize and verify the linker-free v1.5.0 release input closure."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "tools/host-lisp"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

import bytecode_p0_stdlib as STD  # noqa: E402
import c2_lite_v6_product_probe as V6  # noqa: E402
import c2_link95_product_card as L95  # noqa: E402
import c2_repl_direct_expression_gate as DIRECT  # noqa: E402
import c2_startup_require_experience_gate as EXPERIENCE  # noqa: E402
import c2_substitution_artifacts as SUBSTITUTION  # noqa: E402


BUILD = ROOT / "build/c2.3/v1.5.0-release-preflight"
STATIC = BUILD / "static-plane/narrow-static"
SOURCES = BUILD / "sources"
STDLIB_PREFIX = STATIC / "stdlib-p0"
STDLIB = STDLIB_PREFIX.with_suffix(".manifest.json")
PRODUCT = STATIC / "product/substitution-artifacts.json"
V6_PLANE = STATIC / "v6-semantics"
CONTRACT = ROOT / "config/c2-v150-release-contract.json"
CHARTER = ROOT / "docs/planning/v1.5.0-release-work-plan.md"
DIRECT_RECEIPT = DIRECT.RECEIPT
EXPERIENCE_RECEIPT = EXPERIENCE.RECEIPT
PROFILE = ROOT / "config/c2-l-full-product-profile.json"
HEADER = ROOT / "src/c2_lite_static_plane.h"
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-release-preflight-receipt.json"
)
DRIVER = Path(__file__).resolve()
PUBLIC_AUTHORITY = ROOT / "config/c2-v150-public-build-authority.json"
PUBLIC_PREFLIGHT = ROOT / (
    "build/c2.3/v1.5.0-public-selected/product-inputs/"
    "public-release-authorities/v1.5-linker-free-preflight.json")
FORMAT = "lisp65-c2.3-v150-release-preflight-v1"
STATUS = "V150-LINKER-FREE-INPUT-CLOSURE-GREEN; PRODUCT-CARD-UNUSED"
BASE_SPECS = L95.specs()[1:]
ARTIFACT_FIELDS = (
    "blob", "directory", "disasm", "header", "c_source", "embed",
)


class PreflightError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise PreflightError(message)


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
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    }


def run(command: list[str], label: str) -> dict[str, Any]:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False,
    )
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    raw = result.stdout.encode()
    return {
        "status": "passed", "output_bytes": len(raw),
        "output_sha256": hashlib.sha256(raw).hexdigest(),
    }


def specs() -> tuple[tuple[str, str, Path], ...]:
    return (
        ("stdlib-p0", "stdlib", STDLIB),
        *BASE_SPECS,
    )


def source_suite() -> tuple[dict[str, Any], dict[str, bytes]]:
    runtime = DIRECT.candidate_runtime_source()
    require_source = EXPERIENCE.candidate_require_source(
        EXPERIENCE.REQUIRE_SOURCE.read_text(encoding="utf-8"))
    banner_base = (ROOT / "lib/repl-banner.lisp").read_text(encoding="utf-8")
    require(banner_base.count("WORKBENCH 1.4.0") == 1,
            "accepted banner source is absent or ambiguous")
    banner = banner_base.replace("WORKBENCH 1.4.0", "WORKBENCH 1.5.0", 1)
    paths = {
        "runtime": SOURCES / "eval-runtime.lisp",
        "require": SOURCES / "stdlib-require.lisp",
        "banner": SOURCES / "repl-banner.lisp",
    }
    suite = DIRECT.candidate_suite(paths["runtime"], require_path=paths["require"])
    old_banner = [row for row in suite["sources"]
                  if str(row).endswith("/repl-banner.lisp")]
    require(len(old_banner) == 1, "candidate suite banner source is ambiguous")
    suite["sources"] = [
        str(paths["banner"]) if row == old_banner[0] else row
        for row in suite["sources"]
    ]
    return suite, {
        "runtime": runtime.encode(), "require": require_source.encode(),
        "banner": banner.encode(),
    }


def write_sources(texts: dict[str, bytes]) -> None:
    SOURCES.mkdir(parents=True, exist_ok=True)
    for name, raw in texts.items():
        (SOURCES / {
            "runtime": "eval-runtime.lisp", "require": "stdlib-require.lisp",
            "banner": "repl-banner.lisp",
        }[name]).write_bytes(raw)


def emit_static_plane() -> dict[str, Any]:
    require(not BUILD.exists(), "v1.5 preflight build must start fresh")
    suite, texts = source_suite()
    write_sources(texts)
    STATIC.mkdir(parents=True)
    with DIRECT.historical_read_line_input():
        emitted = STD.emit_artifacts(
            str(DIRECT.BASE_SUITE), suite, str(STDLIB_PREFIX),
            artifact_role="stdlib",
        )
    manifest = load(Path(emitted["manifest"]))
    DIRECT.validate_candidate_publication(manifest)
    entry_names = {str(row.get("name")) for row in manifest["entries"]}
    require(
        "lcc-run" in entry_names
        and "WORKBENCH 1.5.0" in texts["banner"].decode()
        and b"loading " in texts["require"],
        "successor stdlib freight did not reach the emitted plane",
    )
    old_sub = (SUBSTITUTION.BUILD, SUBSTITUTION.SPECS)
    old_v6 = (V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS)
    try:
        SUBSTITUTION.BUILD = STATIC / "product"
        SUBSTITUTION.SPECS = specs()
        product = SUBSTITUTION.build()
        static_bytes = sum(int(load(path)["code_bytes"])
                           for _key, _name, path in specs())
        V6.OUT = V6_PLANE
        V6.PRODUCT_IDENTITY = PRODUCT
        V6.STATIC_CODE_BYTES = static_bytes
        V6.A.SPECS = specs()
        V6_PLANE.mkdir(parents=True)
        semantics = V6.host_semantics()
    finally:
        SUBSTITUTION.BUILD, SUBSTITUTION.SPECS = old_sub
        V6.OUT, V6.PRODUCT_IDENTITY, V6.STATIC_CODE_BYTES, V6.A.SPECS = old_v6
    require(product["images"] == 6
            and semantics["static_bank2"]["code_bytes"] == static_bytes,
            "v1.5 static plane failed six-image closure")
    return {"product": product, "semantics": semantics,
            "static_code_bytes": static_bytes}


def manifest_artifacts(path: Path) -> list[dict[str, Any]]:
    value = load(path)
    paths: list[Path] = [path]
    for key in ARTIFACT_FIELDS:
        raw = value.get(key)
        if not isinstance(raw, str):
            continue
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        if candidate.is_file():
            paths.append(candidate)
    external = value.get("external_image", {})
    if isinstance(external, dict) and isinstance(external.get("path"), str):
        candidate = Path(external["path"])
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        paths.append(candidate)
    unique = {item.resolve(): item for item in paths}
    return [bind(unique[key]) for key in sorted(unique, key=str)]


def geometry() -> dict[str, Any]:
    product = load(PRODUCT)
    static_bytes = sum(int(load(path)["code_bytes"])
                       for _key, _name, path in specs())
    return {
        "static_code_bytes": static_bytes,
        "bank2_headroom_bytes": 65536 - static_bytes,
        "entries": int(product["entries"]),
        "resolutions": int(product["resolutions"]),
        "roots": int(product["roots"]),
        "direct_entry_refs": L95.L94.direct_entry_census(STATIC / "product"),
        "product_build_id": str(product["product_build_id_hex"]),
        "bank2_sha256": hashlib.sha256(
            (V6_PLANE / "bank2-static-code.bin").read_bytes()).hexdigest(),
    }


def host_gates() -> dict[str, Any]:
    return {
        "f018b_content_safe_reads": run([
            sys.executable,
            "tools/host-lisp/c2_f018b_content_safe_reads.py", "check"],
            "F018B content-safe read gate"),
        "direct_expression": run([
            sys.executable, "tools/host-lisp/c2_repl_direct_expression_gate.py",
            "check"], "direct-expression gate"),
        "experience": run([
            sys.executable, "tools/host-lisp/c2_startup_require_experience_gate.py",
            "check"], "startup/require experience gate"),
        "trace_abi": run([
            sys.executable, "tools/host-lisp/c2_trace_core_abi.py", "check"],
            "trace ABI gate"),
        "terminal_guard": run([
            sys.executable, "tools/host-lisp/c2_terminal_return_guard_gate.py",
            "selftest"], "terminal guard gate"),
        "packed_callees": run([
            sys.executable, "tools/host-lisp/c2_packed_symbolic_callee_closure.py",
            "audit", "--product", PRODUCT.relative_to(ROOT).as_posix()],
            "packed symbolic callee closure"),
    }


def derive() -> dict[str, Any]:
    contract = load(CONTRACT)
    direct = load(DIRECT_RECEIPT)
    experience = load(EXPERIENCE_RECEIPT)
    require(
        contract.get("format") == "lisp65-c2-v150-release-contract-v1"
        and contract.get("release") == "v1.5.0"
        and contract.get("build", {}).get("product_cards") == 1
        and direct.get("status")
            == "PASSED-DIRECT-EXPRESSION-WIDENING-HOST-AND-ARTIFACT-GATES"
        and experience.get("status")
            == "PASSED-BOOT-LIVENESS-AND-REQUIRE-INTENT-HOST-GATES",
        "v1.5 commissioned freight authority drift",
    )
    candidate_sources = [
        bind(SOURCES / "eval-runtime.lisp"),
        bind(SOURCES / "stdlib-require.lisp"),
        bind(SOURCES / "repl-banner.lisp"),
    ]
    input_manifests = {key: manifest_artifacts(path)
                       for key, _name, path in specs()}
    geo = geometry()
    require(0 < geo["static_code_bytes"] < 65536
            and geo["bank2_headroom_bytes"] > 0,
            "v1.5 linker-free Bank-2 capacity red")
    return {
        "format": FORMAT, "recorded_on": "2026-08-11", "status": STATUS,
        "attempt_accounting": {
            "product_cards_authorized": 1, "product_cards_consumed": 0,
            "product_links": 0, "device_contacts": 0,
        },
        "scope": {
            "release": "v1.5.0", "link": 97,
            "activation_defines": contract["build"]["activation_defines"],
            "historical_worlds_changed": 0,
        },
        "geometry": geo,
        "authorities": {
            "contract": bind(CONTRACT), "charter": bind(CHARTER),
            "direct_expression": bind(DIRECT_RECEIPT),
            "experience": bind(EXPERIENCE_RECEIPT),
            "candidate_sources": candidate_sources,
            "input_manifests_and_payloads": input_manifests,
            "product": bind(PRODUCT),
            "bank2": bind(V6_PLANE / "bank2-static-code.bin"),
            "driver": bind(DRIVER),
        },
        "host_gates": host_gates(),
        "producer_inversion": {
            "input_count": sum(len(rows) for rows in input_manifests.values())
                + len(candidate_sources) + 4,
            "symbol_space_is_not_an_input": True,
            "all_inputs_content_bound": True,
        },
        "claim_limit": (
            "Linker-free v1.5 input closure only; the one product card, media, "
            "device, release and publication remain unclaimed."),
    }


def validate(value: dict[str, Any], *, verify: bool) -> None:
    require(
        value.get("format") == FORMAT and value.get("status") == STATUS
        and value.get("attempt_accounting") == {
            "product_cards_authorized": 1, "product_cards_consumed": 0,
            "product_links": 0, "device_contacts": 0}
        and value.get("scope", {}).get("historical_worlds_changed") == 0
        and value.get("producer_inversion", {}).get(
            "symbol_space_is_not_an_input") is True
        and value.get("producer_inversion", {}).get(
            "all_inputs_content_bound") is True,
        "v1.5 preflight claim drift",
    )
    if verify:
        require(value == derive(), "v1.5 preflight receipt is stale")


def mutations(value: dict[str, Any]) -> list[str]:
    cases: dict[str, Callable[[dict[str, Any]], None]] = {
        "hide-card": lambda x: x["attempt_accounting"].update(
            product_cards_authorized=0),
        "consume-card": lambda x: x["attempt_accounting"].update(
            product_cards_consumed=1),
        "claim-link": lambda x: x["attempt_accounting"].update(product_links=1),
        "claim-device": lambda x: x["attempt_accounting"].update(
            device_contacts=1),
        "change-history": lambda x: x["scope"].update(
            historical_worlds_changed=1),
        "admit-symbol-space": lambda x: x["producer_inversion"].update(
            symbol_space_is_not_an_input=False),
        "unbound-input": lambda x: x["producer_inversion"].update(
            all_inputs_content_bound=False),
    }
    rejected: list[str] = []
    for name, mutate in cases.items():
        candidate = deepcopy(value); mutate(candidate)
        try:
            validate(candidate, verify=False)
        except PreflightError:
            rejected.append(name)
    require(len(rejected) == len(cases), "v1.5 preflight mutation survived")
    return rejected


def prepare() -> int:
    require(not RECEIPT.exists(), "v1.5 preflight receipt already exists")
    emit_static_plane()
    value = derive()
    value["mutations_rejected"] = mutations(value)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 preflight: PASS "
          f"bank2={value['geometry']['static_code_bytes']} "
          f"headroom={value['geometry']['bank2_headroom_bytes']} "
          f"id={value['geometry']['product_build_id']}")
    return 0


def validate_public_projection(value: dict[str, Any],
                               rejected: list[str]) -> None:
    """Validate the living product projection beside the sealed receipt."""
    authority = load(PUBLIC_AUTHORITY)
    current = load(PUBLIC_PREFLIGHT)
    require(
        authority.get("format") == "lisp65-c2-lite-public-build-authority-v3"
        and authority.get("release") == "v1.5.0"
        and current.get("format") == FORMAT
        and current.get("status") == STATUS
        and current.get("geometry") == value.get("geometry")
        and current.get("attempt_accounting")
            == value.get("attempt_accounting")
        and current.get("producer_inversion") == {
            "all_inputs_content_bound": True,
            "input_count": 48,
            "private_evidence_is_not_an_input": True,
            "symbol_space_is_not_an_input": True,
        }
        and current.get("mutations_rejected") == [
            *rejected, "admit-private-evidence"],
        "current public v1.5 preflight projection drift")
    bindings = current["authorities"]
    manifest_rows = [
        row for family in bindings["input_manifests_and_payloads"].values()
        for row in family if row["path"].endswith(".manifest.json")]
    rows = [
        bindings["contract"], bindings["product"], bindings["bank2"],
        bindings["public_driver"], *bindings["candidate_sources"],
        *manifest_rows,
    ]
    require(all(bind(ROOT / row["path"]) == row for row in rows),
            "current public v1.5 preflight input binding drift")
    selected_product = load(ROOT / authority["product_manifest_path"])
    projected_product = load(ROOT / bindings["product"]["path"])
    by_path = lambda items: sorted(items, key=lambda row: row["path"])
    require(len(manifest_rows) == 6
            and by_path(projected_product["manifests"])
                == by_path(selected_product["manifests"])
                == by_path(manifest_rows),
            "current public v1.5 manifest projection/product mismatch")


def check() -> int:
    # The tracked receipt witnesses the commissioned pre-link world.  The
    # living authority is the public selected-product projection emitted by
    # the current product link cycle; checking the historical build directory
    # would reintroduce mutable global manifest paths and break idempotence.
    value = load(RECEIPT)
    rejected = value.pop("mutations_rejected", None)
    validate(value, verify=False)
    require(rejected == mutations(value), "v1.5 preflight mutation set drift")
    validate_public_projection(value, rejected)
    print("v1.5 preflight check: PASS")
    return 0


def rebind() -> int:
    require(BUILD.is_dir() and PRODUCT.is_file(),
            "v1.5 preflight artifacts absent for authority rebind")
    value = derive(); value["mutations_rejected"] = mutations(value)
    RECEIPT.write_bytes(canonical(value))
    print("v1.5 preflight authority rebind: PASS product-links=0 card=0/1")
    return 0


def selftest() -> int:
    contract = load(CONTRACT)
    require(contract.get("accepted_by") == "0c99ce21"
            and contract.get("build", {}).get("resident_delta_bytes") == 0,
            "v1.5 release contract drift")
    print("v1.5 preflight selftest: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "rebind", "check", "selftest"))
    action = parser.parse_args().action
    return {"prepare": prepare, "rebind": rebind,
            "check": check, "selftest": selftest}[action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PreflightError, STD.StdlibCheckError, DIRECT.GateError,
            EXPERIENCE.ExperienceError, OSError, ValueError, KeyError,
            json.JSONDecodeError, subprocess.SubprocessError) as error:
        print(f"v1.5 preflight: FAIL: {error}", file=sys.stderr)
        raise SystemExit(2)
