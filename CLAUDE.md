# CLAUDE.md

Working on the dev-team plugin itself. What the plugin does is in `README.md`; this file is about changing it.

## Structure

```
.claude-plugin/        plugin.json, marketplace.json, icon.png
skills/dev-team/       orchestrator: team table, spawn rules, git isolation, coder prompt template, reflect gate
skills/chunk-plan/     planner: chunk format, model rubric, tech-lead review
skills/review/         the coder's review step (inner reviewer + fabrica:anchor-lint)
agents/the-coder.md    coder and tech lead
hooks/hooks.json       registers the SubagentStop hook
hooks/coder_tests.py   runs the approved .claude/test-command when a coder stops
examples/              a real chunk plan, pseudonymised
```

Every part names the others by their plugin names (`dev-team:chunk-plan`, `dev-team:the-coder`, `dev-team:review`). When you rename or move something, grep all of `skills/`, `agents/` and `README.md` for the old name.

## Rules for changes

- **Generic only.** No project, platform or machine specifics in skills, agent or hook. They belong in the CLAUDE.md of the project they are about; the coder reads that.
- **Fabrica is required.** The librarian, the handoff protocol, `fabrica:anchor-lint` and `/fabrica:reflect` are fixed steps, not optional branches. Keep the "stop if Fabrica is missing" check in every entry point.
- **One source per rule.** The coder prompt template lives in `skills/dev-team`, the review steps in `skills/review`; other files point to them instead of copying them.
- **Public repo.** English; paths as `~/…` or placeholders; people as roles; internal material (handoffs, chunk plans of other projects) only pseudonymised.

## The test hook

Stdlib only, Python 3.12+. It must never raise and never write to stderr; any problem means "no output". It runs a declared command only when the user approved exactly that command by hash (`--approve <repo> <sha256>`); keep that gate on every path to `subprocess.run`, and check trusted roots before any git call or file read.

Test it by hand in a scratch directory, with its own `HOME` (approvals live under `~/.claude/dev-team/`) and without an inherited `DEV_TEAM_TRUSTED_ROOTS` (Claude Code passes `settings.json` env vars to the shell):

```bash
echo '{"agent_type":"dev-team:the-coder","cwd":"<scratch repo>"}' \
  | env -u DEV_TEAM_TRUSTED_ROOTS HOME=<scratch home> CLAUDE_PROJECT_DIR=<scratch repo> \
    CLAUDE_PLUGIN_DATA=<scratch data> python3 -I hooks/coder_tests.py
```

Cover at least: red declaration (block), green (no output), unapproved or changed declaration (systemMessage, not run), checkout outside the trusted roots, a foreign repo's worktree inside them, non-coder agent, `stop_hook_active`, garbage on stdin.

## Checks before a commit

- `claude plugin validate .` passes.
- No machine paths or private names: `grep -rn -E "/home/|<private names>" --exclude-dir=.git .`
- Changes to skills or the agent take effect only after a Claude Code restart.

## Publishing

Push only `main`, by name. Check `git fetch` and `git status -sb` against `origin/main` before pushing; never amend a commit that may already be on GitHub.

## Records

Decisions and BACKLOG items about the dev-team live in the area `~/workspace/ai-architecture/` (outside this repo), in `docs/records/` under the topics `workflow`, `plugin` and `general`. Ask the librarian with that area before changing a rule; record candidates go to the archivist via `/fabrica:reflect`.
