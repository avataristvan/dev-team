# dev-team

A Claude Code plugin that runs large implementation tasks through a small agent team: plan in chunks, review the plan, one coder per chunk with its own review, tests enforced by a hook, and a reflect gate before the next chunk.

## The problem

Give a single agent a big task and it delivers a big bang: one long session, one large diff, no plan anyone checked, and no review until the end, when nobody wants to unpick it. Whatever it learned along the way (a wrong path, an API surprise, a test that only passes in one mode) is gone when the session ends, and the next task starts from zero.

What helps with human teams helps here too: split the work, have someone else look at the plan before building, review every piece before it is merged, and stop between pieces to adjust the plan.

## How it works: Plan → Code → Review → Reflect

```
/dev-team:dev-team <task>
  │
  ├─ Plan     dev-team:chunk-plan (fresh agent)
  │             reads the code, cuts the task into chunks at layer boundaries,
  │             each with scope, model, exit criterion and a self-contained coder prompt
  │           └─ Tech-lead review: a second the-coder reads the plan cold
  │                and names where a coder would have to guess; findings go into the plan
  │
  ├─ Code     one dev-team:the-coder per chunk (parallel chunks in separate git worktrees)
  │           └─ Review: the coder runs dev-team:review on its own diff
  │                (standard code reviewer + anchor check against recorded decisions), fixes or justifies each finding
  │           └─ Test hook: when the coder stops, the project's test command runs; red sends it back once
  │
  └─ Reflect  the orchestrator reads each coder's [retro] block before the next spawn:
              blocked? learned something that changes the next chunk? findings skipped for a good reason?
```

| Part | Kind | Role |
|---|---|---|
| `dev-team:dev-team` | skill | Orchestrator: spawns planner and coders, merges worktrees, runs the reflect gate |
| `dev-team:chunk-plan` | skill | Planner: chunk plan plus the mandatory tech-lead review |
| `dev-team:the-coder` | agent | Implements one chunk; also the tech lead for plan reviews |
| `dev-team:review` | skill | The coder's review step after each chunk |
| `hooks/coder_tests.py` | SubagentStop hook | Runs `.claude/test-command` when a coder stops |

## Why chunks

A chunk is at most about 200 lines of new code, ends at a layer or capability boundary, leaves the code compilable, and has an exit criterion someone else can check ("looks good" doesn't count). That size fits one coder session, keeps each review readable, and gives the orchestrator a point to stop and adjust before a mistake spreads into the next chunk. Chunks on disjoint files run in parallel.

The planner runs every exit-criterion grep against the current tree before writing it down: a grep that already matches before the chunk starts is a hidden scope item or a wrong criterion.

## How the reviews catch errors

- **Plan review before any code.** A fresh agent that has not seen the planning reads the plan cold. Its prompt is deliberately open ("where would a coder have to guess?"); a checklist up front would only steer it towards the concerns the planner already had.
- **Review inside each coder.** The coder reviews its own diff with a standard code reviewer before reporting back, and has to list every finding with `applied` or `skipped` plus a reason. The orchestrator audits that list at the reflect gate.
- **Tests by mechanism, not by habit.** The SubagentStop hook runs the project's test command whenever a coder stops and sends it back once if they are red. A duty that matters belongs in something that enforces it.
- **Anchor check.** Each chunk carries the recorded decisions that bound it as `anchors`; `fabrica:anchor-lint` checks the diff against each one (held / violated / not applicable). A violated anchor is fixed or reported as blocked, never silently skipped.
- **Hard stop on contradictions.** If the librarian says a chunk would reverse a recorded decision, the coder builds nothing and reports `blocked: contradicts <id>`; the user decides. Agents that had only been *told* the reason still built and flagged it afterwards.

Some rules come from incidents. In a four-chunk parallel run, one coder ran `git stash` for a "clean baseline" while others were editing the same tree and wiped their work; since then parallel coders get their own git worktree, stateful git commands are forbidden, and only the orchestrator merges.

## An example

[`examples/chunk-plan-example.md`](examples/chunk-plan-example.md) is a real chunk plan from a build-config cleanup, pseudonymised and shortened: global rules, facts the planner verified in a scratch copy, five chunks with exit criteria, the parallel spawn order, the result, and a post-run correction. The correction shows a limit too: a config change broke the dev server while every exit criterion passed, because none of them loaded a page in dev mode.

## Install

The dev-team requires [Fabrica](https://github.com/avataristvan/fabrica) (see below); install it first, following its README. Then:

```bash
claude plugin marketplace add avataristvan/dev-team
claude plugin install dev-team@dev-team
```

Recommended alongside:
- [`pr-review-toolkit`](https://github.com/anthropics/claude-plugins-official) for its `code-reviewer` agent, the default inner reviewer. Without it, the review step falls back to a general-purpose agent with a review prompt. Change the reviewer in `skills/review/SKILL.md` (`inner_reviewer:`).

## Usage

- `/dev-team:dev-team <task>` runs the whole loop.
- `/dev-team:chunk-plan <task>` only plans (Claude also loads it on its own when you ask for a plan or a breakdown into chunks).
- Declare your test command in `.claude/test-command` (first non-comment line, e.g. `pytest -q` or `./gradlew test`) to enable the test hook.
- The hook only runs inside trusted roots: by default the session's project; set `DEV_TEAM_TRUSTED_ROOTS` (paths separated by `:`) to widen it, e.g. to a folder with all your projects. A test command in a repo outside those roots never runs.
- The hook never runs a command just because a file declares it: a coder can write `.claude/test-command` too. The first time a command appears, and whenever it changes, the hook doesn't run it and shows you the approval call instead (`python3 <plugin>/hooks/coder_tests.py --approve <repo> <sha256>`, which stores the approval only if the command still matches the hash you were shown; without the hash it only shows the command); approvals are stored as hashes in `~/.claude/dev-team/approved-test-commands.json`.
- What an approval means: the command runs without a permission prompt, unsandboxed, on the code the coder just wrote (that is what running tests is). Approve only commands you would run on that code yourself. Declarations containing control or format characters are refused.
- Project-specific rules (build commands, platform conventions, gotchas) belong in the project's `CLAUDE.md`; the coder reads them.

## Requires Fabrica

The team's memory across sessions comes from [Fabrica](https://github.com/avataristvan/fabrica), and the team does not run without it: the planner and every coder ask the librarian for recorded decisions at their boundaries, chunks carry decisions and anchors, the review runs the anchor check, and the `[retro]` blocks feed record candidates to the archivist via `/fabrica:reflect`. Without those steps the reviews would only check code quality, not whether a chunk breaks a decision that was already made. If Fabrica is missing, the orchestrator stops and says so instead of running a reduced team.

To plan from an interview instead of a one-line task, see [briefing-interviewer](https://github.com/avataristvan/briefing-interviewer): its implementation-ready briefing ends with "then `/dev-team:chunk-plan`".

## Status

This is the team I use day to day, packaged as a plugin. It is a working tool, not a polished product: the rules in it are the ones that survived real runs, and some open edges remain (for example, the review step needs git to see the changes).

## License

MIT, see [LICENSE](LICENSE).
