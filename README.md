# Skills

Claude Code skills I use. Each directory is one skill, defined by its `SKILL.md`.

| Skill | What it does |
| --- | --- |
| `codebase-design` | Shared vocabulary for designing deep modules: module, interface, seam, adapter, depth. |
| `grilling` | Relentless interview that stress-tests a plan or decision as a design tree. |
| `grill-me` | Shorthand entry point that calls `grilling`. |
| `unslop` | Cuts AI tells from writing. |
| `wait-what` | Asks for a re-pitch when an explanation did not land. |

## Install

Clone into your Claude Code skills directory:

```sh
git clone https://github.com/eliotshea/claude-skills.git ~/.claude/skills
```

If you already have skills there, clone elsewhere and symlink the ones you want:

```sh
ln -s /path/to/claude-skills/unslop ~/.claude/skills/unslop
```

Skills marked `disable-model-invocation: true` only run when you ask for them by name.
