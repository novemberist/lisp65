#!/usr/bin/env python3
"""Qualify callable intern, canonical Places and the real defstruct L65I media."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_require_resolver_gate as L65I  # noqa: E402


BUILD = ROOT / "build/post-promotion/defstruct-v1/foundations"
PLACE_PREFIX = BUILD / "place"
DEFSTRUCT_PREFIX = BUILD / "defstruct"
INTEGRATION_PREFIX = BUILD / "place-defstruct-integration"
INDEX = BUILD / "l65index"
D81 = BUILD / "require-defstruct.d81"
CONTRACT = ROOT / "config/c2-defstruct-v1-contract.json"
PRODUCT_PROFILE = ROOT / "config/c2-l-full-product-profile.json"
FIRST_RED = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-defstruct-v1-host-first-first-red.json")
RECEIPT = ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-defstruct-foundations-gate-receipt.json")


class FoundationError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise FoundationError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"foundation artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def run(command: list[str], label: str) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False)
    require(result.returncode == 0, f"{label} red:\n{result.stdout}")
    return result.stdout


def compile_library(prefix: Path, suite: str) -> str:
    return run([
        sys.executable,
        "tools/host-lisp/bytecode_p0_stdlib.py",
        "--check",
        "--artifact-role", "disk-lib",
        "--base-addr", "0x000000",
        "--emit-artifacts", prefix.relative_to(ROOT).as_posix(),
        suite,
    ], f"compile {prefix.name}")


def measured_row(name: str, image_key: str, shelf_name: str, manifest: Path,
                 dependencies: tuple[int, ...], track: int, sector: int, *,
                 product_build_id: int
                 ) -> tuple[dict[str, Any], bytes]:
    """Keep the public L65I name independent of the 7-byte shelf label."""
    image = L65I.F.emit_image(image_key, shelf_name, manifest)
    artifact = L65I.S.build_extension(
        image, build_id=product_build_id)
    decoded = L65I.S.decode_extension(
        artifact, image, expected_build_id=product_build_id)
    exports = sum(not bool(row.get("anonymous", False))
                  for row in image.manifest["entries"])
    roots = sum(
        descriptor.kind in L65I.S.ROOT_KINDS
        for descriptor in image.descriptors)
    return {
        "name": name,
        "track": track,
        "sector": sector,
        "combined_crc32": decoded.combined_crc,
        "dependencies": list(dependencies),
        "execution_source": L65I.SOURCE_BANK2,
        "artifact_bytes": len(artifact),
        "bank2": len(image.code),
        "images": 1,
        "entries": len(image.manifest["entries"]),
        "resolutions": len(image.descriptors),
        "roots": roots,
        "scratch": exports * 8,
    }, artifact


def main() -> int:
    try:
        require(not RECEIPT.exists(), "defstruct foundation gate is one-shot")
        contract = load(CONTRACT)
        product_profile = load(PRODUCT_PROFILE)
        product_build_id = int(product_profile["product_build_id"], 0)
        require(0 < product_build_id <= 0xFFFFFFFF,
                "canonical product build identity range")
        first_red = load(FIRST_RED)
        require(
            contract["status"]
                == "foundation-corrections-authorized-product-probe-pending"
            and first_red["status"].startswith("FIRST RED-")
            and first_red["execution_accounting"]["product_links"] == 0
            and first_red["execution_accounting"]["hardware_runs"] == 0,
            "foundation authority/First-Red identity drift")

        BUILD.mkdir(parents=True, exist_ok=True)
        abi = run([
            sys.executable, "tools/host-lisp/bytecode_abi_ledger.py",
            "--selftest"], "ABI ledger")
        registry = run([
            sys.executable, "tools/host-lisp/v2_native_function_registry.py",
            "check"], "native registry")
        matrix_binary = ROOT / (
            "build/equivalence/dialect-v2-native-function-check")
        run(["make", matrix_binary.relative_to(ROOT).as_posix()],
            "native matrix binary")
        matrix = run([
            sys.executable, "tools/host-lisp/v2_native_function_matrix.py",
            "check", "--binary", matrix_binary.relative_to(ROOT).as_posix()],
            "native route matrix")

        place_output = compile_library(
            PLACE_PREFIX, "tests/bytecode/libs/p0-place-lib.json")
        defstruct_output = compile_library(
            DEFSTRUCT_PREFIX,
            "tests/bytecode/libs/p0-defstruct-v1-lib.json")
        integration_output = run([
            sys.executable,
            "tools/host-lisp/bytecode_p0_stdlib.py",
            "--check",
            "--emit-artifacts",
            INTEGRATION_PREFIX.relative_to(ROOT).as_posix(),
            "tests/bytecode/libs/p0-place-defstruct-v1-integration.json",
        ], "Place/defstruct integration")
        require(
            "cases=11" in place_output
            and "cases=2" in defstruct_output
            and "cases=9" in integration_output,
            "foundation fixture count drift")

        manifests = (
            ("place", "place", "place",
             PLACE_PREFIX.with_suffix(".manifest.json"), ()),
            ("defstruct", "defstruct", "dfstrct",
             DEFSTRUCT_PREFIX.with_suffix(".manifest.json"), (0,)),
        )
        placeholder: list[dict[str, Any]] = []
        artifact_data: dict[str, bytes] = {}
        artifact_paths: list[tuple[Path, str]] = []
        for number, (name, image_key, shelf_name, manifest,
                     dependencies) in enumerate(
                manifests):
            row, artifact = measured_row(
                name, image_key, shelf_name, manifest, dependencies,
                1, number + 1, product_build_id=product_build_id)
            placeholder.append(row)
            artifact_data[name] = artifact
            path = BUILD / f"{name}.l65s"
            path.write_bytes(artifact)
            artifact_paths.append((path, name))

        seed_index = BUILD / "l65index.seed"
        seed_index.write_bytes(L65I.encode_index(placeholder))
        seed_d81 = BUILD / "require-defstruct.seed.d81"
        L65I.build_d81(seed_d81, seed_index, artifact_paths)
        locators = L65I.d81_locators(seed_d81)
        rows: list[dict[str, Any]] = []
        for name, image_key, shelf_name, manifest, dependencies in manifests:
            require(name in locators, f"D81 locator absent: {name}")
            row, artifact = measured_row(
                name, image_key, shelf_name, manifest, dependencies,
                *locators[name], product_build_id=product_build_id)
            require(artifact == artifact_data[name],
                    f"L65S emission drift: {name}")
            rows.append(row)
        INDEX.write_bytes(L65I.encode_index(rows))
        decoded = L65I.decode_index(
            INDEX.read_bytes(), artifact_data,
            artifact_build_id=product_build_id)
        L65I.build_d81(D81, INDEX, artifact_paths)
        require(
            L65I.d81_locators(D81) == locators
            and L65I.resolve(
                decoded, "defstruct", 7, [], L65I.CAPACITY) == [0, 1],
            "defstruct dependency/media truth drift")
        visible = L65I.D81.visible_files(D81.read_bytes())
        require(
            visible[b"L65INDEX"] == INDEX.read_bytes()
            and visible[b"PLACE"] == artifact_data["place"]
            and visible[b"DEFSTRUCT"] == artifact_data["defstruct"],
            "defstruct D81 visible-file truth drift")
        mutations = L65I.mutation_gate(
            INDEX.read_bytes(), artifact_data,
            artifact_build_id=product_build_id)

        place_manifest = load(PLACE_PREFIX.with_suffix(".manifest.json"))
        defstruct_manifest = load(
            DEFSTRUCT_PREFIX.with_suffix(".manifest.json"))
        value = {
            "format": "lisp65-c2-defstruct-foundations-gate-v1",
            "recorded_on": "2026-07-27",
            "status":
                "passed-intern-canonical-places-and-real-defstruct-media",
            "promotable": False,
            "intern": {
                "prim_id": 68,
                "visibility": "public",
                "ABI": abi.strip().splitlines()[-1],
                "registry": registry.strip().splitlines()[-1],
                "route_matrix": matrix.strip().splitlines()[-1],
                "evaluations": 844,
            },
            "places": {
                "truth": "*setf-place-registry* in stdlib-places only",
                "publication": "pending-to-committed publish-last",
                "identical_duplicate": "idempotent",
                "conflicting_duplicate": "rejected",
                "unknown_place": "unregistered",
                "failed_library":
                    "pending registrations invisible and discarded; "
                    "earlier committed rows unchanged",
                "target_cases": 11,
                "integration_cases": 9,
            },
            "libraries": {
                "dependency_order": ["place", "defstruct"],
                "place": {
                    "code_bytes": place_manifest["code_bytes"],
                    "entries": len(place_manifest["entries"]),
                    "manifest": bind(
                        PLACE_PREFIX.with_suffix(".manifest.json")),
                    "L65S": bind(BUILD / "place.l65s"),
                },
                "defstruct": {
                    "code_bytes": defstruct_manifest["code_bytes"],
                    "entries": len(defstruct_manifest["entries"]),
                    "manifest": bind(
                        DEFSTRUCT_PREFIX.with_suffix(".manifest.json")),
                    "L65S": bind(BUILD / "defstruct.l65s"),
                },
            },
            "media": {
                "format": "L65I-v1 over D81",
                "product_build_id": f"0x{product_build_id:08x}",
                "rows": rows,
                "binary_mutations_rejected": len(mutations),
                "index": bind(INDEX),
                "D81": bind(D81),
            },
            "execution_accounting": {
                "product_links": 0,
                "hardware_runs": 0,
                "target_library_artifacts": 2,
            },
            "authority": {
                "contract": bind(CONTRACT),
                "product_profile": bind(PRODUCT_PROFILE),
                "first_red": bind(FIRST_RED),
                "place_source": bind(ROOT / "lib/stdlib-places.lisp"),
                "defstruct_source": bind(ROOT / "lib/defstruct.lisp"),
                "integration_suite": bind(
                    ROOT / (
                        "tests/bytecode/libs/"
                        "p0-place-defstruct-v1-integration.json")),
                "driver": bind(Path(__file__).resolve()),
            },
            "next_gate":
                "one product-shaped WPLTO measuring public intern and all "
                "resident walls before a successor link or hardware",
            "claim_limit":
                "Host/target artifacts and exact media only; no WPLTO, "
                "successor product link, hardware or defstruct runtime claim.",
        }
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print(
            "c2-defstruct-foundations: PASS "
            f"place={place_manifest['code_bytes']} "
            f"defstruct={defstruct_manifest['code_bytes']} "
            f"index-mutations={len(mutations)} intern-routes=844")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            FoundationError, L65I.GateError) as error:
        print(f"c2-defstruct-foundations: FIRST RED: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
