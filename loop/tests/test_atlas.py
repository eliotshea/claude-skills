"""atlas.py: list, show, merge and prune against a throwaway repo."""
import pytest

from conftest import load_script, numbered, run_script

ATLAS = 'docs/tasks/atlas.md'


@pytest.fixture(scope='module')
def atlas():
    return load_script('atlas.py')


def run(repo, *args):
    return run_script('atlas.py', *args, cwd=repo.path)


def atlas_text(repo):
    return (repo.path / ATLAS).read_text()


def write_atlas(repo, entries):
    """Write the atlas file directly from {path: (obj, body lines)}."""
    text = '# Atlas\n\n' + '\n'.join(f'### {p} @ {o}\n' + '\n'.join(b) + '\n'
                                      for p, (o, b) in entries.items())
    repo.write(ATLAS, text)


def entries_file(repo, text, name='entries.md'):
    path = repo.path / name
    path.write_text(text)
    return name


# --- pure functions -------------------------------------------------------------------------

def test_read_entries_parses_headings_with_and_without_object(atlas):
    text = ('# Atlas\n\npreamble ignored\n\n### src/a.ts @ abc123\n\nbody a\n\n'
            '### src/dir/\nbody dir\n  \n')
    assert atlas.read_entries(text) == [
        ('src/a.ts', 'abc123', ['body a']),
        ('src/dir/', None, ['body dir']),
    ]


def test_read_entries_ignores_headings_with_spaces_in_the_path(atlas):
    # `### Some notes` has a space, so it is not a heading and stays in the body.
    assert atlas.read_entries('### a.ts\n### Some notes\nx\n') == [
        ('a.ts', None, ['### Some notes', 'x'])]


def test_read_entries_splits_on_a_one_word_heading_inside_a_body(atlas):
    # Oddity: a body line like `### Notes` is read as the start of a new entry.
    assert [p for p, _, _ in atlas.read_entries('### a.ts\n### Notes\nx\n')] == ['a.ts', 'Notes']


def test_trim_strips_blank_lines_at_both_ends_only(atlas):
    assert atlas.trim(['', ' ', 'a', '', 'b', '  ', '']) == ['a', '', 'b']
    assert atlas.trim(['', '']) == []


# --- argument handling ----------------------------------------------------------------------

@pytest.mark.parametrize('args', [
    [],
    ['list'],
    ['list', 'HEAD', 'extra'],
    ['show', 'HEAD'],
    ['merge', 'HEAD', 'entries.md'],                      # no --task
    ['merge', 'HEAD', 'entries.md', '--task', 'nofeature'],  # task without a slash
    ['merge', 'HEAD', '--task', 'f/01'],                  # no entries file
    ['prune', 'HEAD', '--stale', 'a.ts'],                 # --stale with paths
    ['bogus', 'HEAD'],
])
def test_bad_arguments_print_usage(repo, args):
    repo.commit({'a.ts': 'x\n'})
    result = run(repo, *args)
    assert result.returncode == 1
    assert 'atlas.py list' in result.stderr


def test_task_flag_without_a_value_crashes(repo):
    # Oddity: `--task` as the last argument is an IndexError traceback, not the usage text.
    repo.commit({'a.ts': 'x\n'})
    result = run(repo, 'merge', 'HEAD', 'entries.md', '--task')
    assert result.returncode == 1
    assert 'IndexError' in result.stderr


def test_unknown_commit_is_refused(repo):
    repo.commit({'a.ts': 'x\n'})
    result = run(repo, 'list', 'deadbeef')
    assert result.returncode == 1
    assert result.stderr.strip() == 'No such commit: deadbeef'


def test_a_blob_id_is_not_a_commit(repo):
    repo.commit({'a.ts': 'x\n'})
    result = run(repo, 'list', repo.object('HEAD', 'a.ts'))
    assert result.returncode == 1
    assert 'No such commit' in result.stderr


# --- list -----------------------------------------------------------------------------------

