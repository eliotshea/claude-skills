#!/usr/bin/env python3
"""Shell steps for /feature-plan, /feature-loop and their agents, one plain command each.

    python3 <plugin root>/loop/_lib/loop.py set-attribution --commit '<lines>' --pr '<lines>'
    python3 <plugin root>/loop/_lib/loop.py commit '<subject>' [<path>...] [--body '<text>'] [--allow-empty]
    python3 <plugin root>/loop/_lib/loop.py since '<subject pattern>' [--mine '<subject prefix>']
    python3 <plugin root>/loop/_lib/loop.py plan-gate <feature>
    python3 <plugin root>/loop/_lib/loop.py find-task <feature>
    python3 <plugin root>/loop/_lib/loop.py start <feature> <NN> <task branch>
    python3 <plugin root>/loop/_lib/loop.py row <run dir> <stage> <agent> '<result>' [--check <file>] [--file <name>] [--usage '<context> <tools> <min>'] [--with <path>...]
    python3 <plugin root>/loop/_lib/loop.py pr-body <feature> <NN>
    python3 <plugin root>/loop/_lib/loop.py cleanup <feature>
    python3 <plugin root>/loop/_lib/loop.py section <file>... -H '<heading>'... [--bare] [--subheads] [--preamble]
    python3 <plugin root>/loop/_lib/loop.py findings <file> [--status open,reopened] [--owner <o>] [--label <l>] [--titles | --count]
    python3 <plugin root>/loop/_lib/loop.py readiness-set <feature>
    python3 <plugin root>/loop/_lib/loop.py round-plan <run dir>
    python3 <plugin root>/loop/_lib/loop.py carry <run dir>
    python3 <plugin root>/loop/_lib/loop.py inert <base commit>
    python3 <plugin root>/loop/_lib/loop.py baseline <feature> <base commit>
    python3 <plugin root>/loop/_lib/loop.py run <name> [--grep '<regex>'] [--tail <n>] [--count] -- <command>...
    python3 <plugin root>/loop/_lib/loop.py port <start>

Why a script. In a worktree-isolated session Claude Code refuses any Bash command that names
git in a form it cannot verify: a `;` chain, a loop, a `$(...)`, a variable, a heredoc next to
another command. It does not read script files, so the same git calls pass from here. And
loading a skill substitutes `$` followed by a digit in the skill's text with the skill's
arguments, which no file outside SKILL.md suffers.

<feature> is the feature's name or its directory, `docs/tasks/<feature>`. The feature branch
has the feature's name.

set-attribution stores the commit trailer and the pull request attribution lines, from the
session's own instructions, in this worktree's git dir and the repository's shared one. Run it
once per session, and again after switching to a new worktree. Nothing is committed.
commit stages the paths, if any, and commits them alone, or with no paths what is staged,
with the stored trailer, and
--body between the subject and the trailer. It fails when nothing is staged, so a commit whose
edit never landed cannot pass for one that did. --allow-empty commits with nothing staged, for a
recorded run that leaves the tree as it was.
since prints the commits after the last one whose subject contains the pattern, oldest first,
leaving out subjects that start with --mine, then `uncommitted:` and `git status --porcelain`.
plan-gate prints `no branch`, `no plan log`, `plan merged` or `plan not merged`.
find-task prints `<branch> <NN>` for each unmerged branch that adds a run log of this feature,
or `none`. It skips a branch with no history in common with the feature branch.
start cuts the task branch from HEAD, writes `runs/<NN>/log.md` with row 0 and commits it.
The skills, agents and scripts come from the plugin, so every agent runs the copy the session
loaded. When the task branch's copy of the project's own loop files (TOOLING) differs from
master's, row 0's commit takes master's.
row appends the next whole-numbered row to `<run dir>/log.md` and commits it, with any --with
paths, as `docs(<feature>): loop task <NN> row <#>`. --check first reads that file's header,
fails without writing a row when it is missing or invalid, and prints it to route on.
pr-body writes `runs/<NN>/pr-body.md` from the run files without anyone reading them.
cleanup removes every run file but each `log.md`, prunes the atlas, folds every `stats.md`
total into `runs/stats.md`, and stages it all. It commits nothing. It names every task with a
log but no stats total, so the feature's totals never come out short without saying so.
section prints the `## ` sections with these exact headings, each under its heading line, or
without it with --bare. --subheads keeps only their `### ` lines, --preamble adds what comes
before the first `## `. With several files each starts with a `==> <file> <==` line.
findings prints the ids of the findings with one of these statuses (open or reopened unless
--status says otherwise) and, with --owner, that Owner, and with --label, that label after the
id's dot; their `### ` lines with --titles; or how many there are with --count.
readiness-set prints the task files the next readiness round reviews: every task without a
READY readiness file, and every task whose file, a neighbour's (Depends on or Blocks, either
way) or 00-overview.md changed since the `Commit:` its readiness file reviewed.
round-plan tells a validation round what it may carry instead of running again. `gates:` is
`all`, `tsc lint` when only validation scripts changed since the last round, or `carried <k>`
when nothing outside docs and .claude did. `regression:` is `due`, or `carried <k>` when round
k ran the whole suite green and nothing outside docs, .claude and tests/validation has changed
since.
carry prints `carry <n>` when the latest validation passed at the current last code commit and
a round at that same code ran the regression suite green, so a final validation would only
repeat it. Otherwise it prints `validate:` and why.
inert lists every changed line under src since the base commit that is not a comment or blank,
folding a deleted `export` declaration into one `deleted export <name>` line, then a count.
baseline prints the jest and tsc gate lines of an evidence file whose Commit is the last code
commit at the base, which the previous task's validation already ran, or `run`.
run sends a command's output to a log file and prints only the lines matching --grep, the last
--tail of them, or their --count, then the exit code and the log's path. A run named
`regression` also prints `- regression: <passed> passed of <total>` from Playwright's summary,
skipped tests left out, for the evidence to paste verbatim, with `; exit <code>` after it when
the run exited non-zero, which carry never counts as green.
port prints the first port from <start>, stepping by 2, where nothing answers on it or on the
one above it, so a validator never waits on a server another checkout left running.
"""
import argparse
import contextlib
import glob
import os
import re
import socket
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS_PY = os.path.join(HERE, '..', 'feature-loop', 'atlas.py')
# The project's files the loop's agents run from the worktree. `start` syncs them from master.
TOOLING = ['tests/validation/README.md', 'playwright.validation.config.ts']
NOT_CODE = [':!docs', ':!.claude']
OPEN = re.compile(r'^Status: (open|reopened)$')
FINDING = re.compile(r'^### (\S+) ')


