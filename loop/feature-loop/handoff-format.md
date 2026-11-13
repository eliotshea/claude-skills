# Handoff files

`<plugin root>` in this file is the eliot plugin's directory: the path you read this file
from, up to `/loop/`.

Every agent in the feature loop reads its inputs from files in the task's run directory,
`docs/tasks/<feature>/runs/<NN>/`, and writes its output there. The orchestrator reads only
the header of each file. Anything a later agent needs goes in the file, never only in your
final message.

## Your final message, once

Your final message reaches your caller once. If your tools include a hand-back tool, its first
call is your report and every later call is refused, so never call it with a status, a
`(waiting)` or anything but the final message your definition gives. An agent you start runs
in the background and wakes you with its report when it finishes: to wait for one, end your
turn without handing back. Hand back only when the last agent you started has reported and
your own work is done.

## Commands

Run one plain command per Bash call, with literal arguments. Claude Code refuses a command
that names git in a form it cannot verify stays in the worktree: a `;` chain, a loop, a
`$(…)`, a variable, a heredoc beside another command. Each refusal costs a retry, so never
write a compound command of your own. Shell variables also do not survive from one call to the
next. What would need more goes through `python3 <plugin root>/loop/_lib/loop.py` (`loop.py` for
short): `commit` for every commit (it adds the stored commit trailer), `section` to read a
file's `## ` sections, `findings` for ids and counts, and `run` to send long output to a log
and print a summary. Never put `$` followed by a digit in a SKILL.md: loading a skill replaces
it with the skill's arguments, which is why no shell function lives in one.

This section, and the `<usage>` rule under "log.md", hold for `/feature-plan` and its agents
too.

## Files

| File | Written and committed by | Numbering |
|---|---|---|
| `log.md` | orchestrator | |
| `survey.md` | task-scout; a chore-only task has none | |
| `docs/tasks/atlas.md`, outside the run dir | task-scout, through `atlas.py merge`, in the survey's commit; pruned through `atlas.py prune` by the implementer and the cleanup | one, shared by every feature |
| `brief.md` | brief-writer, from `survey.md` | |
| `evidence-<n>.md` | task-validator, in the same commit as its scripts | n is its validation's number |
| `validation-<n>.md` | validation-reporter, from `evidence-<n>.md` | n counts validations across the whole task: 1, 2, 3, … whichever stage each belongs to |
| `architecture-<n>.md` | architect-reviewer | n is the architecture round |
| `review-1.md` | code-reviewer | code review runs once |
| `feedback-<k>.md` | orchestrator, from the human's pull request feedback | k counts feedback rounds |
| `pr-body.md` | orchestrator | |
| `stats.md` | orchestrator, from `run-stats.py`, with the pull request or a `stopped` row | |

When every task is merged, the orchestrator's cleanup pull request removes all of these but
each task's `log.md`, and folds each `stats.md`'s last line into one `runs/stats.md`. So
nothing a later task needs may live only in a run directory.

The implementer writes no file of its own. It edits the `Status:` and `Fix:` lines of the
findings it was handed, in one commit after the fixes. The test-writer and code-writer it
starts read the brief and the code for one tdd cycle each, and write only code and tests. The orchestrator edits a finding's `Status:` and `Ruling:` lines, and
the header, only to record a human's ruling.

`brief.md` is not a report and has no six-line header. Its `PR title:` line shows it is
complete, and its `Counts:` line is what the orchestrator logs for it.

A brief is two agents. The scout reads and records, the writer decides the contract: the PR
title, the allowed diff surface, the seams, the validation methods and the traps. The writer
opens at most three of the files the survey names, and past three the survey is too thin to
brief from: the section is written from what there is and the gap becomes a trap. It sees the
overview rules and the decisions in force only where the survey quotes them, so a rule the
scout leaves out is a rule the task does not have.

A chore-only task's brief is one agent. There is no survey: the writer works from the task
file and the overview, records the baseline itself, and writes the same sections, most of
them short.

The survey is an index: ranges and a line on what sits at each, quoting only signatures, the
lines the change rewrites, the test shapes and the rules. Neither agent types a quote. A line
`<<quote <path>:<start>-<end>>>` is filled from the base commit by
`<plugin root>/loop/feature-loop/fill-quotes.py`, at most 15 lines each, before the file is
committed. The filled survey is at most 40 KB, and a scout that cannot fit Anchors, Rules in
force and Baseline under it says `over budget` in its Size line.

The atlas is the loop's memory of the code, shared by every feature, and the only file
outside a run directory that the loop keeps. An entry for a deleted or renamed file is removed
by the implementer whose commit removed it, and the cleanup removes every entry gone or stale
at the end of a feature, so the atlas holds only what is still true. Each scout reads the entries for the files its task names through
`<plugin root>/loop/feature-loop/atlas.py show`, and an entry whose file is unchanged since it was
written stands in for opening the file. It then writes back the entries it had to rebuild.
Entries record what is in a file, never what a task wants from it. They merge into the feature
branch with the task's pull request, so the next task's scout starts from them.

