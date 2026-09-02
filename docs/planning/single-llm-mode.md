# Single-LLM interim mode — review-desk handover

**Bound:** 2026-08-28, on owner instruction (subscription reduction; the
architecture reviewer goes offline for a period; Codex works alone).
**Status:** **NOT ACTIVE — stood down 2026-08-28.** The owner's word
("hat sich zunächst erledigt") cancels the planned switch; normal
three-tier mode continues for the coming weeks. This document stays
current and ready: it activates on a future owner's word, and its rule
content (red families, self-check heuristics, halt checklists) remains
useful reference in normal mode too. Section 7's handover state is a
snapshot of 2026-08-28 and is rewritten when a switch is actually
announced.
**Reversal:** the owner's word restores the normal three-tier mode; this
document then becomes historical.

## 1. What changes and what does not

The review desk pauses. Its *rules* do not: everything in
`docs/reference/gate-and-tool-register.md` and the standing house rules
remains binding. This document redistributes only the *decisions* the desk
used to take, and freezes the delegations that assumed a live reviewer.

Unchanged owner property: physical device contacts, the release words
(Ship / Publish), owner-bound product promises (public surface, resident
cost beyond a released price, capacity floors), feature commissions and
descopes.

## 2. Codex's expanded interim authority

Codex may decide alone, with the decision bound in the plan as always:

1. **Known-family reds with a standing rule** — without the
   three-consecutive cap. The named families and their standard
   conversions are listed in section 4. The binding must name the family
   row it applies.
2. **Evidence-layer conversions** (checker rebinds, era seals, index
   regenerations, omission-set extensions by name) with the usual
   mutation proof, when zero product bytes change.
3. **Embedded repricing inside an implementation card**, when all of:
   the overrun is stated loudly with exact arithmetic; the post-spend
   margin stays at or above **20 free symbol slots and 300 free name
   bytes over the 32/384 floor**; zero resident bytes are added. Below
   that threshold: owner decision.
4. **Read-only resumes** over a frozen pair (no WPLTO/link consumption).

## 3. What now goes to the owner (with a prepared template)

Everything the desk used to arbitrate that is not covered above stops at
an owner touchpoint. Codex prepares each stop as a **decision card**: at
most ten lines — what happened, the two or three options, exact costs,
one recommendation, and what is *not* decided by choosing. Specifically:

- any new red class (no standing family row);
- any product-byte change and any WPLTO/product-link budget;
- placement releases and anything touching the composed Bank-2 map;
- pair death declarations and candidate resurrections;
- descope decisions (the anti-rabbit-hole rule still fires automatically,
  but the *report* of it is an owner touchpoint);
- session bindings for device contacts (rows and meanings bound before
  the contact, as always).

Rule of thumb for Codex: **when unsure whether something is a known
family, it is not.** A wrongly-invoked family row costs more than an
owner question.

## 4. The red families and their standard conversions

Each row is precedent with sealed evidence; the conversion is the
standard disposition. All carry the same tail: mutation proof in the
sharp direction (a candidate that truly lacks the property must fall),
and no literal-for-literal swaps.

| Family | Signature | Standard conversion |
|---|---|---|
| Source-text pin | A checker requires a literal spelling; the semantics are unchanged | Prove the property from derived facts (call edges, ElfTruth targets, bank expressions), never a new string |
| Presentation-layer pin | objdump labels / linear text order read as caller identity / control flow | ElfTruth-resolved target addresses plus CFG path proof |
| bound ≠ consumed | A consumer binds an artifact but the toolchain consumed another (header, output root, MAP tuple) | Derive the consumed value from the producing authority; prove path **and** value together; divergence mutation |
| Stale derived index | Metadata/receipt indexes legitimately moved by new artifacts | Regenerate from the real successor artifacts; private names must stay out of public records |
| Era crossing | A historical checker rebuilds or writes through living paths | Bind the sealed evidence in its sealing era, read-only; anti-`derive()` mutation |
| Omission drift | New private objects missing from a declared omission set | Extend the named set by exactly the new names; no wildcards |
| Aggregate-as-capacity | Free bytes reported as a sum while another owner sits inside the interval | Composed owner map, disjoint intervals, largest contiguous hole; already a permanent gate |
| Encodability wall | A derived placement violates a hardware encoding law (MAP $100 steps) | The law enters the derivation at placement time; repricing of the placement, never rounding |

