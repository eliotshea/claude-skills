"""base_run.py: the base worktree shots.py shares, and a validation spec run at the base commit,
with Playwright faked."""
import contextlib
import os
import sys

import pytest

import base_run
from conftest import run_script

SPEC = 'tests/validation/feat/01-x.spec.ts'
HELPER = 'tests/validation/feat/helper.ts'
PACKAGE_JSON = '{"dependencies": {"next": "1", "@trpc/next": "1"}}\n'


# --- worktree -------------------------------------------------------------------------------

@pytest.fixture
def project(repo, monkeypatch):
    """A committed repo with the files the worktree copies, cwd inside it."""
    base = repo.commit({'README.md': 'base\n', 'package.json': PACKAGE_JSON})
    repo.write('.env', 'SECRET=1\n')
    repo.write('playwright.validation.config.ts', 'config\n')
    repo.write(SPEC, 'spec\n')
    repo.write(HELPER, 'helper\n')
    repo.write('tests/app/fixtures/song.ts', 'fixture\n')
    monkeypatch.chdir(repo.path)
    repo.base = base
    return repo


def test_worktree_copies_this_checkouts_files_installs_and_removes_it(project, monkeypatch,
                                                                       tmp_path):
    calls = []

    def run(cmd, cwd, log, env=None):
        calls.append((cmd, cwd, log))
        return 0

    monkeypatch.setattr(base_run, 'run', run)
    logs = str(tmp_path / 'logs')
    with base_run.worktree(project.base, SPEC, logs) as tree:
        files = {p: open(os.path.join(tree, p)).read() for p in
                 ['.env', base_run.CONFIG, SPEC, HELPER, 'tests/app/fixtures/song.ts',
                  'README.md']}

    # No node_modules here to share, so it installs, then checks the server's imports load.
    imports_log = os.path.join(logs, 'imports.log')
    assert calls == [
        (['pnpm', 'install', '--frozen-lockfile', '--prefer-offline'], tree,
         os.path.join(logs, 'install.log')),
        (['node', '--input-type=module', '-e', 'await import("next")'], tree, imports_log),
        (['node', '--input-type=module', '-e', 'await import("@trpc/next")'], tree, imports_log),
    ]
    # The spec's whole directory comes along, so a helper the spec imports is there too.
    assert files == {'.env': 'SECRET=1\n', base_run.CONFIG: 'config\n', SPEC: 'spec\n',
                     HELPER: 'helper\n', 'tests/app/fixtures/song.ts': 'fixture\n',
                     'README.md': 'base\n'}
    assert not os.path.exists(tree)
    assert tree not in project.git('worktree', 'list')


def test_worktree_links_this_checkouts_node_modules_when_the_deps_match(project, monkeypatch,
                                                                       tmp_path):
    project.write('node_modules/next/index.js', '\n')
    cmds = []

    def run(cmd, cwd, log, env=None):
        cmds.append(cmd[0])
        return 0

    monkeypatch.setattr(base_run, 'run', run)
    with base_run.worktree(project.base, SPEC, str(tmp_path)) as tree:
        assert (os.readlink(os.path.join(tree, 'node_modules'))
                == os.path.join(str(project.path), 'node_modules'))
    assert cmds == ['node', 'node']


def test_imports_probes_only_the_packages_the_project_lists(tmp_path, monkeypatch):
    (tmp_path / 'package.json').write_text('{"devDependencies": {"next": "1"}}')
    probed = []

    def run(cmd, cwd, log, env=None):
        probed.append(cmd[-1])
        return 0

    monkeypatch.setattr(base_run, 'run', run)
    assert base_run.imports(str(tmp_path), str(tmp_path)) is None
    assert probed == ['await import("next")']


