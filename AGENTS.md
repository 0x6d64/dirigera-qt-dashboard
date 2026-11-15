# AGENTS.md

Working rules for AI agents (and humans) contributing to this repository.
Read this file before making changes.

## Project

PyQt6 desktop dashboard for IKEA DIRIGERA hubs. Python 3.12, managed with `uv`;
talks to the hub through the `dirigera` library (currently 1.6.1). The active
development branch is `refactor`.

## Task management

- The backlog lives in `agent-notes/todo.md`.
- Every backlog item has a unique ID in the form `t-<number>` (e.g. `t-17`).
- **Never reuse a todo number.** IDs are permanent: they survive edits,
  reordering, completion, and removal of tasks.
- New tasks always get the next free number = highest existing number + 1
  (currently `t-54`). Check both open and closed items before claiming an ID.
- Every task carries a priority tag (`A` blocker, `B` should fix, `C` nice to
  have) and an effort tag (`S` < 1 h, `M` 1–4 h, `L` > 1 day). Update these tags
  if scope changes, but never change the ID.
- Completed tasks are checked off in `todo.md` (keep the ID and description).

## Implementation plans

- Implementation plan items go into `agent-notes/implementation-plan.md`.
- Reference tasks by their `t-<number>` ID; plans never get their own
  `t-` numbers.
- One implementation plan entry per task or coherent task group, with concrete
  steps, affected files, and verification steps.

### Plan workflow (branches)

- **Executing a plan happens on a dedicated branch.** Before the first plan
  commit, create `plan/<short-slug>` (e.g. `plan/responsive-grid`,
  `plan/light-color-controls`) from the current working branch.
- Commit each plan step to that branch. Bookkeeping that belongs to the plan
  (checking off `t-` items, execution markers in the plan) goes on the same
  branch.
- When the plan is complete — all commits done and the gates green — merge the
  branch back into the branch it was created from **with a merge commit**
  (`git merge --no-ff`; the repo config already defaults to `merge.ff=false`),
  then delete the merged branch (`git branch -d <branch>`).
- Starting a plan is the standing promotion for commits made under this rule.
  It does **not** promote unrelated changes: keep the branch limited to the
  plan's scope.
- If a plan is abandoned or partially executed, do not merge; report the state
  and leave the decision to the user.
- One plan per branch. Do not mix commits from two plans on one branch.

## Requirements

- Requirements live in `doc/reqs.md`.
- Every requirement has a unique ID in the form `req-<number>` (e.g. `req-3`).
- **Never reuse a requirement number.** IDs are permanent, like todo IDs: they
  survive edits, reordering, and removal.
- New requirements get the next free number = highest existing number + 1.
  Check the whole file before claiming an ID.
- `reqs.md` has two sections: **Explicit** (stated by the user) and
  **Inferred** (derived from tasks, code review, or discussion). Whenever
  requirements are discovered while working, record them in the matching
  section with their `req-` ID instead of relying on memory.
- Tasks and plans may reference requirements by their `req-<number>` ID.

## Environment

- `uv` is installed at `%APPDATA%\Python\Python311\Scripts\uv.exe` and is not on
  `PATH` in all shells. Use it for everything: `uv sync`, `uv lock`,
  `uv run <cmd>`.
- The project requires Python ≥ 3.12; the `.venv` is uv-managed. Never install
  packages with `pip` directly or hand-edit `.venv`.
- After changing `pyproject.toml` dependencies, run `uv lock` and `uv sync`, and
  commit `uv.lock` together with `pyproject.toml`.

## Code conventions

- Formatting/linting/type-checking are enforced; run before you finish:
  - `uv run black .`
  - `uv run ruff check .`
  - `uv run mypy .`
- Match the existing style: flat module layout, type hints on public
  functions, docstrings for non-obvious behavior.
- Never commit secrets: `config.ini`, tokens, `token.txt`, `*.token` are
  gitignored — keep it that way.
- `dirigera` API notes (v1.6.1): state lives on `device.attributes`
  (e.g. `light.attributes.is_on`), `device.room` is a pydantic `Room` model,
  and token generation uses `dirigera.hub.auth` (`create_token` does not
  exist).
- PyQt6 notes (6.12): prefer `toggled`/`valueChanged`-with-debounce over
  comparing raw `stateChanged` ints to enums; enum/int comparisons are not
  equal in PyQt6.
- Blocking network I/O never belongs on the GUI thread; new hub calls must run
  in a worker thread.

## Git

- **Never stage or commit files unless promoted by the user.** An explicit
  request to stage/commit (e.g. "commit this") counts as promotion; finishing
  a task or running the gates does not. When unsure, propose a commit message
  and wait.
- Small, focused commits with short imperative messages (existing history is
  lowercase, e.g. "update packages").
- The working branch is `refactor`; do not commit directly to `master`.
