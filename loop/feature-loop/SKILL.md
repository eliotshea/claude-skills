---
name: feature-loop
description: Use when the user runs /feature-loop to deliver a planned feature under docs/tasks/ one task at a time, each ending in a validated pull request into the feature branch.
disable-model-invocation: true
argument-hint: <docs/tasks/feature-dir> [task number]
---

# Feature loop

You are the orchestrator. You deliver the tasks of one planned feature, one at a time. Each
task passes through a fixed loop of subagents and ends in a pull request into the feature
branch. Then you stop until the human tells you it is merged.

You route. The subagents read the code, write it, check it and judge it. Your context has to
last the whole feature, so what you hand an agent is paths, round numbers and commits, and
what you take back is the short header of the file it wrote.

Arguments: `$ARGUMENTS`. The first is the feature directory. The second, if present, is the
task to run.

Read `${CLAUDE_PLUGIN_ROOT}/loop/feature-loop/handoff-format.md` now. It defines the run directory, the
report header, finding ids, statuses and `log.md`. Every agent follows it too. Every path you
pass to an agent or grep is relative to the repository root.

**One plain command per Bash call,** with the guard and the `loop.py` subcommands that
handoff-format.md's "Commands" gives, and never `$` followed by a digit in this file.

## Setup, once per session

1. **Feature branch.** It has the feature directory's name, e.g.
   `docs/tasks/issue-110-embed-player` is branch `issue-110-embed-player`.
   **Plan gate.** A feature planned with `/feature-plan` has a `plan-log.md`. Its plan PR is
   merged exactly when the feature branch's copy has a `plan PR` row, because that row is only
   ever committed on the plan branch. `loop.py plan-gate <feature>` fetches the branch and
   prints one line:
   - `no branch`: ask the human for the branch.
   - `no plan log`: the feature was planned before `/feature-plan`, go on.
   - `plan merged`: go on.
   - `plan not merged`: refuse. Tell the human the plan PR is not merged into `<name>` and end
     with `/feature-plan <feature>` in a fenced block.
2. **Worktree.** All work happens in `.claude/worktrees/<feature-branch>`. If it does not
   exist, run `git fetch origin` in the main checkout, then `git worktree add
   .claude/worktrees/<feature-branch> <feature-branch>`. If that fails because the branch is
   checked out somewhere else, ask the human. Switch in with EnterWorktree and its `path`.
   Every agent runs in this worktree, one at a time, but for the design and code reviews,
   which change no code and run together.
3. **Runnable and clean.** Copy `.env` from the main checkout root if the worktree lacks it;
   it is gitignored and the build fails without it. Run `pnpm install` if `node_modules` is
   missing. `git fetch origin`. If `git status --porcelain` shows changes while a task branch
   in progress ("Find where you are", step 1) is checked out, leave them for Resuming. Any
   other changes: stop and ask the human about them before switching any branch.
4. **Validation port.** `loop.py port 3100` prints 3100, or the next even port above it
   where nothing answers on it or the one above. Every validator gets this port, and its
   screenshots of the base commit use the one above it. A validator that finds it taken
   later moves up by itself with the same command, and never waits for it.
5. **Attribution.** Your own instructions give attribution lines for commit messages and for
   pull request bodies. Store them, verbatim, in the worktree:

       python3 ${CLAUDE_PLUGIN_ROOT}/loop/_lib/loop.py set-attribution --commit '<commit lines>' --pr '<pull request lines>'

   Every commit you and the agents make goes through `loop.py commit '<subject>' <path>…`,
   which stages those paths and adds the commit lines. `loop.py pr-body` ends `pr-body.md` with
   the pull request lines. Run it every session, since another model may have run the last.
6. **Labels.** The feature branch's pull request into `master` carries the label
   `feature-branch`, and the cleanup pull request carries `cleanup`. `/feature-plan` labels the
   first when it opens it; a feature planned before that gets it here. `--force` makes this safe
   to repeat:

       gh label create feature-branch --color 1D76DB --description "Feature branch PR into master" --force
       gh label create cleanup --color C5DEF5 --description "Removes feature-loop run files" --force
       gh pr list --base master --head <feature-branch> --state open --json number -q '.[].number'

   If that finds a pull request, `gh pr edit <number> --add-label feature-branch`. If it finds
   none, go on: the human opens it when they choose.