def test_worktree_installs_when_the_linked_node_modules_cannot_import(project, monkeypatch,
                                                                     tmp_path):
    project.write('node_modules/next/index.js', '\n')
    cmds = []

    def run(cmd, cwd, log, env=None):
        cmds.append(cmd[0])
        # Imports fail through the link and load once installed.
        if cmd[0] == 'node' and os.path.islink(os.path.join(cwd, 'node_modules')):
            with open(log, 'w') as f:
                f.write('Error: missing\n')
            return 1
        return 0

    monkeypatch.setattr(base_run, 'run', run)
    with base_run.worktree(project.base, SPEC, str(tmp_path)) as tree:
        assert not os.path.islink(os.path.join(tree, 'node_modules'))
    assert cmds == ['node', 'pnpm', 'node', 'node']


def test_worktree_reinstalls_with_force_then_gives_up_on_an_import(project, monkeypatch,
                                                                   tmp_path):
    installs = []

    def run(cmd, cwd, log, env=None):
        if cmd[0] == 'pnpm':
            installs.append(cmd)
        elif '@trpc/next' in cmd[-1]:
            with open(log, 'w') as f:
                f.write('node:internal\nError [ERR_MODULE_NOT_FOUND]: react-ssr-prepass\n')
            return 1
        return 0

    monkeypatch.setattr(base_run, 'run', run)
    with pytest.raises(SystemExit) as exit_:
        with base_run.worktree(project.base, SPEC, str(tmp_path)):
            pytest.fail('the body must not run')
    assert installs == [['pnpm', 'install', '--frozen-lockfile', '--prefer-offline'],
                        ['pnpm', 'install', '--frozen-lockfile', '--prefer-offline', '--force']]
    assert str(exit_.value) == ('The base worktree cannot import @trpc/next: Error '
                                '[ERR_MODULE_NOT_FOUND]: react-ssr-prepass, even after '
                                f'`pnpm install --force`. Log: {tmp_path}/install.log')
    assert len(project.git('worktree', 'list').splitlines()) == 1


def test_worktree_replaces_a_fixtures_dir_the_base_already_has(repo, monkeypatch, tmp_path):
    base = repo.commit({'tests/app/fixtures/old.ts': 'old\n'})
    repo.git('rm', '-q', 'tests/app/fixtures/old.ts')
    repo.write('tests/app/fixtures/new.ts', 'new\n')
    monkeypatch.chdir(repo.path)
    monkeypatch.setattr(base_run, 'run', lambda *a, **k: 0)
    with base_run.worktree(base, SPEC, str(tmp_path)) as tree:
        assert sorted(os.listdir(os.path.join(tree, 'tests/app/fixtures'))) == ['new.ts']


def test_worktree_install_failure_exits_and_still_removes_it(project, monkeypatch, tmp_path):
    trees = []

    def run(cmd, cwd, log, env=None):
        trees.append(cwd)
        return 1

    monkeypatch.setattr(base_run, 'run', run)
    with pytest.raises(SystemExit) as exit_:
        with base_run.worktree(project.base, SPEC, str(tmp_path)):
            pytest.fail('the body must not run')
    assert str(exit_.value) == f'pnpm install failed in the base worktree. Log: {tmp_path}/install.log'
    assert not os.path.exists(trees[0])
    assert len(project.git('worktree', 'list').splitlines()) == 1


def test_worktree_is_removed_when_the_body_raises(project, monkeypatch, tmp_path):
    monkeypatch.setattr(base_run, 'run', lambda *a, **k: 0)
    with pytest.raises(RuntimeError):
        with base_run.worktree(project.base, SPEC, str(tmp_path)) as tree:
            raise RuntimeError('boom')
    assert not os.path.exists(tree)
    assert len(project.git('worktree', 'list').splitlines()) == 1


def test_run_writes_the_log_and_returns_the_exit_code(tmp_path):
    log = tmp_path / 'out.log'
    code = base_run.run([sys.executable, '-c',
                         'import os,sys; print(os.environ["X"]); sys.stderr.write("err\\n"); sys.exit(3)'],
                        tmp_path, str(log), {'X': 'from env'})
    assert code == 3
    assert sorted(log.read_text().split()) == ['env', 'err', 'from']


