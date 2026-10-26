#!/usr/bin/env python3
"""Run a validation spec at the task's base commit.

    python3 <plugin root>/loop/feature-loop/base_run.py <base commit> <spec> <port> [-g '<title regex>'] [--tail <n>]

It builds a throwaway worktree of the base commit, copies in this checkout's spec directory,
`tests/app/fixtures`, playwright.validation.config.ts and .env (the base may predate any of
them), gives it its packages, and runs the spec under the `validation` project on <port>+1,
only the tests whose titles match -g when given. The worktree is removed afterwards, whatever
happened.

Packages: when package.json, pnpm-lock.yaml and the Prisma schema are the same at the base as
here, the worktree links this checkout's node_modules and installs nothing. Otherwise it
installs. Either way it imports the packages the app's server needs first (IMPORTS) and, when
one fails, installs again with --force, then gives up with the error. A fresh install has
come out missing a package before, and the dev server then spent its whole 120-second start
timeout failing on it.

It prints the last --tail lines of Playwright's output (20 by default), leaving out the dev
server's `[WebServer]` lines, then the exit code and the path of the full log. A test that
logs its readings, `console.log("PICTURE", ...)`, prints them into that tail, so measuring at
the base is one run of that test with -g.

shots.py takes its before pictures in the same worktree, through `worktree`.
"""
import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

CONFIG = 'playwright.validation.config.ts'
# Whatever changes the installed packages or the generated Prisma client.
DEPS = ['package.json', 'pnpm-lock.yaml', '.npmrc', 'prisma/schema.prisma']
# Imported before the server starts, those the project lists. @trpc/next is the one a fresh
# install has lost (its peer react-ssr-prepass), and every page loads it through _app.
IMPORTS = ['next', '@trpc/next']


def run(cmd, cwd, log, env=None):
    with open(log, 'w') as f:
        return subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
                              env={**os.environ, **(env or {})}).returncode


def imports(tree, logs):
    """The first of IMPORTS that does not load in the tree, with its error, or None."""
    pkg_json = os.path.join(tree, 'package.json')
    pkg = json.load(open(pkg_json)) if os.path.exists(pkg_json) else {}
    listed = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
    for name in (n for n in IMPORTS if n in listed):
        log = os.path.join(logs, 'imports.log')
        if run(['node', '--input-type=module', '-e', f'await import("{name}")'], tree, log):
            with open(log) as f:
                error = next((l for l in f.read().splitlines() if 'Error' in l), '').strip()
            return f'{name}: {error[:200]}'
    return None


def packages(base, root, tree, logs):
    """node_modules for the base worktree: this checkout's when the deps match, else installed."""
    same = subprocess.run(['git', 'diff', '--quiet', base, 'HEAD', '--', *DEPS]).returncode == 0
    if same and os.path.isdir(os.path.join(root, 'node_modules')):
        os.symlink(os.path.join(root, 'node_modules'), os.path.join(tree, 'node_modules'))
        if not imports(tree, logs):
            return
        os.unlink(os.path.join(tree, 'node_modules'))
    install = ['pnpm', 'install', '--frozen-lockfile', '--prefer-offline']
    for attempt in (install, install + ['--force']):
        if run(attempt, tree, os.path.join(logs, 'install.log')):
            sys.exit(f'pnpm install failed in the base worktree. Log: {logs}/install.log')
        failed = imports(tree, logs)
        if not failed:
            return
    sys.exit(f'The base worktree cannot import {failed}, even after `pnpm install --force`. '
             f'Log: {logs}/install.log')


@contextlib.contextmanager
def worktree(base, spec, logs):
    """A worktree of <base> with this checkout's files for <spec>, installed. Removed on exit."""
    root = os.getcwd()
    tmp = tempfile.mkdtemp(prefix='base-tree-')
    tree = os.path.join(tmp, 'base')
    subprocess.run(['git', 'worktree', 'add', '--detach', '-q', tree, base], check=True)
    try:
        # The base may predate this spec, the helpers beside it, its fixtures or the config.
        for path in ['.env', CONFIG, os.path.dirname(spec), 'tests/app/fixtures']:
            src, dst = os.path.join(root, path), os.path.join(tree, path)
            if os.path.isdir(src):
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)
            elif os.path.exists(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy(src, dst)
        packages(base, root, tree, logs)
        yield tree
    finally:
        subprocess.run(['git', 'worktree', 'remove', '--force', tree])
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    p = argparse.ArgumentParser(prog='base_run.py', description=__doc__.split('\n')[0])
    p.add_argument('base', metavar='<base commit>')
    p.add_argument('spec', metavar='<spec>')
    p.add_argument('port', metavar='<port>', type=int)
    p.add_argument('-g', dest='grep', metavar='<title regex>')
    p.add_argument('--tail', type=int, default=20, metavar='<n>')
    a = p.parse_args()

    logs = tempfile.mkdtemp(prefix='base-run-')
    log = os.path.join(logs, 'playwright.log')
    cmd = ['pnpm', 'exec', 'playwright', 'test', '-c', CONFIG, '--project=validation', a.spec]
    if a.grep:
        cmd += ['-g', a.grep]
    with worktree(a.base, a.spec, logs) as tree:
        code = run(cmd, tree, log, {'VALIDATION_PORT': str(a.port + 1)})
    with open(log) as f:
        lines = [re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', l) for l in f.read().splitlines()]
    lines = [l for l in lines if l.strip() and not l.startswith('[WebServer]')]
    for line in lines[-a.tail:] if a.tail > 0 else []:
        print(line)
    print(f'exit {code}, log {log}')
    return code


if __name__ == '__main__':
    sys.exit(main())
