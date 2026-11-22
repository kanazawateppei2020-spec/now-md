# Getting started / はじめかた

[English](#english) | [日本語](#日本語)

## English

You need: Python 3.8+ (check with `python3 --version`). Nothing to install.

1. **Put `nowmd.py` in your project folder** (or anywhere; use `--dir` to point at the project).
2. **Make your first task and page**
   ```
   python3 nowmd.py add --who claude --title "Set up the project"
   cat NOW.md
   ```
   This creates `tasks/` (one JSON per task) and `NOW.md` (the page).
3. **Tell each AI about it.** Copy the matching file from [`templates/`](../templates) into that AI's instruction file:
   | AI | Instruction file | Template |
   |---|---|---|
   | Claude Code | `CLAUDE.md` | `templates/CLAUDE.md.snippet` |
   | Codex | `AGENTS.md` | `templates/AGENTS.md.snippet` |
   | Gemini CLI | `GEMINI.md` | `templates/GEMINI.md.snippet` |
   | ChatGPT (chat) | Custom Instructions | `templates/chatgpt-custom-instructions.txt` |
4. **Change a task's state** when things move: `python3 nowmd.py update --id <id> --status blocked --why "..." --fix "..."`. Finish with `done`.
5. **Optional**: run `python3 nowmd.py build` from cron/launchd every few minutes so the `⚠ no update` warning appears for tasks that went quiet.

### If something looks wrong
- `python3 nowmd.py check` lists broken files (bad JSON, unknown status, bad time). `build` skips them and says how many.
- "could not get the lock": another run is writing. If none is running, delete `.nowmd.lock` in your folder.
- Several AIs writing at once is fine: ids are unique and writes are locked.

### Tests
`python3 -m unittest discover -s tests -v`

## 日本語

必要なもの: Python 3.8以上(`python3 --version` で確認)。インストールは不要です。

1. **`nowmd.py` をプロジェクトのフォルダに置く**(別の場所でも `--dir` で指定できます)。
2. **最初の1件とページを作る**
   ```
   python3 nowmd.py add --who claude --title "プロジェクトの準備"
   cat NOW.md
   ```
   `tasks/`(1件=JSON1つ)と `NOW.md`(1枚のページ)ができます。
3. **各AIに知らせる。** [`templates/`](../templates) の該当ファイルを、そのAIの指示書にコピーします。
   | AI | 指示書 | 雛形 |
   |---|---|---|
   | Claude Code | `CLAUDE.md` | `templates/CLAUDE.md.snippet` |
   | Codex | `AGENTS.md` | `templates/AGENTS.md.snippet` |
   | Gemini CLI | `GEMINI.md` | `templates/GEMINI.md.snippet` |
   | ChatGPT(チャット) | カスタム指示 | `templates/chatgpt-custom-instructions.txt` |
4. **状態が変わったら更新**: `python3 nowmd.py update --id <id> --status blocked --why "理由" --fix "戻し方"`。終わったら `done`。
5. **任意**: cron/launchd で `python3 nowmd.py build` を数分おきに回すと、止まった作業に `⚠` が付きます。

### おかしいとき
- `python3 nowmd.py check` で壊れた記録(JSON不正・不明な状態・日時不正)を一覧。`build` は壊れたものを飛ばして件数を表示します。
- 「could not get the lock」: 他の実行が書き込み中です。実行中のものが無ければ、フォルダ内の `.nowmd.lock` を消してください。
- 複数のAIが同時に書いても大丈夫です(IDは重ならず、書き込みはロックされます)。

### テスト
`python3 -m unittest discover -s tests -v`