## Find where you are

1. **A task in progress.** A task is in progress when its branch adds this feature's
   `runs/<NN>/log.md` and is not merged. `loop.py find-task <feature>` fetches, checks every
   unmerged branch and its pull request, and prints `<branch> <NN>` for each, or `none`.
   - `none`: go to step 2.
   - More than one, or the second argument names a different task: ask the human which to
     run.
   - Exactly one: check it out, read its `log.md`, and continue from "Resuming".
2. **The next task.** Run `git checkout <feature-branch>`, then, as its own call,
   `git pull --ff-only origin <feature-branch>`. Take the task the second argument names.
   Without one, take the first task, in the dependency order of `00-overview.md`, whose file
   has no `Status: complete` line while all its dependencies have one. When every task is
   complete, go to "Cleanup".
3. **Start it.** Name the task branch like this feature's earlier task branches:
   `gh pr list --base <feature-branch> --state all --json headRefName -q '.[].headRefName'`.
   If there are none, use `<feature-branch>-task-<NN>`. Then:

       python3 ${CLAUDE_PLUGIN_ROOT}/loop/_lib/loop.py start <feature> <NN> <task branch>

   It cuts the branch from the feature branch, writes `runs/<NN>/log.md` from the template in
   handoff-format.md and commits it as row 0. The skills, agents and scripts come from the
   plugin, so you and every agent run the same copy. The project's own loop files
   (`playwright.validation.config.ts`, `tests/validation/README.md`) come from the worktree;
   start makes them match master.
   - **When the branch's copy of those differs from master's,** the same commit replaces it
     with master's, and row 0's Result says `loop tooling synced from master`. The task's pull
     request carries that sync into the feature branch.

   Once it has printed the commit, dispatch the scout, or the brief writer for a chore-only
   task (see "The loop").

### Resuming

List what agents did after the last row, oldest first, and whether anything is uncommitted:

    python3 ${CLAUDE_PLUGIN_ROOT}/loop/_lib/loop.py since 'loop task <NN> row' --mine 'docs(<feature>): loop task <NN>'

`--mine` leaves out your own commits. If an agent you dispatched in this session has sent no
completion notification yet, it is still running: whatever it has left in the tree is work in
progress, not a cut-off step. Wait for its notification before anything below.

- **Nothing, and the last row is `pull request` or `pull request updated`:** tell the human the
  pull request (number in that row) is waiting on them. Handle their reply as in "When the
  human replies".
- **Nothing, and the last row is `escalated` or `stopped`:** tell the human what that row says
  and wait for their instruction.
- **Nothing, and any other row:** route on the last row again, without logging it again. Every
  step is safe to repeat: an agent replaces the file it writes, and the pull request steps
  commit only what changed and reuse a pull request that already exists.
- **Report file commits** (`test(validation): …`, `docs(validation): …`, `docs(<feature>):
  design review …`, `docs(<feature>): code review …`, `docs(<feature>): survey …`,
  `docs(<feature>): brief …`): log one row per commit, in commit order, then route on the last
  one. A validation round leaves two, a brief leaves the survey and the brief, and a retry
  leaves a second commit with the same subject as the first: log the later one only.
- **Commits or uncommitted changes from an agent:** the step the last row routed to was cut
  off. `git status --porcelain` says which agent it was, because each one writes its own
  paths: `survey.md` is the scout, `brief.md` is the brief writer, the script dir or
  `evidence-<n>.md` or `shots/` is the runner, `validation-<n>.md` is the reporter, `architecture-<n>.md`
  is the architect, `review-1.md` is the code reviewer, and code outside the run dir is the
  implementer. Architecture round 1 and the code review run together, so both can be cut off.
  Dispatch each cut-off agent again with its prompt plus
  `Previous attempt: interrupted. Its commits since the last log row and any uncommitted
  changes are in the tree. Finish the job.`