`survey.md` opens with three lines, so `head -3` tells the orchestrator it is complete:

    # Survey: task <NN>
    Base: <branch> @ <short sha>
    Anchors: <n> wrong of <n>

Its sections are Anchors, Code, Rules in force, Test neighbourhood, Validation material,
Baseline and Observations, as `task-scout` defines them.

A validation is two agents. The runner checks and records, the reporter judges. The runner
never writes a verdict, a finding or an id, and the reporter repairs no script and reruns
nothing wider than a single item, at most twice in a round. The reporter gets a window holding the evidence, the criteria and the previous round's
findings, because it makes the round's judgment and the runner reaches the end of a long
round carrying every log tail it read.

`evidence-<n>.md` opens with three lines, so `head -3` tells the orchestrator it is complete:

    # Evidence <n>: task <NN>
    Commit: <last code commit>
    Items: <number of item rows>

Its sections are Items, Gates, Baseline, Diff, Repro reruns, Code reads and Notes, as
`task-validator` defines them. It has no `## For the PR` section: nothing in it reaches the
pull request except through `validation-<n>.md`.

## The report header

Every validation, architecture, review and feedback file opens with exactly these six lines,
so `head -6` gives the orchestrator everything it routes on:

    # <Validation | Architecture | Review | Feedback> <n>: task <NN>
    Commit: <last code commit: git log -1 --format=%h -- . ':!docs/tasks' ':!tests/validation'>
    Verdict: <PASS | BLOCKED> for validation, <APPROVED | CHANGES REQUESTED> for architecture, <CLEAN | FINDINGS> for review and feedback
    Blocking: <number of findings whose Status is open or reopened>
    Disputed: <number of findings whose Status is disputed>
    Repeat: <ids this round moved from fixed or accepted to reopened, comma-separated, or none>

A header is valid when all six lines are present in this order with these keys, and the
verdict is PASS, APPROVED or CLEAN exactly when Blocking is 0.

## A finding

    ### V2-3 · criterion 7
    Status: open
    Evidence: what you observed, with the command or script that shows it and at most ten lines of its output.
    Expected: what should be true, quoted, with its source: a task file criterion or step, DECISIONS.md, CLAUDE.md, the brief's baseline.
    Repro: the one command that reproduces it, or `read <path>:<line>`.
    Fix:
    Ruling:

The id prefix names the stage that raised the finding: `V` validation, `A` architecture, `R`
review, `U` human feedback. The number after it is that file's n or k. `V2-3` is the third
finding raised in `validation-2.md`. An id never changes once written. A later validation or
architecture file copies every earlier finding of its kind forward, under the original id and
with its current status, so the latest file holds the whole history.

The label after the dot names what the finding is measured against: `criterion N`, `step N`,
`gate`, `regression`, `testability`, `tooling`, `design`, `bug`, `nit` or `feedback`.
Non-blocking remarks go in a file's Notes or Observations section, never as findings.

`tooling` is a validation finding whose cause is the validator's own script or the loop's
tools, not the app: a mask that moves with its content, a base worktree that would not serve,
a script asserting the wrong thing. Its Expected says what the tool must do, and its Repro
reruns it. Nobody declines it: the next validation's runner repairs the tool and reruns the
Repro, and its reporter rules on it like any open finding.

## Recorded runs

When a task file asks for a run to be recorded, such as a test going red under a temporary
break before it is reverted, the agent that ran it writes both runs, command and outcome, in
the body of the commit that lands the test (`loop.py commit '<subject>' <paths> --body
'<text>'`). That is where the validator looks: `git log --format=%B <base commit>..HEAD`. When the test
is already committed and the run changes nothing, record it in an empty commit with the same
command and `--allow-empty`, never a plain `git commit`.

## Status

| Status | Set by | Means | Blocking |
|---|---|---|---|
| `open` | whoever raised it | New. | yes |
| `fixed` | implementer | `Fix:` holds a short sha and one sentence. | no, until ruled |
| `declined` | implementer | `Fix:` starts `Declined:` and quotes the task file, DECISIONS.md, overview rule, Out of scope text or observed app behaviour the finding conflicts with. | no, until ruled |
| `accepted` | the ruling round | `Ruling:` confirms the fix, agrees with the decline, or records that this round's evidence no longer shows the problem. Closed. | no |
| `reopened` | the ruling round | `Ruling:` says what is still wrong. | yes |
| `disputed` | the ruling round | Implementer and checker still disagree after their last exchange. Goes to the human in the pull request. | no |

A finding whose `Ruling:` starts `Human:` was settled by the human. No agent changes its
status again. If its problem shows up again, the checker says so under Observations.

Who rules, by prefix:

- **`V`**: the next validation's reporter. A fix is `accepted` or `reopened`. A decline is
  `accepted` or `reopened`, and a finding declined again after being reopened becomes
  `disputed`. A finding still `open` or `reopened` is judged on this round's evidence like a
  new one, and stays as it is unless that evidence clears it. A `disputed` finding stays
  disputed.
