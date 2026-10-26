"""shots.py: report parsing, the baseline and the shots table, with Playwright faked."""
import contextlib
import json
import os
import sys

import pytest

from conftest import load_script, run_script

SPEC = 'tests/validation/feat/01-x.shots.spec.ts'


@pytest.fixture
def shots():
    return load_script('shots.py')


def spec_result(title, status, errors=(), attachments=(), retries=()):
    results = [*({'status': s} for s in retries),
               {'status': status, 'errors': [{'message': m} for m in errors],
                'attachments': list(attachments)}]
    return {'title': title, 'tests': [{'results': results}]}


def report(*specs, nested=()):
    return {'suites': [{'specs': list(specs), 'suites': [{'specs': list(nested)}]}]}


# --- small helpers --------------------------------------------------------------------------

def test_first_line(shots):
    assert shots.first_line('\n  \n  Error: boom  \nmore') == 'Error: boom'
    assert shots.first_line('') == ''


def test_results_walks_nested_suites_and_takes_the_last_retry(shots):
    rep = report(
        spec_result('view home', 'passed', retries=['failed']),
        nested=[spec_result('view   settings ', 'failed',
                            errors=['\x1b[31mError:\x1b[39m one', 'two'],
                            attachments=[{'name': 'a', 'path': '/p'}])])
    assert list(shots.results(rep)) == [
        ('home', 'passed', '', []),
        ('settings', 'failed', 'Error: one two', [{'name': 'a', 'path': '/p'}]),
    ]


def test_results_tolerates_missing_fields(shots):
    rep = {'suites': [{'specs': [{'title': 'no prefix', 'tests': [{}]}]}, {}]}
    assert list(shots.results(rep)) == [('no prefix', None, '', [])]
    assert list(shots.results({})) == []


# --- playwright -----------------------------------------------------------------------------

def fake_run(calls, report_json=None):
    def run(cmd, cwd, log, env=None):
        calls.append((cmd, cwd, log, env))
        if report_json is not None:
            with open(env['PLAYWRIGHT_JSON_OUTPUT_NAME'], 'w') as f:
                f.write(report_json)
        return 1
    return run


@pytest.mark.parametrize('update', [True, False])
def test_playwright_command_and_env(shots, tmp_path, monkeypatch, update):
    calls = []
    monkeypatch.setattr(shots, 'run', fake_run(calls, '{"suites": []}'))
    rep = str(tmp_path / 'r.json')
    assert shots.playwright('/cwd', SPEC, '/shots', 4001, rep, update) == {'suites': []}
    cmd, cwd, log, env = calls[0]
    assert cmd[:8] == ['pnpm', 'exec', 'playwright', 'test', '-c', shots.CONFIG,
                       '--project=shots', SPEC]
    assert ('--update-snapshots' in cmd) is update
    assert '--reporter=json' in cmd
    assert (cwd, log) == ('/cwd', rep + '.log')
    assert env == {'SHOTS_DIR': '/shots', 'VALIDATION_PORT': '4001',
                   'PLAYWRIGHT_JSON_OUTPUT_NAME': rep}


@pytest.mark.parametrize('content', [None, 'not json'])
def test_playwright_without_a_report_exits(shots, tmp_path, monkeypatch, content):
    monkeypatch.setattr(shots, 'run', fake_run([], content))
    rep = str(tmp_path / 'r.json')
    with pytest.raises(SystemExit) as exit_:
        shots.playwright('/cwd', SPEC, '/shots', 4001, rep, False)
    assert str(exit_.value) == f'Playwright wrote no report. Log: {rep}.log'


# --- baseline -------------------------------------------------------------------------------

def test_baseline_photographs_in_the_shared_base_worktree_on_the_next_port(shots, monkeypatch,
                                                                         tmp_path):
    seen = {}

    @contextlib.contextmanager
    def worktree(base, spec, logs):
        seen['worktree'] = (base, spec, logs)
        yield '/base-tree'
        seen['removed'] = True

    def playwright(cwd, spec, shots_dir, port, rep, update):
        seen['playwright'] = (cwd, spec, shots_dir, port, rep, update)
        return report(spec_result('view a', 'passed'),
                      spec_result('view b', 'failed', errors=['\n Error: no server \nstack']))

    monkeypatch.setattr(shots, 'worktree', worktree)
    monkeypatch.setattr(shots, 'playwright', playwright)
    logs = str(tmp_path / 'logs')
    out = shots.baseline('abc123', SPEC, '/out', 5000, logs)

    assert out == {'a': ('passed', ''), 'b': ('failed', 'Error: no server')}
    assert seen['worktree'] == ('abc123', SPEC, logs)
    assert seen['playwright'] == ('/base-tree', SPEC, '/out', 5001,
                                  os.path.join(logs, 'before.json'), True)
    assert seen['removed']


