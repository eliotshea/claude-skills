#!/usr/bin/env python3
"""The atlas: what earlier scouts found in each file, kept while the file is unchanged.

    python3 <plugin root>/loop/feature-loop/atlas.py list  <base commit>
    python3 <plugin root>/loop/feature-loop/atlas.py show  <base commit> <path>...
    python3 <plugin root>/loop/feature-loop/atlas.py merge <base commit> <entries file> --task <feature>/<NN>
    python3 <plugin root>/loop/feature-loop/atlas.py prune <base commit> [--stale] [<path>...]

The atlas is docs/tasks/atlas.md, shared by every feature. Each entry is headed

    ### <path> @ <object id>

where the object id is the file's blob, or for a path ending in `/` the directory's tree, at
the commit the entry was written from. An entry is fresh while that object is unchanged at the
base commit, and then every line range in it still holds.

list prints one line per entry: fresh, stale or gone.
show prints each path's entry with its state. A stale entry comes with the hunk headers of the
change since it was written, or for a directory the files that changed. A path with no entry
says so.
merge takes a file of entries headed `### <path>`, stamps each with its object at the base
commit, and adds or replaces them in the atlas. Every problem is listed at once and the atlas
is left unchanged: a path missing at the base commit, a `:<line>` range past the end of its
file, a quote marker that fill-quotes.py would refuse, or an entry over MAX_LINES lines.
prune removes entries without anyone reading the atlas. With no paths it removes every entry
whose path is gone at the base commit, which covers deleted and renamed files and
directories; --stale removes stale entries too. With paths it removes those entries, and for
a path ending in `/` every entry under it. It prints each entry it removed.
"""
import re
import subprocess
import sys

MAX_LINES = 40
MAX_HUNKS = 12
MAX_QUOTE = 15
HEADING = re.compile(r'^### (\S+?)(?: @ (\S+))?\s*$')
RANGE = re.compile(r'`:(\d+)(?:-(\d+))?`')
MARKER = re.compile(r'^\s*<<quote (\S+?):(\d+)(?:-(\d+))?>>\s*$')
ATLAS = 'docs/tasks/atlas.md'
PREAMBLE = """# Atlas

What feature-loop scouts found in each file, shared by every feature and keyed by the file's
git object at the commit the entry was written from. Written only through
`<plugin root>/loop/feature-loop/atlas.py merge` and `prune`; read through `atlas.py show`. See
`task-scout.md` for what an entry holds.
"""


def git(*args):
    run = subprocess.run(['git', *args], capture_output=True, text=True)
    return run.stdout if run.returncode == 0 else None


def object_at(base, path):
    out = git('rev-parse', '--short=10', f'{base}:{path.rstrip("/")}')
    return out.strip() if out else None


def line_count(base, path):
    out = git('show', f'{base}:{path}')
    return None if out is None else len(out.splitlines())


def read_entries(text):
    """Entries in order, as (path, object id or None, body lines)."""
    entries, current = [], None
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            current = (heading.group(1), heading.group(2), [])
            entries.append(current)
        elif current is not None:
            current[2].append(line)
    return [(path, obj, trim(body)) for path, obj, body in entries]


def trim(body):
    while body and not body[-1].strip():
        body = body[:-1]
    while body and not body[0].strip():
        body = body[1:]
    return body


def load():
    try:
        with open(ATLAS) as f:
            return read_entries(f.read())
    except FileNotFoundError:
        return []


def save(entries):
    out = [PREAMBLE]
    for path in sorted(entries):
        obj, body = entries[path]
        out.append(f'### {path} @ {obj}\n' + '\n'.join(body) + '\n')
    with open(ATLAS, 'w') as f:
        f.write('\n'.join(out))


def state(base, path, obj):
    now = object_at(base, path)
    if now is None:
        return 'gone', now
    return ('fresh' if now == obj else 'stale'), now


def changes(path, old, new):
    if path.endswith('/'):
        out = git('diff', '--stat=120', old, new)
        return out.rstrip().splitlines() if out else [f'(object {old} not found)']
    out = git('diff', '-U0', old, new)
    if out is None:
        return [f'(object {old} not found)']
    hunks = [line for line in out.splitlines() if line.startswith('@@')]
    if len(hunks) > MAX_HUNKS:
        hunks = hunks[:MAX_HUNKS] + [f'... {len(hunks) - MAX_HUNKS} more hunks']
    return hunks


def cmd_list(base):
    entries = load()
    if not entries:
        print(f'No atlas at {ATLAS}.')
        return
    for path, obj, body in entries:
        print(f'{state(base, path, obj)[0]:5}  {path}')


