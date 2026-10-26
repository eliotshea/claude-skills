# Skills

Claude Code skills and agents I use, packaged as the `eliot` plugin. Each directory with a
`SKILL.md` is one skill.

| Skill | What it does |
| --- | --- |
| `codebase-design` | Shared vocabulary for designing deep modules: module, interface, seam, adapter, depth. |
| `grilling` | Relentless interview that stress-tests a plan or decision as a design tree. |
| `grill-me` | Shorthand entry point that calls `grilling`. |
| `tdd` | Test-driven development: what a good test is, where it goes, the red-green rules. |
| `unslop` | Cuts AI tells from writing. |
| `wait-what` | Asks for a re-pitch when an explanation did not land. |
| `abomunist` | Bob Kaufman's Abomunist Manifesto, as a persona. |
| `loop/feature-plan` | `/feature-plan`: plans a feature into task files through drafts, grills and readiness review. |
| `loop/feature-loop` | `/feature-loop`: delivers those tasks one at a time, each a validated PR, through the agents in `loop/agents/`. |

Skills marked `disable-model-invocation: true` only run when you ask for them by name.

## Install as a plugin

In Claude Code:

```
/plugin marketplace add eliotshea/claude-skills
/plugin install eliot@eliotshea
```

Skills and agents are namespaced: `/eliot:tdd`, agent `eliot:task-scout`. A bare `/tdd` also
works when nothing else has that name.

To make a project pull it in for everyone who opens it, commit this to its
`.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "eliotshea": {
      "source": { "source": "github", "repo": "eliotshea/claude-skills" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": { "eliot@eliotshea": true }
}
```

## Install as plain skills

Clone into your Claude Code skills directory:

```sh
git clone https://github.com/eliotshea/claude-skills.git ~/.claude/skills
```

If you already have skills there, clone elsewhere and symlink the ones you want:

```sh
ln -s /path/to/claude-skills/unslop ~/.claude/skills/unslop
```

The `loop/` skills need the plugin: they call their scripts and agents through it.

## The feature loop's project contract

`feature-plan` and `feature-loop` assume a pnpm project with Jest and Playwright, on a
`master` branch, with `gh` signed in. The agents run `pnpm test`, `pnpm exec tsc --noEmit`,
`pnpm run lint`, `pnpm run build`, and validation specs through a
`playwright.validation.config.ts` with `validation` and `regression` projects. App specs and
their fixtures live under `tests/app/`, validation scripts under `tests/validation/<feature>/`,
plans under `docs/tasks/<feature>/`. Styling and reuse rules come from the project's
`CLAUDE.md`.

The scripts' tests: `pip install -r loop/tests/requirements.txt && python -m pytest loop/tests`.