## The loop

```dot
digraph feature_loop {
  node [shape=box];
  survey; brief; build; validate; report; fix; "design and code review"; "review fix";
  "architect round 2+"; refactor;
  "human feedback" [shape=ellipse];
  "PASS?" [shape=diamond];
  "open or update PR, stop" [shape=doublecircle];

  survey -> brief -> build -> validate -> report -> "PASS?";
  "PASS?" -> fix [label="BLOCKED"];
  "PASS?" -> validate [label="BLOCKED, tooling only"];
  fix -> validate;
  "PASS?" -> "design and code review" [label="PASS, not final"];
  "PASS?" -> "architect round 2+" [label="PASS, final, design changes requested"];
  "PASS?" -> "open or update PR, stop" [label="PASS, final"];
  "design and code review" -> "review fix" [label="FINDINGS or CHANGES REQUESTED"];
  "design and code review" -> validate [label="CLEAN and APPROVED, code changed since the last PASS"];
  "design and code review" -> "open or update PR, stop" [label="CLEAN and APPROVED, carry"];
  "review fix" -> validate;
  "architect round 2+" -> "open or update PR, stop" [label="APPROVED"];
  "architect round 2+" -> refactor [label="CHANGES REQUESTED, granted"];
  refactor -> validate;
  "open or update PR, stop" -> "human feedback" [style=dashed];
  "human feedback" -> "review fix";
}
```

After the build's validation passes, the design review (architect round 1) and the code
review run at once, on the same commit, and one review fix answers both files. A style-only
or chore-only task gets the code review alone. Architect round 2 and later run only after a
final validation passes while the design review still has changes requested, and rule only
on round 1's requests.

A **stage** is one piece of implementation work and the validation rounds that follow it.
There are four kinds: the build, a review fix, a refactor and a feedback fix. Reviews with
nothing to fix also start a stage, one that begins at its validation. Each stage allows 3 fix
rounds, counted from the stage's start or from the latest `grant` row for that stage.

A validation is **final** when its stage began at the reviews or later. Only a final
validation that passes opens or updates the pull request.

**A passing round carries.** Before every final validation, run

    python3 ${CLAUDE_PLUGIN_ROOT}/loop/_lib/loop.py carry <run dir>

`carry <n>` means validation n passed at the code that is there now, and a round at that same
code ran the regression suite green: a final round would check the same commit again and
find what n found. Log a `validation carried` row (Result `validation <n> carried`), and route
as on a final PASS. `validate: <why>` means run it. A review fix, a feedback fix or a refactor
that committed code always gets `validate`.

**Tooling findings.** A finding labelled `tooling` (`### V3-1 · tooling`) is about the
validator's own scripts or the loop's tools, such as a mask that moves or a base worktree
that would not serve, never the app. The implementer cannot fix it, because both are outside
its diff surface, so a BLOCKED round whose every blocking finding is tooling goes straight to
the next validation, whose runner repairs them first. That round counts as one of the stage's
fix rounds, so a tool that stays broken still escalates.

A task is **style only** when its file has `[style]` criteria and no `[logic]` ones. Count
each, in two calls:

    grep -cE '^[0-9]+\. \[logic\]' <task file>
    grep -cE '^[0-9]+\. \[style\]' <task file>

Its implementer writes no tests, its validator judges it by before-and-after screenshots, and
it skips the design review: a diff of class strings has no modules or seams for the architect
to weigh, and the code reviewer still reads every line. A task with no tags at all, cut
before they existed, is not style only.

A task is **chore only** when every criterion is `[chore]`: comments, docs, deleting code
nothing uses, turning an existing test on. Count them the same way,
`grep -cE '^[0-9]+\. \[chore\]' <task file>`, against the logic and style counts. A chore
changes nothing a running page does, so it takes the short road:

- **No scout.** The brief writer works from the task file alone (`Mode: chore`) and records
  the baseline itself. A survey of the code around a deleted comment costs more than the task.
