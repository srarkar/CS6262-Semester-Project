# Skills for the DNS pivoting project

Reviewed November 12, 2026 using `find-skills`. The audience is a small student team building a Python command-line PoC. Andrew requires clear, minimal code, useful comments, and Markdown documentation explaining how the code works and runs.

## Recommended shortlist

| Skill | Why it fits | Reported installs | Upstream repository stars |
|---|---|---|---|
| [python-code-style](https://skills.sh/wshobson/agents/python-code-style) | Descriptive Python names, consistent style, concise docstrings, and maintained documentation | About 17.2K | About 42.5K for [wshobson/agents](https://github.com/wshobson/agents) |
| [python-testing-patterns](https://skills.sh/wshobson/agents/python-testing-patterns) | Focused tests of observable behavior, isolated fixtures, and important boundaries | About 40.3K | Same community-maintained repository |
| [crafting-effective-readmes](https://skills.sh/softaworks/agent-toolkit/crafting-effective-readmes) | Documentation organized around what teammates need to understand and run the project | About 4.2K | About 2.7K for [softaworks/agent-toolkit](https://github.com/softaworks/agent-toolkit) |

Counts are approximate snapshots, not a guarantee of quality. These are community-maintained skills, not official Python or OpenAI skills. The directory pages, upstream repositories, and actual instruction files were inspected before selecting them:

- [Python style instructions](https://github.com/wshobson/agents/blob/main/plugins/python-development/skills/python-code-style/SKILL.md).
- [Python testing instructions](https://github.com/wshobson/agents/blob/main/plugins/python-development/skills/python-testing-patterns/SKILL.md).
- [README instructions](https://github.com/softaworks/agent-toolkit/blob/main/skills/crafting-effective-readmes/SKILL.md).

The skills.sh leaderboard was checked first. An `npx skills find` attempt could not reach the npm registry from this session. The already-cached Skills CLI returned no matches for the exact `python-code-style` search, so the shortlist was verified directly through directory pages and upstream instructions instead.

## How the agent should use them

Use `python-code-style` for naming, simple public function signatures, and comments/docstrings. Its Ruff, mypy, CI, packaging, and production configuration examples are optional; the baseline does not need that infrastructure.

Use `python-testing-patterns` when implementing or changing pivot behavior. A small standard-library `unittest` suite is sufficient for Task 001. The useful principles do not require pytest, coverage plugins, property-based testing, or a new dependency.

Use `crafting-effective-readmes` when writing the running/understanding guide. The audience is already known: Andrew and his teammates. Include the actual algorithm, exact commands, evidence and score definitions, and the limitations of mock filtering. Avoid unrelated open-source release, deployment, and contribution templates.

The project-specific DNS rules belong in `AGENTS.md` and the data contract. A general cybersecurity or offensive-security skill is not needed for the first method.

## Optional installation

These skills are recommended, **not installed by this task**. The project agent can implement Task 001 using the local instructions without waiting for them. If you want them installed for Codex, run these commands in your own terminal:

```bash
npx skills add wshobson/agents --skill python-code-style --skill python-testing-patterns --agent codex --global
npx skills add softaworks/agent-toolkit --skill crafting-effective-readmes --agent codex --global
```

Install only this shortlist rather than each repository's entire collection. Future work may justify different skills; these are sufficient recommendations for the current baseline.
