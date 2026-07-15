#!/usr/bin/env python3
"""Mutation tests for the runtime repro receipt gate."""

import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import runtime_known_open_check as checker


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_REL = Path("tests/bytecode/runtime/p0-runtime-known-open.json")
EVIDENCE_REL = Path("tests/bytecode/runtime/evidence/ap8.1-g5-78083d6")
HARNESS_REL = Path("scripts/hw-workbench-ux-smoke.sh")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def prepare(raw_root):
    root = Path(raw_root)
    (root / ".git").write_text("gitdir: %s\n" % (ROOT / ".git").resolve(), encoding="utf-8")
    registry = root / REGISTRY_REL
    registry.parent.mkdir(parents=True)
    shutil.copy2(ROOT / REGISTRY_REL, registry)
    shutil.copytree(ROOT / EVIDENCE_REL, root / EVIDENCE_REL)
    harness = root / HARNESS_REL
    harness.parent.mkdir(parents=True)
    shutil.copy2(ROOT / HARNESS_REL, harness)
    return root, registry


def refresh_receipt_binding(root, registry):
    receipt = root / EVIDENCE_REL / "receipt.json"
    digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
    data = json.loads(registry.read_text(encoding="utf-8"))
    data["resolution_receipts"][0]["sha256"] = digest
    write_json(registry, data)


def mutate_receipt(root, registry, change):
    receipt = root / EVIDENCE_REL / "receipt.json"
    data = json.loads(receipt.read_text(encoding="utf-8"))
    change(data)
    write_json(receipt, data)
    refresh_receipt_binding(root, registry)


def update_evidence_hash(receipt, filename, digest):
    for entry in receipt["supporting_evidence"]:
        if entry["file"] == filename:
            entry["sha256"] = digest
            return
    for case in receipt["cases"]:
        for phase in case["phases"]:
            for kind in ("forms", "transcript"):
                if phase[kind]["file"] == filename:
                    phase[kind]["sha256"] = digest
                    return
    raise AssertionError("unbound evidence file: %s" % filename)


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mutate_registry(registry, change):
    data = json.loads(registry.read_text(encoding="utf-8"))
    change(data)
    write_json(registry, data)


def expect_failure(name, mutation):
    with tempfile.TemporaryDirectory(prefix="lisp65-runtime-receipt-") as raw_tmp:
        root, registry = prepare(raw_tmp)
        mutation(root, registry)
        try:
            checker.validate_registry(registry, quiet=True)
        except (checker.CheckError, json.JSONDecodeError, OSError):
            return
        raise AssertionError("%s: mutation was accepted" % name)


def main():
    with tempfile.TemporaryDirectory(prefix="lisp65-runtime-receipt-baseline-") as raw_tmp:
        _, registry = prepare(raw_tmp)
        checker.validate_registry(registry, quiet=True)

    mutations = [
        ("resolved-without-receipt", lambda root, registry: mutate_registry(
            registry, lambda data: data["cases"][0].pop("resolution"))),
        ("wrong-receipt-sha", lambda root, registry: mutate_registry(
            registry, lambda data: data["resolution_receipts"][0].update({"sha256": "0" * 64}))),
        ("missing-receipt", lambda root, registry: (root / EVIDENCE_REL / "receipt.json").unlink()),
        ("fictional-git-provenance", rebind_fictional_provenance),
        ("dry-run-receipt", lambda root, registry: mutate_receipt(
            root, registry, lambda data: data.update({"dry_run": True}))),
        ("missing-phase", lambda root, registry: mutate_receipt(
            root, registry, lambda data: data["cases"][0]["phases"].pop())),
        ("swapped-phase-order", lambda root, registry: mutate_receipt(
            root, registry, lambda data: (
                data["cases"][0]["phases"][0].update({"order": 2}),
                data["cases"][1]["phases"][0].update({"order": 1})
            ))),
        ("duplicate-phase", lambda root, registry: mutate_receipt(
            root, registry, lambda data: data["cases"][0]["phases"][1].update(
                {"id": data["cases"][0]["phases"][0]["id"]}))),
        ("wrong-expect", lambda root, registry: mutate_receipt(
            root, registry, lambda data: data["cases"][0].update({"expect": "nil"}))),
        ("evidence-drift", lambda root, registry: (root / EVIDENCE_REL /
            "hw-workbench-ux-higher-order-remount-every.txt").write_text("drift\n", encoding="utf-8")),
        ("receipt-traversal", lambda root, registry: mutate_registry(
            registry, lambda data: data["cases"][0]["resolution"].update({"receipt": "../receipt.json"}))),
        ("evidence-symlink", make_evidence_symlink),
        ("duplicate-json-key", add_duplicate_key),
        ("unrelated-forms-old-transcript", install_unrelated_forms),
        ("missing-state-anchor", remove_state_anchor),
    ]
    for name, mutation in mutations:
        expect_failure(name, mutation)
    print("runtime-known-open-check selftest: PASS (%d mutations)" % len(mutations))