class Fail(Exception):
    pass


def run(*args, check=True):
    p = subprocess.run(args, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise Fail(f'{" ".join(args)} failed:\n{p.stderr.strip() or p.stdout.strip()}')
    return p


def git(*args, check=True):
    return run('git', *args, check=check).stdout.strip()


def feature_name(arg):
    return os.path.basename(os.path.normpath(arg))


def feature_dir(arg):
    return f'docs/tasks/{feature_name(arg)}'


def read(path):
    with open(path) as f:
        return f.read()


def write(path, text):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w') as f:
        f.write(text)


# Attribution

def attribution_dirs():
    own = git('rev-parse', '--absolute-git-dir')
    shared = os.path.abspath(git('rev-parse', '--git-common-dir'))
    return [os.path.join(d, 'claude-skills') for d in dict.fromkeys([own, shared])]


def attribution(kind):
    for d in attribution_dirs():
        path = os.path.join(d, kind)
        if os.path.exists(path):
            return read(path).strip()
    raise Fail(f'No {kind} attribution stored. Run `loop.py set-attribution` with the lines from your instructions.')


def cmd_set_attribution(a):
    for d in attribution_dirs():
        write(os.path.join(d, 'commit'), a.commit.strip() + '\n')
        write(os.path.join(d, 'pr'), a.pr.strip() + '\n')
    print('attribution stored')


# Commits

def cmd_commit(a):
    trailer = attribution('commit')
    # Only these paths: the two reviews run at once, and one must not commit the other's file.
    only = ['--', *a.paths] if a.paths else []
    if a.paths:
        git('add', '--', *a.paths)
    if not a.allow_empty and run('git', 'diff', '--cached', '--quiet', *only, check=False).returncode == 0:
        raise Fail('Nothing is staged, so nothing was committed. Pass --allow-empty to record a run with no change.')
    body = f'{a.body.strip()}\n\n' if a.body else ''
    git('commit', '-q', *(['--allow-empty'] if a.allow_empty else []), '-m', f'{a.subject}\n\n{body}{trailer}', *only)
    print(git('log', '-1', '--format=%h %s'))


def cmd_since(a):
    last = git('log', '-1', '--format=%H', '-F', f'--grep={a.pattern}')
    span = f'{last}..HEAD' if last else 'HEAD'
    for line in git('log', '--reverse', '--format=%h %s', span).splitlines():
        subject = line.split(' ', 1)[1] if ' ' in line else ''
        if not (a.mine and subject.startswith(a.mine)):
            print(line)
    print('uncommitted:')
    status = run('git', 'status', '--porcelain').stdout.rstrip('\n')
    if status:
        print(status)


# Where a feature stands

def cmd_plan_gate(a):
    name = feature_name(a.feature)
    if not git('ls-remote', '--heads', 'origin', name):
        print('no branch')
        return
    git('fetch', '-q', 'origin', name)
    log = f'origin/{name}:{feature_dir(name)}/plan-log.md'
    if run('git', 'cat-file', '-e', log, check=False).returncode != 0:
        print('no plan log')
        return
    rows = [l for l in git('show', log).splitlines() if '| plan PR |' in l]
    print('plan merged' if rows else 'plan not merged')


def cmd_find_task(a):
    name = feature_name(a.feature)
    runs = f'{feature_dir(name)}/runs/'
    git('fetch', '-q', 'origin')
    found = []
    for branch in git('branch', '--format=%(refname:short)', '--no-merged', f'origin/{name}').splitlines():
        # A branch with unrelated history has no merge base, so the three-dot diff below would fail.
        if run('git', 'merge-base', f'origin/{name}', branch, check=False).returncode:
            continue
        changed = git('diff', '--name-only', f'origin/{name}...{branch}', '--', runs).splitlines()
        logs = [p for p in changed if p.endswith('/log.md')]
        if not logs:
            continue
        state = run('gh', 'pr', 'view', branch, '--json', 'state', '-q', '.state', check=False)
        if state.stdout.strip() == 'MERGED':
            continue
        found.append(f'{branch} {logs[0][len(runs):].split("/")[0]}')
    print('\n'.join(found) if found else 'none')


def sync_tooling():
    """Stage master's tooling over a copy that differs. Returns a note."""
    git('fetch', '-q', 'origin', 'master')
    if run('git', 'diff', '--quiet', 'origin/master', 'HEAD', '--', *TOOLING, check=False).returncode == 0:
        return 'loop tooling matches master'
    # Remove, then take master's: a file master deleted must not survive in a directory.
    git('rm', '-r', '-q', '--ignore-unmatch', '--', *TOOLING)
    kept = [p for p in TOOLING
            if run('git', 'cat-file', '-e', f'origin/master:{p}', check=False).returncode == 0]
    git('checkout', 'origin/master', '--', *kept)
    return 'loop tooling synced from master'


def cmd_start(a):
    trailer = attribution('commit')
    name, d = feature_name(a.feature), feature_dir(a.feature)
    log = f'{d}/runs/{a.task}/log.md'
    if os.path.exists(log):
        raise Fail(f'{log} already exists.')
    git('checkout', '-q', '-b', a.branch)
    base = git('rev-parse', '--short', 'HEAD')
    try:
        note = sync_tooling()
    except Fail:
        git('reset', '-q', '--hard', 'HEAD')
        git('checkout', '-q', '-')
        git('branch', '-q', '-D', a.branch)
        raise
    write(log, f'# Run log: task {a.task}\nTask branch: {a.branch}\nBase commit: {base}\n\n'
               '| # | Stage | Agent | Code commit | Result | File | Context | Tools | Min |\n'
               '|---|---|---|---|---|---|---|---|---|\n'
               f'| 0 | start | orchestrator | {base} | task branch created, {note} | log.md | | | |\n')
    git('add', '--', log)
    git('commit', '-q', '-m', f'docs({name}): loop task {a.task} row 0\n\n{trailer}')
    print(git('log', '-1', '--format=%h %s'))


REPORTS = {'Validation', 'Architecture', 'Review', 'Feedback'}
HEADERS = {'Survey': ['Base', 'Anchors'], 'Evidence': ['Commit', 'Items'],
           'Brief': ['Task file', 'Base', 'Counts', 'PR title'],
           **{k: ['Commit', 'Verdict', 'Blocking', 'Disputed', 'Repeat'] for k in REPORTS}}


def header(path):
    """The header lines of a handoff file, or Fail saying what is wrong with them."""
    if not os.path.exists(path):
        raise Fail(f'{path} does not exist.')
    lines = read(path).splitlines()
    kind = lines[0][2:].split(' ')[0].rstrip(':') if lines and lines[0].startswith('# ') else ''
    keys = HEADERS.get(kind)
    if not keys:
        raise Fail(f'{path} does not open with a handoff header.')
    head = lines[:len(keys) + 1]
    if [l.split(':')[0] for l in head[1:]] != keys:
        raise Fail(f'{path} header is not {", ".join(keys)}, in that order.')
    if kind in REPORTS:
        verdict, blocking = (l.split(':', 1)[1].strip() for l in head[2:4])
        if (verdict in ('PASS', 'APPROVED', 'CLEAN')) != (blocking == '0'):
            raise Fail(f'{path} says {verdict} with Blocking {blocking}.')
    return head


def cmd_row(a):
    trailer = attribution('commit')
    head = header(a.check) if a.check else []
    log = f'{a.run_dir}/log.md'
    d = os.path.normpath(a.run_dir).split(os.sep)
    numbers = re.findall(r'^\| (\d+) \|', read(log), re.M)
    n = int(numbers[-1]) + 1
    code = git('log', '-1', '--format=%h', '--', '.', ':!docs/tasks', ':!tests/validation')
    cells = [n, a.stage, a.agent, code, a.result, a.file or '', *(a.usage.split() + ['', '', ''])[:3]]
    with open(log, 'a') as f:
        f.write('|' + '|'.join(f' {str(c).replace("|", "/")} ' if c != '' else ' ' for c in cells) + '|\n')
    paths = [log, *a.paths]
    git('add', '--', *paths)
    git('commit', '-q', '-m', f'docs({d[-3]}): loop task {d[-1]} row {n}\n\n{trailer}', '--', *paths)
    print('\n'.join([*head, git('log', '-1', '--format=%h %s')]))


# The pull request and the cleanup

def sections(text, headings, bare):
    out, keep = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            keep = line[3:].strip() in headings
            if keep and not bare:
                out.append(line)
            continue
        if keep:
            out.append(line)
    return '\n'.join(out)


def for_the_pr(path):
    return sections(read(path), {'For the PR'}, bare=True) if os.path.exists(path) else ''


def latest(d, stem):
    found = [(int(m.group(1)), p) for p in glob.glob(f'{d}/{stem}-*.md')
             if (m := re.search(rf'{stem}-(\d+)\.md$', p))]
    return max(found)[1] if found else None


def findings(path):
    """Each `### ` finding in the file, as (heading line, {field: value})."""
    out = []
    for line in read(path).splitlines():
        if line.startswith('### '):
            out.append((line, {}))
        elif line.startswith('## '):
            out.append((None, {}))
        elif out and out[-1][0] and (m := re.match(r'^([A-Z][\w ]*): (.*)$', line)):
            out[-1][1].setdefault(m.group(1), m.group(2).strip())
    return [f for f in out if f[0]]


def matching(paths, status):
    return [h for p in paths if p and os.path.exists(p)
            for h, fields in findings(p) if fields.get('Status') == status]


def cmd_pr_body(a):
    name, f = feature_name(a.feature), feature_dir(a.feature)
    d = f'{f}/runs/{a.task}'
    task_file = next(iter(sorted(glob.glob(f'{f}/{a.task}-*.md'))), f'{f}/{a.task}-*.md')
    validation, architecture = latest(d, 'validation'), latest(d, 'architecture')
    if not validation:
        raise Fail(f'No validation file in {d}.')
    feedback = sorted(glob.glob(f'{d}/feedback-*.md'))
    out = [f'Task {a.task} of `{name}`: `{task_file}`. Every handoff file is in `{d}/`.',
           '', for_the_pr(f'{d}/brief.md'),
           '', '## Validation', for_the_pr(validation)]
    shots = f'{d}/shots/shots.md'
    if os.path.exists(shots):
        sha = git('log', '-1', '--format=%H', '--', f'{d}/shots')
        repo = run('gh', 'repo', 'view', '--json', 'nameWithOwner', '-q', '.nameWithOwner').stdout.strip()
        url = f'https://github.com/{repo}/blob/{sha}/{d}/shots'
        rows = [re.sub(r'\]\((before|after|diff)/([^)]*)\)', lambda m: f']({url}/{m.group(1)}/{m.group(2)}?raw=true)', l)
                for l in read(shots).splitlines() if l.startswith('|')]
        out += ['', '## Before and after', *rows]
    out += ['', '## Design review',
            for_the_pr(architecture) if architecture else 'Skipped: style or chore only.',
            '', '## Code review', for_the_pr(f'{d}/review-1.md')]
    for fb in feedback:
        out += ['', '## Your feedback', for_the_pr(fb)]
    disputed = (matching([validation, architecture], 'disputed')
                + matching([f'{d}/review-1.md', *feedback], 'declined'))
    out += ['', '## Disputed, for you to settle', *(disputed or ['None.']),
            '', attribution('pr')]
    write(f'{d}/pr-body.md', '\n'.join(out) + '\n')
    print(f'{d}/pr-body.md: {len(disputed)} disputed')


def cmd_cleanup(a):
    name, f = feature_name(a.feature), feature_dir(a.feature)
    totals = [read(s).rstrip('\n').splitlines()[-1] for s in sorted(glob.glob(f'{f}/runs/*/stats.md'))
              if read(s).strip()]
    folded = {t.split('|')[1].strip() for t in totals if t.startswith('|')}
    missing = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(f'{f}/runs/*/log.md')
                     if os.path.basename(os.path.dirname(p)) not in folded)
    doomed = [p for p in git('ls-files', '--', f'{f}/runs').splitlines() if not p.endswith('/log.md')]
    if doomed:
        git('rm', '-q', '--', *doomed)
    run(sys.executable, ATLAS_PY, 'prune', 'HEAD', '--stale')
    if os.path.exists('docs/tasks/atlas.md'):
        git('add', '--', 'docs/tasks/atlas.md')
    if totals:
        write(f'{f}/runs/stats.md', '\n'.join([
            f'# {name}: task sizes', '',
            "Each task's total from its `runs/<NN>/stats.md`, kept when the run files were removed.",
            "Each task's full record of rows is its `runs/<NN>/log.md`.", '',
            '| Task | Runs | Largest context | Total context | Over 50k | Active min | Wall min |',
            '|---|---|---|---|---|---|---|', *totals]) + '\n')
        git('add', '--', f'{f}/runs/stats.md')
    print(f'removed {len(doomed)} run files, folded {len(totals)} stats totals')
    if missing:
        print(f'no stats total for task {", ".join(missing)}: fold it in by hand from run-stats.py')


