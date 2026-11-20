# Speed audit: /feature-plan and /feature-loop

2026-11-13. Measured on vamp `origin/master` and the Claude Code transcripts on this machine.
"W" is a cost-weighted token estimate (input 1, cache write 1.25, cache read 0.1, output 5).
Savings are estimates unless a count is given.

## 1. Baseline

### feature-loop, from 19 `stats.md` files (18 tasks, 418 dispatches)

| Per task | Median | Mean | Max |
|---|---|---|---|
| Dispatches | 22.5 | 23.2 | 42 (156/17) |
| Summed peak context | | 794k | 1,412k |
| Active minutes | | 58 | 152 |
| Wall minutes | | 83 | 472 |
| Validation rounds | 3 | | 4 |

| Agent | Runs | Share of context | Share of active time | Median / max context |
|---|---|---|---|---|
| task-validator | 53 | 20% | 36% | 47k / 109k |
| code-writer | 119 | 15% | 13% | 17k / 52k |
| task-implementer | 48 | 15% | 27% | 42k / 82k |
| validation-reporter | 50 | 13% | 5% | 36k / 57k |
| task-scout | 18 | 12% | 9% | 90k / 175k |
| test-writer | 75 | 10% | 4% | 17k / 41k |
| architect-reviewer | 19 | 6% | 1% | 41k / 61k |
| brief-writer | 18 | 6% | 3% | 45k / 58k |
| code-reviewer | 18 | 4% | 2% | 35k / 51k |

Wall time: 1,036 active minutes against 1,503 wall. The 467 stall minutes sit almost
entirely in two tasks (198/03: 408, 156/17: 59). Stalls are rare and large, not a steady tax.

### The orchestrator, which stats.md does not count

From the transcripts of 12 tasks and one cleanup (171.7M raw tokens, 35.4M W):

| Consumer | Share of W | Note |
|---|---|---|
| Orchestrator (main thread) | 29% | 60 turns a task at about 78k cached context, about 7 turns a dispatch |
| task-implementer | 20% | 24 turns a run |
| task-validator | 17% | |
| task-scout | 9% | |
| code-writer + test-writer | 9% | 95 runs, 32k to 38k W each |
| validation-reporter | 5% | |
| reviewers (both) | 8% | |
| brief-writer | 3% | |

The orchestrator is the largest single consumer and over half the cost of small tasks
(284/01, 09, 10: 53 to 55% of W). Its turns are bookkeeping: across 13 runs, 633 Bash calls
(132 `loop.py commit`, 165 touching `log.md`) and 111 Edits for 111 dispatches.

### What each gate changed (46 tasks: 156, 198, 87, 284)

| Gate | Ran | Changed the code | Passed clean or changed nothing real |
|---|---|---|---|
| Validation round 1 | 46 | 21 blocked. Of the 16 with files, 2 by a product defect | 25 passed; 14 blocked by paperwork, wording, task-file conflicts or harness |
| Validation rounds 2+ | 74 | 2 blocked (one repeat, one harness) | 72 passed. The 41 after a review fix or refactor never blocked |
| Architect round 1 | 42 | 11 (all in 156): 17 refactors, 8 dedupes, 3 latent bugs | 31 approved. 0 of 27 since 156 |
| Architect round 2 | 11 | 0 | 11 of 11 confirmed "landed" |
| Code review | 46 | 11 with a real bug (10 in 156), 19 nits only | 16 clean |

The 28 blocking validation findings on file: 4 product defects, 2 weak tests, 10 "red run
not recorded", 4 literal wording, 4 task-file conflicts (declined), 4 harness (declined).

Of 57 review nits, about 30 only reword comments or docs (estimated from excerpts).

### feature-plan, issue-284 (the one feature with every session on disk)

| Stage (one session each) | Span | Agent work | Waiting on the owner |
|---|---|---|---|
| Spec grill | 320 m | 6 m | 314 m |
| Spec gate + design | 98 m | 5 m | 92 m |
| Drafts + evaluator | 12 m | 12 m | 0 |
| Decision grill | 21 m | 7 m | 15 m |
| PLAN.md to plan PR | 132 m | 132 m | 0 |
| Plan gate check | 3 m | 1 m | 3 m |

- 6 sessions, 21 human round-trips, 5 days 3 hours from first session to the plan PR.
- 72% of in-session time was waiting on the owner. The longest idle was between sessions:
  4 days 17 hours after the evaluator session stopped to hand the decision grill to a new one.
