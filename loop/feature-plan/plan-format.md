# Plan files

`<plugin root>` in this file is the eliot plugin's directory: the path you read this file
from, up to `/loop/`.

Every file `/feature-plan` writes, who writes it, and the ids they share. It does for planning
what `<plugin root>/loop/feature-loop/handoff-format.md` does for the loop. Every planning agent and
every grilling session reads it. The router reads only headers, so anything a later step needs
goes in a file, never only in a final message. Every Bash call follows that file's "Commands".

`<feature>` is the feature directory's name and the feature branch's name, e.g.
`issue-190-practice-log`. The loop takes its PR titles' issue ref from it, so it starts
`issue-<n>-`.

## Files

| File | Written by | Committed by |
|---|---|---|
| `docs/tasks/<feature>/plan-log.md` | router, and the grilling and design sessions | whoever writes the row |
| `docs/tasks/<feature>/grill/spec.md` | spec grill session | that session |
| `docs/designs/<feature>.md` | spec grill session, revised by the decision grill | that session |
| `docs/tasks/<feature>/grill/design.md` | design session, choosing between mockups | that session |
| `docs/designs/<feature>-mockups/` | design session | that session |
| `docs/designs/<feature>-visual.md` | design session, only if the spec says `UI: yes` | that session |
| `docs/tasks/<feature>/plans/PLAN-A.md`, `PLAN-B.md` | `plan-drafter`, mode draft | router |
| `docs/tasks/<feature>/EVALUATION.md` | `plan-evaluator` | router |
| `docs/tasks/<feature>/grill/decisions.md` | decision grill session | that session |
| `docs/tasks/<feature>/DECISIONS.md` | decision grill session (D, E), `plan-drafter` mode plan (P) | whoever wrote it |
| `docs/tasks/<feature>/PLAN.md` | `plan-drafter`, mode plan | router |
| `docs/tasks/<feature>/00-overview.md` | `task-cutter`, mode overview, fixed in modes reconcile and fix | router |
| `docs/tasks/<feature>/<NN>-<slug>.md` | `task-cutter`, modes cut, reconcile, fix, decisions, feedback | router |
| `docs/tasks/<feature>/readiness/<NN>.md` | `task-readiness-reviewer`, one file per task, rewritten each round that reviews the task | router |
| `docs/tasks/<feature>/feedback-<k>.md` | router, the owner's words on the plan PR, verbatim | router |
| `docs/tasks/<feature>/plan-pr-body.md` | router, by script | router |

**Agents do not commit.** Drafts, cuts and readiness reviews run in parallel in one worktree,
and parallel commits fight over the index lock. Every agent writes its files and returns. The
router checks them and commits them with the step's log row. An agent writes only the files
its mode names and never touches `src/`, `tests/` or any other source.

Two edits cross those lines. The cutter, fixing findings, sets each one's `Status:` and `Fix:`
lines in the readiness file. The decision grill, settling owner findings, sets their
`Owner:` and `Ruling:` lines. Nobody else edits a readiness file but its reviewer.

## Ids

| Id | Lives in | Written by | Means |
|---|---|---|---|
| `T<n>` | the spec's `## Decisions record` table | spec grill, revised by the decision grill and the design session | a settled behaviour |
| `D<n>` | `DECISIONS.md`, `## Owner decisions` | decision grill | a decision the owner made |
| `E<n>` | `EVALUATION.md`, `## Amendments`, and `DECISIONS.md`, `## Adopted amendments` | the evaluator numbers them, the decision grill adopts them | a change the winning draft needs |
| `P<n>` | `DECISIONS.md`, `## Planner decisions` | `plan-drafter` in mode plan | a choice the planner made without asking the owner |
| `Q<n>` | `EVALUATION.md`, `## Questions for the owner` | evaluator | opens the decision grill's frontier |
| `P<r>-<j>` | `readiness/<NN>.md` | readiness reviewer | the j-th finding raised in readiness round r |

An id never changes and is never reused. An adopted amendment keeps the evaluator's number,
so `E3` in a task is `E3` in `EVALUATION.md`, and a gap in `DECISIONS.md`'s E list is an
amendment the owner rejected. A decision that replaces another says `Replaces D4.` and D4
stays in the file with `Replaced by D23.` under its heading.