- **No tests, no views.** The implementer runs `direct` cycles only, and the validator proves
  each criterion by command and code read, plus `loop.py inert`, which lists every line under
  `src` the diff changed that is not a comment. The regression suite runs only when that list
  has something besides deleted exports, and the specs under `tests/app/` that the diff
  touches run instead.
- **No design review**, as for style only. The code reviewer still reads every line.

A task that mixes chore with logic or style criteria is not chore only: it takes the full
loop, and its chore criteria become `direct` cycles.

## Dispatching

Use the Agent tool with the agent's `subagent_type`. Every prompt starts with these lines,
then the agent-specific ones below. Each agent's own definition says what to do with them.

    Feature dir: docs/tasks/<feature>
    Task file: docs/tasks/<feature>/<NN>-<slug>.md
    Run dir: docs/tasks/<feature>/runs/<NN>
    Base commit: <from log.md>

| Step | subagent_type | Agent-specific lines |
|---|---|---|
| survey | `eliot:task-scout` | `Base branch: <feature-branch>` |
| brief | `eliot:brief-writer` | `Base branch: <feature-branch>`, `Survey file: <run dir>/survey.md` |
| brief, chore only | `eliot:brief-writer` | `Base branch: <feature-branch>`, `Mode: chore` |
| build | `eliot:task-implementer` | `Mode: build` |
| fix | `eliot:task-implementer` | `Mode: fix`, `Findings: <run dir>/validation-<n>.md: <ids>` |
| refactor | `eliot:task-implementer` | `Mode: refactor`, `Findings: <run dir>/architecture-<n>.md: <ids>` |
| review fix | `eliot:task-implementer` | `Mode: review-fix`, then one `Findings: <file>: <ids>` line for each of `<run dir>/review-1.md` and `<run dir>/architecture-1.md` that has open ids, or for `<run dir>/feedback-<k>.md` |
| validate | `eliot:task-validator` | `Round: <latest validation + 1>`, `Final: <yes or no>`, `Kind: <full, style only or chore only>`, `Script dir: tests/validation/<feature>`, `Previous validation: <run dir>/validation-<latest>.md or none`, `VALIDATION_PORT: <port>` |
| report | `eliot:validation-reporter` | `Round: <the round the runner just ran>`, `Final: <yes or no>`, `Kind: <as the runner's>`, `Evidence file: <run dir>/evidence-<n>.md`, `Previous validation: <run dir>/validation-<n-1>.md or none`, `Script dir: tests/validation/<feature>`, `VALIDATION_PORT: <port>` |
| architect | `eliot:architect-reviewer` | `Round: <n>`, `Previous architecture: <run dir>/architecture-<n-1>.md or none` |
| code review | `eliot:code-reviewer` | `Round: 1` |

The ids are the findings whose status is open or reopened, read without opening the file:

    python3 ${CLAUDE_PLUGIN_ROOT}/loop/_lib/loop.py findings <file>

Their titles, for telling the human: `loop.py findings <file> --titles`.

Validation rounds are numbered across the whole task, and `Previous validation` is always the
latest one, whatever stage it came from. A validation is two dispatches: the runner, then the
reporter on the evidence it wrote. They share the round's number.

The design and code reviews are two dispatches in one message, so they run at once. Each
gets its own row when it returns.

## Routing on a result

After each agent returns:

1. **Log it.** One call checks the file the agent left, appends its row to `log.md` and
   commits it:

       python3 ${CLAUDE_PLUGIN_ROOT}/loop/_lib/loop.py row <run dir> '<stage>' <agent> '<result>' --check <its file> --file <its file's name> --usage '<context>k <tools> <min>'

   It prints the file's header, which is all you route on, then the commit. It writes no row
   when the file is missing or its header is not valid, as handoff-format.md defines one.
   - An implementer leaves no file, so leave `--check` out and check its final message
     yourself: it has a `Blocked:` line, and if that is `none`, a `Commits:` line followed by
     at least one commit.
   - A row for your own step has `orchestrator` as its agent and no `--check`.
   - `--with <path>…` commits a file you changed for this step in the same commit.
   - `--usage` comes from the agent's `<usage>` block when it is already in your context.
     Otherwise leave it out, and never go back to fill it: `stats.md` reads every agent's
     numbers from the transcripts.
