#!/usr/bin/env python3
"""Render the complete C2.2 cross-invariant disposition receipt.

This is deliberately a paper gate.  It reads and hashes existing contracts,
sources and receipts, verifies that every canonical matrix row is represented
exactly once, and writes no product, compiler, linker or hardware artifact.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MATRIX = Path("docs/planning/c2.2-cross-invariant-matrix.md")
OUT = Path(
    "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
    "c2.2-cross-invariant-full-matrix-link57-review-receipt.json"
)


def citation(path: str, locator: str, quote: str) -> dict[str, str]:
    return {"path": path, "locator": locator, "quote": quote}


def proven(
    row_id: str,
    crossing: str,
    finding: str,
    citations: list[dict[str, str]],
    boundary: str,
) -> dict[str, Any]:
    return {
        "id": row_id,
        "crossing": crossing,
        "status": "PROVEN",
        "finding": finding,
        "citations": citations,
        "proof_boundary": boundary,
    }


def excluded(
    row_id: str,
    crossing: str,
    finding: str,
    citations: list[dict[str, str]],
    exclusion: str,
) -> dict[str, Any]:
    return {
        "id": row_id,
        "crossing": crossing,
        "status": "EXCLUDED",
        "finding": finding,
        "citations": citations,
        "structural_exclusion": exclusion,
    }


def open_row(
    row_id: str,
    crossing: str,
    finding: str,
    citations: list[dict[str, str]],
    kind: str,
    action: str,
    closure: str,
    schedule: str = "C2.2-before-acceptance",
) -> dict[str, Any]:
    return {
        "id": row_id,
        "crossing": crossing,
        "status": "OPEN",
        "finding": finding,
        "citations": citations,
        "disposition": {
            "kind": kind,
            "proposed_action": action,
            "closure_condition": closure,
            "schedule": schedule,
            "review_status": "proposed-not-yet-reviewed",
        },
    }


ROWS: list[dict[str, Any]] = [
    proven(
        "A1",
        "GC × open overlay transaction",
        (
            "Allocation-triggered collection is permitted while the append "
            "transaction is open.  The canonical root high-water is published "
            "before each later allocation, and the direct append stress fixture "
            "collected after each of two new heap values without losing the "
            "transaction or exposing an uncommitted header."
        ),
        [
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.1-session-extension-probe-receipt.json",
                "/verified/root_publication",
                '"gc_after_each_new_heap_allocation": 2; canonical C2D root_values; writebacks 0',
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-link25-gc-operational-binding-probe-receipt.json",
                "/checkpoint",
                "publish c2_pending_roots before any later allocation",
            ),
            citation(
                "src/c2_product_runtime.c",
                "c2_stream_gc_checkpoint",
                "The seam validates the canonical root range and publishes c2_pending_roots.",
            ),
        ],
        (
            "Direct host stress plus the current product source seam prove root "
            "visibility and transaction survival; this is not a target timing claim."
        ),
    ),
    proven(
        "A2",
        "GC × transient high-edge",
        (
            "Active high-edge roots use the sole C2D root plane.  A transient "
            "transaction raises the scan bound to the complete root capacity; "
            "the collector reads it in 32-byte blocks.  Watermark raise precedes "
            "wipe, so an abort makes handles unreachable before reclamation."
        ),
        [
            citation(
                "config/c2-nested-append-unwind-contract.json",
                "/c2d_v4/gc_roots",
                "committed low root prefix plus root intervals of all active transient records",
            ),
            citation(
                "config/c2-transient-handle-contract.json",
                "/format_decision/removal_rule",
                "watermark is raised first, before records and Attic bytes are wiped",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-transient-handle-contract-probe-receipt.json",
                "/model and /gc_transport",
                "19/19 cases; exact meet accepted; +1 rejected; 96 blockreads per collection",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-latency-attempt2-hardware-presmoke.json",
                "/rows/gc_blockreads_and_frames",
                "2 collections, 192 blockreads, 96 per collection",
            ),
        ],
        (
            "The root-surface crossing and block transport are directly covered; "
            "the 82-frame GC envelope remains informative and limit-free."
        ),
    ),
    excluded(
        "A3",
        "GC × hot code window / refill",
        (
            "The collector marks Lisp objects but does not relocate object cells. "
            "C2-lite code windows, Bank-2 code, Bank-3 native slices and C2D "
            "directory state are raw, fixed external planes outside the heap."
        ),
        [
            citation(
                "docs/planning/c2.1-gc-root-single-source-addendum.md",
                "Non-moving collector rule",
                "The collector is non-moving and performs no writeback.",
            ),
            citation(
                "docs/planning/c2-lite-execution-contract-addendum.md",
                "C2-lite execution planes",
                "Execution uses Chip-RAM planes and removes runtime Attic reads.",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json",
                "/fresh_replacement_gates/no_runtime_attic",
                "hot entry uses Bank 2; native refill uses Bank 3; forbidden edges empty",
            ),
        ],
        (
            "A non-moving mark/sweep collector has no operation that can move or "
            "rewrite raw code/window/C2D storage; those planes are not collected objects."
        ),
    ),
    excluded(
        "A4",
        "GC × C2D publication (steps 5–7)",
        (
            "The publication store is a contracted non-GC-interruptible seam. "
            "All allocating resolution work and root publication precede it; "
            "the header/watermark commit and export-cell stores allocate nothing."
        ),
        [
            citation(
                "config/c2-transient-handle-contract.json",
                "/format_decision/publication_rule",
                "watermark is published last inside the existing non-GC-interruptible publication seam",
            ),
            citation(
                "config/c2-lite-execution-contract.json",
                "/publication",
                "header/watermark after the plan; export cells next; READY last",
            ),
            citation(
                "src/c2_product_runtime.c",
                "c2_append_publish_exports_phase",
                "The committed publication loop validates rows and writes symbol cells without allocation.",
            ),
        ],
        (
            "Natural GC can occur during earlier resolution, but the contracted "
            "publication seam itself contains no allocation or collector entry."
        ),
    ),
    proven(
        "B1",
        "longjmp × open transaction",
        (
            "The central abort landing restores the generation-bound C2J before "
            "longjmp.  Persistent and transient cutpoints at depths one through "
            "four restore exact prior state and retain committed descendants."
        ),
        [
            citation(
                "config/c2-nested-append-unwind-contract.json",
                "/unwind_journal/longjmp_cleanup",
                "central abort landing validates and restores C2J; journal cleared last",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-nested-append-unwind-contract-probe-receipt.json",
                "/cases",
                "48 cases including longjmp-depth-1..4 and every append/unpublish cutpoint",
            ),
            citation(
                "src/interrupt.c",
                "lisp_abort_jump",
                "c2_product_abort_cleanup executes before longjmp",
            ),
        ],
        "The contract model is bound to the implemented single abort landing.",
    ),
    proven(
        "B2",
        "RUN/STOP break × open transaction",
        (
            "RUN/STOP and ordinary errors use the same abort landing and C2J "
            "driver.  The current product gate covers 18 break cutpoints, and "
            "Link 57 hardware observed byte-identical C2D before/after break."
        ),
        [
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json",
                "/fresh_prelink_gates/b2_run_stop",
                "18/18 RUN/STOP cutpoints; one central cleanup before longjmp",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-latency-attempt2-hardware-presmoke.json",
                "/rows/runstop_rollback",
                "C2D before/after SHA identical; directory growth 0; REPL survived",
            ),
        ],
        "Fresh structural product proof and same-identity hardware proof both cover the crossing.",
    ),
    open_row(
        "B3",
        "RUN/STOP break × DMA transport in flight",
        (
            "Current delivery is polling-based and the transport/convergence "
            "closures do not intentionally call lisp_poll, but no contract "
            "states the defer-until-safe rule and no fixture injects RUN/STOP "
            "at the DMA setup/completion cutpoints."
        ),
        [
            citation(
                "src/interrupt.c",
                "lisp_poll",
                "RUN/STOP becomes a longjmp-class abort only when evaluator polling consumes the event.",
            ),
            citation(
                "docs/planning/c2.2-runtime-overlay-dma-completion-contract.md",
                "Bound timeout",
                "The convergence loop restores interrupt state and waits on the owned frame source.",
            ),
            citation(
                "config/c2-kernal-unmap-contract.json",
                "/continuity_invariants/run_stop_abort",
                "a pending abort is latched and delivered before the next evaluator step",
            ),
        ],
        "addendum",
        (
            "Extend the abort-continuity contract to all product DMA seams: no "
            "longjmp/poll inside a submitted transport; a queued break is "
            "delivered exactly once at the first safe evaluator boundary. Add "
            "cutpoint fixtures before submit, during convergence and after proof."
        ),
        "Addendum reviewed and every transport cutpoint passes deferred-delivery plus exact-state fixture.",
    ),
    open_row(
        "B4",
        "longjmp × island installer",
        (
            "The linked installer closure proves no pre-READY Island consumption "
            "and exact zero wipes, but its gate does not explicitly classify "
            "lisp_poll/lisp_abort/longjmp reachability.  A status-returning "
            "failure is proven; absence of non-local exit is not yet a named check."
        ),
        [
            citation(
                "config/c2-preinstall-island-guard-contract.json",
                "/runtime_rule",
                "Island remains non-callable until the installer publishes READY.",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json",
                "/fresh_replacement_gates/preinstallation_island",
                "13-function installer closure; no consuming Island reference before READY",
            ),
        ],
        "fixture",
        (
            "Extend the installer closure gate with forbidden targets "
            "lisp_poll, lisp_abort*, longjmp and C2J abort cleanup; mutate one "
            "edge of each class. Status-returning failures must still wipe and "
            "leave READY false."
        ),
        "Fresh linked closure has zero non-local-exit edges and all four mutations are rejected.",
    ),
    proven(
        "B5",
        "Error inside publish-last seam",
        (
            "C2J is verified before the first mutation and cleared last.  Every "
            "header/export cutpoint restores the prior committed state; corrupt "
            "journal identity/range/CRC fails closed without guessed cleanup."
        ),
        [
            citation(
                "config/c2-nested-append-unwind-contract.json",
                "/unwind_journal",
                "journal read back before first target mutation and cleared last",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-nested-append-unwind-contract-probe-receipt.json",
                "/cases/by_group",
                "12 cutpoints and 3 corrupt-journal negative cases",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json",
                "/fresh_prelink_gates/append_phase_plan_source",
                "publish-before-commit, publish omission/replay and rollback mutations rejected",
            ),
        ],
        "Language errors and cutpoint failures are covered; power loss remains C4.",
    ),
    open_row(
        "C1",
        "Freezer × open transaction",
        (
            "Link 57 proves idle Freezer identity and post-return execution, but "
            "no receipt freezes at a C2J/append cutpoint.  Bank-5 journal and "
            "staged unpublished suffix state have therefore not been exercised "
            "across a real freeze/thaw."
        ),
        [
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-latency-attempt2-hardware-presmoke.json",
                "/rows/freezer_identity",
                "Bank 2 and Bank 3 exact; 8189/8192 E000 stable; post-return arithmetic 9",
            ),
            citation(
                "config/c2-nested-append-unwind-contract.json",
                "/unwind_journal",
                "open transaction authority is the 64-byte Bank-5 C2J",
            ),
        ],
        "fixture",
        (
            "Hardware-freeze at journal-written, staged-before-header, "
            "header-before-exports and abort-unpublish cutpoints; after thaw "
            "either complete normally or abort through C2J and require exact "
            "C2D, export, Bank-2/3 and journal state."
        ),
        "All named open-transaction Freezer cutpoints pass on the acceptance product identity.",
    ),
    proven(
        "C2",
        "Freezer × E000 window (full product)",
        (
            "The permanent same-identity row now exists for Link 57: complete "
            "Bank-2/Bank-3 planes are byte-identical and all nonvolatile E000 "
            "bytes survive; arithmetic resumes after thaw."
        ),
        [
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-latency-attempt2-hardware-presmoke.json",
                "/product_identity and /rows/freezer_identity",
                "Link 57 identity; 8189/8192 E000 bytes preserved; only FF83/FF84/FF86 volatile",
            )
        ],
        "This proof is identity-specific and must be rerun for every later product identity.",
    ),
    open_row(
        "C3",
        "Freezer × handoff state machine",
        (
            "The handoff contract masks IRQ delivery during MAP/vector commit "
            "and publishes vectors after target validity, but it does not state "
            "that hypervisor/Freezer NMI is impossible at every non-steady "
            "cutpoint. SEI alone is not an NMI exclusion proof."
        ),
        [
            citation(
                "config/c2-kernal-unmap-contract.json",
                "/state_machine and /continuity_invariants",
                "interrupt delivery masked only for bounded commit; vector target valid before publication",
            ),
            citation(
                "src/c2_kernal_window.s",
                "c2_kernal_nmi_handler",
                "The owned NMI handler remains a distinct Freezer-return surface.",
            ),
        ],
        "addendum",
        (
            "Specify the authoritative NMI/vector/map owner at every handoff "
            "cutpoint and the only legal recovery path after Freezer entry. Add "
            "a cutpoint state-machine fixture; hardware sample the externally "
            "reachable boundary if the platform permits deterministic injection."
        ),
        "Reviewed handoff/Freezer addendum plus complete cutpoint fixture; no state may resume speculatively.",
    ),
    open_row(
        "C4",
        "Cold reset × partially published C2D",
        (
            "Publish-last, nonzero generation and destination CRCs reject many "
            "torn states, but Link 57 explicitly records that the destructive "
            "restage stale-handle negative was not run.  The exact corruption "
            "and cold-boot repair obligation is not yet one consolidated contract."
        ),
        [
            citation(
                "config/c2-lite-execution-contract.json",
                "/publication",
                "READY is published last after both staged planes and C2D/export publication.",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-latency-attempt2-hardware-presmoke.json",
                "/rows/generation",
                "destructive_restage_stale_handle_negative: not-run",
            ),
            citation(
                "config/c2-nested-append-unwind-contract.json",
                "/unwind_journal/invalid_journal",
                "invalid nonzero journal makes the session plane unusable; cleanup never guesses",
            ),
        ],
        "addendum",
        (
            "Step 2 of the commissioned package: define which C2D header/journal, "
            "Bank-2/3 stage tuple and generation bytes are destroyed; cold boot "
            "must withhold READY, reject every stale handle, rebuild from the "
            "authenticated shelf or emit the specific fail-closed status. Then "
            "run one destructive hardware restage."
        ),
        "Reviewed destructive-restage contract and same-identity hardware negative are green.",
        "C2.2-step-2-before-acceptance-chain",
    ),
    excluded(
        "C5",
        "Attic tenant staleness × session directory",
        (
            "C2-lite has no post-READY source locator and forbids all execution-"
            "time Attic reads.  Newer or stale Session-Attic bytes cannot be "
            "reached by an old directory; only unpublished cold staging may read them."
        ),
        [
            citation(
                "docs/planning/c2-lite-execution-contract-addendum.md",
                "Post-READY source-free rule",
                "The final C2D image has no source locator and no post-READY consumer may interpret it.",
            ),
            citation(
                "config/c2-lite-execution-contract.json",
                "/no_runtime_attic",
                "After READY no VM, GC, RUN/STOP, Freezer-return or resumable error path may read Attic.",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json",
                "/fresh_replacement_gates/no_runtime_attic",
                "724 hot relocations examined; forbidden control/data edges empty",
            ),
        ],
        (
            "The asymmetric content may physically exist, but no published "
            "directory edge can name or consume it in C2-lite."
        ),
    ),
    proven(
        "D1",
        "Owned IRQ × publication window",
        (
            "The linked owned-IRQ closure touches only VIC acknowledgement and "
            "the fixed frame/diagnostic cells.  It has no control or data edge "
            "to C2D, C2J, exports, Bank 2/3 staging or Lisp allocation."
        ),
        [
            citation(
                "config/c2-kernal-unmap-contract.json",
                "/interrupt_and_output/irq_rule",
                "acknowledge only the owned source, preserve context, never call Lisp and never allocate",
            ),
            citation(
                "src/c2_kernal_window.s",
                "c2_kernal_irq_handler -> c2_kernal_frame_tick",
                "Only D019 and FF83/FF84/FF86/FF89 are touched.",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json",
                "/fresh_generic_gates/kernal_freedom_gate",
                "fresh KERNAL-freedom gate passed",
            ),
        ],
        "The complete linked IRQ closure is disjoint from publication state.",
    ),
    proven(
        "D2",
        "Owned IRQ × island install / handoff",
        (
            "The current source-order gate requires ownership and the advancing "
            "owned IRQ before overlay installation, prepare, boot and REPL.  "
            "The IRQ closure is disjoint from Island manufacture, while the "
            "preinstallation gate forbids Island consumption before READY."
        ),
        [
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json",
                "/fresh_generic_gates/pre_ownership_gate",
                "source order: ownership before overlay install, prepare, boot and REPL",
            ),
            citation(
                "config/c2-kernal-unmap-contract.json",
                "/state_machine/transition_rules",
                "owned vectors and frame source verify before product-owned publication",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json",
                "/fresh_replacement_gates/preinstallation_island",
                "no unguarded control edge or consuming Island reference before READY",
            ),
        ],
        "Ordering and both disjoint closures are fresh gates on the Link 57 identity.",
    ),
    open_row(
        "D3",
        "Typed queue overflow × break delivery",
        (
            "Atomic one-head/one-dequeue capture is proven, and handoff continuity "
            "requires a pending abort latch.  Neither evidence defines the "
            "MEGA65 queue-full behavior nor proves that a newly pressed RUN/STOP "
            "cannot be lost behind a full ordinary key queue."
        ),
        [
            citation(
                "config/c2-kernal-unmap-contract.json",
                "/input_and_keymap",
                "code/modifiers captured from one queue head and dequeued exactly once",
            ),
            citation(
                "config/c2-kernal-unmap-contract.json",
                "/continuity_invariants/run_stop_abort",
                "at least one authoritative source; pending abort latched through handoff",
            ),
            citation(
                "src/c2_kernal_window.s",
                "c2_kernal_window_poll",
                "The consumer reads the ordinary D60A/D619 queue head; no separate full-queue break latch is visible.",
            ),
        ],
        "addendum",
        (
            "Choose and contract a gapless RUN/STOP source when the typed queue "
            "is full (independent matrix latch or proved hardware queue rule), "
            "then fill the queue, press RUN/STOP and require exactly one abort "
            "with ordinary tuple ordering preserved."
        ),
        "Queue-full break fixture and source-identity gate pass; no second handwritten key map is introduced.",
    ),
    excluded(
        "E1",
        "Generation change × hot cache",
        (
            "The hot materializer is stateless, every vm_run entry refills its "
            "code window, and restage clears READY/generation before a new "
            "family can publish.  No cache survives across the lifecycle boundary."
        ),
        [
            citation(
                "config/c2-hot-refill-single-source-contract.json",
                "/stage_trust_boundary",
                "hot reads consume only the identity- and generation-bound published plane",
            ),
            citation(
                "docs/planning/c2.2-cross-invariant-matrix.md",
                "Pre-link quick pass E1",
                "stateless materializer, unconditional entry refill, restage invalidates READY/generation",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json",
                "/fresh_replacement_gates/generation",
                "boot binding invalidated before session; nine old handles rejected",
            ),
        ],
        "There is no generation-persistent hot state to invalidate.",
    ),
    excluded(
        "E2",
        "Generation wrap (u16) × fail-closed path",
        (
            "Hot restage is forbidden.  The only product restage boundary is a "
            "cold boot that first makes READY false and resets the resident "
            "generation to zero; no running-session operation increments a u16 "
            "generation toward wrap."
        ),
        [
            citation(
                "config/c2-session-directory-proposal.json",
                "/recommended_contract/reset",
                "Generation wrap requires cold boot. Hot restage remains forbidden.",
            ),
            citation(
                "src/c2_product_runtime.c",
                "c2_product_prepare_boot",
                "c2_ready = 0; c2_runtime.generation = 0 before Boot-family selection",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.1-direct-negative-reset-receipt.json",
                "/reset_restage",
                "generation_wrap_rejected: true",
            ),
        ],
        (
            "No in-product increment exists; cold boot reconstructs from zero. "
            "A future hot-restart feature would reopen this row."
        ),
    ),
    open_row(
        "E3",
        "restart-repl (C2.3) × transient high-edge",
        (
            "restart-repl is not in the C2.2 product surface.  Its future reset "
            "list has not yet been amended to name transient high-edge records, "
            "watermark-first invalidation and both Chip-plane bindings."
        ),
        [
            citation(
                "config/v11-g-green-surface-contract.json",
                "/implementation_status",
                "restart-repl is removed from the 1.1 surface and carried explicitly by C2.3",
            ),
            citation(
                "config/c2-transient-handle-contract.json",
                "/format_decision/restage_rule",
                "inactive watermark precedes generation change",
            ),
        ],
        "addendum",
        (
            "C2.3 restart-repl addendum must explicitly clear high-edge "
            "visibility first, then records/resolutions/roots, both Chip-plane "
            "bindings, exports and generation; add stale-high-handle fixtures."
        ),
        "C2.3 addendum reviewed and its restart fixture green before C2.3 implementation acceptance.",
        "DEFERRED-C2.3-explicit",
    ),
    open_row(
        "E4",
        "restart-repl (C2.3) × open transaction",
        (
            "restart-repl is outside C2.2 and no contract chooses whether an "
            "open C2J transaction is refused or synchronously aborted before restart."
        ),
        [
            citation(
                "config/v11-g-green-surface-contract.json",
                "/implementation_status",
                "restart-repl is a C2.3 surface",
            ),
            citation(
                "config/c2-nested-append-unwind-contract.json",
                "/unwind_journal/longjmp_cleanup",
                "C2J is the sole restoration authority for an open transaction",
            ),
        ],
        "addendum",
        (
            "C2.3 must choose one rule: refuse restart before mutation while "
            "C2J is active, or enter the sole C2J abort landing and restart only "
            "after exact cleanup. Add fixtures at every active journal cutpoint."
        ),
        "C2.3 lifecycle decision reviewed and all restart/open-C2J cutpoints green.",
        "DEFERRED-C2.3-explicit",
    ),
    open_row(
        "E5",
        "Bounded nesting (4) × user-visible error",
        (
            "Depth five is proven to fail before mutation, but current product "
            "plumbing collapses append failure to VM_BADOPCODE/LCC install "
            "failure.  No L65E contract gives nesting exhaustion its own defined, "
            "catchable user error."
        ),
        [
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-nested-append-unwind-contract-probe-receipt.json",
                "/cases/rows/fifth-depth-rejected-before-mutation",
                "bounded depth is four",
            ),
            citation(
                "src/c2_product_runtime.c",
                "c2_product_install",
                "append failure currently sets vm_status = VM_BADOPCODE",
            ),
            citation(
                "config/error-texts.json",
                "lcc-install error row",
                "LISP65_ERR_LCC_INSTALL is generic; no nesting-depth error row exists",
            ),
        ],
        "addendum",
        (
            "Assign depth-five refusal a stable L65E/Lisp error code and detail "
            "policy, preserve byte-identical state, and exercise it through the "
            "real eval/nested-eval user surface."
        ),
        "Defined error renders through the normal surface and a depth-five end-to-end fixture preserves exact state.",
    ),
    proven(
        "F1",
        "C2D growth × Bank-5 ceiling",
        (
            "Every persistent C2D dimension and Session-Attic span is checked "
            "against its high edge before journal publication.  Capacity "
            "mutations for images, entries, resolutions, roots and Attic are "
            "rejected before target mutation."
        ),
        [
            citation(
                "config/c2-session-extension-contract.json",
                "/append_protocol",
                "all C2D dimensions and Session-Attic capacity are checked before mutation",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-nested-append-unwind-contract-probe-receipt.json",
                "/cases/rows group=capacity",
                "image/entry/resolution/root/Attic front collisions all rejected before journal publication",
            ),
            citation(
                "src/c2_product_runtime.c",
                "c2_append_reserve_persistent_bounds_phase",
                "new counts are compared with high fronts before journal or stage writes",
            ),
        ],
        "The refusal is fail-closed before mutation; user wording is separately covered by F3/E5 where applicable.",
    ),
    proven(
        "F2",
        "Transient edge growth × collision with persistent edge",
        (
            "The low and high fronts share one watermark model.  Exact meet is "
            "legal, plus one is refused before journal/target mutation, and a "
            "full persistent edge rejects the first transient record."
        ),
        [
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-transient-handle-contract-probe-receipt.json",
                "/model",
                "f2-exact-meet, f2-plus-one and f2-full-persistent all passed",
            ),
            citation(
                "config/c2-transient-handle-contract.json",
                "/handle_domains/collision_rule",
                "collision is rejected at reservation before journal or target mutation",
            ),
            citation(
                "tests/bytecode/dialect-v2/evidence/architecture-blocks/"
                "c2.2-product-link57-keymap-nullary-fast-path2-structural-receipt.json",
                "/fresh_prelink_gates/transient_execution_lookup_source/model",
                "handle 4095 resolves at physical entry 2047 and root ordinal 1535",
            ),
        ],
        "Both arithmetic boundary directions and the current linked high-edge consumer are covered.",
    ),
    open_row(
        "F3",
        "Name pool / symbol growth × session appends",
        (
            "The symbol allocator checks both MAX_SYM and NAMEPOOL and emits the "
            "defined TOO_MANY_SYMBOLS error before copying.  No current fixture "
            "exhausts each resource independently while an append journal is "
            "open and proves exact C2D/export rollback."
        ),
        [
            citation(
                "src/symbol.c",
                "new_symbol",
                "MAX_SYM and NAMEPOOL are checked before sympool_write; failure is too many symbols",
            ),
            citation(
                "config/error-texts.json",
                "too-many-symbols row",
                "LISP65_ERR_TOO_MANY_SYMBOLS is a user-facing OOM-domain error",
            ),
            citation(
                "src/c2_product_runtime.c",
                "c2_append_publish_plan_resolve_phase",
                "Session publication interns export names while the append state and journal are active.",
            ),
        ],
        "fixture",
        (
            "Independently saturate symbol slots and name-pool bytes at the "
            "publish-name cutpoint for persistent and transient appends. Require "
            "TOO_MANY_SYMBOLS plus byte-identical C2D, C2J and export cells."
        ),
        "Four append-seam exhaustion cases pass and distinguish both physical capacities in the receipt.",
    ),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def binding(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    if not path.is_file():
        raise SystemExit(f"missing cited authority: {relative}")
    return {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def canonical_ids() -> list[str]:
    text = (ROOT / MATRIX).read_text(encoding="utf-8")
    canonical = text.split("## The matrix", 1)[1].split("## Deliverable", 1)[0]
    return re.findall(r"^\| ([A-F][0-9]+) \|", canonical, flags=re.MULTILINE)


def validate() -> None:
    ids = [row["id"] for row in ROWS]
    expected = canonical_ids()
    if len(expected) != 25:
        raise SystemExit(
            f"canonical matrix row count changed: expected 25, observed {len(expected)}"
        )
    if ids != expected:
        raise SystemExit(f"row identity/order mismatch: {ids!r} != {expected!r}")
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate matrix row")
    for row in ROWS:
        if row["status"] not in {"PROVEN", "EXCLUDED", "OPEN"}:
            raise SystemExit(f"{row['id']}: invalid status")
        if not row["citations"]:
            raise SystemExit(f"{row['id']}: missing citation")
        if row["status"] == "OPEN":
            disposition = row.get("disposition")
            if not disposition or disposition["kind"] not in {
                "fixture", "addendum", "benign"
            }:
                raise SystemExit(f"{row['id']}: OPEN without valid disposition")
            if not disposition["proposed_action"] or not disposition["closure_condition"]:
                raise SystemExit(f"{row['id']}: incomplete OPEN disposition")
    for row_id in ("E3", "E4"):
        row = next(item for item in ROWS if item["id"] == row_id)
        if row["disposition"]["schedule"] != "DEFERRED-C2.3-explicit":
            raise SystemExit(f"{row_id}: C2.3 deferral is not explicit")


def render() -> dict[str, Any]:
    validate()
    cited_paths = sorted(
        {str(MATRIX), str(Path(__file__).resolve().relative_to(ROOT))}
        | {
            item["path"]
            for row in ROWS
            for item in row["citations"]
        }
    )
    counts = {
        status: sum(row["status"] == status for row in ROWS)
        for status in ("PROVEN", "EXCLUDED", "OPEN")
    }
    open_ids = [row["id"] for row in ROWS if row["status"] == "OPEN"]
    return {
        "format": "lisp65-c2.2-cross-invariant-full-matrix-receipt-v1",
        "version": 1,
        "recorded_on": "2026-07-23",
        "status": "complete-awaiting-line-by-line-class-c-review",
        "scope": {
            "kind": "paper-gate-only",
            "product_bytes_changed": 0,
            "compiler_runs": 0,
            "linker_runs": 0,
            "hardware_runs": 0,
            "acceptance_chain_started": False,
            "restage_step_started": False,
        },
        "canonical_inventory": {
            "request_said_rows": 24,
            "canonical_rows_observed": 25,
            "resolution": (
                "The matrix method forbids removing rows, so all 25 canonical "
                "rows A1..F3 are dispositioned. The request-count mismatch is "
                "recorded, not silently normalized."
            ),
            "ordered_ids": [row["id"] for row in ROWS],
        },
        "method": {
            "PROVEN": "receipt or passed gate directly covers the crossing",
            "EXCLUDED": "contract makes the crossing structurally impossible",
            "OPEN": "neither; one proposed fixture/addendum/benign disposition is mandatory",
            "honesty_rule": "prefer OPEN over stretched EXCLUDED",
        },
        "summary": {
            **counts,
            "total": len(ROWS),
            "open_ids": open_ids,
            "explicit_c2_3_deferrals": ["E3", "E4"],
            "step2_destructive_restage_row": "C4",
        },
        "rows": ROWS,
        "open_disposition_index": [
            {
                "id": row["id"],
                "kind": row["disposition"]["kind"],
                "schedule": row["disposition"]["schedule"],
                "closure_condition": row["disposition"]["closure_condition"],
            }
            for row in ROWS
            if row["status"] == "OPEN"
        ],
        "bindings": {path: binding(path) for path in cited_paths},
        "gate": {
            "matrix_review": "BLOCKED-until-owner-review-disposes-each-OPEN-row",
            "destructive_restage": "BLOCKED-until-matrix-review",
            "R4_R5_R6_G5_G6": (
                "BLOCKED-until-matrix-review-and-destructive-restage-green"
            ),
            "no_inherited_green": True,
        },
        "claim_limit": (
            "This receipt is a cited disposition of the complete canonical "
            "cross-invariant matrix. It changes no product byte and claims no "
            "new fixture, hardware, restage, promotion or acceptance result. "
            "OPEN dispositions are proposals for line-by-line Class-C review, "
            "not authorization to implement them."
        ),
        "value_string": (
            f"c2.2-cross-matrix=25/25 proven={counts['PROVEN']} "
            f"excluded={counts['EXCLUDED']} open={counts['OPEN']} "
            "c2.3-deferred=E3,E4 restage=C4-not-started "
            "acceptance=blocked-review-required"
        ),
    }


def main() -> None:
    value = render()
    target = ROOT / OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(target.relative_to(ROOT))
    print(value["value_string"])


if __name__ == "__main__":
    main()
