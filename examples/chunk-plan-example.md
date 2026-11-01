# Build hygiene Runs A + B (web app) — chunk plan

<!-- A real chunk plan from a dev-team run (2026-10-06), pseudonymised for publication (2026-11-01):
     product, module and file names, machine paths and process ids are replaced; Chunks 0, 2 and 4
     are shortened to a summary, Chunks 1 and 3 and the global rules are lightly condensed.
     Structure, rules, exit criteria, results and the post-run correction are as they were.
     The plan predates the Decisions/Anchors/Do-not-touch fields of the current template. -->

- Date: 2026-10-06. Audience: the-coder agents. Status: DONE 2026-10-06
- Source of truth: the maintenance review's backlog, items BL-13..BL-18 (build config, type gate, lint config, bundler config, stray files).
- Paths: `$P=~/projects/web-app`, `$O=$P/app` (its own git repo; `$P` is NOT a git repo).
- Librarian: build config / strays → "Not documented". Relied on: `learning_pnpm_builtins_shadow_scripts` (pnpm built-ins shadow scripts → always `pnpm run <script>`, never `pnpm build`/`pnpm start`). Area decision `ship_bias` (deletions preferred) applies.

## 0. Global rules (every chunk)

- Never sidequest: touch only files in the chunk's **Scope**. Read every file right before editing it.
- Never rename symbols, files or dirs (a misspelled module dir stays misspelled).
- No `git commit`/`push`, no `git add`/`git rm` (deletions are plain `rm`; the user stages). No diffs in chat; one sentence per change.
- Off-limits: `src/modules/audio-engine/**` (hot path), `src/modules/license/**`, `docs/reviews/**`, `.env*`.
- Pre-existing working-tree state that MUST survive unchanged (`git -C $O status --porcelain` at plan time), including one intentional uncommitted tuning change in the audio engine.
- Toolchain: Node 24, pnpm 12.9.1. Until Chunk 1 lands, `pnpm run *` fails with `ERR_PNPM_VERIFY_DEPS_BEFORE_RUN`; use `./node_modules/.bin/{next,tsc,eslint}`. After Chunk 1: always `pnpm run <script>`.
- Long-running processes (`serve`, `next dev`) in the background, poll with `curl`, kill **only the processes you started**.
- **Running dev server:** at plan time a `next dev -p 9002` was running, not started by this plan. Never kill a process you did not start. **Orchestrator action before Chunk 1:** ask the user to stop it; pass the confirmation into the Chunk 1 prompt.
- Concurrency with a parallel plan (licensing): its Chunk 0 adds vitest to `$O/package.json`. Do not run a chunk of this plan while a chunk of that plan edits `package.json`/`pnpm-lock.yaml`; always re-read them fresh and keep its changes.

## Pre-verified facts (planner ran these in a scratch copy)

- Moving `overrides` from `package.json` `"pnpm"` to `pnpm-workspace.yaml` leaves `pnpm-lock.yaml` **byte-identical**.
- pnpm 12 **no longer honours `ignoredBuiltDependencies`**: a clean install fails with `ERR_PNPM_IGNORED_BUILDS`. An `allowBuilds` map (each `false`) makes it pass, lockfile unchanged.
- The existing `node_modules` was created by pnpm 10 (store v10); pnpm 12 uses store v11 and would prompt to purge (no TTY → abort). Hence Chunk 1 deletes `node_modules` and reinstalls clean (all packages already in the v11 store).
- `next.config.ts` is loaded via SWC as **CommonJS**, so `__dirname` is defined there; `import.meta` is not safe.
- The mode button's `outline-solid` variant is a codemod leftover; `outline` is the intended inactive look (`src/shared/ui/button.tsx:15`).

## Decisions recorded in this plan

- **BL-17 dropped:** all targets run current Chrome / iPadOS 17+; no `browserslist`.
- **`dev:webpack` deleted** (not fixed): Webpack is no longer configured after BL-16, ship bias favours deletion.
- **Out of scope** (do NOT touch): the 48 parked lint errors in `src`, unused deps, `public/sw.js`, two leftover files inside the off-limits audio engine (left for the orchestrator/user to schedule).

---

### Chunk 0: Baseline capture (read-only)

