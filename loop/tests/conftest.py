"""Shared fixtures for the feature-loop script tests.

The scripts have hyphenated names and live outside any package, so they are loaded by path
(`load_script`) for their pure functions and run as subprocesses (`run_script`) for their CLI.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURE_LOOP = REPO_ROOT / 'loop' / 'feature-loop'
# shots.py imports base_run.py from beside it, as `python3 shots.py` would find it.
sys.path.insert(0, str(FEATURE_LOOP))


def script_path(name):
    return FEATURE_LOOP / name


def load_script(name):
    """Import a feature-loop script as a fresh module."""
    path = script_path(name)
    module_name = 'skill_' + path.stem.replace('-', '_')
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_script(name, *args, cwd, env=None):
    """Run a feature-loop script as its CLI would be run."""
    return subprocess.run([sys.executable, str(script_path(name)), *map(str, args)],
                          cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


class Repo:
    """A throwaway git repo. `commit` writes files (None deletes) and returns the full sha."""

    def __init__(self, path):
        self.path = path
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'commit.gpgsign', 'false')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.path, capture_output=True, text=True,
                              check=True).stdout

    def write(self, rel, text):
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self, files, message='commit'):
        for rel, text in files.items():
            if text is None:
                self.git('rm', '-q', '-r', rel)
            else:
                self.write(rel, text)
                self.git('add', rel)
        self.git('commit', '-q', '--allow-empty', '-m', message)
        return self.head()

    def head(self):
        return self.git('rev-parse', 'HEAD').strip()

    def object(self, rev, path):
        return self.git('rev-parse', '--short=10', f'{rev}:{path.rstrip("/")}').strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    return Repo(root)


def numbered(n, prefix='line'):
    """n lines of text, `line 1` .. `line n`, newline terminated."""
    return ''.join(f'{prefix} {i}\n' for i in range(1, n + 1))
