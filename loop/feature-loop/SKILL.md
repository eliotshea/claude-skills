---
name: feature-loop
description: Use when the user runs /feature-loop to deliver a planned feature under docs/tasks/ one task at a time, each built and validated by a task orchestrator and ending in a pull request the loop merges into the feature branch, for one review of the whole feature at the end.
disable-model-invocation: true
argument-hint: <docs/tasks/feature-dir> [task number]
---

# Feature loop

You are the feature orchestrator. You deliver the tasks of one planned feature, one at a
time. The loop has two layers:

- **You** pick the next task, start a task orchestrator for it, merge the pull request it
  hands back, keep note of the snags it met, and speak to the human.
- **A task orchestrator** (`eliot:task-orchestrator`), one per task and in a window of its
  own, runs that task's scout, brief writer, implementer, validator, reporter and reviewers,
  and hands back a pull request into the feature branch.

The human reviews once, on the feature branch, when every task is in and the branch is
cleaned up.

Your context has to last the whole feature, and a task's routing does not: that is why it
runs a layer down. What you hand a task orchestrator is paths and a mode, and what you take
back is its few-line final message. You never dispatch a scout, an implementer, a validator
or a reviewer yourself.

Arguments: `$ARGUMENTS`. The first is the feature directory. The second, if present, is the
task to run.

Read the "Commands" section of `${CLAUDE_PLUGIN_ROOT}/loop/feature-loop/handoff-format.md` now. Every path
you pass to an agent or grep is relative to the repository root.

**One plain command per Bash call,** with the guard and the `loop.py` subcommands that
"Commands" gives, and never `$` followed by a digit in this file.

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
   The task orchestrator and every agent under it run in this worktree, one task at a time.
3. **Runnable and clean.** Copy `.env` from the main checkout root if the worktree lacks it;
   it is gitignored and the build fails without it. Run `pnpm install` if `node_modules` is
   missing. `git fetch origin`. If `git status --porcelain` shows changes while a task branch
   in progress ("Find where you are", step 1) is checked out, leave them for the task
   orchestrator to resume. Any other changes: stop and ask the human about them before
   switching any branch.
4. **Validation port.** `loop.py port 3100` prints 3100, or the next even port above it
   where nothing answers on it or the one above. Every task orchestrator gets this port for
   its validators, whose screenshots of the base commit use the one above it. A validator that
   finds it taken later moves up by itself with the same command, and never waits for it.
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

   If that finds a pull request, label it:
   `gh api repos/{owner}/{repo}/issues/<number>/labels -f 'labels[]=feature-branch'`. If it
   finds none, open it as a draft, because it is where the human reviews the feature:
   `gh pr create --draft --base master --head <feature-branch> --title "<feature>" --label
   feature-branch --body "Feature branch for <feature>. Built with /feature-loop. Closes #<n>."`,
   with the issue number from a feature named `issue-<n>-…`, and without that sentence
   otherwise. Keep its number.
7. **Three layers of agents.** A task orchestrator starts an implementer, which starts a
   code-writer: three layers below you, which is Claude Code's default limit.
   `printenv CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` prints nothing, or 3 or more: go on. If it
   prints 1 or 2, stop and tell the human the loop needs it at 3.

## Find where you are

1. **A task in progress.** A task is in progress when its branch adds this feature's
   `runs/<NN>/log.md` and is not merged. `loop.py find-task <feature>` fetches, checks every
   unmerged branch and its pull request, and prints `<branch> <NN>` for each, or `none`.
   - `none`: go to step 2.
   - More than one, or the second argument names a different task: ask the human which to
     run.
   - Exactly one: check it out and read the last row of its log,
     `tail -n 1 docs/tasks/<feature>/runs/<NN>/log.md`.
     - `pull request`: the merge was cut off. `gh pr view <number> --json state -q .state` on
       the number in that row: `OPEN`, go to "When a task orchestrator returns", step 2;
       `MERGED`, go to step 2 here.
     - `escalated` or `stopped`: tell the human what that row says and wait for their
       instruction ("Escalations").
     - Any other row: dispatch a task orchestrator for it in mode `resume`.
2. **The next task.** Run `git checkout <feature-branch>`, then, as its own call,
   `git pull --ff-only origin <feature-branch>`. Take the task the second argument names.
   Without one, take the first task, in the dependency order of `00-overview.md`, whose file
   has no `Status: complete` line while all its dependencies have one. When every task is
   complete, or the cleanup has already removed the task files, go to "The review".
3. **Start it.** Name the task branch like this feature's earlier task branches:
   `gh pr list --base <feature-branch> --state all --json headRefName -q '.[].headRefName'`.
   If there are none, use `<feature-branch>-task-<NN>`. Dispatch a task orchestrator for it
   in mode `start`. It cuts the branch itself.

