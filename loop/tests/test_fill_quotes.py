"""fill-quotes.py: quote markers filled from the base commit, budgets, refusals."""
import pytest

from conftest import load_script, numbered, run_script


@pytest.fixture
def fq(repo, monkeypatch):
    # The imported functions run git in the cwd, so work inside the test repo. A fresh module
    # each test, because show() caches by path in a mutable default argument.
    monkeypatch.chdir(repo.path)
    return load_script('fill-quotes.py')


def run(repo, *args):
    return run_script('fill-quotes.py', *args, cwd=repo.path)


def doc(repo, text, name='survey.md'):
    (repo.path / name).write_text(text)
    return name


def read(repo, name='survey.md'):
    return (repo.path / name).read_text()


# --- fill -----------------------------------------------------------------------------------

def test_fill_leaves_ordinary_lines_alone(repo, fq):
    base = repo.commit({'a.ts': 'x\n'})
    problems = []
    for line in ['prose', '`<<quote a.ts:1>>`', 'text <<quote a.ts:1>>', '<<quote a.ts>>']:
        assert fq.fill(line, base, problems) == line
    assert problems == []


def test_fill_quotes_a_range_numbered_like_cat_n(repo, fq):
    base = repo.commit({'src/a.tsx': numbered(20)})
    problems = []
    out = fq.fill('  <<quote src/a.tsx:9-11>>  ', base, problems)
    assert problems == []
    assert out == ('`src/a.tsx:9-11`\n```tsx\n'
                   '     9\tline 9\n    10\tline 10\n    11\tline 11\n```')


def test_fill_single_line_caption_has_no_range(repo, fq):
    base = repo.commit({'a.py': 'one\ntwo\n'})
    assert fq.fill('<<quote a.py:2>>', base, []) == '`a.py:2`\n```python\n     2\ttwo\n```'


@pytest.mark.parametrize('name, lang', [
    ('a.ts', 'ts'), ('a.mjs', 'js'), ('a.yml', 'yaml'), ('a.prisma', 'prisma'),
    ('Makefile', ''), ('a.txt', ''),
])
def test_fill_picks_the_fence_language_from_the_extension(repo, fq, name, lang):
    base = repo.commit({name: 'x\n'})
    assert fq.fill(f'<<quote {name}:1>>', base, []).splitlines()[1] == '```' + lang


def test_fill_lengthens_the_fence_past_backticks_in_the_quote(repo, fq):
    base = repo.commit({'a.md': 'before\n````js\nafter\n'})
    lines = fq.fill('<<quote a.md:1-3>>', base, []).splitlines()
    assert lines[1] == '`````md'
    assert lines[-1] == '`````'


def test_fill_reads_the_base_commit_not_the_working_tree(repo, fq):
    base = repo.commit({'a.ts': 'committed\n'})
    repo.write('a.ts', 'working tree\n')
    assert 'committed' in fq.fill('<<quote a.ts:1>>', base, [])


@pytest.mark.parametrize('marker, problem', [
    ('<<quote nope.ts:1>>', 'nope.ts:1: no such file at {base}'),
    ('<<quote a.ts:0>>', 'a.ts:0: the file has 20 lines'),
    ('<<quote a.ts:21>>', 'a.ts:21: the file has 20 lines'),
    ('<<quote a.ts:5-3>>', 'a.ts:5-3: the file has 20 lines'),
    ('<<quote a.ts:1-16>>', 'a.ts:1-16: 16 lines, over 15. Quote the lines that matter and '
                            'cite the rest as a range.'),
])
def test_fill_reports_problems_and_keeps_the_marker(repo, fq, marker, problem):
    base = repo.commit({'a.ts': numbered(20)})
    problems = []
    assert fq.fill(marker, base, problems) == marker
    assert problems == [problem.format(base=base)]


def test_fill_accepts_exactly_max_lines(repo, fq):
    base = repo.commit({'a.ts': numbered(20)})
    problems = []
    out = fq.fill(f'<<quote a.ts:1-{fq.MAX_LINES}>>', base, problems)
    assert problems == []
    assert len(out.splitlines()) == fq.MAX_LINES + 3


def test_show_caches_by_path_only(repo, fq):
    # Oddity: the cache ignores the base, so one process can only serve one base.
    first = repo.commit({'a.ts': 'first\n'})
    second = repo.commit({'a.ts': 'second\n'})
    assert fq.show(first, 'a.ts') == ['first']
    assert fq.show(second, 'a.ts') == ['first']


# --- sections -------------------------------------------------------------------------------

def test_sections_sizes_each_heading_largest_first(fq):
    text = 'intro\n## Small\nab\n## Big\n' + 'x' * 100 + '\n### sub stays in Big\n'
    sizes = fq.sections(text)
    assert [h for _, h in sizes] == ['## Big', '## Small', '(before the first section)']
    assert sizes[0][0] == len('## Big\n') + 101 + len('### sub stays in Big\n')
    assert sizes[2][0] == len('intro\n')
    assert sum(s for s, _ in sizes) == len(text.encode())


