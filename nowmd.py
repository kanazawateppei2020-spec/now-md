#!/usr/bin/env python3
"""nowmd.py — build ONE page (NOW.md) that any AI (Claude, ChatGPT, Codex, Gemini…) reads first to know the current state.
複数のAIに引き継ぐための「いまの状況.md」を、小さなJSONの記録から機械で作る(AI不使用・標準ライブラリだけ)。

Each task = one small JSON file in ./tasks/ . Each AI (or you) writes its own line; nobody edits NOW.md by hand.

  python3 nowmd.py add  --who claude --title "Fix login bug" --status running
  python3 nowmd.py add  --who codex  --title "Write tests" --status blocked --why "needs API key" --fix "ask the owner for a test key"
  python3 nowmd.py done --id <id> [--result path/to/result.md]
  python3 nowmd.py note "Decision: use SQLite, not Postgres"
  python3 nowmd.py build            # (re)writes NOW.md  — run it from cron every few minutes if you like

Status: running | waiting | blocked | failed | done
Folder: --dir DIR (default: current folder; uses DIR/tasks/, DIR/notes.md, DIR/NOW.md)
"""
import argparse, datetime, glob, json, os, re, sys

MAX_LINES = 120


def now():
    return datetime.datetime.now().astimezone()


def clip(t, n=100):
    return re.sub(r"\s+", " ", str(t)).strip()[:n]


def parse(s):
    try:
        return datetime.datetime.fromisoformat(s)
    except Exception:
        return None


def hm(s):
    d = parse(s)
    return d.astimezone().strftime("%m/%d %H:%M") if d else "?"


def load_tasks(base):
    out = []
    for f in sorted(glob.glob(os.path.join(base, "tasks", "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def save_task(base, d):
    os.makedirs(os.path.join(base, "tasks"), exist_ok=True)
    p = os.path.join(base, "tasks", d["id"] + ".json")
    tmp = p + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def build(base, stale_min=60):
    n = now()
    tasks = load_tasks(base)
    running, stuck, done = [], [], []
    for t in tasks:
        st = t.get("status", "waiting")
        title, who = clip(t.get("title", ""), 60), t.get("who", "?")
        upd = parse(t.get("updated", ""))
        if st == "running":
            stale = upd and (n - upd).total_seconds() > stale_min * 60
            running.append(f"- {title} ({who}) since {hm(t.get('started') or t.get('updated'))}" + (f"  ⚠ no update for {stale_min}+ min — check it" if stale else ""))
        elif st in ("blocked", "failed", "waiting"):
            line = f"- [{st}] {title} ({who}) — why: {clip(t.get('why', '?'), 70)}"
            if t.get("fix"):
                line += f" / how to unblock: {clip(t['fix'], 70)}"
            stuck.append(line)
        elif st == "done" and upd and upd > n - datetime.timedelta(hours=24):
            r = f" → {t['result']}" if t.get("result") else ""
            done.append((t.get("updated", ""), f"- {hm(t.get('updated'))} {title} ({who}){r}"))
    done = [x[1] for x in sorted(done, reverse=True)]
    notes = []
    try:
        notes = [clip(l.rstrip(), 160) for l in open(os.path.join(base, "notes.md"), encoding="utf-8") if l.startswith("- ")][-10:]
    except Exception:
        pass

    def sec(title, lines):
        return ["", f"## {title}"] + (lines or ["- none"])

    out = ["# NOW (written by a script — do not edit by hand)",
           f"- built: {n:%Y-%m-%d %H:%M}   / read this one page first; details live in each task's result file"]
    out += sec("Running", running) + sec("Stuck (and how to unblock)", stuck) + sec("Done in the last 24h", done[:12]) + sec("Latest notes / decisions", notes)
    lines = out[:MAX_LINES - 1] + (["…(truncated)"] if len(out) > MAX_LINES else [])
    path = os.path.join(base, "NOW.md")
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return path, len(lines)


def main():
    ap = argparse.ArgumentParser(description="Build NOW.md for AI handoff")
    ap.add_argument("cmd", choices=["add", "done", "note", "build"])
    ap.add_argument("text", nargs="?")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--who"); ap.add_argument("--title"); ap.add_argument("--status", default="running")
    ap.add_argument("--why"); ap.add_argument("--fix"); ap.add_argument("--id"); ap.add_argument("--result")
    a = ap.parse_args()
    base = os.path.abspath(a.dir)
    n = now().isoformat(timespec="seconds")
    if a.cmd == "add":
        if not (a.who and a.title):
            sys.exit("add needs --who and --title")
        if a.status not in ("running", "waiting", "blocked", "failed", "done"):
            sys.exit("status: running|waiting|blocked|failed|done")
        tid = a.id or now().strftime("%Y%m%d_%H%M%S") + "_" + re.sub(r"[^a-z0-9]+", "", a.who.lower())[:8]
        d = {"id": tid, "who": a.who, "title": a.title, "status": a.status, "started": n, "updated": n}
        if a.why: d["why"] = a.why
        if a.fix: d["fix"] = a.fix
        save_task(base, d); print("added", tid)
    elif a.cmd == "done":
        p = os.path.join(base, "tasks", (a.id or "") + ".json")
        if not a.id or not os.path.exists(p):
            sys.exit("done needs an existing --id")
        d = json.load(open(p, encoding="utf-8")); d.update(status="done", updated=n)
        if a.result: d["result"] = a.result
        save_task(base, d); print("done", a.id)
    elif a.cmd == "note":
        if not a.text:
            sys.exit('note needs text: nowmd.py note "..."')
        with open(os.path.join(base, "notes.md"), "a", encoding="utf-8") as f:
            f.write(f"- {now():%m/%d %H:%M} {clip(a.text, 150)}\n")
        print("noted")
    path, k = build(base)
    print(f"wrote {path} ({k} lines)")


if __name__ == "__main__":
    main()
