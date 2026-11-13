#!/usr/bin/env python3
"""Context size and time for every feature-loop subagent run of one feature.

Reads the subagent transcripts Claude Code keeps under ~/.claude/projects, not the run
directory, so it sees runs that never got a log row (retries, interrupted attempts).

    python3 <plugin root>/loop/feature-loop/run-stats.py issue-156-embed-timeline [task]

Context is input plus cache tokens on the agent's largest turn. A task's total context adds
up every run's. Active minutes leave out
every gap of STALL_MIN or more between two transcript events: a stream that was cut off,
a permission or classifier timeout, a human interrupt. Those count under Stalls instead.
A run the human stopped is left out, and counted in a line between the tables.

Between the two tables, the orchestrator: for each task, the main session's largest context,
its turns and tool calls while it was routing that task, and its turns per dispatch.

Given a task, this prints what the orchestrator commits as runs/<NN>/stats.md, and its last
line is that task's total.
"""
import collections
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

LOOP_AGENTS = {'task-scout', 'brief-writer', 'task-implementer', 'task-validator',
               'validation-reporter', 'architect-reviewer', 'code-reviewer', 'test-writer',
               'code-writer'}
STALL_MIN = 10


def project_dirs():
    common = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                            capture_output=True, text=True, check=True).stdout.strip()
    root = os.path.dirname(common)
    encoded = re.sub(r'[^A-Za-z0-9]', '-', root)
    return glob.glob(os.path.expanduser(f'~/.claude/projects/{encoded}*'))


def when(stamp):
    return dt.datetime.fromisoformat(stamp.replace('Z', '+00:00'))


def read_run(path):
    try:
        with open(path[:-len('.jsonl')] + '.meta.json') as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None
    # Plugin agents are recorded with their plugin prefix: `eliot:task-scout`.
    agent = (meta.get('agentType') or '').split(':')[-1]
    if agent not in LOOP_AGENTS:
        return None

    prompt, stamps, peak, turns, tools, seen = None, [], 0, 0, 0, set()
    with open(path) as f:
        for line in f:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get('timestamp'):
                stamps.append(when(event['timestamp']))
            message = event.get('message')
            if prompt is None and event.get('type') == 'user' and isinstance(message, dict):
                content = message.get('content')
                prompt = content if isinstance(content, str) else json.dumps(content)
            if event.get('type') != 'assistant' or not isinstance(message, dict):
                continue
            usage = message.get('usage') or {}
            peak = max(peak, usage.get('input_tokens', 0) + usage.get('cache_creation_input_tokens', 0)
                       + usage.get('cache_read_input_tokens', 0))
            if message.get('id') not in seen:
                seen.add(message.get('id'))
                turns += 1
            tools += sum(1 for block in message.get('content') or []
                         if isinstance(block, dict) and block.get('type') == 'tool_use')

    task = re.search(r'Task file: docs/tasks/([^/\s]+)/(\w+)-', prompt or '')
    if not task or not stamps:
        return None
    stamps.sort()
    gaps = [(b - a).total_seconds() / 60 for a, b in zip(stamps, stamps[1:])]
    stalls = [g for g in gaps if g >= STALL_MIN]
    step = re.search(r'^(?:Mode|Round|Cycle): (\S+)', prompt, re.M)
    return dict(feature=task.group(1), task=task.group(2), agent=agent,
                stopped=bool(meta.get('stoppedByUser')),
                step=step.group(1) if step else '', start=stamps[0], peak=peak, turns=turns,
                tools=tools, wall=sum(gaps), active=sum(gaps) - sum(stalls), stalls=len(stalls))


def read_orchestrator(path, feature, into):
    """Add a main session's turns to {task: [peak, turns, tools, dispatches]}.

    A turn counts for the task whose files its tool calls last named.
    """
    mark = re.compile(r'docs/tasks/([^/\s"]+)/(?:runs/(\w+)|(?!00-)(\w+)-)')
    task, seen = None, set()
    with open(path) as f:
        for line in f:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            message = event.get('message') if isinstance(event, dict) else None
            if not isinstance(message, dict) or event.get('type') != 'assistant':
                continue
            calls = [b for b in message.get('content') or []
                     if isinstance(b, dict) and b.get('type') == 'tool_use']
            for m in mark.finditer(json.dumps([b.get('input') for b in calls])):
                task = (m.group(2) or m.group(3)) if m.group(1) == feature else None
            if task is None:
                continue
            row, usage = into.setdefault(task, [0, 0, 0, 0]), message.get('usage') or {}
            row[0] = max(row[0], usage.get('input_tokens', 0) + usage.get('cache_creation_input_tokens', 0)
                         + usage.get('cache_read_input_tokens', 0))
            if message.get('id') not in seen:
                seen.add(message.get('id'))
                row[1] += 1
            row[2] += len(calls)
            row[3] += sum(b.get('name') in ('Agent', 'Task') for b in calls)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    feature, only = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    runs, names = [], set()
    for directory in project_dirs():
        # Agents the implementer starts are nested, so their transcripts can sit a level deeper.
        for path in glob.glob(f'{directory}/*/subagents/**/agent-*.jsonl', recursive=True):
            name = os.path.basename(path)
            if name in names:
                continue
            run = read_run(path)
            if run and run['feature'] == feature and only in (None, run['task']):
                names.add(name)
                runs.append(run)
    stopped = sum(r['stopped'] for r in runs)
    runs = [r for r in runs if not r['stopped']]
    if not runs:
        sys.exit(f'No feature-loop transcripts for {feature}.')
    runs.sort(key=lambda r: (r['task'], r['start']))

    print('| Task | Agent | Step | Context | Turns | Tools | Active min | Wall min | Stalls |')
    print('|---|---|---|---|---|---|---|---|---|')
    for r in runs:
        print(f"| {r['task']} | {r['agent']} | {r['step']} | {r['peak'] // 1000}k | {r['turns']} | "
              f"{r['tools']} | {r['active']:.0f} | {r['wall']:.0f} | {r['stalls'] or ''} |")

    if stopped:
        print(f"\nLeft out: {stopped} run{'s' if stopped > 1 else ''} stopped by the human.")

    orchestrator = {}
    for directory in project_dirs():
        for path in glob.glob(f'{directory}/*.jsonl'):
            read_orchestrator(path, feature, orchestrator)
    rows = sorted((t, r) for t, r in orchestrator.items() if only in (None, t))
    if rows:
        print('\n| Task | Orchestrator context | Turns | Tools | Turns per dispatch |')
        print('|---|---|---|---|---|')
        for t, (peak, turns, tools, dispatches) in rows:
            print(f'| {t} | {peak // 1000}k | {turns} | {tools} | {turns / dispatches:.1f} |' if dispatches
                  else f'| {t} | {peak // 1000}k | {turns} | {tools} | |')

    print('\n| Task | Runs | Largest context | Total context | Over 50k | Active min | Wall min |')
    print('|---|---|---|---|---|---|---|')
    by_task = collections.defaultdict(list)
    for r in runs:
        by_task[r['task']].append(r)
    for task, group in by_task.items():
        biggest = max(group, key=lambda r: r['peak'])
        print(f"| {task} | {len(group)} | {biggest['peak'] // 1000}k {biggest['agent']} | "
              f"{sum(r['peak'] for r in group) // 1000}k | {sum(r['peak'] > 50_000 for r in group)} | {sum(r['active'] for r in group):.0f} | "
              f"{sum(r['wall'] for r in group):.0f} |")


if __name__ == '__main__':
    main()