2. **If the check fails, first ask whether the agent has finished.** An agent hands back one
   report, and an agent that starts agents of its own can hand back early, with something like
   `(waiting)`, and keep working. Until its completion notification arrives (`status`
   `completed`, with its `<usage>`), it is still running, and a second dispatch would put two
   agents on one branch. So with no completion notification yet, dispatch nothing: end your
   turn, and the notification wakes you. Then ask it with SendMessage:
   `Your hand-back was missing <what was wrong>. Send your final message as your definition
   gives it.` Its reply is the result to check.
3. **If the check fails on a finished agent,** or on its reply to that message, dispatch the
   same agent again with the same prompt plus one line: `Previous attempt: <what was wrong>.`
   A retry gets no log row. If the second attempt fails too, escalate.
4. **The row is committed before its next step starts.** Wait for `row` to print the commit,
   then dispatch, in a later call: parallel calls do not wait on each other, so a refused row
   would leave an agent running on a step the log does not show.
5. **Route on the first row that matches:**

| Result | Next |
|---|---|
| The log holds only its start row, chore only | brief, chore only |
| The log holds only its start row | survey |
| Scout wrote the survey | brief |
| Brief writer wrote the brief | build |
| Implementer's `Blocked:` is not `none` | Escalate. |
| Implementer returned, Final yes for its stage | `loop.py carry`: carried, or validate, final |
| Implementer returned | validate, with Final from the stage it is in |
| Runner wrote the evidence | report, same round |
| Validation `Repeat:` names an id that no `grant` row for this stage names | Escalate. A fix did not hold. |
| Validation BLOCKED, and this stage has had 3 fix rounds | Escalate. |
| Validation BLOCKED, and `loop.py findings <file> --label tooling --count` equals Blocking | validate, same Final, no fix |
| Validation BLOCKED | fix |
| Validation PASS, final, or `validation carried`, and the latest architecture file is CHANGES REQUESTED | architecture, with round = the latest architecture round + 1 |
| Validation PASS, final, or `validation carried`, and `log.md` has a `pull request` row | update the pull request |
| Validation PASS, final, or `validation carried` | open the pull request |
| Validation PASS, style only or chore only | code review |
| Validation PASS | architecture round 1 and code review, at once |
| Architecture round 1 or review returned, neither style only nor chore only, and the other has no row yet | Wait for the other while it runs. After a resume, dispatch it. |
| Review CLEAN, and architecture round 1 APPROVED or skipped | `loop.py carry`: carried, or validate, final |
| Review or architecture round 1 returned | review fix, with the open ids of both files |
| Architecture APPROVED | as on a final PASS: update or open the pull request |
| Architecture CHANGES REQUESTED, and a `grant: architecture round <this round>` row exists | refactor |
| Architecture CHANGES REQUESTED | Escalate. |

## Escalating

Log an `escalated` row saying why, commit it, and tell the human: the task, the stage, the
round, the file path, and what stopped the loop. A validation round has two files and so does a
brief, so name the one that holds the answer, and say which of the two exists: a scout that
failed its check twice leaves no survey and the writer cannot run at all, while a writer that
failed twice leaves a good survey and no brief.

- **A cap, a Repeat or a second architecture refusal.** Give the titles of the blocking or
  repeated findings and three choices: another round, a ruling on a finding, or stop.
- **An implementer's `Blocked:` or an agent that failed its check twice.** Relay its words and
  ask what to do.

Applying the answer:

- **Another round.** Log a `grant` row. Its Result is `grant: <stage>, <ids>` after a cap or a
  Repeat, naming the stage (e.g. `build`, `refactor 1`, `review fix`) and the ids that were
  blocking or repeated. After an architecture refusal it is `grant: architecture round <n>`.
  Then route again on the same result. A stage grant resets that stage's fix count and stops
  its named Repeat ids escalating again within the stage. An architecture grant lets that
  round's requests be refactored.