def test_list_without_an_atlas(repo):
    base = repo.commit({'a.ts': 'x\n'})
    result = run(repo, 'list', base)
    assert result.returncode == 0
    assert result.stdout == f'No atlas at {ATLAS}.\n'


def test_list_reports_fresh_stale_and_gone(repo):
    first = repo.commit({'fresh.ts': 'f\n', 'stale.ts': 'old\n', 'gone.ts': 'g\n', 'd/x.ts': 'x\n'})
    write_atlas(repo, {
        'fresh.ts': (repo.object(first, 'fresh.ts'), ['f']),
        'stale.ts': (repo.object(first, 'stale.ts'), ['s']),
        'gone.ts': (repo.object(first, 'gone.ts'), ['g']),
        'd/': (repo.object(first, 'd/'), ['dir']),
    })
    base = repo.commit({'stale.ts': 'new\n', 'gone.ts': None})
    result = run(repo, 'list', base)
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        'fresh  fresh.ts', 'stale  stale.ts', 'gone   gone.ts', 'fresh  d/']


def test_list_sees_a_directory_go_stale_when_a_file_under_it_changes(repo):
    first = repo.commit({'d/x.ts': 'x\n'})
    write_atlas(repo, {'d/': (repo.object(first, 'd/'), [])})
    base = repo.commit({'d/y.ts': 'y\n'})
    assert run(repo, 'list', base).stdout == 'stale  d/\n'


# --- show -----------------------------------------------------------------------------------

def test_show_fresh_entry(repo):
    base = repo.commit({'a.ts': 'a\n'})
    obj = repo.object(base, 'a.ts')
    write_atlas(repo, {'a.ts': (obj, ['body line'])})
    result = run(repo, 'show', base, 'a.ts')
    assert result.returncode == 0
    assert result.stdout == (f'### a.ts @ {obj}\n'
                             'State: fresh. Every range below holds at the base commit.\n'
                             'body line\n\n')


def test_show_stale_file_lists_hunk_headers(repo):
    first = repo.commit({'a.ts': numbered(10)})
    old = repo.object(first, 'a.ts')
    write_atlas(repo, {'a.ts': (old, ['body'])})
    base = repo.commit({'a.ts': numbered(10).replace('line 3\n', 'LINE 3\n')})
    new = repo.object(base, 'a.ts')
    out = run(repo, 'show', base, 'a.ts').stdout.splitlines()
    assert out[0] == f'### a.ts @ {old}'
    assert out[1] == f'State: stale. Changed since the entry ({old} -> {new}):'
    assert out[2].startswith('    @@ -3 +3 @@')
    assert out[3] == 'body'


def test_show_stale_file_caps_hunks(repo, atlas):
    lines = numbered(60)
    first = repo.commit({'a.ts': lines})
    old = repo.object(first, 'a.ts')
    write_atlas(repo, {'a.ts': (old, [])})
    changed = ''.join(f'CHANGED {i}\n' if i % 3 == 0 else f'line {i}\n' for i in range(1, 61))
    base = repo.commit({'a.ts': changed})
    out = run(repo, 'show', base, 'a.ts').stdout.splitlines()
    hunks = [l for l in out if l.startswith('    @@')]
    assert len(hunks) == atlas.MAX_HUNKS
    assert f'    ... {20 - atlas.MAX_HUNKS} more hunks' in out


def test_show_stale_directory_lists_changed_files(repo):
    first = repo.commit({'d/x.ts': 'x\n', 'd/y.ts': 'y\n'})
    old = repo.object(first, 'd/')
    write_atlas(repo, {'d/': (old, ['dir body'])})
    base = repo.commit({'d/y.ts': 'y2\n'})
    out = run(repo, 'show', base, 'd/').stdout
    assert 'State: stale.' in out
    changed = out.split('State')[1].split('dir body')[0]
    assert 'y.ts' in changed and 'x.ts' not in changed
    assert '1 file changed' in out