- 5 of the 21 round-trips were re-running `/feature-plan` to push the next stage along.
- The grills already batch: 24 of 28 questions arrived in calls of 2 to 4.
- Tokens: main threads 4.0M W, subagents 9.2M W (cutter 3.6M, readiness 3.5M, drafter 1.8M,
  evaluator 0.4M).

### The paper trail on origin/master

| Feature | Lines (text) | In run files | Left after this branch's cleanup (estimate) |
|---|---|---|---|
| issue-156 | 32,604 | 25,921 | about 5,800 (4,938 are task files) |
| issue-198 | 29,167 | 20,833, plus 6 MB PNG | about 5,000 |
| issue-87 | 6,955 | 4,009 | about 1,400 |
| issue-284 (cleaned once already) | 5,222 | 272 | about 2,800; today 5,222, of which 2,399 are plan intermediates |
| issue-110 | 7,054 | 0 | about 4,400, after the hand removals in section 4 |

Largest classes: PNG 6.0 MB, briefs 1.05 MB, task files 0.99 MB, validations 0.89 MB,
surveys 0.87 MB, evidence 0.68 MB.

## 2. Answers to the questions

**Where does wall time go?** In the loop: agent work. Validation is 41% of active time
(runner 36%, reporter 5%), implementation 44%. Stalls are 31% of wall but concentrated in
two tasks. In the plan: waiting on the owner, and above all the forced stops between stages.

**Which dispatches merge cheaply?** The expensive thing is not a gate but the round it
triggers. A review finding costs a review fix, then a validator and a reporter, and that
re-validation has never blocked (0 of 41). Merging the reporter into the runner would save
about 5% W; removing one whole round saves about 15%. See bets B1 to B4.

**Should depth scale with task size?** Not by gate. Architect and code review together are
8% of W and 3% of time, and style-only and chore-only tasks already skip the architect. Small
tasks (12 anchors or fewer, n=7) had no architect change and no review bug, but the stronger
predictor is the feature: 156 produced all 11 architect changes and 10 of 11 review bugs. What
makes a small task slow is the orchestrator (over half its cost) and the number of rounds.

**Why does the scout reach 112k?** Average peak is 77k. Per scout: about 26k tokens of tool
results, 5.7k of that `00-overview.md`, the task file read whole 2.4 times, 199 greps across
10 scouts. The atlas already stands in for unchanged files. What is left is reading the
overview, the decisions and the stale files, which is the job. No large safe cut here.

**Can the grills batch?** They do. The round-trips come from session boundaries, not from
question count.

**Are two drafts and an evaluator worth it?** Yes on this evidence. The evaluator's
amendments were adopted every time (11, 3 and 5), and for 284 the three agents cost 12 minutes
and about 17% of the plan's subagent tokens. Not changed.

**Can readiness run less?** Rounds 2 and 3 raised 10 new findings across three features, so
they are doing work. Round 1 blocks nearly every task (47, 23 and 7 findings, mostly in
criteria), which points at the cutter's first output, not at the reviewers. Not changed.

**Can the plan run in one or two sessions?** Two, with the change below. One would need the
spec PR gate to go (bet B6).

## 3. Changes, ranked

### Safe: implemented on this branch, one commit each

| # | Change | Saving (estimate) | Quality risk | Evidence |
|---|---|---|---|---|
| S1 | `loop.py row`: one call checks the hand-back header, appends the log row and commits it. Sub-rows and back-filled usage cells removed | 10 to 12% of task W; about 25 fewer orchestrator turns a task | None. The header check is now code, and a refused row writes nothing | Orchestrator 29% of W, 7 turns a dispatch |
| S2 | Every green cycle writes `Red: <command>: <failing line>` in its commit body | A fix round (about 0.75M W, 12 to 15 minutes) on each task it would have blocked: 10 of 36 file-backed tasks carried the finding | None. Adds a record | 10 of 28 blocking findings |
| S3 | `carry` treats whole `//` comment lines as no change, so a comment-only fix skips the final validation | A validator and reporter round (about 0.33M W, 8 minutes) on an estimated 6 to 9 of 46 tasks | Low. Directive comments (`@ts-`, eslint, jest) still validate. A `//` line inside a template literal or JSX text would be misread; marked in code | 0 of 41 re-validations blocked; about 30 of 57 nits are comments |
| S4 | Reporter, both reviewers and the fixing implementer read five sections of handoff-format.md (5.4 KB of 14.7 KB). Scout told to read the task file once | About 1% of W | None. Same rules reach the agent | 54 of 206 agents read the file whole |
| S5 | Cleanup also removes plans/, readiness/, grill/, EVALUATION.md, PLAN.md and plan-pr-body.md, and writes `runs/findings.md`: one line per finding that led to a fix | 2,399 of 5,222 lines on 284 | None for the loop. Removed files stay in history | 284 after cleanup |
| S6 | feature-plan: owner steps and agent steps share a session. It stops only for the spec PR and the plan PR, and the plan PR hands to `/feature-loop` | 6 sessions to 2; 5 re-invocations to 1; no idle between stages | Low to moderate. Reverses the earlier "no grill after routing" rule. The router's window grows by the grill's code reads; grills now send an agent for checks over a few reads | 284 session table |