- **A ruling on a finding.** In the latest file that holds the finding, set its status as the
  human decided (`accepted` closes it, `reopened` keeps it blocking) and write
  `Ruling: Human: <their words>`. Recount that file's header with
  `loop.py findings <file> --count` and `loop.py findings <file> --status disputed --count`,
  and set its verdict to match. Log a `ruling` row, committing the edit with it, then route on the
  corrected header. No agent reopens a finding whose ruling starts `Human:`.
- **Stop.** Write `stats.md` as in step 1 of the pull request, log a `stopped` row committing
  it, and stop. End with the same fenced block as step 5
  of the pull request, naming this task instead of the next one, so the human can pick the
  loop up where it stopped.
- **Anything else.** Do it if an agent can: dispatch that agent with the human's words as an
  extra prompt line. Log it, then route on what it returns.

## The pull request

1. **Body.** Build `runs/<NN>/pr-body.md`. It stitches each run file's `## For the PR` section
   together without you reading them, from the latest validation and architecture files, and
   ends with the pull request lines you stored:

       python3 ${CLAUDE_PLUGIN_ROOT}/loop/_lib/loop.py pr-body <feature> <NN>

   The latest validation and architecture files carry every earlier finding forward, so these
   greps see each finding once.

   Then record every agent's context and time, including retries that never got a row, with
   stalls separated out:

       python3 ${CLAUDE_PLUGIN_ROOT}/loop/feature-loop/run-stats.py <feature> <NN> > docs/tasks/<feature>/runs/<NN>/stats.md

2. **Push.** If `pr-body.md` or `stats.md` changed, commit them:
   `loop.py commit 'docs(<feature>): loop task <NN> pr body' <run dir>/pr-body.md <run dir>/stats.md`.
   `git status --porcelain` is now empty. Run `git push -u origin <task-branch>`.
3. **Open.** If `gh pr view <task-branch> --json number` already finds a pull request, use it.
   Otherwise `gh pr create --base <feature-branch> --head <task-branch> --title "<the brief's
   PR title>" --body-file <run dir>/pr-body.md`. Always pass `--base`: the repository default
   is `master`.
4. **Completion marks.** Every task gets both:
   - A status line directly under the task file's H1, followed by a blank line:
     `> **Status: complete.** PR #<number>, commit <last code commit>, <YYYY-MM-DD>.`
   - A row in `<feature dir>/PROGRESS.md`: `| <NN> | <task title> | #<number> | <last code
     commit> | <YYYY-MM-DD> |`. If the file does not exist, create it with a `# <feature>:
     progress` heading and the table header `| Task | Title | PR | Commit | Date |`.

   The last code commit is `git log -1 --format=%h -- . ':!docs/tasks' ':!tests/validation'`.
   If either mark changed, commit them with `loop.py commit 'docs(<feature>): loop task <NN> marks'`
   and the two files. Push.
5. **Stop.** Log a `pull request` row with the number, commit, push. Tell the human: the pull
   request URL; the number of manual checks waiting for them
   (`grep -c -- '- \[ \]' <latest validation file>`); the number of entries under Disputed in
   `pr-body.md`; the largest context and its agent, if it is over 50k, from the last line of
   `stats.md` (`tail -1`); and to
   reply `merged` once it is in, or with feedback.

   Then end the message with the command that starts the next task, alone in a fenced code
   block, because a fenced block is what gives the human a copy button on the phone and in the
   app:

       ```
       /feature-loop docs/tasks/<feature> <NN of the next task>
       ```

   Nothing follows it. The next task is the first one in `00-overview.md`'s dependency order
   whose file has no `Status: complete` line, which is never this one: step 4 just marked it.
   When every task is marked, this was the final task: say that once it is merged the loop
   opens the cleanup pull request, and the command is `/feature-loop docs/tasks/<feature>`
   with no task number.

   Name the number rather than leaving the loop to pick. The human pastes this into a session
   that does not exist yet, hours or days later, and a command that says which task it starts
   is one they can check against the pull request they just merged.

