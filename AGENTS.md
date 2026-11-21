# AGENTS.md

Working rules for AI agents (and humans) contributing to this repository.
Read this file before making changes.

**Keeping this file fresh:** it holds rules, not state. Do not write facts that
change with every commit here (current branch, next free ID, dependency
versions, file counts, task status). Look them up with the commands given
below. If you must add a fact that can go stale, add the command that derives
it instead.

## Project

PyQt6 desktop dashboard for IKEA DIRIGERA hubs, managed with `uv`; talks to the
hub through the `dirigera` library. Versions are authoritative in
`pyproject.toml` and `uv.lock`; the layout is `dashboard.py` (main window and
workers), `widgets/` (components), `theme.py` (design tokens). Read the tree
rather than trusting a description of it.

Orientation docs: `README.md`, `doc/design-doc.md` (visual design), `doc/dirigera-api.md` (library facts),
`doc/qt-gotchas.md`,
`doc/reqs.md` (requirements), `agent-notes/todo.md` (backlog),
`agent-notes/implementation-plan.md` (plans and their status).

## Task management

- The backlog lives in `agent-notes/todo.md`.
- Every backlog item has a unique ID in the form `t-<number>` (e.g. `t-17`).
- **Never reuse a todo number.** IDs are permanent: they survive edits,
  reordering, completion, and removal of tasks.
- New tasks get the next free number = highest existing number + 1. Find it
  with `grep -ohE "t-[0-9]+" agent-notes/*.md | sort -t- -k2 -n -u | tail -1`
  (covers open and closed items and plan references).
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
- A plan's status is recorded once, in its own entry in
  `implementation-plan.md` (executed markers on commits). Do not copy status
  into other files.

### Plan workflow (branches)

- **Executing a plan happens on a dedicated branch.** Before the first plan
  commit, create `<type>/<short-slug>` (e.g. `feat/responsive-grid`) from the
  current working branch (`git branch --show-current`). The type describes the
  kind of change:

  | Type | Use |
  |---|---|
  | `feat/` | new behaviour |
  | `fix/` | bug fixes |
  | `test/` | tests and CI |
  | `docs/` | docs and notes only |
  | `chore/` | tooling, dependencies, cleanup |
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
- New requirements get the next free number = highest existing number + 1
  (`grep -oE "req-[0-9]+" doc/reqs.md | sort -t- -k2 -n -u | tail -1`).
- `reqs.md` has two sections: **Explicit** (stated by the user) and
  **Inferred** (derived from tasks, code review, or discussion). Whenever
  requirements are discovered while working, record them in the matching
  section with their `req-` ID instead of relying on memory.
- Tasks and plans may reference requirements by their `req-<number>` ID.

## Environment

- `uv` is installed at `%APPDATA%\Python\Python311\Scripts\uv.exe` and is not on
  `PATH` in all shells. Use it for everything: `uv sync`, `uv lock`,
  `uv run <cmd>`.
- The Python requirement is in `pyproject.toml`; the `.venv` is uv-managed.
  Never install packages with `pip` directly or hand-edit `.venv`.
- After changing `pyproject.toml` dependencies, run `uv lock` and `uv sync`, and
  commit `uv.lock` together with `pyproject.toml`.

## Code conventions

- Line endings are LF in every tracked file: source, docs, and notes alike.
  `.gitattributes` (`* text=auto eol=lf`) enforces this; when a script writes
  files, pass `newline="\n"` or write bytes so nothing converts them to CRLF.
- Formatting/linting/type-checking are enforced; run before you finish:
  - `uv run black .`
  - `uv run ruff check .`
  - `uv run mypy .`
  - `uv run pytest` (CI skips tests marked `slow` outside master and never runs
    `hardware` ones; mark new tests accordingly)
- Match the existing style: flat module layout, type hints on public
  functions, docstrings for non-obvious behavior.
- Never commit secrets: `config.ini`, tokens, `token.txt`, `*.token` are
  gitignored — keep it that way.
- `dirigera` API gotchas (verify against the version in `uv.lock` if in
  doubt): state lives on `device.attributes` (e.g. `light.attributes.is_on`),
  `device.room` is a pydantic `Room` model (may be `None`), and token
  generation uses `dirigera.hub.auth` (`create_token` does not exist).
- PyQt6 and QSS gotchas live in `doc/qt-gotchas.md`; read it before writing
  widgets or stylesheets.
- Blocking network I/O never belongs on the GUI thread; new hub calls must run
  in a worker thread.
- Colours, spacing, and fonts come from `theme.py` tokens; do not hard-code
  them in widgets.

## Git

- Hooks: after cloning run `uv run pre-commit install --install-hooks`. Commits then
  run formatting, lint and type checks (config: `.pre-commit-config.yaml`);
  pushes also run the fast tests. Do not bypass them with `--no-verify`.
- **Never stage or commit files unless promoted by the user.** An explicit
  request to stage/commit (e.g. "commit this") counts as promotion; finishing
  a task or running the gates does not. When unsure, propose a commit message
  and wait.
- Small, focused commits with short imperative messages (existing history is
  lowercase, e.g. "update packages").
- **Do not switch branches unless the user asks for it.** The plan workflow
  above is the only exception: create the `<type>/<slug>` branch when a plan
  starts, and switch back to merge it when the plan is complete.
- Do not commit directly to `master`. Work on the current plan
  branch; check it with `git branch --show-current` instead of assuming a name.
