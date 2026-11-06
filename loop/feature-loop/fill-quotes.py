#!/usr/bin/env python3
"""Fill the quote markers in a survey or brief from the base commit.

    python3 <plugin root>/loop/feature-loop/fill-quotes.py <file> <base commit> [--budget KB] [--over-budget]

A marker is a line of its own:

    <<quote src/components/player/embed/navBar.tsx:40-52>>

It becomes the path and range as a caption, then those lines of the file at the base commit
in a fenced block, numbered like `cat -n`. A single line is `path:40`. The quoted text never
passes through the agent that wrote the marker, so it costs that agent no output.

A quote is at most MAX_LINES lines. Every problem is listed at once and the file is left
unchanged: a path missing at the base commit, a range past the end of the file, a range
longer than MAX_LINES, or, with --budget, a filled file over that many KB. Over budget, it
prints each section's size so the writer knows what to trim. --over-budget writes the file
anyway and says by how much it is over.
"""
import os
import re
import subprocess
import sys

MAX_LINES = 15
MARKER = re.compile(r'^\s*<<quote (\S+?):(\d+)(?:-(\d+))?>>\s*$')
LANGS = {'.ts': 'ts', '.tsx': 'tsx', '.js': 'js', '.jsx': 'jsx', '.mjs': 'js', '.json': 'json',
         '.css': 'css', '.md': 'md', '.py': 'python', '.sh': 'bash', '.prisma': 'prisma',
         '.yml': 'yaml', '.yaml': 'yaml'}


def show(base, path, cache={}):
    if path not in cache:
        run = subprocess.run(['git', 'show', f'{base}:{path}'], capture_output=True, text=True)
        cache[path] = run.stdout.splitlines() if run.returncode == 0 else None
    return cache[path]


def fill(line, base, problems):
    marker = MARKER.match(line)
    if not marker:
        return line
    path, start = marker.group(1), int(marker.group(2))
    end = int(marker.group(3) or start)
    lines = show(base, path)
    where = f'{path}:{start}' + (f'-{end}' if end != start else '')
    if lines is None:
        problems.append(f'{where}: no such file at {base}')
    elif start < 1 or end < start or end > len(lines):
        problems.append(f'{where}: the file has {len(lines)} lines')
    elif end - start + 1 > MAX_LINES:
        problems.append(f'{where}: {end - start + 1} lines, over {MAX_LINES}. Quote the lines '
                        'that matter and cite the rest as a range.')
    else:
        body = [f'{n:6}\t{lines[n - 1]}' for n in range(start, end + 1)]
        ticks = max([3] + [len(run) + 1 for text in body for run in re.findall(r'`{3,}', text)])
        fence = '`' * ticks
        lang = LANGS.get(os.path.splitext(path)[1], '')
        return '\n'.join([f'`{where}`', fence + lang, *body, fence])
    return line


def sections(text):
    sizes, heading = [], '(before the first section)'
    size = 0
    for line in text.splitlines(keepends=True):
        if line.startswith('## '):
            sizes.append((size, heading))
            heading, size = line.strip(), 0
        size += len(line.encode())
    sizes.append((size, heading))
    return sorted(sizes, reverse=True)


def main():
    args, budget, over = sys.argv[1:], None, False
    if '--over-budget' in args:
        args.remove('--over-budget')
        over = True
    if '--budget' in args:
        i = args.index('--budget')
        budget = int(args[i + 1])
        del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    path, base = args
    with open(path) as f:
        text = f.read()

    problems = []
    filled = '\n'.join(fill(line, base, problems) for line in text.split('\n'))
    if problems:
        sys.exit('Nothing written.\n' + '\n'.join(problems))

    kb = len(filled.encode()) / 1000
    if budget is not None and kb > budget:
        report = '\n'.join(f'{size / 1000:6.1f} KB  {heading}' for size, heading in sections(filled))
        if not over:
            sys.exit(f'Nothing written: {kb:.1f} KB filled, over the {budget} KB budget.\n{report}')
        print(f'Written {kb:.1f} KB, {kb - budget:.1f} KB over the {budget} KB budget.')
    else:
        print(f'Written {kb:.1f} KB.')
    with open(path, 'w') as f:
        f.write(filled)


if __name__ == '__main__':
    main()