# --- main -----------------------------------------------------------------------------------

@pytest.fixture
def fake(monkeypatch, tmp_path):
    """main() with the worktree and Playwright faked. Playwright prints `output` and exits 1."""
    state = {'worktrees': [], 'runs': [], 'output': 'one\ntwo\n'}

    @contextlib.contextmanager
    def worktree(base, spec, logs):
        state['worktrees'].append((base, spec, logs))
        yield '/base-tree'

    def run(cmd, cwd, log, env=None):
        state['runs'].append((cmd, cwd, log, env))
        with open(log, 'w') as f:
            f.write(state['output'])
        return 1

    monkeypatch.setattr(base_run, 'worktree', worktree)
    monkeypatch.setattr(base_run, 'run', run)
    monkeypatch.setattr(base_run.tempfile, 'mkdtemp', lambda prefix: str(tmp_path))

    def main(*args):
        monkeypatch.setattr(sys, 'argv', ['base_run.py', *args])
        return base_run.main()

    state['main'] = main
    state['log'] = str(tmp_path / 'playwright.log')
    return state


def test_main_runs_the_spec_under_the_validation_project_on_the_next_port(fake, capsys):
    assert fake['main']('abc123', SPEC, '3100') == 1
    assert fake['worktrees'] == [('abc123', SPEC, os.path.dirname(fake['log']))]
    assert fake['runs'] == [(['pnpm', 'exec', 'playwright', 'test', '-c', base_run.CONFIG,
                              '--project=validation', SPEC],
                             '/base-tree', fake['log'], {'VALIDATION_PORT': '3101'})]
    assert capsys.readouterr().out.splitlines() == ['one', 'two', f'exit 1, log {fake["log"]}']


def test_main_passes_a_title_regex_to_playwright(fake):
    fake['main']('abc123', SPEC, '3100', '-g', 'criterion 9:')
    assert fake['runs'][0][0][-3:] == [SPEC, '-g', 'criterion 9:']


def test_main_prints_only_the_tail_without_colour_codes(fake, capsys):
    fake['output'] = ''.join(f'line {i}\n' for i in range(1, 31)) + '\x1b[32m  1 passed\x1b[39m\n'
    fake['main']('abc123', SPEC, '3100')
    out = capsys.readouterr().out.splitlines()
    assert out == [f'line {i}' for i in range(12, 31)] + ['  1 passed',
                                                          f'exit 1, log {fake["log"]}']
    assert '\x1b[32m' in open(fake['log']).read()  # the log keeps everything


def test_main_tail_leaves_out_the_dev_servers_lines_and_cursor_codes(fake, capsys):
    # The line reporter rewrites its line with cursor codes, and next dev logs every query.
    fake['output'] = ('\x1b[1A\x1b[2KPICTURE phone 390 219\n'
                      + '\x1b[1A\x1b[2K[WebServer] prisma:query SELECT 1\n' * 30
                      + '\x1b[1A\x1b[2K  1 passed (3.0s)\n')
    fake['main']('abc123', SPEC, '3100')
    assert capsys.readouterr().out.splitlines() == ['PICTURE phone 390 219', '  1 passed (3.0s)',
                                                    f'exit 1, log {fake["log"]}']
    assert open(fake['log']).read().count('[WebServer]') == 30


def test_main_tail_is_adjustable(fake, capsys):
    fake['output'] = 'a\nb\nc\n'
    fake['main']('abc123', SPEC, '3100', '--tail', '1')
    assert capsys.readouterr().out.splitlines() == ['c', f'exit 1, log {fake["log"]}']


@pytest.mark.parametrize('args', [[], ['HEAD', SPEC], ['HEAD', SPEC, 'abc']])
def test_cli_bad_arguments_print_usage(repo, args):
    result = run_script('base_run.py', *args, cwd=repo.path)
    assert result.returncode == 2
    assert 'usage: base_run.py' in result.stderr