def make_evidence_symlink(root, registry):
    evidence = root / EVIDENCE_REL / "hw-workbench-ux-higher-order-remount-every.txt"
    outside = root / "outside-evidence.txt"
    shutil.copy2(evidence, outside)
    evidence.unlink()
    evidence.symlink_to(outside)


def add_duplicate_key(root, registry):
    raw = registry.read_text(encoding="utf-8")
    registry.write_text(raw.replace(
        '  "format": "lisp65-runtime-known-open-v2",',
        '  "format": "lisp65-runtime-known-open-v2",\n  "format": "duplicate",',
        1,
    ), encoding="utf-8")


def rebind_fictional_provenance(root, registry):
    evidence = root / EVIDENCE_REL
    receipt_path = evidence / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    old_manifest_sha = receipt["ship"]["manifest_sha256"]
    manifest_path = evidence / receipt["ship"]["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source"]["commit"] = "0" * 40
    manifest["source"]["tree"] = "1" * 40
    write_json(manifest_path, manifest)
    new_manifest_sha = file_sha(manifest_path)
    receipt["ship"].update({
        "source_commit": "0" * 40,
        "source_tree": "1" * 40,
        "manifest_sha256": new_manifest_sha,
    })

    memory_path = evidence / "hw-workbench-overlay-stack-guard-verified-ship-manifest-receipt.json"
    memory = json.loads(memory_path.read_text(encoding="utf-8"))
    memory["manifest_sha256"] = new_manifest_sha
    write_json(memory_path, memory)
    update_evidence_hash(receipt, memory_path.name, file_sha(memory_path))

    for filename in (
        "hw-workbench-overlay-stack-guard-verified-ship-staged.txt",
        "hw-workbench-overlay-stack-guard-verified-ship-post-reset.txt",
    ):
        readback = evidence / filename
        readback.write_text(
            readback.read_text(encoding="utf-8").replace(old_manifest_sha, new_manifest_sha),
            encoding="utf-8",
        )
        update_evidence_hash(receipt, filename, file_sha(readback))

    write_json(receipt_path, receipt)
    refresh_receipt_binding(root, registry)


def install_unrelated_forms(root, registry):
    evidence = root / EVIDENCE_REL
    filename = "hw-workbench-ux-higher-order-remount-every.forms"
    forms = evidence / filename
    forms.write_text(
        '(setq y (char->string 39))\n(load "unrelated")\n(load "unrelated")\nx\n',
        encoding="utf-8",
    )
    mutate_receipt(root, registry, lambda receipt: update_evidence_hash(
        receipt, filename, file_sha(forms)))


def remove_state_anchor(root, registry):
    evidence = root / EVIDENCE_REL
    filename = "hw-workbench-ux-higher-order-remount-every.txt"
    transcript = evidence / filename
    transcript.write_text(
        transcript.read_text(encoding="utf-8").replace("(m65d-remount)", "(m65d-remounx)"),
        encoding="utf-8",
    )
    mutate_receipt(root, registry, lambda receipt: update_evidence_hash(
        receipt, filename, file_sha(transcript)))


if __name__ == "__main__":
    main()
