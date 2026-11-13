"""run-stats.py: subagent transcripts under a fake ~/.claude/projects."""
import datetime as dt
import json
import os
import re
import subprocess
import types

import pytest

from conftest import load_script, run_script

T0 = dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def rs():
    return load_script('run-stats.py')


def stamp(minutes):
    return (T0 + dt.timedelta(minutes=minutes)).isoformat().replace('+00:00', 'Z')


def prompt(feature='feat-a', task='01', step=None):
    text = f'Task file: docs/tasks/{feature}/{task}-some-slug.md\n'
    if step:
        text += f'{step}\n'
    return text


def events(prompt_text, minutes=(0, 1, 2), usage=None, tools=0, msg_ids=None):
    """A transcript: one user prompt, then one assistant event per later minute."""
    out = [{'type': 'user', 'timestamp': stamp(minutes[0]),
            'message': {'role': 'user', 'content': prompt_text}}]
    for i, m in enumerate(minutes[1:]):
        content = [{'type': 'text', 'text': 'hi'}] + [{'type': 'tool_use', 'id': f't{j}'}
                                                      for j in range(tools)]
        out.append({'type': 'assistant', 'timestamp': stamp(m),
                    'message': {'id': (msg_ids or [f'm{k}' for k in range(len(minutes))])[i],
                                'content': content,
                                'usage': usage or {'input_tokens': 10,
                                                   'cache_creation_input_tokens': 1000,
                                                   'cache_read_input_tokens': 20000}}})
    return out


def write_run(directory, name, agent, lines, meta_extra=None, raw=None):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{name}.jsonl'
    path.write_text(raw if raw is not None else ''.join(json.dumps(e) + '\n' for e in lines))
    if agent is not None:
        (directory / f'{name}.meta.json').write_text(
            json.dumps({'agentType': agent, **(meta_extra or {})}))
    return path


@pytest.fixture
def home(tmp_path, repo):
    """HOME with a projects dir named the way Claude Code names this repo's."""
    common = repo.git('rev-parse', '--path-format=absolute', '--git-common-dir').strip()
    encoded = re.sub(r'[^A-Za-z0-9]', '-', os.path.dirname(common))
    root = tmp_path / 'home'
    projects = root / '.claude' / 'projects'
    (projects / encoded).mkdir(parents=True)
    return types.SimpleNamespace(root=root, projects=projects, project=projects / encoded,
                                 encoded=encoded)


def run(repo, home, *args):
    return run_script('run-stats.py', *args, cwd=repo.path, env={'HOME': str(home.root)})


def table_rows(stdout):
    return [l for l in stdout.splitlines() if l.startswith('| ') and not l.startswith('| Task')]


# --- read_run -------------------------------------------------------------------------------

def test_read_run_measures_one_transcript(rs, tmp_path):
    lines = events(prompt('feat-a', '03', 'Mode: fix'), minutes=(0, 2, 5, 30, 31), tools=2)
    run_ = rs.read_run(str(write_run(tmp_path, 'agent-1', 'task-implementer', lines)))
    assert run_ == dict(feature='feat-a', task='03', agent='task-implementer', stopped=False,
                        step='fix', start=T0, peak=21010, turns=4, tools=8,
                        wall=31.0, active=6.0, stalls=1)


def test_read_run_turns_count_distinct_message_ids_and_peak_is_the_max(rs, tmp_path):
    lines = events(prompt(), minutes=(0, 1, 2, 3), msg_ids=['a', 'a', 'b'], tools=1)
    lines[1]['message']['usage'] = {'input_tokens': 5}
    lines[2]['message']['usage'] = {'input_tokens': 1, 'cache_read_input_tokens': 70000}
    lines[3]['message'].pop('usage')
    r = rs.read_run(str(write_run(tmp_path, 'agent-1', 'code-writer', lines)))
    assert (r['turns'], r['tools'], r['peak']) == (2, 3, 70001)


def test_read_run_gap_of_exactly_stall_min_is_a_stall(rs, tmp_path):
    lines = events(prompt(), minutes=(0, rs.STALL_MIN, rs.STALL_MIN + 1))
    r = rs.read_run(str(write_run(tmp_path, 'agent-1', 'task-scout', lines)))
    assert (r['stalls'], r['active'], r['wall']) == (1, 1.0, rs.STALL_MIN + 1.0)


def test_read_run_sorts_out_of_order_timestamps(rs, tmp_path):
    lines = events(prompt(), minutes=(3, 0, 1))
    r = rs.read_run(str(write_run(tmp_path, 'agent-1', 'task-scout', lines)))
    assert r['start'] == T0 and r['wall'] == 3.0


@pytest.mark.parametrize('step_line, step', [
    ('Round: 2', '2'), ('Cycle: 3a', '3a'), ('Mode: build', 'build'), ('  Mode: indented', ''),
    (None, ''),
])
def test_read_run_step(rs, tmp_path, step_line, step):
    lines = events(prompt(step=step_line))
    assert rs.read_run(str(write_run(tmp_path, 'agent-1', 'task-scout', lines)))['step'] == step