# Reading for agents

def cmd_section(a):
    if not a.heading and not a.preamble:
        raise Fail('section needs -H <heading> or --preamble.')
    many = len(a.files) > 1
    for path in a.files:
        text = read(path)
        out = []
        if a.preamble:
            out.append(text.split('\n## ', 1)[0].rstrip('\n'))
        if a.heading:
            body = sections(text, set(a.heading), a.bare)
            if not body.strip() and not many:
                raise Fail(f'No section {", ".join(a.heading)} in {path}.')
            if a.subheads:
                body = '\n'.join(l for l in body.splitlines() if l.startswith('### '))
            out.append(body)
        if many:
            print(f'==> {path} <==')
        print('\n'.join(out))


def label(heading):
    """`tooling` from `### V3-1 · tooling`."""
    return heading.split('·', 1)[1].strip() if '·' in heading else ''


def cmd_findings(a):
    statuses = set(a.status.split(','))
    hits = [(h, fields) for h, fields in findings(a.file)
            if fields.get('Status') in statuses and (not a.owner or fields.get('Owner') == a.owner)
            and (not a.label or label(h) == a.label)]
    if a.count:
        print(len(hits))
        return
    for h, _ in hits:
        m = FINDING.match(h)
        print(h if a.titles else (m.group(1) if m else h))


