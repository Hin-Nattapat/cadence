# brigade

The project's settings for the brigade skills. Written by `/brigade setup`; run it again or edit by hand. Commit this file.
`inbox:` says where issues go: `gh` or `docs/issues/`. With no `inbox:` line: `gh` if `gh repo view` succeeds, otherwise `docs/issues/`.
`style:` names a rule file no `AGENTS.md` or `CLAUDE.md` names; `none` or no line means no extra file.
`reviewers: <folder>/ <file>` runs that reviewer prompt at taste when the diff touches the folder; `./` is the whole repo. `reviewers: <folder>/ skill:<name> <command>` runs a skill that way.
`design: <skill>` names the design skill: recipe draws comps with it for a job that changes a screen, and taste offers its critique at smoke.

inbox: gh
reviewers: ./ .claude/agents/cadence-reviewer.md
