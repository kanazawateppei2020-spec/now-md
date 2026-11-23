# now-md — one page that tells every AI "what's going on right now"

> Machine-written `NOW.md` for people who juggle Claude, ChatGPT, Codex and Gemini. Each AI drops one tiny JSON per task; one script builds a single hand-off page. No AI, no network, standard library only.

[![tests](https://github.com/kanazawateppei2020-spec/now-md/actions/workflows/test.yml/badge.svg)](https://github.com/kanazawateppei2020-spec/now-md/actions/workflows/test.yml) [![license: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) [Changelog](CHANGELOG.md)

[English](#english) | [日本語](#日本語)

![demo](docs/demo.gif)

## English

**Who it's for**: people who switch between several AIs (Claude, ChatGPT, Codex, Gemini…) and keep re-explaining "where we are" every time.

How it works: each AI (or you) writes one tiny JSON per task into `tasks/`. A script gathers them into a single **`NOW.md`**. The next AI reads only that page first. `NOW.md` is machine-written (never hand-edited), so the format never drifts and the reader spends few tokens.

`NOW.md` contains: **Running / Stuck (with how to unblock) / Done in the last 24h / Latest notes & decisions** — capped at 120 lines (if there is more, the last line says `…(N行省略 / lines omitted)`).

**How it differs**
- The page is written by a script, so the format never drifts, whichever AI wrote the records.
- No AI and no network are involved in building it, so the reader pays only for reading one short page.
- Several AIs can write at the same time (lock file, unique ids, atomic replace) — on one machine, in a normal local folder. It is not a memory store or an agent framework: it keeps no conversations and calls no model.
- It holds only *the current working state* (what is running, stuck, just done). It does not replace a single `AGENTS.md` / `CLAUDE.md` (standing instructions) or a memory tool (long-term knowledge) — use those alongside it, and let `NOW.md` be the page that changes every hour.

### Install (optional)
```
pipx install git+https://github.com/kanazawateppei2020-spec/now-md
nowmd --version
```
After that, use `nowmd add ...` wherever this README says `python3 nowmd.py add ...`. (No install is needed either: `nowmd.py` is a single file you can copy.)

### Try it in 30 seconds
Work in a copy so the bundled `examples/` stays untouched (on Windows, copy the folder anywhere and use that path):
```
cp -r examples /tmp/nowmd-try
python3 nowmd.py --dir /tmp/nowmd-try add --who claude --title "Fix login bug" --status running
python3 nowmd.py --dir /tmp/nowmd-try add --who codex --title "Write tests" --status blocked --why "needs API key" --fix "ask the owner for a test key"
python3 nowmd.py --dir /tmp/nowmd-try note "Decision: use SQLite"
cat /tmp/nowmd-try/NOW.md
```
When things change: `python3 nowmd.py --dir /tmp/nowmd-try update --id <id> --status blocked --why "..." --fix "..."`
When finished: `python3 nowmd.py --dir /tmp/nowmd-try done --id <id> --result result.md`
Broken record? `python3 nowmd.py --dir /tmp/nowmd-try check`
Forgot an id? `python3 nowmd.py --dir /tmp/nowmd-try list` (one line per task: id, `[status]`, title)
For real use, point `--dir` at your own project folder (or run from it without `--dir`).

New in v0.2: `update` (any status change), collision-proof ids and a lock so several AIs can write at once, `check` for bad JSON/status/dates, ready-made instruction snippets in [`templates/`](templates) (Claude / Codex / Gemini / ChatGPT), a [getting-started guide](docs/GETTING_STARTED.md), and tests (`python3 -m unittest discover -s tests`).

**v0.2.1 (security fix)**: `update`/`done` now validate `--id` like `add` does (no path tricks like `../`), a lock is only taken over if its owner process is gone (`NOWMD_LOCK_STALE` / `NOWMD_LOCK_WAIT` env vars), and `check` reads under the lock. Please upgrade from v0.2.0.

**v0.2.2 (stability)**: a record with an out-of-range date (year 0001 / 9999) no longer crashes `check` / `build`; `--who` and `result` are shortened to one line, so a task can no longer forge headings in `NOW.md` or break the 120-line cap; a corrupted lock file or a bad `NOWMD_LOCK_*` value no longer crashes; new `list` command. Python 3.11+ is now the stated minimum.

**v0.2.3 (edge cases)**: `add` rejects a blank `--title`; when `NOW.md` is cut at 120 lines it says how many lines were omitted; JSON written with a BOM (some Windows editors) is read; the 30-second trial no longer modifies `examples/`; the README says what now-md is *not* (not an `AGENTS.md` replacement, not a memory tool).

**v0.2.4 (install + endurance)**: installs as a `nowmd` command with pipx; a new test runs 10 separate processes writing at once and checks nothing is lost; CI now installs the package on Linux / macOS / Windows.

### Trust and limits
`NOW.md` assumes the writers are trusted: whatever a task says ends up in the page the next AI reads. Do not put `tasks/` where untrusted people or tools can write. Use a normal local folder on one machine (not a synced or network folder).

### Tips
- Add one line to your agent instructions (CLAUDE.md / AGENTS.md / GEMINI.md…) — copy from [`templates/`](templates): "Read NOW.md first. Leave one line with `nowmd.py add / update / done / note` at each milestone."
- Run `python3 nowmd.py build` from cron every few minutes; a task stuck in `running` with no update for 60+ min gets a ⚠.
- Old task files can stay; `done` items older than 24h simply drop out of `NOW.md`.

## 日本語

**こんな人向け**: Claude・ChatGPT・Codex・Geminiなど**複数のAIを使い分けていて、AIを替えるたびに「いまどこまで進んだか」を説明し直している**人。

仕組み: 各AI(や自分)が「やること1件=小さなJSON1つ」を `tasks/` に書く。スクリプトがそれらを集めて **`NOW.md` を1枚**作る。次のAIは最初にこの1枚だけ読めばよい。`NOW.md` は手で直さない(機械が書く)ので、書き方がぶれず、読む側のトークンも少なくて済みます。AI・ネット接続なし、標準ライブラリだけ。

`NOW.md` の中身: **動いている作業 / 止まっている作業(戻し方つき)/ 直近24時間に終わった作業 / 最新のメモ・決定**。最大120行(超えたときは最後の行に `…(N行省略 / lines omitted)` と出ます)。

**他と何が違うか**
- ページはスクリプトが書くので、どのAIが記録を書いても書式がぶれません。
- 作るときにAIもネットも使わないので、読む側は短い1枚を読むぶんのトークンだけです。
- 複数のAIが同時に書けます(ロックファイル・重ならないID・原子的な置き換え)。ただし同じマシンの普通のフォルダで使う前提です。会話を保存する「メモリ」や、AIを呼ぶエージェントの枠組みではありません。
- 扱うのは「今の作業状態」(動いている・止まっている・いま終わった)だけです。`AGENTS.md` / `CLAUDE.md`(いつも守る指示)や、メモリ系ツール(長期の記憶)の代わりではありません。それらと併用し、`NOW.md` は「1時間ごとに変わるページ」として使ってください。

### インストール(任意)
```
pipx install git+https://github.com/kanazawateppei2020-spec/now-md
nowmd --version
```
入れたあとは、このREADMEの `python3 nowmd.py add ...` を `nowmd add ...` に読み替えてください。(入れなくても、`nowmd.py` は1ファイルなのでコピーするだけで使えます。)

### 30秒で試す
同梱の `examples/` を書き換えないよう、コピーで試します(Windows は好きな場所にフォルダをコピーして、そのパスを使ってください):
```
cp -r examples /tmp/nowmd-try
python3 nowmd.py --dir /tmp/nowmd-try add --who claude --title "ログイン不具合を直す" --status running
python3 nowmd.py --dir /tmp/nowmd-try add --who codex --title "テストを書く" --status blocked --why "APIキー待ち" --fix "持ち主にテスト用キーを頼む"
python3 nowmd.py --dir /tmp/nowmd-try note "決定: DBはSQLiteにする"
cat /tmp/nowmd-try/NOW.md
```
状態が変わったら: `python3 nowmd.py --dir /tmp/nowmd-try update --id <id> --status blocked --why "理由" --fix "戻し方"`
終わったら: `python3 nowmd.py --dir /tmp/nowmd-try done --id <id> --result 結果.md`
記録が壊れていないか: `python3 nowmd.py --dir /tmp/nowmd-try check`
IDを忘れたら: `python3 nowmd.py --dir /tmp/nowmd-try list`(1件1行: ID・`[状態]`・題)
本番で使うときは、`--dir` に自分のプロジェクトのフォルダを指定します(そのフォルダで実行すれば `--dir` は不要)。

v0.2 の新機能: `update`(状態の変更)、IDが重ならない・ロックで複数のAIが同時に書ける、`check`(JSON・状態・日時の検査)、[`templates/`](templates) の指示書の雛形(Claude / Codex / Gemini / ChatGPT)、[はじめかたガイド](docs/GETTING_STARTED.md)、テスト(`python3 -m unittest discover -s tests`)。

**v0.2.1(セキュリティ修正)**: `update`/`done` でも `--id` を `add` と同じ厳しさで検査(`../` などでtasks外を触れない)、ロックは「持ち主のプロセスが終わっているとき」だけ奪う(環境変数 `NOWMD_LOCK_STALE` / `NOWMD_LOCK_WAIT` で調整可)、`check` もロックを取って読む。v0.2.0 をお使いの方は更新してください。

**v0.2.2(安定性の修正)**: 範囲外の日付(0001年・9999年)の記録1件で `check` / `build` が落ちる問題を修正。`--who` と `result` は1行に短縮され、`NOW.md` に偽の見出しを入れたり120行の上限を破ったりできなくなりました。壊れたロックファイルや不正な `NOWMD_LOCK_*` の値でも落ちません。新コマンド `list`。最低バージョンは Python 3.11 と明記しました。

**v0.2.3(細かい穴の修正)**: `add` は空白だけの `--title` を拒否。`NOW.md` が120行で切れるときは「何行省略したか」を最後の行に表示。BOM付きJSON(一部のWindowsエディタ)も読めます。「30秒で試す」は同梱の `examples/` を書き換えない手順に変更。「他と何が違うか」に、`AGENTS.md`・メモリ系ツールとの住み分けを追記しました。

**v0.2.4(インストールと耐久テスト)**: pipx で `nowmd` コマンドとして入ります。別々のプロセス10個が同時に書いても何も失われないことを確かめるテストを追加。CIは Linux / macOS / Windows でパッケージのインストールも確認します。

### 信頼と限界
`NOW.md` は「書き手を信頼する」前提です。タスクに書かれた文字は、次のAIが読むページにそのまま入ります。信頼できない人やツールが書き込める場所に `tasks/` を置かないでください。同期フォルダやネットワーク共有ではなく、1台のマシンの普通のフォルダで使ってください。

### 使い方のコツ
- AIへの指示書(CLAUDE.md / AGENTS.md / GEMINI.md 等)に「作業の最初に NOW.md を読む。節目に `nowmd.py add / update / done / note` で1行残す」と1行書くだけ([`templates/`](templates) からコピー)。
- cron や launchd で `python3 nowmd.py build` を数分おきに回すと、`running` のまま長時間更新が無い作業に ⚠ が付きます。
- `tasks/` の記録は消さずに溜めてOK(24時間より古い `done` は `NOW.md` に出ません)。

## Related writing (Japanese) / 関連記事
The tool above is free and complete on its own. These are optional Japanese write-ups by the author:
- Series / 連載マガジン: https://note.com/teppei_lil_white/m/m5d06e069f1fd
- Author on note: https://note.com/teppei_lil_white

## License
MIT — see [LICENSE](LICENSE).
