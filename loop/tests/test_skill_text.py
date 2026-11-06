"""Checks on the text of every skill."""
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