def test_show_stale_with_unknown_old_object(repo):
    base = repo.commit({'a.ts': 'a\n'})
    write_atlas(repo, {'a.ts': ('0123456789', ['b'])})
    out = run(repo, 'show', base, 'a.ts').stdout
    assert '    (object 0123456789 not found)' in out


def test_show_stale_directory_with_unknown_old_object(repo):
    base = repo.commit({'d/a.ts': 'a\n'})
    write_atlas(repo, {'d/': ('0123456789', [])})
    out = run(repo, 'show', base, 'd/').stdout
    assert '    (object 0123456789 not found)' in out


def test_show_gone_entry(repo):
    first = repo.commit({'a.ts': 'a\n', 'b.ts': 'b\n'})
    write_atlas(repo, {'a.ts': (repo.object(first, 'a.ts'), ['body'])})
    base = repo.commit({'a.ts': None})
    out = run(repo, 'show', base, 'a.ts').stdout
    assert f'State: gone. No such path at {base}.' in out
    assert 'body' in out


def test_show_path_without_entry(repo):
    base = repo.commit({'a.ts': 'a\n'})
    out = run(repo, 'show', base, 'a.ts', 'missing.ts').stdout
    assert out == ('### a.ts\nState: no entry\n\n'
                   f'### missing.ts\nState: no entry, and no such path at {base}\n\n')


# --- merge ----------------------------------------------------------------------------------

def test_merge_creates_the_atlas_with_stamped_sorted_entries(repo, atlas):
    base = repo.commit({'src/b.ts': numbered(5), 'src/a.ts': numbered(5), 'src/d/x.ts': 'x\n'})
    (repo.path / 'docs/tasks').mkdir(parents=True)
    name = entries_file(repo, '### src/b.ts\nb body `:2-4`\n\n### src/a.ts\na body\n'
                              '### src/d/\ndir body\n')
    result = run(repo, 'merge', base, name, '--task', 'my-feature/03')
    assert result.returncode == 0, result.stderr
    assert result.stdout == f'Written {ATLAS}: 3 added, 0 replaced, 3 entries.\n'
    text = atlas_text(repo)
    assert text.startswith(atlas.PREAMBLE)
    assert atlas.read_entries(text) == [
        ('src/a.ts', repo.object(base, 'src/a.ts'),
         [f'Written: my-feature task 03 @ {base}', 'a body']),
        ('src/b.ts', repo.object(base, 'src/b.ts'),
         [f'Written: my-feature task 03 @ {base}', 'b body `:2-4`']),
        ('src/d/', repo.object(base, 'src/d/'),
         [f'Written: my-feature task 03 @ {base}', 'dir body']),
    ]


def test_merge_replaces_existing_entries_and_keeps_others(repo, atlas):
    base = repo.commit({'a.ts': 'a\n', 'b.ts': 'b\n'})
    (repo.path / 'docs/tasks').mkdir(parents=True)
    run(repo, 'merge', base, entries_file(repo, '### a.ts\nold a\n### b.ts\nold b\n'),
        '--task', 'f/01')
    result = run(repo, 'merge', base,
                 entries_file(repo, '### a.ts @ whatever\nWritten: stale stamp\nnew a\n', 'e2.md'),
                 '--task', 'nested/feat/02')
    assert result.stdout == f'Written {ATLAS}: 0 added, 1 replaced, 2 entries.\n'
    entries = {p: b for p, _, b in atlas.read_entries(atlas_text(repo))}
    # The task splits on its last slash, and an incoming Written: line is replaced.
    assert entries['a.ts'] == [f'Written: nested/feat task 02 @ {base}', 'new a']
    assert entries['b.ts'] == [f'Written: f task 01 @ {base}', 'old b']


def test_merge_with_no_entries_writes_nothing(repo):
    base = repo.commit({'a.ts': 'a\n'})
    result = run(repo, 'merge', base, entries_file(repo, 'just prose\n'), '--task', 'f/01')
    assert result.returncode == 1
    assert result.stderr.strip() == 'Nothing written: no `### <path>` entries in entries.md.'
    assert not (repo.path / ATLAS).exists()