A task cites ids bare: `T4`, `D2`, `E3`, `P1`. A readiness finding id always has its hyphen,
`P2-3`, so it never reads as a planner decision.

## plan-log.md

    # Plan log: <feature>
    Feature branch: <feature>, draft PR #<n>
    Spec: docs/designs/<feature>.md

    | # | Phase | Agent | Result | File | Context | Min |
    |---|---|---|---|---|---|---|
    | 0 | start | router | feature branch and spec branch created | plan-log.md | | |
    | 1 | spec grill | session | started | grill/spec.md | | |
    | 2 | spec grill | session | done, 9 rounds, 31 T rows, UI yes | docs/designs/<feature>.md | | |
    | 3 | spec | session | spec PR #201 | | | |
    | 4 | gate | router | spec PR #201 merged, plan branch cut | | | |
    | 5 | design | session | started | | | |
    | 6 | design | session | done, 4 mockups, chose 02 | docs/designs/<feature>-visual.md | | |
    | 7 | draft | plan-drafter ×2 | A 14 slices 6 questions, B 11 slices 4 questions | plans/ | Σ 169k | 21 |
    | 7.1 | draft › A | └ plan-drafter | 14 slices, 6 questions | plans/PLAN-A.md | 88k | 21 |
    | 7.2 | draft › B | └ plan-drafter | 11 slices, 4 questions | plans/PLAN-B.md | 81k | 19 |
    | 8 | evaluate | plan-evaluator | winner B, 9 amendments, 7 questions | EVALUATION.md | 104k | 18 |
    | 9 | decision grill | session | started | grill/decisions.md | | |
    | 10 | decision grill | session | done, 14 D, 8 E adopted, 3 T revised | DECISIONS.md | | |
    | 11 | plan | plan-drafter | 11 slices, 5 P | PLAN.md | 96k | 22 |
    | 12 | overview | task-cutter | 15 tasks, 23 files in the map | 00-overview.md | 61k | 9 |
    | 13 | cut | task-cutter ×11 | 15 tasks, 212 anchors | | Σ 603k | 14 |
    | 13.1 | cut › slice 1 | └ task-cutter | 2 tasks | 01-, 02- | 49k | 8 |
    | 13.2 | cut › slice 2 | └ task-cutter | 1 task | 03- | 74k | 14 |
    | … | | | | | | |
    | 13.11 | cut › slice 11 | └ task-cutter | 1 task | 15- | 52k | 9 |
    | 14 | reconcile | task-cutter | 9 fixes in 6 files | | 48k | 6 |
    | 15 | readiness 1 | task-readiness-reviewer ×15 | 4 ready, 11 blocked, 31 blocking, 1 owner | readiness/ | Σ 712k | 12 |
    | 15.1 | readiness 1 › 01 | └ task-readiness-reviewer | BLOCKED, 3 blocking | readiness/01.md | 44k | 7 |
    | … | | | | | | |
    | 15.15 | readiness 1 › 15 | └ task-readiness-reviewer | READY | readiness/15.md | 67k | 12 |
    | 16 | fix 1 | task-cutter | 30 fixed, 1 declined | | 58k | 10 |
    | 17 | readiness 2 | task-readiness-reviewer ×15 | 15 ready | readiness/ | Σ 588k | 8 |
    | 17.1 | readiness 2 › 01 | └ task-readiness-reviewer | READY | readiness/01.md | 38k | 5 |
    | … | | | | | | |
    | 17.15 | readiness 2 › 15 | └ task-readiness-reviewer | READY | readiness/15.md | 52k | 8 |
    | 18 | plan PR | router | plan PR #214 | | | |

Row 0 is on the feature branch, spec rows on the spec branch, and every later row on the plan
branch, which inherits the earlier ones when the spec PR merges.

