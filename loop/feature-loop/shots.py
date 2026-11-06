#!/usr/bin/env python3
"""Before-and-after screenshots of one task's views.

    python3 <plugin root>/loop/feature-loop/shots.py <base commit> <shots spec> <run dir> <port> [--rebase]

The shots spec is `tests/validation/<feature>/<NN>-<slug>.shots.spec.ts`: one test per view,
titled `view <name>`, ending in `toHaveScreenshot("<name>.png")`. It runs under the `shots`
project of playwright.validation.config.ts.

The first run photographs every view at the base commit, in base_run.py's throwaway worktree
served on <port>+1, into <run dir>/shots/before/. Every run then photographs them at HEAD on <port> and
compares with Playwright's own comparator. `--rebase` takes the before pictures again.

It writes <run dir>/shots/shots.md, a table with every view's result and its pictures, and
prints one line per view. Changed views get after/<name>.png and diff/<name>.png, a view the
base did not have gets after/<name>.png alone, and an identical view gets neither.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from base_run import CONFIG, run, worktree


def playwright(cwd, spec, shots_dir, port, report, update):
    cmd = ['pnpm', 'exec', 'playwright', 'test', '-c', CONFIG, '--project=shots', spec,
           '--reporter=json']
    if update:
        cmd.append('--update-snapshots')
    run(cmd, cwd, report + '.log', {'SHOTS_DIR': shots_dir, 'VALIDATION_PORT': str(port),
                                    'PLAYWRIGHT_JSON_OUTPUT_NAME': report})
    try:
        with open(report) as f:
            return json.load(f)
    except (OSError, ValueError):
        sys.exit(f'Playwright wrote no report. Log: {report}.log')


def results(report):
    """(view name, status, first error line, attachments) for every test in the report."""
    def walk(suite):
        for spec in suite.get('specs', []):
            for test in spec.get('tests', []):
                last = (test.get('results') or [{}])[-1]
                errors = [re.sub(r'\x1b\[[0-9;]*m', '', e.get('message', ''))
                          for e in last.get('errors', [])]
                name = re.sub(r'^view\s+', '', spec['title']).strip()
                yield name, last.get('status'), ' '.join(errors), last.get('attachments', [])
        for child in suite.get('suites', []):
            yield from walk(child)
    for suite in report.get('suites', []):
        yield from walk(suite)


def first_line(text):
    return next((l.strip() for l in text.splitlines() if l.strip()), '')


def baseline(base, spec, out, port, logs):
    with worktree(base, spec, logs) as tree:
        report = playwright(tree, spec, out, port + 1, os.path.join(logs, 'before.json'), True)
        return {name: (status, first_line(err)) for name, status, err, _ in results(report)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 4:
        sys.exit(__doc__)
    base, spec, run_dir, port = args[0], args[1], args[2], int(args[3])
    base = subprocess.run(['git', 'rev-parse', '--short', base], capture_output=True, text=True,
                          check=True).stdout.strip()
    out = os.path.abspath(os.path.join(run_dir, 'shots'))
    before = os.path.join(out, 'before')
    logs = tempfile.mkdtemp(prefix='shots-logs-')

    if '--rebase' in sys.argv or not os.path.isdir(before) or not os.listdir(before):
        shutil.rmtree(before, ignore_errors=True)
        os.makedirs(before)
        for name, (status, err) in baseline(base, spec, out, port, logs).items():
            if not os.path.exists(os.path.join(before, name + '.png')):
                print(f'{name}: no before picture, {status}: {err[:160]}')

    for sub in ('after', 'diff'):
        shutil.rmtree(os.path.join(out, sub), ignore_errors=True)
        os.makedirs(os.path.join(out, sub))

    report = playwright(os.getcwd(), spec, out, port, os.path.join(logs, 'after.json'), False)
    rows, counts = [], {}
    for name, status, err, attachments in results(report):
        png = name + '.png'
        files = {a.get('name'): a.get('path') for a in attachments}
        if status == 'passed':
            result, pics = 'identical', ('before',)
        elif "doesn't exist" in err:
            # Playwright writes a missing snapshot where the baseline goes. It is the after.
            shutil.move(os.path.join(before, png), os.path.join(out, 'after', png))
            result, pics = 'new, no before picture', ('after',)
        elif files.get(f'{name}-actual.png'):
            shutil.copy(files[f'{name}-actual.png'], os.path.join(out, 'after', png))
            pics = ('before', 'after')
            if files.get(f'{name}-diff.png'):
                shutil.copy(files[f'{name}-diff.png'], os.path.join(out, 'diff', png))
                pics += ('diff',)
            ratio = re.search(r'ratio ([0-9.]+) of all image pixels', err)
            size = re.search(r'Expected an image (\S+ by \S+), received (\S+ by \S+)', err)
            result = (f'changed, {float(ratio.group(1)) * 100:.2f}% of pixels' if ratio
                      else f'changed size, {size.group(1)} to {size.group(2)}' if size
                      else 'changed')
        else:
            result, pics = f'error: {first_line(err)[:160]}', ()
        kind = result.split(',')[0].split(':')[0]
        counts[kind] = counts.get(kind, 0) + 1
        cells = [f'![{p}]({p}/{png})' if p in pics else '' for p in ('before', 'after', 'diff')]
        rows.append(f'| {name} | {result} | ' + ' | '.join(cells) + ' |')
        print(f'{name}: {result}')

    head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True,
                          text=True).stdout.strip()
    with open(os.path.join(out, 'shots.md'), 'w') as f:
        f.write(f'# Shots: {spec}\n\nBefore: {base}. After: {head}. Logs: {logs}\n\n'
                '| View | Result | Before | After | Diff |\n|---|---|---|---|---|\n')
        f.write('\n'.join(rows) + '\n')
    print(', '.join(f'{n} {k}' for k, n in counts.items()) or 'No views ran.')
    print(f'File: {os.path.relpath(out, os.getcwd())}/shots.md')


if __name__ == '__main__':
    main()
