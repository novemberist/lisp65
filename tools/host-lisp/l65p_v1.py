#!/usr/bin/env python3
"""Host model for the strict L65P-v1 project and generation-scoped require."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bytecode_p0_compiler as reader  # noqa: E402


FORMAT = "l65-project-v1"
INDEX_INPUT_FORMAT = "lisp65-library-index-input-v1"
INDEX_FORMAT = "lisp65-library-index-v1"
LOCK_FORMAT = "lisp65-project-resolution-lock-v1"
CAPACITY = {
    "bank2_code_bytes": 65536,
    "images": 64,
    "entries": 2048,
    "resolutions": 4096,
    "roots": 1536,
    "c2d_scratch_bytes": 14544,
}
BASELINE = {
    "bank2_code_bytes": 34990,
    "images": 6,
    "entries": 602,
    "resolutions": 2299,
    "roots": 283,
    "c2d_scratch_bytes": 0,
}
DELTA_KEYS = tuple(CAPACITY)
APPEND_STATES = (
    "COLD_VERIFIED",
    "C2J_ACTIVE",
    "TARGET_VERIFIED",
    "C2D_PUBLISHED",
    "EXPORTS_PUBLISHED",
    "LOADED",
)


class L65PError(RuntimeError):
    """A strict manifest, index, preflight or transaction rejection."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise L65PError(message)


def _strict_keys(value: Any, expected: set[str], label: str) -> None:
    require(isinstance(value, dict), f"{label}-not-object")
    require(set(value) == expected, f"{label}-fields")


def _string(value: Any, label: str) -> str:
    require(isinstance(value, reader.StringLit), label)
    return value.value


def _path(value: str) -> str:
    path = PurePosixPath(value)
    require(value and not path.is_absolute(), "absolute-path")
    require(":" not in path.parts[0], "device-prefix")
    require(value == path.as_posix(), "noncanonical-path")
    require(all(part not in ("", ".", "..") for part in path.parts), "parent-path")
    return value


@dataclass(frozen=True)
class Project:
    name: str
    requires: tuple[str, ...]
    sources: tuple[str, ...]
    default_target: str


