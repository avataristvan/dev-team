#!/usr/bin/env python3
"""SubagentStop hook: run the project's tests when a `the-coder` agent stops, block once when they fail.

Tests run deterministically instead of depending on the coder's habit: a duty that matters
belongs in a mechanism that enforces it, not in an instruction the agent may forget.

- Working directory: the `worktree:` line of the coder's last `[retro]` block if it names a git
  checkout, else the event's `cwd`.
- Test command: the first non-empty line of `.claude/test-command` in that checkout, else in its
  main checkout (a fresh worktree has no untracked files).
- Trusted roots: only checkouts below one of them run. `DEV_TEAM_TRUSTED_ROOTS` (paths separated
  by the OS path separator, `~` allowed) if set, else the session's project (`CLAUDE_PROJECT_DIR`).
  A declaration elsewhere (a cloned foreign repo) never runs. No declaration: no output.
- Approval: a declared command runs only if the user approved exactly this command for this
  declaring checkout (sha256 in ~/.claude/dev-team/approved-test-commands.json). A new or changed
  declaration does not run; the hook shows the user a `systemMessage` with the approval command
  (`python3 coder_tests.py --approve <checkout> <sha256>`) and does not block the coder. The
  approval stores the hash only if the declaration still matches the hash the user was shown. A coder can write
  `.claude/test-command`, so writing it must never be enough to execute it.
- Red, or the command could not run: `{"decision": "block", ...}` with the output's tail, once;
  with `stop_hook_active` nothing runs, so it never loops. The orchestrator still runs the full
  suite after the merge.
- Every run appends one line to `coder_tests.jsonl` in `CLAUDE_PLUGIN_DATA` (else ~/.claude/dev-team/).

Stdlib only; exits 0 with nothing on stderr whatever stdin holds.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

ROLE = "the-coder"  # matched bare or namespaced (`dev-team:the-coder`)
DECLARATION = Path(".claude", "test-command")
LOG = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or Path.home() / ".claude" / "dev-team") / "coder_tests.jsonl"
TIMEOUT = 840  # seconds; the hook's own timeout in hooks.json is 900
TAIL_LINES = 40
APPROVALS = Path.home() / ".claude" / "dev-team" / "approved-test-commands.json"
_WORKTREE = re.compile(r"^[\s>*#-]*\**worktree\**\s*:\s*`?([^`\s]+)`?", re.IGNORECASE | re.MULTILINE)


def _git(cwd: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _checkout(path: Path) -> Path | None:
    """Top level of the git checkout containing `path`, or None."""
    if not path.is_dir():
        return None
    top = _git(path, "rev-parse", "--show-toplevel")
    return Path(top) if top else None


def _main_checkout(checkout: Path) -> Path | None:
    common = _git(checkout, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(common).parent if common else None


def _trusted(path: Path, roots: list[Path]) -> bool:
    resolved = path.expanduser().resolve()
    return any(resolved.is_relative_to(root) for root in roots)


def _work_dir(event: dict, roots: list[Path]) -> Path | None:
    """The checkout to test. The `worktree:` path comes from model output, so it is checked
    against the trusted roots before git ever runs in it, and the checkout git reports is
    checked again."""
    candidates = []
    message = event.get("last_assistant_message")
    if isinstance(message, str):
        retro = message.rfind("[retro]")
        match = _WORKTREE.search(message[retro:]) if retro >= 0 else None
        if match:
            candidates.append(Path(match.group(1)).expanduser())
    cwd = event.get("cwd")
    if isinstance(cwd, str):
        candidates.append(Path(cwd))
    for candidate in candidates:
        if not _trusted(candidate, roots):
            continue
        checkout = _checkout(candidate)
        if checkout and _trusted(checkout, roots):
            return checkout
    return None


def _command(checkout: Path, roots: list[Path] | None) -> tuple[str, Path] | None:
    """The declared command and the checkout that declares it; `roots=None` skips the trust check."""
    for root in (checkout, _main_checkout(checkout)):
        if root is None or (roots is not None and not _trusted(root, roots)):
            continue
        try:
            lines = (root / DECLARATION).read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if line.strip() and not line.lstrip().startswith("#"):
                if not _printable(line.strip()):
                    return None  # never show, approve or run a line that could disguise itself
                return line.strip(), root.resolve()
    return None


def _printable(command: str) -> bool:
    """No control, format (bidi, zero-width) or separator characters other than a plain space,
    so what the user approves is what runs."""
    return not any(unicodedata.category(char) in ("Cc", "Cf", "Zl", "Zp")
                   or (unicodedata.category(char) == "Zs" and char != " ") for char in command)


def _digest(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8")).hexdigest()


def _approvals() -> dict:
    try:
        data = json.loads(APPROVALS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _approved(command: str, declared_in: Path) -> bool:
    return _approvals().get(str(declared_in)) == _digest(command)


def _approve_call(declared_in: Path, digest: str) -> str:
    script = shlex.quote(str(Path(__file__).resolve()))
    return f"python3 {script} --approve {shlex.quote(str(declared_in))} {digest}"


def approve(path: str, expected: str | None) -> int:
    """CLI for the user. Without `expected`: show the declared command and its hash, store nothing.
    With it: store the approval only if the declaration still has exactly that hash."""
    checkout = _checkout(Path(path).expanduser())
    found = _command(checkout, None) if checkout else None
    if not found:
        print(f"no {DECLARATION} found for {path}")
        return 1
    command, declared_in = found
    digest = _digest(command)
    if expected is None:
        print(f"declared in {declared_in}: {command} ({len(command)} chars)\nto approve exactly this command: {_approve_call(declared_in, digest)}")
        return 0
    if expected != digest:
        print(f"not approved: the declaration in {declared_in} changed since the hash was shown; now: {command}")
        return 2
    approvals = _approvals()
    approvals[str(declared_in)] = digest
    APPROVALS.parent.mkdir(parents=True, exist_ok=True)
    APPROVALS.write_text(json.dumps(approvals, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"approved for {declared_in}: {command}")
    return 0


def _is_coder(agent_type: object) -> bool:
    return isinstance(agent_type, str) and agent_type.split(":")[-1] == ROLE


def _trusted_roots(event: dict) -> list[Path]:
    declared = os.environ.get("DEV_TEAM_TRUSTED_ROOTS", "")
    if declared.strip():
        raw = [part for part in declared.split(os.pathsep) if part.strip()]
    else:
        project = os.environ.get("CLAUDE_PROJECT_DIR")
        raw = [project] if isinstance(project, str) and project else []
    return [Path(part).expanduser().resolve() for part in raw]


def _log(entry: dict) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def handle(event: dict) -> dict | None:
    if not _is_coder(event.get("agent_type")) or event.get("stop_hook_active") is True:
        return None
    roots = _trusted_roots(event)
    checkout = _work_dir(event, roots)
    if checkout is None:
        return None
    found = _command(checkout, roots)
    if not found:
        return None
    command, declared_in = found
    if not _approved(command, declared_in):
        _log({"ts": time.time(), "agent_id": event.get("agent_id"), "checkout": str(checkout),
              "command": command, "exit": None, "tail": "not approved, not run"})
        return {"systemMessage": f"dev-team test hook: `{command}` ({len(command)} chars, declared in {declared_in / DECLARATION}) "
                                 f"is new or changed and was not run. If you trust it, approve it with: "
                                 f"{_approve_call(declared_in, _digest(command))}"}
    started = time.time()
    try:
        done = subprocess.run(command, shell=True, cwd=checkout, capture_output=True, text=True,
                              timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        code, output = done.returncode, (done.stdout + done.stderr)
    except subprocess.TimeoutExpired as exc:
        code, output = None, f"timed out after {TIMEOUT}s\n{exc.stdout or ''}"
    except OSError as exc:
        code, output = None, f"could not run: {exc}"
    tail = "\n".join(output.strip().splitlines()[-TAIL_LINES:])
    _log({"ts": started, "seconds": round(time.time() - started, 1), "agent_id": event.get("agent_id"),
          "checkout": str(checkout), "command": command, "exit": code, "tail": tail[-1000:]})
    if code == 0:
        return None
    return {
        "decision": "block",
        "reason": f"The project's tests did not pass in {checkout} (`{command}`, exit {code}). "
                  f"Fix them, or report the failure under `blocked:` in your [retro]. Last lines:\n{tail}",
    }


def main() -> None:
    if len(sys.argv) in (3, 4) and sys.argv[1] == "--approve":
        sys.exit(approve(sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else None))
    try:
        event = json.load(sys.stdin)
        result = handle(event) if isinstance(event, dict) else None
        if result:
            sys.stdout.write(json.dumps(result))
    except BaseException:  # noqa: BLE001 -- a hook must not raise
        pass


if __name__ == "__main__":
    main()