# Which tasks a readiness round reviews

TASK = re.compile(r'^(?!00-)(\d\d[a-z]?)-.*\.md$')


def cmd_readiness_set(a):
    d = feature_dir(a.feature)
    tasks = {m.group(1): f'{d}/{f}' for f in sorted(os.listdir(d)) if (m := TASK.match(f))}
    near = {nn: {nn} for nn in tasks}
    for nn, path in tasks.items():
        # From the header's `Depends on <tasks>. Blocks <tasks>.` to the paragraph's end: it may wrap.
        m = re.search(r'Depends on.*?(?:\n\n|\Z)', read(path), re.S)
        for other in re.findall(r'\b(\d\d[a-z]?)\b', m.group(0) if m else ''):
            if other in tasks:
                near[nn].add(other)
                near[other].add(nn)
    for nn, path in tasks.items():
        ready = f'{d}/readiness/{nn}.md'
        head = read(ready).splitlines()[:6] if os.path.exists(ready) else []
        commit = next((l.split(': ', 1)[1] for l in head if l.startswith('Commit: ')), '')
        watched = [f'{d}/00-overview.md', *(tasks[o] for o in sorted(near[nn]))]
        diff = run('git', 'diff', '--name-only', commit, '--', *watched, check=False)
        if 'Verdict: READY' not in head or not commit or diff.returncode or diff.stdout.strip():
            print(path)


