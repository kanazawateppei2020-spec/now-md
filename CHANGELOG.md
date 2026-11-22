# Changelog

All notable changes to now-md. Versions follow `__version__` in `nowmd.py`.

## Unreleased (no code change)
- GitHub Actions: unit tests on Linux / macOS / Windows with Python 3.12 and 3.13, plus a tests badge in the README.
- Demo GIF now shows `add` → `update` → `check`.
- Added this changelog.

## 0.2.1 — security fix
- `update` / `done` validate `--id` exactly like `add` (no `../`, absolute paths, leading dots, or ids over 120 chars; the resolved path must stay inside `tasks/`).
- Lock file records `PID time`. A lock older than 30 s is only taken over if its owner process is gone. Release only your own lock. Windows liveness check via `ctypes`. Tunable with `NOWMD_LOCK_STALE` / `NOWMD_LOCK_WAIT`.
- `check` reads under the lock, so it no longer reports half-written files.
- Tests: 16 (4 added).

## 0.2.0
- New `update` command (any status change, e.g. running → blocked).
- Collision-proof ids (time + name + random suffix, file reserved with exclusive create) and a lock file, so several AIs can write at the same time. Atomic file replacement.
- New `check` command: validates JSON, status values and dates.
- Ready-made instruction snippets in `templates/` (Claude / Codex / Gemini / ChatGPT).
- `docs/GETTING_STARTED.md` and unit tests (`python3 -m unittest discover -s tests`).

## 0.1.0
- Initial release: `add`, `done`, `note`, `build`. Builds a single `NOW.md` (Running / Stuck / Done in 24h / Latest notes, max 120 lines). Standard library only.