**Scope:** no repo file changes; writes only the "Baseline record" section of this plan file.
**Depends on:** none · **Parallelizable with:** nothing · **Model:** sonnet — mechanical commands + browser console capture.
*(Steps shortened.)* Records: porcelain list, `tsc` error count (1), pnpm verify error (1), eslint rc (2, crashes), build rc and warnings, HTTP 200 for `/` served from `out/`, browser console errors/warnings.

---

### Chunk 1: Run A — BL-13 (pnpm 12 config) + BL-14 (type gate)

**Scope:**
- `$O/pnpm-workspace.yaml` (edit)
- `$O/package.json` (remove `"pnpm"` field; `dev` script)
- `$O/pnpm-lock.yaml` (must stay byte-identical; verify only)
- `$O/node_modules/` (delete + clean reinstall)
- `$O/src/modules/controller/ui/mode-button.tsx` (one prop value)
- `$O/next.config.ts` (only `typescript.ignoreBuildErrors`)
- `$O/CLAUDE.md`, `$O/README.md` (named lines only)
**Depends on:** Chunk 0
**Parallelizable with:** nothing
**Model:** sonnet — fully specified mechanical edits; the pnpm surprises are pre-verified above.

**Implementation steps (cwd `$O`):**
1. Pre-flight: list `next` processes and their cwd. If any has cwd `$O` and was not started by you: **stop and report back** ("dev server running from $O/node_modules; needs user to stop it before reinstall"). Do not kill it.
2. `cp pnpm-lock.yaml <scratchpad>/pnpm-lock.before.yaml`.
3. Edit `pnpm-workspace.yaml` to exactly:
   ```yaml
   allowBuilds:
     '@firebase/util': false
     protobufjs: false
     sharp: false
   overrides:
     '@types/react': 19.2.8
     '@types/react-dom': 19.2.3
   ```
   If the parallel plan added other keys meanwhile, keep them.
4. `package.json`: delete the whole `"pnpm": { "overrides": {...} }` field; `"dev": "next dev --turbopack"` → `"dev": "next dev --turbopack -p 9002"`. Touch nothing else (`dev:webpack` is Chunk 2).
5. `rm -rf node_modules && pnpm install --frozen-lockfile` → rc 0, no `ERR_PNPM`. If it fails with `ERR_PNPM_IGNORED_BUILDS` naming a package not in step 3, stop and report (do not add approvals on your own).
6. `cmp pnpm-lock.yaml <scratchpad>/pnpm-lock.before.yaml` → identical.
7. `mode-button.tsx` line 18: `'outline-solid'` → `'outline'`. Nothing else in the file.
8. `next.config.ts`: `ignoreBuildErrors: true` → `false`. Nothing else (other keys are Chunk 2).
9. `CLAUDE.md` / `README.md`: replace `npm`/`pnpm build`-style commands in the named lines with `pnpm run …`.

**Exit criterion (all from `$O`):**
- `pnpm run typecheck; echo rc=$?` → no `ERR_PNPM`, `rc=0`; `tsc --noEmit` error count → `0`.
- `pnpm run build` → `rc=0`; `grep -c "Skipping validation of types"` → `0`; `grep -c ERR_PNPM` → `0`.
- `pnpm run lint 2>&1 | grep -c ERR_PNPM_VERIFY_DEPS_BEFORE_RUN` → `0` (lint itself still crashes, rc 2 — expected until Chunk 2).
- Dev server on :9002 answers `200` and pnpm echoes `next dev --turbopack -p 9002`; kill it.
- `cmp` identical; `grep -c '"pnpm"' package.json` → `0`; `grep -c "outline-solid" …/mode-button.tsx` → `0`.
- `git status --porcelain` = §0 list plus exactly the five expected ` M` lines (no `pnpm-lock.yaml`).

**Coder prompt core:** This is Chunk 1 of a pre-approved plan (read §0 and "Pre-verified facts" first). Move pnpm `overrides` into `pnpm-workspace.yaml` and replace `ignoredBuiltDependencies` with the given `allowBuilds` map, drop the `package.json` `"pnpm"` field, add `-p 9002` to `dev`, clean-reinstall `node_modules` (lockfile must stay byte-identical; stop if a foreign process still runs from `$O`), fix `outline-solid`→`outline`, set `ignoreBuildErrors: false`, and update the named doc lines. Implement exactly this scope. Do not replan.

---

### Chunk 2: Run B config — BL-15 (lint config) + BL-16 (next.config cleanup)