**Updating** an open pull request, after a feedback fix or a ruling, reuses these steps: steps
1 and 2, then `gh pr edit <number> --body-file <run dir>/pr-body.md`, then step 4 with the
current last code commit. Get the URL with `gh pr view <number> --json url -q .url`. Log a
`pull request updated` row and stop as in step 5.

## Cleanup

Once every task is complete and merged, the run files have done their job. One last pull
request into the feature branch removes them, so the feature does not reach `master` carrying
hundreds of handoff files. It keeps each task's `log.md`, the record the tasks' sizes are
compared from, and folds each `stats.md` total into one table. Everything else stays in git
history at the commit the cleanup starts from.

1. **Once only.** Look for a cleanup pull request already made:

       gh pr list --base <feature-branch> --label cleanup --state all --json number,state,url

   `MERGED`: say the feature is done and stop. `OPEN`: give the human its URL, ask them to
   reply `merged` once it is in, and stop. `CLOSED`, with none open or merged: ask the human
   whether to open another. None: go on.
2. **Branch.** From the feature branch, freshly pulled in "Find where you are", step 2:

       git checkout -B <feature-branch>-cleanup origin/<feature-branch>

   `-B` rebuilds the branch if a cut-off cleanup left one behind. Note the starting commit,
   `git rev-parse --short HEAD`, for the body.
3. **Condense.** `loop.py cleanup <feature>` removes every run file but each `log.md`, prunes
   the atlas of gone and stale entries, folds every `runs/<NN>/stats.md` total into
   `runs/stats.md`, and stages it all. When it prints `no stats total for task <NN>…`, run
   `run-stats.py <feature> <NN>` for each, add its last line to the table in `runs/stats.md`
   and stage it. A task it still cannot measure is named in the body as missing from the totals.

   It leaves `runs/<NN>/log.md` for every task and `runs/stats.md`, and nothing else under
   `runs/`. The shared atlas keeps only its fresh entries, for the next feature's scouts. The
   task files, `00-overview.md`, `PROGRESS.md`, the plan's files and the validation scripts in
   `tests/validation/<feature>/` stay.
4. **Commit and push.** `loop.py commit 'docs(<feature>): clean up loop run files'` commits
   what the cleanup staged. `git push --force-with-lease -u origin <feature-branch>-cleanup`.
5. **Open.** Write the body to a file outside the repository, `mktemp`, since the run
   directories are gone: one line saying this removes the loop's run files for `<feature>`;
   the counts of files removed and kept, from `git diff --shortstat HEAD^ HEAD`; that each
   task's `log.md` stays for comparing task sizes and `runs/stats.md` holds every task's
   total; that every removed file is still at `<starting commit>`, as
   `git show <starting commit>:docs/tasks/<feature>/runs/<NN>/<file>`; and the pull request
   attribution lines. Then

       gh pr create --base <feature-branch> --head <feature-branch>-cleanup --title "docs(<feature>): clean up loop run files" --label cleanup --body-file <that file>

6. **Stop.** Give the human the URL and ask them to reply `merged` once it is in. When they
   do, confirm it as in "When the human replies", then say the feature is done. Print no
   command.

The cleanup gets no log row: it belongs to no task, and each `log.md` ends where its task did.

## Task size

Each agent should finish under 50k of context. An agent over it usually means the task file
asks too much of one pass: too many criteria, or code spread over too many files for one
brief. The loop does not split a task in flight. It reports the size, and the human
resizes the tasks not yet started. For a whole feature, including retries that never got a
row, run:

    python3 ${CLAUDE_PLUGIN_ROOT}/loop/feature-loop/run-stats.py <feature> [task]

It prints each agent's largest context, its active minutes with stalls of 10 minutes or more
removed, and a total per task: the number of runs, the largest context and its agent, the
context of all its runs added up, and the minutes. It includes the test-writers and
code-writers the implementer starts and retries that got no row, and leaves out runs the
human stopped. Each task's `stats.md` is this output for that task alone.

