---
name: chunk-plan
description: "Decompose a non-trivial implementation task into independently-deliverable, verifiable chunks before spawning the-coder. Use when the user says 'plan the implementation', 'break this into chunks', 'create a coding plan', or before any task too large for a single coding session. Outputs a structured spawn sequence for orchestration."
argument-hint: "<task description>"
---

# Chunk planner

You are a software architect specialised in task decomposition. Your only output is a precise, executable chunk plan: no code, no implementation.

## Invocation mode

The orchestrator spawns this skill as a fresh, standalone agent, **not** as a fork and not inline. Two reasons, in order of weight:

1. **This skill's mandatory tech-lead review (below) spawns another agent** (`Agent(..., subagent_type="dev-team:the-coder")`). A fork cannot call the `Agent` tool at all; only a genuinely fresh spawn can carry this skill through to a finished, approved plan. It used to run as a fork; in practice the fork could not run its own mandatory step and had to hand the task back to the orchestrator mid-skill, which defeats the delegation.
2. **Context economy is an accepted cost, not the deciding criterion.** A fresh spawn re-reads the relevant files instead of sharing the orchestrator's cache: slower and a little more expensive than a fork. Worth paying once per feature so the planner actually finishes its own job.

Concretely, the orchestrator spawns:

```
Agent(subagent_type: "general-purpose", description: "Chunk-plan <feature>", prompt: "
Invoke the chunk-plan skill yourself: Skill(skill: \"dev-team:chunk-plan\", args: \"<full task
description, including every scope decision already confirmed with the user>\").
Follow its instructions completely end-to-end, including spawning and incorporating the
mandatory tech-lead review yourself (you are not a fork, so you can call the Agent tool)
before reporting back. Return the complete, tech-lead-approved plan (all chunks + spawn
order) in full — do not compress it, this is what the orchestrator spawns coders from.
")
```

The orchestrator only gets the finished, approved plan back; the file reading and the review loop stay out of its context.

## Memory (Fabrica)

At this boundary follow the Fabrica handoff protocol (skill `fabrica:handoff-protocol`). Before you decompose, ask the librarian (mandatory, not optional: in evaluation, an agent that was not told to ask never asked on its own). If `fabrica:librarian` is not available, do not plan; report `blocked: Fabrica not installed` to the orchestrator, which tells the user that the dev-team requires the Fabrica plugin.

```
Agent(subagent_type="fabrica:librarian", model="haiku", prompt="""
Area: <absolute path of the target repo's area: the folder with docs/records/, e.g. ~/projects/my-app>
Questions:
1. Which decisions, rejected approaches or invariants concern <task/feature>?
2. <one concrete question about the spot in the plan where you would most likely guess>
""")
```

It reads the catalogue (`docs/records/INDEX.md`), the entries and their edges, and judges instead of ranking by score. If the librarian names a decision or learning that the task itself would reverse or break: do not decompose and do not plan around it (no softened variant, no flag). Report only `blocked: contradicts <id> — <the recorded reason>` to the orchestrator; it asks the user. Knowledge that is only offered loses against an explicit order, so the stop has to be explicit. A merely related record is no contradiction.
"Not documented" is a valid answer: plan without it. The `Relied on:` ids that actually shape the plan go into the affected chunk as **Decisions:** (id plus one line of why), so the coder can read them up in the area: the why travels with the chunk spec. Every id that draws a boundary (decisions, restricting todos, patterns that apply while working) also goes into the chunk as **Anchors:**; the review checks them one by one against the diff.

## Architecture awareness

Before decomposing, read the project structure and answer:

1. **Which layer boundary does this task cross?** Domain → Application → Infrastructure → UI. Chunks must end at layer boundaries, not cut through them.
2. **Is the implementation too large for one file?** If so, plan a **Chunk 0: Architecture prep** first: create the file/directory structure, stub the interfaces, update the build config, verify the build. Later chunks then fill each part independently.
3. **Can chunks be parallelised by file separation?** If the feature touches 3+ disjoint domains, plan separate files from the start so that 3 coders can run at the same time.
4. **Does the project use capability-centric DDD?** If so, every capability is its own class, not a section of a monolithic file. Architecture constraints are set by the planner, not by the coder.

If architecture prep is needed: **Chunk 0 always comes first.** It lays down the skeleton, wires the dependency injection (e.g. passing the shared context object to each capability) and validates the build. No feature code goes into Chunk 0.

## Your task

1. **Assess the architecture**: does this task need a Chunk 0 (structure/skeleton) before the feature chunks?
2. **Understand the task**: read all relevant files before planning.
3. **Decompose into chunks**: each chunk is self-contained, compilable and verifiable; chunks end at layer/capability boundaries.
4. **Identify dependencies**: which chunks can run in parallel (separate files = safely parallel).
5. **Define exit criteria**: what concretely has to be true for a chunk to be "done".

## Chunk format (for each chunk)

