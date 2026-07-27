#!/usr/bin/env python3
"""Complete the E5 WPLTO after its read-only work-header First Red.

The sole product closure link already exists.  This driver copies that frozen
tree, restores the explicitly saved unbound PRG in the copy, and runs only the
declared publish-last, pack, and structural artifact gates.  Compiler and
linker entry points are trapped.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_lite_v6_link55_append_suffix_fusion_artifact_replay as PROFILE  # noqa: E402
import c2_product_substitution_link as PRODUCT  # noqa: E402


EVIDENCE = ROOT / "tests/bytecode/dialect-v2/evidence/architecture-blocks"
SOURCE = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-terminal-detail-seam-wplto-inventory-replay2")
FIRST_COMPLETION_OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-terminal-detail-seam-wplto-artifact-completion")
OUT = ROOT / (
    "build/c2.2/substitution/"
    "link58-matrix-addenda-terminal-detail-seam-wplto-artifact-completion2")
FIRST_RED = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-"
    "inventory-replay2-internal.json")
RECEIPT = EVIDENCE / (
    "c2.2-link58-matrix-addenda-terminal-detail-seam-wplto-"
    "artifact-completion2-receipt.json")
FINAL_NAME = "lisp65-c2-substitution-linked.prg"
EXPECTED_LINKED_SHA = (
    "bbd8508adec846ee84fe8f5fbf8ad6549c1695a8f2eabed9fcf39a78adeda0f0")
EXPECTED_UNBOUND_SHA = (
    "38d0788d8fa086079e07269e3d5b4c6f49ef2acecebf63f04f080e84ad42d067")
EXPECTED_ELF_SHA = (
    "c60b3e906d99698f0ff0522ef466d6f4008938eb6cbff5a9e825fab3613d61ee")
EXPECTED_MAP_SHA = (
    "b9fae173635641f827c9c1c99184ab43c9bc79c9bd16d154a94098c725838dd9")
EXPECTED_LTO_SHA = (
    "63016f0fd7c158446e8b4eab00d6090c9cb58c89d060aac80cdf89a9843cbd2e")


class CompletionError(RuntimeError):
    pass


def require(value: bool, message: str) -> None:
    if not value:
        raise CompletionError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"artifact absent: {path}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def snapshot(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "mode": oct(path.stat().st_mode & 0o777),
            "sha256": sha(path),
        }
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")


def configure_profile() -> None:
    PROFILE.configure()
    require(
        PRODUCT.VERIFIER_BINDING_BASE == 0xB94E
        and PRODUCT.runtime_binding_bytes() == 40
        and PRODUCT.total_publish_last_bytes() == 42
        and PRODUCT.E000_FINAL_FLOOR_BYTES == 54
        and len(PRODUCT.SESSION_SLICE_SPECS) == 48,
        "artifact completion profile differs from linked WPLTO profile")


def validate_source() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    require(SOURCE.is_dir() and FIRST_RED.is_file(),
            "artifact-completion authority absent")
    first = json.loads(FIRST_RED.read_text(encoding="utf-8"))
    require(
        first["diagnostic"]["type"] == "PermissionError"
        and first["diagnostic"]["message"].endswith(
            "c2-kernal-window.generated.h'")
        and first["execution_accounting"]["product_closure_links"] == 1
        and first["execution_accounting"]["hardware_runs"] == 0,
        "artifact-completion First Red drift")
    tree = snapshot(SOURCE)
    require(tree and all((int(row["mode"], 8) & 0o222) == 0
                         for row in tree.values()),
            "source WPLTO tree is not read-only")
    final = SOURCE / FINAL_NAME
    checks = {
        final: EXPECTED_LINKED_SHA,
        SOURCE / "lisp65-c2-substitution-unbound.prg":
            EXPECTED_UNBOUND_SHA,
        Path(str(final) + ".elf"): EXPECTED_ELF_SHA,
        Path(str(final) + ".map"): EXPECTED_MAP_SHA,
        Path(str(final) + ".lto.o"): EXPECTED_LTO_SHA,
    }
    require(all(path.is_file() and sha(path) == expected
                for path, expected in checks.items()),
            "linked WPLTO authority bytes drift")
    require(
        FIRST_COMPLETION_OUT.is_dir()
        and (FIRST_COMPLETION_OUT /
             "lisp65-c2-substitution-unbound.prg").is_file()
        and (FIRST_COMPLETION_OUT.stat().st_mode & 0o222) == 0,
        "first artifact-completion directory-mode Red drift")
    return tree, first


def copy_and_restore_unbound() -> tuple[Path, dict[str, str]]:
    require(not OUT.exists() and not RECEIPT.exists(),
            "artifact completion is one-shot")
    shutil.copytree(SOURCE, OUT, copy_function=shutil.copy2)
    os.chmod(OUT, 0o755)
    for path in sorted(OUT.rglob("*")):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    final = OUT / FINAL_NAME
    unbound = OUT / "lisp65-c2-substitution-unbound.prg"
    partial_sha = sha(final)
    unbound_sha = sha(unbound)
    final.write_bytes(unbound.read_bytes())
    unbound.unlink()
    require(sha(final) == EXPECTED_UNBOUND_SHA,
            "copied product did not restore the declared unbound identity")
    return final, {
        "partial_window_bound_sha256": partial_sha,
        "restored_unbound_sha256": unbound_sha,
    }


def build() -> dict[str, Any]:
    before, first = validate_source()
    configure_profile()
    final, restoration = copy_and_restore_unbound()
    elf = Path(str(final) + ".elf")
    map_path = Path(str(final) + ".map")
    lto = Path(str(final) + ".lto.o")
    immutable_link_outputs = {
        "elf": sha(elf), "map": sha(map_path), "lto": sha(lto),
        "stdout": sha(Path(str(final) + ".link.stdout.txt")),
        "stderr": sha(Path(str(final) + ".link.stderr.txt")),
    }

    original_run = subprocess.run
    original_compile = PRODUCT.compile_link
    original_single = PRODUCT.single_link
    commands: list[str] = []

    def guarded_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        executable = Path(str(
            command[0] if isinstance(command, (list, tuple))
            else command)).name
        lowered = executable.lower()
        require(
            "clang" not in lowered and lowered not in {
                "cc", "gcc", "ld", "ld.lld", "lld",
                "mos-mega65-clang"},
            f"artifact completion attempted compiler/linker: {executable}")
        commands.append(executable)
        return original_run(command, *args, **kwargs)

    def prohibited(*_args: Any, **_kwargs: Any) -> Any:
        raise CompletionError(
            "compiler/linker entry point entered during artifact completion")

    try:
        subprocess.run = guarded_run
        PRODUCT.compile_link = prohibited
        PRODUCT.single_link = prohibited
        PRODUCT.finish_single_link(
            OUT, final, OUT / "resolved-profile.txt")
    finally:
        subprocess.run = original_run
        PRODUCT.compile_link = original_compile
        PRODUCT.single_link = original_single

    after_link_outputs = {
        "elf": sha(elf), "map": sha(map_path), "lto": sha(lto),
        "stdout": sha(Path(str(final) + ".link.stdout.txt")),
        "stderr": sha(Path(str(final) + ".link.stderr.txt")),
    }
    require(immutable_link_outputs == after_link_outputs,
            "artifact completion changed a compiler/linker output")
    require(before == snapshot(SOURCE),
            "artifact completion changed the frozen WPLTO source tree")

    structure_path = OUT / "product-substitution-link.json"
    total_path = OUT / "total-publish-last-domain.json"
    structure = json.loads(structure_path.read_text(encoding="utf-8"))
    total = json.loads(total_path.read_text(encoding="utf-8"))
    require(
        structure["status"] == "passed"
        and structure["product_closure_link_count"] == 1
        and total["status"] == "passed"
        and total["declared_domain_bytes"] == 42,
        "artifact completion did not close the generic product gates")

    value = {
        "format":
            "lisp65-c2-link58-matrix-addenda-terminal-detail-seam-"
            "WPLTO-artifact-completion-v1",
        "recorded_on": "2026-07-23",
        "status":
            "passed-existing-WPLTO-link-publish-last-and-structural-gates",
        "promotable": False,
        "authority": {
            "permission_first_red": bind(FIRST_RED),
            "completion_driver": bind(Path(__file__)),
            "class_A_root_mode_first_red": {
                "path": FIRST_COMPLETION_OUT.relative_to(ROOT).as_posix(),
                "root_mode":
                    oct(FIRST_COMPLETION_OUT.stat().st_mode & 0o777),
                "diagnostic":
                    "copied root directory remained 0555; removing the "
                    "restored unbound work file was denied before any "
                    "publish-last or product gate ran",
            },
            "source_product_partial": {
                "path": (SOURCE / FINAL_NAME).relative_to(ROOT).as_posix(),
                "sha256": EXPECTED_LINKED_SHA,
            },
            "source_product_unbound": {
                "path": (
                    SOURCE / "lisp65-c2-substitution-unbound.prg"
                ).relative_to(ROOT).as_posix(),
                "sha256": EXPECTED_UNBOUND_SHA,
            },
        },
        "class_A_correction": {
            "cause":
                "the replay copied the seed work header read-only; the sole "
                "product link completed and the two-byte KERNAL patch landed "
                "before the header write was rejected",
            "correction":
                "copy the frozen tree with its root and members writable, "
                "restore its declared unbound PRG, and continue only "
                "artifact-side publication and gates",
            "product_source_bytes_changed": 0,
            "capacity_effect_bytes": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
        },
        "restoration": restoration,
        "product_identity": {
            "product": bind(final),
            "elf": bind(elf),
            "map": bind(map_path),
            "lto_object": bind(lto),
        },
        "publish_last": total,
        "generic_structure": structure,
        "immutable_source_tree": {
            "files": len(before),
            "byte_and_mode_identity": "unchanged",
        },
        "execution_accounting": {
            "source_whole_program_lto_closure_links": 1,
            "artifact_completion_compiler_runs": 0,
            "artifact_completion_linker_runs": 0,
            "new_product_links": 0,
            "hardware_runs": 0,
            "read_only_or_artifact_tool_invocations": commands,
        },
        "next_gate":
            "fresh current-profile replacement-gate replay and simultaneous "
            "wall qualification against this completed artifact",
    }
    write_json(RECEIPT, value)
    for path in OUT.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o444)
    os.chmod(RECEIPT, 0o444)
    return value


def main() -> int:
    try:
        value = build()
    except Exception as error:
        print(
            "c2-matrix-addenda-terminal-detail-seam-artifact-completion: "
            "FIRST RED: " + str(error),
            file=sys.stderr)
        return 2
    structure = value["generic_structure"]
    print(
        "c2-matrix-addenda-terminal-detail-seam-artifact-completion: PASS "
        f"product={value['product_identity']['product']['sha256']} "
        f"e000={structure['actual_e000_future_margin_bytes']} "
        "compiler=0 linker=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
