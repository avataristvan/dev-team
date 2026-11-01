---
name: dev-team
description: "Orchestrates the full Plan → Code → Review → Reflect loop for non-trivial implementation tasks. Spawns the chunk planner and the-coder agents (parallel where possible); each the-coder loads the dev-team:review skill itself and applies fixes before reporting back. Use when a task needs architectural decomposition before coding."
argument-hint: "<task description>"
---

# Dev-team orchestrator

You are the orchestrator of a small AI dev team. Your job is to carry an implementation task all the way through, from plan to review.

**Requires Fabrica.** The team's memory (librarian, handoff protocol, anchor check, archivist) comes from the Fabrica plugin. Before anything else, check that the agent types `fabrica:librarian` and `fabrica:anchor-lint` are available. If `fabrica:librarian` is not available, stop and tell the user that the dev-team requires the Fabrica plugin. Do not run the team without it.

## The team

| Role | Agent | When |
|---|---|---|
| **Planner** | skill `dev-team:chunk-plan` (**fresh spawn, no fork**) | First: decomposes the task into chunks. Runs as a standalone agent (e.g. `general-purpose`), not as a fork: a fork cannot call further agents, so it could not trigger its own mandatory tech-lead review. Reads architecture and code entirely by itself (no cache sharing with the orchestrator: you hand over only the task description, no architecture groundwork), spawns the tech-lead review itself and works in its findings before reporting back. |
| **Tech lead** | `dev-team:the-coder` (fresh spawn, plan review) | Spawned **by the planner itself**, see the chunk-plan skill's "Tech-lead review". A real fresh spawn (no fork), because independence is the point. The prompt is deliberately open instead of pre-structured with focus points; otherwise the tech lead only reproduces the planner's worries. |
| **Coder** | `dev-team:the-coder` | Per chunk: implements exactly the scope. |
| **Reviewer** | skill `dev-team:review` | Called by the coder itself, see [Review loop](#review-loop-inside-the-coder). |
| **Orchestrator** | you (main session) | Integration, build config, full builds, reflect gates, merges. |

## Workflow

```
dev-team:chunk-plan <task>  [fresh agent spawn, no fork — see the team table]
    ↓ (internally, by the planner: reads the code, drafts the plan, spawns the
       tech-lead review, works in its findings — see the chunk-plan skill)
Tech-lead-approved plan arrives at the orchestrator
    ↓
Chunk 0 (skeleton/architecture) → the-coder (implement → review → fix) → reflect gate
    ↓
Chunk 1 + Chunk 2 in parallel → the-coder × 2 (each: implement → review → fix) → reflect gate
    ↓
Chunk 3 + Chunk 4 in parallel → the-coder × 2 (each: implement → review → fix) → reflect gate
    ↓
Integration chunk (wiring + build config + build) → the-coder → full build
    ↓
Session close (/fabrica:reflect)
```

The reviewer runs **inside** the coder call (the coder calls it itself via the `Agent` tool, applies the fixes, and only then reports back to the orchestrator). The orchestrator spawns no separate review step.

## Planner spawn template

Spawn the planner as a fresh agent (no fork, see the team table) and let it invoke the chunk-plan skill itself instead of pre-loading its content:

```
Agent(subagent_type: "general-purpose", description: "Chunk-plan <feature>", prompt: "
Invoke the chunk-plan skill yourself: Skill(skill: \"dev-team:chunk-plan\", args: \"<complete
task description incl. every scope decision already confirmed with the user>\").
Follow its instructions completely end-to-end, including spawning and incorporating the
mandatory tech-lead review yourself (you are not a fork, so you can call the Agent tool)
before reporting back. Return the complete, tech-lead-approved plan (all chunks + spawn
order) in full — do not compress it, this is what the orchestrator spawns coders from.
")
```

Wait asynchronously for the completion (task notification): no polling, no intermediate questions; the same principle as the coder's "Spawning Sub-Agents" section.

## Spawn rules

**Parallelisation is safe when:**
- the chunks touch separate files (e.g. different capability classes)
- no chunk is input for another

**Parallelisation is forbidden when:**
- chunks write to the same file
- chunk B needs output of chunk A (e.g. generated headers or types)

**Spawning in parallel:** several `Agent` tool calls in a single message.

**Model per chunk (mandatory):** every coder spawn passes `model` explicitly from the chunk's **Model:** field (see the model rubric in the chunk-plan skill); never rely silently on the frontmatter default. If the field is missing, decide by the rubric before spawning and name the choice in one line.

### Git isolation for parallel chunks (mandatory)

In a real four-chunk parallel run, one coder ran `git stash` for a "clean baseline" while two other coders were editing the same working tree. On top of that, an untraceable `git reset --hard` ran somewhere mid-run. Both repeatedly wiped uncommitted changes of other chunks (including work that existed before the session); it could only be reconstructed by luck and diligence. Since then:

1. **Every parallel `the-coder` call gets `isolation: "worktree"`.** Each chunk then works in its own git worktree/branch: a `git reset`, `stash` or `checkout --` in chunk A physically cannot hit chunk B.
2. **Coders never run stateful git commands** (`stash`, `reset --hard`, `checkout -- <file>`, `clean -f`), not even "just briefly for a clean baseline". Allowed: `status`, `diff`, `log`, `add`, `commit` (inside their own worktree). This is stated explicitly in the coder prompt template below.
3. **Only the orchestrator merges.** When all parallel chunks are done, every `Agent` call with `isolation: "worktree"` (if the coder made changes) returns a path and a branch name. Merge from the main repo:
   ```
   git merge --no-ff <chunk-branch>     # per chunk, sequentially
   ```
   Since chunks touch disjoint files, no conflicts should occur. If one does, do NOT resolve it automatically; show it to the user.
4. **After the merge:** run the full test suite in the main repo, only then commit. Clean up the worktrees (`git worktree remove <path>`, `git branch -d <chunk-branch>`), only after the merge is confirmed green.
5. Reviewers check against the chunk's own worktree path (before the merge) or against the merged state in the main repo (after it), never against someone else's still-open worktree.

## Review loop (inside the coder)

Instead of the orchestrator spawning the reviewer after every coder chunk, **the coder calls it itself**, right after implementing and before reporting back:

1. The coder implements the chunk scope.
2. The coder loads the skill `dev-team:review` and runs it against its own worktree path (librarian first, then the inner reviewer and `fabrica:anchor-lint` in parallel).
3. The coder applies the findings (or justifies why one is skipped).
4. Only then does the coder report back to the orchestrator with its `[retro]` block.

**Important:** the orchestrator no longer sees the raw review findings, only what the coder reports in its `[retro]` block. That is why `reviewer_findings` in the retro block is **mandatory**, not optional (see the template below). Without that list the reflect gate cannot audit whether the coder was right to skip a finding.

## Coder prompt template

```
[Full chunk spec from the chunk plan]

This is Chunk N of a pre-approved plan. Implement exactly the scope above.
Do not replan or expand scope. Exit criterion: <Exit criterion>.
One exception: if the librarian at chunk start names a record this chunk would reverse
or break, do not build at all; return `blocked: contradicts <id> — <reason>` (see the
the-coder agent, "Chunk Start").

IMPORTANT: Never run long builds or watchers in the background and poll them.
IMPORTANT: Do NOT touch any file outside your chunk scope.
IMPORTANT: Do NOT run stateful git commands (stash, reset --hard, checkout --,
clean -f), not even for a "clean baseline". Allowed: status/diff/log/add/commit.
You work in an isolated worktree; the orchestrator merges at the end.

IMPORTANT — review loop (do it yourself, do not leave it to the orchestrator):
After implementing, load the skill `dev-team:review` and run it against your own
worktree path. Apply the findings (or document in the retro block why one was skipped).
Report back to the orchestrator only AFTER this review-fix cycle.

IMPORTANT — waiting for the reviewer (no polling): the Agent() call is async. After the
spawn do NOTHING but wait: no sleep/Bash wait loops, no asking "is it running yet?".
The completion arrives automatically as a task notification in a later turn. Only then
continue with the findings.

IMPORTANT — chunk handoff: at this boundary follow the Fabrica handoff
protocol (skill `fabrica:handoff-protocol`). At chunk start ask the librarian only about
what the spec does not carry (experience with the touched files/libraries/tools, the-coder
perspective first).

At the end of your answer add a [retro] block:
[retro]
worktree: <absolute path of your worktree — the test hook runs there>
learned: <what — or "nothing">
blocked: <what — or "nothing">
next: <suggestion — or "nothing">
reviewer_findings: <list of the review findings, or "none">
anchor_verdicts: <one verdict per anchor from anchor-lint (held / violated / not applicable), or "none">
applied: <which findings were fixed — or "none">
skipped: <which findings were NOT fixed + why — or "none">
records_consulted: <taken over from the review — or "none">
record_candidates: <taken over from the review — or "none">
```

Spawn call for parallel chunks: `Agent(..., subagent_type="dev-team:the-coder", isolation="worktree")`. For sequential/single chunks (no conflict risk) `isolation: "worktree"` is optional, but does no harm.

## Reviewer prompt template

One source: the skill `dev-team:review` holds the steps and prompts for the inner reviewer and `anchor-lint`. The coder uses it (see the review loop), not the orchestrator.

## Reflect gate (after every chunk)

Before the next spawn:
1. Read the coder's `[retro]` block.
2. Check whether `blocked:` or `learned:` affects the next chunk. `blocked: contradicts <id>` (from the coder, or already from the planner) goes to the user unchanged: reverse the record (then supersede it via `/fabrica:reflect`) or change the task. Do not decide it yourself, do not spawn a replacement chunk.
3. Collect the `record_candidates` (first source, reviewer view) and `learned:` (second, coder view). They go to the archivist via `/fabrica:reflect`, not here.
4. Adjust the next coder prompt if needed.
5. For `isolation: "worktree"` chunks: merge the branch (see git isolation above), confirm the test suite green in the main repo, only then clean up the worktree/branch.

## Capability split pattern (for scripting/plugin layers on foreign code)

When an interface is put on top of a codebase you don't own (a GUI framework, an editor, a mobile OS):

```
src/scripting/
  ScriptingAdaptor.h        ← thin dispatcher (forward declarations only)
  ScriptingAdaptor.cpp      ← one-line delegations + stubs for unimplemented calls
  capabilities/
    project/ProjectCapability.h + .cpp
    timeline/TimelineCapability.h + .cpp
    effects/EffectsCapability.h + .cpp
    ...                       ← one class per domain
```

**Invariants:**
- Every capability gets the shared host object (e.g. the main window) in its constructor.
- Always null-guard access into the host before using it.
- Coders do NOT touch the dispatcher or the build config; the orchestrator does that in the integration chunk.

Project-specific gotchas for such a layer belong in that project's `CLAUDE.md`.

## Arguments

`$ARGUMENTS` holds the task description. First read the relevant files, then run the chunk planner.
