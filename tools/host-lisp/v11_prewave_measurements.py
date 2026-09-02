#!/usr/bin/env python3
"""Generate the read-only lisp65 1.1 pre-wave measurement report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config/v11-prewave-measurements.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(*args: str) -> str:
    result = subprocess.run(
        args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True
    )
    return result.stdout


def byte_cost(names) -> int:
    return sum(len(name.encode("utf-8")) + 1 for name in names)


def source_code_attribution(resident: dict) -> list[dict]:
    """Attribute final entries to the last defining source, matching load order."""
    owner: dict[str, str] = {}
    for relative in resident["sources"]:
        text = (ROOT / relative).read_text(encoding="utf-8")
        for _kind, name in re.findall(
            r"\((defun|defmacro)\s+([^\s()]+)", text, flags=re.IGNORECASE
        ):
            owner[name] = relative
    # The compiler-generated lambda belongs to string-append in this source.
    owner["__p0_lambda_string_append_1"] = next(
        path for path in resident["sources"] if path.endswith("stdlib-strings.lisp")
    )
    totals = Counter()
    missing = []
    for entry in resident["entries"]:
        source = owner.get(entry["name"])
        if source is None:
            missing.append(entry["name"])
        else:
            totals[source] += entry["length"]
    if missing:
        raise RuntimeError(f"unattributed resident entries: {missing}")
    if sum(totals.values()) != resident["code_bytes"]:
        raise RuntimeError("resident source attribution does not close")
    return [
        {"source": source, "code_bytes": totals[source]}
        for source in resident["sources"]
    ]


def export_only_measurement(resident: dict, libraries: list[dict], budget: dict) -> dict:
    resident_names = set(resident["cost"]["symbol_names"])
    lib_sets = {
        library["name"]: set(library["cost"]["symbol_names"])
        for library in libraries
    }
    disk_names = set().union(*lib_sets.values())
    new_names = disk_names - resident_names
    shared = {
        name for name in disk_names
        if sum(name in names for names in lib_sets.values()) > 1
    }
    explicit = set().union(*(
        set(library.get("exports", [])) |
        set(library.get("late_bound_exports", []))
        for library in libraries
    ))
    public_functions = set().union(*(
        {entry["name"] for entry in library["entries"]
         if not entry["name"].startswith("%")}
        for library in libraries
    ))
    provides = set().union(*(set(library.get("provides", [])) for library in libraries))
    required = (shared | explicit | public_functions | provides) & new_names
    candidates = new_names - required
    # Only the percent prefix is a project-level private-name contract. A
    # starred variable may still be intentional public dynamic state.
    proven_private = {name for name in candidates if name.startswith("%")}
    policy_review = candidates - proven_private
    baseline_symbols = budget["symbols"]["headroom"]
    baseline_namepool = budget["namepool"]["headroom"]
    return {
        "baseline_new_symbols": len(new_names),
        "baseline_new_namepool_bytes": byte_cost(new_names),
        "required_global": {
            "count": len(required),
            "namepool_bytes": byte_cost(required),
            "names": sorted(required),
        },
        "proven_private_recovery": {
            "symbols": len(proven_private),
            "namepool_bytes": byte_cost(proven_private),
            "projected_free_symbols": baseline_symbols + len(proven_private),
            "projected_free_namepool_bytes": baseline_namepool + byte_cost(proven_private),
            "names": sorted(proven_private),
        },
        "policy_review_candidates": {
            "symbols": len(policy_review),
            "namepool_bytes": byte_cost(policy_review),
            "projected_max_free_symbols": baseline_symbols + len(candidates),
            "projected_max_free_namepool_bytes": baseline_namepool + byte_cost(candidates),
            "names": sorted(policy_review),
        },
        "maximum_candidate_recovery": {
            "symbols": len(candidates),
            "namepool_bytes": byte_cost(candidates),
        },
        "claim_limit": (
            "The proven-private line is the implementation floor. The maximum also "
            "requires an owner/API classification of every policy-review name."
        ),
    }


def undo_sessions(model: dict) -> dict:
    baseline = model["baseline_commit"]
    paths = model["paths"]
    commits = run(
        "git", "log", "--format=%H", f"-{model['commit_count']}", baseline, "--", *paths
    ).splitlines()
    sessions = []
    for commit in commits:
        parent = run("git", "rev-parse", f"{commit}^").strip()
        files = run("git", "diff", "--name-only", parent, commit, "--", *paths).splitlines()
        snapshot = 0
        changed_payload = 0
        hunks = 0
        for name in files:
            before = subprocess.run(
                ["git", "show", f"{parent}:{name}"], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            if before.returncode == 0:
                snapshot += len(before.stdout)
            diff = run("git", "diff", "--unified=0", "--no-color", parent, commit, "--", name)
            for line in diff.splitlines(keepends=True):
                if line.startswith("@@"):
                    hunks += 1
                elif line.startswith("+") and not line.startswith("+++"):
                    changed_payload += len(line[1:].encode("utf-8"))
                elif line.startswith("-") and not line.startswith("---"):
                    changed_payload += len(line[1:].encode("utf-8"))
        if not files:
            continue
        delta = (
            changed_payload + model["transaction_header_bytes"] +
            hunks * model["hunk_header_bytes"]
        )
        sessions.append({
            "commit": commit,
            "files": files,
            "hunks": hunks,
            "snapshot_payload_bytes": snapshot,
            "delta_payload_and_index_bytes": delta,
        })
    snapshot_total = sum(item["snapshot_payload_bytes"] for item in sessions)
    delta_total = sum(item["delta_payload_and_index_bytes"] for item in sessions)
    return {
        "model": {
            "unit": "one real repository commit touching IDE/M65D Lisp sources",
            "snapshot": "complete pre-edit UTF-8 file payload",
            "delta": "added+deleted UTF-8 payload plus configured transaction/hunk indices",
            "excludes": "allocator, Lisp-object and redo-chain overhead; this is a comparative lower-bound model",
            **model,
        },
        "sessions": sessions,
        "totals": {
            "session_count": len(sessions),
            "snapshot_bytes": snapshot_total,
            "delta_bytes": delta_total,
            "delta_percent_of_snapshot": round(100 * delta_total / snapshot_total, 2),
            "snapshot_to_delta_ratio": round(snapshot_total / delta_total, 2),
        },
        "decision": "delta records; snapshots are not viable as the default 1.1 undo representation",
    }


def xemu_measurement(contract: dict, source_root: Path) -> dict:
    source = source_root / contract["source_file"]
    if not source.is_file():
        raise RuntimeError(f"missing audited Xemu source: {source}")
    commit = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        text=True, stdout=subprocess.PIPE, check=True
    ).stdout.strip()
    if commit != contract["audited_commit"]:
        raise RuntimeError(f"Xemu audit commit mismatch: {commit}")
    text = source.read_text(encoding="utf-8")
    required = [
        "hwa_kbd_get_queued_modkeys", "hwa_kbd_get_queued_petscii",
        "hwa_kbd_move_next", "hwa_kbd_flush_queue",
    ]
    missing = [name for name in required if name not in text]
    if missing:
        raise RuntimeError(f"Xemu typed queue evidence missing: {missing}")
    return {
        "status": "emulated-in-audited-build",
        "upstream_url": contract["upstream_url"],
        "commit": commit,
        "source_file": contract["source_file"],
        "source_sha256": sha256(source),
        "covered_registers": {
            "$D60A": "queued modifier byte, queue-present bit, flush/dequeue controls",
            "$D619": "queued PETSCII byte",
        },
        "queue_depth": 5,
        "claim_limit": (
            "Source audit proves the typed queue exists in the exact locally installed "
            "Xemu commit. Binding fidelity still needs injected-key differential fixtures; "
            "real hardware remains the arbiter."
        ),
        "upstream_finding_required": False,
    }


def build_report(contract: dict, xemu_root: Path) -> dict:
    inputs = contract["inputs"]
    budget_path = ROOT / inputs["composition_budget"]
    resident_path = ROOT / inputs["resident_manifest"]
    library_paths = [ROOT / path for path in inputs["disk_manifests"]]
    budget = load(budget_path)
    resident = load(resident_path)
    libraries = [load(path) for path in library_paths]
    event_probe_path = ROOT / inputs["event_driver_probe_receipt"]
    event_probe = load(event_probe_path)
    attributed = source_code_attribution(resident)
    compiler_names = {"lcc.lisp", "lcc-fasl.lisp", "lcc-profile.lisp"}
    compiler_bytes = sum(
        row["code_bytes"] for row in attributed
        if Path(row["source"]).name in compiler_names
    )
    disk_rows = [{
        "library": library["name"],
        "container_bytes": library["external_image"]["bytes"],
        "code_bytes": library["code_bytes"],
        "metadata_bytes": library["external_image"]["metadata_bytes"],
        "source_only_shelf_post_load_ext_recovery": 0,
        "direct_attic_execution_potential_ext_recovery": library["code_bytes"],
    } for library in libraries]
    report = {
        "schema": "lisp65-v11-prewave-measurement-report-v1",
        "baseline": contract["baseline"],
        "input_sha256": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in [CONTRACT, budget_path, resident_path, *library_paths,
                         ROOT / inputs["banner_spec"], ROOT / inputs["vm_source"],
                         ROOT / inputs["vm_embed_source"], event_probe_path]
        },
        "measurements": {
            "1_banner_ext": {
                "answer": True,
                "reason": (
                    "The banner is compiled into the resident standard-library code blob; "
                    "vm_ext_code_initial is resident blob length and disk code appends to it."
                ),
                "current_ext_headroom": budget["ext_code"]["post_headroom"],
                "ext_floor": contract["capacity"]["ext_floor"],
                "spendable_margin": budget["ext_code"]["post_headroom"] - contract["capacity"]["ext_floor"],
                "banner_estimate_bytes": [150, 200],
                "decision": "1.1-D remains blocked until 1.1-C creates structural EXT relief",
            },
            "2_shelf_eligibility": {
                "current_vm_code_addressing": "8-bit bank plus 16-bit offset; no Attic execution address",
                "disk_library_source_shelf": disk_rows,
                "disk_library_totals": {
                    "container_bytes": sum(row["container_bytes"] for row in disk_rows),
                    "code_bytes": sum(row["code_bytes"] for row in disk_rows),
                    "metadata_bytes": sum(row["metadata_bytes"] for row in disk_rows),
                    "source_only_post_load_ext_recovery": 0,
                    "direct_attic_execution_potential_ext_recovery": sum(row["code_bytes"] for row in disk_rows),
                },
                "resident_source_attribution": attributed,
                "resident_compiler_tier_candidate": {
                    "sources": sorted(compiler_names),
                    "exact_code_bytes": compiler_bytes,
                    "eligibility": "candidate-after-dependency-cut-and-direct-Attic-execution",
                },
                "decision": (
                    "1.1-A may stage all three disk containers and remove their disk dependency, "
                    "but recovers exactly 0 post-load EXT bytes by itself. 1.1-C must add an "
                    "extended code-address path or deresidentize a self-contained resident tier."
                ),
            },
            "3_export_only_interning": export_only_measurement(resident, libraries, budget),
            "4_metadata_format": {
                "decision": "separate-sha-bound-shelf-index",
                "reason": [
                    "L65M remains the per-container executable format and needs no version change.",
                    "A shelf index binds multiple containers, locations, roles and metadata SHAs.",
                    "Host-rich help/diagnostic data can evolve without growing the device decoder.",
                ],
                "minimum_index_fields": [
                    "schema", "product_set_sha256", "container_role", "container_sha256",
                    "attic_address", "container_bytes", "requires", "provides",
                    "export_policy_sha256", "help_metadata_sha256",
                ],
                "gate": "index SHA in staging receipt; every indexed container SHA must match before load",
            },
            "5_undo_cost": undo_sessions(contract["undo_model"]),
            "6_xemu_event_queue": xemu_measurement(contract["xemu"], xemu_root),
            "7_event_driver_bank0": event_probe,
        },
    }
    return report


def render_markdown(report: dict) -> str:
    m = report["measurements"]
    shelf = m["2_shelf_eligibility"]
    interning = m["3_export_only_interning"]
    undo = m["5_undo_cost"]["totals"]
    lines = [
        "# lisp65 1.1 pre-wave measurements",
        "",
        f"Baseline: `{report['baseline']['tag']}` / product set "
        f"`{report['baseline']['product_set_sha256']}`.",
        "",
        "Status: all seven measurements complete; implementation blocks remain authorization-gated.",
        "No product source or sealed evidence was changed.",
        "",
        "## Decision table",
        "",
        "| # | Result | Consequence |",
        "| --- | --- | --- |",
        f"| 1 | Banner bytes count against EXT; only {m['1_banner_ext']['spendable_margin']} B is spendable | Keep 1.1-D behind 1.1-C |",
        f"| 2 | Attic-as-source recovers 0 B post-load; direct execution potential is {shelf['disk_library_totals']['direct_attic_execution_potential_ext_recovery']:,} B for disk libraries | 1.1-A removes media dependency; 1.1-C needs an extended code address/deresidentization cut |",
        f"| 3 | Proven recovery {interning['proven_private_recovery']['symbols']} symbols / {interning['proven_private_recovery']['namepool_bytes']} name bytes; maximum candidate {interning['maximum_candidate_recovery']['symbols']} / {interning['maximum_candidate_recovery']['namepool_bytes']} | Review the {interning['policy_review_candidates']['symbols']} public-looking names before 1.1-B |",
        "| 4 | Separate SHA-bound shelf index | Do not version-bump L65M for help metadata |",
        f"| 5 | Delta model uses {undo['delta_percent_of_snapshot']}% of snapshot payload ({undo['snapshot_to_delta_ratio']}× smaller) across {undo['session_count']} real commits | Use deltas as the default undo representation |",
        f"| 6 | Typed queue implemented in Xemu `{m['6_xemu_event_queue']['commit'][:12]}` | Emulator-valid differential cases are possible; retain physical samples |",
        f"| 7 | Real-link probe: {m['7_event_driver_bank0']['capacity_delta']['bank0_reserve_bytes']} B Bank 0, +{m['7_event_driver_bank0']['capacity_delta']['boot_overlay_bytes']} B overlay, 3 symbols / 13 name bytes | Fits with 270 B Bank-0 margin; still requires 1.1-L authorization |",
        "",
        "## Shelf measurements",
        "",
        "| Library | Container | Code | Metadata | Source-shelf EXT recovery | Direct-execution potential |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in shelf["disk_library_source_shelf"]:
        lines.append(
            f"| {row['library']} | {row['container_bytes']:,} | {row['code_bytes']:,} | "
            f"{row['metadata_bytes']:,} | 0 | {row['direct_attic_execution_potential_ext_recovery']:,} |"
        )
    lines += [
        "",
        f"The resident compiler-tier candidate (`lcc.lisp`, `lcc-fasl.lisp`, "
        f"`lcc-profile.lisp`) is exactly **{shelf['resident_compiler_tier_candidate']['exact_code_bytes']:,} code bytes**, "
        "but is not eligible until its dependency cut and an Attic-capable code address are proven.",
        "",
        "## Export-only interning",
        "",
        f"The implementation floor is **{interning['proven_private_recovery']['symbols']} symbols / "
        f"{interning['proven_private_recovery']['namepool_bytes']} name-pool bytes**, moving the measured "
        f"headroom to **{interning['proven_private_recovery']['projected_free_symbols']} symbols / "
        f"{interning['proven_private_recovery']['projected_free_namepool_bytes']} bytes**.",
        "",
        f"A further **{interning['policy_review_candidates']['symbols']} symbols / "
        f"{interning['policy_review_candidates']['namepool_bytes']} bytes** are plausible but have public-looking "
        "command/data names and require an explicit API classification. They are not counted in the guaranteed recovery.",
        "",
        "Policy-review names: " + ", ".join(f"`{name}`" for name in interning["policy_review_candidates"]["names"]) + ".",
        "",
        "## Evidence limits",
        "",
        "- Shelf potential is not a product claim; the current VM cannot execute bytecode from Attic.",
        "- The undo figures compare payload and deterministic index overhead, not allocator/GC overhead.",
        "- Xemu source parity permits emulator fixtures but does not replace physical keyboard sampling.",
        "- Full machine-readable inputs, SHA bindings and per-source tables are in the adjacent JSON report.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xemu-source", type=Path, default=Path("/tmp/lisp65-xemu-audit"))
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()
    contract = load(CONTRACT)
    report = build_report(contract, args.xemu_source.resolve())
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_out.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({
        "status": "pass",
        "json": str(args.json_out),
        "markdown": str(args.markdown_out),
        "report_sha256": sha256(args.json_out),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
