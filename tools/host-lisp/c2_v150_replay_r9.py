#!/usr/bin/env python3
"""Run the authorized Link-97 r9 replay with isolated one-shot fixtures."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/host-lisp"))
import c2_v150_candidate_product as CARD  # noqa: E402


BUILD = CARD.BUILD
R8 = BUILD / "post-link-qualification-replay-r8"
R9 = BUILD / "post-link-qualification-replay-r9"
R8_FIRST_RED = CARD.ROOT / (
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.3-v1.5.0-link97-post-link-qualification-replay-r8-first-red.json")
AUTHORIZATION = "5ebf8e93"


def configure_replay() -> None:
    CARD.REPLAY_PREVIOUS_RED = R8
    CARD.REPLAY = R9
    CARD.REPLAY_PROFILE = R9 / "candidate-profile.json"
    CARD.REPLAY_INTERNAL = R9 / "wplto-internal.json"
    CARD.REPLAY_LINKED_GATE = R9 / "single-submit-linked-gates.json"
    CARD.REPLAY_FIRST_RED_RECEIPT = R8_FIRST_RED
    CARD.REPLAY_AUTHORIZATIONS = [
        *[value for value in CARD.REPLAY_AUTHORIZATIONS
          if value != AUTHORIZATION],
        AUTHORIZATION,
    ]


def complete_in_fresh_process() -> None:
    environment = os.environ.copy()
    environment.update(CARD.L95.CAN.canonical_build_environment())
    environment["LISP65_V150_POSTLINK_REPLAY"] = "1"
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "_complete"],
        cwd=ROOT, env=environment, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    CARD.require(result.returncode == 0,
                 "v1.5 r9 fresh-process completion red:\n" + result.stdout)
    paths = CARD.completed_paths()
    (paths["receipts"] / "artifact-completion.log").write_text(
        result.stdout, encoding="utf-8")


def selftest() -> int:
    configure_replay()
    CARD.require(
        R8.is_dir() and (R8 / "candidate-profile.json").is_file()
        and R8_FIRST_RED.is_file()
        and not R9.exists()
        and CARD.AMBIENT.RECEIPT == CARD.AMBIENT.ISOLATED_RECEIPT
        and CARD.AMBIENT.ISOLATED_RECEIPT.is_file()
        and CARD.REPLAY_AUTHORIZATIONS[-1] == AUTHORIZATION,
        "v1.5 r9 replay adapter boundary red")
    CARD.selftest()
    print("v1.5 Link-97 r9 replay adapter selftest: PASS")
    return 0


def replay() -> int:
    configure_replay()
    CARD.complete_in_fresh_process = complete_in_fresh_process
    return CARD.replay()


def complete() -> int:
    configure_replay()
    os.environ.update(CARD.L95.CAN.canonical_build_environment())
    CARD.configure(CARD.REPLAY_PROFILE)
    return CARD.L95.L94.complete_action()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("selftest", "replay", "_complete"))
    return {"selftest": selftest, "replay": replay,
            "_complete": complete}[parser.parse_args().action]()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CARD.CardError, RuntimeError, OSError, ValueError, KeyError,
            subprocess.CalledProcessError) as error:
        print(f"v1.5 Link-97 r9 replay: FIRST RED: {error}")
        raise SystemExit(2)