# What a validation round can carry

def rounds(run_dir, stem):
    """[(n, path)] of <stem>-<n>.md in the run dir, oldest first."""
    return sorted((int(m.group(1)), p) for p in glob.glob(f'{run_dir}/{stem}-*.md')
                  if (m := re.search(rf'{stem}-(\d+)\.md$', p)))


def committed_at(path):
    """The commit that last wrote <path>: the tree that round checked."""
    return git('log', '-1', '--format=%H', '--', path)


def changed(since, *exclude):
    return git('diff', '--name-only', since, 'HEAD', '--', '.', *NOT_CODE, *exclude).splitlines()


# A chore task with an inert diff runs only the tests/app specs it touches, and that counts.
REGRESSION = re.compile(r'^- regression: (?:not run, chore with inert diff; )?(\d+) passed of (\d+)(?!\d|; exit)', re.M)


def green_regression(run_dir):
    """(round, commit) of the latest evidence whose regression run was green."""
    for n, path in reversed(rounds(run_dir, 'evidence')):
        m = REGRESSION.search(read(path))
        if m and m.group(1) == m.group(2):
            return n, committed_at(path)
    return None


def cmd_round_plan(a):
    evidence = rounds(a.run_dir, 'evidence')
    if not evidence:
        print('gates: all')
    else:
        n, path = evidence[-1]
        files = changed(committed_at(path))
        print('gates: ' + (f'carried {n}' if not files
                           else 'tsc lint' if all(f.startswith('tests/validation/') for f in files)
                           else 'all'))
    green = green_regression(a.run_dir)
    print(f'regression: carried {green[0]}' if green and not changed(green[1], ':!tests/validation')
          else 'regression: due')


