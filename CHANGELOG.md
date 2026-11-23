# Changelog

All notable changes to now-md. Versions follow `__version__` in `nowmd.py`.

## 0.2.3 — input and output edge cases, clearer positioning
- `add` rejects a blank (whitespace-only) `--title`; a padded title is stored trimmed.
- When `NOW.md` is cut at the 120-line cap, the last line now says `…(N行省略 / lines omitted)` instead of a bare "truncated".
- Task JSON written with a BOM (utf-8-sig, common with Windows editors) is read instead of being reported as broken.
- README: "Try it in 30 seconds" now works on a copy, so the bundled `examples/` is not modified; the 120-line cap is documented; "How it differs" says now-md holds only the current working state and does not replace `AGENTS.md` / `CLAUDE.md` or a memory tool.
- GitHub repo description and Topics reviewed for discoverability.
- Tests: 25.

## 0.2.2 — stability and input fixes
- A task with an out-of-range date (year 0001 / 9999, or before 1970 on Windows) no longer crashes `check` / `build`; it is reported as a bad time. `parse()` / `hm()` never raise.
- `--who` is shortened to one line (30 chars) when added and when built; `result` is shortened to 100 chars when built. A task can no longer forge headings in `NOW.md`. The 120-line cap now counts real lines.
- A corrupted lock file (huge or garbage PID) no longer raises `OverflowError`; `NOWMD_LOCK_WAIT` / `NOWMD_LOCK_STALE` ignore `nan`, `inf`, negative and non-numeric values.
- New `list` command: one line per task (`id  [status]  title`), so the id for `update` / `done` is easy to find.
- Minimum Python is now stated as 3.11 (CI runs 3.11 / 3.12 / 3.13).
- README: "How it differs", "Trust and limits"; the links to the author's Japanese writing are now under "Related writing".
- Tests: 23 (the lock test is now deterministic instead of timing-based).
- GitHub Actions (Linux / macOS / Windows), tests badge, demo GIF (`add` → `update` → `check`) and this changelog were added after 0.2.1 without code changes.

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