def test_sections_counts_bytes_not_characters(fq):
    assert fq.sections('é\n') == [(3, '(before the first section)')]


# --- CLI ------------------------------------------------------------------------------------

@pytest.mark.parametrize('args', [[], ['survey.md'], ['survey.md', 'HEAD', 'extra']])
def test_bad_arguments_print_usage(repo, args):
    repo.commit({'a.ts': 'x\n'})
    doc(repo, 'x')
    result = run(repo, *args)
    assert result.returncode == 1
    assert 'fill-quotes.py <file> <base commit>' in result.stderr


def test_cli_fills_every_marker_and_keeps_the_rest(repo):
    base = repo.commit({'a.ts': numbered(5), 'b.css': 'body {}\n'})
    doc(repo, '# Survey\n\n<<quote a.ts:2-3>>\nmiddle\n<<quote b.css:1>>\n')
    result = run(repo, 'survey.md', base)
    assert result.returncode == 0, result.stderr
    expected = ('# Survey\n\n`a.ts:2-3`\n```ts\n     2\tline 2\n     3\tline 3\n```\nmiddle\n'
                '`b.css:1`\n```css\n     1\tbody {}\n```\n')
    assert read(repo) == expected
    assert result.stdout == f'Written {len(expected.encode()) / 1000:.1f} KB.\n'


def test_cli_without_markers_rewrites_the_file_unchanged(repo):
    base = repo.commit({'a.ts': 'x\n'})
    doc(repo, 'no trailing newline')
    assert run(repo, 'survey.md', base).returncode == 0
    assert read(repo) == 'no trailing newline'


def test_cli_lists_every_problem_and_writes_nothing(repo):
    base = repo.commit({'a.ts': numbered(5)})
    text = '<<quote a.ts:1>>\n<<quote a.ts:9>>\n<<quote gone.ts:1-2>>\n'
    doc(repo, text)
    result = run(repo, 'survey.md', base)
    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        'Nothing written.', 'a.ts:9: the file has 5 lines', f'gone.ts:1-2: no such file at {base}']
    assert read(repo) == text


def test_cli_accepts_a_short_ref_as_base(repo):
    repo.commit({'a.ts': 'old\n'})
    repo.commit({'a.ts': 'new\n'})
    doc(repo, '<<quote a.ts:1>>\n')
    assert run(repo, 'survey.md', 'HEAD~1').returncode == 0
    assert 'old' in read(repo)


def test_cli_within_budget(repo):
    base = repo.commit({'a.ts': 'x\n'})
    doc(repo, 'small\n')
    result = run(repo, 'survey.md', base, '--budget', '1')
    assert result.returncode == 0
    assert result.stdout == 'Written 0.0 KB.\n'


def test_cli_over_budget_writes_nothing_and_sizes_sections(repo):
    base = repo.commit({'a.ts': 'x\n'})
    text = '## One\n' + 'a' * 1500 + '\n## Two\n' + 'b' * 300 + '\n'
    doc(repo, text)
    result = run(repo, 'survey.md', '--budget', '1', base)
    assert result.returncode == 1
    assert result.stderr.splitlines() == [
        'Nothing written: 1.8 KB filled, over the 1 KB budget.',
        '   1.5 KB  ## One',
        '   0.3 KB  ## Two',
        '   0.0 KB  (before the first section)',
    ]
    assert read(repo) == text


def test_cli_over_budget_flag_writes_anyway(repo):
    base = repo.commit({'a.ts': 'x\n'})
    text = 'a' * 2500
    doc(repo, text)
    result = run(repo, 'survey.md', base, '--over-budget', '--budget', '2')
    assert result.returncode == 0
    assert result.stdout == 'Written 2.5 KB, 0.5 KB over the 2 KB budget.\n'
    assert read(repo) == text


def test_cli_budget_counts_the_filled_text(repo):
    base = repo.commit({'a.ts': ('y' * 150 + '\n') * 10})
    doc(repo, '<<quote a.ts:1-10>>\n')  # 20 bytes before, about 1.6 KB after
    result = run(repo, 'survey.md', base, '--budget', '1')
    assert result.returncode == 1
    assert 'over the 1 KB budget' in result.stderr


def test_cli_problems_win_over_budget(repo):
    base = repo.commit({'a.ts': 'x\n'})
    doc(repo, '<<quote a.ts:5>>\n' + 'z' * 5000)
    result = run(repo, 'survey.md', base, '--budget', '1')
    assert result.stderr.startswith('Nothing written.\na.ts:5')


def test_cli_missing_file_crashes(repo):
    base = repo.commit({'a.ts': 'x\n'})
    result = run(repo, 'nope.md', base)
    assert result.returncode == 1
    assert 'FileNotFoundError' in result.stderr