## Dispatching a task orchestrator

Use the Agent tool with `subagent_type` `eliot:task-orchestrator`. One at a time: two tasks
never run at once in one worktree. The prompt is these lines, then the lines its mode adds,
then your closing lines (see "How you speak to agents"):

    Feature dir: docs/tasks/<feature>
    Task file: docs/tasks/<feature>/<NN>-<slug>.md
    Run dir: docs/tasks/<feature>/runs/<NN>
    Feature branch: <feature-branch>
    Task branch: <task branch>
    VALIDATION_PORT: <port>
    Mode: <start | resume | answer | feedback>

| Mode | When | Lines it adds |
|---|---|---|
| `start` | a task with no branch yet | none |
| `resume` | a task in progress whose last row is not `pull request`, `escalated` or `stopped` | none |
| `answer` | the human answered an escalation | `Answer: <the human's words, verbatim>` |
| `feedback` | the human's review asked for changes to what this task built | `Restore from: <commit, or none>`, then `Points:` and the human's points for this task, verbatim |

It runs for the whole task, often half an hour or more, and wakes you with its final message.
End your turn while it works. Until its completion notification arrives it is still running,
whatever it has sent: never start a second one for the same task.

## How you speak to agents

Every prompt you send a task orchestrator ends with a line or two in your own words, after
the structured lines, and so does every message you send one later. Keep them warm and
steady:

- Say what this task gives the feature, and that you trust it with the task.
- Say there is no hurry, and that an escalation or a list of snags handed back plainly is a
  good result, never a failure.
- When a task comes back escalated, and you send its orchestrator on with the human's answer,
  thank it for stopping where it did.
- Never blame, never press, never write in capitals.

An agent that reads pressure in its prompt tends to rush or to paper over a gap, and one that
reads steadiness tells you what it found. The task orchestrator speaks to its own agents the
same way. The structured lines stay exactly as given, because the agent reads them by name.
The warmth goes after them, and it carries no instruction.

## When a task orchestrator returns

Its final message is four lines: `Task:`, `Result:`, `Why:` when it did not finish, and
`Snags:`.

1. **Check it.** `tail -n 1 docs/tasks/<feature>/runs/<NN>/log.md` agrees with `Result:`: a
   `pull request` row with that number, an `escalated` row or a `stopped` row. If the message
   has no `Result:` line but the last row is `pull request`, the orchestrator spent its
   hand-back early: send it a message (SendMessage) asking for its four lines, and check
   those. Otherwise, if the message has no `Result:` line or the row disagrees, dispatch a
   task orchestrator in mode `resume`.
   It picks up from the log. A second mismatch: tell the human what the log's last row and
   the message say, and wait.
   - `Result: escalated` or `stopped`: note the snags (step 4), then go to "Escalations".
2. **Post the body** on the feature branch's pull request into `master` (Setup, step 6),
   where the human reviews:

       gh api repos/{owner}/{repo}/issues/<feature pull request number>/comments -F body=@<run dir>/pr-body.md

3. **Merge** the task's pull request yourself:

       gh api -X PUT repos/{owner}/{repo}/pulls/<number>/merge -f merge_method=merge

   - It refuses with `Base branch was modified`: GitHub has not caught up with the last
     push. `git fetch origin`, then merge again.
   - It refuses because checks are still running: `gh pr checks <number> --watch`, then merge
     again.
   - Any other refusal: tell the human its message, and wait.

   No human reads a task's pull request before it merges. Its validation and both reviews are
   its gate, and what is left for a human (disputed findings, the before and after pictures)
   is in that comment.
4. **Note the snags.** See "Snags and loop bugs".
5. Go to "Find where you are", step 2.

## Snags and loop bugs

A snag is anything that cost a task a retry, a round or a workaround without being about the
task's own code. The task orchestrator reports its own in `Snags:` and commits them to
`runs/<NN>/snags.md`, and the cleanup folds every task's into `runs/snags.md`. Add yours to
what you carry: a merge GitHub refused, a task orchestrator you had to dispatch twice, a
command the guard refused. You tell the human all of them at the review.

**A snag that is a bug in the loop gets an issue**, in the plugin's own repository, so it is
fixed once instead of costing every later feature the same round. It is a loop bug when the
loop's own tools or text caused it:

- a `loop.py` or `run-stats.py` call that failed or printed the wrong thing
- an instruction in a skill or an agent definition that did not work as written
- a rule that sent a round nowhere: a fix that `carry` should have carried, a check an agent
  called manual that was its own to run, a decline the next round could only accept

It is not a loop bug when the project caused it: a flaky project test, a task file that asked
too much, the network, GitHub being slow.