def parse_project(source: str) -> Project:
    """Parse exactly one data form through the canonical P0 host reader."""
    try:
        form = reader.parse_one(source)
    except reader.CompileError as exc:
        raise L65PError("reader-error") from exc
    require(isinstance(form, list) and form and form[0] == FORMAT, "bad-version")
    rows = form[1:]
    require(all(isinstance(row, list) and len(row) >= 1 for row in rows), "field-shape")
    names = [row[0] for row in rows]
    require(all(isinstance(name, str) for name in names), "field-name")
    require(len(names) == len(set(names)), "duplicate-field")
    require(
        set(names) == {"name", "requires", "sources", "default-target"},
        "unknown-or-missing-field",
    )
    by_name = {row[0]: row[1:] for row in rows}
    require(len(by_name["name"]) == 1, "name-arity")
    name = _string(by_name["name"][0], "name-type")
    require(name != "", "empty-name")
    require(all(isinstance(item, str) for item in by_name["requires"]), "require-type")
    dependencies = tuple(by_name["requires"])
    require(len(dependencies) == len(set(dependencies)), "duplicate-require")
    sources = tuple(_path(_string(item, "source-type")) for item in by_name["sources"])
    require(sources, "empty-sources")
    require(len(sources) == len(set(sources)), "duplicate-source")
    require(len(by_name["default-target"]) == 1, "default-target-arity")
    default_target = _path(_string(by_name["default-target"][0], "default-target-type"))
    require(default_target in sources, "default-target-not-source")
    return Project(name, dependencies, sources, default_target)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_index(spec: dict[str, Any], root: Path) -> dict[str, Any]:
    _strict_keys(spec, {"format", "libraries"}, "index-input")
    require(spec["format"] == INDEX_INPUT_FORMAT, "index-input-version")
    require(isinstance(spec["libraries"], list) and spec["libraries"], "empty-index")
    rows = []
    names: set[str] = set()
    for number, source in enumerate(spec["libraries"]):
        _strict_keys(
            source,
            {"name", "artifact", "requires", "exports", "c2_delta", "measurement"},
            f"library-{number}",
        )
        name = source["name"]
        require(isinstance(name, str) and name and name == name.lower(), "library-name")
        require(name not in names, "duplicate-library")
        names.add(name)
        artifact = PurePosixPath(source["artifact"])
        require(not artifact.is_absolute() and ".." not in artifact.parts, "artifact-path")
        artifact_path = root / artifact
        require(artifact_path.is_file() and not artifact_path.is_symlink(), "artifact-missing")
        dependencies = source["requires"]
        exports = source["exports"]
        require(
            isinstance(dependencies, list)
            and all(isinstance(item, str) and item for item in dependencies)
            and len(dependencies) == len(set(dependencies)),
            "library-requires",
        )
        require(
            isinstance(exports, list)
            and all(isinstance(item, str) and item for item in exports)
            and len(exports) == len(set(exports)),
            "library-exports",
        )
        delta = source["c2_delta"]
        _strict_keys(delta, set(DELTA_KEYS), "c2-delta")
        require(all(isinstance(delta[key], int) and delta[key] >= 0 for key in DELTA_KEYS), "c2-delta-value")
        require(source["measurement"] == "fixture-measured", "unmeasured-delta")
        payload = artifact_path.read_bytes()
        artifact_sha = hashlib.sha256(payload).hexdigest()
        identity_material = json.dumps(
            {
                "format": "l65lib-v1",
                "name": name,
                "artifact_sha256": artifact_sha,
                "requires": dependencies,
                "exports": exports,
                "c2_delta": delta,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        identity_sha = hashlib.sha256(identity_material).hexdigest()
        identity_u32 = int.from_bytes(bytes.fromhex(identity_sha[:8]), "little")
        require(identity_u32 != 0, "zero-library-identity")
        rows.append(
            {
                "name": name,
                "identity_u32": identity_u32,
                "identity_sha256": identity_sha,
                "artifact": artifact.as_posix(),
                "artifact_bytes": len(payload),
                "artifact_crc32": zlib.crc32(payload) & 0xFFFFFFFF,
                "artifact_sha256": artifact_sha,
                "requires": dependencies,
                "exports": exports,
                "c2_delta": delta,
                "execution_source": "bank2",
            }
        )
    rows.sort(key=lambda row: row["name"])
    require(
        all(dependency in names for row in rows for dependency in row["requires"]),
        "unknown-dependency",
    )
    value = {"format": INDEX_FORMAT, "libraries": rows}
    value["index_sha256"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return value


def validate_index(index: dict[str, Any], root: Path) -> None:
    _strict_keys(index, {"format", "libraries", "index_sha256"}, "index")
    require(index["format"] == INDEX_FORMAT, "index-version")
    require(isinstance(index["libraries"], list) and index["libraries"], "empty-index")
    material = {"format": index["format"], "libraries": index["libraries"]}
    require(
        hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == index["index_sha256"],
        "index-sha",
    )
    seen: set[str] = set()
    for number, row in enumerate(index["libraries"]):
        _strict_keys(
            row,
            {
                "name",
                "identity_u32",
                "identity_sha256",
                "artifact",
                "artifact_bytes",
                "artifact_crc32",
                "artifact_sha256",
                "requires",
                "exports",
                "c2_delta",
                "execution_source",
            },
            f"index-row-{number}",
        )
        require(row["name"] not in seen, "duplicate-library")
        seen.add(row["name"])
        artifact = root / row["artifact"]
        require(artifact.is_file() and not artifact.is_symlink(), "artifact-missing")
        payload = artifact.read_bytes()
        require(len(payload) == row["artifact_bytes"], "artifact-bytes")
        require(zlib.crc32(payload) & 0xFFFFFFFF == row["artifact_crc32"], "artifact-crc")
        require(hashlib.sha256(payload).hexdigest() == row["artifact_sha256"], "artifact-sha")
        identity_material = json.dumps(
            {
                "format": "l65lib-v1",
                "name": row["name"],
                "artifact_sha256": row["artifact_sha256"],
                "requires": row["requires"],
                "exports": row["exports"],
                "c2_delta": row["c2_delta"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        identity_sha = hashlib.sha256(identity_material).hexdigest()
        require(identity_sha == row["identity_sha256"], "identity-sha")
        require(
            int.from_bytes(bytes.fromhex(identity_sha[:8]), "little")
            == row["identity_u32"]
            != 0,
            "identity-u32",
        )


def _row(index: dict[str, Any], name: str) -> dict[str, Any]:
    rows = [row for row in index["libraries"] if row["name"] == name]
    require(rows, "unknown-library")
    require(len(rows) == 1, "ambiguous-library")
    return rows[0]


def resolve(
    project: Project,
    index: dict[str, Any],
    generation: int,
) -> dict[str, Any]:
    require(index.get("format") == INDEX_FORMAT, "index-version")
    require(isinstance(generation, int) and 0 < generation <= 0xFFFF, "generation")
    order: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise L65PError("dependency-cycle")
        if name in visited:
            return
        row = _row(index, name)
        require(row["execution_source"] == "bank2", "runtime-attic")
        visiting.add(name)
        for dependency in row["requires"]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        order.append(name)

    for name in project.requires:
        visit(name)

    totals = dict(BASELINE)
    for name in order:
        delta = _row(index, name)["c2_delta"]
        for key in DELTA_KEYS:
            totals[key] += delta[key]
    for key, ceiling in CAPACITY.items():
        require(totals[key] <= ceiling, f"capacity-{key}")

    body = {
        "format": LOCK_FORMAT,
        "project": project.name,
        "generation": generation,
        "index_sha256": index["index_sha256"],
        "libraries": [
            {"name": name, "identity_u32": _row(index, name)["identity_u32"]}
            for name in order
        ],
        "sources": list(project.sources),
        "default_target": project.default_target,
        "post_load_totals": totals,
    }
    body["lock_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return body


class Session:
    """Transaction model: each library append is atomic, the graph is not."""

    def __init__(self, generation: int = 1) -> None:
        require(0 < generation <= 0xFFFF, "generation")
        self.generation = generation
        self.loaded: dict[str, int] = {}
        self.totals = dict(BASELINE)
        self.exports: dict[str, str] = {}
        self.history: list[tuple[str, str]] = []

    def snapshot(self) -> str:
        value = {
            "generation": self.generation,
            "loaded": self.loaded,
            "totals": self.totals,
            "exports": self.exports,
            "history": self.history,
        }
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _append(
        self,
        row: dict[str, Any],
        *,
        fail_at: str | None = None,
    ) -> None:
        before_loaded = dict(self.loaded)
        before_totals = dict(self.totals)
        before_exports = dict(self.exports)
        before_history = list(self.history)
        try:
            for state in APPEND_STATES:
                self.history.append((row["name"], state))
                if state == "C2D_PUBLISHED":
                    for key in DELTA_KEYS:
                        self.totals[key] += row["c2_delta"][key]
                elif state == "EXPORTS_PUBLISHED":
                    for symbol in row["exports"]:
                        self.exports[symbol] = row["name"]
                elif state == "LOADED":
                    self.loaded[row["name"]] = row["identity_u32"]
                if fail_at == state:
                    raise L65PError(f"injected-{state.lower()}")
        except L65PError:
            self.loaded = before_loaded
            self.totals = before_totals
            self.exports = before_exports
            self.history = before_history
            raise

    def require(
        self,
        name: str,
        index: dict[str, Any],
        *,
        fail_library: str | None = None,
        fail_at: str | None = None,
    ) -> str:
        project = Project("require", (name,), ("require.l65",), "require.l65")
        lock = resolve(project, index, self.generation)
        projected = dict(self.totals)
        for item in lock["libraries"]:
            row = _row(index, item["name"])
            loaded_identity = self.loaded.get(row["name"])
            if loaded_identity is not None:
                require(loaded_identity == row["identity_u32"], "loaded-identity-drift")
                continue
            for key in DELTA_KEYS:
                projected[key] += row["c2_delta"][key]
        for key, ceiling in CAPACITY.items():
            require(projected[key] <= ceiling, f"capacity-{key}")
        for item in lock["libraries"]:
            row = _row(index, item["name"])
            if row["name"] in self.loaded:
                continue
            self._append(
                row,
                fail_at=fail_at if row["name"] == fail_library else None,
            )
        return "t"


def validate_lock(lock: dict[str, Any], project: Project, index: dict[str, Any]) -> None:
    expected = resolve(project, index, lock.get("generation", 0))
    require(lock == expected, "resolution-lock-drift")