Each row is its own commit, `docs(<feature>): plan row <#>`, carrying the files that step wrote.
A parallel step (`×N`) gets a row for the step and a sub-row under it for every agent, so
each agent's context is on record. The step row's Context is the sum of its sub-rows, written
`Σ 712k`, and its Min is wall clock from the first dispatch to the last return. A sub-row's `#`
is the step's number and a counter (`15.1`, `15.2`), its Phase is the step's phase and
`› <which one>` (the draft's letter, the slice, the task number), its Agent is the type after
`└ `, and its Result and File are that agent's own. The `…` rows above stand for sub-rows
left out of this example; the log writes every one. The step row and its sub-rows are one
commit. A sub-row never routes: "the last row" always means the last row whose `#` is a whole
number. Context and Min come from each agent's `<usage>` block as in handoff-format.md, `?`
when it has not arrived, and nobody waits for one. A
retry adds its numbers to its agent's row with `+`, and the step row's sum counts both. A row rebuilt on resume
from files already in the tree ends its Result with `, from resume`.

Sessions with the owner log `started` when they begin and `done, ...` when they write their
output. The router's own rows have `router` as Agent and one of these phases: `start`, `gate`,
`readiness: owner questions`, `feedback`, `plan PR`, `plan PR updated`, `stopped`.

## The spec

`docs/designs/<feature>.md`, in the layout of `docs/designs/embed-timeline.md`:

    # Design: <title>

    Settled in a grilling session on <YYYY-MM-DD>
    Issue: #<n>
    Status: IN REVIEW, then APPROVED when the spec PR merges
    UI: yes | no
    Builds on: <earlier features or designs, or none>

    ## Problem
    ## Summary
    ## <one section per area of behaviour>
    ## Out of scope
    ## Known risks for the implementer
    ## Decisions record
    | # | Decision | Answer |
    | T1 | ... | ... |

`UI: yes` is what makes the design phase run (G9). A later revision adds a
`Revised <date> after <what>: <T ids>` line under the header and edits the rows in place,
saying `(revised <date>; was <old answer>)` in the row.

## Grill files

`grill/spec.md` and `grill/decisions.md` are each grill's whole state. A fresh session picks a
grill up from the last `Frontier:` line and nothing else.

    # Grill: <spec | decisions>, <feature>

    ## Round <n>, <YYYY-MM-DD>
    ### Asked
    The reasoning behind the round, then each question as it was put, with its options.
    ### Answers
    The owner's answers, verbatim, one per question.
    ### Checked against the code
    Each answer's claim about the code, the `path:line` that confirms or contradicts it, and
    what changed when one contradicted it.
    Frontier: <the open branches of the design tree, comma-separated, or empty>

A round's `### Asked` is appended before the questions go out, the rest after the answers
come in. A decision grill reopened by readiness starts a section `## Reopened <k>,
<YYYY-MM-DD>` whose first frontier is the owner findings it was sent.

## Drafts, PLAN-<X>.md

    # Plan <A | B>: <feature>
    Leaning: <A: fewest new concepts, build on what exists | B: test seams first>
    Code: <short sha the draft read>
    Slices: <n>
    Questions: <n>

    ## 1. What the code says
    Numbered facts, each with a `path:start-end`. Every later choice comes from one of these.
    ## 2. Architecture
    The model, the module map, the interfaces as signatures, where state lives.
    ## 3. Slices
    ### Slice <n>: <title>
    Each slice: what it delivers, the files it changes, the seams its tests use, what can be
    observed when it is done, and what it depends on. Name which of its outcomes are logic,
    which are style and which are chore, as "Logic and style" defines them: only the logic
    ones get seams. The chore outcomes are the cleanup the slice leaves behind: code it makes
    dead, comments it makes false, a `test.fixme` it makes pass. Name each one, or no task
    will do it.
    ## 4. Known risks
    ## 5. Trade-offs and rejected alternatives
    ## 6. Questions it could not settle
    Numbered. Only what the code cannot answer.

`head -5` of a draft is its header.

## EVALUATION.md

    # Evaluation: <feature>
    Code: <short sha>
    Winner: Plan <A | B>
    Amendments: <n>
    Questions: <n>

    ## Facts settled from the code
    Numbered. Every claim about existing code that the drafts disagree on, that only one
    makes, or that the winner's slices depend on, checked, with its `path:start-end` and which
    drafts had it right.
    ## Verdict
    ## Plan A
    **Strengths** and **Weaknesses**, bulleted.
    ## Plan B
    ## Amendments
    ### E<n>. <title>
    What changes in the winner, and where it comes from (`A §3`, fact 4).
    ## Questions for the owner
    ### Q<n>. <title>
    The question, the positions the drafts took, and the fact it rests on.

The verdict and every Q open the decision grill's first frontier.

## DECISIONS.md

    # Decisions: <feature>

    Settled with the owner in a grilling session on <date>, after `EVALUATION.md`.
    `grill/decisions.md` holds every round. Where this file and the spec disagree, the spec has
    been revised to match.

    ## Owner decisions
    ### D<n>. <the decision as a statement>
    The answer, the reason, the code it rests on as `path:line`, and `Replaces:` the spec rows
    or earlier decisions it changes.
    ## Adopted amendments
    ### E<n>. <title from EVALUATION.md>
    Adopted as written, or adopted with a change the owner made.
    ## Planner decisions
    ### P<n>. <the decision>
    What the planner chose, why, and why it did not need the owner.

## PLAN.md

The winning draft rewritten with every adopted amendment and decision applied, in the draft's
sections. Its header:

    # Plan: <feature>
    From: Plan <X>, with <E ids> and <D ids> applied
    Code: <short sha>
    Slices: <n>

The loop never opens PLAN.md. Every task carries what it needs from it.

## 00-overview.md

The loop's scout reads all of it for every task, so it holds what every task needs and nothing
one task needs.

    # <Issue ref>: <title>

    <What the feature delivers, two or three sentences.>

    Read this file before starting any task. Everything under "Rules that apply to every task"
    and "How every task is validated" is part of every task's acceptance criteria.

    ## Sources, and what not to read
    | Document | What it is | Read it? |
    The spec (only the sections a task cites), the visual spec, DECISIONS.md (only the
    entries a task cites), PLAN.md (No), EVALUATION.md (No).

    ## Order and dependencies
    A fenced block, one line per task in dependency order: `NN   <title>   (<depends on>)`,
    with `[chore]` after the title of a chore-only task. Then which tasks can run together,
    and the reason for each edge. A chore-only task depends on the task whose change leaves
    the cleanup behind.

    ## Plan slices
    | Task | Plan slice |

    ## File map
    | File | Tasks, in order |
    Every source and test file any task changes or creates, and the tasks that touch it in
    dependency order, marking the one that creates it: `12 (creates), 12b, 13`. This table
    decides every anchor's form.

    ## <The model every task shares>, if there is one

    ## Rules that apply to every task
    From CLAUDE.md, the previous feature's overview, and the decisions. Each rule is one a
    validator can check.

    ## How every task is validated
    ### 1. Automated
    Its file-map check, and every task check that expects an exact list of changed files, uses
    the pathspec the reviewers use, which leaves out the files the loop itself commits (run
    logs, the atlas, validation scripts):
    `git diff --name-only <feature branch>...HEAD -- . ':!docs/tasks' ':!tests/validation'`.
    ### 2. Agent browser checks
    ### 3. Owner checks

    ## Task file layout
    Every task file follows `<plugin root>/loop/feature-plan/plan-format.md`, "Task files".

## Task files

`<NN>-<slug>.md`. NN is two digits in dependency order. A task split late takes a letter
(`11b`). These sections, in this order, with these headings. `task-scout`, `brief-writer`,
`task-implementer`, `task-validator` and `validation-reporter` find sections 4, 5, 8 and 9 by
their exact heading, so those four headings cannot change without changing the loop.

    # Task <NN>: <Title>

    Read `00-overview.md` first. Its rules are part of this task's acceptance criteria.

    Plan slice <n>. Depends on <tasks, or none>. Blocks <tasks, or none>.

    Implements <spec sections and T ids>. Decisions <D, E and P ids, or none>.

1. **The header above.** The loop writes `> **Status: complete.** ...` under the H1 later.
2. `## Why`. What the owner gets, and why this task is cut where it is.
3. `## Seams under test`. A table: seam, public interface, test file. These are the agreed
   seams the tdd skill asks for, for the task's logic criteria. A task with no logic criteria
   writes `None: every criterion is style.`, or `chore`, or `style or chore`.
4. `## What must be true when this is done`. Numbered across the whole section, grouped under
   bold labels naming their T or D ids. Each criterion starts with its kind, `[logic]`,
   `[style]` or `[chore]`, as "Logic and style" below defines them:
   `4. [style] The speed thumb is a 16px brand-blue circle ...`. Each is falsifiable by a test, a script, a command, a code read, a
   view or a named owner check, and carries an anchor where it is about code.
5. `## Tests`. Per seam, the behaviours to drive in tracer-bullet order, with test names for
   Playwright specs. Logic criteria only: a style criterion never appears here. A chore
   criterion appears only to name an existing test it turns on, with the temporary break that
   proves the test can fail, if it needs one. A task with no logic criteria writes
   `None: every criterion is style.` (or `chore`) otherwise.
6. `## Where the code is`. A table: what, where. Anchors only, in the forms below.
7. `## Known traps`. What will cost a cycle if missed, each with its anchor.
8. `## Out of scope`. What a reader might expect here that another task or nobody does,
   naming which.
9. `## How to validate`. Automated (the extra greps and specs), agent browser checks, owner
   checks. Each step names the criterion it proves. A task with style criteria adds a
   `Views:` list, one line per screen the validator photographs before and after the change:

       Views:
       - view <name>: <route> at <w>×<h>, <the state and the fixture that seeds it>, <a selector, or page>. Proves <criteria>.
       - view <name>: ... Unchanged.

   `<name>` is kebab-case and becomes the screenshot's file name. Every style criterion is
   proved by at least one view. A view marked `Unchanged.` in place of `Proves` is a screen
   the task must leave exactly as it was, such as the legacy player when a shared atom
   changes. Keep views few: one per screen and size a criterion is about, not one per
   criterion. A chore-only task has no `Views:` and no agent browser checks: its steps are
   greps, commands, code reads and a run of any test it turns on.
10. `## Size`. Exactly these three lines, then any notes:

        Scout: <n> anchors over <n> files.
        Largest cycle: <the behaviour>. Reads <files>.
        Validation: <n> steps, <n> of them browser checks, <n> owner checks.

    A chore-only task has no scout and no tdd cycles. Its `Scout:` line counts the anchors
    the brief-writer checks in the scout's place, and `Largest cycle:` names its biggest
    direct edit. The brief-writer opens at most three files, so anchors in any further file
    reach the code-writer unchecked: keep a chore-only task to three files where the cleanup
    allows it.

A task carries everything it needs from PLAN.md: interfaces as signatures, the reason for a
choice, a risk. "See PLAN.md" is never enough.

## Logic and style

Every criterion is one of three kinds, and the kind decides how the loop builds and checks it.

- **`[logic]`** is anything code decides: state, data, events and handlers, conditions in
  TypeScript or JSX that choose what renders, server calls, computed values, accessible roles
  and names, keyboard behaviour. The loop builds it test-first, and its test runs in CI.
- **`[style]`** is anything only CSS decides: class strings and Tailwind tokens, colour, size,
  spacing, layout, typography, responsive visibility through breakpoint classes, focus rings,
  animation. The loop implements it directly, with no test written for it, and the validator
  checks it by photographing each `Views:` screen before and after the change and measuring it
  in the task's validation script, which CI never runs.

- **`[chore]`** is anything a running page cannot feel: comments and docs, deleting an export
  or a file nothing imports, a rename only comments mention, turning on a test that already
  exists. It is proved by a command (a grep, `tsc`, the build, that one test) or a code read,
  never by a new test or a view. A task whose criteria are all chore takes the loop's short
  road: no scout, no tests, no screenshots, no design review, and no regression run when
  `loop.py inert` shows the diff under `src` is comments and deleted exports. So it lists no
  `Views:`, and no `Unchanged.` view to prove nothing moved: `inert` proves that.

The test is the construct that changes. A class string, a stylesheet or a static attribute
that only affects appearance is style, even when it hides or shows something. A branch, a
hook, a handler or data is logic, even when what it changes is how something looks. A
criterion that needs both is two criteria. A change that leaves every construct behaving as
before is chore, however many lines it deletes; deleting code something still calls is not a
chore, because the build would fail or the behaviour would change. A task that would mix chore
criteria into logic or style work keeps them there only when they touch the same lines: a
cleanup that can land on its own is cut as its own chore task, so it gets the short road.

A style criterion says what the user sees, in numbers where there are any (`a 16px brand-blue
circle centred within 1px on its 48px input`), and never the class string that paints it.
The implementer chooses the classes. A criterion that pins an exact class literal, and a
Jest or `tests/app/` assertion on a class, colour or size, encode styling in tests: the plan
does not ask for either.

## Anchors

A line number is right until the next commit touches its file, and on a planned feature that
commit is usually an earlier task. The overview's file map decides which form each anchor
takes:

| The code is | Cite | Example |
|---|---|---|
| in a file no earlier task in this feature changes | `path:line` or `path:start-end` | `src/hooks/utilities/useEvent.tsx:4-34` |
| in a file an earlier task changes | the path and the symbol, as two adjacent code spans, no line | `src/player/playerController.ts` `setLoop` |
| a part of a symbol, in such a file | the path, the symbol, and the part in words | `waveformHandler.tsx` `handleClick`, the `isNaN` guard |
| a symbol an earlier task creates | the task and the symbol | task 11's `TimelineView.follow` |

A quoted fact about the code ("`toggleLoop` rebuilds from `returnPoint` on the on direction")
always carries a symbol anchor, whatever the file map says, because a later task is the likely
thing to make it false.

"Earlier" means earlier in the dependency order, not just a lower number. A file the task
itself is the first to change keeps line anchors.

The loop's scout checks each form: a line anchor holds when the lines still show what the task
says, a symbol anchor when the symbol exists in that file (it reports the line it found), and a
task anchor when that task's file says `Status: complete`.

## readiness/<NN>.md

One per task, rewritten by each round that reviews the task, with every earlier finding
carried forward under its original id. A round that skips a READY task leaves its file as it is. It opens with six lines, so `head -6` is everything the router routes
on:

    # Readiness <round>: task <NN>
    Commit: <short sha of the plan branch the review read>
    Verdict: <READY | BLOCKED>
    Blocking: <findings open or reopened with Owner: cutter>
    Owner: <findings open or reopened with Owner: human>
    Repeat: <ids this round moved from fixed or accepted to reopened, comma-separated, or none>

A header is valid when all six lines are present in this order, the round matches the round
dispatched, and the verdict is READY exactly when Blocking and Owner are both 0. A READY file
from an earlier round is valid for a task the round did not dispatch.

    ## Findings

    ### P2-3 · where the code is
    Status: open
    Owner: cutter
    Evidence: what the reviewer saw, with the command or `path:line` that shows it.
    Expected: what should be true, with its source: plan-format.md, the spec, DECISIONS.md, the code.
    Repro: `read <path>:<line>`, or the one command that shows it.
    Fix:
    Ruling:

    ## Size
    The task's three size lines, copied, and one line of notes. Never a finding in v1.

    ## Notes
    One line each. What does not block.

The label after the dot is the task section the finding is in (`header`, `why`, `seams under
test`, `criterion 7`, `tests`, `where the code is`, `known traps`, `out of scope`, `validate
step 3`, `size`) or `layout` for a missing or misordered section.

`Owner: human` is for what only the owner can settle: a choice the spec and decisions leave
open, a spec row the code shows is wrong, two decisions that contradict. The router sends
those to the decision grill instead of the cutter.

| Status | Set by | Means | Blocking |
|---|---|---|---|
| `open` | reviewer | New. | yes |
| `fixed` | cutter | `Fix:` says what changed in one sentence. | no, until ruled |
| `declined` | cutter | `Fix:` starts `Declined:` and quotes the spec, DECISIONS.md, PLAN.md or code it conflicts with. | no, until ruled |
| `accepted` | next round | `Ruling:` confirms the fix or agrees with the decline. Closed. | no |
| `reopened` | next round | `Ruling:` says what is still wrong. A decline reopened a second time becomes `Owner: human`. | yes |

A finding whose `Ruling:` starts `Human:` was settled in the decision grill. The next round
rules only on whether the task now carries that decision, and never argues with it.