def test_read_run_prompt_from_a_content_block_list(rs, tmp_path):
    lines = events('')
    lines[0]['message']['content'] = [{'type': 'text', 'text': prompt('feat-b', '07')}]
    r = rs.read_run(str(write_run(tmp_path, 'agent-1', 'task-scout', lines)))
    assert (r['feature'], r['task']) == ('feat-b', '07')


def test_read_run_uses_only_the_first_user_message_as_prompt(rs, tmp_path):
    lines = events('no task here')
    lines.append({'type': 'user', 'timestamp': stamp(3), 'message': {'content': prompt()}})
    assert rs.read_run(str(write_run(tmp_path, 'agent-1', 'task-scout', lines))) is None


def test_read_run_skips_lines_that_are_not_json(rs, tmp_path):
    raw = 'not json\n' + ''.join(json.dumps(e) + '\n' for e in events(prompt())) + '{broken\n'
    r = rs.read_run(str(write_run(tmp_path, 'agent-1', 'task-scout', None, raw=raw)))
    assert r['turns'] == 2


def test_read_run_crashes_on_a_json_line_that_is_not_an_object(rs, tmp_path):
    # Bug: a valid JSON line that is not an object (e.g. `[]`) raises instead of being skipped.
    raw = '[]\n' + ''.join(json.dumps(e) + '\n' for e in events(prompt()))
    with pytest.raises(AttributeError):
        rs.read_run(str(write_run(tmp_path, 'agent-1', 'task-scout', None, raw=raw)))


@pytest.mark.parametrize('case', ['no meta', 'bad meta', 'other agent', 'no task', 'no stamps'])
def test_read_run_returns_none(rs, tmp_path, case):
    lines = events(prompt())
    agent = 'task-scout'
    if case == 'no meta':
        agent = None
    elif case == 'other agent':
        agent = 'Explore'
    elif case == 'no task':
        lines = events('Task file: somewhere/else.md')
    elif case == 'no stamps':
        for e in lines:
            e.pop('timestamp')
    path = write_run(tmp_path, 'agent-1', agent, lines)
    if case == 'bad meta':
        (tmp_path / 'agent-1.meta.json').write_text('{nope')
    assert rs.read_run(str(path)) is None


def test_read_run_stopped_by_user(rs, tmp_path):
    path = write_run(tmp_path, 'agent-1', 'task-scout', events(prompt()), {'stoppedByUser': True})
    assert rs.read_run(str(path))['stopped'] is True


def test_when_parses_z_suffix(rs):
    assert rs.when('2026-10-01T12:00:00.000Z') == T0


# --- project_dirs ---------------------------------------------------------------------------

def test_project_dirs_matches_the_repo_and_its_worktrees_by_prefix(rs, repo, home, monkeypatch):
    (home.projects / (home.encoded + '--claude-worktrees-x')).mkdir()
    (home.projects / 'unrelated').mkdir()
    monkeypatch.setenv('HOME', str(home.root))
    monkeypatch.chdir(repo.path)
    found = sorted(os.path.basename(p) for p in rs.project_dirs())
    assert found == [home.encoded, home.encoded + '--claude-worktrees-x']


def test_project_dirs_outside_git_raises(rs, tmp_path, monkeypatch):
    outside = tmp_path / 'not-a-repo'
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setenv('GIT_CEILING_DIRECTORIES', str(tmp_path))
    with pytest.raises(subprocess.CalledProcessError):
        rs.project_dirs()


# --- CLI ------------------------------------------------------------------------------------

def test_cli_without_arguments_prints_usage(repo, home):
    result = run(repo, home)
    assert result.returncode == 1
    assert 'run-stats.py issue-156-embed-timeline [task]' in result.stderr


def test_cli_with_no_matching_transcripts(repo, home):
    result = run(repo, home, 'feat-a')
    assert result.returncode == 1
    assert result.stderr.strip() == 'No feature-loop transcripts for feat-a.'


