"""Checks on the text of every skill."""
import json
import re

from conftest import REPO_ROOT

ARGUMENT = re.compile(r'\$[0-9]')


def test_no_skill_contains_a_positional_argument_placeholder():
    # Claude Code replaces $0..$9 in a SKILL.md with the skill's arguments when it loads the
    # skill, so a literal `$1` (in a shell snippet, say) reaches the agent as something else.
    hits = [f'{path.relative_to(REPO_ROOT)}:{n}: {line.strip()}'
            for path in sorted(REPO_ROOT.glob('**/SKILL.md'))
            for n, line in enumerate(path.read_text().splitlines(), 1)
            if ARGUMENT.search(line)]
    assert not hits, ('Claude Code substitutes $0..$9 with skill arguments. Rewrite these lines:\n'
                      + '\n'.join(hits))


def test_every_loop_agent_is_in_the_plugin_manifest():
    # An agent file the manifest leaves out is never loaded, and its dispatch fails at run time.
    listed = set(json.loads((REPO_ROOT / '.claude-plugin' / 'plugin.json').read_text())['agents'])
    files = {f'./loop/agents/{p.name}' for p in (REPO_ROOT / 'loop' / 'agents').glob('*.md')}
    assert files == listed