def test_merge_lists_every_problem_and_leaves_the_atlas_unchanged(repo, atlas):
    base = repo.commit({'a.ts': numbered(10), 'q.ts': numbered(30), 'd/x.ts': 'x\n'})
    (repo.path / 'docs/tasks').mkdir(parents=True)
    run(repo, 'merge', base, entries_file(repo, '### a.ts\nkeep me\n'), '--task', 'f/01')
    before = atlas_text(repo)
    long_body = '\n'.join(f'l{i}' for i in range(atlas.MAX_LINES + 1))
    text = '\n'.join([
        '### missing.ts', 'x',
        '### a.ts', 'ok `:1-10` bad `:11` worse `:0` backwards `:5-3`',
        '<<quote q.ts:1-16>>',
        '<<quote q.ts:29-31>>',
        '<<quote nope.ts:1>>',
        '<<quote q.ts:1-15>>',
        '### d/', 'dirs skip ranges `:999`',
        '### q.ts', long_body,
        '### d/', 'twice',
    ])
    result = run(repo, 'merge', base, entries_file(repo, text, 'bad.md'), '--task', 'f/02')
    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        'Nothing written.',
        f'missing.ts: no such path at {base}',
        'a.ts: `:11` is outside its 10 lines',
        'a.ts: `:0` is outside its 10 lines',
        'a.ts: `:5-3` is outside its 10 lines',
        'a.ts: quote q.ts:1-16: over 15 lines',
        'a.ts: quote q.ts:29-31: the file has 30 lines',
        f'a.ts: quote nope.ts: no such file at {base}',
        f'q.ts: {atlas.MAX_LINES + 1} lines, over {atlas.MAX_LINES}. Keep the index, drop the prose.',
        'd/: two entries',
    ]
    assert atlas_text(repo) == before


def test_merge_counts_a_written_line_toward_the_line_limit(repo, atlas):
    # Oddity: the line limit is checked before an incoming `Written:` line is dropped.
    base = repo.commit({'a.ts': 'a\n'})
    body = ['Written: old'] + [f'l{i}' for i in range(atlas.MAX_LINES)]
    result = run(repo, 'merge', base, entries_file(repo, '### a.ts\n' + '\n'.join(body)),
                 '--task', 'f/01')
    assert result.returncode == 1
    assert f'{atlas.MAX_LINES + 1} lines' in result.stderr


def test_merge_entry_at_the_line_limit_is_accepted(repo, atlas):
    base = repo.commit({'a.ts': 'a\n'})
    (repo.path / 'docs/tasks').mkdir(parents=True)
    body = '\n'.join(f'l{i}' for i in range(atlas.MAX_LINES))
    result = run(repo, 'merge', base, entries_file(repo, '### a.ts\n' + body), '--task', 'f/01')
    assert result.returncode == 0, result.stderr


def test_merge_without_a_docs_tasks_directory_crashes(repo):
    # Oddity: merge does not create docs/tasks/, so a first merge in a repo without it
    # ends in a FileNotFoundError traceback rather than a message.
    base = repo.commit({'a.ts': 'a\n'})
    result = run(repo, 'merge', base, entries_file(repo, '### a.ts\nx\n'), '--task', 'f/01')
    assert result.returncode == 1
    assert 'FileNotFoundError' in result.stderr


def test_merge_validates_against_the_base_not_the_working_tree(repo):
    base = repo.commit({'a.ts': numbered(3)})
    repo.write('a.ts', numbered(50))  # uncommitted
    result = run(repo, 'merge', base, entries_file(repo, '### a.ts\n`:40`\n'), '--task', 'f/01')
    assert result.returncode == 1
    assert 'a.ts: `:40` is outside its 3 lines' in result.stderr