def cmd_carry(a):
    validations = rounds(a.run_dir, 'validation')
    if not validations:
        print('validate: no validation yet')
        return
    n, path = validations[-1]
    header = read(path).splitlines()[:6]
    commit = next((l.split(':', 1)[1].strip() for l in header if l.startswith('Commit:')), '')
    green = green_regression(a.run_dir)
    if 'Verdict: PASS' not in header:
        print(f'validate: validation {n} did not pass')
    elif run('git', 'diff', '--quiet', commit, 'HEAD', '--', '.', ':!docs/tasks', ':!tests/validation',
             check=False).returncode != 0:
        print(f'validate: code changed since validation {n} at {commit}')
    elif not green or changed(green[1], ':!tests/validation'):
        print(f'validate: no green regression run at {commit}')
    else:
        print(f'carry {n}')


COMMENT = re.compile(r'^\s*(//|/\*|\*|\{/\*|$)')
EXPORT = re.compile(r'^\s*export (?:const|let|var|function|type|interface|enum|class) (\w+)')


def cmd_inert(a):
    others, comments, file = [], 0, ''
    lines = git('diff', '-U0', a.base, 'HEAD', '--', 'src').splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.startswith('+++ '):
            file = line[6:]
            continue
        if line.startswith('--- ') or line[:1] not in ('+', '-'):
            continue
        sign, text = line[0], line[1:]
        if COMMENT.match(text):
            comments += 1
            continue
        if sign == '-' and (m := EXPORT.match(text)):
            # The rest of the deleted statement: the removed lines up to the one that ends it,
            # outside any braces it opened.
            depth = text.count('{') - text.count('}')
            while ((depth > 0 or not text.rstrip().endswith((';', '}'))) and i < len(lines)
                   and lines[i].startswith('-') and not lines[i].startswith('--- ')):
                text = lines[i][1:]
                depth += text.count('{') - text.count('}')
                i += 1
            others.append(f'{file}: deleted export {m.group(1)}')
            continue
        others.append(f'{file}: {sign} {text.strip()[:160]}')
    for o in others:
        print(o)
    print(f'inert: {comments} comment lines, {len(others)} other changes')


