"""loop.py, driven as the skills drive it: one subprocess per call, in a throwaway repo."""
import os
import subprocess
import sys
import textwrap

import pytest

LOOP = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '_lib', 'loop.py'))
FEATURE = 'feat-x'
TRAILER = 'Co-Authored-By: Test Model <noreply@example.com>'
PR_LINES = 'Generated in a test'


def sh(cwd, *args, check=True):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode:
        raise AssertionError(f'{args} failed: {p.stderr}{p.stdout}')
    return p.stdout.strip()


def git(cwd, *args):
    return sh(cwd, 'git', *args)


def write(root, path, text):
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w') as f:
        f.write(textwrap.dedent(text))


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A clone of a bare origin with master and the feature branch, a fake gh on PATH."""
    origin, work, bin_dir = tmp_path / 'origin.git', tmp_path / 'work', tmp_path / 'bin'
    subprocess.run(['git', 'init', '-q', '--bare', '-b', 'master', str(origin)], check=True)
    subprocess.run(['git', 'clone', '-q', str(origin), str(work)], check=True, capture_output=True)
    for k, v in (('user.name', 'T'), ('user.email', 't@example.com'), ('commit.gpgsign', 'false')):
        git(work, 'config', k, v)
    write(work, 'README.md', 'x\n')
    write(work, 'docs/tasks/atlas.md', '# Atlas\n')
    write(work, 'playwright.validation.config.ts', 'master copy\n')
    git(work, 'add', '.')
    git(work, 'commit', '-q', '-m', 'init')
    git(work, 'push', '-q', 'origin', 'master')
    git(work, 'checkout', '-q', '-b', FEATURE)
    git(work, 'push', '-q', '-u', 'origin', FEATURE)
    bin_dir.mkdir()
    gh = bin_dir / 'gh'
    gh.write_text('#!/bin/sh\n'
                  'case "$1 $2" in\n'
                  '  "pr view") echo "${FAKE_GH_STATE:-OPEN}" ;;\n'
                  '  "repo view") echo owner/repo ;;\n'
                  'esac\n')
    gh.chmod(0o755)
    monkeypatch.setenv('PATH', f'{bin_dir}{os.pathsep}{os.environ["PATH"]}')
    return work


def loop(cwd, *args, check=True):
    p = subprocess.run([sys.executable, LOOP, *args], cwd=cwd, capture_output=True, text=True)
    if check and p.returncode:
        raise AssertionError(f'loop.py {args} exited {p.returncode}: {p.stderr}')
    return p


def attributed(repo):
    loop(repo, 'set-attribution', '--commit', TRAILER, '--pr', PR_LINES)


# set-attribution and commit

def test_commit_refuses_without_attribution(repo):
    write(repo, 'a.txt', 'a\n')
    p = loop(repo, 'commit', 'docs: a', 'a.txt', check=False)
    assert p.returncode == 1
    assert 'set-attribution' in p.stderr


def test_commit_stages_paths_and_appends_trailer(repo):
    attributed(repo)
    write(repo, 'a.txt', 'a\n')
    out = loop(repo, 'commit', 'docs(feat-x): loop task 01 row 3', 'a.txt').stdout
    assert out.endswith('docs(feat-x): loop task 01 row 3\n')
    assert git(repo, 'log', '-1', '--format=%B') == f'docs(feat-x): loop task 01 row 3\n\n{TRAILER}'
    assert git(repo, 'status', '--porcelain') == ''


def test_commit_without_paths_commits_what_is_staged(repo):
    attributed(repo)
    write(repo, 'a.txt', 'a\n')
    write(repo, 'b.txt', 'b\n')
    git(repo, 'add', 'a.txt')
    loop(repo, 'commit', 'docs: staged only')
    assert git(repo, 'show', '--name-only', '--format=', 'HEAD') == 'a.txt'
    assert git(repo, 'status', '--porcelain') == '?? b.txt'


def test_commit_with_paths_leaves_another_agents_staged_file(repo):
    attributed(repo)
    write(repo, 'review-1.md', 'r\n')
    git(repo, 'add', 'review-1.md')
    write(repo, 'architecture-1.md', 'a\n')
    loop(repo, 'commit', 'docs: design review', 'architecture-1.md')
    assert git(repo, 'show', '--name-only', '--format=', 'HEAD') == 'architecture-1.md'
    loop(repo, 'commit', 'docs: code review', 'review-1.md')
    assert git(repo, 'show', '--name-only', '--format=', 'HEAD') == 'review-1.md'


def test_commit_fails_when_nothing_is_staged(repo):
    attributed(repo)
    head = git(repo, 'rev-parse', 'HEAD')
    p = loop(repo, 'commit', 'docs: nothing', 'README.md', check=False)
    assert p.returncode == 1
    assert 'Nothing is staged' in p.stderr
    assert git(repo, 'rev-parse', 'HEAD') == head


def test_commit_allow_empty_records_a_run_with_nothing_staged(repo):
    attributed(repo)
    loop(repo, 'commit', 'test: red run', '--allow-empty', '--body', 'red: 1 failed')
    assert git(repo, 'log', '-1', '--format=%B') == f'test: red run\n\nred: 1 failed\n\n{TRAILER}'
    assert git(repo, 'show', '--name-only', '--format=', 'HEAD') == ''


def test_attribution_is_shared_with_a_new_worktree(repo, tmp_path):
    attributed(repo)
    other = tmp_path / 'other'
    git(repo, 'worktree', 'add', '-q', '-b', 'side', str(other))
    write(other, 'c.txt', 'c\n')
    loop(other, 'commit', 'docs: from the worktree', 'c.txt')
    assert git(other, 'log', '-1', '--format=%b') == TRAILER


def test_a_worktree_attribution_wins_over_the_shared_one(repo, tmp_path):
    attributed(repo)
    other = tmp_path / 'other'
    git(repo, 'worktree', 'add', '-q', '-b', 'side', str(other))
    loop(other, 'set-attribution', '--commit', 'Co-Authored-By: Newer', '--pr', 'x')
    write(repo, 'd.txt', 'd\n')
    loop(repo, 'commit', 'docs: main checkout', 'd.txt')
    assert git(repo, 'log', '-1', '--format=%b') == 'Co-Authored-By: Newer'


# since

def test_since_lists_later_commits_oldest_first_without_mine(repo):
    attributed(repo)
    for subject, name in (('docs(feat-x): loop task 01 row 4', 'r4'), ('feat: one', 'f1'),
                          ('docs(feat-x): loop task 01 design review', 'own'), ('fix: two', 'f2')):
        write(repo, name, name)
        loop(repo, 'commit', subject, name)
    write(repo, 'README.md', 'changed\n')
    write(repo, 'loose.txt', 'x')
    out = loop(repo, 'since', 'loop task 01 row', '--mine', 'docs(feat-x): loop task 01 row').stdout
    lines = out.splitlines()
    assert [l.split(' ', 1)[1] for l in lines[:3]] == ['feat: one', 'docs(feat-x): loop task 01 design review', 'fix: two']
    assert lines[3:] == ['uncommitted:', ' M README.md', '?? loose.txt']


def test_since_with_no_matching_commit_lists_all_history(repo):
    out = loop(repo, 'since', 'plan row').stdout.splitlines()
    assert out[0].endswith(' init') and out[-1] == 'uncommitted:'


# plan-gate

def test_plan_gate(repo):
    assert loop(repo, 'plan-gate', 'docs/tasks/nope').stdout.strip() == 'no branch'
    assert loop(repo, 'plan-gate', f'docs/tasks/{FEATURE}').stdout.strip() == 'no plan log'
    write(repo, f'docs/tasks/{FEATURE}/plan-log.md', '| 1 | tasks | router | cut |\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-q', '-m', 'log')
    git(repo, 'push', '-q')
    assert loop(repo, 'plan-gate', FEATURE).stdout.strip() == 'plan not merged'
    write(repo, f'docs/tasks/{FEATURE}/plan-log.md', '| 1 | tasks | router | cut |\n| 9 | plan PR | router | plan PR #3 |\n')
    git(repo, 'commit', '-q', '-am', 'row')
    git(repo, 'push', '-q')
    assert loop(repo, 'plan-gate', FEATURE).stdout.strip() == 'plan merged'


# start and find-task

def test_start_cuts_branch_and_commits_row_0(repo):
    attributed(repo)
    base = git(repo, 'rev-parse', '--short', 'HEAD')
    loop(repo, 'start', f'docs/tasks/{FEATURE}', '02', f'{FEATURE}-task-02')
    assert git(repo, 'branch', '--show-current') == f'{FEATURE}-task-02'
    assert git(repo, 'log', '-1', '--format=%B') == f'docs({FEATURE}): loop task 02 row 0\n\n{TRAILER}'
    log = open(os.path.join(repo, f'docs/tasks/{FEATURE}/runs/02/log.md')).read()
    assert log.startswith(f'# Run log: task 02\nTask branch: {FEATURE}-task-02\nBase commit: {base}\n')
    assert log.endswith(f'| 0 | start | orchestrator | {base} | task branch created, loop tooling matches master | log.md | | | |\n')


def test_row_checks_the_header_then_appends_and_commits(repo):
    attributed(repo)
    run_dir = f'docs/tasks/{FEATURE}/runs/02'
    loop(repo, 'start', f'docs/tasks/{FEATURE}', '02', f'{FEATURE}-task-02')
    base = git(repo, 'rev-parse', '--short', 'origin/master')
    write(repo, f'{run_dir}/validation-1.md',
          '# Validation 1: task 02\nCommit: x\nVerdict: PASS\nBlocking: 2\nDisputed: 0\nRepeat: none\n')
    bad = loop(repo, 'row', run_dir, 'validation 1 report', 'validation-reporter', 'PASS',
               '--check', f'{run_dir}/validation-1.md', check=False)
    assert bad.returncode == 1 and 'PASS with Blocking 2' in bad.stderr
    write(repo, f'{run_dir}/validation-1.md',
          '# Validation 1: task 02\nCommit: x\nVerdict: BLOCKED\nBlocking: 2\nDisputed: 0\nRepeat: none\n')
    out = loop(repo, 'row', run_dir, 'validation 1 report', 'validation-reporter', 'BLOCKED, 2 blocking',
               '--check', f'{run_dir}/validation-1.md', '--file', 'validation-1.md', '--usage', '34k 9 2').stdout
    assert out.startswith('# Validation 1: task 02\nCommit: x\nVerdict: BLOCKED\n')
    assert out.endswith(f'docs({FEATURE}): loop task 02 row 1\n')
    log = open(os.path.join(repo, f'{run_dir}/log.md')).read()
    assert log.endswith(f'| 1 | validation 1 report | validation-reporter | {base} | BLOCKED, 2 blocking | validation-1.md | 34k | 9 | 2 |\n')
    assert log.count('\n| ') == 3  # the refused row was never written
    loop(repo, 'row', run_dir, 'escalated', 'orchestrator', 'cap reached')
    assert open(os.path.join(repo, f'{run_dir}/log.md')).read().endswith('| 2 | escalated | orchestrator | ' + base + ' | cap reached | | | | |\n')
    assert git(repo, 'status', '--porcelain') == '?? ' + f'{run_dir}/validation-1.md'


def test_start_syncs_tooling_that_differs_from_master(repo):
    attributed(repo)
    write(repo, 'tests/validation/README.md', 'gone on master\n')
    write(repo, 'playwright.validation.config.ts', 'branch copy\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-q', '-m', 'branch tooling')
    loop(repo, 'start', FEATURE, '02', f'{FEATURE}-task-02')
    assert 'task branch created, loop tooling synced from master |' in open(
        os.path.join(repo, f'docs/tasks/{FEATURE}/runs/02/log.md')).read()
    assert git(repo, 'diff', 'origin/master', 'HEAD', '--stat', '--', 'tests', 'playwright.validation.config.ts') == ''
    assert not os.path.exists(os.path.join(repo, 'tests/validation/README.md'))


def test_start_refuses_an_existing_log(repo):
    attributed(repo)
    loop(repo, 'start', FEATURE, '02', 'b1')
    p = loop(repo, 'start', FEATURE, '02', 'b2', check=False)
    assert p.returncode == 1 and 'already exists' in p.stderr


def test_find_task(repo, monkeypatch):
    attributed(repo)
    assert loop(repo, 'find-task', FEATURE).stdout.strip() == 'none'
    loop(repo, 'start', FEATURE, '03', f'{FEATURE}-task-03')
    git(repo, 'checkout', '-q', FEATURE)
    git(repo, 'checkout', '-q', '-b', 'unrelated')
    write(repo, 'u.txt', 'u')
    loop(repo, 'commit', 'feat: unrelated', 'u.txt')
    assert loop(repo, 'find-task', FEATURE).stdout.strip() == f'{FEATURE}-task-03 03'
    git(repo, 'checkout', '-q', '--orphan', 'no-history')
    loop(repo, 'commit', 'chore: orphan')
    assert loop(repo, 'find-task', FEATURE).stdout.strip() == f'{FEATURE}-task-03 03'
    monkeypatch.setenv('FAKE_GH_STATE', 'MERGED')
    assert loop(repo, 'find-task', FEATURE).stdout.strip() == 'none'


# pr-body

RUN = f'docs/tasks/{FEATURE}/runs/04'


def report(kind, n, body):
    return f'# {kind} {n}: task 04\nCommit: abc\nVerdict: X\nBlocking: 0\nDisputed: 0\nRepeat: none\n\n{body}'


def test_pr_body_stitches_the_latest_files(repo):
    attributed(repo)
    write(repo, f'docs/tasks/{FEATURE}/04-thing.md', '# Thing\n')
    write(repo, f'{RUN}/brief.md', 'PR title: x\n\n## For the PR\nBrief says hi.\n\n## Traps\nsecret\n')
    write(repo, f'{RUN}/validation-1.md', report('Validation', 1, '## For the PR\nOld round.\n'))
    write(repo, f'{RUN}/validation-10.md', report('Validation', 10, '## For the PR\nRound ten.\n\n## Findings\n### V10-1 · c2\nStatus: disputed\n'))
    write(repo, f'{RUN}/architecture-2.md', report('Architecture', 2, '## For the PR\nLooks deep.\n'))
    write(repo, f'{RUN}/review-1.md', report('Review', 1, '## For the PR\nTwo nits.\n### R1-1 · nit\nStatus: declined\n'))
    write(repo, f'{RUN}/feedback-1.md', report('Feedback', 1, '## For the PR\nOne point.\n'))
    out = loop(repo, 'pr-body', FEATURE, '04').stdout
    assert '2 disputed' in out
    body = open(os.path.join(repo, f'{RUN}/pr-body.md')).read()
    assert body.startswith(f'Task 04 of `{FEATURE}`: `docs/tasks/{FEATURE}/04-thing.md`.')
    for text in ('Brief says hi.', '## Validation\nRound ten.', '## Design review\nLooks deep.',
                 '## Code review\nTwo nits.', '## Your feedback\nOne point.',
                 '## Disputed, for you to settle\n### V10-1 · c2\n### R1-1 · nit\n'):
        assert text in body
    assert 'Old round.' not in body and 'secret' not in body
    assert body.endswith(f'{PR_LINES}\n')


def test_pr_body_style_only_shots_and_no_disputes(repo):
    attributed(repo)
    write(repo, f'{RUN}/brief.md', '## For the PR\nB\n')
    write(repo, f'{RUN}/validation-1.md', report('Validation', 1, '## For the PR\nV\n'))
    write(repo, f'{RUN}/review-1.md', report('Review', 1, '## For the PR\nR\n'))
    write(repo, f'{RUN}/shots/shots.md', '# Shots\n| c1 | ![b](before/a.png) | ![a](after/a.png) |\n')
    loop(repo, 'commit', 'docs: shots', f'{RUN}/shots')
    sha = git(repo, 'rev-parse', 'HEAD')
    loop(repo, 'pr-body', FEATURE, '04')
    body = open(os.path.join(repo, f'{RUN}/pr-body.md')).read()
    assert '## Design review\nSkipped: style or chore only.' in body
    assert '## Disputed, for you to settle\nNone.' in body
    url = f'https://github.com/owner/repo/blob/{sha}/{RUN}/shots'
    assert f'| c1 | ![b]({url}/before/a.png?raw=true) | ![a]({url}/after/a.png?raw=true) |' in body


def test_pr_body_needs_a_validation(repo):
    attributed(repo)
    write(repo, f'{RUN}/brief.md', '## For the PR\nB\n')
    assert loop(repo, 'pr-body', FEATURE, '04', check=False).returncode == 1


# cleanup

def test_cleanup_keeps_logs_and_folds_stats(repo):
    attributed(repo)
    f = f'docs/tasks/{FEATURE}'
    write(repo, f'{f}/01-a.md', 'task\n')
    write(repo, f'{f}/runs/01/log.md', 'log 1\n')
    write(repo, f'{f}/runs/01/brief.md', 'brief\n')
    write(repo, f'{f}/runs/01/stats.md', 'header\n| 01 | 9 | 40k | 200k | 0 | 30 | 50 |\n')
    write(repo, f'{f}/runs/02/log.md', 'log 2\n')
    write(repo, f'{f}/runs/02/shots/before/x.png', 'png')
    loop(repo, 'commit', 'docs: runs', f)
    out = loop(repo, 'cleanup', f).stdout
    assert 'removed 3 run files, folded 1 stats totals' in out
    assert 'no stats total for task 02' in out
    staged = git(repo, 'diff', '--cached', '--name-status').splitlines()
    assert sorted(staged) == sorted([f'D\t{f}/runs/01/brief.md', f'D\t{f}/runs/01/stats.md',
                                     f'A\t{f}/runs/stats.md', f'D\t{f}/runs/02/shots/before/x.png'])
    stats = open(os.path.join(repo, f'{f}/runs/stats.md')).read()
    assert stats.startswith(f'# {FEATURE}: task sizes\n')
    assert stats.endswith('|---|---|---|---|---|---|---|\n| 01 | 9 | 40k | 200k | 0 | 30 | 50 |\n')


# section and ids

BRIEF = """\
    # Brief
    PR title: x

    ## Allowed diff surface
    src/a.ts

    ## Files to change
    ### src/a.ts
    change it
    ### src/b.ts
    and this

    ## Traps
    none
    """


def test_section_prints_named_sections_with_headings(repo):
    write(repo, 'brief.md', BRIEF)
    out = loop(repo, 'section', 'brief.md', '-H', 'Traps', '-H', 'Allowed diff surface').stdout
    assert out == '## Allowed diff surface\nsrc/a.ts\n\n## Traps\nnone\n'


def test_section_bare_drops_the_heading(repo):
    write(repo, 'brief.md', BRIEF)
    out = loop(repo, 'section', 'brief.md', '-H', 'Files to change', '--bare').stdout
    assert out.splitlines()[0] == '### src/a.ts'
    assert '## Files' not in out


def test_section_subheads_keeps_only_the_file_headings(repo):
    write(repo, 'brief.md', BRIEF)
    out = loop(repo, 'section', 'brief.md', '-H', 'Files to change', '--subheads').stdout
    assert out == '### src/a.ts\n### src/b.ts\n'


def test_section_fails_on_a_missing_heading(repo):
    write(repo, 'brief.md', BRIEF)
    p = loop(repo, 'section', 'brief.md', '-H', 'Nope', check=False)
    assert p.returncode == 1 and 'No section Nope' in p.stderr


def test_section_needs_a_heading_or_preamble(repo):
    write(repo, 'brief.md', BRIEF)
    assert loop(repo, 'section', 'brief.md', check=False).returncode == 1


def test_section_over_several_files_with_preamble(repo):
    write(repo, 'tasks/01-a.md', '# Task 01\nDepends on: none\n\n## Why\nbecause\n\n## Where the code is\nsrc/a.ts\n')
    write(repo, 'tasks/02-b.md', '# Task 02\nDepends on: 01\n\n## Why\nso\n')
    out = loop(repo, 'section', 'tasks/01-a.md', 'tasks/02-b.md', '--preamble', '-H', 'Where the code is').stdout
    assert out == ('==> tasks/01-a.md <==\n# Task 01\nDepends on: none\n## Where the code is\nsrc/a.ts\n'
                   '==> tasks/02-b.md <==\n# Task 02\nDepends on: 01\n\n')


FINDINGS = """\
    # Validation 2: task 04
    ### V2-1 · criterion 1
    Status: fixed
    ### V2-2 · criterion 3
    Evidence: it broke
    Status: open
    Owner: cutter
    ### V1-4 · criterion 2
    Status: reopened
    Owner: human
    ### V2-3 · nit
    Status: disputed

    ## Notes
    Status: open
    """


def test_findings_ids_and_titles_in_file_order(repo):
    write(repo, 'v.md', FINDINGS)
    assert loop(repo, 'findings', 'v.md').stdout == 'V2-2\nV1-4\n'
    assert loop(repo, 'findings', 'v.md', '--titles').stdout == '### V2-2 · criterion 3\n### V1-4 · criterion 2\n'


def test_findings_counts_by_status_and_owner(repo):
    write(repo, 'v.md', FINDINGS)
    assert loop(repo, 'findings', 'v.md', '--count').stdout == '2\n'
    assert loop(repo, 'findings', 'v.md', '--owner', 'human', '--count').stdout == '1\n'
    assert loop(repo, 'findings', 'v.md', '--status', 'disputed').stdout == 'V2-3\n'


# readiness-set

def readiness(repo, nn, verdict, commit):
    write(repo, f'docs/tasks/{FEATURE}/readiness/{nn}.md',
          f'# Readiness 1: task {nn}\nCommit: {commit}\nVerdict: {verdict}\n'
          'Blocking: 0\nOwner: 0\nRepeat: none\n')


def test_readiness_set_reviews_changed_tasks_their_neighbours_and_the_unready(repo):
    d = f'docs/tasks/{FEATURE}'
    write(repo, f'{d}/00-overview.md', '# Overview\n')
    write(repo, f'{d}/01-a.md', '# Task 01: A\n\nPlan slice 1. Depends on none. Blocks 02.\n')
    write(repo, f'{d}/02-b.md', '# Task 02: B\n\nPlan slice 1. Depends on 01.\nBlocks none.\n')
    write(repo, f'{d}/03-c.md', '# Task 03: C\n\nPlan slice 2. Depends on none. Blocks none.\n')
    write(repo, f'{d}/04-d.md', '# Task 04: D\n\nPlan slice 12. Depends on none. Blocks none.\n')
    write(repo, f'{d}/11b-e.md', '# Task 11b: E\n\nPlan slice 3. Depends on none. Blocks none.\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-q', '-m', 'cut')
    reviewed = git(repo, 'rev-parse', '--short', 'HEAD')
    for nn in ('01', '02', '03', '04'):
        readiness(repo, nn, 'READY', reviewed)
    readiness(repo, '11b', 'BLOCKED', reviewed)
    git(repo, 'add', '.')
    git(repo, 'commit', '-q', '-m', 'readiness 1')
    assert loop(repo, 'readiness-set', FEATURE).stdout == f'{d}/11b-e.md\n'

    write(repo, f'{d}/02-b.md', '# Task 02: B\n\nPlan slice 1. Depends on 01.\nBlocks none. Fixed.\n')
    git(repo, 'commit', '-qam', 'fix')
    assert loop(repo, 'readiness-set', FEATURE).stdout == f'{d}/01-a.md\n{d}/02-b.md\n{d}/11b-e.md\n'

    write(repo, f'{d}/00-overview.md', '# Overview, fixed\n')
    assert len(loop(repo, 'readiness-set', FEATURE).stdout.splitlines()) == 5


# run

def test_run_filters_its_log_and_reports_the_exit(repo):
    p = loop(repo, 'run', 'demo', '--grep', '^keep', '--', sys.executable, '-c',
             'import sys; print("keep 1"); print("drop"); print("keep 2"); sys.exit(3)')
    lines = p.stdout.splitlines()
    assert lines[:2] == ['keep 1', 'keep 2']
    assert lines[2].startswith('exit 3, log ') and lines[2].endswith('demo.log')
    assert 'drop' in open(lines[2].split('log ', 1)[1]).read()


def test_run_tail_and_count(repo):
    script = 'print("\\n".join(str(i) for i in range(10)))'
    assert loop(repo, 'run', 't', '--tail', '2', '--', sys.executable, '-c', script).stdout.splitlines()[:2] == ['8', '9']
    assert loop(repo, 'run', 'c', '--count', '--grep', '[05]', '--', sys.executable, '-c', script).stdout.splitlines()[0] == '2'


def test_run_regression_prints_the_evidence_line(repo):
    summary = 'print("[1/5] [regression] x"); print("  1 failed"); print("    [regression] a.spec.ts"); print("  1 skipped"); print("  3 passed (4.1m)")'
    lines = loop(repo, 'run', 'regression', '--tail', '1', '--', sys.executable, '-c', summary).stdout.splitlines()
    assert lines[1] == '- regression: 3 passed of 4'
    assert lines[2].startswith('exit 0, log ')
    other = loop(repo, 'run', 'scripts', '--', sys.executable, '-c', summary).stdout
    assert '- regression:' not in other


def test_run_regression_reads_counts_behind_cursor_codes_and_flags_a_failed_exit(repo):
    # Playwright's line reporter, as a real log has it: cursor up and clear line before `1 failed`.
    summary = 'import sys; print("\\x1b[1A\\x1b[2K  1 failed"); print("  136 passed (5.3m)"); sys.exit(1)'
    lines = loop(repo, 'run', 'regression', '--tail', '1', '--', sys.executable, '-c', summary).stdout.splitlines()
    assert lines[1] == '- regression: 136 passed of 137; exit 1'
    green = 'import sys; print("  3 passed (1m)"); sys.exit(1)'
    lines = loop(repo, 'run', 'regression', '--tail', '1', '--', sys.executable, '-c', green).stdout.splitlines()
    assert lines[1] == '- regression: 3 passed of 3; exit 1'


# round-plan, carry and inert

CODE = f'docs/tasks/{FEATURE}/runs/05'


def evidence(repo, n, regression):
    write(repo, f'{CODE}/evidence-{n}.md', f'# Evidence {n}: task 05\nCommit: x\nItems: 1\n\n## Gates\n- lint: 0\n{regression}\n')
    loop(repo, 'commit', f'test(validation): task 05 round {n}', CODE)


def validation(repo, n, verdict='PASS'):
    commit = git(repo, 'log', '-1', '--format=%h', '--', '.', ':!docs/tasks', ':!tests/validation')
    write(repo, f'{CODE}/validation-{n}.md', f'# Validation {n}: task 05\nCommit: {commit}\nVerdict: {verdict}\nBlocking: 0\nDisputed: 0\nRepeat: none\n')
    loop(repo, 'commit', f'docs(validation): task 05 round {n}', CODE)


def test_carry_with_a_green_regression_at_the_current_code(repo):
    attributed(repo)
    write(repo, 'src/a.ts', 'export const a = 1;\n')
    loop(repo, 'commit', 'feat: a', 'src/a.ts')
    evidence(repo, 1, '- regression: 116 passed of 116')
    validation(repo, 1)
    write(repo, 'tests/validation/feat-x/05.spec.ts', 'x\n')
    loop(repo, 'commit', 'test(validation): script', 'tests/validation')
    assert loop(repo, 'carry', CODE).stdout == 'carry 1\n'


def test_carry_ignores_comment_lines_but_not_code_or_directives(repo):
    attributed(repo)
    write(repo, 'src/a.ts', '// old note\nexport const a = 1;\n')
    loop(repo, 'commit', 'feat: a', 'src/a.ts')
    evidence(repo, 1, '- regression: 116 passed of 116')
    validation(repo, 1)
    write(repo, 'src/a.ts', '// a clearer note\n\nexport const a = 1;\n')
    loop(repo, 'commit', 'docs: nit', 'src/a.ts')
    assert loop(repo, 'carry', CODE).stdout == 'carry 1, only // comment lines changed since\n'
    write(repo, 'src/a.ts', '// a clearer note\n\n// @ts-expect-error\nexport const a = 1;\n')
    loop(repo, 'commit', 'chore: directive', 'src/a.ts')
    assert loop(repo, 'carry', CODE).stdout.startswith('validate: code changed')
    write(repo, 'src/a.ts', '// a clearer note\n\nexport const a = 2;\n')
    loop(repo, 'commit', 'fix: a', 'src/a.ts')
    assert loop(repo, 'carry', CODE).stdout.startswith('validate: code changed')


def test_carry_validates_without_a_regression_line(repo):
    attributed(repo)
    evidence(repo, 1, '- regression: 116 of 116 passed')
    validation(repo, 1)
    assert loop(repo, 'carry', CODE).stdout.startswith('validate: no green regression run')


def test_carry_validates_after_a_regression_run_that_exited_non_zero(repo):
    attributed(repo)
    evidence(repo, 1, '- regression: 116 passed of 116; exit 1')
    validation(repo, 1)
    assert loop(repo, 'carry', CODE).stdout.startswith('validate: no green regression run')


def test_round_plan_after_a_validation_only_change(repo):
    attributed(repo)
    assert loop(repo, 'round-plan', CODE).stdout == 'gates: all\nregression: due\n'
    evidence(repo, 1, '- regression: 3 passed of 4')
    evidence(repo, 2, '- regression: 4 passed of 4')
    write(repo, 'tests/validation/feat-x/05.spec.ts', 'x\n')
    loop(repo, 'commit', 'test(validation): script', 'tests/validation')
    assert loop(repo, 'round-plan', CODE).stdout == 'gates: tsc lint\nregression: carried 2\n'
    write(repo, 'src/a.ts', 'export const a = 2;\n')
    loop(repo, 'commit', 'feat: a', 'src/a.ts')
    assert loop(repo, 'round-plan', CODE).stdout == 'gates: all\nregression: due\n'


def test_inert_folds_a_deleted_export(repo):
    attributed(repo)
    write(repo, 'src/a.ts', 'export function gone(\n  x: number,\n) {\n  return x;\n}\nexport const kept = 1;\n')
    base = loop(repo, 'commit', 'feat: a', 'src/a.ts').stdout.split()[0]
    write(repo, 'src/a.ts', '// kept is kept\nexport const kept = 2;\n')
    loop(repo, 'commit', 'chore: a', 'src/a.ts')
    out = loop(repo, 'inert', base).stdout.splitlines()
    assert out[0] == 'src/a.ts: deleted export gone'
    assert out[-1] == 'inert: 1 comment lines, 3 other changes'


def test_baseline_copies_the_previous_tasks_gates_at_the_same_code(repo):
    attributed(repo)
    write(repo, 'src/a.ts', 'export const a = 1;\n')
    code = loop(repo, 'commit', 'feat: a', 'src/a.ts').stdout.split()[0]
    gates = f'Commit: {code}\nItems: 1\n\n## Gates\n- jest: 0 failed of 40 suites\n- tsc: carried from round 1\n'
    write(repo, f'docs/tasks/{FEATURE}/runs/01/evidence-2.md', f'# Evidence 2: task 01\n{gates}')
    write(repo, f'docs/tasks/{FEATURE}/runs/01/evidence-1.md', f'# Evidence 1: task 01\n{gates}- tsc: 0 errors\n')
    base = loop(repo, 'commit', 'docs: marks', 'docs').stdout.split()[0]
    assert loop(repo, 'baseline', FEATURE, base).stdout == '- jest: 0 failed of 40 suites\n- tsc: 0 errors\n'
    write(repo, 'src/a.ts', 'export const a = 2;\n')
    later = loop(repo, 'commit', 'feat: other task', 'src/a.ts').stdout.split()[0]
    assert loop(repo, 'baseline', FEATURE, later).stdout == 'run\n'


def test_port_skips_a_pair_with_a_listener(tmp_path):
    import socket
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        s.listen()
        taken = s.getsockname()[1]
        start = taken - taken % 2  # the listener holds start or start + 1
        out = int(sh(str(tmp_path), sys.executable, LOOP, 'port', str(start)))
    assert out != start and (out - start) % 2 == 0