- **`A`**: the next architecture round. A fix is `accepted` or `reopened`. A decline is
  `accepted` or `disputed`. A finding the refactor left unaddressed is `reopened`.
- **`R` and `U`**: nobody. `fixed` stands, since the final validation after it reruns the
  whole contract without ruling on these ids. `declined` goes to the human in the pull request.

## For the PR

Every file except `log.md`, `survey.md`, `evidence-<n>.md`, `pr-body.md` and `stats.md` ends with a
`## For the PR` section, written for
the human reviewing the pull request. The orchestrator stitches these sections into the pull
request body with a shell script, without reading them, so each must stand on its own.

## log.md

    # Run log: task <NN>
    Task branch: <branch>
    Base commit: <short sha of the feature branch the task branch was cut from>

    | # | Stage | Agent | Code commit | Result | File | Context | Tools | Min |
    |---|---|---|---|---|---|---|---|---|
    | 0 | start | orchestrator | 57a85c5 | task branch created | log.md | | | |
    | 1 | survey | task-scout | 57a85c5 | 1 wrong of 14 anchors, 6 observations, 22 KB, atlas 9 fresh 2 stale 3 new | survey.md | 62k | 19 | 4 |
    | 2 | brief | brief-writer | 57a85c5 | 1 wrong anchor, 3 traps, 2 extra reads | brief.md | 37k | 12 | 2 |
    | 3 | build | task-implementer | 9c1e2f0 | 3 commits, 3 red, 3 green, 0 direct | | 31k | 24 | 14 |
    | 3.1 | build › cycle 1 red | └ test-writer | | | | 22k | 8 | 1 |
    | 3.2 | build › cycle 1 green | └ code-writer | | | | 38k | 14 | 3 |
    | 3.3 | build › cycle 2 red | └ test-writer | | | | 19k | 6 | 1 |
    | 3.4 | build › cycle 2 green | └ code-writer | | | | 27k | 11 | 2 |
    | 3.5 | build › cycle 3 red | └ test-writer | | | | 20k | 7 | 1 |
    | 3.6 | build › cycle 3 green | └ code-writer | | | | 24k | 9 | 2 |
    | 4 | validation 1 run | task-validator | 9c1e2f0 | 19 passed, 2 failed, 1 manual | evidence-1.md | 96k | 68 | 11 |
    | 5 | validation 1 report | validation-reporter | 9c1e2f0 | BLOCKED, 2 blocking | validation-1.md | 34k | 9 | 2 |
    | 6 | fix | task-implementer | a41d7b2 | 2 fixed, 0 declined | | 49k | 20 | 3 |

Result is taken from the agent's final message or the file's header. An implementer row's
Result is its commit count and its `Cycles:` line. Every agent it started gets a sub-row
directly under it, one per line of its `Agents:` block, in order: `#` is the parent's number
and a counter (`3.1`, `3.2`), Stage is the parent's stage and `› cycle <n> <red|green|direct|style>`,
Agent is the type after `└ `, and Code commit, Result and File are empty. The parent row and
its sub-rows are one commit. A sub-row never routes: "the last row" always means the last row
whose `#` is a whole number. A validation's two agents
get a row each, staged `validation <n> run` and `validation <n> report`, and so do the brief's,
staged `survey` and `brief`. A row rebuilt from a commit on resume has no final message to
read: take its Result from the count in the file's header and add `, from resume`, so the
runner's reads `22 items, from resume`, the scout's `1 wrong of 14 anchors, from resume` and
the writer's comes from the brief's `Counts:` line. Context, Tools and Min
come from the `<usage>` block that reports the agent finished: `subagent_tokens` in thousands,
`tool_uses`, and `duration_ms` in whole minutes. Context is how full the agent's window was
when it stopped. Min is wall clock and includes stalls. `run-stats.py` separates them. A
usage block that has not arrived when the row is written leaves `?` in all three cells, filled
in a later row's commit if it turns up. **Never end your turn to wait for a `<usage>`
block.** An agent's report and the notification carrying its usage arrive as two messages,
sometimes minutes apart, and the usage changes nothing about where the run goes next. Log with
`?`, route, dispatch. `stats.md` reads every agent's numbers from the transcripts at the pull
request, so a `?` loses nothing. A retry
that gets no row of its own adds its numbers to the row, as `+`, e.g. `61k+88k`. An
implementer row rebuilt on resume has no `Agents:` block and so no sub-rows; `stats.md`
still counts those agents. A row the orchestrator
writes for its own step has `orchestrator` as its agent and one of these stages: `feedback`,
`ruling`, `grant`, `escalated`, `stopped`, `validation carried`, `pull request`, `pull request updated`. Its Context,
Tools and Min are empty.

Row 0 is the file's creation, before any agent runs. Each row is its own commit,
`docs(<feature>): loop task <NN> row <#>`. It carries any file the orchestrator changed for that step. The orchestrator's
few other commits also start `docs(<feature>): loop task <NN>`, so a resuming orchestrator can
tell its own commits from an agent's.