def test_cli_prints_both_tables(repo, home):
    sub = home.project / 'session-1' / 'subagents'
    # Plugin agents are recorded with their prefix, as Claude Code records them now.
    write_run(sub, 'agent-b', 'eliot:brief-writer', events(prompt('feat-a', '01'), minutes=(5, 6, 8)))
    write_run(sub, 'agent-a', 'task-scout', events(prompt('feat-a', '01', 'Round: 1'),
                                                   minutes=(0, 1, 15, 16), tools=1))
    big = {'input_tokens': 60_000}
    write_run(sub, 'agent-c', 'task-validator',
              events(prompt('feat-a', '02'), minutes=(0, 4), usage=big))
    # Nested one level deeper, as runs the implementer starts are.
    write_run(sub / 'nested', 'agent-d', 'eliot:test-writer',
              events(prompt('feat-a', '02'), minutes=(10, 11)))
    write_run(sub, 'agent-e', 'task-scout', events(prompt('other-feature', '01')))
    result = run(repo, home, 'feat-a')
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == '| Task | Agent | Step | Context | Turns | Tools | Active min | Wall min | Stalls |'
    assert lines[2:6] == [
        '| 01 | task-scout | 1 | 21k | 3 | 3 | 2 | 16 | 1 |',
        '| 01 | brief-writer |  | 21k | 2 | 0 | 3 | 3 |  |',
        '| 02 | task-validator |  | 60k | 1 | 0 | 4 | 4 |  |',
        '| 02 | test-writer |  | 21k | 1 | 0 | 1 | 1 |  |',
    ]
    assert lines[6] == ''
    assert lines[7] == ('| Task | Runs | Largest context | Total context | Over 50k | '
                        'Active min | Wall min |')
    assert lines[9:] == [
        '| 01 | 2 | 21k task-scout | 42k | 0 | 5 | 19 |',
        '| 02 | 2 | 60k task-validator | 81k | 1 | 5 | 5 |',
    ]


def test_cli_filters_to_one_task(repo, home):
    sub = home.project / 's' / 'subagents'
    write_run(sub, 'agent-a', 'task-scout', events(prompt('feat-a', '01')))
    write_run(sub, 'agent-b', 'task-scout', events(prompt('feat-a', '02')))
    result = run(repo, home, 'feat-a', '02')
    rows = table_rows(result.stdout)
    assert [r.split(' | ')[0] for r in rows] == ['| 02', '| 02']
    assert result.stdout.splitlines()[-1].startswith('| 02 | 1 |')


def test_cli_leaves_out_stopped_runs_and_counts_them(repo, home):
    sub = home.project / 's' / 'subagents'
    write_run(sub, 'agent-a', 'task-scout', events(prompt()))
    write_run(sub, 'agent-b', 'task-scout', events(prompt()), {'stoppedByUser': True})
    write_run(sub, 'agent-c', 'task-scout', events(prompt()), {'stoppedByUser': True})
    out = run(repo, home, 'feat-a').stdout
    assert '\nLeft out: 2 runs stopped by the human.\n' in out
    assert len(table_rows(out)) == 2


def test_cli_singular_stopped_run(repo, home):
    sub = home.project / 's' / 'subagents'
    write_run(sub, 'agent-a', 'task-scout', events(prompt()))
    write_run(sub, 'agent-b', 'task-scout', events(prompt()), {'stoppedByUser': True})
    assert 'Left out: 1 run stopped by the human.' in run(repo, home, 'feat-a').stdout


def test_cli_only_stopped_runs_is_no_transcripts(repo, home):
    sub = home.project / 's' / 'subagents'
    write_run(sub, 'agent-a', 'task-scout', events(prompt()), {'stoppedByUser': True})
    assert run(repo, home, 'feat-a').returncode == 1


def test_cli_counts_a_transcript_name_once_across_project_dirs(repo, home):
    worktree_dir = home.projects / (home.encoded + '-wt') / 's' / 'subagents'
    write_run(home.project / 's' / 'subagents', 'agent-a', 'task-scout', events(prompt()))
    write_run(worktree_dir, 'agent-a', 'task-scout', events(prompt()))
    write_run(worktree_dir, 'agent-b', 'task-scout', events(prompt()))
    assert len(table_rows(run(repo, home, 'feat-a').stdout)) == 2 + 1


def test_cli_ignores_transcripts_outside_subagents(repo, home):
    write_run(home.project / 's', 'agent-a', 'task-scout', events(prompt()))
    write_run(home.project, 'agent-b', 'task-scout', events(prompt()))
    assert run(repo, home, 'feat-a').returncode == 1


def test_cli_counts_the_orchestrators_turns_for_the_task_its_calls_name(repo, home):
    write_run(home.project / 's' / 'subagents', 'agent-a', 'task-scout', events(prompt()))

    def turn(i, name, text):
        return {'type': 'assistant', 'timestamp': stamp(i),
                'message': {'id': f'm{i}', 'usage': {'input_tokens': 70_000 + i},
                            'content': [{'type': 'tool_use', 'name': name, 'input': {'x': text}}]}}
    main = [turn(0, 'Bash', 'git fetch origin'),  # before any task is named: not counted
            turn(1, 'Agent', prompt('feat-a', '01')),
            turn(2, 'Bash', 'loop.py row docs/tasks/feat-a/runs/01 survey'),
            turn(3, 'Bash', 'head docs/tasks/feat-a/00-overview.md'),
            turn(4, 'Agent', prompt('other', '09'))]
    (home.project / 'session.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in main))
    lines = run(repo, home, 'feat-a').stdout.splitlines()
    at = lines.index('| Task | Orchestrator context | Turns | Tools | Turns per dispatch |')
    assert lines[at + 2] == '| 01 | 70k | 3 | 3 | 3.0 |'  # the other feature's turn is not this task's
    assert lines[-1].startswith('| 01 | 1 |')