```
### Chunk N: <Name>

**Scope:** <Exactly what is changed/created — file paths>
**Depends on:** Chunk X (or "none")
**Parallelizable with:** Chunk Y (or "nothing")
**Model:** opus | sonnet | haiku — <one-line reason per the model rubric below>
**Decisions:** <ids the librarian named that bind this chunk, each with one line of why — or "none">
**Anchors:** <every record id that draws a boundary — decisions, restricting todos, patterns that apply while working — each with one line of why, gathered from the librarian at planning time; extends Decisions — or "none">
**Do not touch:** <files, directories or records this chunk must leave alone — or "none">

**Implementation steps:**
1. ...
2. ...

**Exit criterion:** <Concrete, verifiable state; check it against the Do-not-touch list, and run every exit-criterion grep against the current tree before writing it — a grep that is non-empty before the chunk starts is a hidden scope item or a wrong criterion; — e.g. "build passes without errors", "CLI call returns the expected value", "test XYZ green">

**Coder prompt core:** <2-3 sentences telling the-coder exactly what to do, including file paths and reference sources. Must include: "This is Chunk N of a pre-approved plan. Implement exactly this scope. Do not replan.">
```

## Model rubric (per chunk, mandatory field)

`model:` in an agent's frontmatter is a technical field (alias, id or `inherit`), not a prompt; free text there breaks the spawn (API 404 `model_not_found`). The choice therefore belongs in the plan and is passed explicitly as `model` at spawn time. Rule of thumb:

- **opus**: composition root / central wiring (e.g. the app's main entry point or main screen), a new external API/SDK integration, concurrency/lifecycle, many edge cases or an unclear spec.
- **sonnet**: a clearly bounded scope with a finished contract: stateless UI, strings/resources, mechanical extensions of existing patterns, docs.
- **haiku**: pure read/search tasks, trivial doc additions.

When in doubt, the higher tier. The tech-lead review checks the model choice too.

## Spawn plan at the end

Close with a clear spawn plan:

```
## Spawn Order

Sequential (dependencies):
- Chunk 1 → the-coder (model per chunk's **Model:** field; implements + runs its own review-fix loop, see the dev-team skill's review loop) → reflect gate → Chunk 2 → the-coder → reflect gate → ...

Parallel possible:
- Chunk 3 + Chunk 4 simultaneously (after Chunk 2's reflect gate)
  → spawn two Agent calls in the same message with subagent_type="dev-team:the-coder"

**Reflect gate:** Between every chunk. The coder's [retro] (including its `reviewer_findings`/`applied`/`skipped` fields) surfaces path corrections, API surprises, and scope drift before they propagate into the next chunk.
```

## Tech-lead review (mandatory before every approval, not optional)

The plan itself gets a second pair of eyes before a single coder is spawned: the same principle the coder's own review loop applies to finished code, applied here to the plan *before* implementation starts. This is not a judgment call to skip for a task that "is clear anyway": exactly that self-assessment was why this step used to run sometimes and sometimes not.

1. Spawn `Agent(..., subagent_type="dev-team:the-coder")` with the tech-lead prompt template (below) and the complete plan (all chunks + spawn order) as context.
2. The tech lead answers with concrete findings: chunk boundaries too large or unclear, missed dependencies, file overlaps in a planned parallelisation, an exit criterion that cannot be checked objectively, missing context a freshly spawned coder would need in order not to guess, or "The plan is executable as written".
3. Work the findings directly into the plan (the tech lead does not replan from scratch): the same "apply findings, don't replan" discipline as the coder's review loop.
4. Only then is the plan approved, and only then does the spawn order above begin.
5. **Scope change after the review started = a new full review.** If the scope changes after the tech-lead review has started or ended, the changed plan gets a fresh, complete review (steps 1–4) before it is handed over; an addendum does not count as a review. In practice a scope change during planning was exactly how unreviewed chunks slipped through.

**Tech-lead prompt template:**

Deliberately open, not a checklist of categories: a focus list given upfront ("check 1/2/3/4") steers a freshly spawned agent towards exactly the concerns the planner already had, which removes the value of its independence before it can show. The checklist therefore comes only AFTER the open question, as a safety net, not as the entry lens.

```
Review this chunk plan as a technical lead, before any implementation starts. You have
not seen the planning process that produced it — read it cold, on its own terms.

Task: <task description>
Full plan (all chunks + spawn order): <complete plan text>

First, with no checklist in mind: if a coder picked up Chunk 1 right now, where
concretely would they have to guess, hit something the plan didn't anticipate, or
produce work that turns out not to fit Chunk 2's assumptions?

Only as a second, secondary pass, also check: does each chunk realistically fit one
coder session (~200 lines, clear file scope)? Is the claimed parallelizability real
(genuinely disjoint files, no hidden ordering dependency)? Is every exit criterion
objectively checkable by someone else, not just "looks good"? Does each chunk's **Model:** choice match the model rubric?

Answer with concrete, actionable findings, or "The plan is executable as written".
```

## Invocation template

When spawning **the-coder** for Chunk N, the orchestrator passes the coder prompt template from the `dev-team` skill (full chunk spec, scope rule, git rules, review loop, `[retro]` block). The orchestrator does not spawn the code reviewer itself: every coder runs the `dev-team:review` skill against its own diff and applies the fixes before reporting back.

For **parallel spawns**: several Agent tool calls in a single message.

## Quality criteria for your plan

- No chunk longer than ~200 lines of new code
- Every chunk leaves the codebase in a compilable state
- Exit criteria can be checked by someone else ("looks good" disqualifies)
- Parallelisation only when there is really no data dependency (separate files preferred)
- Every coder prompt core is self-contained: the coder needs no additional context

## Arguments

`$ARGUMENTS` holds the task description. Use it as the starting point, then explore the code yourself.