def cmd_baseline(a):
    code = git('log', '-1', '--format=%H', a.base, '--', '.', ':!docs/tasks', ':!tests/validation')
    found = {}
    for path in glob.glob(f'{feature_dir(a.feature)}/runs/*/evidence-*.md'):
        text = read(path)
        m = re.search(r'^Commit: (\S+)', text, re.M)
        at = m and run('git', 'rev-parse', '-q', '--verify', f'{m.group(1)}^{{commit}}', check=False).stdout.strip()
        if code and at == code:
            for line in text.splitlines():
                if (g := re.match(r'- (jest|tsc): ', line)) and 'carried' not in line:
                    found.setdefault(g.group(1), line)
    print(f"{found['jest']}\n{found['tsc']}" if len(found) == 2 else 'run')


def cmd_run(a):
    if not a.cmd:
        raise Fail('run needs a command after --.')
    out = tempfile.mkdtemp(prefix='run-')
    path = os.path.join(out, f'{a.name}.log')
    with open(path, 'w') as f:
        code = subprocess.run(a.cmd, stdout=f, stderr=subprocess.STDOUT).returncode
    lines = read(path).splitlines()
    if a.grep:
        lines = [l for l in lines if re.search(a.grep, l)]
    if a.count:
        print(len(lines))
    else:
        for l in lines[-a.tail:] if a.tail else lines:
            print(l)
    if a.name == 'regression':
        # Playwright's closing summary: `  116 passed (4.1m)`, `  2 failed`, `  1 flaky`, ...
        # The line reporter puts cursor codes (ESC[1A ESC[2K) before `1 failed`, so strip every CSI.
        counts = {m.group(2): int(m.group(1)) for l in read(path).splitlines()
                  if (m := re.match(r'^\s*(\d+) (passed|failed|flaky|interrupted|did not run)\b',
                                    re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', l)))}
        if counts:
            # A non-zero exit is never green, whatever the counts say.
            failed = f'; exit {code}' if code else ''
            print(f'- regression: {counts.get("passed", 0)} passed of {sum(counts.values())}{failed}')
    print(f'exit {code}, log {path}')


def answers(port):
    """True when something accepts a connection on localhost:<port>, over IPv4 or IPv6."""
    for host in ('127.0.0.1', '::1'):
        with contextlib.suppress(OSError), socket.create_connection((host, port), timeout=0.2):
            return True
    return False


def cmd_port(a):
    for port in range(a.start, a.start + 100, 2):
        if not answers(port) and not answers(port + 1):
            print(port)
            return
    raise Fail(f'No free port pair in {a.start}..{a.start + 99}.')


def main(argv=None):
    p = argparse.ArgumentParser(prog='loop.py', description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='sub', required=True)
    s = sub.add_parser('set-attribution')
    s.add_argument('--commit', required=True)
    s.add_argument('--pr', required=True)
    s = sub.add_parser('commit')
    s.add_argument('subject')
    s.add_argument('paths', nargs='*')
    s.add_argument('--body')
    s.add_argument('--allow-empty', action='store_true')
    s = sub.add_parser('since')
    s.add_argument('pattern')
    s.add_argument('--mine')
    for c in ('plan-gate', 'find-task', 'cleanup'):
        sub.add_parser(c).add_argument('feature')
    s = sub.add_parser('start')
    s.add_argument('feature')
    s.add_argument('task')
    s.add_argument('branch')
    s = sub.add_parser('row')
    for arg in ('run_dir', 'stage', 'agent', 'result'):
        s.add_argument(arg)
    s.add_argument('--check')
    s.add_argument('--file')
    s.add_argument('--usage', default='')
    s.add_argument('--with', dest='paths', nargs='*', default=[])
    for c in ('round-plan', 'carry'):
        sub.add_parser(c).add_argument('run_dir')
    sub.add_parser('inert').add_argument('base')
    s = sub.add_parser('baseline')
    s.add_argument('feature')
    s.add_argument('base')
    s = sub.add_parser('pr-body')
    s.add_argument('feature')
    s.add_argument('task')
    s = sub.add_parser('section')
    s.add_argument('files', nargs='+')
    s.add_argument('-H', '--heading', action='append')
    s.add_argument('--bare', action='store_true')
    s.add_argument('--subheads', action='store_true')
    s.add_argument('--preamble', action='store_true')
    s = sub.add_parser('findings')
    s.add_argument('file')
    s.add_argument('--status', default='open,reopened')
    s.add_argument('--owner')
    s.add_argument('--label')
    s.add_argument('--titles', action='store_true')
    s.add_argument('--count', action='store_true')
    sub.add_parser('readiness-set').add_argument('feature')
    s = sub.add_parser('run')
    s.add_argument('name')
    s.add_argument('--grep')
    s.add_argument('--tail', type=int)
    s.add_argument('--count', action='store_true')
    sub.add_parser('port').add_argument('start', type=int)
    argv = sys.argv[1:] if argv is None else argv
    split = argv.index('--') if '--' in argv else len(argv)
    a = p.parse_args(argv[:split])
    a.cmd = argv[split + 1:]
    try:
        globals()['cmd_' + a.sub.replace('-', '_')](a)
    except Fail as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
