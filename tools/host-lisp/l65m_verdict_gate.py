#!/usr/bin/env python3
"""Build and bind the pinned L65M before/after verdict-diff gate."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile


BASELINE_COMMIT = "129e3f5ec32364625a7777da818a8312021811b2"
GRAPH_DEPTH_CONTRACT = 9
SOURCE_FILES = (
    "src/l65m_validate.c",
    "src/l65m_validate.h",
    "src/l65m_overlay_abi.h",
    "src/vm.h",
    "src/obj.h",
    "src/error_codes.h",
)


class GateError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def bundle_sha(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        encoded = name.encode("ascii")
        digest.update(len(encoded).to_bytes(2, "big"))
        digest.update(encoded)
        digest.update(len(files[name]).to_bytes(8, "big"))
        digest.update(files[name])
    return digest.hexdigest()


def load_worktree_sources(repo: Path) -> dict[str, bytes]:
    return {name: (repo / name).read_bytes() for name in SOURCE_FILES}


def load_git_sources(repo: Path, commit: str) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for name in SOURCE_FILES:
        result[name] = subprocess.check_output(
            ["git", "show", f"{commit}:{name}"], cwd=repo
        )
    return result


def normalize_baseline_contract(files: dict[str, bytes]) -> dict[str, bytes]:
    normalized = dict(files)
    name = "src/l65m_validate.h"
    old = b"#define L65M_MAX_GRAPH_DEPTH 32u"
    new = f"#define L65M_MAX_GRAPH_DEPTH {GRAPH_DEPTH_CONTRACT}u".encode("ascii")
    if normalized[name].count(old) != 1:
        raise GateError("baseline-graph-depth-contract-mismatch")
    normalized[name] = normalized[name].replace(old, new)
    return normalized


def materialize(files: dict[str, bytes], root: Path) -> None:
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def validate_binding(
    *,
    resolved_commit: str,
    expected_baseline_source_sha: str,
    actual_baseline_source_sha: str,
    current_source_sha_before: str,
    current_source_sha_after: str,
    baseline_so_sha: str,
    current_so_sha: str,
) -> None:
    if resolved_commit != BASELINE_COMMIT:
        raise GateError("baseline-commit-mismatch")
    if actual_baseline_source_sha != expected_baseline_source_sha:
        raise GateError("baseline-source-sha-mismatch")
    if current_source_sha_after != current_source_sha_before:
        raise GateError("current-source-changed-during-gate")
    if current_source_sha_before == expected_baseline_source_sha:
        raise GateError("baseline-and-current-source-sha-identical")
    if baseline_so_sha == current_so_sha:
        raise GateError("baseline-and-current-so-sha-identical")


def compile_library(
    hostcc: str,
    include_dir: Path,
    wrapper: Path,
    validator: Path,
    output: Path,
) -> list[str]:
    command = shlex.split(hostcc) + [
        "-shared", "-fPIC", "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-DLISP65_VM", "-DLISP65_DISK_LIBS", f"-I{include_dir}",
        str(wrapper), str(validator), "-o", str(output),
    ]
    subprocess.run(command, check=True)
    return command


def selftest() -> int:
    good = dict(
        resolved_commit=BASELINE_COMMIT,
        expected_baseline_source_sha="a" * 64,
        actual_baseline_source_sha="a" * 64,
        current_source_sha_before="b" * 64,
        current_source_sha_after="b" * 64,
        baseline_so_sha="c" * 64,
        current_so_sha="d" * 64,
    )
    validate_binding(**good)
    mutations = {
        "same-so": {"current_so_sha": good["baseline_so_sha"]},
        "commit": {"resolved_commit": "0" * 40},
        "baseline-sha": {"actual_baseline_source_sha": "e" * 64},
        "same-source": {"current_source_sha_before": "a" * 64,
                        "current_source_sha_after": "a" * 64},
        "current-source-drift": {"current_source_sha_after": "e" * 64},
    }
    for label, mutation in mutations.items():
        candidate = good | mutation
        try:
            validate_binding(**candidate)
        except GateError:
            continue
        raise AssertionError(f"{label} mutation survived")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        files = {"src/a.c": b"one", "src/b.h": b"two"}
        materialize(files, root)
        actual = {name: (root / name).read_bytes() for name in files}
        if bundle_sha(files) != bundle_sha(actual):
            raise AssertionError("materialized source bundle changed")
    normalized = normalize_baseline_contract({
        "src/l65m_validate.h": b"#define L65M_MAX_GRAPH_DEPTH 32u\n",
    })
    if normalized["src/l65m_validate.h"] != b"#define L65M_MAX_GRAPH_DEPTH 9u\n":
        raise AssertionError("baseline graph-depth normalization failed")
    print(f"l65m-verdict-gate-selftest: PASS mutations={len(mutations)}")
    return 0


def run_gate(repo: Path, build_dir: Path, report: Path, hostcc: str) -> int:
    resolved_commit = subprocess.check_output(
        ["git", "rev-parse", f"{BASELINE_COMMIT}^{{commit}}"],
        cwd=repo, text=True,
    ).strip()
    baseline_files = load_git_sources(repo, resolved_commit)
    baseline_contract_files = normalize_baseline_contract(baseline_files)
    expected_baseline_sha = bundle_sha(baseline_files)
    expected_baseline_contract_sha = bundle_sha(baseline_contract_files)
    baseline_root = build_dir / "baseline"
    baseline_contract_root = build_dir / "baseline-contract"
    materialize(baseline_files, baseline_root)
    materialize(baseline_contract_files, baseline_contract_root)
    actual_baseline_sha = bundle_sha({
        name: (baseline_root / name).read_bytes() for name in SOURCE_FILES
    })
    actual_baseline_contract_sha = bundle_sha({
        name: (baseline_contract_root / name).read_bytes() for name in SOURCE_FILES
    })
    if actual_baseline_contract_sha != expected_baseline_contract_sha:
        raise GateError("baseline-contract-source-sha-mismatch")
    current_files = load_worktree_sources(repo)
    expected_current_depth = (
        f"#define L65M_MAX_GRAPH_DEPTH {GRAPH_DEPTH_CONTRACT}u".encode("ascii")
    )
    if current_files["src/l65m_validate.h"].count(expected_current_depth) != 1:
        raise GateError("current-graph-depth-contract-mismatch")
    current_sha_before = bundle_sha(current_files)

    wrapper = repo / "scripts" / "l65m-verdict-diff-wrapper.c"
    wrapper_sha_before = sha256_file(wrapper)
    build_dir.mkdir(parents=True, exist_ok=True)
    baseline_so = build_dir / "baseline.so"
    current_so = build_dir / "current.so"
    baseline_command = compile_library(
        hostcc, baseline_contract_root / "src", wrapper,
        baseline_contract_root / "src" / "l65m_validate.c", baseline_so,
    )
    current_command = compile_library(
        hostcc, repo / "src", wrapper, repo / "src" / "l65m_validate.c", current_so,
    )
    current_sha_after = bundle_sha(load_worktree_sources(repo))
    wrapper_sha_after = sha256_file(wrapper)
    if wrapper_sha_after != wrapper_sha_before:
        raise GateError("wrapper-changed-during-gate")
    baseline_so_sha = sha256_file(baseline_so)
    current_so_sha = sha256_file(current_so)
    validate_binding(
        resolved_commit=resolved_commit,
        expected_baseline_source_sha=expected_baseline_sha,
        actual_baseline_source_sha=actual_baseline_sha,
        current_source_sha_before=current_sha_before,
        current_source_sha_after=current_sha_after,
        baseline_so_sha=baseline_so_sha,
        current_so_sha=current_so_sha,
    )

    diff_report = build_dir / "verdict-diff.txt"
    diff_tool = repo / "tools" / "host-lisp" / "l65m_verdict_diff.py"
    completed = subprocess.run(
        [
            sys.executable, str(diff_tool), "--repo", str(repo),
            "--baseline-so", str(baseline_so), "--current-so", str(current_so),
            "--out", str(diff_report),
        ],
        check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if completed.returncode:
        raise GateError(completed.stdout.strip() or "verdict-diff-failed")

    head_revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()
    compiler = subprocess.check_output(
        shlex.split(hostcc) + ["--version"], text=True
    ).splitlines()[0]
    lines = [
        "schema=lisp65-l65m-verdict-gate-v1",
        f"baseline_commit={resolved_commit}",
        f"current_head={head_revision}",
        f"baseline_source_sha256={actual_baseline_sha}",
        f"baseline_contract_source_sha256={actual_baseline_contract_sha}",
        f"graph_depth_contract={GRAPH_DEPTH_CONTRACT}",
        f"current_source_sha256={current_sha_after}",
        f"wrapper_sha256={wrapper_sha_after}",
        f"baseline_so_sha256={baseline_so_sha}",
        f"current_so_sha256={current_so_sha}",
        f"compiler={compiler}",
        "baseline_compile=" + shlex.join(baseline_command),
        "current_compile=" + shlex.join(current_command),
        completed.stdout.strip(),
        "gate=PASS",
        "",
    ]
    report.parent.mkdir(parents=True, exist_ok=True)
    temporary = report.with_suffix(report.suffix + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    temporary.replace(report)
    print(
        "l65m-verdict-gate: PASS "
        f"baseline={resolved_commit[:12]} report={report}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--build-dir", type=Path,
                        default=Path("build/l65m-verdict-diff"))
    parser.add_argument("--report", type=Path,
                        default=Path("build/bytecode/workbench-l65m-verdict-diff.txt"))
    parser.add_argument("--hostcc", default="cc")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    repo = args.repo.resolve()
    build_dir = args.build_dir if args.build_dir.is_absolute() else repo / args.build_dir
    report = args.report if args.report.is_absolute() else repo / args.report
    try:
        return run_gate(repo, build_dir, report, args.hostcc)
    except (GateError, OSError, subprocess.CalledProcessError) as exc:
        print(f"l65m-verdict-gate: FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