Together: an estimated 15 to 20% fewer tokens per loop task, more on small tasks, and a plan
that takes two sessions. That is real but short of "much faster". The rest is in the bets.

### Bets: decided on 2026-11-13 (section 6), each still needs a live run to judge

| # | Change | Saving (estimate) | Quality risk | Evidence |
|---|---|---|---|---|
| B1 | Run the design and code reviews beside validation round 1, then one fix for all three files, then one final validation | About 15% of W and 10 minutes on the 30 of 46 tasks with review findings; typical task goes from 3 validation rounds to 2 | When round 1 blocks (21 of 46), its fix is not reviewed. Review-fix code is equally unreviewed today. Reviews of a broken build are wasted (2 of 46 product defects) | 41 re-validations, 0 blocked |
| B2 | One agent per tdd cycle (red then green in one window) for small cycles | 6 to 8% of W; halves implementer turns | The test and the code share a window, so a test can fit the code. The reviewer's "passes by construction" check is the backstop. Gate it by size: cycles on one file | 73% of test-writers and 75% of code-writers finish under 20k |
| B3 | A scripted final recheck (gates, task spec, regression, no agent) after a review fix or refactor; agents only if it fails | About 10% of W. Overlaps B1; pick one | No model reads the evidence or the views on that round. Runs project commands, so it needs live testing | 0 of 41 |
| B4 | Runner writes the validation file itself on rounds 2+ when nothing failed | About 3% of W | Judgment in the runner's full window | 72 of 74 later rounds passed |
| B5 | Count the orchestrator in `stats.md` | None; it makes S1 measurable | None | Issue filed |
| B6 | Drop the spec PR; the owner's confirmation at the end of the spec grill approves it, and the spec lands in the plan PR | 2 sessions to 1; one merge fewer | No diff review of the spec before about 9M W of planning | 284: the next session began 14 minutes after the spec PR opened |
| B7 | Screenshots on a side ref that is never merged (`refs/heads/loop-shots/<feature>`), linked from the PR body, deleted at cleanup | 6 MB of 12 MB | PR pictures die when the ref goes. Changes `shots.py`, `pr-body` and the validator's commit | 57 PNGs |
| B8 | Cleanup deletes completed task files; or runs per task at the next task's start | 2,000 to 5,000 lines a feature | Task files are the only prose record of what each PR was asked for; PROGRESS.md and the PRs remain | Paper trail table |

### Looked at and left alone

- Competing drafts and the evaluator: amendments adopted every time.
- Architect round 1: cheap, and it found 8 duplications and 3 latent bugs on 156.
- Architect round 2: 11 runs in 46 tasks, about 26k each. Not worth a contract change.
- Readiness rounds 2 and 3: they find new problems.
- Scout and brief-writer merge: the brief-writer is 3% of W.

## 4. Cleanup plan for vamp `docs/tasks/` (proposal, nothing done)

Per-feature budget after its cleanup PR: **1,000 committed lines without task files, 3,000
with them**, and no binary files. In flight a task may commit what it needs.

1. **issue-156, issue-198, issue-87: run the loop's cleanup.** One PR per feature into
   `master`, from a branch off `origin/master`:
   `python3 <plugin root>/loop/_lib/loop.py cleanup docs/tasks/<feature>`, then
   `loop.py commit 'docs(<feature>): clean up loop run files'`. It keeps each `log.md`, folds
   `stats.md` totals and fixed findings, and removes the rest, PNGs included. issue-156 has
   only task 17's `stats.md`; the command names the tasks with no total, and
   `run-stats.py issue-156-embed-timeline <NN>` fills them only for runs whose transcripts
   are still on this machine.
