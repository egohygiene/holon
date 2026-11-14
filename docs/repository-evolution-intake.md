# Repository evolution intake — version 1

The [portable manual template](../templates/repository-evolution-intake.md)
helps review an **existing** repository before deciding its next bounded work.
It is not a new generator, maturity policy, audit engine or source of architecture
truth. Copy it into a reviewed issue body or use it as a prompt with inspected
public-safe evidence. No program or provider is needed to run the procedure.

1. Verify scope, instructions, visibility and exact source/work-tracker snapshot.
   Inspect relevant files without executing untrusted repository commands.
2. Freeze observations, keeping file/revision/digest evidence separate from
   interpretations, recommendations and unavailable evidence.
3. Evaluate semantic capabilities against the requested direction. A static
   brochure does not need a database because another profile has one. A test
   filename does not prove tests were executed.
4. Reconcile existing and completed work by owner, surface and acceptance. Keep
   stable `repository:capability` candidate IDs; attach existing issues instead
   of proposing duplicates. Do not infer a gap from a missing filename.
5. Propose finite dependency-aware work only for evidenced applicable gaps.
   Preserve unknowns as questions and conflicts as unresolved decisions.
6. Review the plan with its owner. Intake itself does not apply changes, create
   issues or grant merge/publication authority. Re-run against unchanged inputs
   before making external writes; identical snapshots should retain IDs and
   dispositions. Changed issue state must be re-inspected even without source
   changes.
7. After one bounded reviewed or explicitly simulated change, freeze the new
   snapshot and reassess. Mark resolved capabilities satisfied rather than
   keeping obsolete candidates or silently modifying other issue scopes.

Use Hygiene for policy/applicability, Aether for reusable analysis (including
the draft audit profiles under aether#86 when deliberately selected), Holon for
reviewed materialization and Pace for fleet adoption. This pilot consumes facts
that an orientation card under holon#32 could expose; it does not implement that
card, holon#41 organization bootstrap, or aether#89 project incubation.

## Synthetic manual pilots and limits

[The pilot record](../examples/repository-evolution/pilots.v1.json) contains two
materially different existing-repository fixtures: an offline Python CLI and a
static documentation site. Its `before` and `after` directories freeze actual
source bytes. Ordered relative-path/SHA-256 inventories bind each assessment to
the fixture tree. Synthetic issue inventories avoid live/private data.

The CLI already has passing unit-test source, a known existing recovery issue,
and no requested release channel. The manual intake reuses the existing issue
and proposes one specific missing input-error behavior. The static site already
has a canonical page and no database need, but its HTML lacks a language. An
unknown hosting observation remains unknown rather than becoming a deployment
task. Simulated changes fix only the selected gaps. Unit tests execute the CLI
behavior and inspect the static HTML; they also verify evidence bindings,
candidate IDs/dispositions and unchanged-input rerun equality.

These are **recorded manual assessments** with deterministic consistency checks,
not automated semantic analysis or an AI quality benchmark. Copying an initial
assessment into the rerun record demonstrates the manual no-change procedure;
the checks prove those stored records agree, not that arbitrary model output is
deterministic. Existing work in a real pilot requires a new live inspection.

Friction observed in constructing the pilots: file presence cannot distinguish
working tests from unexecuted tests; unknown infrastructure invites premature
recommendations; different issue titles can describe the same recovery gap;
maturity labels need rationale and must not become certification. Conflicting
goals, inaccessible evidence and missing owner decisions stop recommendation
for that capability; they do not justify fabricated certainty.

## Feasibility of a later `bootstrap evolve`

A later interface could collect allowlisted source inventories and work-tracker
references, validate evidence paths/digests, compare stable candidate IDs and
preview a plan. Those are mechanically testable steps. Applicability, maturity,
semantic duplicate detection, accepted architecture, priority and authorization
remain reviewed judgments. No CLI is implemented or selected here; observe the
manual pilot's usefulness before proposing a separate implementation issue.

Run the offline fixture controls with:

```sh
python3 -m unittest tests.test_repository_evolution_intake -v
```