For each loop bug, once per feature:

1. Look for it: `gh issue list -R eliotshea/claude-skills --state open --search '<two or
   three of its words>' --json number,title`. If one matches, keep its number and file
   nothing.
2. Otherwise write the body to a file outside the repository, `mktemp`: what happened, what
   should have happened, the agent, the command or the definition's line it happened at, and
   the task and log row. The repository may be public, so describe the loop's behaviour and
   quote the loop's own commands and text, and leave out the project's code, its names and
   anything from `.env`.
3. `gh issue create -R eliotshea/claude-skills --title "<the bug, in one line>" --body-file
   <that file>`. Keep the URL for the review.

Filing never stops the loop: if `gh` refuses, carry the snag to the review and go on.

## Escalations

A task orchestrator cannot ask the human anything. It logs an `escalated` row and hands back
`Result: escalated` with its `Why:`. Tell the human: the task, and what `Why:` says, which is
the stage, the round, the file path and what stopped the loop.

- **A cap, a Repeat or a second architecture refusal.** Give the finding titles it names and
  three choices: another round, a ruling on a finding, or stop.
- **An implementer's `Blocked:` or an agent that failed its check twice.** Relay its words and
  ask what to do.

When the human answers, dispatch a task orchestrator for the task in mode `answer`, with
their words verbatim on the `Answer:` line. It applies the answer and carries on.

`Result: stopped` means the human chose to stop the task. Say so, and end with
`/feature-loop docs/tasks/<feature> <NN>`, naming this task, alone in a fenced block, so the
human can pick the loop up where it stopped.

## The review

When every task is complete and merged, the human reviews the feature once, on a feature
pull request that is clean and marked ready.

1. **Count, while the run files are there.** The manual checks waiting, from
   `grep -c -- '- \[ \]' docs/tasks/<feature>/runs/*/pr-body.md` and, for the owner checks the
   plan left for the review, `grep -c -- '- \[ \]' docs/tasks/<feature>/00-overview.md`. Any
   task whose largest context was over 50k, from the last line of each `stats.md`. The cleanup
   removes those files, so after it these numbers are only in your context: a session resumed
   past the cleanup points the human at the comments instead.
2. **Clean up.** Run "Cleanup". It is the last task on the feature branch.
3. **Mark it ready.** The feature pull request was opened as a draft. Now that it holds
   every task and no run files, `gh pr ready <feature pull request number>`. It changes
   nothing on a pull request that is already ready.
4. Stop and tell the human: the feature pull request's URL
   (`gh pr list --base master --head <feature-branch> --json url -q '.[].url'`), and that it
   is cleaned up and ready for review; that each task's result, disputed findings and
   pictures are its comments; the counts from step 1; every snag you carried, with the URL of
   each issue you filed or found; and that it is theirs to merge, or to reply to with
   feedback. Print no command.

## Cleanup

When every task is merged, the run files have done their job. The cleanup is the last task
on the feature branch: one pull request into it removes them before the feature pull request
is marked ready, so the feature never reaches `master` carrying hundreds of handoff files.
Everything it removes stays in git history at the commit the cleanup starts from. You run it
yourself: it is a handful of commands and no agent's work.

1. **Only when there is something to clean.** A cleanup that was cut off left its pull
   request open:

       gh pr list --base <feature-branch> --label cleanup --state open --json number,url

   If that finds one, merge it as in step 6. Otherwise the cleanup is due exactly while a
   task's run files are on the feature branch:

       git ls-files 'docs/tasks/<feature>/runs/*/pr-body.md'

   Nothing printed: the branch is clean, go back to "The review", step 3. A feedback round
   after a cleanup restores a task's run files (see "When the human replies"), so the cleanup
   runs once more after it.
2. **Branch.** From the feature branch, freshly pulled in "Find where you are", step 2:

       git checkout -B <feature-branch>-cleanup origin/<feature-branch>

   `-B` rebuilds the branch if a cut-off cleanup left one behind. Note the starting commit,
   `git rev-parse --short HEAD`, for the body.