The implementer's own Context stays small because it reads no code: each tdd cycle runs in a
`test-writer` and a `code-writer` of its own. `stats.md` gives each of them, and the largest
is the number to watch for code spread over too many files. A single cycle over 50k means
one behaviour touches more code than one window holds.

The survey row's size is another size signal. A survey `over budget` is a task whose
anchors, rules and baseline alone fill more than one writer's window should hold.

The survey row's `atlas` counts say how much of the task's ground the atlas already knew,
from this feature or an earlier one. Mostly fresh is a task on files earlier tasks mapped and left alone, so its scout reads little.
Mostly new is a task breaking new ground, and its survey costs what a first survey costs.

The brief row's `extra reads` is a third. It counts the files the writer had to
open because the survey did not carry them, out of three. A task that spends all three is a
task whose scout could not fit the ground it had to cover.

## When the human replies

- **`merged`.** Confirm with `gh pr view <number> --json state -q .state` that it says
  `MERGED`, then go to "Find where you are", step 2. For the cleanup pull request, say the
  feature is done instead.
- **Feedback on the pull request.** Write `runs/<NN>/feedback-<k>.md`, where k counts feedback
  rounds on this task:
  - The header comes from handoff-format.md, with Verdict FINDINGS and Blocking set to the
    number of points.
  - Each point becomes a finding `### U<k>-<j> · feedback` with `Status: open`. Evidence is the
    human's words, verbatim. Expected is `Asked for by the human on PR #<number>`. Repro is
    `none given`. Fix and Ruling are empty.
  - `## For the PR` is one line saying how many points this round raised.

  Log a `feedback` row, committing the file with it, and start a feedback fix: a review fix with this file, then
  final validation.
- **A ruling on disputed or declined findings in the pull request.** Record it as in "A ruling
  on a finding" under Escalating, without routing on the header. If the ruling asks for a
  change, write that change up as feedback. Otherwise update the pull request.
- **Anything else.** Answer it. The loop does not advance.

## What you read

These are all you take in from a task:

- the header `loop.py row` prints, or the implementer's final message
- finding ids and titles, through `loop.py findings`
- `log.md`, and `loop.py since` when resuming
- `00-overview.md` and the task files' status lines, to pick the next task
- each agent's final message, which its definition keeps to a few lines

When you record a ruling, change only that finding's `Status:` and `Ruling:` lines and the
header, using Edit on those lines.

| Thought | Do this |
|---|---|
| "The evidence file says it failed, that's a finding" | The reporter decides that. The runner's evidence is what happened, not what it means. |
| "It's a one-line fix, I'll make it myself" | Dispatch a fix. Your edit skips the test, and the next validator would judge a commit no agent accounted for. |
| "I'll read the validation file to understand the failure" | The implementer reads it. You route on the header. |
| "The review fix was tiny, and the last validation passed" | Run `loop.py carry`. A fix that committed code gets a final validation: the pull request claims what that validation saw. |
| "Nothing changed since the last PASS, but the table says validate, final" | Run `loop.py carry`. It carries that PASS when the code and a green regression run are the same. |
| "Every finding is about the validator's own script; the implementer can decline them" | Route on the `tooling` label: the next runner repairs its scripts. A decline only buys another round to rule on it. |
| "Architecture round 2 raised a good new point" | Round 2 rules only on round 1's requests. New points are notes for the human. |
| "I'll chain these few commands in one call" | One plain command per call, or a `loop.py` subcommand. A refused chain is a retry, and a variable or `$(…)` never survives the guard. |
| "These calls are independent, I'll batch them" | Not a row and the dispatch it routes to. The dispatch waits for the row's commit. |
| "The implementer handed back `(waiting)`, I'll dispatch it again" | It is still running until its completion notification. Wait for that, then ask it with SendMessage. |
| "The human is away, I'll start the next task" | Stop. The next task branches from a feature branch that includes this one. |
| "The finding contradicts the task file, I'll skip it" | The implementer declines it, quoting the task file. A V or A decline is ruled on by the next round of its stage. An R or U decline goes to the human in the pull request. |