def test_baseline_uses_base_runs_worktree(shots):
    import base_run
    assert shots.worktree is base_run.worktree
    assert shots.CONFIG == base_run.CONFIG


# --- main -----------------------------------------------------------------------------------

def png(path, content=b'png'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(content)
    return str(path)


@pytest.fixture
def main_env(shots, repo, monkeypatch, tmp_path):
    """Run main() in a repo with baseline and playwright faked. Returns a namespace of hooks."""
    base = repo.commit({'a.ts': 'a\n'})
    monkeypatch.chdir(repo.path)
    state = {'baseline_calls': [], 'baseline': {}, 'after': report(), 'playwright_calls': []}

    def baseline(base_, spec, out, port, logs):
        state['baseline_calls'].append((base_, spec, out, port))
        for name in state.get('baseline_writes', ()):  # as Playwright would
            png(os.path.join(out, 'before', name + '.png'))
        return state['baseline']

    def playwright(cwd, spec, shots_dir, port, rep, update):
        state['playwright_calls'].append((cwd, spec, shots_dir, port, update))
        return state['after']

    monkeypatch.setattr(shots, 'baseline', baseline)
    monkeypatch.setattr(shots, 'playwright', playwright)

    def main(*args):
        monkeypatch.setattr(sys, 'argv', ['shots.py', *args])
        shots.main()

    state.update(main=main, repo=repo, base=base, out=repo.path / 'run' / 'shots',
                 tmp=tmp_path)
    return state


def test_main_first_run_takes_the_baseline(main_env, capsys):
    env = main_env
    env['baseline'] = {'home': ('passed', ''), 'broken': ('failed', 'Error: ' + 'x' * 200)}
    env['baseline_writes'] = ['home']
    env['main']('HEAD', SPEC, 'run', '4000')
    short = env['repo'].git('rev-parse', '--short', env['base']).strip()
    assert env['baseline_calls'] == [(short, SPEC, str(env['out']), 4000)]
    assert env['playwright_calls'] == [(os.getcwd(), SPEC, str(env['out']), 4000, False)]
    out = capsys.readouterr().out.splitlines()
    assert out[0] == 'broken: no before picture, failed: ' + ('Error: ' + 'x' * 200)[:160]
    assert out[-2:] == ['No views ran.', 'File: run/shots/shots.md']


def test_main_skips_the_baseline_when_before_pictures_exist(main_env):
    png(main_env['out'] / 'before' / 'home.png')
    main_env['main']('HEAD', SPEC, 'run', '4000')
    assert main_env['baseline_calls'] == []
    assert os.path.exists(main_env['out'] / 'before' / 'home.png')


def test_main_rebase_clears_and_retakes_the_baseline(main_env):
    old = png(main_env['out'] / 'before' / 'old.png')
    main_env['main']('HEAD', SPEC, 'run', '4000', '--rebase')
    assert len(main_env['baseline_calls']) == 1
    assert not os.path.exists(old)


def test_main_empty_before_dir_takes_the_baseline(main_env):
    os.makedirs(main_env['out'] / 'before')
    main_env['main']('HEAD', SPEC, 'run', '4000')
    assert len(main_env['baseline_calls']) == 1


def test_main_classifies_every_view_and_writes_the_table(main_env, capsys):
    env, out = main_env, main_env['out']
    png(out / 'before' / 'same.png')
    png(out / 'before' / 'brand-new.png', b'new')  # Playwright wrote the missing snapshot here
    png(out / 'after' / 'stale.png')  # cleared on every run
    pics = env['tmp'] / 'pw'
    actual, diff = png(pics / 'moved-actual.png', b'A'), png(pics / 'moved-diff.png', b'D')
    resized = png(pics / 'resized-actual.png', b'R')
    nodiff = png(pics / 'plain-actual.png', b'P')
    env['after'] = report(
        spec_result('view same', 'passed'),
        spec_result('view brand-new', 'failed',
                    errors=["A snapshot doesn't exist at /x/brand-new.png, writing actual."]),
        spec_result('view moved', 'failed',
                    errors=['Error: 1234 pixels (ratio 0.0123 of all image pixels) are different.'],
                    attachments=[{'name': 'moved-actual.png', 'path': actual},
                                 {'name': 'moved-diff.png', 'path': diff},
                                 {'name': 'moved-expected.png', 'path': '/nope'}]),
        # Oddity: the size regex captures the sentence's closing period.
        spec_result('view resized', 'failed',
                    errors=['Expected an image 100px by 200px, received 100px by 250px.'],
                    attachments=[{'name': 'resized-actual.png', 'path': resized}]),
        spec_result('view plain', 'failed', errors=['something odd'],
                    attachments=[{'name': 'plain-actual.png', 'path': nodiff}]),
        spec_result('view crashed', 'timedOut', errors=['\nTimeout 30000ms exceeded.\n  at x']),
    )
    env['main']('HEAD', SPEC, 'run', '4000')

    printed = capsys.readouterr().out.splitlines()
    assert printed == [
        'same: identical',
        'brand-new: new, no before picture',
        'moved: changed, 1.23% of pixels',
        'resized: changed size, 100px by 200px to 100px by 250px.',
        'plain: changed',
        'crashed: error: Timeout 30000ms exceeded.',
        '1 identical, 1 new, 2 changed, 1 changed size, 1 error',
        'File: run/shots/shots.md',
    ]
    assert sorted(os.listdir(out / 'after')) == ['brand-new.png', 'moved.png', 'plain.png',
                                                 'resized.png']
    assert (out / 'after' / 'brand-new.png').read_bytes() == b'new'
    assert not os.path.exists(out / 'before' / 'brand-new.png')
    assert (out / 'after' / 'moved.png').read_bytes() == b'A'
    assert os.listdir(out / 'diff') == ['moved.png']

    table = (out / 'shots.md').read_text()
    short = env['repo'].git('rev-parse', '--short', env['base']).strip()
    head = env['repo'].git('rev-parse', '--short', 'HEAD').strip()
    lines = table.splitlines()
    assert lines[0] == f'# Shots: {SPEC}'
    assert lines[2].startswith(f'Before: {short}. After: {head}. Logs: ')
    assert lines[4:6] == ['| View | Result | Before | After | Diff |', '|---|---|---|---|---|']
    assert lines[6:] == [
        '| same | identical | ![before](before/same.png) |  |  |',
        '| brand-new | new, no before picture |  | ![after](after/brand-new.png) |  |',
        '| moved | changed, 1.23% of pixels | ![before](before/moved.png) | '
        '![after](after/moved.png) | ![diff](diff/moved.png) |',
        '| resized | changed size, 100px by 200px to 100px by 250px. | '
        '![before](before/resized.png) | ![after](after/resized.png) |  |',
        '| plain | changed | ![before](before/plain.png) | ![after](after/plain.png) |  |',
        '| crashed | error: Timeout 30000ms exceeded. |  |  |  |',
    ]


@pytest.mark.parametrize('args', [[], ['HEAD', SPEC, 'run'], ['HEAD', SPEC, 'run', '4000', 'x']])
def test_cli_wrong_argument_count_prints_usage(repo, args):
    result = run_script('shots.py', *args, cwd=repo.path)
    assert result.returncode == 1
    assert 'shots.py <base commit> <shots spec> <run dir> <port>' in result.stderr


def test_cli_ignores_unknown_flags_when_counting_arguments(repo):
    # Any `--` argument is dropped before counting, so a typo like --rebse is silently ignored.
    result = run_script('shots.py', 'HEAD', SPEC, 'run', '--rebse', cwd=repo.path)
    assert 'shots.py <base commit>' in result.stderr


def test_cli_unknown_base_is_a_traceback(repo):
    repo.commit({'a.ts': 'a\n'})
    result = run_script('shots.py', 'nope', SPEC, 'run', '4000', cwd=repo.path)
    assert result.returncode == 1
    assert 'CalledProcessError' in result.stderr


def test_cli_non_numeric_port_is_a_traceback(repo):
    result = run_script('shots.py', 'HEAD', SPEC, 'run', 'abc', cwd=repo.path)
    assert result.returncode == 1
    assert 'ValueError' in result.stderr