## 5. Review heuristics Codex must apply to itself

These were the desk's actual checks; they become self-checks, and each
card report states that they ran:

1. **Re-derive the arithmetic** from the receipt, not the prose: slot and
   byte deltas, object sums, margins over the floor. A prose total that
   the receipt cannot reproduce is a stopper (the 6-byte three-card-sum
   lesson: the receipt carried the truth, the report was terse).
2. **Receipt ⇄ report consistency**: every number in the report exists in
   a receipt; every receipt stopper is in the report.
3. **Claim-boundary check**: what does this card *not* claim? Host-green
   is not device-green; a scheduling projection is not timing; a probe run
   is not a candidate run.
4. **Neutrality check for instruments and fast paths**: the untouched
   path must be SHA-identical, not "unchanged by inspection".
5. **Full-attribution bar for artifact diffs**: every byte/symbol/
   relocation in a named family, zero unexplained — before qualification,
   not after.
6. **Closing protocol**: report committed before the certifying run; two
   consecutive green `make -k check-source` runs, second one changing
   nothing; clean tree; honest statement when a long runner was skipped.

## 6. Owner checklists for the two halts

**Before Ship** (session green report): the bound session rows are all
green in the report; any deviation from a projection has a named
attribution line; no row was improvised during the contact.

**Before Publish** (release package): asset SHAs read back identically;
the release notes claim exactly what was accepted (check the claim-
boundary list); the capacity line quotes the *measured* D5, not a
projection.

If either list fails, the answer is "not yet", never a workaround.

## 7. State at handover

- v1.7.0: D-session green; Ship and Publish are the owner's next words;
  one open pre-Publish condition: the +8 slot / +93 name-byte D5-vs-
  projection delta needs its one-line attribution.
- Agreed v1.8 opening (349fcc5a): Block 1 `$22` host reproduction,
  Block 2 capture/lossless input; Comfort returns only after both;
  G1 (`room`) awaits owner weighting; the #670 upstream reproducer is
  promised outward work.
- The parked register was audited 2026-08-28 and is complete, including
  the recovered rows (word motion/`C-k`, items 3/4 heritage, `$8040`,
  auto-closing delimiters).

## 7a. Agreed endgame window — 2026-08-28

Owner word: roughly four days of normal mode remain; the aim is to close
v1.8.0 together. Agreed shape: after the v1.7.0 Publish both v1.8 blocks
start immediately in parallel (both host-heavy); on the last day, **what
is accepted ships** — a one-block v1.8.0 is an honest release, an
unfinished block seals into the register as usual. Comfort returns only
if both blocks stand first. The owner announces the switch before it
happens; section 7 is then rewritten to the actual cut point. A switch
in the middle of a release halt is avoided.

## 8. On the reviewer's return

The returning desk reads: this file's decision log (Codex appends every
interim decision card and family invocation below), the pre-plan tail,
and the register diff since `06accfd3`. Interim decisions are not
re-litigated; they are audited like any other sealed era.

---

## Interim decision log

(Codex appends one dated line per decision card and per family-row
invocation: family or owner-touchpoint, one-line outcome, commit.)

- 2026-08-29 — Owner touchpoint `r6-Link frei`: converted the favorable
  Fixed-Bank0 Stored-World checker before spending the link; the zero-build
  preflight now inventories every known candidate-world pin checker before
  each authorized WPLTO. Commit: this preflight seal.
- 2026-08-29 — Phase/output-ownership family: the first six-entry pin
  inventory activated Link-60 too early and stopped before WPLTO; its
  seven-entry successor requests during setup and activates only at the live
  Link-60 selector. No retry budget consumed.