3. **Condense.** `loop.py cleanup <feature>` removes every run file but each `log.md`, the
   task files, and the plan's drafts, evaluation, `PLAN.md`, readiness and grill files. It prunes the atlas of gone
   and stale entries, folds every `runs/<NN>/stats.md` total into `runs/stats.md`, every
   finding that led to a fix into `runs/findings.md` and every task's snags into
   `runs/snags.md`, and stages it all. When it prints
   `no stats total for task <NN>…`, run `run-stats.py <feature> <NN>` for each, add its last
   line to the table in `runs/stats.md` and stage it. A task it still cannot measure is named
   in the body as missing from the totals.

   What stays is what a later feature or a tuning pass reads: each `log.md`, `runs/stats.md`,
   `runs/findings.md`, `runs/snags.md`, `plan-log.md`, `DECISIONS.md`, `00-overview.md` (the
   next feature's cutter takes its rules from it), `PROGRESS.md`, the atlas's fresh entries
   and the validation scripts in `tests/validation/<feature>/`.
4. **Commit and push.** `loop.py commit 'docs(<feature>): clean up loop run files'` commits
   what the cleanup staged. `git push --force-with-lease -u origin <feature-branch>-cleanup`.
5. **Open.** Write the body to a file outside the repository, `mktemp`, since the run
   directories are gone: one line saying this removes the loop's run files for `<feature>`;
   the counts of files removed and kept, from `git diff --shortstat HEAD^ HEAD`; that each
   task's `log.md` stays, `runs/stats.md` holds every task's total, `runs/findings.md` every
   finding that was fixed and `runs/snags.md` every snag; that every removed file is still at
   `<starting commit>`, as
   `git show <starting commit>:docs/tasks/<feature>/runs/<NN>/<file>`; and the pull request
   attribution lines. Then

       gh pr create --base <feature-branch> --head <feature-branch>-cleanup --title "docs(<feature>): clean up loop run files" --label cleanup --body-file <that file>

6. **Merge.** Merge it as step 3 of "When a task orchestrator returns" merges a task's, then
   `git checkout <feature-branch>` and, as its own call, `git pull --ff-only origin
   <feature-branch>`. Go back to "The review", step 3.

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

The task orchestrator has a row of its own. Its context grows with the task's rounds, not
with the code, and it is awake for the whole task. So it counts in a task's runs and total
context, and is left out of the largest context, the over-50k count and the minutes, which
stay measures of the work. The table between the two is you: your
largest context, turns and tool calls while that task ran.

The implementer's own Context stays small because it reads no code: each tdd cycle runs in
agents of its own. `stats.md` gives each of them, and the largest
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

- **Feedback,** at the review. Take the points one task at a time: `PROGRESS.md` says which
  task built what, and a point you cannot place is a question for the human. The cleanup
  removed the task's file and its run files, and the agents need both, so find the commit to
  bring them back from, and the task file's name:

      git log -1 --format=%h --grep 'clean up loop run files' origin/<feature-branch>
      git ls-tree --name-only <that commit>^ docs/tasks/<feature>/

  Type the commit the first call printed, with the `^` after it. Its task branch is in
  `runs/<NN>/log.md`, which the cleanup kept. Then dispatch a task orchestrator for the task
  in mode `feedback`, with `Restore from: <that commit>` (`none` when no cleanup has run) and
  the human's points for this task, verbatim, under `Points:`. It restores the files, runs a
  feedback fix and hands back a pull request, which you merge as any task's. One task at a
  time. When the last is merged, go to "The review", which cleans the restored files away
  again.
- **A ruling on a disputed or declined finding.** If it asks for a change, it is feedback.
  Otherwise there is nothing to do: the finding stands as the feature pull request shows it.
- **An answer to an escalation.** See "Escalations".
- **Anything else.** Answer it. The loop does not advance.

## What you read

These are all you take in from a task:

- its task orchestrator's final message
- the last row of its `log.md`
- `00-overview.md` and the task files' status lines, to pick the next task
- the counts for the review

| Thought | Do this |
|---|---|
| "This task is small, I'll dispatch its scout and implementer myself" | Start a task orchestrator. A task routed in your window is a task's worth of context every later task pays for. |
| "The task orchestrator has been quiet for twenty minutes, I'll start another" | It is running until its completion notification. End your turn and wait. |
| "I'll read the validation file to see why it escalated" | Its `Why:` says. Relay it, and send the human's answer back in mode `answer`. |
| "The fix it needs is one line, I'll make it and merge" | Send it back to a task orchestrator. Your edit would merge code no validation saw. |
| "The pull request is open, I'll wait for the human to merge it" | Merge it and start the next task. The human reviews the feature branch, once, at the end. |
| "The human has not reviewed yet, I'll leave the run files for them" | Clean up, then mark the pull request ready. What they need from a run is in its comment, and every removed file is still at the cleanup's starting commit. |
| "That snag sorted itself out, no need to keep it" | Keep it for the review, and file it if the loop caused it. The next feature meets it again otherwise. |
| "This flaky test is a loop bug, I'll file it" | It is the project's. File what the loop's own tools or text got wrong. |
| "I'll chain these few commands in one call" | One plain command per call, or a `loop.py` subcommand. A refused chain is a retry, and a variable or `$(…)` never survives the guard. |
| "The prompt lines say it all, the closing note is padding" | Write it. A steady word costs a line, and an agent that feels pressed costs a round. |