def test_merge_round_trips_through_save_and_load(repo, atlas):
    base = repo.commit({'a.ts': 'a\n'})
    (repo.path / 'docs/tasks').mkdir(parents=True)
    run(repo, 'merge', base, entries_file(repo, '### a.ts\n\nx\n\ny\n\n'), '--task', 'f/01')
    first = atlas_text(repo)
    run(repo, 'merge', base, entries_file(repo, '### a.ts\n\nx\n\ny\n\n'), '--task', 'f/01')
    assert atlas_text(repo) == first


# --- prune ----------------------------------------------------------------------------------

def make_prunable(repo):
    first = repo.commit({'fresh.ts': 'f\n', 'stale.ts': 's\n', 'gone.ts': 'g\n',
                         'd/x.ts': 'x\n', 'd/sub/y.ts': 'y\n'})
    (repo.path / 'docs/tasks').mkdir(parents=True, exist_ok=True)
    run(repo, 'merge', first, entries_file(repo, '\n'.join(
        f'### {p}\nbody' for p in ['fresh.ts', 'stale.ts', 'gone.ts', 'd/', 'd/x.ts', 'd/sub/y.ts'])),
        '--task', 'f/01')
    return repo.commit({'stale.ts': 's2\n', 'gone.ts': None})


def remaining(repo, atlas):
    return [p for p, _, _ in atlas.read_entries(atlas_text(repo))]


def test_prune_removes_gone_entries_only(repo, atlas):
    base = make_prunable(repo)
    result = run(repo, 'prune', base)
    assert result.returncode == 0
    assert result.stdout == f'gone   gone.ts\nPruned 1 from {ATLAS}, 5 left.\n'
    assert 'gone.ts' not in remaining(repo, atlas)
    assert 'stale.ts' in remaining(repo, atlas)


def test_prune_stale_removes_stale_and_gone(repo, atlas):
    base = make_prunable(repo)
    result = run(repo, 'prune', base, '--stale')
    assert result.stdout.splitlines() == [
        'gone   gone.ts', 'stale  stale.ts', f'Pruned 2 from {ATLAS}, 4 left.']
    assert remaining(repo, atlas) == ['d/', 'd/sub/y.ts', 'd/x.ts', 'fresh.ts']


def test_prune_named_paths_and_directory_prefixes(repo, atlas):
    base = make_prunable(repo)
    result = run(repo, 'prune', base, 'fresh.ts', 'd/sub/', 'not-there.ts')
    assert result.stdout.splitlines() == [
        'named  d/sub/y.ts', 'named  fresh.ts', f'Pruned 2 from {ATLAS}, 4 left.']
    assert remaining(repo, atlas) == ['d/', 'd/x.ts', 'gone.ts', 'stale.ts']


def test_prune_directory_path_removes_itself_and_everything_under_it(repo, atlas):
    base = make_prunable(repo)
    run(repo, 'prune', base, 'd/')
    assert remaining(repo, atlas) == ['fresh.ts', 'gone.ts', 'stale.ts']


def test_prune_file_path_is_not_a_prefix(repo, atlas):
    base = make_prunable(repo)
    assert run(repo, 'prune', base, 'd').stdout == 'Nothing to prune.\n'


def test_prune_with_nothing_to_do_leaves_the_file_alone(repo):
    base = repo.commit({'a.ts': 'a\n'})
    (repo.path / 'docs/tasks').mkdir(parents=True)
    run(repo, 'merge', base, entries_file(repo, '### a.ts\nx\n'), '--task', 'f/01')
    before = atlas_text(repo)
    result = run(repo, 'prune', base)
    assert result.stdout == 'Nothing to prune.\n'
    assert atlas_text(repo) == before


def test_prune_without_an_atlas(repo):
    base = repo.commit({'a.ts': 'a\n'})
    result = run(repo, 'prune', base)
    assert result.returncode == 0
    assert result.stdout == 'Nothing to prune.\n'
    assert not (repo.path / ATLAS).exists()