def cmd_show(base, paths):
    entries = {path: (obj, body) for path, obj, body in load()}
    for path in paths:
        if path not in entries:
            now = object_at(base, path)
            print(f'### {path}\nState: no entry' + ('' if now else f', and no such path at {base}') + '\n')
            continue
        obj, body = entries[path]
        st, now = state(base, path, obj)
        print(f'### {path} @ {obj}')
        if st == 'fresh':
            print('State: fresh. Every range below holds at the base commit.')
        elif st == 'gone':
            print(f'State: gone. No such path at {base}.')
        else:
            print(f'State: stale. Changed since the entry ({obj} -> {now}):')
            print('\n'.join('    ' + line for line in changes(path, obj, now)))
        print('\n'.join(body) + '\n')


def check(base, path, body, problems):
    if len(body) > MAX_LINES:
        problems.append(f'{path}: {len(body)} lines, over {MAX_LINES}. Keep the index, drop the prose.')
    lines = None if path.endswith('/') else line_count(base, path)
    for text in body:
        marker = MARKER.match(text)
        if marker:
            where, start = marker.group(1), int(marker.group(2))
            end = int(marker.group(3) or start)
            n = line_count(base, where)
            if n is None:
                problems.append(f'{path}: quote {where}: no such file at {base}')
            elif start < 1 or end < start or end > n:
                problems.append(f'{path}: quote {where}:{start}-{end}: the file has {n} lines')
            elif end - start + 1 > MAX_QUOTE:
                problems.append(f'{path}: quote {where}:{start}-{end}: over {MAX_QUOTE} lines')
            continue
        if lines is None:
            continue
        for start, end in RANGE.findall(text):
            start, end = int(start), int(end or start)
            if start < 1 or end < start or end > lines:
                problems.append(f'{path}: `:{start}{"-" + str(end) if end != start else ""}` '
                                f'is outside its {lines} lines')


def cmd_merge(base, entries_file, task):
    with open(entries_file) as f:
        incoming = read_entries(f.read())
    if not incoming:
        sys.exit(f'Nothing written: no `### <path>` entries in {entries_file}.')
    problems, stamped = [], {}
    for path, _, body in incoming:
        obj = object_at(base, path)
        if obj is None:
            problems.append(f'{path}: no such path at {base}')
            continue
        if path in stamped:
            problems.append(f'{path}: two entries')
        check(base, path, body, problems)
        body = [line for line in body if not line.startswith('Written: ')]
        feature, _, number = task.rpartition('/')
        stamped[path] = (obj, [f'Written: {feature} task {number} @ {base}'] + body)
    if problems:
        sys.exit('Nothing written.\n' + '\n'.join(problems))

    merged = {path: (obj, body) for path, obj, body in load()}
    added = sum(1 for path in stamped if path not in merged)
    merged.update(stamped)
    save(merged)
    print(f'Written {ATLAS}: {added} added, {len(stamped) - added} replaced, '
          f'{len(merged)} entries.')


def cmd_prune(base, paths, stale):
    entries = {path: (obj, body) for path, obj, body in load()}
    doomed = {}
    for path, (obj, _) in entries.items():
        if paths:
            if any(path == p or (p.endswith('/') and path.startswith(p)) for p in paths):
                doomed[path] = 'named'
        else:
            st = state(base, path, obj)[0]
            if st == 'gone' or (stale and st == 'stale'):
                doomed[path] = st
    if not doomed:
        print('Nothing to prune.')
        return
    for path in doomed:
        del entries[path]
    save(entries)
    for path, why in sorted(doomed.items()):
        print(f'{why:5}  {path}')
    print(f'Pruned {len(doomed)} from {ATLAS}, {len(entries)} left.')


def main():
    args = sys.argv[1:]
    task = None
    if '--task' in args:
        i = args.index('--task')
        task = args[i + 1]
        del args[i:i + 2]
    stale = '--stale' in args
    if stale:
        args.remove('--stale')
    if len(args) < 2:
        sys.exit(__doc__)
    command, base, rest = args[0], args[1], args[2:]
    if git('rev-parse', '--verify', '--quiet', f'{base}^{{commit}}') is None:
        sys.exit(f'No such commit: {base}')
    if command == 'list' and not rest:
        cmd_list(base)
    elif command == 'show' and rest:
        cmd_show(base, rest)
    elif command == 'merge' and len(rest) == 1 and task and '/' in task:
        cmd_merge(base, rest[0], task)
    elif command == 'prune' and not (stale and rest):
        cmd_prune(base, rest, stale)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