**Depends on:** Chunk 1 · **Parallelizable with:** Chunk 3 (disjoint files) · **Model:** sonnet.
*(Steps shortened.)* Remove the broken Tailwind ESLint plugin, ignore `public/`, delete `dev:webpack`, reduce `next.config.ts` to `output`, `turbopack.root: __dirname`, `typescript.ignoreBuildErrors: false`, `images.unoptimized: true` (fallback: drop `turbopack` if `__dirname` fails). Exit: lint runs to completion without crashing (expected ~48 errors / 3 warnings, parked, not fixed), typecheck and build green.

---

### Chunk 3: Run B deletions — BL-18 (strays)

**Scope:** 8 tracked stray paths in `$O` (a stale service-worker bundle, two misnamed image files, three empty root files, two leftover tool dirs), deleted with plain `rm`, never `git rm`.
**Depends on:** Chunk 1
**Parallelizable with:** Chunk 2
**Model:** sonnet — deletions with a reference check before each; needs judgement on grep hits.

**Implementation steps (cwd `$O`):**
1. For each path, confirm it is tracked (`git ls-files <path>` non-empty) and its size/content matches the scope note.
2. Reference grep per path over `$P` (excluding `node_modules`, `.next`, `out`, `.git`, `docs/reviews`, `docs/plans`, which name them as findings). Any hit that is a real reference (code, config, manifest, `sw.js`, docs instructions — not prose) → do NOT delete that path; report it.
3. `rm` only the paths cleared in step 2.
4. Do NOT build in this chunk (Chunk 2 runs builds concurrently; Chunk 4 rebuilds from scratch).

**Exit criterion:** the 8 paths are gone (or fewer, each withheld path reported); `git status --porcelain` shows exactly the 10 expected new ` D` lines; every out-of-scope file named in "Decisions" still exists.

**Coder prompt core:** This is Chunk 3 of a pre-approved plan (read §0 and "Decisions recorded"). Delete exactly the 8 listed stray paths with plain `rm` after a per-path reference grep (withhold and report any path with a real reference); leave everything under `src/` untouched. Implement exactly this scope. Do not replan.

---

### Chunk 4: Smoke check + coordination with the parallel plan

**Depends on:** Chunk 2 and Chunk 3 · **Parallelizable with:** nothing · **Model:** sonnet.
*(Steps shortened.)* Clean rebuild, serve `out/`, assets 200, browser console compared against the Chunk 0 baseline, mode button carries the outline classes; update the four baseline lines in the parallel plan; fill the Result record.

---

## Spawn Order

Sequential:
- Chunk 0 → the-coder (sonnet) → reflect gate
- Orchestrator: ask the user to stop the running dev server and keep it stopped until Chunk 1 reports; then Chunk 1 → the-coder (sonnet) → reflect gate.

Parallel:
- Chunk 2 + Chunk 3 simultaneously (after Chunk 1's reflect gate) → two `Agent(subagent_type="the-coder", model="sonnet")` calls in one message.

Sequential:
- Chunk 4 → the-coder (sonnet) → reflect gate (after both 2 and 3).

**Reflect gate:** between every chunk. The coder's [retro] (incl. `reviewer_findings`/`applied`/`skipped`) surfaces path corrections, API surprises and scope drift before they propagate.

---

## Result record (filled by Chunk 4)

- `tsc --noEmit` errors: **0** (was 1). Build **rc 0**, type check no longer skipped.
- `pnpm run lint`: `51 problems (48 errors, 3 warnings)`, rc 1 (was: crash; errors parked).
- 8 strays deleted, nothing withheld; working tree = §0 list + the expected ` M`/` D` lines, nothing else.
- Console vs baseline: same 3 warning kinds, **no new** errors or warnings.

## Post-run correction (orchestrator, same day)

`turbopack.root: __dirname` (Chunk 2) broke `pnpm run dev`: every page request failed with "Can't resolve 'tailwindcss'". The build was unaffected, which is why Chunks 2 and 4 passed: no exit criterion exercised a dev page load after Chunk 2. Fix: removed the `turbopack` key (dev page 200, build + typecheck green); the workspace-root warning is back and stays a user decision. Recorded as an anti-pattern (bundler root setting breaks the dev server). The general lesson: an exit criterion has to exercise every mode the change touches (dev and build), not only the one that is easiest to check.
