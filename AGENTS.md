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
  (currently `t-40`). Check both open and closed items before claiming an ID.
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
