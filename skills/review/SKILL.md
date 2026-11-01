---
name: review
description: "Review step of a coder after implementing a chunk: runs git diff in the worktree, asks the Fabrica librarian, spawns the standard code reviewer (inner_reviewer) and fabrica:anchor-lint in parallel, merges the results into the [retro] and applies or justifies each finding. Load it after implementing a chunk, before reporting back."
inner_reviewer: pr-review-toolkit:code-reviewer
---

# Dev-team review

The coder loads this skill after implementing a chunk, before reporting back to the orchestrator. The coder never judges its own anchors.

`inner_reviewer:` is the standard code reviewer, default `pr-review-toolkit:code-reviewer` (the value in the frontmatter above). It stays unchanged: no foreign output format is imposed on it. If that agent type is not available, use `general-purpose` with the same prompt and the instruction "review this diff for correctness bugs and violations of the project's CLAUDE.md; list concrete findings with file and line".

At this boundary follow the Fabrica handoff protocol (skill `fabrica:handoff-protocol`). The dev-team requires Fabrica; if `fabrica:librarian` or `fabrica:anchor-lint` is not available, do not review without them: report `blocked: Fabrica not installed` in your `[retro]`.

## Steps

1. **Diff.** Run `git diff HEAD` in your own worktree (include new files, e.g. `git add -N .` first, or `git status` plus reading them).
   Ask the librarian with the changed paths, always, because spawn depth differs per caller: `Agent(subagent_type="fabrica:librarian", model="haiku")` with the area path (nearest ancestor with `docs/records/`), the changed paths, the chunk spec and the question "which decisions/learnings concern this change, and does it contradict one?".
2. **Spawn the reviewers in parallel** (one message, one `Agent` call each, `model: sonnet`):
   - the `inner_reviewer` with the usual prompt: Focus (2-3 concerns from the chunk spec), Context (file paths), Verify (exit criterion), and "run `git diff HEAD --name-only` in the worktree path to see the changes";
   - `fabrica:anchor-lint` with what the handoff protocol says a caller passes to it: chunk, worktree path, the diff as text, `anchors:` verbatim from the chunk entry, area path, the librarian answer from step 1.
   Then wait for every task-notification. No polling, no sleep loops.
3. **Merge** the results into your `[retro]`: `reviewer_findings`, `anchor_verdicts`, `records_consulted`, `record_candidates`. Apply every finding or justify skipping it (`applied` / `skipped`). A `violated` anchor is fixed or reported as blocked, never silently skipped.

The spawn-wait rule from the coder definition holds: after spawning, do nothing but wait for the notification.