2. **Older layouts the command does not match.** Remove by hand in the same PRs:
   top-level `PLAN-A.md`, `PLAN-B.md` (156, 110), `REVIEW.md`, `review.html`,
   `IMPLEMENTATION-SESSION.md` (110), `red-evidence.md`, `reds.md`, `handoff.md`,
   `base-readings.log`.
3. **issue-284:** rerun the cleanup with this branch's `loop.py`; it removes the 2,399 lines
   of plan intermediates the earlier cleanup left.
4. **Task files of merged features** (15,225 lines across five features): an owner decision.
   Deleting them takes the tree from about 20k lines to about 5k. PROGRESS.md, DECISIONS.md,
   the spec in `docs/designs/` and the PRs still say what was built.
5. **History.** Do not rewrite it. The PNG blobs are 6 MB; removing them from history means
   a force-push of `master` and re-cloning every worktree, to save 6 MB.
6. **`dashboard-desktop.png`** in the working tree is untracked and unrelated; left alone.

Expected result: about 80k lines and 12 MB down to about 20k lines and under 1 MB with task
files kept, about 5k lines without.

## 5. Verifying it

I could not run this myself: both commands are user-invoked only, the spec grill needs the
owner, and two PRs need merging.

1. Point the plugin at this branch: `git -C ~/.claude/plugins/marketplaces/eliotshea switch
   loop-speed`, then reload plugins. Not verified: whether Claude Code runs the plugin from
   that checkout or from a cached copy that needs `/plugin` to refresh.
2. Issue: **vamp #283, "Player XP readout ignores the user's streak"**. Small, logic, one
   area, so it exercises tdd cycles, validation and both reviews.
3. `/feature-plan issue-283-xp-readout-streak`, merge the spec PR, run it again, merge the
   plan PR, then `/feature-loop docs/tasks/issue-283-xp-readout-streak`.
4. Compare each task's `stats.md` with the small-task baseline:

| Baseline task | Dispatches | Summed context | Active min | Validation rounds |
|---|---|---|---|---|
| 198/09 | 20 | 548k | 29 | 2 |
| 87/03 | 11 | 464k | 30 | 2 |
| 198/02 | 22 | 615k | 39 | 2 |
| 198/11 (chore) | 14 | 454k | 25 | 3 |

5. Pass marks for the safe set:
   - plan: 2 sessions, 1 re-invocation of `/feature-plan`;
   - no validation finding about an unrecorded red;
   - a comment-only review fix logs `validation carried`, not a new round;
   - `git log --oneline --grep 'loop task .* row'` shows one commit a row and no `?` cells;
   - orchestrator turns per dispatch at 4 or fewer. Until B5 lands, count them from the
     session transcript: distinct assistant `message.id` values divided by `Agent` tool
     calls (baseline about 7).
6. `stats.md` leaves the orchestrator out, so S1, the largest saving, will not show in it.
   Summed agent context should fall by roughly a fix round on tasks S2 or S3 touch and stay
   flat otherwise.

## 6. Decisions, 2026-11-13

Settled with the owner in a grill after the audit, then implemented on this branch.

| Item | Decision |
|---|---|
| B1 | Adopted. Validation round 1, the design review and the code review run at once; one fix answers all three files |
| B2 | Adopted for cycles that change one file of the brief. Larger cycles keep the test-writer |
| B3 | Not adopted. B1 removes the same round |
| B4 | Adopted, narrowly: the runner reports a later round only when nothing failed and no view's result changed |
| B5 | Adopted. `stats.md` has an orchestrator table. Also: `loop.py row` checks Blocking against the findings |
| B6 | Not adopted. The spec PR stays, so planning is two sessions |
| B7 | Adopted. Pictures go to `refs/loop-shots/<feature>`, which is kept until deleted by hand |
| B8 | Task files are deleted at cleanup. Cleanup still runs once, at the end of the feature |
| Vamp | One draft cleanup PR. issue-198's task 15 is abandoned, so it is cleaned as a closed feature. issue-110's drafts and reviews are deleted |

Section 5's pass marks gain three: the build's row is followed by the runner and both
reviews in one message; a one-file cycle shows one code-writer and no test-writer in
`stats.md`; and no PNG appears in `git ls-files docs/tasks`.
